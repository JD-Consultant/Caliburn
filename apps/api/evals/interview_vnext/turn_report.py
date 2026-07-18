"""Case aggregate, batch hard/quality gate and Markdown renderer (§15).

Aggregation is deliberately layered: per-trial hard gate + metrics → per-case
``pass^3`` (three quality slots all pass, no averaging) → batch hard gates
(100% invariants, zero forbidden/critical) → batch quality gate (precision/
recall/qualifier thresholds, split gap). A single critical failure fails the
case regardless of other scores; cost-data gaps never change the quality score
but block any "controlled cost" claim (§15.4). The highest normal decision for
a one-person team is ``TURN_GATE_PASS_ENGINEERING`` (§15.5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Sequence
from uuid import UUID

from .contracts import (
    BatchDecision,
    BatchTotals,
    CaseDecision,
    CasePassEntry,
    CaseSlotReport,
    CaseSplit,
    ExecutionMode,
    ExpectedCommit,
    FailureRecord,
    FailureSeverity,
    GraderStatus,
    HardGateResult,
    MetricResult,
    MetricSummary,
    ReviewCompleteness,
    SplitMetrics,
    TrialDisposition,
    TurnEvalBatchReport,
    TurnEvalCaseReport,
    TurnEvalGold,
    TurnEvalGraderResult,
)
from .turn_graders import TrialMetrics

SPLIT_GAP_LIMIT = Decimal("0.10")
RAW_PRECISION_FLOOR = Decimal("0.95")
RECALL_FLOOR = Decimal("0.85")
QUALIFIER_FLOOR = Decimal("0.90")

# §15.4:這些 case 各自 case-specific gate 三次全過
CASE_SPECIFIC_GATE_IDS = frozenset(
    {
        "TI-02-action-output",
        "TI-03-tools-not-skills",
        "TI-09-known-correction",
        "TI-10-unknown-correction-target",
        "TI-11-zero-evidence",
        "TI-12-injection-unicode-repeat",
    }
)


@dataclass(frozen=True)
class TrialScore:
    """Everything the aggregator needs from one graded trial."""

    trial_id: UUID
    case_id: str
    split: CaseSplit
    slot_index: int
    disposition: TrialDisposition
    grader_results: tuple[TurnEvalGraderResult, ...]
    metrics: TrialMetrics
    review_complete: bool
    had_infrastructure_retry: bool = False
    inference_calls: int = 0
    observed_cost_usd: Decimal | None = None
    usage_input_tokens: int | None = None
    usage_output_tokens: int | None = None
    usage_cache_read_tokens: int | None = None
    usage_cache_write_tokens: int | None = None
    usage_reasoning_tokens: int | None = None

    @property
    def scored(self) -> bool:
        return self.disposition == TrialDisposition.QUALITY_SCORED

    @property
    def critical_count(self) -> int:
        return sum(
            1
            for g in self.grader_results
            if g.status == GraderStatus.FAIL
            and g.severity == FailureSeverity.CRITICAL
        )

    @property
    def major_count(self) -> int:
        return sum(
            1
            for g in self.grader_results
            if g.status == GraderStatus.FAIL and g.severity == FailureSeverity.MAJOR
        )

    @property
    def minor_count(self) -> int:
        return sum(
            1
            for g in self.grader_results
            if g.status == GraderStatus.FAIL and g.severity == FailureSeverity.MINOR
        )

    @property
    def deterministic_hard_pass(self) -> bool:
        """所有 deterministic gate 無 critical fail、無 needs_review、無 invalid。"""

        for g in self.grader_results:
            if g.status == GraderStatus.INVALID:
                return False
            if g.status == GraderStatus.FAIL:
                return False
            if g.status == GraderStatus.NEEDS_REVIEW:
                return False
        return True


def trial_hard_gate(score: TrialScore, gold: TurnEvalGold) -> bool:
    """§15.1 raw model hard gate for one quality trial."""

    if not score.scored:
        return False
    if not score.deterministic_hard_pass:
        return False
    if score.critical_count > 0:
        return False
    if score.metrics.review_incomplete:
        return False
    if not score.metrics.signals_pass:
        return False
    if not score.metrics.insufficiency_pass:
        return False
    if gold.expected_commit == ExpectedCommit.NO_OP:
        return score.metrics.expected_no_evidence_passed is True
    # evidence case:required recall 必須 1(raw model 準)
    return score.metrics.recall.value == Decimal("1.000000")


def _slot_report(score: TrialScore, gold: TurnEvalGold) -> CaseSlotReport:
    hard = trial_hard_gate(score, gold) if score.scored else None
    return CaseSlotReport(
        slot_index=score.slot_index,
        trial_id=score.trial_id,
        disposition=score.disposition,
        hard_gate_passed=hard,
        raw_precision=score.metrics.raw_precision if score.scored else None,
        committed_precision=score.metrics.committed_precision if score.scored else None,
        recall=score.metrics.recall if score.scored else None,
        qualifier_exactness=score.metrics.qualifier_exactness if score.scored else None,
        expected_no_evidence_passed=(
            score.metrics.expected_no_evidence_passed if score.scored else None
        ),
        critical_count=score.critical_count,
        major_count=score.major_count,
        minor_count=score.minor_count,
        review_complete=score.review_complete,
    )


def build_case_report(
    case_id: str,
    split: CaseSplit,
    gold: TurnEvalGold,
    scores: Sequence[TrialScore],
) -> TurnEvalCaseReport:
    """Three quality slots → pass^3 case report (§15.2)."""

    ordered = sorted(scores, key=lambda s: s.slot_index)
    slots = tuple(_slot_report(score, gold) for score in ordered)
    scored = [s for s in ordered if s.scored]
    pass_pow_3 = len(scored) == 3 and all(
        trial_hard_gate(s, gold) for s in scored
    )

    def summary(getter) -> MetricSummary:
        values = tuple(
            getter(s.metrics).value if s.scored else None for s in ordered
        )
        return MetricSummary.compute(values)

    trials_with_critical = sum(1 for s in ordered if s.critical_count > 0)
    trials_with_major = sum(1 for s in ordered if s.major_count > 0)
    trials_with_minor = sum(1 for s in ordered if s.minor_count > 0)

    case_specific = None
    if case_id in CASE_SPECIFIC_GATE_IDS:
        case_specific = pass_pow_3

    if trials_with_critical > 0:
        decision = CaseDecision.FAIL
    elif any(s.metrics.review_incomplete for s in scored) or len(scored) < 3:
        decision = (
            CaseDecision.REVIEW_INCOMPLETE
            if any(s.metrics.review_incomplete for s in scored)
            else CaseDecision.FAIL
        )
    elif pass_pow_3:
        decision = CaseDecision.PASS
    else:
        decision = CaseDecision.FAIL

    return TurnEvalCaseReport(
        schema_version="turn_eval_case_report.v1",
        case_id=case_id,
        split=split,
        slots=slots,
        pass_pow_3=pass_pow_3,
        raw_precision_summary=summary(lambda m: m.raw_precision),
        committed_precision_summary=summary(lambda m: m.committed_precision),
        recall_summary=summary(lambda m: m.recall),
        qualifier_exactness_summary=summary(lambda m: m.qualifier_exactness),
        trials_with_critical=trials_with_critical,
        trials_with_major=trials_with_major,
        trials_with_minor=trials_with_minor,
        case_specific_gate_passed=case_specific,
        case_decision=decision,
    )


def _micro(getter, scores: Sequence[TrialScore]) -> MetricResult:
    numerator = 0
    denominator = 0
    for score in scores:
        if not score.scored:
            continue
        metric = getter(score.metrics)
        if not metric.applicable:
            continue
        numerator += metric.numerator
        denominator += metric.denominator
    return MetricResult.compute(numerator, denominator)


@dataclass
class BatchAggregate:
    case_reports: list[TurnEvalCaseReport] = field(default_factory=list)
    failures: list[FailureRecord] = field(default_factory=list)


def _split_metrics(
    scores: Sequence[TrialScore], split: CaseSplit
) -> SplitMetrics | None:
    subset = [s for s in scores if s.split == split]
    if not subset:
        return None
    return SplitMetrics(
        precision=_micro(lambda m: m.raw_precision, subset),
        recall=_micro(lambda m: m.recall, subset),
        qualifier_exactness=_micro(lambda m: m.qualifier_exactness, subset),
    )


def build_batch_report(
    *,
    batch_id: UUID,
    plan_hash: str,
    suite_version: str,
    suite_hash: str,
    execution_mode,
    git_sha: str,
    dirty_worktree: bool,
    gold_by_case: dict[str, TurnEvalGold],
    split_by_case: dict[str, CaseSplit],
    scores: Sequence[TrialScore],
    review: ReviewCompleteness,
    route_clean: bool,
    capture_verified: bool,
    created_at,
    batch_incomplete: bool = False,
    harness_invalid: bool = False,
    wall_clock_seconds: int | None = None,
    failures: Sequence[FailureRecord] = (),
    limitations: Sequence[str] = (),
) -> TurnEvalBatchReport:
    """§15.3~§15.6:hard gate → quality gate → decision enum。"""

    by_case: dict[str, list[TrialScore]] = {}
    for score in scores:
        by_case.setdefault(score.case_id, []).append(score)

    case_reports = [
        build_case_report(
            case_id,
            split_by_case[case_id],
            gold_by_case[case_id],
            _slot_scores(case_scores),
        )
        for case_id, case_scores in sorted(by_case.items())
    ]

    quality_scores = [s for s in scores if s.scored]
    raw_precision = _micro(lambda m: m.raw_precision, quality_scores)
    committed_precision = _micro(lambda m: m.committed_precision, quality_scores)
    recall = _micro(lambda m: m.recall, quality_scores)
    qualifier = _micro(lambda m: m.qualifier_exactness, quality_scores)

    dev = _split_metrics(quality_scores, CaseSplit.DEVELOPMENT)
    challenge = _split_metrics(quality_scores, CaseSplit.CHALLENGE)

    def gap_ok(getter) -> bool | None:
        if dev is None or challenge is None:
            return None
        d = getter(dev).value
        c = getter(challenge).value
        if d is None or c is None:
            return None
        return (d - c) <= SPLIT_GAP_LIMIT

    gap_flags = [
        gap_ok(lambda s: s.precision),
        gap_ok(lambda s: s.recall),
        gap_ok(lambda s: s.qualifier_exactness),
    ]
    split_gap_within = None if None in gap_flags else all(gap_flags)

    totals = _totals(scores, wall_clock_seconds=wall_clock_seconds)

    # ── hard gates(§15.3)──────────────────────────────────────────────────
    all_scored_pass = all(
        trial_hard_gate(s, gold_by_case[s.case_id]) for s in quality_scores
    )
    every_case_three_slots = all(
        len([s for s in by_case.get(c, ()) if s.scored]) == 3
        for c in gold_by_case
    )
    no_critical = all(s.critical_count == 0 for s in scores)
    reports_by_case = {report.case_id: report for report in case_reports}
    all_case_specific = all(
        case_id not in CASE_SPECIFIC_GATE_IDS
        or (
            case_id in reports_by_case
            and reports_by_case[case_id].case_specific_gate_passed is True
        )
        for case_id in gold_by_case
    )
    hard_gates = (
        HardGateResult(gate_name="deterministic_invariants", passed=all_scored_pass),
        HardGateResult(gate_name="route_exact", passed=route_clean),
        HardGateResult(gate_name="capture_reproducible", passed=capture_verified),
        HardGateResult(gate_name="no_critical_failure", passed=no_critical),
        HardGateResult(
            gate_name="review_complete",
            passed=review.complete and review.needs_sme_count == 0,
        ),
        HardGateResult(
            gate_name="every_case_three_quality_trials", passed=every_case_three_slots
        ),
        HardGateResult(gate_name="case_specific_gates", passed=all_case_specific),
    )
    hard_ok = all(g.passed for g in hard_gates)

    # ── quality gate(§15.4)────────────────────────────────────────────────
    quality_ok = (
        (raw_precision.value or Decimal(0)) >= RAW_PRECISION_FLOOR
        and (recall.value or Decimal(0)) >= RECALL_FLOOR
        and (qualifier.value or Decimal(0)) >= QUALIFIER_FLOOR
        and split_gap_within is True
    )

    # ── decision enum(§15.5)───────────────────────────────────────────────
    decision = _decide(
        hard_ok=hard_ok,
        quality_ok=quality_ok,
        review=review,
        split_gap_within=split_gap_within,
        totals=totals,
        capture_verified=capture_verified,
        route_clean=route_clean,
        batch_incomplete=batch_incomplete,
        harness_invalid=harness_invalid,
    )
    # §8.3:只有 live batch 可能 promotion-eligible;mocked/reference 一律 false。
    promotion_eligible = (
        execution_mode == ExecutionMode.LIVE
        and decision
        in {
            BatchDecision.TURN_GATE_PASS_ENGINEERING,
            BatchDecision.TURN_GATE_PASS_DOMAIN_REVIEWED,
        }
        and not dirty_worktree
    )

    case_matrix = tuple(
        CasePassEntry(
            case_id=case_id,
            split=split_by_case[case_id],
            pass_pow_3=(
                reports_by_case[case_id].pass_pow_3
                if case_id in reports_by_case
                else False
            ),
            case_decision=(
                reports_by_case[case_id].case_decision
                if case_id in reports_by_case
                else CaseDecision.FAIL
            ),
        )
        for case_id in sorted(gold_by_case)
    )

    return TurnEvalBatchReport(
        schema_version="turn_eval_batch_report.v1",
        batch_id=batch_id,
        plan_hash=plan_hash,
        suite_version=suite_version,
        suite_hash=suite_hash,
        execution_mode=execution_mode,
        git_sha=git_sha,
        dirty_worktree=dirty_worktree,
        promotion_eligible=promotion_eligible,
        decision=decision,
        hard_gates=hard_gates,
        raw_precision_micro=raw_precision,
        committed_precision_micro=committed_precision,
        recall_micro=recall,
        qualifier_exactness_micro=qualifier,
        development_metrics=dev,
        challenge_metrics=challenge,
        split_gap_within_limit=split_gap_within,
        case_matrix=case_matrix,
        totals=totals,
        review=review,
        failures=tuple(failures),
        limitations=tuple(sorted(set(limitations))),
        created_at=created_at,
    )


def _slot_scores(scores: Sequence[TrialScore]) -> list[TrialScore]:
    """Select one report row per quality slot while retaining replacement
    attempts in batch totals.  A quality-scored attempt wins; otherwise the
    final infrastructure/harness attempt represents the unfilled slot."""

    grouped: dict[int, list[TrialScore]] = {}
    for score in scores:
        grouped.setdefault(score.slot_index, []).append(score)
    selected: list[TrialScore] = []
    for slot_index in sorted(grouped):
        attempts = grouped[slot_index]
        quality = [score for score in attempts if score.scored]
        selected.append(quality[-1] if quality else attempts[-1])
    return selected


def _totals(
    scores: Sequence[TrialScore], *, wall_clock_seconds: int | None = None
) -> BatchTotals:
    quality = sum(1 for s in scores if s.disposition == TrialDisposition.QUALITY_SCORED)
    infra = sum(
        1 for s in scores if s.disposition == TrialDisposition.INFRASTRUCTURE_INVALID
    )
    harness = sum(
        1 for s in scores if s.disposition == TrialDisposition.HARNESS_INVALID
    )
    cancelled = sum(1 for s in scores if s.disposition == TrialDisposition.CANCELLED)
    inference_calls = sum(s.inference_calls for s in scores)

    costs = [s.observed_cost_usd for s in scores if s.observed_cost_usd is not None]
    observed_cost = sum(costs, Decimal(0)) if costs else None
    input_tokens = _sum_optional(s.usage_input_tokens for s in scores)
    output_tokens = _sum_optional(s.usage_output_tokens for s in scores)
    cache_read_tokens = _sum_optional(s.usage_cache_read_tokens for s in scores)
    cache_write_tokens = _sum_optional(s.usage_cache_write_tokens for s in scores)
    reasoning_tokens = _sum_optional(s.usage_reasoning_tokens for s in scores)
    return BatchTotals(
        total_trials=len(scores),
        quality_trials=quality,
        infrastructure_invalid_trials=infra,
        harness_invalid_trials=harness,
        cancelled_trials=cancelled,
        inference_calls=inference_calls,
        usage_input_tokens=input_tokens,
        usage_output_tokens=output_tokens,
        usage_cache_read_tokens=cache_read_tokens,
        usage_cache_write_tokens=cache_write_tokens,
        usage_reasoning_tokens=reasoning_tokens,
        observed_cost_total_usd=observed_cost,
        wall_clock_seconds=wall_clock_seconds,
    )


def _sum_optional(values) -> int | None:
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def _decide(
    *,
    hard_ok: bool,
    quality_ok: bool,
    review: ReviewCompleteness,
    split_gap_within: bool | None,
    totals: BatchTotals,
    capture_verified: bool,
    route_clean: bool,
    batch_incomplete: bool,
    harness_invalid: bool,
) -> BatchDecision:
    if harness_invalid or not capture_verified or not route_clean:
        return BatchDecision.HARNESS_INVALID
    if batch_incomplete:
        return BatchDecision.BATCH_INCOMPLETE
    if not review.complete or review.needs_sme_count > 0:
        # review 未完成或仍需 SME，都不可進品質裁決。
        return BatchDecision.REVIEW_INCOMPLETE
    if split_gap_within is None:
        return BatchDecision.REVIEW_INCOMPLETE
    if not hard_ok:
        return BatchDecision.TURN_GATE_FAIL
    if not quality_ok:
        return BatchDecision.TURN_GATE_FAIL
    return BatchDecision.TURN_GATE_PASS_ENGINEERING


# ── Markdown renderer(§12.2 去除 raw provider content 的 aggregate report)──


def render_markdown(report: TurnEvalBatchReport) -> str:
    lines: list[str] = []
    lines.append(f"# Turn Eval Batch Report — {report.decision.value}")
    lines.append("")
    lines.append(f"- batch_id: `{report.batch_id}`")
    lines.append(f"- suite: `{report.suite_version}` (`{report.suite_hash}`)")
    lines.append(f"- execution mode: `{report.execution_mode.value}`")
    lines.append(f"- git SHA: `{report.git_sha}` (dirty={report.dirty_worktree})")
    lines.append(f"- promotion eligible: **{report.promotion_eligible}**")
    lines.append("")

    lines.append("## Hard gates")
    lines.append("")
    lines.append("| gate | passed |")
    lines.append("|---|---|")
    for gate in report.hard_gates:
        lines.append(f"| {gate.gate_name} | {'✅' if gate.passed else '❌'} |")
    lines.append("")

    lines.append("## Raw-model micro metrics")
    lines.append("")
    lines.append("| metric | value |")
    lines.append("|---|---|")
    lines.append(f"| evidence precision (raw) | {_fmt(report.raw_precision_micro)} |")
    lines.append(
        f"| evidence precision (committed) | {_fmt(report.committed_precision_micro)} |"
    )
    lines.append(f"| evidence recall | {_fmt(report.recall_micro)} |")
    lines.append(f"| qualifier exactness | {_fmt(report.qualifier_exactness_micro)} |")
    lines.append(f"| split gap within 0.10 | {report.split_gap_within_limit} |")
    lines.append("")

    lines.append("## Per-case pass^3 matrix")
    lines.append("")
    lines.append("| case | split | pass^3 | decision |")
    lines.append("|---|---|---|---|")
    for entry in report.case_matrix:
        lines.append(
            f"| {entry.case_id} | {entry.split.value} | "
            f"{'✅' if entry.pass_pow_3 else '❌'} | {entry.case_decision.value} |"
        )
    lines.append("")

    t = report.totals
    lines.append("## Trial totals")
    lines.append("")
    lines.append(f"- total trials: {t.total_trials}")
    lines.append(f"- quality-scored: {t.quality_trials}")
    lines.append(f"- infrastructure-invalid: {t.infrastructure_invalid_trials}")
    lines.append(f"- harness-invalid: {t.harness_invalid_trials}")
    lines.append(f"- cancelled: {t.cancelled_trials}")
    lines.append(f"- inference calls: {t.inference_calls}")
    lines.append(
        f"- observed cost USD: "
        f"{t.observed_cost_total_usd if t.observed_cost_total_usd is not None else 'unavailable'}"
    )
    lines.append("")

    r = report.review
    lines.append("## Review completeness")
    lines.append("")
    lines.append(
        f"- adjudicated {r.completed_review_items}/{r.required_review_items} items"
    )
    lines.append(
        f"- passing-trace sample {r.passing_trace_sample_read}/"
        f"{r.passing_trace_sample_required}"
    )
    lines.append(f"- needs_sme: {r.needs_sme_count}")
    lines.append("")

    if report.failures:
        lines.append("## Failures")
        lines.append("")
        lines.append("| case | attribution | severity | reason | prevented_by_verifier |")
        lines.append("|---|---|---|---|---|")
        for f in report.failures:
            lines.append(
                f"| {f.case_id or '-'} | {f.attribution.value} | {f.severity.value} | "
                f"{f.reason_code} | {f.prevented_by_verifier} |"
            )
        lines.append("")

    if report.limitations:
        lines.append("## Limitations")
        lines.append("")
        for item in report.limitations:
            lines.append(f"- {item}")
        lines.append("")

    # §15.6 小樣本誠實性
    lines.append("## Honesty notes")
    lines.append("")
    lines.append(
        "- 12 constructed component tasks, up to 36 quality trials; not a "
        "population win rate and no p-values."
    )
    lines.append(
        "- challenge cases were built and seen by the maintainer, not a true "
        "blind held-out set."
    )
    lines.append(
        "- three trials per case is an early cost trade-off; this gate only "
        "decides whether V3-6 may begin."
    )
    return "\n".join(lines) + "\n"


def _fmt(metric: MetricResult) -> str:
    return "n/a" if metric.value is None else str(metric.value)
