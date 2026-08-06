"""Employee decisions for durable OPKS proposals."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.job_analysis.application import (
    IdempotencyConflict,
    OpksProposalNotDecidable,
    add_jd_task,
    create_document,
    delete_jd_task,
    decide_opks_proposal,
    edit_opks_item,
    load_document,
)
from app.job_analysis.domain import (
    JdTaskFields,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    OpksProposal,
    OpksProposalAction,
    OpksProposalStatus,
    SourceKind,
    SourceRef,
)


pytestmark = pytest.mark.asyncio
NOW = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


def factory(session_factory):
    return lambda: SqlAlchemyJobAnalysisUnitOfWork(session_factory)


def evidence(source_id: str = "employee-1") -> OpksEvidenceLink:
    return OpksEvidenceLink(
        source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id=source_id),
        quote="我每週彙整營運週報",
    )


def item(
    entity_id: str,
    text: str,
    *,
    task_id: str,
    kind: OpksEntityKind = OpksEntityKind.OUTPUT,
) -> OpksItem:
    return OpksItem(
        entity_id=entity_id,
        entity_kind=kind,
        text=text,
        display_order=0,
        task_refs=(task_id,),
        evidence_links=(evidence(),),
    )


def add_proposal(
    candidate: OpksItem,
    *,
    proposal_id: str = "opks-proposal-add",
) -> OpksProposal:
    return OpksProposal(
        proposal_id=proposal_id,
        operation_id="opks-operation-1",
        entity_id=candidate.entity_id,
        entity_kind=candidate.entity_kind,
        action=OpksProposalAction.ADD,
        after=candidate,
        base_authority_generation=0,
        created_at=NOW,
    )


def revise_proposal(
    before: OpksItem,
    after_text: str,
    *,
    proposal_id: str = "opks-proposal-revise",
) -> OpksProposal:
    return OpksProposal(
        proposal_id=proposal_id,
        operation_id="opks-operation-1",
        entity_id=before.entity_id,
        entity_kind=before.entity_kind,
        action=OpksProposalAction.REVISE,
        before=before,
        after=before.model_copy(update={"text": after_text}),
        base_authority_generation=0,
        created_at=NOW,
    )


async def seed(
    session_factory,
    document_id,
    *,
    task_id: str | None = "task-1",
    items: tuple[OpksItem, ...] = (),
    proposals: tuple[OpksProposal, ...] = (),
) -> None:
    uow_factory = factory(session_factory)
    await create_document(
        uow_factory,
        document_id=document_id,
        title="門市營運專員",
    )
    if task_id is not None:
        await add_jd_task(
            uow_factory,
            document_id=document_id,
            entry_id="seed-task",
            fields=JdTaskFields(statement="每週彙整營運週報"),
        )
    async with uow_factory() as uow:
        await uow.opks.replace(document_id, items)
        await uow.opks_proposals.replace(document_id, proposals)
        await uow.commit()


async def test_accept_adds_exact_candidate_without_forging_employee_evidence(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    candidate = item("output-1", "營運週報", task_id="direct-seed-task")
    proposal = add_proposal(candidate)
    await seed(
        postgres_session_factory,
        document_id,
        proposals=(proposal,),
    )

    decided = await decide_opks_proposal(
        factory(postgres_session_factory),
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="accept-opks",
        decision="accepted",
    )
    replay = await decide_opks_proposal(
        factory(postgres_session_factory),
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="accept-opks",
        decision="accepted",
    )
    loaded = await load_document(factory(postgres_session_factory), document_id)

    assert replay == decided
    assert decided.status is OpksProposalStatus.ACCEPTED
    assert loaded is not None
    assert loaded.state.current_opks.items == (candidate,)
    assert loaded.state.current_opks.items[0].evidence_links == candidate.evidence_links
    assert loaded.document.authority_generation == 2


async def test_edited_decision_adds_one_direct_edit_source_and_two_journal_entries(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    before = item("output-1", "營運週報", task_id="direct-seed-task")
    proposal = revise_proposal(before, "每週營運週報")
    await seed(
        postgres_session_factory,
        document_id,
        items=(before,),
        proposals=(proposal,),
    )
    uow_factory = factory(postgres_session_factory)

    decided = await decide_opks_proposal(
        uow_factory,
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="edit-opks",
        decision="edited",
        edited_text="員工確認的每週營運週報",
    )
    replay = await decide_opks_proposal(
        uow_factory,
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="edit-opks",
        decision="edited",
        edited_text="員工確認的每週營運週報",
    )
    loaded = await load_document(uow_factory, document_id)

    assert replay == decided
    assert decided.status is OpksProposalStatus.EDITED
    assert decided.edited_after is not None
    assert decided.edited_after.text == "員工確認的每週營運週報"
    assert loaded is not None
    current = loaded.state.current_opks.item_by_id(before.entity_id)
    assert current is not None
    assert current.text == "員工確認的每週營運週報"
    assert [link.source_ref for link in current.evidence_links] == [
        evidence().source_ref,
        SourceRef(kind=SourceKind.DIRECT_EDIT, id="edit-opks-direct-edit"),
    ]
    async with uow_factory() as uow:
        decision_entry = await uow.journal.get(document_id, "edit-opks")
        edit_entry = await uow.journal.get(document_id, "edit-opks-direct-edit")
    assert decision_entry.kind == "proposal_decision"
    assert edit_entry.kind == "direct_edit"

    with pytest.raises(IdempotencyConflict):
        await decide_opks_proposal(
            uow_factory,
            document_id=document_id,
            proposal_id=proposal.proposal_id,
            decision_id="edit-opks",
            decision="edited",
            edited_text="另一段文字",
        )


async def test_defer_reload_reject_and_terminal_state_are_explicit(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    candidate = item("output-1", "營運週報", task_id="direct-seed-task")
    proposal = add_proposal(candidate)
    await seed(
        postgres_session_factory,
        document_id,
        proposals=(proposal,),
    )
    uow_factory = factory(postgres_session_factory)

    deferred = await decide_opks_proposal(
        uow_factory,
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="defer-opks",
        decision="deferred",
    )
    reloaded = await load_document(uow_factory, document_id)
    assert deferred.status is OpksProposalStatus.DEFERRED
    assert reloaded is not None
    assert reloaded.state.opks_proposals[0].status is OpksProposalStatus.DEFERRED

    rejected = await decide_opks_proposal(
        uow_factory,
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id="reject-opks",
        decision="rejected",
        reason="這不是必要的工作產出",
    )
    assert rejected.status is OpksProposalStatus.REJECTED
    assert rejected.rejection_reason == "這不是必要的工作產出"
    with pytest.raises(OpksProposalNotDecidable):
        await decide_opks_proposal(
            uow_factory,
            document_id=document_id,
            proposal_id=proposal.proposal_id,
            decision_id="accept-after-reject",
            decision="accepted",
        )


@pytest.mark.parametrize("failure", ["missing-target", "missing-task-ref"])
async def test_invalid_authority_turns_the_proposal_stale_instead_of_applying_it(
    postgres_session_factory,
    cleanup_job_analysis_rows,
    failure,
):
    document_id = cleanup_job_analysis_rows
    if failure == "missing-target":
        before = item("output-1", "營運週報", task_id="direct-seed-task")
        proposal = revise_proposal(before, "每週營運週報")
        task_id = "task-1"
    else:
        proposal = add_proposal(item("output-1", "營運週報", task_id="missing"))
        task_id = None
    await seed(
        postgres_session_factory,
        document_id,
        task_id=task_id,
        proposals=(proposal,),
    )

    stale = await decide_opks_proposal(
        factory(postgres_session_factory),
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id=f"accept-{failure}",
        decision="accepted",
    )
    loaded = await load_document(factory(postgres_session_factory), document_id)
    replay = await decide_opks_proposal(
        factory(postgres_session_factory),
        document_id=document_id,
        proposal_id=proposal.proposal_id,
        decision_id=f"accept-{failure}",
        decision="accepted",
    )
    reloaded = await load_document(factory(postgres_session_factory), document_id)

    assert stale.status is OpksProposalStatus.STALE
    assert replay == stale
    assert stale.stale_reason
    assert loaded is not None
    assert reloaded is not None
    assert loaded.state.current_opks.items == ()
    assert (
        reloaded.document.authority_generation
        == loaded.document.authority_generation
    )


async def test_accepting_one_proposal_stales_a_competing_proposal_for_same_entity(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    first = add_proposal(
        item("output-1", "營運週報", task_id="direct-seed-task"),
        proposal_id="proposal-first",
    )
    competing = add_proposal(
        item("output-1", "每週營運週報", task_id="direct-seed-task"),
        proposal_id="proposal-competing",
    )
    await seed(
        postgres_session_factory,
        document_id,
        proposals=(first, competing),
    )

    await decide_opks_proposal(
        factory(postgres_session_factory),
        document_id=document_id,
        proposal_id=first.proposal_id,
        decision_id="accept-first",
        decision="accepted",
    )
    loaded = await load_document(factory(postgres_session_factory), document_id)

    assert loaded is not None
    by_id = {
        proposal.proposal_id: proposal
        for proposal in loaded.state.opks_proposals
    }
    assert by_id[first.proposal_id].status is OpksProposalStatus.ACCEPTED
    assert by_id[competing.proposal_id].status is OpksProposalStatus.STALE


async def test_historical_acceptance_does_not_stale_a_later_revision(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    current = item("output-1", "營運週報", task_id="direct-seed-task")
    historical = add_proposal(
        current,
        proposal_id="proposal-historical",
    ).model_copy(
        update={
            "status": OpksProposalStatus.ACCEPTED,
            "resolved_at": NOW,
        }
    )
    later = revise_proposal(
        current,
        "每週營運週報",
        proposal_id="proposal-later",
    ).model_copy(update={"created_at": NOW + timedelta(minutes=1)})
    await seed(
        postgres_session_factory,
        document_id,
        items=(current,),
        proposals=(historical, later),
    )

    decided = await decide_opks_proposal(
        factory(postgres_session_factory),
        document_id=document_id,
        proposal_id=later.proposal_id,
        decision_id="accept-later",
        decision="accepted",
    )

    assert decided.status is OpksProposalStatus.ACCEPTED


async def test_direct_edit_stales_only_the_related_active_proposal(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    before = item("output-1", "營運週報", task_id="direct-seed-task")
    related = revise_proposal(before, "每週營運週報")
    terminal = revise_proposal(
        before,
        "主管營運週報",
        proposal_id="proposal-terminal",
    ).model_copy(
        update={
            "status": OpksProposalStatus.REJECTED,
            "rejection_reason": "不要這個版本",
            "resolved_at": NOW,
        }
    )
    await seed(
        postgres_session_factory,
        document_id,
        items=(before,),
        proposals=(related, terminal),
    )

    await edit_opks_item(
        factory(postgres_session_factory),
        document_id=document_id,
        entry_id="manual-edit",
        entity_id=before.entity_id,
        entity_kind=before.entity_kind,
        text="員工手動改寫",
        task_refs=before.task_refs,
    )
    loaded = await load_document(factory(postgres_session_factory), document_id)

    assert loaded is not None
    by_id = {
        proposal.proposal_id: proposal
        for proposal in loaded.state.opks_proposals
    }
    assert by_id[related.proposal_id].status is OpksProposalStatus.STALE
    assert by_id[terminal.proposal_id].status is OpksProposalStatus.REJECTED


async def test_task_delete_stales_a_proposal_that_references_the_removed_task(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    before = item("output-1", "營運週報", task_id="direct-seed-task")
    proposal = revise_proposal(before, "每週營運週報")
    await seed(
        postgres_session_factory,
        document_id,
        items=(before,),
        proposals=(proposal,),
    )
    uow_factory = factory(postgres_session_factory)

    await delete_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="delete-task",
        task_id="direct-seed-task",
    )
    loaded = await load_document(uow_factory, document_id)

    assert loaded is not None
    assert loaded.state.current_opks.items == ()
    assert loaded.state.opks_proposals[0].status is OpksProposalStatus.STALE
    assert loaded.state.opks_proposals[0].stale_reason
