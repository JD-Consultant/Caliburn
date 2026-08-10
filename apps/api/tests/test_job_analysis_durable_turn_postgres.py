"""Durable two-phase AI turns on the greenfield PostgreSQL seam."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

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
    put_jd_header,
    select_scheduled_opks,
)
from app.core.domain import (
    CurrentWorkModel,
    JdHeader,
    JdTask,
    JdTaskFields,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    OpksProposal,
    OpksProposalAction,
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
OPKS_CREATED_AT = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)


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


def persisted_attitude() -> OpksItem:
    return OpksItem(
        entity_id="attitude-1",
        entity_kind=OpksEntityKind.ATTITUDE,
        text="主動釐清異常",
        evidence_links=(
            OpksEvidenceLink(
                source_ref=SourceRef(
                    kind=SourceKind.EMPLOYEE_TURN,
                    id="seed-turn",
                ),
                quote="遇到異常我會主動釐清",
            ),
        ),
    )


def persisted_opks_proposal() -> OpksProposal:
    item = persisted_attitude()
    return OpksProposal(
        proposal_id="opks-proposal-1",
        operation_id="opks-operation-1",
        entity_id=item.entity_id,
        entity_kind=item.entity_kind,
        action=OpksProposalAction.ADD,
        after=item,
        base_authority_generation=0,
        created_at=OPKS_CREATED_AT,
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
    header = JdHeader(
        competency_name="門市營運管理",
        work_description="負責門市日常營運與週報彙整。",
    )
    async with uow_factory() as uow:
        record = await uow.documents.get(document_id, for_update=True)
        assert record is not None
        changed = await uow.documents.update_authority(
            document_id,
            expected_generation=record.authority_generation,
            jd_header=header,
            work_model=record.work_model,
            active_question=record.active_question,
            updated_at=record.updated_at + timedelta(seconds=1),
        )
        assert changed
        await uow.opks.replace(document_id, (persisted_attitude(),))
        await uow.opks_proposals.replace(
            document_id,
            (persisted_opks_proposal(),),
        )
        await uow.commit()
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
    assert loaded.document.authority_generation == 2
    assert loaded.state.jd_header == header
    assert [task.task_id for task in loaded.state.work_model.tasks] == [
        "operation-1-t0"
    ]
    assert loaded.document.active_question is not None
    assert loaded.document.active_question.text == "這份週報主要交給誰？"
    assert loaded.state.current_opks.items == (persisted_attitude(),)
    assert loaded.state.opks_proposals == (persisted_opks_proposal(),)
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


async def test_header_change_after_prepare_rejects_the_old_model_result(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    """Header 是本輪讀取的背景 authority，不能讓舊結果覆蓋新描述。"""

    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    await create_document(
        uow_factory,
        document_id=document_id,
        title="門市營運專員",
    )
    initial_header = JdHeader(
        competency_name="門市營運管理",
        occupation_category_name="商業服務類",
        work_description="負責門市日常營運與週報彙整。",
        competency_level=4,
        notes="只作表頭說明",
    )
    await put_jd_header(
        uow_factory,
        document_id=document_id,
        entry_id="header-before-provider",
        header=initial_header,
    )
    employee = employee_turn()
    snapshot = await prepare_turn(
        uow_factory,
        document_id=document_id,
        employee_turn=employee,
    )
    assert snapshot.packet.employee_written_overview == (
        "職能基準名稱：門市營運管理\n工作描述：負責門市日常營運與週報彙整。"
    )

    changed_header = initial_header.model_copy(
        update={"work_description": "改為負責門市巡檢與異常處理。"}
    )
    await put_jd_header(
        uow_factory,
        document_id=document_id,
        entry_id="header-during-provider",
        header=changed_header,
    )

    with pytest.raises(StaleAuthoritySnapshot):
        await commit_verified_turn(
            uow_factory,
            snapshot=snapshot,
            operation_id="stale-header-operation",
            employee_turn=employee,
            operation_result=verified_add_result(),
        )

    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert loaded.document.authority_generation == 2
    assert loaded.state.jd_header == changed_header
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
            jd_header=record.jd_header,
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

    assert committed.transition.created_proposal_ids == ("operation-revise-p0",)
    assert loaded is not None
    assert loaded.document.authority_generation == 2
    assert loaded.state.proposals[0].proposal_id == "operation-revise-p0"
    assert loaded.state.current_jd == (jd_task,)
    assert loaded.conversation_turns[-1].speaker is TurnSpeaker.CONSULTANT


# ── 主回合凍結的唯一 OPKS child(ADR 0054 決定 7–9)────────────────────────────


def analysed_task(task_id: str = "task-existing") -> Task:
    return Task(
        task_id=task_id,
        statement="每週整理營運週報",
        action="整理",
        object="營運週報",
        support_links=(
            SupportLink(
                source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="old-turn"),
                quote="我每週會整理營運週報",
            ),
        ),
    )


async def seed_analysed_task(uow_factory, document_id, *tasks: Task) -> None:
    async with uow_factory() as uow:
        record = await uow.documents.get(document_id, for_update=True)
        assert record is not None
        changed = await uow.documents.update_authority(
            document_id,
            expected_generation=record.authority_generation,
            jd_header=record.jd_header,
            work_model=CurrentWorkModel(tasks=tasks),
            active_question=None,
            updated_at=record.updated_at + timedelta(seconds=1),
        )
        assert changed
        await uow.tasks.replace(
            document_id,
            tuple(
                JdTask(
                    task_id=task.task_id,
                    statement=task.statement,
                    display_order=order,
                )
                for order, task in enumerate(tasks)
            ),
        )
        await uow.commit()


def blocking_opks_proposal(task_id: str) -> OpksProposal:
    """一筆待決的 O 提案,足以讓 pre-gate 擋住那個 Task。"""

    item = OpksItem(
        entity_id="output-1",
        entity_kind=OpksEntityKind.OUTPUT,
        text="營運週報",
        task_refs=(task_id,),
        evidence_links=(
            OpksEvidenceLink(
                source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="old-turn"),
                quote="我每週會整理營運週報",
            ),
        ),
    )
    return OpksProposal(
        proposal_id="opks-proposal-block",
        operation_id="opks-operation-block",
        entity_id=item.entity_id,
        entity_kind=item.entity_kind,
        action=OpksProposalAction.ADD,
        after=item,
        base_authority_generation=1,
        created_at=OPKS_CREATED_AT,
    )


def verified_support_only_result() -> TaskAnalysisOperationResult:
    """只補依據、不動 Task 的一輪。"""

    result = TaskAnalysisResult(
        work_signals=(
            WorkSignal(
                anchors=(
                    SignalAnchor(turn_ordinal=2, quote="我每週會彙整營運週報"),
                ),
                identity=IdentityAssessment(
                    relation=IdentityRelation.DUPLICATE,
                    target_task_ordinals=(1,),
                ),
                disposition=SignalDisposition.SUPPORT_ONLY,
            ),
        ),
        next_question=NextQuestion(text="這份週報主要交給誰？"),
    )
    return TaskAnalysisOperationResult(
        outcome=OperationOutcome.VERIFIED,
        result=result,
        report=VerificationReport(),
    )


async def test_a_committed_turn_freezes_one_scheduled_opks_child(
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
    await seed_analysed_task(uow_factory, document_id, analysed_task())
    employee = employee_turn()
    snapshot = await prepare_turn(
        uow_factory,
        document_id=document_id,
        employee_turn=employee,
    )

    committed = await commit_verified_turn(
        uow_factory,
        snapshot=snapshot,
        operation_id="operation-1",
        employee_turn=employee,
        operation_result=verified_support_only_result(),
    )

    assert committed.scheduled_opks is not None
    assert committed.scheduled_opks.task_id == "task-existing"
    async with uow_factory() as uow:
        entry = await uow.journal.get(document_id, "operation-1")
    assert entry is not None
    assert entry.payload.scheduled_opks == committed.scheduled_opks


async def test_replay_returns_the_frozen_child_even_after_the_state_moved_on(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    """決定 8:綁定在 receipt 寫入時凍結。

    這是整條線最重要的不變量。沒有它,replay 會重跑 scheduler 並依當下 state 改選,
    使**同一個員工回合付兩次錢**。這裡在第一次提交後放進一筆待決 OPKS Proposal,
    讓 scheduler 現在會做出不同的選擇,再重播同一個 operation。
    """

    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    await create_document(
        uow_factory,
        document_id=document_id,
        title="門市營運專員",
    )
    await seed_analysed_task(uow_factory, document_id, analysed_task())
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
        operation_result=verified_support_only_result(),
    )
    assert first.scheduled_opks is not None

    async with uow_factory() as uow:
        await uow.opks_proposals.replace(
            document_id,
            (blocking_opks_proposal(first.scheduled_opks.task_id),),
        )
        await uow.commit()
    moved_on = await load_document(uow_factory, document_id)
    assert moved_on is not None
    async with uow_factory() as uow:
        reselected = await select_scheduled_opks(
            uow,
            document_id=document_id,
            state=moved_on.state,
        )
    assert reselected is None, "前置條件:scheduler 現在會做出不同的選擇"

    replay = await commit_verified_turn(
        uow_factory,
        snapshot=snapshot,
        operation_id="operation-1",
        employee_turn=employee,
        operation_result=verified_support_only_result(),
    )

    assert replay.scheduled_opks == first.scheduled_opks


async def test_a_turn_with_nothing_analysable_schedules_no_child(
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

    committed = await commit_verified_turn(
        uow_factory,
        snapshot=snapshot,
        operation_id="operation-1",
        employee_turn=employee,
        operation_result=verified_add_result(),
    )

    assert committed.scheduled_opks is None
