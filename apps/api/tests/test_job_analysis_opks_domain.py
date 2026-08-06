"""ADR 0048–0051 的 OPKS domain contract 行為測試。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.job_analysis.domain import (
    OPKS_ALLOWED_STATUS_TRANSITIONS,
    OPKS_TERMINAL_STATUSES,
    CurrentJdOpks,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    OpksProposal,
    OpksProposalAction,
    OpksProposalStatus,
    SourceKind,
    SourceRef,
    is_allowed_opks_transition,
)


NOW = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)


def employee_evidence(turn_id: str = "turn-1") -> OpksEvidenceLink:
    return OpksEvidenceLink(
        source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id=turn_id),
        quote="我每週彙整營運週報",
    )


def direct_edit_evidence(entry_id: str = "edit-1") -> OpksEvidenceLink:
    return OpksEvidenceLink(
        source_ref=SourceRef(kind=SourceKind.DIRECT_EDIT, id=entry_id)
    )


def opks_item(
    *,
    entity_id: str = "knowledge-1",
    entity_kind: OpksEntityKind = OpksEntityKind.KNOWLEDGE,
    text: str = "營運資料定義",
    task_refs: tuple[str, ...] = (),
    indicator_refs: tuple[str, ...] = (),
    evidence_links: tuple[OpksEvidenceLink, ...] | None = None,
) -> OpksItem:
    return OpksItem(
        entity_id=entity_id,
        entity_kind=entity_kind,
        text=text,
        display_order=0,
        task_refs=task_refs,
        indicator_refs=indicator_refs,
        evidence_links=(employee_evidence(),) if evidence_links is None else evidence_links,
    )


def pending_proposal(
    *,
    action: OpksProposalAction = OpksProposalAction.ADD,
    before: OpksItem | None = None,
    after: OpksItem | None = None,
    **overrides,
) -> OpksProposal:
    if action is OpksProposalAction.ADD and after is None:
        after = opks_item()
    base = {
        "proposal_id": "proposal-1",
        "operation_id": "operation-1",
        "entity_id": "knowledge-1",
        "entity_kind": OpksEntityKind.KNOWLEDGE,
        "action": action,
        "before": before,
        "after": after,
        "base_authority_generation": 3,
        "created_at": NOW,
    }
    base.update(overrides)
    return OpksProposal(**base)


def test_opks_enum_values_match_the_accepted_contracts():
    assert {kind.value for kind in OpksEntityKind} == {
        "output",
        "indicator",
        "knowledge",
        "skill",
        "attitude",
    }
    assert {action.value for action in OpksProposalAction} == {
        "add",
        "revise",
        "remove",
    }
    assert {status.value for status in OpksProposalStatus} == {
        "pending",
        "deferred",
        "accepted",
        "edited",
        "rejected",
        "stale",
    }


def test_opks_item_requires_employee_evidence_and_rejects_decision_as_evidence():
    with pytest.raises(ValidationError, match="at least one evidence"):
        opks_item(evidence_links=())

    with pytest.raises(ValidationError, match="employee_turn or direct_edit"):
        OpksEvidenceLink(
            source_ref=SourceRef(
                kind=SourceKind.PROPOSAL_DECISION,
                id="decision-1",
            )
        )

    assert opks_item(evidence_links=(direct_edit_evidence(),)).evidence_origins == {
        "employee"
    }


@pytest.mark.parametrize("kind", [OpksEntityKind.OUTPUT, OpksEntityKind.INDICATOR])
def test_output_and_indicator_belong_to_exactly_one_task(kind):
    with pytest.raises(ValidationError, match="exactly one task"):
        opks_item(entity_kind=kind)
    with pytest.raises(ValidationError, match="exactly one task"):
        opks_item(entity_kind=kind, task_refs=("task-1", "task-2"))
    with pytest.raises(ValidationError, match="must not reference indicators"):
        opks_item(
            entity_kind=kind,
            task_refs=("task-1",),
            indicator_refs=("indicator-1",),
        )

    assert opks_item(entity_kind=kind, task_refs=("task-1",)).task_linkage == (
        "linked"
    )


def test_knowledge_skill_and_attitude_reference_rules_are_distinct():
    assert opks_item().task_linkage == "unlinked"
    assert opks_item(
        entity_kind=OpksEntityKind.SKILL,
        task_refs=("task-1", "task-2"),
        indicator_refs=("indicator-1",),
    )
    assert opks_item(
        entity_kind=OpksEntityKind.ATTITUDE,
        entity_id="attitude-1",
        text="審慎",
    )
    with pytest.raises(ValidationError, match="attitude must not carry references"):
        opks_item(
            entity_kind=OpksEntityKind.ATTITUDE,
            entity_id="attitude-1",
            task_refs=("task-1",),
        )


@pytest.mark.parametrize(
    ("field_name", "values"),
    [
        ("task_refs", ("task-1", "task-1")),
        ("indicator_refs", ("indicator-1", "indicator-1")),
    ],
)
def test_opks_item_rejects_duplicate_references_instead_of_silently_deduplicating(
    field_name, values
):
    with pytest.raises(ValidationError, match=f"duplicate {field_name}"):
        opks_item(**{field_name: values})


def test_current_jd_opks_validates_item_and_reference_identities():
    indicator = opks_item(
        entity_id="indicator-1",
        entity_kind=OpksEntityKind.INDICATOR,
        text="週報數字可回溯來源",
        task_refs=("task-1",),
    )
    knowledge = opks_item(indicator_refs=("indicator-1",))
    current = CurrentJdOpks(items=(indicator, knowledge))

    assert current.item_by_id("knowledge-1") == knowledge
    current.validate_against_tasks(frozenset({"task-1"}))

    with pytest.raises(ValidationError, match="duplicate OPKS entity id"):
        CurrentJdOpks(items=(knowledge, knowledge))
    with pytest.raises(ValidationError, match="unknown indicator"):
        CurrentJdOpks(items=(opks_item(indicator_refs=("indicator-missing",)),))
    with pytest.raises(ValidationError, match="must identify an indicator"):
        CurrentJdOpks(
            items=(
                opks_item(
                    entity_id="output-1",
                    entity_kind=OpksEntityKind.OUTPUT,
                    task_refs=("task-1",),
                ),
                opks_item(indicator_refs=("output-1",)),
            )
        )
    with pytest.raises(ValueError, match="unknown Current JD task"):
        current.validate_against_tasks(frozenset({"task-2"}))


def test_derived_axes_do_not_create_serialized_second_truths():
    item = opks_item(task_refs=("task-1",))

    assert item.task_linkage == "linked"
    assert item.evidence_origins == {"employee"}
    assert "task_linkage" not in item.model_dump()
    assert "evidence_origins" not in item.model_dump()


@pytest.mark.parametrize(
    ("action", "before", "after"),
    [
        (OpksProposalAction.ADD, None, opks_item()),
        (
            OpksProposalAction.REVISE,
            opks_item(text="舊文字"),
            opks_item(text="新文字"),
        ),
        (OpksProposalAction.REMOVE, opks_item(), None),
    ],
)
def test_opks_proposal_snapshots_match_the_action(action, before, after):
    assert pending_proposal(action=action, before=before, after=after).action is action


@pytest.mark.parametrize(
    ("action", "before", "after"),
    [
        (OpksProposalAction.ADD, opks_item(), opks_item()),
        (OpksProposalAction.REVISE, None, opks_item()),
        (OpksProposalAction.REMOVE, opks_item(), opks_item()),
    ],
)
def test_opks_proposal_rejects_snapshots_that_do_not_match_the_action(
    action, before, after
):
    with pytest.raises(ValidationError, match="snapshot"):
        pending_proposal(action=action, before=before, after=after)


def test_opks_proposal_snapshots_keep_the_stable_identity_and_kind():
    with pytest.raises(ValidationError, match="entity identity"):
        pending_proposal(after=opks_item(entity_id="knowledge-2"))
    with pytest.raises(ValidationError, match="entity kind"):
        pending_proposal(
            entity_kind=OpksEntityKind.SKILL,
            after=opks_item(entity_kind=OpksEntityKind.KNOWLEDGE),
        )


def test_edited_proposal_changes_only_text_and_requires_a_real_edit():
    original = opks_item(text="營運資料定義")
    edited = original.model_copy(update={"text": "營運指標與欄位定義"})
    proposal = pending_proposal(
        status=OpksProposalStatus.EDITED,
        after=original,
        edited_after=edited,
        resolved_at=NOW,
    )
    assert proposal.edited_after == edited

    with pytest.raises(ValidationError, match="must differ"):
        pending_proposal(
            status=OpksProposalStatus.EDITED,
            after=original,
            edited_after=original,
            resolved_at=NOW,
        )
    with pytest.raises(ValidationError, match="only change text"):
        pending_proposal(
            status=OpksProposalStatus.EDITED,
            after=original,
            edited_after=original.model_copy(
                update={"text": "營運資料規格", "task_refs": ("task-2",)}
            ),
            resolved_at=NOW,
        )


def test_status_payloads_and_resolution_time_are_not_ambiguous():
    with pytest.raises(ValidationError, match="requires edited_after"):
        pending_proposal(status=OpksProposalStatus.EDITED, resolved_at=NOW)
    with pytest.raises(ValidationError, match="rejected status only"):
        pending_proposal(rejection_reason="不是必要知識")
    with pytest.raises(ValidationError, match="employee-visible reason"):
        pending_proposal(status=OpksProposalStatus.STALE, resolved_at=NOW)
    with pytest.raises(ValidationError, match="active proposal must not be resolved"):
        pending_proposal(resolved_at=NOW)
    with pytest.raises(ValidationError, match="terminal proposal requires resolved_at"):
        pending_proposal(status=OpksProposalStatus.ACCEPTED)

    assert pending_proposal(
        status=OpksProposalStatus.REJECTED,
        rejection_reason="不是必要知識",
        resolved_at=NOW,
    )
    assert pending_proposal(
        status=OpksProposalStatus.STALE,
        stale_reason="Current JD 已變更",
        resolved_at=NOW,
    )


def test_opks_status_machine_has_deferred_as_the_only_nonterminal_decision():
    expected_terminal = {
        OpksProposalStatus.ACCEPTED,
        OpksProposalStatus.EDITED,
        OpksProposalStatus.REJECTED,
        OpksProposalStatus.STALE,
    }
    assert OPKS_ALLOWED_STATUS_TRANSITIONS[OpksProposalStatus.PENDING] == (
        expected_terminal | {OpksProposalStatus.DEFERRED}
    )
    assert OPKS_ALLOWED_STATUS_TRANSITIONS[OpksProposalStatus.DEFERRED] == (
        expected_terminal
    )
    assert OPKS_TERMINAL_STATUSES == expected_terminal
    assert is_allowed_opks_transition(
        OpksProposalStatus.PENDING, OpksProposalStatus.DEFERRED
    )
    assert not is_allowed_opks_transition(
        OpksProposalStatus.DEFERRED, OpksProposalStatus.PENDING
    )
    assert "unknown" not in {status.value for status in OpksProposalStatus}


@pytest.mark.parametrize("terminal", sorted(OPKS_TERMINAL_STATUSES))
def test_terminal_opks_proposals_have_no_outgoing_transitions(terminal):
    assert OPKS_ALLOWED_STATUS_TRANSITIONS[terminal] == frozenset()
