"""Durable employee edits for Current JD O/P/K/S/A items."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.job_analysis.domain import (
    CurrentJdOpks,
    JdHeader,
    JdTask,
    OpenIssue,
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


def _item(
    *,
    entity_id: str,
    entity_kind: OpksEntityKind,
    text: str,
    task_refs: tuple[str, ...],
    indicator_refs: tuple[str, ...],
    entry_id: str,
) -> OpksItem:
    return OpksItem(
        entity_id=entity_id,
        entity_kind=entity_kind,
        text=text,
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


def prune_opks_gaps_for_current_jd(
    open_issues: tuple[OpenIssue, ...],
    current_jd: tuple[JdTask, ...],
) -> tuple[OpenIssue, ...]:
    """移除指向已不在 Current JD 的 Task 的 OPKS 缺口(ADR 0054 決定 26–27)。

    `prune_opks_for_current_jd()` 只收／回 `CurrentJdOpks`,**碰不到
    `work_model.open_issues`**;缺口的清理需要這個相鄰函式,在同一個 authority
    transaction、同一批呼叫點一起做。

    **這裡是「移除」,不是寫 `terminal_resolution`。** 那個欄位的兩個值
    (`employee_unknown`／`not_applicable`)都是**員工的回答**;Task 被刪除、撤回、
    合併或拆分時員工並沒有回答任何事,借用它們等於偽造一筆不存在的回答,而那筆假
    回答會進到 packet 的「已問過、勿重問」記憶區,被主顧問與 specialist 當真。

    **merge／split 一律移除,不遷移。** 沿用既有政策「不把舊 refs 猜接到 replacement
    Task」——沒有人知道新 Task 是不是還缺同一件事。真的還缺,下次分析會自己重新提出,
    那是有依據的判斷而不是猜測。
    """

    task_ids = frozenset(task.task_id for task in current_jd)
    return tuple(
        issue
        for issue in open_issues
        if issue.opks_axis is None or issue.subject_task_id in task_ids
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
        jd_header=JdHeader(),
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
    expected = _item(
        entity_id=_entity_id(entry_id, kind),
        entity_kind=kind,
        text=text,
        task_refs=task_refs,
        indicator_refs=indicator_refs,
        entry_id=entry_id,
    )
    async with uow_factory() as uow:
        record, state = await _locked_state(uow, document_id)
        replay = await uow.journal.get(document_id, entry_id)
        if replay is not None:
            payload = _require_replay(replay, action="add")
            if payload.after != expected:
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed with another OPKS item"
                )
            assert payload.after is not None
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
    expected = _item(
        entity_id=entity_id,
        entity_kind=kind,
        text=text,
        task_refs=task_refs,
        indicator_refs=indicator_refs,
        entry_id=entry_id,
    )
    async with uow_factory() as uow:
        record, state = await _locked_state(uow, document_id)
        replay = await uow.journal.get(document_id, entry_id)
        if replay is not None:
            payload = _require_replay(replay, action="edit")
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
