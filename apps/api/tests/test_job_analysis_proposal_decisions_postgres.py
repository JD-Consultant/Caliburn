"""Employee Proposal decisions persist and update both authority layers atomically."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.job_analysis.application import (
    IdempotencyConflict,
    ProposalNotDecidable,
    create_document,
    decide_proposal,
    load_document,
)
from app.job_analysis.domain import (
    CurrentWorkModel,
    JdEntry,
    JdTask,
    MergeTarget,
    Proposal,
    ProposalAction,
    ProposalStatus,
    Retirement,
    RetirementKind,
    SingleTaskTarget,
    SourceKind,
    SourceRef,
    StagedTask,
    StagedTaskLineage,
    StagedWorkModelDelta,
    SupportLink,
    Task,
    TaskFields,
    TaskState,
)


pytestmark = pytest.mark.asyncio


def factory(session_factory):
    return lambda: SqlAlchemyJobAnalysisUnitOfWork(session_factory)


def support(quote: str) -> SupportLink:
    return SupportLink(
        source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="employee-1"),
        quote=quote,
    )


def task(task_id: str, statement: str) -> Task:
    return Task(
        task_id=task_id,
        statement=statement,
        action="彙整",
        object=statement,
        support_links=(support(statement),),
    )


def jd_task(task_id: str, statement: str, order: int = 0) -> JdTask:
    return JdTask(task_id=task_id, statement=statement, display_order=order)


def add_proposal() -> tuple[CurrentWorkModel, tuple[JdTask, ...], Proposal]:
    candidate = task("task-new", "每週彙整營運週報")
    jd_after = jd_task(candidate.task_id, candidate.statement)
    proposal = Proposal(
        proposal_id="proposal-add",
        target=SingleTaskTarget(
            action=ProposalAction.ADD,
            task_id=candidate.task_id,
        ),
        jd_before=(JdEntry(task_id=candidate.task_id, value=None),),
        jd_after=(JdEntry(task_id=candidate.task_id, value=jd_after),),
    )
    return CurrentWorkModel(tasks=(candidate,)), (), proposal


def merge_proposal() -> tuple[CurrentWorkModel, tuple[JdTask, ...], Proposal]:
    first = task("task-1", "彙整每日營運數據")
    second = task("task-2", "製作每週營運週報")
    merged_fields = TaskFields(
        statement="彙整營運數據並製作週報",
        action="彙整並製作",
        object="營運數據與週報",
    )
    source = SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="employee-1")
    merged = StagedTask(
        task_id="task-merged",
        fields=merged_fields,
        support_links=(support("彙整每日營運數據"), support("製作每週營運週報")),
    )
    delta = StagedWorkModelDelta(
        lineage_changes=(
            StagedTaskLineage(
                task_id="task-1",
                retirement=Retirement(kind=RetirementKind.MERGED, source_ref=source),
                merged_into="task-merged",
            ),
            StagedTaskLineage(
                task_id="task-2",
                retirement=Retirement(kind=RetirementKind.MERGED, source_ref=source),
                merged_into="task-merged",
            ),
        ),
        new_tasks=(merged,),
    )
    current_jd = (
        jd_task("task-1", first.statement, 0),
        jd_task("task-2", second.statement, 1),
    )
    merged_jd = jd_task("task-merged", merged_fields.statement, 0)
    proposal = Proposal(
        proposal_id="proposal-merge",
        target=MergeTarget(
            new_task_id="task-merged",
            member_task_ids=("task-1", "task-2"),
        ),
        jd_before=(
            JdEntry(task_id="task-1", value=current_jd[0]),
            JdEntry(task_id="task-2", value=current_jd[1]),
            JdEntry(task_id="task-merged", value=None),
        ),
        jd_after=(
            JdEntry(task_id="task-1", value=None),
            JdEntry(task_id="task-2", value=None),
            JdEntry(task_id="task-merged", value=merged_jd),
        ),
        staged_work_model_delta=delta,
    )
    return CurrentWorkModel(tasks=(first, second)), current_jd, proposal


async def seed(
    session_factory,
    document_id,
    *,
    work_model: CurrentWorkModel,
    current_jd: tuple[JdTask, ...],
    proposal: Proposal,
) -> None:
    uow_factory = factory(session_factory)
    await create_document(
        uow_factory,
        document_id=document_id,
        title="門市營運專員",
    )
    async with uow_factory() as uow:
        record = await uow.documents.get(document_id, for_update=True)
        assert record is not None
        updated = await uow.documents.update_authority(
            document_id,
            expected_generation=record.authority_generation,
            work_model=work_model,
            active_question=None,
            updated_at=record.updated_at + timedelta(seconds=1),
        )
        assert updated
        await uow.tasks.replace(document_id, current_jd)
        await uow.proposals.replace(document_id, (proposal,))
        await uow.commit()


async def test_accept_adds_the_task_to_current_jd_and_replay_is_a_noop(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    work_model, current_jd, proposal = add_proposal()
    await seed(
        postgres_session_factory,
        document_id,
        work_model=work_model,
        current_jd=current_jd,
        proposal=proposal,
    )
    uow_factory = factory(postgres_session_factory)

    accepted = await decide_proposal(
        uow_factory,
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="decision-accept",
        decision="accepted",
    )
    replay = await decide_proposal(
        uow_factory,
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="decision-accept",
        decision="accepted",
    )
    loaded = await load_document(uow_factory, document_id)

    assert accepted.status is ProposalStatus.ACCEPTED
    assert replay == accepted
    assert loaded is not None
    assert [item.task_id for item in loaded.state.current_jd] == ["task-new"]
    assert loaded.document.authority_generation == 2


async def test_edited_acceptance_saves_employee_text_and_marks_reconciliation(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    work_model, current_jd, proposal = add_proposal()
    await seed(
        postgres_session_factory,
        document_id,
        work_model=work_model,
        current_jd=current_jd,
        proposal=proposal,
    )
    edited = (
        JdEntry(
            task_id="task-new",
            value=jd_task("task-new", "員工修改後的營運週報工作"),
        ),
    )

    decided = await decide_proposal(
        factory(postgres_session_factory),
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="decision-edit",
        decision="edited",
        edited_jd_after=edited,
    )
    loaded = await load_document(factory(postgres_session_factory), document_id)

    assert decided.status is ProposalStatus.EDITED
    assert loaded is not None
    assert loaded.state.current_jd[0].statement == "員工修改後的營運週報工作"
    assert (
        loaded.state.work_model.task_by_id("task-new").pending_reconciliation
        == SourceRef(kind=SourceKind.PROPOSAL_DECISION, id="decision-edit")
    )
    with pytest.raises(IdempotencyConflict):
        await decide_proposal(
            factory(postgres_session_factory),
            document_id=document_id,
            proposal_id=proposal.proposal_id,
            decision_id="decision-edit",
            decision="edited",
            edited_jd_after=(
                JdEntry(
                    task_id="task-new",
                    value=jd_task("task-new", "同一決定 ID 的另一份文字"),
                ),
            ),
        )


async def test_deferred_proposal_survives_reload_and_can_later_be_rejected(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    work_model, current_jd, proposal = add_proposal()
    await seed(
        postgres_session_factory,
        document_id,
        work_model=work_model,
        current_jd=current_jd,
        proposal=proposal,
    )
    uow_factory = factory(postgres_session_factory)

    await decide_proposal(
        uow_factory,
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="decision-defer",
        decision="deferred",
    )
    reloaded = await load_document(uow_factory, document_id)
    assert reloaded is not None
    assert reloaded.state.proposals[0].status is ProposalStatus.DEFERRED

    rejected = await decide_proposal(
        uow_factory,
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="decision-reject",
        decision="rejected",
        reason="這不是我的固定工作",
    )
    assert rejected.status is ProposalStatus.REJECTED

    with pytest.raises(ProposalNotDecidable):
        await decide_proposal(
            uow_factory,
            document_id=document_id,
            proposal_id=proposal.proposal_id,
            decision_id="another-decision",
            decision="accepted",
        )


async def test_accept_merge_atomically_updates_current_jd_and_work_model(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    work_model, current_jd, proposal = merge_proposal()
    await seed(
        postgres_session_factory,
        document_id,
        work_model=work_model,
        current_jd=current_jd,
        proposal=proposal,
    )

    await decide_proposal(
        factory(postgres_session_factory),
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="decision-merge",
        decision="accepted",
    )
    loaded = await load_document(factory(postgres_session_factory), document_id)

    assert loaded is not None
    assert [item.task_id for item in loaded.state.current_jd] == ["task-merged"]
    assert loaded.state.work_model.task_by_id("task-merged").state is TaskState.ACTIVE
    assert loaded.state.work_model.task_by_id("task-1").state is TaskState.RETIRED
    assert loaded.state.work_model.task_by_id("task-2").state is TaskState.RETIRED


async def test_revision_request_preserves_the_exclusion_without_applying_delta(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    work_model, current_jd, proposal = merge_proposal()
    await seed(
        postgres_session_factory,
        document_id,
        work_model=work_model,
        current_jd=current_jd,
        proposal=proposal,
    )

    decided = await decide_proposal(
        factory(postgres_session_factory),
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="decision-revision",
        decision="revision_requested",
        excluded_member_task_ids=("task-2",),
    )
    loaded = await load_document(factory(postgres_session_factory), document_id)

    assert decided.status is ProposalStatus.REVISION_REQUESTED
    assert decided.excluded_member_task_ids == ("task-2",)
    assert loaded is not None
    assert loaded.state.current_jd == current_jd
    assert all(item.state is TaskState.ACTIVE for item in loaded.state.work_model.tasks)


async def test_changed_jd_precondition_marks_the_proposal_stale(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    work_model, _, proposal = add_proposal()
    already_present = (jd_task("task-new", "員工已直接加入的版本"),)
    await seed(
        postgres_session_factory,
        document_id,
        work_model=work_model,
        current_jd=already_present,
        proposal=proposal,
    )

    stale = await decide_proposal(
        factory(postgres_session_factory),
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="decision-too-late",
        decision="accepted",
    )
    loaded = await load_document(factory(postgres_session_factory), document_id)

    assert stale.status is ProposalStatus.STALE
    assert loaded is not None
    assert loaded.state.current_jd == already_present
