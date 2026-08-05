"""主要職責（Duty）的員工直接編輯 use cases（Duty 切片 T4）。"""

from __future__ import annotations

from uuid import UUID

import pytest

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.job_analysis.application import (
    DutyNotChanged,
    DutyNotFound,
    IdempotencyConflict,
    InvalidDutyOrder,
    add_duty,
    add_jd_task,
    create_document,
    delete_duty,
    edit_duty,
    edit_jd_task,
    load_document,
    reorder_duties,
)
from app.job_analysis.domain import (
    JdEntry,
    JdTaskFields,
    Proposal,
    ProposalAction,
    ProposalStatus,
    SingleTaskTarget,
)


pytestmark = pytest.mark.asyncio


def factory(session_factory):
    return lambda: SqlAlchemyJobAnalysisUnitOfWork(session_factory)


async def seed_document(session_factory, document_id: UUID):
    uow_factory = factory(session_factory)
    await create_document(uow_factory, document_id=document_id, title="門市營運專員")
    return uow_factory


async def generation(uow_factory, document_id: UUID) -> int:
    async with uow_factory() as uow:
        record = await uow.documents.get(document_id)
        assert record is not None
        return record.authority_generation


# ── add ────────────────────────────────────────────────────────────────────


async def test_add_duty_saves_and_appends_in_order(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed_document(postgres_session_factory, document_id)

    first = await add_duty(
        uow_factory,
        document_id=document_id,
        entry_id="duty-a",
        statement="維運門市營運系統",
    )
    second = await add_duty(
        uow_factory,
        document_id=document_id,
        entry_id="duty-b",
        statement="處理門市帳號權限",
    )

    assert (first.duty_id, first.display_order) == ("direct-duty-a", 0)
    assert (second.duty_id, second.display_order) == ("direct-duty-b", 1)
    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert loaded.state.current_duties == (first, second)


async def test_add_duty_replays_the_same_key_without_a_second_duty(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed_document(postgres_session_factory, document_id)

    created = await add_duty(
        uow_factory,
        document_id=document_id,
        entry_id="duty-a",
        statement="維運門市營運系統",
    )
    before = await generation(uow_factory, document_id)
    replayed = await add_duty(
        uow_factory,
        document_id=document_id,
        entry_id="duty-a",
        statement="維運門市營運系統",
    )

    assert replayed == created
    assert await generation(uow_factory, document_id) == before
    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert loaded.state.current_duties == (created,)


async def test_add_duty_rejects_the_same_key_with_another_statement(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed_document(postgres_session_factory, document_id)

    await add_duty(
        uow_factory,
        document_id=document_id,
        entry_id="duty-a",
        statement="維運門市營運系統",
    )
    with pytest.raises(IdempotencyConflict):
        await add_duty(
            uow_factory,
            document_id=document_id,
            entry_id="duty-a",
            statement="處理門市帳號權限",
        )


async def test_a_duty_key_cannot_reuse_a_jd_task_entry_id(
    postgres_session_factory, cleanup_job_analysis_rows
):
    """兩種 direct edit 共用 Journal，同一個 entry_id 不得被兩種操作各認一次。"""

    document_id = cleanup_job_analysis_rows
    uow_factory = await seed_document(postgres_session_factory, document_id)

    await add_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="shared",
        fields=JdTaskFields(statement="每週彙整營運週報"),
    )
    with pytest.raises(IdempotencyConflict):
        await add_duty(
            uow_factory,
            document_id=document_id,
            entry_id="shared",
            statement="維運門市營運系統",
        )


async def test_add_duty_bumps_the_authority_generation(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed_document(postgres_session_factory, document_id)
    before = await generation(uow_factory, document_id)

    await add_duty(
        uow_factory,
        document_id=document_id,
        entry_id="duty-a",
        statement="維運門市營運系統",
    )

    assert await generation(uow_factory, document_id) == before + 1


# ── edit ───────────────────────────────────────────────────────────────────


async def test_edit_duty_keeps_the_id_and_position(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed_document(postgres_session_factory, document_id)
    await add_duty(
        uow_factory, document_id=document_id, entry_id="a", statement="維運門市營運系統"
    )
    created = await add_duty(
        uow_factory, document_id=document_id, entry_id="b", statement="處理帳號權限"
    )

    edited = await edit_duty(
        uow_factory,
        document_id=document_id,
        entry_id="edit-1",
        duty_id=created.duty_id,
        statement="處理門市帳號權限與稽核",
    )

    assert edited.duty_id == created.duty_id
    assert edited.display_order == created.display_order == 1
    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert loaded.state.current_duties[1] == edited


async def test_edit_duty_rejects_an_unchanged_statement(
    postgres_session_factory, cleanup_job_analysis_rows
):
    """比照 `put_jd_header()`：空編輯不寫 Journal、不 bump generation。"""

    document_id = cleanup_job_analysis_rows
    uow_factory = await seed_document(postgres_session_factory, document_id)
    created = await add_duty(
        uow_factory, document_id=document_id, entry_id="a", statement="維運門市營運系統"
    )
    before = await generation(uow_factory, document_id)

    with pytest.raises(DutyNotChanged):
        await edit_duty(
            uow_factory,
            document_id=document_id,
            entry_id="edit-1",
            duty_id=created.duty_id,
            statement="維運門市營運系統",
        )

    assert await generation(uow_factory, document_id) == before


async def test_edit_duty_rejects_an_unknown_duty(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed_document(postgres_session_factory, document_id)

    with pytest.raises(DutyNotFound):
        await edit_duty(
            uow_factory,
            document_id=document_id,
            entry_id="edit-1",
            duty_id="duty-gone",
            statement="維運門市營運系統",
        )


async def test_edit_duty_replays_the_same_key(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed_document(postgres_session_factory, document_id)
    created = await add_duty(
        uow_factory, document_id=document_id, entry_id="a", statement="維運門市營運系統"
    )
    edited = await edit_duty(
        uow_factory,
        document_id=document_id,
        entry_id="edit-1",
        duty_id=created.duty_id,
        statement="維運門市營運與結帳系統",
    )
    before = await generation(uow_factory, document_id)

    replayed = await edit_duty(
        uow_factory,
        document_id=document_id,
        entry_id="edit-1",
        duty_id=created.duty_id,
        statement="維運門市營運與結帳系統",
    )

    assert replayed == edited
    assert await generation(uow_factory, document_id) == before


# ── delete ─────────────────────────────────────────────────────────────────


async def _document_with_an_assigned_task(session_factory, document_id: UUID):
    uow_factory = await seed_document(session_factory, document_id)
    duty = await add_duty(
        uow_factory, document_id=document_id, entry_id="a", statement="維運門市營運系統"
    )
    task = await add_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="task-a",
        fields=JdTaskFields(statement="每週彙整營運週報"),
    )
    assigned = await edit_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="assign-1",
        task_id=task.task_id,
        fields=JdTaskFields(
            statement=task.statement,
            duty_id=duty.duty_id,
            competency_level=4,
        ),
    )
    return uow_factory, duty, assigned


async def test_deleting_a_duty_keeps_its_tasks_and_unassigns_them(
    postgres_session_factory, cleanup_job_analysis_rows
):
    """Task 是員工權威內容，不因為職責重整而消失（計畫 T4 第 2 點）。"""

    document_id = cleanup_job_analysis_rows
    uow_factory, duty, assigned = await _document_with_an_assigned_task(
        postgres_session_factory, document_id
    )

    unassigned = await delete_duty(
        uow_factory,
        document_id=document_id,
        entry_id="del-1",
        duty_id=duty.duty_id,
    )

    assert unassigned == (assigned.task_id,)
    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert loaded.state.current_duties == ()
    assert len(loaded.state.current_jd) == 1
    surviving = loaded.state.current_jd[0]
    assert surviving.task_id == assigned.task_id
    assert surviving.statement == assigned.statement
    assert surviving.duty_id is None
    # 級別是 Task 自己的內容，不隨職責一起被清掉
    assert surviving.competency_level == 4


async def test_deleting_a_duty_leaves_unrelated_tasks_assigned(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory, duty, assigned = await _document_with_an_assigned_task(
        postgres_session_factory, document_id
    )
    other_duty = await add_duty(
        uow_factory, document_id=document_id, entry_id="b", statement="處理帳號權限"
    )
    other_task = await add_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="task-b",
        fields=JdTaskFields(statement="每月盤點門市帳號"),
    )
    await edit_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="assign-2",
        task_id=other_task.task_id,
        fields=JdTaskFields(
            statement=other_task.statement,
            duty_id=other_duty.duty_id,
        ),
    )

    unassigned = await delete_duty(
        uow_factory,
        document_id=document_id,
        entry_id="del-1",
        duty_id=duty.duty_id,
    )

    assert unassigned == (assigned.task_id,)
    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert loaded.state.current_duties == (
        other_duty.model_copy(update={"display_order": 1}),
    )
    by_id = {task.task_id: task for task in loaded.state.current_jd}
    assert by_id[assigned.task_id].duty_id is None
    assert by_id[other_task.task_id].duty_id == other_duty.duty_id


async def test_deleting_a_duty_replays_the_same_key(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory, duty, assigned = await _document_with_an_assigned_task(
        postgres_session_factory, document_id
    )
    first = await delete_duty(
        uow_factory, document_id=document_id, entry_id="del-1", duty_id=duty.duty_id
    )
    before = await generation(uow_factory, document_id)

    replayed = await delete_duty(
        uow_factory, document_id=document_id, entry_id="del-1", duty_id=duty.duty_id
    )

    assert replayed == first == (assigned.task_id,)
    assert await generation(uow_factory, document_id) == before


async def test_deleting_an_unknown_duty_is_rejected(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed_document(postgres_session_factory, document_id)

    with pytest.raises(DutyNotFound):
        await delete_duty(
            uow_factory,
            document_id=document_id,
            entry_id="del-1",
            duty_id="duty-gone",
        )


async def test_deleting_a_duty_stales_a_pending_proposal_for_its_task(
    postgres_session_factory, cleanup_job_analysis_rows
):
    """不是為了整潔，是正確性。

    `_apply_jd_entries()` 接受提案時把 `jd_after` 的 `JdTask` 整份寫回 Current JD，
    快照裡還帶著剛被刪掉的 `duty_id`。不轉 stale 的話那筆提案永遠接受不了——state 驗證
    會擋下 dangling `duty_id`——員工只剩「拒絕」一條路。
    """

    document_id = cleanup_job_analysis_rows
    uow_factory, duty, assigned = await _document_with_an_assigned_task(
        postgres_session_factory, document_id
    )
    pending = Proposal(
        proposal_id="proposal-1",
        target=SingleTaskTarget(
            action=ProposalAction.REVISE,
            task_id=assigned.task_id,
        ),
        jd_before=(JdEntry(task_id=assigned.task_id, value=assigned),),
        jd_after=(
            JdEntry(
                task_id=assigned.task_id,
                value=assigned.model_copy(update={"statement": "每週檢查營運週報"}),
            ),
        ),
    )
    async with uow_factory() as uow:
        await uow.proposals.replace(document_id, (pending,))
        await uow.commit()

    await delete_duty(
        uow_factory, document_id=document_id, entry_id="del-1", duty_id=duty.duty_id
    )

    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert loaded.state.proposals[0].status is ProposalStatus.STALE
    # 那筆快照確實還帶著被刪掉的職責——這就是它不能留在 pending 的理由
    assert loaded.state.proposals[0].jd_after[0].value.duty_id == duty.duty_id


async def test_deleting_a_duty_does_not_touch_the_opks_of_its_tasks(
    postgres_session_factory, cleanup_job_analysis_rows
):
    """O/P/K/S 綁的是 `task_id`；Task 沒被刪，OPKS 就不該動（計畫 T4 第 3 點）。"""

    document_id = cleanup_job_analysis_rows
    uow_factory, duty, assigned = await _document_with_an_assigned_task(
        postgres_session_factory, document_id
    )
    async with uow_factory() as uow:
        before = await uow.opks.list(document_id)

    await delete_duty(
        uow_factory, document_id=document_id, entry_id="del-1", duty_id=duty.duty_id
    )

    async with uow_factory() as uow:
        assert await uow.opks.list(document_id) == before


# ── reorder ────────────────────────────────────────────────────────────────


async def test_reorder_duties_renumbers_from_zero(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed_document(postgres_session_factory, document_id)
    first = await add_duty(
        uow_factory, document_id=document_id, entry_id="a", statement="維運門市營運系統"
    )
    second = await add_duty(
        uow_factory, document_id=document_id, entry_id="b", statement="處理帳號權限"
    )

    reordered = await reorder_duties(
        uow_factory,
        document_id=document_id,
        entry_id="order-1",
        ordered_duty_ids=(second.duty_id, first.duty_id),
    )

    assert [duty.duty_id for duty in reordered] == [second.duty_id, first.duty_id]
    assert [duty.display_order for duty in reordered] == [0, 1]
    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert loaded.state.current_duties == reordered


async def test_reorder_duties_rejects_a_partial_or_repeated_order(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed_document(postgres_session_factory, document_id)
    first = await add_duty(
        uow_factory, document_id=document_id, entry_id="a", statement="維運門市營運系統"
    )
    await add_duty(
        uow_factory, document_id=document_id, entry_id="b", statement="處理帳號權限"
    )

    with pytest.raises(InvalidDutyOrder):
        await reorder_duties(
            uow_factory,
            document_id=document_id,
            entry_id="order-1",
            ordered_duty_ids=(first.duty_id,),
        )
    with pytest.raises(InvalidDutyOrder):
        await reorder_duties(
            uow_factory,
            document_id=document_id,
            entry_id="order-2",
            ordered_duty_ids=(first.duty_id, first.duty_id),
        )


async def test_reorder_duties_keeps_the_task_links(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory, duty, assigned = await _document_with_an_assigned_task(
        postgres_session_factory, document_id
    )
    other = await add_duty(
        uow_factory, document_id=document_id, entry_id="b", statement="處理帳號權限"
    )

    await reorder_duties(
        uow_factory,
        document_id=document_id,
        entry_id="order-1",
        ordered_duty_ids=(other.duty_id, duty.duty_id),
    )

    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert loaded.state.current_jd[0].duty_id == duty.duty_id
    assert loaded.state.current_jd[0].competency_level == 4


async def test_reorder_duties_replays_the_same_key(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory = await seed_document(postgres_session_factory, document_id)
    first = await add_duty(
        uow_factory, document_id=document_id, entry_id="a", statement="維運門市營運系統"
    )
    second = await add_duty(
        uow_factory, document_id=document_id, entry_id="b", statement="處理帳號權限"
    )
    order = (second.duty_id, first.duty_id)
    reordered = await reorder_duties(
        uow_factory,
        document_id=document_id,
        entry_id="order-1",
        ordered_duty_ids=order,
    )
    before = await generation(uow_factory, document_id)

    replayed = await reorder_duties(
        uow_factory,
        document_id=document_id,
        entry_id="order-1",
        ordered_duty_ids=order,
    )

    assert replayed == reordered
    assert await generation(uow_factory, document_id) == before

    with pytest.raises(IdempotencyConflict):
        await reorder_duties(
            uow_factory,
            document_id=document_id,
            entry_id="order-1",
            ordered_duty_ids=(first.duty_id, second.duty_id),
        )
