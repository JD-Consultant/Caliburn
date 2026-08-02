"""Durable employee authoring use cases on the greenfield PostgreSQL seam."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.job_analysis.application import (
    IdempotencyConflict,
    add_jd_task,
    create_document,
    delete_jd_task,
    edit_jd_task,
    list_documents,
    load_document,
    put_document_metadata,
    reorder_jd_tasks,
)
from app.job_analysis.domain import (
    CurrentWorkModel,
    JdEntry,
    JdTask,
    JdTaskFields,
    OpenIssueKind,
    Proposal,
    ProposalAction,
    ProposalStatus,
    ResponsibilityRole,
    SingleTaskTarget,
    SourceKind,
    SourceRef,
    SupportLink,
    Task,
)


pytestmark = pytest.mark.asyncio
NOW = datetime(2026, 7, 29, 11, 0, tzinfo=UTC)


def fields(statement: str) -> JdTaskFields:
    return JdTaskFields(
        statement=statement,
        purpose_result="讓主管掌握營運狀況",
        frequency_text="每週一次",
        responsibility_role=ResponsibilityRole.PRIMARY,
    )


async def test_create_list_and_load_an_empty_document(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows

    created = await create_document(
        lambda: SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory),
        document_id=document_id,
        title="門市營運專員",
    )
    summaries = await list_documents(
        lambda: SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory)
    )
    loaded = await load_document(
        lambda: SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory),
        document_id,
    )

    assert loaded is not None
    assert loaded.document == created
    assert loaded.state.current_jd == ()
    assert loaded.document.active_question is not None
    assert loaded.document.active_question.text == (
        "先不用照職稱回答：你這個職位最主要替誰解決什麼問題？"
    )
    assert [turn.text for turn in loaded.conversation_turns] == [
        "先不用照職稱回答：你這個職位最主要替誰解決什麼問題？"
    ]
    assert next(item for item in summaries if item.document_id == document_id).task_count == 0


async def test_rename_changes_only_document_metadata(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory)
    await create_document(factory, document_id=document_id, title="門市營運專員")
    before = await load_document(factory, document_id)

    result = await put_document_metadata(
        factory,
        document_id=document_id,
        title="資深門市營運專員",
    )
    after = await load_document(factory, document_id)

    assert before is not None
    assert after is not None
    assert result.created is False
    assert after.document.title == "資深門市營運專員"
    assert after.document.authority_generation == before.document.authority_generation
    assert after.state == before.state
    assert after.conversation_turns == before.conversation_turns

    async with factory() as uow:
        assert await uow.documents.update_title(
            UUID(int=0),
            title="不存在的文件",
            updated_at=NOW,
        ) is False


async def test_add_edit_reorder_delete_reload_and_idempotent_replay(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory)
    await create_document(factory, document_id=document_id, title="門市營運專員")

    first = await add_jd_task(
        factory,
        document_id=document_id,
        entry_id="edit-add-1",
        fields=fields("每週彙整營運週報"),
    )
    replay = await add_jd_task(
        factory,
        document_id=document_id,
        entry_id="edit-add-1",
        fields=fields("每週彙整營運週報"),
    )
    assert replay == first

    edited = await edit_jd_task(
        factory,
        document_id=document_id,
        entry_id="edit-update-1",
        task_id=first.task_id,
        fields=fields("每週彙整並檢查營運週報"),
    )
    second = await add_jd_task(
        factory,
        document_id=document_id,
        entry_id="edit-add-2",
        fields=fields("每月盤點門市耗材"),
    )
    reordered = await reorder_jd_tasks(
        factory,
        document_id=document_id,
        entry_id="edit-reorder-1",
        ordered_task_ids=(second.task_id, first.task_id),
    )
    await delete_jd_task(
        factory,
        document_id=document_id,
        entry_id="edit-delete-1",
        task_id=first.task_id,
    )

    loaded = await load_document(factory, document_id)
    assert loaded is not None
    assert edited.display_order == first.display_order
    assert [task.task_id for task in reordered] == [second.task_id, first.task_id]
    assert loaded.state.current_jd == (
        second.model_copy(update={"display_order": 0}),
    )
    assert len(loaded.state.work_model.open_issues) == 1
    issue = loaded.state.work_model.open_issues[0]
    assert issue.summary == "每月盤點門市耗材"
    assert issue.kind is OpenIssueKind.INSUFFICIENT_EVIDENCE
    assert issue.reconciliation_task_id == second.task_id
    # add replay does not execute the mutation or increment generation twice:
    # four distinct edits after the first add => generation 5.
    assert loaded.document.authority_generation == 5

    async with factory() as uow:
        for entry_id in (
            "edit-add-1",
            "edit-update-1",
            "edit-add-2",
            "edit-reorder-1",
            "edit-delete-1",
        ):
            assert await uow.journal.get(document_id, entry_id) is not None


async def test_same_entry_id_with_different_payload_is_a_typed_conflict(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory)
    await create_document(factory, document_id=document_id, title="門市營運專員")
    await add_jd_task(
        factory,
        document_id=document_id,
        entry_id="same-entry",
        fields=fields("每週彙整營運週報"),
    )

    with pytest.raises(IdempotencyConflict):
        await add_jd_task(
            factory,
            document_id=document_id,
            entry_id="same-entry",
            fields=fields("每月盤點門市耗材"),
        )

    loaded = await load_document(factory, document_id)
    assert loaded is not None
    assert loaded.document.authority_generation == 1
    assert loaded.state.current_jd[0].statement == "每週彙整營運週報"


def work_model_task() -> Task:
    return Task(
        task_id="task-existing",
        statement="每週彙整營運週報",
        action="彙整",
        object="營運週報",
        support_links=(
            SupportLink(
                source_ref=SourceRef(
                    kind=SourceKind.EMPLOYEE_TURN,
                    id="turn-1",
                ),
                quote="我每週會彙整營運週報",
            ),
        ),
    )


async def seed_existing_authority(
    session_factory,
    document_id: UUID,
) -> None:
    factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(session_factory)
    await create_document(factory, document_id=document_id, title="門市營運專員")
    task = JdTask(
        task_id="task-existing",
        statement="每週彙整營運週報",
        display_order=0,
    )
    pending = Proposal(
        proposal_id="proposal-existing",
        target=SingleTaskTarget(
            action=ProposalAction.REVISE,
            task_id=task.task_id,
        ),
        jd_before=(JdEntry(task_id=task.task_id, value=task),),
        jd_after=(
            JdEntry(
                task_id=task.task_id,
                value=task.model_copy(update={"statement": "每週檢查營運週報"}),
            ),
        ),
    )
    async with factory() as uow:
        record = await uow.documents.get(document_id, for_update=True)
        assert record is not None
        changed = await uow.documents.update_authority(
            document_id,
            expected_generation=record.authority_generation,
            work_model=CurrentWorkModel(tasks=(work_model_task(),)),
            active_question=None,
            updated_at=record.updated_at + timedelta(seconds=1),
        )
        assert changed
        await uow.tasks.replace(document_id, (task,))
        await uow.proposals.replace(document_id, (pending,))
        await uow.commit()


async def test_direct_edit_marks_work_model_for_reconciliation_and_stales_proposal(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory)
    await seed_existing_authority(postgres_session_factory, document_id)

    await edit_jd_task(
        factory,
        document_id=document_id,
        entry_id="employee-edit-1",
        task_id="task-existing",
        fields=fields("員工修改後的週報工作"),
    )

    loaded = await load_document(factory, document_id)
    assert loaded is not None
    analysed = loaded.state.work_model.task_by_id("task-existing")
    assert analysed is not None
    assert analysed.pending_reconciliation == SourceRef(
        kind=SourceKind.DIRECT_EDIT,
        id="employee-edit-1",
    )
    assert loaded.state.proposals[0].status is ProposalStatus.STALE
    assert loaded.state.current_jd[0].statement == "員工修改後的週報工作"
