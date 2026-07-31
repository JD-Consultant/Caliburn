"""One no-network vertical across authoring, AI analysis, Proposal, and reload."""

from __future__ import annotations

import pytest

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.job_analysis.application import (
    ConversationTurn,
    OperationOutcome,
    TaskAnalysisOperationResult,
    TurnSpeaker,
    VerificationReport,
    add_jd_task,
    commit_verified_turn,
    create_document,
    decide_proposal,
    edit_jd_task,
    load_document,
    prepare_turn,
    reorder_jd_tasks,
)
from app.job_analysis.domain import JdTaskFields, ProposalStatus
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


async def test_local_document_survives_every_transaction_boundary(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(
        postgres_session_factory
    )
    await create_document(
        uow_factory,
        document_id=document_id,
        title="門市營運專員",
    )

    weekly = await add_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="direct-add-weekly",
        fields=JdTaskFields(statement="整理每週營運資料"),
    )
    weekly = await edit_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="direct-edit-weekly",
        task_id=weekly.task_id,
        fields=JdTaskFields(
            statement="每週彙整營運資料",
            purpose_result="讓主管掌握門市狀況",
            frequency_text="每週一次",
        ),
    )
    monthly = await add_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="direct-add-monthly",
        fields=JdTaskFields(
            statement="每月盤點門市耗材",
            frequency_text="每月一次",
        ),
    )
    await reorder_jd_tasks(
        uow_factory,
        document_id=document_id,
        entry_id="direct-reorder",
        ordered_task_ids=(monthly.task_id, weekly.task_id),
    )

    after_authoring = await load_document(uow_factory, document_id)
    assert after_authoring is not None
    assert [task.statement for task in after_authoring.state.current_jd] == [
        "每月盤點門市耗材",
        "每週彙整營運資料",
    ]

    employee = ConversationTurn(
        turn_id="employee-turn-1",
        speaker=TurnSpeaker.EMPLOYEE,
        text="我每天會追蹤缺料並回報主管",
    )
    snapshot = await prepare_turn(
        uow_factory,
        document_id=document_id,
        employee_turn=employee,
    )
    model_result = TaskAnalysisResult(
        work_signals=(
            WorkSignal(
                anchors=(
                    SignalAnchor(
                        turn_ordinal=snapshot.packet.current_turn_ordinal,
                        quote="我每天會追蹤缺料並回報主管",
                    ),
                ),
                identity=IdentityAssessment(relation=IdentityRelation.NO_MATCH),
                disposition=SignalDisposition.TASK_CHANGE,
                task_change=TaskChangePayload(
                    change=TaskChangeKind.ADD,
                    task_fields={
                        "statement": "每日追蹤缺料並回報主管",
                        "action": "追蹤並回報",
                        "object": "缺料狀況",
                        "purpose_result": "讓主管及時安排補料",
                    },
                ),
            ),
        ),
        next_question=NextQuestion(
            text="你通常透過什麼方式回報缺料？",
        ),
    )
    await commit_verified_turn(
        uow_factory,
        snapshot=snapshot,
        operation_id="analysis-1",
        employee_turn=employee,
        operation_result=TaskAnalysisOperationResult(
            outcome=OperationOutcome.VERIFIED,
            result=model_result,
            report=VerificationReport(),
        ),
    )

    after_analysis = await load_document(uow_factory, document_id)
    assert after_analysis is not None
    proposal = after_analysis.state.proposals[0]
    assert proposal.proposal_id == "analysis-1-p0"
    await decide_proposal(
        uow_factory,
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="decision-accept-shortage",
        decision="accepted",
    )

    reloaded = await load_document(uow_factory, document_id)
    assert reloaded is not None
    assert reloaded.document.authority_generation == 6
    assert [task.statement for task in reloaded.state.current_jd] == [
        "每月盤點門市耗材",
        "每週彙整營運資料",
        "每日追蹤缺料並回報主管",
    ]
    assert (
        reloaded.state.work_model.task_by_id("analysis-1-t0").statement
        == "每日追蹤缺料並回報主管"
    )
    assert reloaded.state.proposals[0].status is ProposalStatus.ACCEPTED
    assert len(reloaded.conversation_turns) == 3
    assert (
        reloaded.document.active_question.text
        == "你通常透過什麼方式回報缺料？"
    )

    async with uow_factory() as uow:
        for entry_id in (
            "direct-add-weekly",
            "direct-edit-weekly",
            "direct-add-monthly",
            "direct-reorder",
            "analysis-1",
            "decision-accept-shortage",
        ):
            assert await uow.journal.get(document_id, entry_id) is not None
