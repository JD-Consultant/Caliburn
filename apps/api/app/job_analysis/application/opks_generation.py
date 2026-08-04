"""Provider-outside-transaction 的 durable OPKS Proposal generation。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.job_analysis.domain import (
    CurrentJdOpks,
    OpksProposal,
    Task,
    TaskState,
)
from app.job_analysis.providers import OpenRouterAdapter

from .authority_commit import commit_authority_change
from .durable_turn import StaleAuthoritySnapshot, UncommittableOperationResult
from .errors import DocumentNotFound, IdempotencyConflict, JdTaskNotFound
from .operation import OperationOutcome
from .opks_context import (
    OpksContextPacket,
    OpksGroundingUnavailable,
    build_opks_context_packet,
)
from .opks_operation import OpksOperationResult, run_opks_operation
from .persistence import (
    OPKS_GENERATION_SCHEMA_ID,
    DocumentRecord,
    JobAnalysisUnitOfWork,
    JobAnalysisUnitOfWorkFactory,
    JournalEntry,
    OpksGenerationOutcome,
    OpksGenerationPayload,
)
from .transition import JobAnalysisState


@dataclass(frozen=True)
class OpksGenerationSnapshot:
    document_id: UUID
    authority_generation: int
    selected_task_id: str
    state: JobAnalysisState
    packet: OpksContextPacket


class OpksGenerationResult(OpksGenerationPayload):
    """回 API 的 typed result；沿用 receipt 的可重播內容。"""


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _load_state(
    uow: JobAnalysisUnitOfWork,
    record: DocumentRecord,
) -> JobAnalysisState:
    return JobAnalysisState(
        jd_header=record.jd_header,
        work_model=record.work_model,
        current_jd=await uow.tasks.list(record.document_id),
        proposals=await uow.proposals.list(record.document_id),
        current_opks=CurrentJdOpks(
            items=await uow.opks.list(record.document_id)
        ),
        opks_proposals=await uow.opks_proposals.list(record.document_id),
    )


def _selected_task(state: JobAnalysisState, task_id: str) -> Task:
    if task_id not in state.current_jd_task_ids:
        raise JdTaskNotFound(f"Current JD task {task_id!r} was not found")
    task = state.work_model.task_by_id(task_id)
    if task is None:
        raise OpksGroundingUnavailable(
            "selected Current JD task has not been reconciled into the Work Model"
        )
    if task.state is not TaskState.ACTIVE:
        raise OpksGroundingUnavailable(
            "selected task is not stable enough for OPKS generation"
        )
    return task


def _packet_for(state: JobAnalysisState, task_id: str) -> OpksContextPacket:
    return build_opks_context_packet(
        selected_task=_selected_task(state, task_id),
        current_opks=state.current_opks,
        proposals=state.opks_proposals,
    )


def _result(payload: OpksGenerationPayload) -> OpksGenerationResult:
    return OpksGenerationResult.model_validate(payload.model_dump())


def _require_generation_replay(
    entry: JournalEntry,
    *,
    operation_id: str,
    task_id: str,
) -> OpksGenerationResult:
    if entry.kind != "opks_generation" or not isinstance(
        entry.payload, OpksGenerationPayload
    ):
        raise IdempotencyConflict(
            f"entry {operation_id!r} already belongs to another operation"
        )
    if (
        entry.payload.operation_id != operation_id
        or entry.payload.selected_task_id != task_id
    ):
        raise IdempotencyConflict(
            f"operation {operation_id!r} was replayed for another Task"
        )
    return _result(entry.payload)


async def _committed_replay(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    operation_id: str,
    task_id: str,
) -> OpksGenerationResult | None:
    async with uow_factory() as uow:
        existing = await uow.journal.get(document_id, operation_id)
        if existing is None:
            return None
        return _require_generation_replay(
            existing,
            operation_id=operation_id,
            task_id=task_id,
        )


async def prepare_opks_generation(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    task_id: str,
) -> OpksGenerationSnapshot:
    async with uow_factory() as uow:
        record = await uow.documents.get(document_id)
        if record is None:
            raise DocumentNotFound(f"document {document_id} was not found")
        state = await _load_state(uow, record)
        return OpksGenerationSnapshot(
            document_id=document_id,
            authority_generation=record.authority_generation,
            selected_task_id=task_id,
            state=state,
            packet=_packet_for(state, task_id),
        )


def _require_verified(operation_result: OpksOperationResult) -> None:
    if (
        operation_result.outcome is not OperationOutcome.VERIFIED
        or operation_result.report is None
        or not operation_result.report.is_valid
    ):
        raise UncommittableOperationResult(
            f"cannot commit OPKS operation outcome {operation_result.outcome.value!r}"
        )


async def commit_opks_generation(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    snapshot: OpksGenerationSnapshot,
    operation_id: str,
    operation_result: OpksOperationResult,
) -> OpksGenerationResult:
    _require_verified(operation_result)
    assert operation_result.report is not None

    async with uow_factory() as uow:
        record = await uow.documents.get(snapshot.document_id, for_update=True)
        if record is None:
            raise DocumentNotFound(f"document {snapshot.document_id} was not found")
        state = await _load_state(uow, record)

        existing = await uow.journal.get(snapshot.document_id, operation_id)
        if existing is not None:
            return _require_generation_replay(
                existing,
                operation_id=operation_id,
                task_id=snapshot.selected_task_id,
            )

        try:
            current_packet = _packet_for(state, snapshot.selected_task_id)
        except (JdTaskNotFound, OpksGroundingUnavailable) as error:
            raise StaleAuthoritySnapshot(
                "selected Task changed while OPKS generation was running"
            ) from error
        if (
            record.authority_generation != snapshot.authority_generation
            or current_packet.read_set != snapshot.packet.read_set
        ):
            raise StaleAuthoritySnapshot(
                "the document changed after OPKS generation was prepared"
            )

        now = _utcnow()
        additions = tuple(
            OpksProposal(
                proposal_id=f"{operation_id}-op{change.source_index}",
                operation_id=operation_id,
                entity_id=change.entity_id,
                entity_kind=change.entity_kind,
                action=change.action,
                before=change.before,
                after=change.after,
                base_authority_generation=record.authority_generation,
                created_at=now,
            )
            for change in operation_result.report.changes
        )
        proposal_ids = tuple(proposal.proposal_id for proposal in additions)
        outcome = (
            OpksGenerationOutcome.PROPOSED
            if proposal_ids
            else OpksGenerationOutcome.NO_GROUNDED_CANDIDATES
        )
        payload = OpksGenerationPayload(
            operation_id=operation_id,
            selected_task_id=snapshot.selected_task_id,
            outcome=outcome,
            proposal_ids=proposal_ids,
        )
        next_state = state.model_copy(
            update={"opks_proposals": (*state.opks_proposals, *additions)}
        )
        await commit_authority_change(
            uow,
            record=record,
            state=next_state,
            updated_at=now,
            journal_entries=(
                JournalEntry(
                    document_id=snapshot.document_id,
                    entry_id=operation_id,
                    kind="opks_generation",
                    payload_schema_id=OPKS_GENERATION_SCHEMA_ID,
                    payload=payload,
                    created_at=now,
                ),
            ),
        )
        return _result(payload)


async def generate_opks_proposals(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    adapter: OpenRouterAdapter,
    document_id: UUID,
    task_id: str,
    operation_id: str,
) -> OpksGenerationResult:
    replay = await _committed_replay(
        uow_factory,
        document_id=document_id,
        operation_id=operation_id,
        task_id=task_id,
    )
    if replay is not None:
        return replay
    snapshot = await prepare_opks_generation(
        uow_factory,
        document_id=document_id,
        task_id=task_id,
    )
    operation_result = await run_opks_operation(
        packet=snapshot.packet,
        adapter=adapter,
        operation_id=operation_id,
    )
    return await commit_opks_generation(
        uow_factory,
        snapshot=snapshot,
        operation_id=operation_id,
        operation_result=operation_result,
    )
