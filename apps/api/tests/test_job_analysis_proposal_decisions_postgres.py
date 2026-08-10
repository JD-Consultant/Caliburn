"""Employee Proposal decisions persist and update both authority layers atomically."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.documents import load_document
from app.documents.authoring import create_document
from app.core.errors import IdempotencyConflict
from app.task_analysis import ProposalNotDecidable, decide_proposal, propose_task_for_jd
from app.core.domain import (
    CurrentWorkModel,
    JdEntry,
    JdHeader,
    JdTask,
    MergeTarget,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    OpksProposal,
    OpksProposalAction,
    OpksProposalStatus,
    OpenIssue,
    OpenIssueKind,
    Proposal,
    ProposalAction,
    ProposalStatus,
    Retirement,
    RetirementKind,
    RetirementReason,
    SingleTaskTarget,
    SplitTarget,
    SourceKind,
    SourceAnchor,
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
NOW = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


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


def opks_item(
    entity_id: str,
    entity_kind: OpksEntityKind,
    text: str,
    *,
    task_refs: tuple[str, ...] = (),
    indicator_refs: tuple[str, ...] = (),
) -> OpksItem:
    return OpksItem(
        entity_id=entity_id,
        entity_kind=entity_kind,
        text=text,
        task_refs=task_refs,
        indicator_refs=indicator_refs,
        evidence_links=(
            OpksEvidenceLink(
                source_ref=SourceRef(kind=SourceKind.DIRECT_EDIT, id="edit-opks"),
            ),
        ),
    )


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


def jd_only_withdraw_proposal():
    task_id = "task-direct-1"
    current = jd_task(task_id, "只幫同事做過一次盤點")
    issue = OpenIssue(
        id="issue-direct-1",
        kind=OpenIssueKind.INSUFFICIENT_EVIDENCE,
        summary="需要確認是否為固定責任",
        source_anchors=(
            SourceAnchor(
                source_ref=SourceRef(kind=SourceKind.DIRECT_EDIT, id="edit-1")
            ),
        ),
        reconciliation_task_id=task_id,
    )
    proposal = Proposal(
        proposal_id="proposal-jd-only-withdraw",
        target=SingleTaskTarget(
            action=ProposalAction.WITHDRAW,
            task_id=task_id,
        ),
        jd_before=(JdEntry(task_id=task_id, value=current),),
        jd_after=(JdEntry(task_id=task_id, value=None),),
    )
    return CurrentWorkModel(open_issues=(issue,)), (current,), proposal


def split_proposal() -> tuple[CurrentWorkModel, tuple[JdTask, ...], Proposal]:
    parent = task("task-parent", "維護營運資料並製作週報")
    first_fields = TaskFields(
        statement="維護營運資料",
        action="維護",
        object="營運資料",
    )
    second_fields = TaskFields(
        statement="製作營運週報",
        action="製作",
        object="營運週報",
    )
    source = SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="employee-1")
    child_a = StagedTask(
        task_id="task-child-a",
        fields=first_fields,
        support_links=(support("維護營運資料"),),
    )
    child_b = StagedTask(
        task_id="task-child-b",
        fields=second_fields,
        support_links=(support("製作營運週報"),),
    )
    delta = StagedWorkModelDelta(
        lineage_changes=(
            StagedTaskLineage(
                task_id="task-parent",
                retirement=Retirement(kind=RetirementKind.SPLIT, source_ref=source),
            ),
            StagedTaskLineage(task_id="task-child-a", split_from="task-parent"),
            StagedTaskLineage(task_id="task-child-b", split_from="task-parent"),
        ),
        new_tasks=(child_a, child_b),
    )
    current_jd = (jd_task("task-parent", parent.statement),)
    proposal = Proposal(
        proposal_id="proposal-split",
        target=SplitTarget(
            parent_task_id="task-parent",
            child_task_ids=("task-child-a", "task-child-b"),
        ),
        jd_before=(
            JdEntry(task_id="task-child-a", value=None),
            JdEntry(task_id="task-child-b", value=None),
            JdEntry(task_id="task-parent", value=current_jd[0]),
        ),
        jd_after=(
            JdEntry(
                task_id="task-child-a",
                value=jd_task("task-child-a", first_fields.statement, 0),
            ),
            JdEntry(
                task_id="task-child-b",
                value=jd_task("task-child-b", second_fields.statement, 1),
            ),
            JdEntry(task_id="task-parent", value=None),
        ),
        staged_work_model_delta=delta,
    )
    return CurrentWorkModel(tasks=(parent,)), current_jd, proposal


async def seed(
    session_factory,
    document_id,
    *,
    work_model: CurrentWorkModel,
    current_jd: tuple[JdTask, ...],
    proposal: Proposal | None,
    current_opks: tuple[OpksItem, ...] = (),
    opks_proposals: tuple[OpksProposal, ...] = (),
    jd_header: JdHeader | None = None,
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
            jd_header=jd_header if jd_header is not None else record.jd_header,
            work_model=work_model,
            active_question=None,
            updated_at=record.updated_at + timedelta(seconds=1),
        )
        assert updated
        await uow.tasks.replace(document_id, current_jd)
        await uow.proposals.replace(
            document_id,
            (proposal,) if proposal is not None else (),
        )
        await uow.opks.replace(document_id, current_opks)
        await uow.opks_proposals.replace(document_id, opks_proposals)
        await uow.commit()


async def test_active_candidate_can_become_a_pending_add_proposal(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    candidate = task("task-new", "每週彙整營運週報")
    await seed(
        postgres_session_factory,
        document_id,
        work_model=CurrentWorkModel(tasks=(candidate,)),
        current_jd=(),
        proposal=None,
    )
    uow_factory = factory(postgres_session_factory)

    proposed = await propose_task_for_jd(
        uow_factory,
        document_id=document_id,
        task_id=candidate.task_id,
        proposal_id="proposal-add",
    )
    replay = await propose_task_for_jd(
        uow_factory,
        document_id=document_id,
        task_id=candidate.task_id,
        proposal_id="proposal-add",
    )
    loaded = await load_document(uow_factory, document_id)

    assert proposed == replay
    assert proposed.status is ProposalStatus.PENDING
    assert proposed.action is ProposalAction.ADD
    assert loaded is not None
    assert loaded.state.current_jd == ()
    assert loaded.state.proposals == (proposed,)


async def test_accept_adds_the_task_to_current_jd_and_replay_is_a_noop(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    work_model, current_jd, proposal = add_proposal()
    header = JdHeader(
        competency_name="門市營運管理",
        work_description="負責門市日常營運與週報彙整。",
    )
    await seed(
        postgres_session_factory,
        document_id,
        work_model=work_model,
        current_jd=current_jd,
        proposal=proposal,
        jd_header=header,
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
    assert loaded.state.jd_header == header


async def test_accepting_several_add_proposals_gives_each_task_its_own_position(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    """一次訪談產出多筆 add 提案是常態,而它們的 `display_order` 全都是 0。

    `transition._next_jd_order()` 讀的是**提案建立當下**的 Current JD;訪談期間 JD 是空的,
    所以每一筆 add 都算出 0。照抄那個值的話第二筆一被接受就撞上「display order 必須唯一」,
    員工在 UI 上按第二個 accept 就失敗——AI 找到的工作永遠進不完 JD。
    位置是 JD 清單的性質,不是提案的內容,要在**插入時**才決定。
    """
    document_id = cleanup_job_analysis_rows
    candidates = tuple(
        task(f"task-{index}", statement)
        for index, statement in enumerate(("每週彙整營運週報", "維護資料匯入程式"))
    )
    proposals = tuple(
        Proposal(
            proposal_id=f"proposal-add-{index}",
            target=SingleTaskTarget(
                action=ProposalAction.ADD, task_id=candidate.task_id
            ),
            jd_before=(JdEntry(task_id=candidate.task_id, value=None),),
            jd_after=(
                JdEntry(
                    task_id=candidate.task_id,
                    # 兩筆都是 0,正是 transition 對空 JD 會產生的值。
                    value=jd_task(candidate.task_id, candidate.statement, order=0),
                ),
            ),
        )
        for index, candidate in enumerate(candidates)
    )
    await seed(
        postgres_session_factory,
        document_id,
        work_model=CurrentWorkModel(tasks=candidates),
        current_jd=(),
        proposal=None,
    )
    uow_factory = factory(postgres_session_factory)
    async with uow_factory() as uow:
        await uow.proposals.replace(document_id, proposals)
        await uow.commit()

    for index, proposal in enumerate(proposals):
        decided = await decide_proposal(
            uow_factory,
            document_id=document_id,
            proposal_id=proposal.proposal_id,
            decision_id=f"decision-accept-{index}",
            decision="accepted",
        )
        assert decided.status is ProposalStatus.ACCEPTED

    loaded = await load_document(uow_factory, document_id)

    assert loaded is not None
    assert [item.task_id for item in loaded.state.current_jd] == ["task-0", "task-1"]
    assert [item.display_order for item in loaded.state.current_jd] == [0, 1]


async def test_accept_jd_only_withdraw_removes_the_jd_task_and_dangling_issue(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    work_model, current_jd, proposal = jd_only_withdraw_proposal()
    output = opks_item(
        "output-withdrawn",
        OpksEntityKind.OUTPUT,
        "每週營運週報",
        task_refs=("task-direct-1",),
    )
    knowledge = opks_item(
        "knowledge-withdrawn",
        OpksEntityKind.KNOWLEDGE,
        "營運資料定義",
        task_refs=("task-direct-1",),
    )
    attitude = opks_item(
        "attitude-kept",
        OpksEntityKind.ATTITUDE,
        "主動釐清異常",
    )
    await seed(
        postgres_session_factory,
        document_id,
        work_model=work_model,
        current_jd=current_jd,
        proposal=proposal,
        current_opks=(output, knowledge, attitude),
    )

    accepted = await decide_proposal(
        factory(postgres_session_factory),
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="decision-withdraw-jd-only",
        decision="accepted",
    )
    loaded = await load_document(factory(postgres_session_factory), document_id)

    assert accepted.status is ProposalStatus.ACCEPTED
    assert loaded is not None
    assert loaded.state.current_jd == ()
    assert loaded.state.work_model.tasks == ()
    assert loaded.state.work_model.open_issues == ()
    opks_by_id = {
        item.entity_id: item for item in loaded.state.current_opks.items
    }
    assert opks_by_id == {
        knowledge.entity_id: knowledge.model_copy(update={"task_refs": ()}),
        attitude.entity_id: attitude,
    }


async def test_delta_less_withdraw_goes_stale_if_an_active_work_model_task_now_exists(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    _, current_jd, proposal = jd_only_withdraw_proposal()
    active = task("task-direct-1", current_jd[0].statement)
    await seed(
        postgres_session_factory,
        document_id,
        work_model=CurrentWorkModel(tasks=(active,)),
        current_jd=current_jd,
        proposal=proposal,
    )

    stale = await decide_proposal(
        factory(postgres_session_factory),
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="decision-stale-withdraw",
        decision="accepted",
    )
    loaded = await load_document(factory(postgres_session_factory), document_id)

    assert stale.status is ProposalStatus.STALE
    assert loaded is not None
    assert loaded.state.current_jd == current_jd
    assert loaded.state.work_model.task_by_id("task-direct-1").state is TaskState.ACTIVE


async def test_old_withdraw_delta_cannot_overwrite_a_newer_retirement(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    task_id = "task-existing"
    current = jd_task(task_id, "每週彙整營運週報")
    old_source = SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="employee-old")
    newer_retirement = Retirement(
        kind=RetirementKind.WITHDRAWN,
        reason=RetirementReason.ONE_OFF,
        source_ref=old_source,
    )
    retired = task(task_id, current.statement).model_copy(
        update={"retirement": newer_retirement}
    )
    stale_delta = StagedWorkModelDelta(
        lineage_changes=(
            StagedTaskLineage(
                task_id=task_id,
                retirement=Retirement(
                    kind=RetirementKind.WITHDRAWN,
                    reason=RetirementReason.EMPLOYEE_DENIED,
                    source_ref=SourceRef(
                        kind=SourceKind.EMPLOYEE_TURN,
                        id="employee-stale",
                    ),
                ),
            ),
        )
    )
    proposal = Proposal(
        proposal_id="proposal-old-withdraw",
        target=SingleTaskTarget(
            action=ProposalAction.WITHDRAW,
            task_id=task_id,
        ),
        jd_before=(JdEntry(task_id=task_id, value=current),),
        jd_after=(JdEntry(task_id=task_id, value=None),),
        staged_work_model_delta=stale_delta,
    )
    await seed(
        postgres_session_factory,
        document_id,
        work_model=CurrentWorkModel(tasks=(retired,)),
        current_jd=(current,),
        proposal=proposal,
    )

    stale = await decide_proposal(
        factory(postgres_session_factory),
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="decision-old-withdraw",
        decision="accepted",
    )
    loaded = await load_document(factory(postgres_session_factory), document_id)

    assert stale.status is ProposalStatus.STALE
    assert loaded is not None
    preserved = loaded.state.work_model.task_by_id(task_id)
    assert preserved.retirement == newer_retirement
    assert loaded.state.current_jd == (current,)


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
    output = opks_item(
        "output-task-1",
        OpksEntityKind.OUTPUT,
        "門市資料",
        task_refs=("task-1",),
    )
    indicator = opks_item(
        "indicator-task-2",
        OpksEntityKind.INDICATOR,
        "每週完成週報",
        task_refs=("task-2",),
    )
    skill = opks_item(
        "skill-shared",
        OpksEntityKind.SKILL,
        "試算表整理",
        task_refs=("task-1", "task-2"),
        indicator_refs=(indicator.entity_id,),
    )
    pending_opks_proposal = OpksProposal(
        proposal_id="opks-revise-skill",
        operation_id="opks-operation-1",
        entity_id=skill.entity_id,
        entity_kind=skill.entity_kind,
        action=OpksProposalAction.REVISE,
        before=skill,
        after=skill.model_copy(update={"text": "進階試算表整理"}),
        base_authority_generation=0,
        created_at=NOW,
    )
    await seed(
        postgres_session_factory,
        document_id,
        work_model=work_model,
        current_jd=current_jd,
        proposal=proposal,
        current_opks=(output, indicator, skill),
        opks_proposals=(pending_opks_proposal,),
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
    assert loaded.state.current_opks.items == (
        skill.model_copy(update={"task_refs": (), "indicator_refs": ()}),
    )
    assert loaded.state.opks_proposals[0].status is OpksProposalStatus.STALE
    assert loaded.state.opks_proposals[0].stale_reason


async def test_accept_split_prunes_parent_opks_without_guessing_child_links(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    work_model, current_jd, proposal = split_proposal()
    output = opks_item(
        "output-parent",
        OpksEntityKind.OUTPUT,
        "營運資料與週報",
        task_refs=("task-parent",),
    )
    knowledge = opks_item(
        "knowledge-parent",
        OpksEntityKind.KNOWLEDGE,
        "營運資料定義",
        task_refs=("task-parent",),
    )
    await seed(
        postgres_session_factory,
        document_id,
        work_model=work_model,
        current_jd=current_jd,
        proposal=proposal,
        current_opks=(output, knowledge),
    )

    await decide_proposal(
        factory(postgres_session_factory),
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="decision-split",
        decision="accepted",
    )
    loaded = await load_document(factory(postgres_session_factory), document_id)

    assert loaded is not None
    assert [item.task_id for item in loaded.state.current_jd] == [
        "task-child-a",
        "task-child-b",
    ]
    assert loaded.state.work_model.task_by_id("task-parent").state is TaskState.RETIRED
    assert loaded.state.current_opks.items == (
        knowledge.model_copy(update={"task_refs": ()}),
    )


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
