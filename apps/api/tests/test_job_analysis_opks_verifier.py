"""OPKS deterministic verifier 只裁決機械規則，不冒充語意 grader。"""

from __future__ import annotations

import pytest

from app.job_analysis.application import (
    OpksViolationCode,
    build_opks_context_packet,
    verify_opks_result,
)
from app.job_analysis.domain import (
    CurrentJdOpks,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    OpksProposalAction,
    SourceKind,
    SourceRef,
    SupportLink,
    Task,
)
from app.job_analysis.llm import (
    OpksDecision,
    OpksGenerationEntityKind,
    OpksResult,
    OpksResultItem,
)


def source(source_id: str = "turn-1") -> SourceRef:
    return SourceRef(kind=SourceKind.EMPLOYEE_TURN, id=source_id)


def employee_evidence(source_id: str = "turn-1") -> OpksEvidenceLink:
    return OpksEvidenceLink(
        source_ref=source(source_id),
        quote="我每週彙整營運週報",
    )


def selected_task() -> Task:
    return Task(
        task_id="task-selected",
        statement="彙整營運週報",
        action="彙整",
        object="營運週報",
        purpose_result="提供主管追蹤營運狀況",
        support_links=(
            SupportLink(
                source_ref=source(),
                quote="我每週彙整營運週報",
            ),
        ),
    )


def item(
    entity_id: str,
    kind: OpksEntityKind,
    text: str,
    *,
    task_refs: tuple[str, ...] = (),
    indicator_refs: tuple[str, ...] = (),
    evidence_links: tuple[OpksEvidenceLink, ...] | None = None,
) -> OpksItem:
    return OpksItem(
        entity_id=entity_id,
        entity_kind=kind,
        text=text,
        task_refs=task_refs,
        indicator_refs=indicator_refs,
        evidence_links=(employee_evidence("turn-old"),)
        if evidence_links is None
        else evidence_links,
    )


def packet(*items: OpksItem):
    return build_opks_context_packet(
        selected_task=selected_task(),
        current_opks=CurrentJdOpks(items=items),
    )


def result(*items: OpksResultItem) -> OpksResult:
    return OpksResult(items=items)


def model_item(
    kind: OpksGenerationEntityKind,
    decision: OpksDecision,
    *,
    target: int | None = None,
    text: str | None = None,
) -> OpksResultItem:
    return OpksResultItem(
        entity_kind=kind,
        decision=decision,
        target_ordinal=target,
        text=text,
    )


def test_add_new_builds_a_grounded_candidate_with_deterministic_identity():
    report = verify_opks_result(
        packet(),
        result(
            model_item(
                OpksGenerationEntityKind.OUTPUT,
                OpksDecision.ADD_NEW,
                text="營運週報",
            ),
            model_item(
                OpksGenerationEntityKind.KNOWLEDGE,
                OpksDecision.ADD_NEW,
                text="營運指標定義",
            ),
        ),
        operation_id="operation-1",
    )

    assert report.is_valid
    assert [change.action for change in report.changes] == [
        OpksProposalAction.ADD,
        OpksProposalAction.ADD,
    ]
    output, knowledge = [change.after for change in report.changes]
    assert output is not None
    assert output.entity_id == "operation-1-o0"
    assert output.task_refs == ("task-selected",)
    assert output.evidence_links == (employee_evidence(),)
    assert knowledge is not None
    assert knowledge.entity_id == "operation-1-k1"
    assert knowledge.task_refs == ("task-selected",)
    assert knowledge.indicator_refs == ()


def test_reuse_existing_knowledge_adds_the_selected_task_and_employee_evidence():
    existing = item(
        "knowledge-1",
        OpksEntityKind.KNOWLEDGE,
        "營運指標定義",
        task_refs=("task-other",),
    )

    report = verify_opks_result(
        packet(existing),
        result(
            model_item(
                OpksGenerationEntityKind.KNOWLEDGE,
                OpksDecision.REUSE_EXISTING,
                target=1,
            )
        ),
        operation_id="operation-1",
    )

    assert report.is_valid
    assert len(report.changes) == 1
    change = report.changes[0]
    assert change.action is OpksProposalAction.REVISE
    assert change.before == existing
    assert change.after is not None
    assert change.after.text == existing.text
    assert change.after.task_refs == ("task-other", "task-selected")
    assert [link.source_ref.id for link in change.after.evidence_links] == [
        "turn-old",
        "turn-1",
    ]


