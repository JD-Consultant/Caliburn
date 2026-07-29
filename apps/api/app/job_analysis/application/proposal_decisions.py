"""Durable employee decisions for Task Proposals."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import ValidationError

from app.job_analysis.domain import (
    CurrentWorkModel,
    JdEntry,
    JdTask,
    Proposal,
    ProposalAction,
    ProposalStatus,
    SourceKind,
    SourceRef,
    StagedWorkModelDelta,
    Task,
    TaskId,
    is_allowed_transition,
    jd_map,
)

from .authoring import (
    ConcurrentAuthorityChange,
    DocumentNotFound,
    IdempotencyConflict,
    JobAnalysisApplicationError,
)
from .persistence import (
    PROPOSAL_DECISION_SCHEMA_ID,
    DocumentRecord,
    JobAnalysisUnitOfWork,
    JobAnalysisUnitOfWorkFactory,
    JournalEntry,
    ProposalDecisionPayload,
)
from .transition import JobAnalysisState


ProposalDecision = Literal[
    "accepted",
    "edited",
    "rejected",
    "deferred",
    "revision_requested",
]


class ProposalNotFound(JobAnalysisApplicationError):
    pass


class ProposalNotDecidable(JobAnalysisApplicationError):
    pass


class InvalidProposalDecision(JobAnalysisApplicationError):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _replace_proposal(
    proposals: tuple[Proposal, ...],
    decided: Proposal,
) -> tuple[Proposal, ...]:
    return tuple(
        decided if proposal.proposal_id == decided.proposal_id else proposal
        for proposal in proposals
    )


def _jd_matches_before(
    current_jd: tuple[JdTask, ...],
    proposal: Proposal,
) -> bool:
    current = {task.task_id: task for task in current_jd}
    return all(
        current.get(entry.task_id) == entry.value
        for entry in proposal.jd_before
    )


def _apply_jd_entries(
    current_jd: tuple[JdTask, ...],
    entries: tuple[JdEntry, ...],
) -> tuple[JdTask, ...]:
    result = {task.task_id: task for task in current_jd}
    for entry in entries:
        if entry.value is None:
            result.pop(entry.task_id, None)
        else:
            result[entry.task_id] = entry.value
    return tuple(
        sorted(result.values(), key=lambda task: (task.display_order, task.task_id))
    )


def _apply_staged_delta(
    work_model: CurrentWorkModel,
    delta: StagedWorkModelDelta | None,
) -> CurrentWorkModel:
    if delta is None:
        return work_model

    tasks = {task.task_id: task for task in work_model.tasks}
    lineage = {change.task_id: change for change in delta.lineage_changes}
    for staged in delta.new_tasks:
        change = lineage.get(staged.task_id)
        tasks[staged.task_id] = Task(
            task_id=staged.task_id,
            **staged.fields.model_dump(),
            support_links=staged.support_links,
            split_from=change.split_from if change is not None else None,
        )
    for change in delta.lineage_changes:
        task = tasks.get(change.task_id)
        if task is None:
            raise InvalidProposalDecision(
                f"staged delta refers to unknown Task {change.task_id!r}"
            )
        tasks[change.task_id] = Task.model_validate(
            {
                **task.model_dump(),
                "retirement": (
                    change.retirement.model_dump()
                    if change.retirement is not None
                    else None
                ),
                "merged_into": change.merged_into,
                "split_from": change.split_from,
                "pending_reconciliation": (
                    None
                    if change.retirement is not None
                    else task.pending_reconciliation
                ),
            }
        )
    return CurrentWorkModel(
        tasks=tuple(tasks.values()),
        open_issues=work_model.open_issues,
        excluded_signals=work_model.excluded_signals,
    )


def _mark_reconciliation(
    work_model: CurrentWorkModel,
    *,
    task_ids: set[TaskId],
    decision_id: str,
) -> CurrentWorkModel:
    source = SourceRef(kind=SourceKind.PROPOSAL_DECISION, id=decision_id)
    available = {
        task.task_id for task in work_model.tasks if task.retirement is None
    }
    missing = task_ids - available
    if missing:
        raise InvalidProposalDecision(
            f"cannot reconcile unknown or retired Tasks: {sorted(missing)}"
        )
    tasks: list[Task] = []
    for task in work_model.tasks:
        if task.task_id in task_ids and task.retirement is None:
            tasks.append(
                Task.model_validate(
                    {
                        **task.model_dump(),
                        "pending_reconciliation": source.model_dump(),
                    }
                )
            )
        else:
            tasks.append(task)
    return CurrentWorkModel(
        tasks=tuple(tasks),
        open_issues=work_model.open_issues,
        excluded_signals=work_model.excluded_signals,
    )


def _validate_request_payload(
    decision: ProposalStatus,
    *,
    edited_jd_after: tuple[JdEntry, ...] | None,
    reason: str | None,
    excluded_member_task_ids: tuple[TaskId, ...],
    excluded_child_refs: tuple[TaskId, ...],
) -> None:
    if decision is ProposalStatus.EDITED:
        if edited_jd_after is None:
            raise InvalidProposalDecision("edited decision requires edited_jd_after")
    elif edited_jd_after is not None:
        raise InvalidProposalDecision(
            "edited_jd_after belongs to the edited decision only"
        )

    if reason is not None and decision is not ProposalStatus.REJECTED:
        raise InvalidProposalDecision("reason belongs to the rejected decision only")

    excluded = bool(excluded_member_task_ids or excluded_child_refs)
    if decision is ProposalStatus.REVISION_REQUESTED:
        if not excluded:
            raise InvalidProposalDecision(
                "revision_requested requires an excluded member or child"
            )
    elif excluded:
        raise InvalidProposalDecision(
            "excluded members and children belong to revision_requested only"
        )


def _decided_value(
    proposal: Proposal,
    *,
    decision: ProposalStatus,
    edited_jd_after: tuple[JdEntry, ...] | None,
    reason: str | None,
    excluded_member_task_ids: tuple[TaskId, ...],
    excluded_child_refs: tuple[TaskId, ...],
) -> Proposal:
    try:
        return Proposal.model_validate(
            {
                **proposal.model_dump(),
                "status": decision,
                "edited_jd_after": (
                    tuple(entry.model_dump() for entry in edited_jd_after)
                    if edited_jd_after is not None
                    else None
                ),
                "rejection_reason": (
                    reason if decision is ProposalStatus.REJECTED else None
                ),
                "excluded_member_task_ids": excluded_member_task_ids,
                "excluded_child_refs": excluded_child_refs,
            }
        )
    except ValidationError as error:
        raise InvalidProposalDecision(
            error.errors()[0]["msg"]
        ) from error


def _require_same_replay(
    entry: JournalEntry,
    *,
    proposal: Proposal,
    proposal_id: str,
    decision: ProposalStatus,
    reason: str | None,
    edited_jd_after: tuple[JdEntry, ...] | None,
    excluded_member_task_ids: tuple[TaskId, ...],
    excluded_child_refs: tuple[TaskId, ...],
) -> None:
    if entry.kind != "proposal_decision" or not isinstance(
        entry.payload,
        ProposalDecisionPayload,
    ):
        raise IdempotencyConflict(
            f"entry {entry.entry_id!r} already belongs to another operation"
        )
    payload = entry.payload
    if (
        payload.proposal_id != proposal_id
        or payload.decision is not decision
        or payload.reason != reason
    ):
        raise IdempotencyConflict(
            f"decision {entry.entry_id!r} was replayed with another payload"
        )
    if decision is ProposalStatus.EDITED and (
        proposal.edited_jd_after != edited_jd_after
    ):
        raise IdempotencyConflict(
            f"decision {entry.entry_id!r} was replayed with other edited text"
        )
    if decision is ProposalStatus.REVISION_REQUESTED and (
        proposal.excluded_member_task_ids != excluded_member_task_ids
        or proposal.excluded_child_refs != excluded_child_refs
    ):
        raise IdempotencyConflict(
            f"decision {entry.entry_id!r} was replayed with other exclusions"
        )


async def _persist(
    uow: JobAnalysisUnitOfWork,
    *,
    record: DocumentRecord,
    work_model: CurrentWorkModel,
    current_jd: tuple[JdTask, ...],
    proposals: tuple[Proposal, ...],
    journal_entry: JournalEntry | None,
) -> None:
    now = _utcnow()
    # Validate the complete two-layer state before issuing any writes.
    JobAnalysisState(
        work_model=work_model,
        current_jd=current_jd,
        proposals=proposals,
    )
    await uow.tasks.replace(record.document_id, current_jd)
    await uow.proposals.replace(record.document_id, proposals)
    if journal_entry is not None:
        await uow.journal.add(journal_entry)
    updated = await uow.documents.update_authority(
        record.document_id,
        expected_generation=record.authority_generation,
        work_model=work_model,
        active_question=record.active_question,
        updated_at=now,
    )
    if not updated:
        raise ConcurrentAuthorityChange(
            f"document {record.document_id} authority changed concurrently"
        )
    await uow.commit()


async def decide_proposal(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    proposal_id: str,
    decision_id: str,
    decision: ProposalDecision,
    edited_jd_after: tuple[JdEntry, ...] | None = None,
    reason: str | None = None,
    excluded_member_task_ids: tuple[TaskId, ...] = (),
    excluded_child_refs: tuple[TaskId, ...] = (),
) -> Proposal:
    try:
        target_status = ProposalStatus(decision)
    except ValueError as error:
        raise InvalidProposalDecision(f"unknown decision {decision!r}") from error
    _validate_request_payload(
        target_status,
        edited_jd_after=edited_jd_after,
        reason=reason,
        excluded_member_task_ids=excluded_member_task_ids,
        excluded_child_refs=excluded_child_refs,
    )

    async with uow_factory() as uow:
        record = await uow.documents.get(document_id, for_update=True)
        if record is None:
            raise DocumentNotFound(f"document {document_id} was not found")
        proposals = await uow.proposals.list(document_id)
        proposal = next(
            (item for item in proposals if item.proposal_id == proposal_id),
            None,
        )
        if proposal is None:
            raise ProposalNotFound(f"proposal {proposal_id!r} was not found")

        replay = await uow.journal.get(document_id, decision_id)
        if replay is not None:
            _require_same_replay(
                replay,
                proposal=proposal,
                proposal_id=proposal_id,
                decision=target_status,
                reason=reason,
                edited_jd_after=edited_jd_after,
                excluded_member_task_ids=excluded_member_task_ids,
                excluded_child_refs=excluded_child_refs,
            )
            return proposal

        if not is_allowed_transition(proposal.status, target_status):
            raise ProposalNotDecidable(
                f"proposal {proposal_id!r} cannot move from "
                f"{proposal.status.value!r} to {target_status.value!r}"
            )

        current_jd = await uow.tasks.list(document_id)
        if not _jd_matches_before(current_jd, proposal):
            stale = Proposal.model_validate(
                {
                    **proposal.model_dump(),
                    "status": ProposalStatus.STALE,
                    "stale_reason": (
                        "Current JD 已在提案建立後變更，請重新產生提案。"
                    ),
                }
            )
            await _persist(
                uow,
                record=record,
                work_model=record.work_model,
                current_jd=current_jd,
                proposals=_replace_proposal(proposals, stale),
                journal_entry=None,
            )
            return stale

        decided = _decided_value(
            proposal,
            decision=target_status,
            edited_jd_after=edited_jd_after,
            reason=reason,
            excluded_member_task_ids=excluded_member_task_ids,
            excluded_child_refs=excluded_child_refs,
        )
        next_jd = current_jd
        work_model = record.work_model
        if target_status in {ProposalStatus.ACCEPTED, ProposalStatus.EDITED}:
            entries = (
                decided.edited_jd_after
                if target_status is ProposalStatus.EDITED
                else decided.jd_after
            )
            assert entries is not None
            next_jd = _apply_jd_entries(current_jd, entries)
            work_model = _apply_staged_delta(
                work_model,
                decided.staged_work_model_delta,
            )
            active = {
                task.task_id
                for task in work_model.tasks
                if task.retirement is None
            }
            required = {
                entry.task_id
                for entry in entries
                if entry.value is not None
            }
            missing = required - active
            if missing:
                raise InvalidProposalDecision(
                    "accepted JD content lacks active Work Model Tasks: "
                    f"{sorted(missing)}"
                )
            if target_status is ProposalStatus.EDITED:
                work_model = _mark_reconciliation(
                    work_model,
                    task_ids=required,
                    decision_id=decision_id,
                )
        elif target_status is ProposalStatus.REJECTED and proposal.action in {
            ProposalAction.ADD,
            ProposalAction.REVISE,
        }:
            work_model = _mark_reconciliation(
                work_model,
                task_ids=set(proposal.affected_task_ids),
                decision_id=decision_id,
            )

        now = _utcnow()
        journal_entry = JournalEntry(
            document_id=document_id,
            entry_id=decision_id,
            kind="proposal_decision",
            payload_schema_id=PROPOSAL_DECISION_SCHEMA_ID,
            payload=ProposalDecisionPayload(
                proposal_id=proposal_id,
                decision=target_status,
                reason=reason,
            ),
            created_at=now,
        )
        await _persist(
            uow,
            record=record,
            work_model=work_model,
            current_jd=next_jd,
            proposals=_replace_proposal(proposals, decided),
            journal_entry=journal_entry,
        )
        return decided
