"""Duty 與 Task 職能級別的 PostgreSQL 往返、CAS 與資料遺失守衛（Duty 切片 T3）。"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.job_analysis.application import (
    add_jd_task,
    create_document,
    edit_jd_task,
    load_document,
    put_jd_header,
)
from app.job_analysis.application.authority_commit import commit_authority_change
from app.job_analysis.application.transition import JobAnalysisState
from app.job_analysis.domain import Duty, JdHeader, JdTaskFields


pytestmark = pytest.mark.asyncio


def factory(session_factory):
    return lambda: SqlAlchemyJobAnalysisUnitOfWork(session_factory)


DUTY = Duty(duty_id="duty-1", statement="維運門市營運系統", display_order=0)


async def _seed(uow_factory, document_id, *, duties, assign_to=None, level=None):
    """建一份文件、一條 Task，並用 authority seam 寫入 duties／指派。"""

    await create_document(uow_factory, document_id=document_id, title="門市營運專員")
    task = await add_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="add-1",
        fields=JdTaskFields(statement="每週彙整營運週報"),
    )
    async with uow_factory() as uow:
        record = await uow.documents.get(document_id, for_update=True)
        assert record is not None
        assigned = task.model_copy(
            update={"duty_id": assign_to, "competency_level": level}
        )
        await commit_authority_change(
            uow,
            record=record,
            state=JobAnalysisState(
                jd_header=record.jd_header,
                current_duties=duties,
                current_jd=(assigned,),
                work_model=record.work_model,
            ),
            updated_at=record.updated_at,
        )
    return task


async def test_duties_and_the_task_link_survive_a_reload(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)

    await _seed(
        uow_factory, document_id, duties=(DUTY,), assign_to="duty-1", level=4
    )
    loaded = await load_document(uow_factory, document_id)

    assert loaded is not None
    assert loaded.state.current_duties == (DUTY,)
    assert loaded.state.current_jd[0].duty_id == "duty-1"
    assert loaded.state.current_jd[0].competency_level == 4


async def test_documents_written_before_the_slice_load_with_no_duties(
    postgres_session_factory, cleanup_job_analysis_rows
):
    """0016 不回填任何 Duty——ADR 0052 決定 13 禁止合成假的 T1。"""

    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)

    await create_document(uow_factory, document_id=document_id, title="門市營運專員")
    await add_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="add-1",
        fields=JdTaskFields(statement="每週彙整營運週報"),
    )
    loaded = await load_document(uow_factory, document_id)

    assert loaded is not None
    assert loaded.state.current_duties == ()
    assert loaded.state.current_jd[0].duty_id is None
    assert loaded.state.current_jd[0].competency_level is None


async def test_duties_are_ordered_and_survive_a_replace(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    second = Duty(duty_id="duty-2", statement="處理門市帳號權限", display_order=1)

    await _seed(uow_factory, document_id, duties=(DUTY, second))
    async with uow_factory() as uow:
        record = await uow.documents.get(document_id, for_update=True)
        assert record is not None
        # 對調兩者的 display_order（tuple 本身仍須 canonical），replace 後要讀回新順序
        await commit_authority_change(
            uow,
            record=record,
            state=JobAnalysisState(
                jd_header=record.jd_header,
                current_duties=(
                    second.model_copy(update={"display_order": 0}),
                    DUTY.model_copy(update={"display_order": 1}),
                ),
                current_jd=await uow.tasks.list(document_id),
                work_model=record.work_model,
            ),
            updated_at=record.updated_at,
        )
    loaded = await load_document(uow_factory, document_id)

    assert loaded is not None
    assert [d.duty_id for d in loaded.state.current_duties] == ["duty-2", "duty-1"]


async def test_an_employee_header_edit_does_not_drop_the_duties(
    postgres_session_factory, cleanup_job_analysis_rows
):
    """`put_jd_header()` 重建整個 state；漏帶 duties 就會靜默清空。"""

    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    await _seed(
        uow_factory, document_id, duties=(DUTY,), assign_to="duty-1", level=4
    )

    await put_jd_header(
        uow_factory,
        document_id=document_id,
        entry_id="header-1",
        header=JdHeader(competency_name="系統維運工程師"),
    )
    loaded = await load_document(uow_factory, document_id)

    assert loaded is not None
    assert loaded.state.current_duties == (DUTY,)
    assert loaded.state.current_jd[0].duty_id == "duty-1"


async def test_an_employee_task_edit_does_not_drop_the_duties(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    task = await _seed(
        uow_factory, document_id, duties=(DUTY,), assign_to="duty-1", level=4
    )

    await edit_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="edit-1",
        task_id=task.task_id,
        fields=JdTaskFields(
            statement="每週彙整並檢查營運週報",
            duty_id="duty-1",
            competency_level=5,
        ),
    )
    loaded = await load_document(uow_factory, document_id)

    assert loaded is not None
    assert loaded.state.current_duties == (DUTY,)
    assert loaded.state.current_jd[0].statement == "每週彙整並檢查營運週報"
    assert loaded.state.current_jd[0].competency_level == 5


async def test_the_database_itself_rejects_an_out_of_range_level(
    postgres_session_factory, cleanup_job_analysis_rows
):
    """0016 的 CHECK 讓「級別 9」連寫都寫不進去，不必等讀取時才發現。"""

    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    await _seed(uow_factory, document_id, duties=(DUTY,), assign_to="duty-1", level=4)

    async with postgres_session_factory() as session:
        with pytest.raises(Exception, match="ja2_ck_jd_tasks_competency_level"):
            await session.execute(
                sa.text(
                    "UPDATE job_analysis_jd_tasks SET competency_level = 9 "
                    "WHERE document_id = :document_id"
                ),
                {"document_id": document_id},
            )


async def test_a_dangling_duty_reference_fails_closed_on_read(
    postgres_session_factory, cleanup_job_analysis_rows
):
    """`duty_id` 沒有 FK（見 migration 0016），所以守門的是 domain：讀取時整份拒收。"""

    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    await _seed(uow_factory, document_id, duties=(DUTY,), assign_to="duty-1", level=4)

    async with postgres_session_factory() as session:
        await session.execute(
            sa.text(
                "UPDATE job_analysis_jd_tasks SET duty_id = 'duty-gone' "
                "WHERE document_id = :document_id"
            ),
            {"document_id": document_id},
        )
        await session.commit()

    with pytest.raises(Exception, match="unknown duty"):
        await load_document(uow_factory, document_id)
