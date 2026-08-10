"""Duty authoring must use the same durable Current-JD authority seam."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.documents import (
    InvalidDutyOrder,
    add_duty,
    add_jd_task,
    delete_duty,
    edit_duty,
    edit_jd_task,
    load_document,
    reorder_duties,
)
from app.documents.authoring import create_document
from app.core.journal import ConversationTurn, TurnSpeaker
from app.core.model_outcome import OperationOutcome
from app.core.state import JobAnalysisState
from app.job_analysis.application import (
    DutyDirectEditPayload,
    IdempotencyConflict,
    commit_verified_turn,
    prepare_turn,
)
from app.opks import (
    OpksOperationResult,
    commit_opks_generation,
    compute_analysis_input_digest,
    prepare_opks_generation,
)
from app.task_analysis import (
    TaskAnalysisOperationResult,
    VerificationReport,
    decide_proposal,
)
from app.core.authority import commit_authority_change
from app.core.domain import (
    CurrentJdOpks,
    CurrentWorkModel,
    JdEntry,
    JdTask,
    JdTaskFields,
    Proposal,
    ProposalAction,
    ProposalStatus,
    SourceKind,
    SourceRef,
    SingleTaskTarget,
    SupportLink,
    Task,
)
from app.task_analysis.llm import NextQuestion, TaskAnalysisResult


pytestmark = pytest.mark.asyncio


def _factory(session_factory):
    return lambda: SqlAlchemyJobAnalysisUnitOfWork(session_factory)


def _fields(
    statement: str,
    *,
    duty_id: str | None = None,
    competency_level: int | None = None,
) -> JdTaskFields:
    return JdTaskFields(
        statement=statement,
        duty_id=duty_id,
        competency_level=competency_level,
    )


async def _seed_document_with_assigned_tasks(session_factory, document_id):
    factory = _factory(session_factory)
    await create_document(factory, document_id=document_id, title="門市營運專員")
    first_duty = await add_duty(
        factory,
        document_id=document_id,
        entry_id="duty-add-1",
        statement="門市營運管理",
    )
    second_duty = await add_duty(
        factory,
        document_id=document_id,
        entry_id="duty-add-2",
        statement="例行報表與追蹤",
    )
    first_task = await add_jd_task(
        factory,
        document_id=document_id,
        entry_id="task-add-1",
        fields=_fields("盤點門市庫存"),
    )
    second_task = await add_jd_task(
        factory,
        document_id=document_id,
        entry_id="task-add-2",
        fields=_fields("彙整營運週報"),
    )
    first_task = await edit_jd_task(
        factory,
        document_id=document_id,
        entry_id="task-assign-1",
        task_id=first_task.task_id,
        fields=_fields(
            first_task.statement,
            duty_id=first_duty.duty_id,
            competency_level=3,
        ),
    )
    second_task = await edit_jd_task(
        factory,
        document_id=document_id,
        entry_id="task-assign-2",
        task_id=second_task.task_id,
        fields=_fields(
            second_task.statement,
            duty_id=second_duty.duty_id,
            competency_level=4,
        ),
    )
    return factory, first_duty, second_duty, first_task, second_task


async def test_postgres_rejects_a_task_with_a_dangling_duty_reference(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    """The deferred FK must fail at commit, not merely exist in metadata."""

    document_id = cleanup_job_analysis_rows
    factory = _factory(postgres_session_factory)
    await create_document(factory, document_id=document_id, title="門市營運專員")

    with pytest.raises(IntegrityError):
        async with factory() as uow:
            await uow.tasks.replace(
                document_id,
                (
                    JdTask(
                        task_id="dangling-task",
                        statement="盤點門市庫存",
                        duty_id="missing-duty",
                        display_order=0,
                    ),
                ),
            )
            await uow.commit()

    loaded = await load_document(factory, document_id)
    assert loaded is not None
    assert loaded.state.current_jd == ()


async def test_add_edit_reorder_and_replay_duties_through_authority_journal(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    """Removing receipt-first handling would duplicate a Duty on a retry."""

    document_id = cleanup_job_analysis_rows
    factory = _factory(postgres_session_factory)
    await create_document(factory, document_id=document_id, title="門市營運專員")

    first = await add_duty(
        factory,
        document_id=document_id,
        entry_id="duty-add-1",
        statement="門市營運管理",
    )
    second = await add_duty(
        factory,
        document_id=document_id,
        entry_id="duty-add-2",
        statement="例行報表與追蹤",
    )
    replay = await add_duty(
        factory,
        document_id=document_id,
        entry_id="duty-add-1",
        statement="門市營運管理",
    )
    edited = await edit_duty(
        factory,
        document_id=document_id,
        entry_id="duty-edit-1",
        duty_id=first.duty_id,
        statement="門市營運與庫存管理",
    )
    reordered = await reorder_duties(
        factory,
        document_id=document_id,
        entry_id="duty-order-1",
        ordered_duty_ids=(second.duty_id, first.duty_id),
    )
    replay_order = await reorder_duties(
        factory,
        document_id=document_id,
        entry_id="duty-order-1",
        ordered_duty_ids=(second.duty_id, first.duty_id),
    )
    loaded = await load_document(factory, document_id)

    assert first.duty_id == "duty-add-1-d0"
    assert replay == first
    assert edited.duty_id == first.duty_id
    assert edited.display_order == first.display_order
    assert [duty.duty_id for duty in reordered] == [second.duty_id, first.duty_id]
    assert replay_order == reordered
    assert loaded is not None
    assert loaded.state.current_duties == reordered
    assert loaded.document.authority_generation == 4

    with pytest.raises(IdempotencyConflict):
        await add_duty(
            factory,
            document_id=document_id,
            entry_id="duty-add-1",
            statement="另一個主要職責",
        )
    with pytest.raises(InvalidDutyOrder):
        await reorder_duties(
            factory,
            document_id=document_id,
            entry_id="duty-order-invalid",
            ordered_duty_ids=(first.duty_id, first.duty_id),
        )


async def test_delete_duty_unassigns_only_its_tasks_and_stales_only_related_proposals(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    """Deleting a Duty must never delete its Tasks or mutate their Work Model."""

    document_id = cleanup_job_analysis_rows
    factory, first_duty, second_duty, first_task, second_task = (
        await _seed_document_with_assigned_tasks(
            postgres_session_factory,
            document_id,
        )
    )
    first_pending = Proposal(
        proposal_id="proposal-first",
        target=SingleTaskTarget(
            action=ProposalAction.REVISE,
            task_id=first_task.task_id,
        ),
        jd_before=(JdEntry(task_id=first_task.task_id, value=first_task),),
        jd_after=(
            JdEntry(
                task_id=first_task.task_id,
                value=first_task.model_copy(update={"statement": "檢核門市庫存"}),
            ),
        ),
    )
    unrelated_pending = Proposal(
        proposal_id="proposal-second",
        target=SingleTaskTarget(
            action=ProposalAction.REVISE,
            task_id=second_task.task_id,
        ),
        jd_before=(JdEntry(task_id=second_task.task_id, value=second_task),),
        jd_after=(
            JdEntry(
                task_id=second_task.task_id,
                value=second_task.model_copy(update={"statement": "檢核營運週報"}),
            ),
        ),
    )
    async with factory() as uow:
        await uow.proposals.replace(document_id, (first_pending, unrelated_pending))
        await uow.commit()
    before = await load_document(factory, document_id)

    await delete_duty(
        factory,
        document_id=document_id,
        entry_id="duty-delete-1",
        duty_id=first_duty.duty_id,
    )
    await delete_duty(
        factory,
        document_id=document_id,
        entry_id="duty-delete-1",
        duty_id=first_duty.duty_id,
    )
    after = await load_document(factory, document_id)

    assert before is not None
    assert after is not None
    assert after.state.work_model == before.state.work_model
    assert [duty.duty_id for duty in after.state.current_duties] == [second_duty.duty_id]
    by_id = {task.task_id: task for task in after.state.current_jd}
    assert by_id[first_task.task_id].duty_id is None
    assert by_id[first_task.task_id].competency_level == 3
    assert by_id[second_task.task_id].duty_id == second_duty.duty_id
    assert by_id[second_task.task_id].competency_level == 4
    proposals = {proposal.proposal_id: proposal for proposal in after.state.proposals}
    assert proposals[first_pending.proposal_id].status is ProposalStatus.STALE
    assert proposals[unrelated_pending.proposal_id].status is ProposalStatus.PENDING

    async with factory() as uow:
        entry = await uow.journal.get(document_id, "duty-delete-1")
    assert entry is not None
    assert isinstance(entry.payload, DutyDirectEditPayload)
    assert entry.payload.before == first_duty
    assert entry.payload.after is None


async def test_duty_and_task_level_survive_task_edit_proposal_decision_durable_turn_and_opks_operation(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    """Any loader that substitutes current_duties=() would fail this authority chain."""

    document_id = cleanup_job_analysis_rows
    factory = _factory(postgres_session_factory)
    await create_document(factory, document_id=document_id, title="門市營運專員")
    duty = await add_duty(
        factory,
        document_id=document_id,
        entry_id="duty-seed",
        statement="門市庫存管理",
    )
    current_task = JdTask(
        task_id="task-stable",
        statement="盤點門市庫存",
        duty_id=duty.duty_id,
        competency_level=3,
        display_order=0,
    )
    work_task = Task(
        task_id=current_task.task_id,
        statement="盤點門市庫存",
        action="盤點",
        object="門市庫存",
        support_links=(
            SupportLink(
                source_ref=SourceRef(
                    kind=SourceKind.EMPLOYEE_TURN,
                    id="seed-evidence",
                ),
                quote="我每週會盤點門市庫存",
            ),
        ),
    )
    async with factory() as uow:
        record = await uow.documents.get(document_id, for_update=True)
        assert record is not None
        await commit_authority_change(
            uow,
            record=record,
            state=JobAnalysisState(
                jd_header=record.jd_header,
                current_duties=(duty,),
                work_model=CurrentWorkModel(tasks=(work_task,)),
                current_jd=(current_task,),
                current_opks=CurrentJdOpks(),
                opks_proposals=(),
            ),
            updated_at=record.updated_at,
        )

    pending = Proposal(
        proposal_id="duty-preservation-proposal",
        target=SingleTaskTarget(
            action=ProposalAction.REVISE,
            task_id=current_task.task_id,
        ),
        jd_before=(JdEntry(task_id=current_task.task_id, value=current_task),),
        jd_after=(
            JdEntry(
                task_id=current_task.task_id,
                value=current_task.model_copy(
                    update={"statement": "檢核門市庫存"}
                ),
            ),
        ),
    )
    async with factory() as uow:
        await uow.proposals.replace(document_id, (pending,))
        await uow.commit()

    deferred = await decide_proposal(
        factory,
        document_id=document_id,
        proposal_id=pending.proposal_id,
        decision_id="duty-preservation-decision",
        decision="deferred",
    )
    assert deferred.status is ProposalStatus.DEFERRED

    employee = ConversationTurn(
        turn_id="duty-preservation-turn",
        speaker=TurnSpeaker.EMPLOYEE,
        text="我每週會盤點門市庫存",
    )
    turn_snapshot = await prepare_turn(
        factory,
        document_id=document_id,
        employee_turn=employee,
    )
    await commit_verified_turn(
        factory,
        snapshot=turn_snapshot,
        operation_id="duty-preservation-turn-operation",
        employee_turn=employee,
        operation_result=TaskAnalysisOperationResult(
            outcome=OperationOutcome.VERIFIED,
            result=TaskAnalysisResult(
                next_question=NextQuestion(text="盤點差異通常怎麼處理？")
            ),
            report=VerificationReport(),
        ),
    )

    digest = compute_analysis_input_digest(work_task)
    opks_snapshot = await prepare_opks_generation(
        factory,
        document_id=document_id,
        task_id=current_task.task_id,
        expected_digest=digest,
    )
    opks_result = await commit_opks_generation(
        factory,
        snapshot=opks_snapshot,
        operation_id="duty-preservation-opks",
        operation_result=OpksOperationResult(
            outcome=OperationOutcome.FAILED,
            detail="test provider failure",
        ),
    )
    assert opks_result.outcome.value == "failed"

    await edit_jd_task(
        factory,
        document_id=document_id,
        entry_id="duty-preservation-task-edit",
        task_id=current_task.task_id,
        fields=_fields(
            "檢核門市庫存",
            duty_id=duty.duty_id,
            competency_level=3,
        ),
    )

    reloaded = await load_document(factory, document_id)

    assert reloaded is not None
    assert reloaded.state.current_duties == (duty,)
    assert reloaded.state.current_jd[0].duty_id == duty.duty_id
    assert reloaded.state.current_jd[0].competency_level == 3
    assert current_task.task_id in {
        task.task_id for task in reloaded.state.current_jd
    }
