"""V3-5 E5:deterministic graders、candidate edges、matching、metrics、review(§18.4)。

用合成 output 建立 TP/FP/FN、optional、forbidden、空分母、one-to-one tie、
narrower/broader/different/unknown、dropped-by-verifier、qualifier 逐欄錯誤等
情境;不依賴 live provider,也不放進 quality denominator 的規則在此測。
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from app.interview_vnext.domain.evidence import (
    EvidenceKind,
    EvidenceStatus,
    EvidenceSubject,
    FrequencyUnit,
    Importance,
    Ownership,
    Polarity,
    TimeScope,
    Typicality,
)
from app.interview_vnext.llm.turn_interpret import (
    EpisodeSignal,
    EvidenceQualifiersProposal,
    FrequencyQualifierProposal,
    ObservationProposal,
    TurnInterpretOutput,
    UserSignal,
)
from evals.interview_vnext.contracts import (
    ExpectedCommit,
    GraderStatus,
    ReviewDecisionLabel,
    TurnEvalReviewDecision,
)
from evals.interview_vnext.fixture_builder import run_pure_reference_gate
from evals.interview_vnext.identities import prior_evidence_uuid, trial_scoped_ids
from evals.interview_vnext.loader import load_suite
from evals.interview_vnext.review import (
    ReviewImportError,
    build_review_items,
    edge_decision_map,
    import_review_decisions,
    missing_decisions,
    order_review_queue,
    reason_contains_provider_identity,
)
from evals.interview_vnext.contracts import MetricResult
from evals.interview_vnext.turn_graders import (
    GradingContext,
    build_candidate_edges,
    compute_trial_metrics,
    grade_correction_lineage,
    grade_no_op,
    grade_quote_span,
    grade_reference_leakage,
    grade_source_subject,
    grade_state_transition,
    grade_unsupported_quantification,
    match_edges,
    qualifier_field_scores,
    run_deterministic_graders,
    split_gap_within_limit,
)

from pathlib import Path

CASES_ROOT = Path(__file__).resolve().parents[1] / "evals/interview_vnext/cases"
BASE_TIME = datetime(2026, 7, 18, 8, 0, tzinfo=UTC)
SHA = "sha256:" + "0" * 64


@pytest.fixture(scope="module")
def suite():
    return load_suite(CASES_ROOT, suite_version="turn-interpret-pilot.v1")


def case_pair(suite, case_id: str):
    index = [c.case.case_id for c in suite.runtime_inputs].index(case_id)
    return suite.runtime_inputs[index], suite.evaluation_contracts[index]


def qualifiers(
    *, time_scope="current", typicality="typical", polarity="affirmed",
    unit="unknown", value=None, verbatim=None, importance="not_stated",
    ownership="owner",
) -> EvidenceQualifiersProposal:
    return EvidenceQualifiersProposal(
        time_scope=TimeScope(time_scope),
        typicality=Typicality(typicality),
        polarity=Polarity(polarity),
        frequency=FrequencyQualifierProposal(
            value=value, unit=FrequencyUnit(unit), verbatim=verbatim
        ),
        importance=Importance(importance),
        ownership=Ownership(ownership),
    )


def proposal(
    key, *, kind="action", claim, quote, occurrence=1, subject="employee",
    quals=None, targets=(), unknown=False,
) -> ObservationProposal:
    return ObservationProposal(
        proposal_key=key,
        subject=EvidenceSubject(subject),
        kind=EvidenceKind(kind),
        claim=claim,
        quote=quote,
        quote_occurrence=occurrence,
        qualifiers=quals or qualifiers(),
        correction_target_evidence_ids=tuple(targets),
        correction_target_unknown=unknown,
    )


def output(*observations, user_signal="answer", episode_signal="continue", insufficiencies=()):
    return TurnInterpretOutput(
        schema_version="turn_interpret_output.v1",
        observations=tuple(observations),
        user_signal=UserSignal(user_signal),
        episode_signal=EpisodeSignal(episode_signal),
        emergent_topics=(),
        insufficiencies=tuple(insufficiencies),
    )


def make_context(
    suite, case_id, *, output_value, committed_kind="evidence",
    state_before="sha256:" + "a" * 64, state_after="sha256:" + "b" * 64,
    evidence_status=None, trial_id=None,
):
    inputs, evaluation = case_pair(suite, case_id)
    return GradingContext(
        inputs=inputs,
        gold=evaluation.gold,
        trial_id=trial_id or uuid5(NAMESPACE_URL, f"grader-test:{case_id}"),
        case_id=case_id,
        output=output_value,
        report=None,
        committed_kind=committed_kind,
        state_before_hash=state_before,
        state_after_hash=state_after,
        evidence_status=evidence_status or {},
    )


# ── deterministic graders ────────────────────────────────────────────────────


def test_quote_span_flags_unresolvable_quote(suite):
    ctx = make_context(
        suite,
        "TI-01-single-action",
        output_value=output(
            proposal("obs", claim="x", quote="不存在的逐字引文")
        ),
    )
    result = grade_quote_span(ctx)
    assert result.status == GraderStatus.FAIL
    assert "obs" in result.subject_ids


def test_source_subject_rejects_non_target_quote(suite):
    inputs, _ = case_pair(suite, "TI-09-known-correction")
    prior_turn_text = inputs.transcript[1].text  # employee-prior 的原文
    ctx = make_context(
        suite,
        "TI-09-known-correction",
        output_value=output(
            proposal("obs", kind="correction", claim="x", quote=prior_turn_text, targets=())
        ),
    )
    result = grade_source_subject(ctx)
    # 引文只在 prior turn 出現、不在 target turn → critical
    assert result.status == GraderStatus.FAIL
    assert result.severity.value == "critical"


def test_foreign_id_grader_rejects_unknown_target(suite):
    ctx = make_context(
        suite,
        "TI-01-single-action",
        output_value=output(
            proposal(
                "obs", kind="correction", claim="x",
                quote="核對前一日的出貨訂單", targets=(uuid4(),),
            )
        ),
    )
    results = {g.grader_name: g for g in run_deterministic_graders(ctx)}
    assert results["foreign_id"].status == GraderStatus.FAIL
    assert results["foreign_id"].severity.value == "critical"


def test_state_transition_detects_hash_mismatch(suite):
    ctx = make_context(
        suite,
        "TI-01-single-action",
        output_value=output(proposal("obs", claim="x", quote="核對前一日的出貨訂單")),
        state_before=SHA,
        state_after=SHA,  # gold 期望改變,但這裡沒變
    )
    result = grade_state_transition(ctx)
    assert result.status == GraderStatus.FAIL
    assert result.severity.value == "critical"


def test_no_op_grader_fails_if_evidence_committed(suite):
    ctx = make_context(
        suite,
        "TI-11-zero-evidence",
        output_value=output(),
        committed_kind="evidence",
        state_before=SHA,
        state_after="sha256:" + "c" * 64,
    )
    result = grade_no_op(ctx)
    assert result.status == GraderStatus.FAIL
    assert result.severity.value == "critical"


def test_no_op_grader_passes_typed_noop(suite):
    ctx = make_context(
        suite,
        "TI-11-zero-evidence",
        output_value=output(insufficiencies=()),
        committed_kind="noop",
        state_before=SHA,
        state_after=SHA,
    )
    assert grade_no_op(ctx).status == GraderStatus.PASS


def test_unsupported_quantification_flags_invented_number(suite):
    ctx = make_context(
        suite,
        "TI-01-single-action",
        output_value=output(
            proposal(
                "obs", claim="每天核對 5 批出貨訂單",
                quote="核對前一日的出貨訂單",
            )
        ),
    )
    result = grade_unsupported_quantification(ctx)
    assert result.status == GraderStatus.FAIL
    assert result.severity.value == "critical"


def test_reference_leakage_flags_taxonomy_marker(suite):
    ctx = make_context(
        suite,
        "TI-01-single-action",
        output_value=output(
            proposal(
                "obs", claim="依據職業分類核對訂單",
                quote="核對前一日的出貨訂單",
            )
        ),
    )
    assert grade_reference_leakage(ctx).status == GraderStatus.FAIL


def test_correction_lineage_flags_guessed_unknown_target(suite):
    ctx = make_context(
        suite,
        "TI-10-unknown-correction-target",
        output_value=output(
            proposal(
                "obs", kind="correction", claim="每季一次",
                quote="應該是每季一次", targets=(),
            )
        ),
    )
    # gold 要求 unknown,但這裡沒 target 也沒標 unknown → 由 lineage 判 pass?
    # 反例:提供 target 才是 critical
    trial_id = ctx.trial_id
    with_target = make_context(
        suite,
        "TI-10-unknown-correction-target",
        output_value=output(
            proposal(
                "obs", kind="correction", claim="每季一次",
                quote="應該是每季一次",
                targets=(prior_evidence_uuid(trial_id, "prior-inventory-report-frequency"),),
            )
        ),
        trial_id=trial_id,
    )
    result = grade_correction_lineage(with_target)
    assert result.status == GraderStatus.FAIL
    assert result.severity.value == "critical"


# ── candidate edges 與 matching ──────────────────────────────────────────────


def test_reference_output_edges_match_all_required(suite):
    for inputs, evaluation in zip(
        suite.runtime_inputs, suite.evaluation_contracts, strict=True
    ):
        if evaluation.gold.expected_commit != ExpectedCommit.EVIDENCE:
            continue
        trial_id = uuid5(NAMESPACE_URL, f"edge-test:{inputs.case.case_id}")
        result = run_pure_reference_gate(
            inputs, evaluation, trial_id=trial_id, base_time=BASE_TIME
        )
        edges = build_candidate_edges(
            inputs, evaluation.gold, result.output, trial_id=trial_id
        )
        decisions = {
            edge.edge_key: ReviewDecisionLabel.EQUIVALENT for edge in edges
        }
        metrics = compute_trial_metrics(
            gold=evaluation.gold,
            output=result.output,
            edges=edges,
            decisions=decisions,
            accepted_proposal_keys=frozenset(
                p.proposal_key for p in result.output.observations
            ),
        )
        assert metrics.recall.value == Decimal("1.000000"), inputs.case.case_id
        assert metrics.raw_precision.value == Decimal("1.000000"), inputs.case.case_id
        assert metrics.qualifier_exactness.value == Decimal("1.000000"), (
            inputs.case.case_id
        )


def test_broader_unsupported_is_false_positive(suite):
    inputs, evaluation = case_pair(suite, "TI-03-tools-not-skills")
    trial_id = uuid5(NAMESPACE_URL, "broader")
    # 一筆合法 SAP tool + 一筆技能強化(broader)
    out = output(
        proposal("obs-sap", kind="tool", claim="使用 SAP", quote="SAP"),
        proposal("obs-skill", kind="tool", claim="熟練 Excel 分析能力", quote="Excel"),
    )
    edges = build_candidate_edges(inputs, evaluation.gold, out, trial_id=trial_id)
    decisions = {}
    for edge in edges:
        if edge.proposal_key == "obs-skill":
            decisions[edge.edge_key] = ReviewDecisionLabel.BROADER_UNSUPPORTED
        else:
            decisions[edge.edge_key] = ReviewDecisionLabel.EQUIVALENT
    metrics = compute_trial_metrics(
        gold=evaluation.gold,
        output=out,
        edges=edges,
        decisions=decisions,
        accepted_proposal_keys=frozenset({"obs-sap", "obs-skill"}),
    )
    # SAP matched;Excel-skill broader → false positive,precision < 1
    assert metrics.raw_precision.value == Decimal("0.500000")
    assert "obs-skill" in metrics.false_positive_keys
    # Excel required gold 沒被滿足 → recall < 1
    assert metrics.recall.value == Decimal("0.500000")


def test_narrower_but_valid_matches_recall(suite):
    inputs, evaluation = case_pair(suite, "TI-01-single-action")
    trial_id = uuid5(NAMESPACE_URL, "narrower")
    out = output(
        proposal(
            "obs", claim="核對出貨訂單", quote="核對前一日的出貨訂單",
            quals=qualifiers(unit="per_day", verbatim="每天"),
        )
    )
    edges = build_candidate_edges(inputs, evaluation.gold, out, trial_id=trial_id)
    decisions = {edge.edge_key: ReviewDecisionLabel.NARROWER_BUT_VALID for edge in edges}
    metrics = compute_trial_metrics(
        gold=evaluation.gold, output=out, edges=edges, decisions=decisions,
        accepted_proposal_keys=frozenset({"obs"}),
    )
    assert metrics.recall.value == Decimal("1.000000")


def test_dropped_by_verifier_stays_in_raw_precision(suite):
    inputs, evaluation = case_pair(suite, "TI-01-single-action")
    trial_id = uuid5(NAMESPACE_URL, "dropped")
    out = output(
        proposal("obs-good", claim="核對出貨訂單", quote="核對前一日的出貨訂單"),
        proposal("obs-bad", claim="憑空 KPI 100 件", quote="核對前一日的出貨訂單"),
    )
    edges = build_candidate_edges(inputs, evaluation.gold, out, trial_id=trial_id)
    decisions = {}
    for edge in edges:
        if edge.proposal_key == "obs-bad":
            decisions[edge.edge_key] = ReviewDecisionLabel.BROADER_UNSUPPORTED
        else:
            decisions[edge.edge_key] = ReviewDecisionLabel.EQUIVALENT
    decisions[("__unmatched__", "obs-bad")] = ReviewDecisionLabel.BROADER_UNSUPPORTED
    # verifier 只接受 obs-good;obs-bad 被 drop
    metrics = compute_trial_metrics(
        gold=evaluation.gold, output=out, edges=edges, decisions=decisions,
        accepted_proposal_keys=frozenset({"obs-good"}),
    )
    # raw precision:2 個 output,1 個 match → 0.5(bad 仍在分母)
    assert metrics.raw_precision.value == Decimal("0.500000")
    # committed precision:只有 obs-good committed 且 matched → 1.0
    assert metrics.committed_precision.value == Decimal("1.000000")
    assert "obs-bad" in metrics.prevented_by_verifier_keys


def test_matching_is_one_to_one(suite):
    inputs, evaluation = case_pair(suite, "TI-03-tools-not-skills")
    trial_id = uuid5(NAMESPACE_URL, "one-to-one")
    # 兩筆 output 都用「用 SAP 和 Excel」全句 quote,能同時 cover SAP 與 Excel gold
    out = output(
        proposal("obs-a", kind="tool", claim="使用 SAP", quote="用 SAP 和 Excel"),
        proposal("obs-b", kind="tool", claim="使用 Excel", quote="用 SAP 和 Excel"),
    )
    edges = build_candidate_edges(inputs, evaluation.gold, out, trial_id=trial_id)
    assert len(edges) == 4  # 每個 output × 每個 gold
    decisions = {edge.edge_key: ReviewDecisionLabel.EQUIVALENT for edge in edges}
    matching = match_edges(edges, decisions, gold=evaluation.gold, output=out)
    assert len(matching.pairs) == 2  # 一對一:兩 gold、兩 output 各配一次
    # 兩種對稱 matching 的分數完全相同(都 equivalent、都 match),不算影響分數的 tie
    assert matching.ambiguous is False


def test_matching_flags_score_affecting_tie(suite):
    inputs, evaluation = case_pair(suite, "TI-03-tools-not-skills")
    trial_id = uuid5(NAMESPACE_URL, "ambiguous")
    # 兩筆 output 都只 cover SAP gold;哪一個被選會改變「哪個 output 是 false
    # positive」與其 label,因此是影響分數/報告的 tie → needs_review。
    out = output(
        proposal("obs-a", kind="tool", claim="使用 SAP", quote="SAP"),
        proposal("obs-b", kind="tool", claim="也用 SAP", quote="SAP"),
    )
    edges = build_candidate_edges(inputs, evaluation.gold, out, trial_id=trial_id)
    sap_edges = [e for e in edges if e.gold_id == "g-tool-sap"]
    assert len(sap_edges) == 2
    decisions = {}
    for edge in sap_edges:
        decisions[edge.edge_key] = (
            ReviewDecisionLabel.EQUIVALENT
            if edge.proposal_key == "obs-a"
            else ReviewDecisionLabel.NARROWER_BUT_VALID
        )
    matching = match_edges(edges, decisions, gold=evaluation.gold, output=out)
    assert len(matching.pairs) == 1
    assert matching.ambiguous is True


def test_qualifier_field_scores_counts_only_applicable(suite):
    inputs, evaluation = case_pair(suite, "TI-04-numeric-frequency")
    gold_item = evaluation.gold.observations[0]
    good = proposal(
        "obs", kind="action", claim="每月盤點庫存 2 次", quote="我每月盤點庫存 2 次。",
        quals=qualifiers(unit="per_month", value="2", verbatim="每月"),
    )
    correct, applicable, wrong = qualifier_field_scores(gold_item, good)
    assert applicable >= 5 and not wrong and correct == applicable
    bad = proposal(
        "obs", kind="action", claim="每週盤點", quote="我每月盤點庫存 2 次。",
        quals=qualifiers(unit="per_week", value="2", verbatim="每月"),
    )
    _, _, wrong_bad = qualifier_field_scores(gold_item, bad)
    assert "frequency_unit" in wrong_bad


def test_empty_denominator_metrics_are_not_applicable(suite):
    inputs, evaluation = case_pair(suite, "TI-11-zero-evidence")
    trial_id = uuid5(NAMESPACE_URL, "noop")
    out = output(user_signal="mixed", insufficiencies=())
    metrics = compute_trial_metrics(
        gold=evaluation.gold, output=out, edges=(), decisions={},
        accepted_proposal_keys=frozenset(),
    )
    assert metrics.raw_precision.value is None  # 空分母
    assert metrics.expected_no_evidence_passed is True


def test_refusal_output_is_quality_failure(suite):
    inputs, evaluation = case_pair(suite, "TI-01-single-action")
    metrics = compute_trial_metrics(
        gold=evaluation.gold, output=None, edges=(), decisions={},
        accepted_proposal_keys=frozenset(),
    )
    assert metrics.recall.value == Decimal("0.000000")
    assert metrics.signals_pass is False
    assert metrics.missed_required_gold_ids


# ── review contract ──────────────────────────────────────────────────────────


def build_reference_review(suite, case_id, batch_id):
    inputs, evaluation = case_pair(suite, case_id)
    trial_id = uuid5(batch_id, case_id)
    result = run_pure_reference_gate(
        inputs, evaluation, trial_id=trial_id, base_time=BASE_TIME
    )
    edges = build_candidate_edges(
        inputs, evaluation.gold, result.output, trial_id=trial_id
    )
    matched_outputs = {e.proposal_key for e in edges}
    unmatched = [
        p.proposal_key
        for p in result.output.observations
        if p.proposal_key not in matched_outputs
    ]
    items = build_review_items(
        batch_id=batch_id,
        trial_id=trial_id,
        inputs=inputs,
        gold=evaluation.gold,
        output=result.output,
        accepted_proposal_keys=frozenset(
            p.proposal_key for p in result.output.observations
        ),
        verifier_reason_codes={},
        edges=edges,
        unmatched_proposal_keys=unmatched,
    )
    return inputs, evaluation, items


def test_review_items_hide_provider_and_expose_rubric(suite):
    batch_id = uuid4()
    _, _, items = build_reference_review(suite, "TI-01-single-action", batch_id)
    assert items
    dumped = " ".join(item.model_dump_json() for item in items)
    for forbidden in ("openrouter", "anthropic", "claude", "slot", "attempt", "cost"):
        assert forbidden not in dumped.lower()
    assert any(item.gold_rubric is not None for item in items)


def test_review_queue_ordering_is_seed_stable(suite):
    batch_id = uuid4()
    _, _, items = build_reference_review(suite, "TI-08-explicit-denial", batch_id)
    a = order_review_queue(items, ordering_seed="seed-1")
    b = order_review_queue(items, ordering_seed="seed-1")
    c = order_review_queue(items, ordering_seed="seed-2")
    assert [i.review_item_id for i in a] == [i.review_item_id for i in b]
    # 不同 seed 通常改變順序(至少 id 集合相同)
    assert {i.review_item_id for i in a} == {i.review_item_id for i in c}


def decision_for(item, label, *, reviewer="maintainer", reason="語意等價"):
    return TurnEvalReviewDecision(
        schema_version="turn_eval_review_decision.v1",
        review_item_id=item.review_item_id,
        review_item_hash=item.review_item_hash,
        decision=label,
        reason=reason,
        reviewer=reviewer,
        reviewed_at=BASE_TIME,
    )


def test_import_rejects_hash_mismatch(suite):
    batch_id = uuid4()
    _, _, items = build_reference_review(suite, "TI-01-single-action", batch_id)
    bad = decision_for(items[0], ReviewDecisionLabel.EQUIVALENT).model_copy(
        update={"review_item_hash": SHA}
    )
    with pytest.raises(ReviewImportError, match="hash"):
        import_review_decisions(items, [bad])


def test_import_rejects_provider_identity_in_reason(suite):
    batch_id = uuid4()
    _, _, items = build_reference_review(suite, "TI-01-single-action", batch_id)
    bad = decision_for(
        items[0], ReviewDecisionLabel.EQUIVALENT, reason="claude 表現不錯"
    )
    with pytest.raises(ReviewImportError, match="provider"):
        import_review_decisions(items, [bad])
    assert reason_contains_provider_identity("這是 OpenRouter 的輸出")


def test_import_revision_supersedes_previous(suite):
    batch_id = uuid4()
    _, _, items = build_reference_review(suite, "TI-01-single-action", batch_id)
    first = decision_for(items[0], ReviewDecisionLabel.EQUIVALENT)
    changed = decision_for(items[0], ReviewDecisionLabel.NARROWER_BUT_VALID).model_copy(
        update={"revision": 2, "supersedes_revision": 1}
    )
    imported = import_review_decisions(items, [first, changed])
    assert (
        imported.decisions_by_item[items[0].review_item_id].decision
        == ReviewDecisionLabel.NARROWER_BUT_VALID
    )
    conflict = decision_for(items[0], ReviewDecisionLabel.DIFFERENT)
    with pytest.raises(ReviewImportError, match="revision"):
        import_review_decisions(items, [first, conflict])


def test_missing_decisions_reported(suite):
    batch_id = uuid4()
    _, _, items = build_reference_review(suite, "TI-02-action-output", batch_id)
    first = decision_for(items[0], ReviewDecisionLabel.EQUIVALENT)
    imported = import_review_decisions(items, [first])
    missing = missing_decisions(items, imported)
    assert len(missing) == len(items) - 1


def test_split_gap_boundary(suite):
    limit = Decimal("0.10")
    dev = MetricResult.compute(95, 100)  # 0.95
    challenge_ok = MetricResult.compute(85, 100)  # 0.85 → gap 0.10 恰好通過
    challenge_fail = MetricResult.compute(84, 100)  # 0.84 → gap 0.11 > 0.10
    assert split_gap_within_limit(dev, challenge_ok, limit=limit) is True
    assert split_gap_within_limit(dev, challenge_fail, limit=limit) is False
    # 任一無適用分母 → None(batch 需 REVIEW_INCOMPLETE,不能假設通過)
    empty = MetricResult.compute(0, 0)
    assert split_gap_within_limit(dev, empty, limit=limit) is None


def test_edge_decision_map_feeds_metrics(suite):
    batch_id = uuid4()
    inputs, evaluation, items = build_reference_review(
        suite, "TI-01-single-action", batch_id
    )
    decisions = [
        decision_for(item, ReviewDecisionLabel.EQUIVALENT) for item in items
    ]
    imported = import_review_decisions(items, decisions)
    edge_map = edge_decision_map(imported, items)
    trial_id = uuid5(batch_id, "TI-01-single-action")
    result = run_pure_reference_gate(
        inputs, evaluation, trial_id=trial_id, base_time=BASE_TIME
    )
    edges = build_candidate_edges(
        inputs, evaluation.gold, result.output, trial_id=trial_id
    )
    metrics = compute_trial_metrics(
        gold=evaluation.gold,
        output=result.output,
        edges=edges,
        decisions=edge_map,
        accepted_proposal_keys=frozenset(
            p.proposal_key for p in result.output.observations
        ),
    )
    assert metrics.recall.value == Decimal("1.000000")
    assert metrics.review_incomplete is False
