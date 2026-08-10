"""Durable employee edits for Current JD O/P/K/S/A items."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.core.domain import (
    CurrentJdOpks,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    SourceKind,
    SourceRef,
)
from app.core.authority import commit_authority_change
from app.core.opks_integrity import (
    prune_opks_for_current_jd,
    prune_opks_gaps_for_current_jd,
)
from app.core.persistence import (
    OPKS_DIRECT_EDIT_SCHEMA_ID,
    JobAnalysisUnitOfWork,
    JobAnalysisUnitOfWorkFactory,
    JournalEntry,
    OpksDirectEditPayload,
)

from .errors import (
    DocumentNotFound,
    IdempotencyConflict,
    InvalidOpksOrder,
    OpksItemNotFound,
)
from .opks_proposals import (
    remove_opks_item_and_indicator_refs,
    stale_invalid_opks_proposals,
)
from .transition import JobAnalysisState


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _entity_id(entry_id: str, kind: OpksEntityKind) -> str:
    return f"direct-{entry_id}-{kind.value}"


def _item(
    *,
    entity_id: str,
    entity_kind: OpksEntityKind,
    text: str,
    task_refs: tuple[str, ...],
    indicator_refs: tuple[str, ...],
    entry_id: str,
    display_order: int,
) -> OpksItem:
    return OpksItem(
        entity_id=entity_id,
        entity_kind=entity_kind,
        text=text,
        display_order=display_order,
        task_refs=task_refs,
        indicator_refs=indicator_refs,
        evidence_links=(
            OpksEvidenceLink(
                source_ref=SourceRef(
                    kind=SourceKind.DIRECT_EDIT,
                    id=entry_id,
                )
            ),
        ),
    )


def _require_replay(
    entry: JournalEntry,
    *,
    action: str,
) -> OpksDirectEditPayload:
    if entry.kind != "direct_edit" or not isinstance(
        entry.payload,
        OpksDirectEditPayload,
    ):
        raise IdempotencyConflict(
            f"entry {entry.entry_id!r} already belongs to another operation"
        )
    if entry.payload.action != action:
        raise IdempotencyConflict(
            f"entry {entry.entry_id!r} already records "
            f"{entry.payload.action!r}"
        )
    return entry.payload


async def _locked_state(
    uow: JobAnalysisUnitOfWork,
    document_id: UUID,
):
    record = await uow.documents.get(document_id, for_update=True)
    if record is None:
        raise DocumentNotFound(f"document {document_id} was not found")
    state = JobAnalysisState(
        jd_header=record.jd_header,
        current_duties=await uow.duties.list(document_id),
        work_model=record.work_model,
        current_jd=await uow.tasks.list(document_id),
        proposals=await uow.proposals.list(document_id),
        current_opks={"items": await uow.opks.list(document_id)},
        opks_proposals=await uow.opks_proposals.list(document_id),
    )
    return record, state


async def _commit(
    uow: JobAnalysisUnitOfWork,
    *,
    record,
    state: JobAnalysisState,
    entry_id: str,
    payload: OpksDirectEditPayload,
) -> None:
    now = _utcnow()
    state = state.model_copy(
        update={
            "opks_proposals": stale_invalid_opks_proposals(
                state.opks_proposals,
                current_opks=state.current_opks,
                current_jd=state.current_jd,
                now=now,
            )
        }
    )
    await commit_authority_change(
        uow,
        record=record,
        state=state,
        journal_entries=(
            JournalEntry(
                document_id=record.document_id,
                entry_id=entry_id,
                kind="direct_edit",
                payload_schema_id=OPKS_DIRECT_EDIT_SCHEMA_ID,
                payload=payload,
                created_at=now,
            ),
        ),
        updated_at=now,
    )


async def add_opks_item(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    entry_id: str,
    entity_kind: OpksEntityKind,
    text: str,
    task_refs: tuple[str, ...] = (),
    indicator_refs: tuple[str, ...] = (),
) -> OpksItem:
    kind = OpksEntityKind(entity_kind)
    async with uow_factory() as uow:
        record, state = await _locked_state(uow, document_id)
        replay = await uow.journal.get(document_id, entry_id)
        if replay is not None:
            payload = _require_replay(replay, action="add")
            if payload.after is None:
                raise IdempotencyConflict(
                    f"entry {entry_id!r} has no added OPKS item"
                )
            expected = _item(
                entity_id=_entity_id(entry_id, kind),
                entity_kind=kind,
                text=text,
                task_refs=task_refs,
                indicator_refs=indicator_refs,
                entry_id=entry_id,
                display_order=payload.after.display_order,
            )
            if payload.after != expected:
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed with another OPKS item"
                )
            assert payload.after is not None
            return payload.after
        expected = _item(
            entity_id=_entity_id(entry_id, kind),
            entity_kind=kind,
            text=text,
            task_refs=task_refs,
            indicator_refs=indicator_refs,
            entry_id=entry_id,
            display_order=state.current_opks.next_display_order(kind),
        )
        if state.current_opks.item_by_id(expected.entity_id) is not None:
            raise IdempotencyConflict(
                f"generated OPKS entity id {expected.entity_id!r} already exists"
            )
        next_opks = CurrentJdOpks(items=(*state.current_opks.items, expected))
        await _commit(
            uow,
            record=record,
            state=state.model_copy(update={"current_opks": next_opks}),
            entry_id=entry_id,
            payload=OpksDirectEditPayload(action="add", after=expected),
        )
        return expected


async def edit_opks_item(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    entry_id: str,
    entity_id: str,
    entity_kind: OpksEntityKind,
    text: str,
    task_refs: tuple[str, ...] = (),
    indicator_refs: tuple[str, ...] = (),
) -> OpksItem:
    kind = OpksEntityKind(entity_kind)
    async with uow_factory() as uow:
        record, state = await _locked_state(uow, document_id)
        replay = await uow.journal.get(document_id, entry_id)
        if replay is not None:
            payload = _require_replay(replay, action="edit")
            if payload.after is None:
                raise IdempotencyConflict(
                    f"entry {entry_id!r} has no edited OPKS item"
                )
            expected = _item(
                entity_id=entity_id,
                entity_kind=kind,
                text=text,
                task_refs=task_refs,
                indicator_refs=indicator_refs,
                entry_id=entry_id,
                display_order=payload.after.display_order,
            )
            if payload.after != expected:
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed with another OPKS edit"
                )
            assert payload.after is not None
            return payload.after
        before = state.current_opks.item_by_id(entity_id)
        if before is None:
            raise OpksItemNotFound(f"OPKS item {entity_id!r} was not found")
        if before.entity_kind is not kind:
            raise ValueError("OPKS edit must preserve entity kind")
        expected = _item(
            entity_id=entity_id,
            entity_kind=kind,
            text=text,
            task_refs=task_refs,
            indicator_refs=indicator_refs,
            entry_id=entry_id,
            display_order=before.display_order,
        )
        next_opks = CurrentJdOpks(
            items=tuple(
                expected if item.entity_id == entity_id else item
                for item in state.current_opks.items
            )
        )
        await _commit(
            uow,
            record=record,
            state=state.model_copy(update={"current_opks": next_opks}),
            entry_id=entry_id,
            payload=OpksDirectEditPayload(
                action="edit",
                before=before,
                after=expected,
            ),
        )
        return expected


async def delete_opks_item(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    entry_id: str,
    entity_id: str,
) -> None:
    async with uow_factory() as uow:
        record, state = await _locked_state(uow, document_id)
        replay = await uow.journal.get(document_id, entry_id)
        if replay is not None:
            payload = _require_replay(replay, action="delete")
            if payload.before is None or payload.before.entity_id != entity_id:
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed for another OPKS item"
                )
            return
        before = state.current_opks.item_by_id(entity_id)
        if before is None:
            raise OpksItemNotFound(f"OPKS item {entity_id!r} was not found")
        next_opks = remove_opks_item_and_indicator_refs(
            state.current_opks,
            entity_id,
        )
        await _commit(
            uow,
            record=record,
            state=state.model_copy(update={"current_opks": next_opks}),
            entry_id=entry_id,
            payload=OpksDirectEditPayload(
                action="delete",
                before=before,
            ),
        )


async def reorder_opks_items(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    entry_id: str,
    entity_kind: OpksEntityKind,
    ordered_entity_ids: tuple[str, ...],
) -> tuple[OpksItem, ...]:
    """Replace one OPKS kind's complete display order atomically."""

    kind = OpksEntityKind(entity_kind)
    async with uow_factory() as uow:
        record, state = await _locked_state(uow, document_id)
        current_ids = tuple(
            item.entity_id
            for item in state.current_opks.items
            if item.entity_kind is kind
        )
        replay = await uow.journal.get(document_id, entry_id)
        if replay is not None:
            payload = _require_replay(replay, action="reorder")
            if (
                payload.entity_kind is not kind
                or payload.ordered_entity_ids != ordered_entity_ids
            ):
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed with another OPKS order"
                )
            if set(ordered_entity_ids) != set(current_ids):
                raise IdempotencyConflict(
                    "the reordered OPKS set changed after the original request"
                )
            return tuple(
                next(
                    item
                    for item in state.current_opks.items
                    if item.entity_id == entity_id
                )
                for entity_id in ordered_entity_ids
            )

        if len(set(ordered_entity_ids)) != len(ordered_entity_ids):
            raise InvalidOpksOrder("ordered_entity_ids must be distinct")
        if set(ordered_entity_ids) != set(current_ids):
            raise InvalidOpksOrder(
                "ordered_entity_ids must cover exactly the OPKS items of one kind"
            )
        by_id = {
            item.entity_id: item
            for item in state.current_opks.items
            if item.entity_kind is kind
        }
        reordered_by_id = {
            entity_id: by_id[entity_id].model_copy(
                update={"display_order": index}
            )
            for index, entity_id in enumerate(ordered_entity_ids)
        }
        next_opks = CurrentJdOpks(
            items=tuple(
                reordered_by_id.get(item.entity_id, item)
                for item in state.current_opks.items
            )
        )
        await _commit(
            uow,
            record=record,
            state=state.model_copy(update={"current_opks": next_opks}),
            entry_id=entry_id,
            payload=OpksDirectEditPayload(
                action="reorder",
                entity_kind=kind,
                ordered_entity_ids=ordered_entity_ids,
            ),
        )
        return tuple(
            next(
                item
                for item in next_opks.items
                if item.entity_id == entity_id
            )
            for entity_id in ordered_entity_ids
        )
