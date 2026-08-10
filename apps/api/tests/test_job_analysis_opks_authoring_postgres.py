"""Employee OPKS edits share the Current JD authority transaction."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.documents import add_jd_task, delete_jd_task, load_document
from app.documents.authoring import create_document
from app.job_analysis.application import (
    IdempotencyConflict,
    OpksDirectEditPayload,
)
from app.opks import OpksItemNotFound, add_opks_item, delete_opks_item, edit_opks_item
from app.core.domain import (
    JdHeader,
    JdTaskFields,
    OpksEntityKind,
    SourceKind,
    SourceRef,
)


pytestmark = pytest.mark.asyncio


def factory(session_factory):
    return lambda: SqlAlchemyJobAnalysisUnitOfWork(session_factory)


async def seed_task(
    session_factory,
    document_id,
    *,
    entry_id: str,
    statement: str,
    jd_header: JdHeader | None = None,
):
    uow_factory = factory(session_factory)
    await create_document(
        uow_factory,
        document_id=document_id,
        title="門市營運專員",
    )
    if jd_header is not None:
        async with uow_factory() as uow:
            record = await uow.documents.get(document_id, for_update=True)
            assert record is not None
            changed = await uow.documents.update_authority(
                document_id,
                expected_generation=record.authority_generation,
                jd_header=jd_header,
                work_model=record.work_model,
                active_question=record.active_question,
                updated_at=record.updated_at,
            )
            assert changed
            await uow.commit()
    return await add_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id=entry_id,
        fields=JdTaskFields(statement=statement),
    )


async def test_add_edit_delete_reload_and_idempotent_replay(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    header = JdHeader(
        competency_name="門市營運管理",
        work_description="負責門市日常營運與週報彙整。",
    )
    task = await seed_task(
        postgres_session_factory,
        document_id,
        entry_id="task-1",
        statement="每週彙整營運週報",
        jd_header=header,
    )

    created = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="opks-add-1",
        entity_kind=OpksEntityKind.OUTPUT,
        text="營運週報",
        task_refs=(task.task_id,),
    )
    replay = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="opks-add-1",
        entity_kind=OpksEntityKind.OUTPUT,
        text="營運週報",
        task_refs=(task.task_id,),
    )
    assert replay == created
    assert created.entity_id == "direct-opks-add-1-output"
    assert created.evidence_links[0].source_ref == SourceRef(
        kind=SourceKind.DIRECT_EDIT,
        id="opks-add-1",
    )

    with pytest.raises(IdempotencyConflict):
        await add_opks_item(
            uow_factory,
            document_id=document_id,
            entry_id="opks-add-1",
            entity_kind=OpksEntityKind.OUTPUT,
            text="另一份產出",
            task_refs=(task.task_id,),
        )

    edited = await edit_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="opks-edit-1",
        entity_id=created.entity_id,
        entity_kind=OpksEntityKind.OUTPUT,
        text="每週營運週報",
        task_refs=(task.task_id,),
    )
    assert edited.entity_id == created.entity_id
    assert edited.text == "每週營運週報"
    assert [link.source_ref.id for link in edited.evidence_links] == ["opks-edit-1"]

    await delete_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="opks-delete-1",
        entity_id=created.entity_id,
    )
    await delete_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="opks-delete-1",
        entity_id=created.entity_id,
    )

    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert loaded.state.current_opks.items == ()
    assert loaded.document.authority_generation == 5
    assert loaded.state.jd_header == header

    async with uow_factory() as uow:
        add_entry = await uow.journal.get(document_id, "opks-add-1")
        edit_entry = await uow.journal.get(document_id, "opks-edit-1")
        delete_entry = await uow.journal.get(document_id, "opks-delete-1")
    assert isinstance(add_entry.payload, OpksDirectEditPayload)
    assert add_entry.payload.before is None
    assert add_entry.payload.after == created
    assert edit_entry.payload.before == created
    assert edit_entry.payload.after == edited
    assert delete_entry.payload.before == edited
    assert delete_entry.payload.after is None


async def test_direct_add_uses_next_kind_order_edit_preserves_and_delete_keeps_gap(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    task = await seed_task(
        postgres_session_factory,
        document_id,
        entry_id="task-1",
        statement="每週彙整營運週報",
    )

    first = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="opks-output-1",
        entity_kind=OpksEntityKind.OUTPUT,
        text="營運週報",
        task_refs=(task.task_id,),
    )
    second = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="opks-output-2",
        entity_kind=OpksEntityKind.OUTPUT,
        text="營運月報",
        task_refs=(task.task_id,),
    )
    knowledge = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="opks-knowledge-1",
        entity_kind=OpksEntityKind.KNOWLEDGE,
        text="營運數據定義",
    )

    assert (first.display_order, second.display_order, knowledge.display_order) == (
        0,
        1,
        0,
    )
    edited = await edit_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="opks-output-edit",
        entity_id=first.entity_id,
        entity_kind=first.entity_kind,
        text="每週營運週報",
        task_refs=(task.task_id,),
    )
    assert edited.display_order == first.display_order

    await delete_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="opks-output-delete",
        entity_id=first.entity_id,
    )
    loaded = await load_document(uow_factory, document_id)

    assert loaded is not None
    assert loaded.state.current_opks.items == (knowledge, second)
    assert second.display_order == 1


async def test_invalid_manual_opks_edits_fail_before_writing(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    task = await seed_task(
        postgres_session_factory,
        document_id,
        entry_id="task-1",
        statement="每週彙整營運週報",
    )

    with pytest.raises(ValidationError, match="String should have at least 1 character"):
        await add_opks_item(
            uow_factory,
            document_id=document_id,
            entry_id="blank",
            entity_kind=OpksEntityKind.OUTPUT,
            text="",
            task_refs=(task.task_id,),
        )
    with pytest.raises(ValidationError, match="unknown Current JD task refs"):
        await add_opks_item(
            uow_factory,
            document_id=document_id,
            entry_id="unknown-task",
            entity_kind=OpksEntityKind.OUTPUT,
            text="週報",
            task_refs=("missing",),
        )
    with pytest.raises(OpksItemNotFound):
        await edit_opks_item(
            uow_factory,
            document_id=document_id,
            entry_id="missing-item",
            entity_id="missing",
            entity_kind=OpksEntityKind.KNOWLEDGE,
            text="報表知識",
        )

    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert loaded.state.current_opks.items == ()
    assert loaded.document.authority_generation == 1


async def test_task_delete_prunes_owned_opks_and_unlinks_shared_knowledge_skill(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    first = await seed_task(
        postgres_session_factory,
        document_id,
        entry_id="task-1",
        statement="每週彙整營運週報",
    )
    second = await add_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="task-2",
        fields=JdTaskFields(statement="每月盤點門市耗材"),
    )
    output = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="output",
        entity_kind=OpksEntityKind.OUTPUT,
        text="營運週報",
        task_refs=(first.task_id,),
    )
    indicator = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="indicator",
        entity_kind=OpksEntityKind.INDICATOR,
        text="依期限完成週報",
        task_refs=(first.task_id,),
    )
    knowledge = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="knowledge",
        entity_kind=OpksEntityKind.KNOWLEDGE,
        text="營運數據定義",
        task_refs=(first.task_id, second.task_id),
        indicator_refs=(indicator.entity_id,),
    )
    skill = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="skill",
        entity_kind=OpksEntityKind.SKILL,
        text="試算表整理",
        task_refs=(first.task_id,),
    )
    attitude = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="attitude",
        entity_kind=OpksEntityKind.ATTITUDE,
        text="主動釐清異常",
    )

    await delete_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="delete-task-1",
        task_id=first.task_id,
    )

    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    by_id = {
        item.entity_id: item for item in loaded.state.current_opks.items
    }
    assert output.entity_id not in by_id
    assert indicator.entity_id not in by_id
    assert by_id[knowledge.entity_id].task_refs == (second.task_id,)
    assert by_id[knowledge.entity_id].indicator_refs == ()
    assert by_id[skill.entity_id].task_refs == ()
    assert by_id[attitude.entity_id] == attitude


async def test_indicator_delete_unlinks_knowledge_and_skill_in_the_same_commit(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    task = await seed_task(
        postgres_session_factory,
        document_id,
        entry_id="task-1",
        statement="每週彙整營運週報",
    )
    indicator = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="indicator",
        entity_kind=OpksEntityKind.INDICATOR,
        text="依期限完成週報",
        task_refs=(task.task_id,),
    )
    knowledge = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="knowledge",
        entity_kind=OpksEntityKind.KNOWLEDGE,
        text="營運數據定義",
        indicator_refs=(indicator.entity_id,),
    )
    skill = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="skill",
        entity_kind=OpksEntityKind.SKILL,
        text="試算表整理",
        indicator_refs=(indicator.entity_id,),
    )

    await delete_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="delete-indicator",
        entity_id=indicator.entity_id,
    )
    loaded = await load_document(uow_factory, document_id)

    assert loaded is not None
    by_id = {item.entity_id: item for item in loaded.state.current_opks.items}
    assert indicator.entity_id not in by_id
    assert by_id[knowledge.entity_id].indicator_refs == ()
    assert by_id[skill.entity_id].indicator_refs == ()


# ── Task 離開 Current JD 時移除 OPKS 缺口(ADR 0054 決定 26–27)────────────────


def opks_gap_issue(issue_id: str, task_id: str, *, summary: str = "還看不出這項工作交出什麼"):
    from app.core.domain import (
        OpenIssue,
        OpenIssueKind,
        OpksGapAxis,
        SourceAnchor,
    )

    return OpenIssue(
        id=issue_id,
        kind=OpenIssueKind.INSUFFICIENT_EVIDENCE,
        summary=summary,
        source_anchors=(
            SourceAnchor(
                source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="turn-1"),
                quote="我每週彙整營運週報",
            ),
        ),
        subject_task_id=task_id,
        opks_axis=OpksGapAxis.OUTPUT,
    )


def general_issue(issue_id: str = "general-1"):
    from app.core.domain import OpenIssue, OpenIssueKind, SourceAnchor

    return OpenIssue(
        id=issue_id,
        kind=OpenIssueKind.RESPONSIBILITY_UNCLEAR,
        summary="責任邊界還不清楚",
        source_anchors=(
            SourceAnchor(
                source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="turn-1"),
                quote="我每週彙整營運週報",
            ),
        ),
    )


async def test_deleting_a_jd_task_removes_its_gap_in_the_same_transaction(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    """呼叫點驗收:純函式接上了 delete 這條路,不是只存在於單元測試裡。"""

    from datetime import timedelta

    from app.core.domain import CurrentWorkModel

    document_id = cleanup_job_analysis_rows
    uow_factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory)
    await create_document(
        uow_factory,
        document_id=document_id,
        title="門市營運專員",
    )
    created = await add_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="direct-1",
        fields=JdTaskFields(statement="每週彙整營運週報"),
    )
    async with uow_factory() as uow:
        record = await uow.documents.get(document_id, for_update=True)
        assert record is not None
        assert await uow.documents.update_authority(
            document_id,
            expected_generation=record.authority_generation,
            jd_header=record.jd_header,
            work_model=CurrentWorkModel(
                open_issues=(
                    opks_gap_issue("gap-1", created.task_id),
                    general_issue(),
                )
            ),
            active_question=record.active_question,
            updated_at=record.updated_at + timedelta(seconds=1),
        )
        await uow.commit()

    await delete_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="delete-1",
        task_id=created.task_id,
    )
    loaded = await load_document(uow_factory, document_id)

    assert loaded is not None
    assert [issue.id for issue in loaded.state.work_model.open_issues] == ["general-1"]
