"""Prepare and commit one Task Analysis turn without holding a DB lock over LLM I/O."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID

from .authority_commit import commit_authority_change
from .errors import (
    ConcurrentAuthorityChange,
    DocumentNotFound,
    IdempotencyConflict,
    JobAnalysisApplicationError,
)
from .context import (
    ActiveQuestion,
    ConversationTurn,
    TaskAnalysisPacket,
    build_context_packet,
)
from .operation import OperationOutcome, TaskAnalysisOperationResult
from .opks_digest import ScheduledOpks
from .opks_scheduler import question_target_task_ids, select_scheduled_opks
from .persistence import (
    COMPLETED_TURN_SCHEMA_ID,
    CompletedTurnPayload,
    DocumentRecord,
    JobAnalysisUnitOfWork,
    JobAnalysisUnitOfWorkFactory,
    JournalEntry,
)
from .transition import (
    JobAnalysisState,
    TransitionOutcome,
    TransitionResult,
    apply_task_analysis_result,
)
from .verifier import TurnSpeaker


class StaleAuthoritySnapshot(ConcurrentAuthorityChange):
    """The model read authority that is no longer current."""


class UncommittableOperationResult(JobAnalysisApplicationError):
    """Only a verified operation result may change Current State."""


class TransitionCommitRejected(JobAnalysisApplicationError):
    """The pure transition rejected a result before persistence."""


@dataclass(frozen=True)
class TurnSnapshot:
    document_id: UUID
    authority_generation: int
    state: JobAnalysisState
    packet: TaskAnalysisPacket


@dataclass(frozen=True)
class CommittedTurn:
    """一個已提交的員工回合,連同它凍結的唯一 OPKS child(決定 7–8)。

    `scheduled_opks` 為 `None` 表示這一輪沒有排定分析。replay 回傳的是**既存**
    payload 裡那一筆,不是重算的結果。
    """

    transition: TransitionResult
    scheduled_opks: ScheduledOpks | None = None

    @property
    def is_applied(self) -> bool:
        return self.transition.is_applied

    @property
    def state(self) -> JobAnalysisState:
        return self.transition.state


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _load_state(
    uow: JobAnalysisUnitOfWork,
    record: DocumentRecord,
) -> JobAnalysisState:
    return JobAnalysisState(
        jd_header=record.jd_header,
        current_duties=await uow.duties.list(record.document_id),
        work_model=record.work_model,
        current_jd=await uow.tasks.list(record.document_id),
        proposals=await uow.proposals.list(record.document_id),
        current_opks={"items": await uow.opks.list(record.document_id)},
        opks_proposals=await uow.opks_proposals.list(record.document_id),
    )


async def _packet_for(
    uow: JobAnalysisUnitOfWork,
    *,
    record: DocumentRecord,
    state: JobAnalysisState,
    employee_turn: ConversationTurn,
) -> TaskAnalysisPacket:
    conversation = await uow.journal.list_conversation_turns(record.document_id)
    overview_lines = tuple(
        line
        for line in (
            (
                f"職能基準名稱：{record.jd_header.competency_name}"
                if record.jd_header.competency_name is not None
                else None
            ),
            (
                f"工作描述：{record.jd_header.work_description}"
                if record.jd_header.work_description is not None
                else None
            ),
        )
        if line is not None
    )
    return build_context_packet(
        transcript=(*conversation, employee_turn),
        current_turn_id=employee_turn.turn_id,
        work_model=state.work_model,
        current_jd=state.current_jd,
        active_question=record.active_question,
        proposals=state.proposals,
        employee_written_overview="\n".join(overview_lines) or None,
    )


async def prepare_turn(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    employee_turn: ConversationTurn,
) -> TurnSnapshot:
    """Read one immutable authority snapshot, then close the transaction."""

    async with uow_factory() as uow:
        record = await uow.documents.get(document_id)
        if record is None:
            raise DocumentNotFound(f"document {document_id} was not found")
        state = await _load_state(uow, record)
        packet = await _packet_for(
            uow,
            record=record,
            state=state,
            employee_turn=employee_turn,
        )
        return TurnSnapshot(
            document_id=document_id,
            authority_generation=record.authority_generation,
            state=state,
            packet=packet,
        )


def _consultant_turn(
    operation_id: str,
    operation_result: TaskAnalysisOperationResult,
) -> ConversationTurn:
    result = operation_result.result
    assert result is not None
    return ConversationTurn(
        turn_id=f"{operation_id}-consultant",
        speaker=TurnSpeaker.CONSULTANT,
        text=result.next_question.text,
    )


def _require_verified(
    operation_result: TaskAnalysisOperationResult,
) -> None:
    if (
        operation_result.outcome is not OperationOutcome.VERIFIED
        or operation_result.result is None
    ):
        raise UncommittableOperationResult(
            f"cannot commit operation outcome {operation_result.outcome.value!r}"
        )


def _require_same_replay(
    entry: JournalEntry,
    *,
    operation_id: str,
    employee_turn: ConversationTurn,
    consultant_turn: ConversationTurn,
) -> CompletedTurnPayload:
    """確認這是同一個回合的重播,並交回**已凍結**的 payload。

    **刻意不比對 `scheduled_opks`。** 綁定在 receipt 寫入時就凍結了(決定 8);
    replay 一律以既存 payload 為準,不重算——重算會讓 scheduler 依當下 state 改選
    下一個 Task,同一個員工回合因此付兩次錢。
    """

    if entry.kind != "employee_turn" or not isinstance(
        entry.payload,
        CompletedTurnPayload,
    ):
        raise IdempotencyConflict(
            f"entry {operation_id!r} already belongs to another operation"
        )
    payload = entry.payload
    if (
        payload.operation_id != operation_id
        or payload.employee_turn != employee_turn
        or payload.consultant_turn != consultant_turn
    ):
        raise IdempotencyConflict(
            f"operation {operation_id!r} was replayed with different turns"
        )
    return payload


async def commit_verified_turn(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    snapshot: TurnSnapshot,
    operation_id: str,
    employee_turn: ConversationTurn,
    operation_result: TaskAnalysisOperationResult,
) -> CommittedTurn:
    """Apply a verified result only if the exact authority it read is still current."""

    _require_verified(operation_result)
    consultant_turn = _consultant_turn(operation_id, operation_result)

    async with uow_factory() as uow:
        record = await uow.documents.get(snapshot.document_id, for_update=True)
        if record is None:
            raise DocumentNotFound(f"document {snapshot.document_id} was not found")
        state = await _load_state(uow, record)

        existing = await uow.journal.get(snapshot.document_id, operation_id)
        if existing is not None:
            frozen = _require_same_replay(
                existing,
                operation_id=operation_id,
                employee_turn=employee_turn,
                consultant_turn=consultant_turn,
            )
            return CommittedTurn(
                transition=TransitionResult(
                    outcome=TransitionOutcome.APPLIED,
                    state=state,
                    detail="operation was already committed",
                ),
                scheduled_opks=frozen.scheduled_opks,
            )

        current_packet = await _packet_for(
            uow,
            record=record,
            state=state,
            employee_turn=employee_turn,
        )
        if (
            record.authority_generation != snapshot.authority_generation
            or current_packet.read_set != snapshot.packet.read_set
            or current_packet.conversation_context
            != snapshot.packet.conversation_context
        ):
            raise StaleAuthoritySnapshot(
                "the document changed after this Task Analysis turn was prepared"
            )

        assert operation_result.result is not None
        transition = apply_task_analysis_result(
            state=state,
            packet=snapshot.packet,
            result=operation_result.result,
            operation_id=operation_id,
        )
        if not transition.is_applied:
            raise TransitionCommitRejected(
                transition.detail or "the verified result could not be applied"
            )

        now = _utcnow()
        active_question = ActiveQuestion(
            turn_id=consultant_turn.turn_id,
            text=consultant_turn.text,
        )
        # 用 **post-transition** state 排定:本輪剛加進 Current JD 的 Task 也該排得到。
        assert operation_result.result is not None
        scheduled_opks = await select_scheduled_opks(
            uow,
            document_id=snapshot.document_id,
            state=transition.state,
            question_task_ids=question_target_task_ids(
                result=operation_result.result,
                packet=snapshot.packet,
                operation_id=operation_id,
            ),
        )
        try:
            await commit_authority_change(
                uow,
                record=replace(record, active_question=active_question),
                state=transition.state,
                updated_at=now,
                journal_entries=(
                    JournalEntry(
                        document_id=snapshot.document_id,
                        entry_id=operation_id,
                        kind="employee_turn",
                        payload_schema_id=COMPLETED_TURN_SCHEMA_ID,
                        payload=CompletedTurnPayload(
                            operation_id=operation_id,
                            employee_turn=employee_turn,
                            consultant_turn=consultant_turn,
                            scheduled_opks=scheduled_opks,
                        ),
                        created_at=now,
                    ),
                ),
            )
        except ConcurrentAuthorityChange as error:
            raise StaleAuthoritySnapshot(
                "the document changed while this Task Analysis turn was committed"
            ) from error
        return CommittedTurn(transition=transition, scheduled_opks=scheduled_opks)
