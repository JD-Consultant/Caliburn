"""Durable employee authoring use cases for Current JD Duties."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.core.domain import CurrentJdOpks, Duty, DutyId, JdTask, Proposal

from app.core.authority import commit_authority_change
from app.core.journal import (
    DUTY_DIRECT_EDIT_SCHEMA_ID,
    DutyDirectEditPayload,
    JournalEntry,
)
from app.core.persistence import (
    DocumentRecord,
    JobAnalysisUnitOfWork,
    JobAnalysisUnitOfWorkFactory,
)

from .authoring import stale_task_proposals_for_direct_edit
from .errors import (
    DocumentNotFound,
    DutyNotFound,
    IdempotencyConflict,
    InvalidDutyOrder,
)
from .transition import JobAnalysisState


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _locked_document(
    uow: JobAnalysisUnitOfWork,
    document_id: UUID,
) -> DocumentRecord:
    record = await uow.documents.get(document_id, for_update=True)
    if record is None:
        raise DocumentNotFound(f"document {document_id} was not found")
    return record


def _require_duty_direct_edit(entry: JournalEntry) -> DutyDirectEditPayload:
    if entry.kind != "direct_edit" or not isinstance(
        entry.payload,
        DutyDirectEditPayload,
    ):
        raise IdempotencyConflict(
            f"entry {entry.entry_id!r} already belongs to another operation"
        )
    return entry.payload


async def _state(
    uow: JobAnalysisUnitOfWork,
    *,
    record: DocumentRecord,
    current_duties: tuple[Duty, ...],
    current_jd: tuple[JdTask, ...],
    proposals: tuple[Proposal, ...],
) -> JobAnalysisState:
    return JobAnalysisState(
        jd_header=record.jd_header,
        current_duties=current_duties,
        work_model=record.work_model,
        current_jd=current_jd,
        proposals=proposals,
        current_opks=CurrentJdOpks(items=await uow.opks.list(record.document_id)),
        opks_proposals=await uow.opks_proposals.list(record.document_id),
    )


async def _commit_duty_direct_edit(
    uow: JobAnalysisUnitOfWork,
    *,
    record: DocumentRecord,
    current_duties: tuple[Duty, ...],
    current_jd: tuple[JdTask, ...],
    proposals: tuple[Proposal, ...],
    entry_id: str,
    payload: DutyDirectEditPayload,
) -> None:
    now = _utcnow()
    await commit_authority_change(
        uow,
        record=record,
        state=await _state(
            uow,
            record=record,
            current_duties=current_duties,
            current_jd=current_jd,
            proposals=proposals,
        ),
        journal_entries=(
            JournalEntry(
                document_id=record.document_id,
                entry_id=entry_id,
                kind="direct_edit",
                payload_schema_id=DUTY_DIRECT_EDIT_SCHEMA_ID,
                payload=payload,
                created_at=now,
            ),
        ),
        updated_at=now,
    )


async def add_duty(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    entry_id: str,
    statement: str,
) -> Duty:
    """Append one employee-authored Duty with a replay-stable identity."""

    duty_id: DutyId = f"{entry_id}-d0"
    async with uow_factory() as uow:
        record = await _locked_document(uow, document_id)
        existing_entry = await uow.journal.get(document_id, entry_id)
        if existing_entry is not None:
            payload = _require_duty_direct_edit(existing_entry)
            if (
                payload.action != "add"
                or payload.after is None
                or payload.after.duty_id != duty_id
                or payload.after.statement != statement
            ):
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed with another Duty add"
                )
            return payload.after

        duties = await uow.duties.list(document_id)
        if any(duty.duty_id == duty_id for duty in duties):
            raise IdempotencyConflict(f"generated Duty id {duty_id!r} already exists")
        created = Duty(
            duty_id=duty_id,
            statement=statement,
            display_order=max((duty.display_order for duty in duties), default=-1) + 1,
        )
        await _commit_duty_direct_edit(
            uow,
            record=record,
            current_duties=(*duties, created),
            current_jd=await uow.tasks.list(document_id),
            proposals=await uow.proposals.list(document_id),
            entry_id=entry_id,
            payload=DutyDirectEditPayload(action="add", after=created),
        )
        return created


async def edit_duty(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    entry_id: str,
    duty_id: DutyId,
    statement: str,
) -> Duty:
    """Change Duty wording while preserving its identity and order."""

    async with uow_factory() as uow:
        record = await _locked_document(uow, document_id)
        existing_entry = await uow.journal.get(document_id, entry_id)
        if existing_entry is not None:
            payload = _require_duty_direct_edit(existing_entry)
            if (
                payload.action != "edit"
                or payload.before is None
                or payload.after is None
                or payload.before.duty_id != duty_id
                or payload.after.statement != statement
            ):
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed with another Duty edit"
                )
            return payload.after

        duties = await uow.duties.list(document_id)
        existing = next((duty for duty in duties if duty.duty_id == duty_id), None)
        if existing is None:
            raise DutyNotFound(f"Duty {duty_id!r} was not found")
        edited = Duty(
            duty_id=existing.duty_id,
            statement=statement,
            display_order=existing.display_order,
        )
        await _commit_duty_direct_edit(
            uow,
            record=record,
            current_duties=tuple(
                edited if duty.duty_id == duty_id else duty for duty in duties
            ),
            current_jd=await uow.tasks.list(document_id),
            proposals=await uow.proposals.list(document_id),
            entry_id=entry_id,
            payload=DutyDirectEditPayload(
                action="edit",
                before=existing,
                after=edited,
            ),
        )
        return edited


async def delete_duty(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    entry_id: str,
    duty_id: DutyId,
) -> None:
    """Remove a Duty and unassign only its Current JD Tasks atomically."""

    async with uow_factory() as uow:
        record = await _locked_document(uow, document_id)
        existing_entry = await uow.journal.get(document_id, entry_id)
        if existing_entry is not None:
            payload = _require_duty_direct_edit(existing_entry)
            if (
                payload.action != "delete"
                or payload.before is None
                or payload.before.duty_id != duty_id
            ):
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed for another Duty"
                )
            return

        duties = await uow.duties.list(document_id)
        existing = next((duty for duty in duties if duty.duty_id == duty_id), None)
        if existing is None:
            raise DutyNotFound(f"Duty {duty_id!r} was not found")
        current_jd = await uow.tasks.list(document_id)
        affected_task_ids = frozenset(
            task.task_id for task in current_jd if task.duty_id == duty_id
        )
        unassigned_tasks = tuple(
            JdTask.model_validate({**task.model_dump(), "duty_id": None})
            if task.task_id in affected_task_ids
            else task
            for task in current_jd
        )
        proposals = stale_task_proposals_for_direct_edit(
            await uow.proposals.list(document_id),
            affected_task_ids=affected_task_ids,
        )
        await _commit_duty_direct_edit(
            uow,
            record=record,
            current_duties=tuple(
                duty for duty in duties if duty.duty_id != duty_id
            ),
            current_jd=unassigned_tasks,
            proposals=proposals,
            entry_id=entry_id,
            payload=DutyDirectEditPayload(action="delete", before=existing),
        )


async def reorder_duties(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    entry_id: str,
    ordered_duty_ids: tuple[DutyId, ...],
) -> tuple[Duty, ...]:
    """Replace the complete Duty order and keep all identities stable."""

    async with uow_factory() as uow:
        record = await _locked_document(uow, document_id)
        duties = await uow.duties.list(document_id)
        by_id = {duty.duty_id: duty for duty in duties}
        existing_entry = await uow.journal.get(document_id, entry_id)
        if existing_entry is not None:
            payload = _require_duty_direct_edit(existing_entry)
            if payload.action != "reorder" or payload.ordered_duty_ids != ordered_duty_ids:
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed with another Duty order"
                )
            if set(ordered_duty_ids) != set(by_id):
                raise IdempotencyConflict(
                    "the reordered Duty set changed after the original request"
                )
            return tuple(
                Duty(
                    duty_id=by_id[duty_id].duty_id,
                    statement=by_id[duty_id].statement,
                    display_order=index,
                )
                for index, duty_id in enumerate(ordered_duty_ids)
            )

        if len(set(ordered_duty_ids)) != len(ordered_duty_ids):
            raise InvalidDutyOrder("ordered_duty_ids must be distinct")
        if set(ordered_duty_ids) != set(by_id):
            raise InvalidDutyOrder(
                "ordered_duty_ids must cover exactly the Current JD Duties"
            )
        reordered = tuple(
            Duty(
                duty_id=by_id[duty_id].duty_id,
                statement=by_id[duty_id].statement,
                display_order=index,
            )
            for index, duty_id in enumerate(ordered_duty_ids)
        )
        await _commit_duty_direct_edit(
            uow,
            record=record,
            current_duties=reordered,
            current_jd=await uow.tasks.list(document_id),
            proposals=await uow.proposals.list(document_id),
            entry_id=entry_id,
            payload=DutyDirectEditPayload(
                action="reorder",
                ordered_duty_ids=ordered_duty_ids,
            ),
        )
        return reordered
