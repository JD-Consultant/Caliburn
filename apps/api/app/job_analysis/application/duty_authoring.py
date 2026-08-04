"""員工對主要職責（Duty）的直接編輯（Duty 切片 T4）。

四支 use case 與 JD Task 的那四支同形：document lock → entry replay → 一次
`commit_authority_change()`，不呼叫 LLM。Task 的 `duty_id`／`competency_level`
**不在這裡**——它們是 `JdTaskFields` 的欄位，走既有的 `edit_jd_task`。

刻意**沒有**做的兩件事：

- **不動 Work Model。** `_reconciled_work_model()` 是用來標記「員工直接改了這條 Task 的
  內容，AI 之後要對齊」。職責歸屬 AI 從頭到尾沒有權限，也沒有東西需要對齊，標了只是雜訊。
- **不 prune OPKS。** O/P/K/S 綁的是 `task_id`，刪職責不會刪 Task，所以 OPKS 原封不動。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.job_analysis.domain import Duty, DutyId, JdTask, Proposal, TaskId

from .authoring import _locked_document, _stale_related_proposals
from .authority_commit import commit_authority_change
from .errors import (
    DutyNotChanged,
    DutyNotFound,
    IdempotencyConflict,
    InvalidDutyOrder,
)
from .opks_proposals import stale_invalid_opks_proposals
from .persistence import (
    DUTY_DIRECT_EDIT_SCHEMA_ID,
    DocumentRecord,
    DutyDirectEditPayload,
    JobAnalysisUnitOfWork,
    JobAnalysisUnitOfWorkFactory,
    JournalEntry,
)
from .transition import JobAnalysisState


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _direct_duty_id(entry_id: str) -> DutyId:
    return f"direct-{entry_id}"


def _require_duty_direct_edit(
    entry: JournalEntry,
    *,
    edit_kind: str,
) -> DutyDirectEditPayload:
    if entry.kind != "direct_edit" or not isinstance(
        entry.payload,
        DutyDirectEditPayload,
    ):
        raise IdempotencyConflict(
            f"entry {entry.entry_id!r} already belongs to another operation"
        )
    if entry.payload.edit_kind != edit_kind:
        raise IdempotencyConflict(
            f"entry {entry.entry_id!r} already records "
            f"{entry.payload.edit_kind!r}"
        )
    return entry.payload


async def _commit_duty_edit(
    uow: JobAnalysisUnitOfWork,
    *,
    record: DocumentRecord,
    duties: tuple[Duty, ...],
    entry_id: str,
    payload: DutyDirectEditPayload,
    tasks: tuple[JdTask, ...] | None = None,
    proposals: tuple[Proposal, ...] | None = None,
) -> None:
    """`tasks`／`proposals` 只有 delete 需要傳——其餘三支不碰它們。"""

    document_id = record.document_id
    now = _utcnow()
    state = JobAnalysisState(
        jd_header=record.jd_header,
        current_duties=duties,
        work_model=record.work_model,
        current_jd=(
            tasks if tasks is not None else await uow.tasks.list(document_id)
        ),
        proposals=(
            proposals
            if proposals is not None
            else await uow.proposals.list(document_id)
        ),
        current_opks={"items": await uow.opks.list(document_id)},
        opks_proposals=await uow.opks_proposals.list(document_id),
    )
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
                document_id=document_id,
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
    duty_id = _direct_duty_id(entry_id)
    async with uow_factory() as uow:
        record = await _locked_document(uow, document_id)
        existing_entry = await uow.journal.get(document_id, entry_id)
        if existing_entry is not None:
            payload = _require_duty_direct_edit(existing_entry, edit_kind="add")
            if (
                payload.duty_id != duty_id
                or payload.after is None
                or payload.after.statement != statement
            ):
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed with another add payload"
                )
            return payload.after

        duties = await uow.duties.list(document_id)
        if any(duty.duty_id == duty_id for duty in duties):
            raise IdempotencyConflict(f"generated duty id {duty_id!r} already exists")
        created = Duty(
            duty_id=duty_id,
            statement=statement,
            display_order=max(
                (duty.display_order for duty in duties),
                default=-1,
            )
            + 1,
        )
        await _commit_duty_edit(
            uow,
            record=record,
            duties=(*duties, created),
            entry_id=entry_id,
            payload=DutyDirectEditPayload(
                edit_kind="add",
                duty_id=duty_id,
                after=created,
            ),
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
    async with uow_factory() as uow:
        record = await _locked_document(uow, document_id)
        existing_entry = await uow.journal.get(document_id, entry_id)
        if existing_entry is not None:
            payload = _require_duty_direct_edit(existing_entry, edit_kind="edit")
            if (
                payload.duty_id != duty_id
                or payload.after is None
                or payload.after.statement != statement
            ):
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed with another edit payload"
                )
            return payload.after

        duties = await uow.duties.list(document_id)
        existing = next((duty for duty in duties if duty.duty_id == duty_id), None)
        if existing is None:
            raise DutyNotFound(f"duty {duty_id!r} was not found")
        edited = existing.model_copy(update={"statement": statement})
        if edited == existing:
            # 比照 `put_jd_header()`：沒改內容就不寫 Journal、不 bump generation，
            # 免得別的 client 的 read-set 因為一次空編輯而失效。
            raise DutyNotChanged("duty edit must change the statement")
        await _commit_duty_edit(
            uow,
            record=record,
            duties=tuple(
                edited if duty.duty_id == duty_id else duty for duty in duties
            ),
            entry_id=entry_id,
            payload=DutyDirectEditPayload(
                edit_kind="edit",
                duty_id=duty_id,
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
) -> tuple[TaskId, ...]:
    """刪掉一條主要職責，回傳因此變成「未指派」的 Task。

    Task **不跟著消失**：它是員工權威內容，職責重整不該連內容一起丟。所以底下 Task 的
    `duty_id` 在同一交易設回 `None`，缺漏由 readiness 的 `task_duty_missing` 提示。
    這條保證原本計畫是靠 `ON DELETE SET NULL` 提供的；T3 已裁定不建 FK（見該 migration
    的 docstring），保證因此改由這裡與 domain 驗證共同提供。

    受影響 Task 上仍在等待的 Task Proposal 一併轉 stale。**這不是為了整潔而是正確性**：
    `_apply_jd_entries()` 接受提案時是把 `jd_after` 的 `JdTask` 整個寫回 Current JD，
    而那份快照還帶著剛被刪掉的 `duty_id`；不轉 stale 的話那筆提案會變成永遠接受不了
    （state 驗證會擋下 dangling `duty_id`），員工只剩「拒絕」一條路。
    """

    async with uow_factory() as uow:
        record = await _locked_document(uow, document_id)
        existing_entry = await uow.journal.get(document_id, entry_id)
        if existing_entry is not None:
            payload = _require_duty_direct_edit(existing_entry, edit_kind="delete")
            if payload.duty_id != duty_id:
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed for another duty"
                )
            return payload.unassigned_task_ids

        duties = await uow.duties.list(document_id)
        if not any(duty.duty_id == duty_id for duty in duties):
            raise DutyNotFound(f"duty {duty_id!r} was not found")

        tasks = await uow.tasks.list(document_id)
        unassigned = tuple(
            task.task_id for task in tasks if task.duty_id == duty_id
        )
        next_tasks = tuple(
            task.model_copy(update={"duty_id": None})
            if task.duty_id == duty_id
            else task
            for task in tasks
        )
        await _commit_duty_edit(
            uow,
            record=record,
            duties=tuple(duty for duty in duties if duty.duty_id != duty_id),
            tasks=next_tasks,
            proposals=_stale_related_proposals(
                await uow.proposals.list(document_id),
                affected_task_ids=frozenset(unassigned),
            ),
            entry_id=entry_id,
            payload=DutyDirectEditPayload(
                edit_kind="delete",
                duty_id=duty_id,
                after=None,
                unassigned_task_ids=unassigned,
            ),
        )
        return unassigned


async def reorder_duties(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    entry_id: str,
    ordered_duty_ids: tuple[DutyId, ...],
) -> tuple[Duty, ...]:
    async with uow_factory() as uow:
        record = await _locked_document(uow, document_id)
        existing_entry = await uow.journal.get(document_id, entry_id)
        duties = await uow.duties.list(document_id)
        by_id = {duty.duty_id: duty for duty in duties}
        if existing_entry is not None:
            payload = _require_duty_direct_edit(existing_entry, edit_kind="reorder")
            if payload.ordered_duty_ids != ordered_duty_ids:
                raise IdempotencyConflict(
                    f"entry {entry_id!r} was replayed with another order"
                )
            if set(ordered_duty_ids) != set(by_id):
                raise IdempotencyConflict(
                    "the reordered Duty set changed after the original request"
                )
            return _reordered(by_id, ordered_duty_ids)

        if len(set(ordered_duty_ids)) != len(ordered_duty_ids):
            raise InvalidDutyOrder("ordered_duty_ids must be distinct")
        if set(ordered_duty_ids) != set(by_id):
            raise InvalidDutyOrder(
                "ordered_duty_ids must cover exactly the current Duties"
            )
        reordered = _reordered(by_id, ordered_duty_ids)
        await _commit_duty_edit(
            uow,
            record=record,
            duties=reordered,
            entry_id=entry_id,
            payload=DutyDirectEditPayload(
                edit_kind="reorder",
                ordered_duty_ids=ordered_duty_ids,
            ),
        )
        return reordered


def _reordered(
    by_id: dict[DutyId, Duty],
    ordered_duty_ids: tuple[DutyId, ...],
) -> tuple[Duty, ...]:
    return tuple(
        by_id[duty_id].model_copy(update={"display_order": index})
        for index, duty_id in enumerate(ordered_duty_ids)
    )