def test_revise_existing_updates_text_but_keeps_identity():
    existing = item(
        "indicator-1",
        OpksEntityKind.INDICATOR,
        "每週完成",
        task_refs=("task-selected",),
    )
    report = verify_opks_result(
        packet(existing),
        result(
            model_item(
                OpksGenerationEntityKind.INDICATOR,
                OpksDecision.REVISE_EXISTING,
                target=1,
                text="依約定時程完成營運週報",
            )
        ),
        operation_id="operation-1",
    )

    assert report.is_valid
    assert report.changes[0].entity_id == "indicator-1"
    assert report.changes[0].after.text == "依約定時程完成營運週報"


def test_remove_output_removes_it_but_remove_knowledge_only_unlinks_selected_task():
    selected_indicator = item(
        "indicator-selected",
        OpksEntityKind.INDICATOR,
        "依約定時程完成",
        task_refs=("task-selected",),
    )
    other_indicator = item(
        "indicator-other",
        OpksEntityKind.INDICATOR,
        "排班錯誤為零",
        task_refs=("task-other",),
    )
    output = item(
        "output-1",
        OpksEntityKind.OUTPUT,
        "營運週報",
        task_refs=("task-selected",),
    )
    knowledge = item(
        "knowledge-1",
        OpksEntityKind.KNOWLEDGE,
        "營運指標定義",
        task_refs=("task-selected", "task-other"),
        indicator_refs=("indicator-selected", "indicator-other"),
    )
    report = verify_opks_result(
        packet(selected_indicator, other_indicator, output, knowledge),
        result(
            model_item(
                OpksGenerationEntityKind.OUTPUT,
                OpksDecision.REMOVE_EXISTING,
                target=1,
            ),
            model_item(
                OpksGenerationEntityKind.KNOWLEDGE,
                OpksDecision.REMOVE_EXISTING,
                target=1,
            ),
        ),
        operation_id="operation-1",
    )

    assert report.is_valid
    remove_output, unlink_knowledge = report.changes
    assert remove_output.action is OpksProposalAction.REMOVE
    assert remove_output.after is None
    assert unlink_knowledge.action is OpksProposalAction.REVISE
    assert unlink_knowledge.after is not None
    assert unlink_knowledge.after.task_refs == ("task-other",)
    assert unlink_knowledge.after.indicator_refs == ("indicator-other",)


def test_remove_knowledge_keeps_the_document_level_item_even_when_it_becomes_unlinked():
    existing = item(
        "knowledge-1",
        OpksEntityKind.KNOWLEDGE,
        "營運指標定義",
        task_refs=("task-selected",),
    )
    report = verify_opks_result(
        packet(existing),
        result(
            model_item(
                OpksGenerationEntityKind.KNOWLEDGE,
                OpksDecision.REMOVE_EXISTING,
                target=1,
            )
        ),
        operation_id="operation-1",
    )

    assert report.is_valid
    assert report.changes[0].action is OpksProposalAction.REVISE
    assert report.changes[0].after is not None
    assert report.changes[0].after.task_linkage == "unlinked"


def test_uncertain_creates_no_proposal_change():
    report = verify_opks_result(
        packet(),
        result(
            model_item(
                OpksGenerationEntityKind.SKILL,
                OpksDecision.UNCERTAIN,
            )
        ),
        operation_id="operation-1",
    )

    assert report.is_valid
    assert report.changes == ()


