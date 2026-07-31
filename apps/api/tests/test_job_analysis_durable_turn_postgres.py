"""Durable two-phase AI turns on the greenfield PostgreSQL seam."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.job_analysis.application import (
    CompletedTurnPayload,
    ConversationTurn,
    OperationOutcome,
    StaleAuthoritySnapshot,
    TaskAnalysisOperationResult,
    TurnSpeaker,
    UncommittableOperationResult,
    VerificationReport,
    add_jd_task,
    commit_verified_turn,
    create_document,
    load_document,
    prepare_turn,
)
from app.job_analysis.domain import (
    CurrentWorkModel,
    JdTask,
    JdTaskFields,
    SourceKind,
    SourceRef,
    SupportLink,
    Task,
)
from app.job_analysis.llm import (
    IdentityAssessment,
    IdentityRelation,
    NextQuestion,
    SignalAnchor,
    SignalDisposition,
    TaskAnalysisResult,
    TaskChangeKind,
    TaskChangePayload,
    WorkSignal,
)


pytestmark = pytest.mark.asyncio


def factory(session_factory):
    return lambda: SqlAlchemyJobAnalysisUnitOfWork(session_factory)


def employee_turn(turn_id: str = "employee-1") -> ConversationTurn:
    return ConversationTurn(
        turn_id=turn_id,
        speaker=TurnSpeaker.EMPLOYEE,
        text="我每週會彙整營運週報",
    )


def verified_add_result() -> TaskAnalysisOperationResult:
    result = TaskAnalysisResult(
        work_signals=(
            WorkSignal(
                anchors=(
                    SignalAnchor(
                        turn_ordinal=2,
                        quote="我每週會彙整營運週報",
                    ),
                ),
                identity=IdentityAssessment(relation=IdentityRelation.NO_MATCH),
                disposition=SignalDisposition.TASK_CHANGE,
                task_change=TaskChangePayload(
                    change=TaskChangeKind.ADD,
                    task_fields={
                        "statement": "每週彙整營運週報",
                        "action": "彙整",
                        "object": "營運週報",
                        "purpose_result": "讓主管掌握營運狀況",
                    },
                ),
            ),
        ),
        next_question=NextQuestion(
            text="這份週報主要交給誰？",
        ),
    )
    return TaskAnalysisOperationResult(
        outcome=OperationOutcome.VERIFIED,
        result=result,
        report=VerificationReport(),
    )


async def test_verified_turn_commits_state_question_journal_and_replays_once(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    await create_document(
        uow_factory,
        document_id=document_id,
        title="門市營運專員",
    )
    employee = employee_turn()
    snapshot = await prepare_turn(
        uow_factory,
        document_id=document_id,
        employee_turn=employee,
    )

    first = await commit_verified_turn(
        uow_factory,
        snapshot=snapshot,
        operation_id="operation-1",
        employee_turn=employee,
        operation_result=verified_add_result(),
    )
    replay = await commit_verified_turn(
        uow_factory,
        snapshot=snapshot,
        operation_id="operation-1",
        employee_turn=employee,
        operation_result=verified_add_result(),
    )
    loaded = await load_document(uow_factory, document_id)

    assert first.is_applied
    assert replay.is_applied
    assert loaded is not None
    assert loaded.document.authority_generation == 1
    assert [task.task_id for task in loaded.state.work_model.tasks] == [
        "operation-1-t0"
    ]
    assert loaded.document.active_question is not None
    assert loaded.document.active_question.text == "這份週報主要交給誰？"
    assert len(loaded.conversation_turns) == 3
    assert loaded.conversation_turns[-1].turn_id == "operation-1-consultant"


async def test_authority_change_after_prepare_rejects_the_old_model_result(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    await create_document(
        uow_factory,
        document_id=document_id,
        title="門市營運專員",
    )
    employee = employee_turn()
    snapshot = await prepare_turn(
        uow_factory,
        document_id=document_id,
        employee_turn=employee,
    )
    await add_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="direct-edit-during-model-call",
        fields=JdTaskFields(statement="員工直接新增的工作"),
    )

    with pytest.raises(StaleAuthoritySnapshot):
        await commit_verified_turn(
            uow_factory,
            snapshot=snapshot,
            operation_id="stale-operation",
            employee_turn=employee,
            operation_result=verified_add_result(),
        )

    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert loaded.document.authority_generation == 1
    assert len(loaded.conversation_turns) == 1
    assert loaded.state.work_model.tasks == ()


async def test_partial_jd_task_materializes_with_the_same_identity_after_reload(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    await create_document(
        uow_factory,
        document_id=document_id,
        title="門市營運專員",
    )
    created = await add_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="direct-partial-weekly",
        fields=JdTaskFields(statement="每週彙整營運週報"),
    )
    employee = employee_turn()
    snapshot = await prepare_turn(
        uow_factory,
        document_id=document_id,
        employee_turn=employee,
    )
    result = TaskAnalysisResult(
        work_signals=(
            WorkSignal(
                anchors=(
                    SignalAnchor(
                            turn_ordinal=2,
                        quote="我每週會彙整營運週報",
                    ),
                ),
                identity=IdentityAssessment(relation=IdentityRelation.NO_MATCH),
                resolves_open_issue_ordinal=1,
                disposition=SignalDisposition.TASK_CHANGE,
                task_change=TaskChangePayload(
                    change=TaskChangeKind.ADD,
                    task_fields={
                        "statement": "每週彙整營運週報",
                        "action": "彙整",
                        "object": "營運週報",
                    },
                ),
            ),
        ),
        next_question=NextQuestion(
            text="這份週報主要提供給誰？",
        ),
    )
    operation = TaskAnalysisOperationResult(
        outcome=OperationOutcome.VERIFIED,
        result=result,
        report=VerificationReport(),
    )

    await commit_verified_turn(
        uow_factory,
        snapshot=snapshot,
        operation_id="operation-partial-weekly",
        employee_turn=employee,
        operation_result=operation,
    )
    loaded = await load_document(uow_factory, document_id)

    assert loaded is not None
    assert loaded.state.work_model.task_by_id(created.task_id) is not None
    assert loaded.state.work_model.open_issues == ()
    assert loaded.state.current_jd == (created,)


async def test_unverified_provider_outcome_never_writes_current_state(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    await create_document(
        uow_factory,
        document_id=document_id,
        title="門市營運專員",
    )
    employee = employee_turn()
    snapshot = await prepare_turn(
        uow_factory,
        document_id=document_id,
        employee_turn=employee,
    )

    with pytest.raises(UncommittableOperationResult):
        await commit_verified_turn(
            uow_factory,
            snapshot=snapshot,
            operation_id="failed-operation",
            employee_turn=employee,
            operation_result=TaskAnalysisOperationResult(
                outcome=OperationOutcome.FAILED,
                detail="provider timeout",
            ),
        )

    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert loaded.document.authority_generation == 0
    assert len(loaded.conversation_turns) == 1


async def test_verified_revise_persists_the_proposal_with_the_completed_turn(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    await create_document(
        uow_factory,
        document_id=document_id,
        title="門市營運專員",
    )
    source = SupportLink(
        source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="old-turn"),
        quote="我每週會整理營運週報",
    )
    analysed = Task(
        task_id="task-existing",
        statement="每週整理營運週報",
        action="整理",
        object="營運週報",
        support_links=(source,),
    )
    jd_task = JdTask(
        task_id="task-existing",
        statement="每週整理營運週報",
        display_order=0,
    )
    async with uow_factory() as uow:
        record = await uow.documents.get(document_id, for_update=True)
        assert record is not None
        changed = await uow.documents.update_authority(
            document_id,
            expected_generation=record.authority_generation,
            work_model=CurrentWorkModel(tasks=(analysed,)),
            active_question=None,
            updated_at=record.updated_at + timedelta(seconds=1),
        )
        assert changed
        await uow.tasks.replace(document_id, (jd_task,))
        await uow.commit()

    employee = employee_turn()
    snapshot = await prepare_turn(
        uow_factory,
        document_id=document_id,
        employee_turn=employee,
    )
    result = TaskAnalysisResult(
        work_signals=(
            WorkSignal(
                anchors=(
                    SignalAnchor(
                            turn_ordinal=2,
                        quote="我每週會彙整營運週報",
                    ),
                ),
                identity=IdentityAssessment(
                    relation=IdentityRelation.OVERLAP,
                    target_task_ordinals=(1,),
                ),
                disposition=SignalDisposition.TASK_CHANGE,
                task_change=TaskChangePayload(
                    change=TaskChangeKind.REVISE,
                    target_task_ordinals=(1,),
                    task_fields={
                        "statement": "每週彙整營運週報",
                        "action": "彙整",
                        "object": "營運週報",
                    },
                ),
            ),
        ),
        next_question=NextQuestion(
            text="你通常在星期幾完成？",
        ),
    )
    operation_result = TaskAnalysisOperationResult(
        outcome=OperationOutcome.VERIFIED,
        result=result,
        report=VerificationReport(),
    )

    committed = await commit_verified_turn(
        uow_factory,
        snapshot=snapshot,
        operation_id="operation-revise",
        employee_turn=employee,
        operation_result=operation_result,
    )
    loaded = await load_document(uow_factory, document_id)

    assert committed.created_proposal_ids == ("operation-revise-p0",)
    assert loaded is not None
    assert loaded.document.authority_generation == 2
    assert loaded.state.proposals[0].proposal_id == "operation-revise-p0"
    assert loaded.state.current_jd == (jd_task,)
    assert loaded.conversation_turns[-1].speaker is TurnSpeaker.CONSULTANT
