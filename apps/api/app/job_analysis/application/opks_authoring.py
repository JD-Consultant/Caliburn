"""Durable employee edits for Current JD O/P/K/S/A items."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.job_analysis.domain import (
    CurrentJdOpks,
    JdTask,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    SourceKind,
    SourceRef,
)

from .authority_commit import commit_authority_change
from .errors import (
    DocumentNotFound,
    IdempotencyConflict,
    InvalidOpksOrder,
    OpksItemNotFound,
)
from .persistence import (
    OPKS_DIRECT_EDIT_SCHEMA_ID,
    JobAnalysisUnitOfWork,
    JobAnalysisUnitOfWorkFactory,
    JournalEntry,
    OpksDirectEditPayload,
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


def opks_content(item: OpksItem) -> tuple:
    """replay 比對用的內容指紋，**刻意不含 `display_order`**。

    `display_order` 由當下的 Current JD 決定，同一把 key 重播時清單可能已經變了；
    把位置算進比對會讓合法的重播被誤判成 `IdempotencyConflict`。比照 `add_jd_task`
    只比 `JdTaskFields`（不含 `display_order`）的既有作法。
    """

    return (
        item.entity_id,
        item.entity_kind,
        item.text,
        item.task_refs,
        item.indicator_refs,
        item.evidence_links,
    )


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


def prune_opks_for_current_jd(
    current_opks: CurrentJdOpks,
    current_jd: tuple[JdTask, ...],
) -> CurrentJdOpks:
    """Remove invalid Task-owned items and unlink shared K/S without guessing.

    O/P belong to one Task and disappear when that Task leaves Current JD. K/S
    survive as document-level items; only references to removed Tasks and the
    Indicators removed with them are pruned. Attitude is document-level and is
    unchanged. No old reference is guessed onto a merge/split replacement.
    """

    task_ids = frozenset(task.task_id for task in current_jd)
    retained = tuple(
        item
        for item in current_opks.items
        if item.entity_kind not in {
            OpksEntityKind.OUTPUT,
            OpksEntityKind.INDICATOR,
        }
        or item.task_refs[0] in task_ids
    )
    indicator_ids = frozenset(
        item.entity_id
        for item in retained
        if item.entity_kind is OpksEntityKind.INDICATOR
    )
    normalized: list[OpksItem] = []
    for item in retained:
        if item.entity_kind in {
            OpksEntityKind.KNOWLEDGE,
            OpksEntityKind.SKILL,
        }:
            normalized.append(
                item.model_copy(
                    update={
                        "task_refs": tuple(
                            task_id
                            for task_id in item.task_refs
                            if task_id in task_ids
                        ),
                        "indicator_refs": tuple(
                            indicator_id
                            for indicator_id in item.indicator_refs
                            if indicator_id in indicator_ids
                        ),
                    }
                )
            )
        else:
            normalized.append(item)
    return CurrentJdOpks(items=tuple(normalized))


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
        expected = _item(
            entity_id=_entity_id(entry_id, kind),
            entity_kind=kind,
            text=text,
            task_refs=task_refs,
            indicator_refs=indicator_refs,
            entry_id=entry_id,
            display_order=state.current_opks.next_display_order(kind),
        )
        replay = await uow.journal.get(document_id, entry_id)
        if replay is not None:
            payload = _require_replay(replay, action="add")
            if payload.after is None or opks_content(payload.after) != opks_content(
                expected
            ):
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed with another OPKS item"
                )
            return payload.after
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
        existing = state.current_opks.item_by_id(entity_id)
        # 編輯只改內容，位置留在原地（比照 `edit_jd_task` 沿用 `existing.display_order`）
        expected = _item(
            entity_id=entity_id,
            entity_kind=kind,
            text=text,
            task_refs=task_refs,
            indicator_refs=indicator_refs,
            entry_id=entry_id,
            display_order=existing.display_order if existing is not None else 0,
        )
        replay = await uow.journal.get(document_id, entry_id)
        if replay is not None:
            payload = _require_replay(replay, action="edit")
            if payload.after is None or opks_content(payload.after) != opks_content(
                expected
            ):
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed with another OPKS edit"
                )
            return payload.after
        before = existing
        if before is None:
            raise OpksItemNotFound(f"OPKS item {entity_id!r} was not found")
        if before.entity_kind is not kind:
            raise ValueError("OPKS edit must preserve entity kind")
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


async def reorder_opks_items(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    entry_id: str,
    entity_kind: OpksEntityKind,
    ordered_entity_ids: tuple[str, ...],
) -> tuple[OpksItem, ...]:
    """重排單一 kind 的 O/P/K/S/A，回傳該 kind 重排後的項目。

    範圍是 **kind**，不是 Task：O 只跟 O 換位置。這與 `display_order` 的唯一性範圍一致
    （ADR 0058 決定 5），也讓 `O{i}.{j}.{k}` 的 `{k}` 能在各 Task 內重新從 1 編號。
    """

    kind = OpksEntityKind(entity_kind)
    async with uow_factory() as uow:
        record, state = await _locked_state(uow, document_id)
        in_kind = tuple(
            item for item in state.current_opks.items if item.entity_kind is kind
        )
        by_id = {item.entity_id: item for item in in_kind}
        replay = await uow.journal.get(document_id, entry_id)
        if replay is not None:
            payload = _require_replay(replay, action="reorder")
            if (
                payload.entity_kind is not kind
                or payload.ordered_entity_ids != ordered_entity_ids
            ):
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed with another order"
                )
            if set(ordered_entity_ids) != set(by_id):
                raise IdempotencyConflict(
                    "the reordered OPKS set changed after the original request"
                )
            return _reordered_in_kind(by_id, ordered_entity_ids)

        if len(set(ordered_entity_ids)) != len(ordered_entity_ids):
            raise InvalidOpksOrder("ordered_entity_ids must be distinct")
        if set(ordered_entity_ids) != set(by_id):
            raise InvalidOpksOrder(
                f"ordered_entity_ids must cover exactly the current {kind.value} items"
            )
        reordered = _reordered_in_kind(by_id, ordered_entity_ids)
        placed = {item.entity_id: item for item in reordered}
        next_opks = CurrentJdOpks(
            items=tuple(
                placed.get(item.entity_id, item) for item in state.current_opks.items
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
        return reordered


def _reordered_in_kind(
    by_id: dict[str, OpksItem],
    ordered_entity_ids: tuple[str, ...],
) -> tuple[OpksItem, ...]:
    return tuple(
        by_id[entity_id].model_copy(update={"display_order": index})
        for index, entity_id in enumerate(ordered_entity_ids)
    )


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