@pytest.mark.parametrize(
    "bad_item",
    [
        model_item(
            OpksGenerationEntityKind.OUTPUT,
            OpksDecision.ADD_NEW,
            target=1,
            text="產出",
        ),
        model_item(OpksGenerationEntityKind.OUTPUT, OpksDecision.ADD_NEW),
        model_item(
            OpksGenerationEntityKind.OUTPUT,
            OpksDecision.REUSE_EXISTING,
            target=1,
        ),
        model_item(
            OpksGenerationEntityKind.KNOWLEDGE,
            OpksDecision.REUSE_EXISTING,
            target=1,
            text="不該填",
        ),
        model_item(
            OpksGenerationEntityKind.OUTPUT,
            OpksDecision.REVISE_EXISTING,
            target=1,
        ),
        model_item(
            OpksGenerationEntityKind.OUTPUT,
            OpksDecision.REMOVE_EXISTING,
            target=1,
            text="不該填",
        ),
        model_item(
            OpksGenerationEntityKind.SKILL,
            OpksDecision.UNCERTAIN,
            target=1,
        ),
    ],
)
def test_decision_payload_mappings_are_deterministic(bad_item):
    existing_output = item(
        "output-1",
        OpksEntityKind.OUTPUT,
        "營運週報",
        task_refs=("task-selected",),
    )
    existing_knowledge = item(
        "knowledge-1",
        OpksEntityKind.KNOWLEDGE,
        "營運指標定義",
        task_refs=("task-selected",),
    )
    report = verify_opks_result(
        packet(existing_output, existing_knowledge),
        result(bad_item),
        operation_id="operation-1",
    )

    assert not report.is_valid
    assert report.changes == ()
    assert OpksViolationCode.DECISION_PAYLOAD_INVALID in {
        violation.code for violation in report.violations
    }


def test_unknown_duplicate_and_unrelated_targets_are_rejected_as_a_batch():
    unrelated_output = item(
        "output-other",
        OpksEntityKind.OUTPUT,
        "排班表",
        task_refs=("task-other",),
    )
    unrelated_skill = item(
        "skill-other",
        OpksEntityKind.SKILL,
        "排班",
        task_refs=("task-other",),
    )
    report = verify_opks_result(
        packet(unrelated_output, unrelated_skill),
        result(
            model_item(
                OpksGenerationEntityKind.OUTPUT,
                OpksDecision.REVISE_EXISTING,
                target=9,
                text="不存在",
            ),
            model_item(
                OpksGenerationEntityKind.SKILL,
                OpksDecision.REMOVE_EXISTING,
                target=1,
            ),
            model_item(
                OpksGenerationEntityKind.SKILL,
                OpksDecision.REVISE_EXISTING,
                target=1,
                text="排班規劃",
            ),
        ),
        operation_id="operation-1",
    )

    assert not report.is_valid
    assert report.changes == ()
    assert {violation.code for violation in report.violations} == {
        OpksViolationCode.TARGET_ORDINAL_UNKNOWN,
        OpksViolationCode.TARGET_NOT_RELATED_TO_SELECTED_TASK,
        OpksViolationCode.DUPLICATE_TARGET,
    }


def test_exact_duplicate_add_candidates_are_rejected_as_a_batch():
    report = verify_opks_result(
        packet(),
        result(
            model_item(
                OpksGenerationEntityKind.KNOWLEDGE,
                OpksDecision.ADD_NEW,
                text="營運指標定義",
            ),
            model_item(
                OpksGenerationEntityKind.KNOWLEDGE,
                OpksDecision.ADD_NEW,
                text="營運指標定義",
            ),
        ),
        operation_id="operation-1",
    )

    assert not report.is_valid
    assert report.changes == ()
    assert [violation.code for violation in report.violations] == [
        OpksViolationCode.DUPLICATE_ADD_CANDIDATE
    ]


def test_semantic_quality_is_not_falsely_encoded_as_a_deterministic_rule():
    report = verify_opks_result(
        packet(),
        result(
            model_item(
                OpksGenerationEntityKind.SKILL,
                OpksDecision.ADD_NEW,
                text="精通資料分析並於 3 分鐘內完成",
            )
        ),
        operation_id="operation-1",
    )

    assert report.is_valid
