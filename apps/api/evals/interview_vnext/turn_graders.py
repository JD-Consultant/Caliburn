"""Deterministic graders, candidate edges, one-to-one matching and metrics (§13).

Grader 順序固定(§13):integrity → deterministic gates → claim anchoring →
blind adjudication → metrics。本模組只含 code 可判定的部分;語意等價由
``review.py`` 的盲化人工裁決供給,matching 在拿到 decisions 後才產生分數。
Verifier drop 不能讓 trial 自動通過:raw model precision 把被 drop 的
proposal 留在分母,committed precision 另計(§13.1)。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Mapping, Sequence
from uuid import UUID

from app.interview_vnext.domain.evidence import EvidenceStatus
from app.interview_vnext.domain.hashing import canonical_json
from app.interview_vnext.llm.turn_interpret import (
    ObservationProposal,
    TURN_INTERPRET_VERIFIER_POLICY_V1,
    TurnInterpretOutput,
    TurnInterpretVerificationReport,
)

from .contracts import (
    ExpectedCommit,
    FailureSeverity,
    GoldLabelStatus,
    GoldRequirement,
    GraderDefinition,
    GraderStatus,
    MetricResult,
    QualifierExact,
    QualifierNotApplicable,
    QualifierOneOf,
    ReviewDecisionLabel,
    TurnEvalGold,
    TurnEvalGoldObservation,
    TurnEvalGraderResult,
)
from .identities import prior_evidence_uuid
from .loader import TurnEvalCaseInputs, quote_occurrences


_NUMBER = re.compile(TURN_INTERPRET_VERIFIER_POLICY_V1.number_pattern)
_REFERENCE_MARKERS = TURN_INTERPRET_VERIFIER_POLICY_V1.reference_markers

# 進 recall 分母/自動裁決的 gold label 狀態;disputed/unknown/needs_sme 不計分(§6.5)
_SCORABLE_LABELS = frozenset({GoldLabelStatus.ADJUDICATED})

RECALL_MATCH_LABELS = frozenset(
    {ReviewDecisionLabel.EQUIVALENT, ReviewDecisionLabel.NARROWER_BUT_VALID}
)
PRECISION_MATCH_LABELS = RECALL_MATCH_LABELS


def _span(text: str, quote: str, occurrence: int) -> tuple[int, int] | None:
    positions: list[int] = []
    start = 0
    while True:
        found = text.find(quote, start)
        if found < 0:
            break
        positions.append(found)
        start = found + 1
    if occurrence < 1 or occurrence > len(positions):
        return None
    begin = positions[occurrence - 1]
    return begin, begin + len(quote)


# ── Grading context ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GradingContext:
    """Everything the deterministic graders may see for one trial.

    gold 只在 trial 拿到 terminal outcome 後由 caller 載入(§8.2)。"""

    inputs: TurnEvalCaseInputs
    gold: TurnEvalGold
    trial_id: UUID
    case_id: str
    output: TurnInterpretOutput | None
    report: TurnInterpretVerificationReport | None
    committed_kind: str | None  # "evidence" | "noop" | None(failed)
    state_before_hash: str | None
    state_after_hash: str | None
    evidence_status: Mapping[UUID, EvidenceStatus] = field(default_factory=dict)
    failure_reason_code: str | None = None

    @property
    def target_text(self) -> str:
        return self.inputs.transcript[-1].text

    @property
    def prior_uuid_by_key(self) -> dict[str, UUID]:
        return {
            item.evidence_key: prior_evidence_uuid(self.trial_id, item.evidence_key)
            for item in self.inputs.initial_fixture.prior_evidence
        }


def _result(
    context: GradingContext,
    definition: GraderDefinition,
    *,
    status: GraderStatus,
    reason_code: str,
    severity: FailureSeverity | None = None,
    subject_ids: tuple[str, ...] = (),
    details: dict | None = None,
) -> TurnEvalGraderResult:
    return TurnEvalGraderResult(
        schema_version="turn_eval_grader_result.v1",
        grader_name=definition.grader_name,
        grader_version=definition.grader_version,
        grader_definition_hash=definition.definition_hash,
        case_id=context.case_id,
        trial_id=context.trial_id,
        status=status,
        severity=severity,
        reason_code=reason_code,
        subject_ids=subject_ids,
        details_json=canonical_json(details or {}),
    )


# ── Deterministic graders(§13.1;每個 grader 有版本識別)────────────────────

OUTPUT_SCHEMA_GRADER = GraderDefinition(
    grader_name="output_schema", grader_version="1.0.0"
)
QUOTE_SPAN_GRADER = GraderDefinition(grader_name="quote_span", grader_version="1.0.0")
SOURCE_SUBJECT_GRADER = GraderDefinition(
    grader_name="source_subject", grader_version="1.0.0"
)
FOREIGN_ID_GRADER = GraderDefinition(grader_name="foreign_id", grader_version="1.0.0")
STATE_TRANSITION_GRADER = GraderDefinition(
    grader_name="state_transition", grader_version="1.0.0"
)
NO_OP_GRADER = GraderDefinition(grader_name="no_op", grader_version="1.0.0")
CORRECTION_LINEAGE_GRADER = GraderDefinition(
    grader_name="correction_lineage", grader_version="1.0.0"
)
UNSUPPORTED_QUANTIFICATION_GRADER = GraderDefinition(
    grader_name="unsupported_quantification", grader_version="1.0.0"
)
REFERENCE_LEAKAGE_GRADER = GraderDefinition(
    grader_name="reference_leakage", grader_version="1.0.0"
)


def grade_output_schema(context: GradingContext) -> TurnEvalGraderResult:
    """正常內容 parse/schema 失敗算 quality fail(§9.4/§13.1)。"""

    if context.output is not None:
        return _result(
            context, OUTPUT_SCHEMA_GRADER, status=GraderStatus.PASS, reason_code="ok"
        )
    return _result(
        context,
        OUTPUT_SCHEMA_GRADER,
        status=GraderStatus.FAIL,
        severity=FailureSeverity.MAJOR,
        reason_code=context.failure_reason_code or "no_parsed_output",
    )


def grade_quote_span(context: GradingContext) -> TurnEvalGraderResult:
    if context.output is None:
        return _result(
            context, QUOTE_SPAN_GRADER, status=GraderStatus.NOT_APPLICABLE,
            reason_code="no_output",
        )
    bad: list[str] = []
    for proposal in context.output.observations:
        if _span(context.target_text, proposal.quote, proposal.quote_occurrence) is None:
            bad.append(proposal.proposal_key)
    for topic in context.output.emergent_topics:
        if _span(context.target_text, topic.quote, topic.quote_occurrence) is None:
            bad.append(f"topic:{topic.topic}")
    if bad:
        return _result(
            context, QUOTE_SPAN_GRADER, status=GraderStatus.FAIL,
            severity=FailureSeverity.MAJOR, reason_code="quote_span_unresolvable",
            subject_ids=tuple(bad),
        )
    return _result(
        context, QUOTE_SPAN_GRADER, status=GraderStatus.PASS, reason_code="ok"
    )


def grade_source_subject(context: GradingContext) -> TurnEvalGraderResult:
    """不可拿 consultant/system/reference 文字當 employee quote(§13.1)。"""

    if context.output is None:
        return _result(
            context, SOURCE_SUBJECT_GRADER, status=GraderStatus.NOT_APPLICABLE,
            reason_code="no_output",
        )
    non_target_texts = [
        turn.text for turn in context.inputs.transcript[:-1]
    ]
    offenders: list[str] = []
    for proposal in context.output.observations:
        in_target = quote_occurrences(context.target_text, proposal.quote) > 0
        if not in_target and any(
            quote_occurrences(text, proposal.quote) > 0 for text in non_target_texts
        ):
            offenders.append(proposal.proposal_key)
    if offenders:
        return _result(
            context, SOURCE_SUBJECT_GRADER, status=GraderStatus.FAIL,
            severity=FailureSeverity.CRITICAL,
            reason_code="quote_from_non_target_turn",
            subject_ids=tuple(offenders),
        )
    return _result(
        context, SOURCE_SUBJECT_GRADER, status=GraderStatus.PASS, reason_code="ok"
    )


def grade_foreign_id(context: GradingContext) -> TurnEvalGraderResult:
    if context.output is None:
        return _result(
            context, FOREIGN_ID_GRADER, status=GraderStatus.NOT_APPLICABLE,
            reason_code="no_output",
        )
    allowed = set(context.prior_uuid_by_key.values())
    offenders = [
        proposal.proposal_key
        for proposal in context.output.observations
        if set(proposal.correction_target_evidence_ids) - allowed
    ]
    if offenders:
        return _result(
            context, FOREIGN_ID_GRADER, status=GraderStatus.FAIL,
            severity=FailureSeverity.CRITICAL, reason_code="foreign_correction_target",
            subject_ids=tuple(offenders),
        )
    return _result(
        context, FOREIGN_ID_GRADER, status=GraderStatus.PASS, reason_code="ok"
    )


def grade_state_transition(context: GradingContext) -> TurnEvalGraderResult:
    expectation = context.gold.state_expectation
    if context.committed_kind is None:
        # terminal failed trial:state 必須不變(安全性),但 quality 已由
        # output_schema/attempt 分數反映。
        if context.state_before_hash == context.state_after_hash:
            return _result(
                context, STATE_TRANSITION_GRADER, status=GraderStatus.PASS,
                reason_code="failed_trial_state_unchanged",
            )
        return _result(
            context, STATE_TRANSITION_GRADER, status=GraderStatus.FAIL,
            severity=FailureSeverity.CRITICAL,
            reason_code="failed_trial_mutated_state",
        )
    changed = context.state_before_hash != context.state_after_hash
    if changed != expectation.state_hash_changed:
        return _result(
            context, STATE_TRANSITION_GRADER, status=GraderStatus.FAIL,
            severity=FailureSeverity.CRITICAL, reason_code="state_hash_mismatch",
            details={"expected_changed": expectation.state_hash_changed},
        )
    prior = context.prior_uuid_by_key
    for key in expectation.prior_evidence_superseded_keys:
        if context.evidence_status.get(prior[key]) != EvidenceStatus.SUPERSEDED:
            return _result(
                context, STATE_TRANSITION_GRADER, status=GraderStatus.FAIL,
                severity=FailureSeverity.CRITICAL,
                reason_code="expected_supersede_missing", subject_ids=(key,),
            )
    for key in expectation.forbidden_superseded_keys:
        if context.evidence_status.get(prior[key]) != EvidenceStatus.ACTIVE:
            return _result(
                context, STATE_TRANSITION_GRADER, status=GraderStatus.FAIL,
                severity=FailureSeverity.CRITICAL,
                reason_code="forbidden_supersede_happened", subject_ids=(key,),
            )
    return _result(
        context, STATE_TRANSITION_GRADER, status=GraderStatus.PASS, reason_code="ok"
    )


def grade_no_op(context: GradingContext) -> TurnEvalGraderResult:
    if context.gold.expected_commit != ExpectedCommit.NO_OP:
        return _result(
            context, NO_OP_GRADER, status=GraderStatus.NOT_APPLICABLE,
            reason_code="not_a_noop_case",
        )
    if (
        context.committed_kind == "noop"
        and context.state_before_hash == context.state_after_hash
    ):
        return _result(
            context, NO_OP_GRADER, status=GraderStatus.PASS, reason_code="ok"
        )
    return _result(
        context, NO_OP_GRADER, status=GraderStatus.FAIL,
        severity=FailureSeverity.CRITICAL, reason_code="noop_case_committed_evidence",
        details={"committed_kind": context.committed_kind},
    )


def grade_correction_lineage(context: GradingContext) -> TurnEvalGraderResult:
    """known target 必 supersede;unknown target 不得猜(§13.1)。"""

    expected_known = any(
        item.correction_target_evidence_keys for item in context.gold.observations
    )
    expected_unknown = (
        "correction_target_unknown"
        in {reason.value for reason in context.gold.required_insufficiencies}
    )
    if not expected_known and not expected_unknown:
        return _result(
            context, CORRECTION_LINEAGE_GRADER, status=GraderStatus.NOT_APPLICABLE,
            reason_code="no_correction_expectation",
        )
    if context.output is None:
        return _result(
            context, CORRECTION_LINEAGE_GRADER, status=GraderStatus.FAIL,
            severity=FailureSeverity.MAJOR, reason_code="no_output",
        )
    prior = context.prior_uuid_by_key
    if expected_known:
        expected_targets = {
            prior[key]
            for item in context.gold.observations
            for key in item.correction_target_evidence_keys
        }
        claimed = {
            target
            for proposal in context.output.observations
            for target in proposal.correction_target_evidence_ids
        }
        if claimed != expected_targets:
            return _result(
                context, CORRECTION_LINEAGE_GRADER, status=GraderStatus.FAIL,
                severity=FailureSeverity.CRITICAL,
                reason_code="correction_target_mismatch",
                details={
                    "expected": sorted(str(t) for t in expected_targets),
                    "claimed": sorted(str(t) for t in claimed),
                },
            )
    if expected_unknown:
        guessed = [
            proposal.proposal_key
            for proposal in context.output.observations
            if proposal.correction_target_evidence_ids
        ]
        if guessed:
            return _result(
                context, CORRECTION_LINEAGE_GRADER, status=GraderStatus.FAIL,
                severity=FailureSeverity.CRITICAL,
                reason_code="guessed_unknown_correction_target",
                subject_ids=tuple(guessed),
            )
        superseded = [
            key
            for key, uuid in prior.items()
            if context.evidence_status.get(uuid) == EvidenceStatus.SUPERSEDED
        ]
        if superseded:
            return _result(
                context, CORRECTION_LINEAGE_GRADER, status=GraderStatus.FAIL,
                severity=FailureSeverity.CRITICAL,
                reason_code="unknown_correction_overwrote_prior",
                subject_ids=tuple(superseded),
            )
    return _result(
        context, CORRECTION_LINEAGE_GRADER, status=GraderStatus.PASS, reason_code="ok"
    )


def grade_unsupported_quantification(context: GradingContext) -> TurnEvalGraderResult:
    if context.output is None:
        return _result(
            context, UNSUPPORTED_QUANTIFICATION_GRADER,
            status=GraderStatus.NOT_APPLICABLE, reason_code="no_output",
        )
    offenders: list[str] = []
    for proposal in context.output.observations:
        quote_numbers = set(_NUMBER.findall(proposal.quote))
        if not set(_NUMBER.findall(proposal.claim)) <= quote_numbers:
            offenders.append(proposal.proposal_key)
            continue
        value = proposal.qualifiers.frequency.value
        if value is not None and value not in proposal.quote:
            offenders.append(proposal.proposal_key)
    if offenders:
        return _result(
            context, UNSUPPORTED_QUANTIFICATION_GRADER, status=GraderStatus.FAIL,
            severity=FailureSeverity.CRITICAL, reason_code="unsupported_quantification",
            subject_ids=tuple(offenders),
        )
    return _result(
        context, UNSUPPORTED_QUANTIFICATION_GRADER, status=GraderStatus.PASS,
        reason_code="ok",
    )


def grade_reference_leakage(context: GradingContext) -> TurnEvalGraderResult:
    if context.output is None:
        return _result(
            context, REFERENCE_LEAKAGE_GRADER, status=GraderStatus.NOT_APPLICABLE,
            reason_code="no_output",
        )
    offenders = [
        proposal.proposal_key
        for proposal in context.output.observations
        if any(marker in proposal.claim.casefold() for marker in _REFERENCE_MARKERS)
    ]
    if offenders:
        return _result(
            context, REFERENCE_LEAKAGE_GRADER, status=GraderStatus.FAIL,
            severity=FailureSeverity.CRITICAL, reason_code="reference_leakage",
            subject_ids=tuple(offenders),
        )
    return _result(
        context, REFERENCE_LEAKAGE_GRADER, status=GraderStatus.PASS, reason_code="ok"
    )


DETERMINISTIC_GRADERS = (
    grade_output_schema,
    grade_quote_span,
    grade_source_subject,
    grade_foreign_id,
    grade_state_transition,
    grade_no_op,
    grade_correction_lineage,
    grade_unsupported_quantification,
    grade_reference_leakage,
)


def run_deterministic_graders(
    context: GradingContext,
) -> tuple[TurnEvalGraderResult, ...]:
    """固定順序執行;前層 invalid/fail 不會讓後層假 pass(§13)。"""

    return tuple(grader(context) for grader in DETERMINISTIC_GRADERS)


# ── Candidate edges 與一對一 matching(§13.2)────────────────────────────────


@dataclass(frozen=True)
class CandidateEdge:
    gold_id: str
    proposal_key: str
    output_index: int  # 1-based
    qualifiers_pass: bool
    correction_conflict: bool

    @property
    def edge_key(self) -> tuple[str, str]:
        return (self.gold_id, self.proposal_key)


def qualifier_expectations_pass(
    gold_item: TurnEvalGoldObservation, proposal: ObservationProposal
) -> bool:
    getters = {
        "time_scope": proposal.qualifiers.time_scope.value,
        "typicality": proposal.qualifiers.typicality.value,
        "polarity": proposal.qualifiers.polarity.value,
        "frequency_unit": proposal.qualifiers.frequency.unit.value,
        "frequency_value": proposal.qualifiers.frequency.value,
        "importance": proposal.qualifiers.importance.value,
        "ownership": proposal.qualifiers.ownership.value,
    }
    for field_name, actual in getters.items():
        expectation = getattr(gold_item.qualifiers, field_name)
        if isinstance(expectation, QualifierNotApplicable):
            continue
        if field_name == "frequency_value":
            if isinstance(expectation, QualifierExact):
                if actual is None or Decimal(actual) != Decimal(expectation.value):
                    return False
            elif isinstance(expectation, QualifierOneOf):
                if actual is None or all(
                    Decimal(actual) != Decimal(value) for value in expectation.values
                ):
                    return False
            continue
        if isinstance(expectation, QualifierExact) and actual != expectation.value:
            return False
        if isinstance(expectation, QualifierOneOf) and actual not in expectation.values:
            return False
    return True


def qualifier_field_scores(
    gold_item: TurnEvalGoldObservation, proposal: ObservationProposal
) -> tuple[int, int, tuple[str, ...]]:
    """(correct, applicable, wrong_fields);not_applicable 不進分母(§13.3)。"""

    getters = {
        "time_scope": proposal.qualifiers.time_scope.value,
        "typicality": proposal.qualifiers.typicality.value,
        "polarity": proposal.qualifiers.polarity.value,
        "frequency_unit": proposal.qualifiers.frequency.unit.value,
        "frequency_value": proposal.qualifiers.frequency.value,
        "importance": proposal.qualifiers.importance.value,
        "ownership": proposal.qualifiers.ownership.value,
    }
    correct = 0
    applicable = 0
    wrong: list[str] = []
    for field_name, actual in getters.items():
        expectation = getattr(gold_item.qualifiers, field_name)
        if isinstance(expectation, QualifierNotApplicable):
            continue
        applicable += 1
        ok: bool
        if field_name == "frequency_value":
            if isinstance(expectation, QualifierExact):
                ok = actual is not None and Decimal(actual) == Decimal(
                    expectation.value
                )
            else:
                assert isinstance(expectation, QualifierOneOf)
                ok = actual is not None and any(
                    Decimal(actual) == Decimal(value) for value in expectation.values
                )
        elif isinstance(expectation, QualifierExact):
            ok = actual == expectation.value
        else:
            assert isinstance(expectation, QualifierOneOf)
            ok = actual in expectation.values
        if ok:
            correct += 1
        else:
            wrong.append(field_name)
    return correct, applicable, tuple(wrong)


def build_candidate_edges(
    inputs: TurnEvalCaseInputs,
    gold: TurnEvalGold,
    output: TurnInterpretOutput,
    *,
    trial_id: UUID,
) -> tuple[CandidateEdge, ...]:
    """§13.2 edge 條件:同 source turn(恆為 target)、quote/occ 命中 anchor 或
    span 被 anchor 完整包含、subject/kind 無衝突、correction target 無衝突。"""

    target_text = inputs.transcript[-1].text
    prior = {
        item.evidence_key: prior_evidence_uuid(trial_id, item.evidence_key)
        for item in inputs.initial_fixture.prior_evidence
    }
    edges: list[CandidateEdge] = []
    for index, proposal in enumerate(output.observations, 1):
        span = _span(target_text, proposal.quote, proposal.quote_occurrence)
        if span is None:
            continue
        for gold_item in gold.observations:
            if proposal.subject not in gold_item.allowed_subjects:
                continue
            if proposal.kind not in gold_item.allowed_kinds:
                continue
            anchor_hit = False
            for anchor in gold_item.source_anchors:
                if (
                    proposal.quote == anchor.quote
                    and proposal.quote_occurrence == anchor.occurrence
                ):
                    anchor_hit = True
                    break
                anchor_span = _span(target_text, anchor.quote, anchor.occurrence)
                if (
                    anchor_span is not None
                    and anchor_span[0] <= span[0]
                    and span[1] <= anchor_span[1]
                ):
                    anchor_hit = True
                    break
            if not anchor_hit:
                continue
            expected_targets = {
                prior[key] for key in gold_item.correction_target_evidence_keys
            }
            claimed_targets = set(proposal.correction_target_evidence_ids)
            correction_conflict = False
            if gold_item.correction_target_evidence_keys:
                correction_conflict = claimed_targets != expected_targets
            elif claimed_targets:
                correction_conflict = True
            edges.append(
                CandidateEdge(
                    gold_id=gold_item.gold_id,
                    proposal_key=proposal.proposal_key,
                    output_index=index,
                    qualifiers_pass=qualifier_expectations_pass(gold_item, proposal),
                    correction_conflict=correction_conflict,
                )
            )
    return tuple(sorted(edges, key=lambda e: (e.gold_id, e.output_index)))


@dataclass(frozen=True)
class MatchingResult:
    pairs: tuple[tuple[str, str], ...]  # (gold_id, proposal_key)
    ambiguous: bool
    unmatched_gold_ids: tuple[str, ...]
    unmatched_proposal_keys: tuple[str, ...]


def _all_maximum_matchings(
    edges: Sequence[CandidateEdge],
) -> list[frozenset[tuple[str, str]]]:
    gold_ids = sorted({edge.gold_id for edge in edges})
    results: set[frozenset[tuple[str, str]]] = set()
    best_size = 0

    def extend(index: int, used_outputs: frozenset[str], chosen: frozenset):
        nonlocal best_size, results
        if index == len(gold_ids):
            if len(chosen) > best_size:
                best_size = len(chosen)
                results = {chosen}
            elif len(chosen) == best_size:
                results.add(chosen)
            return
        gold_id = gold_ids[index]
        extend(index + 1, used_outputs, chosen)  # 不配這個 gold
        for edge in edges:
            if edge.gold_id != gold_id or edge.proposal_key in used_outputs:
                continue
            extend(
                index + 1,
                used_outputs | {edge.proposal_key},
                chosen | {(edge.gold_id, edge.proposal_key)},
            )

    extend(0, frozenset(), frozenset())
    return [m for m in results if len(m) == best_size]


def match_edges(
    edges: Sequence[CandidateEdge],
    decisions: Mapping[tuple[str, str], ReviewDecisionLabel],
    *,
    gold: TurnEvalGold,
    output: TurnInterpretOutput,
) -> MatchingResult:
    """Deterministic maximum-cardinality matching;影響分數的 tie 標 ambiguous,
    不由排序偷偷裁決語意(§13.2)。"""

    acceptable = [
        edge
        for edge in edges
        if decisions.get(edge.edge_key) in PRECISION_MATCH_LABELS
        and not edge.correction_conflict
    ]
    matchings = _all_maximum_matchings(acceptable)
    label_of = {edge.edge_key: decisions.get(edge.edge_key) for edge in acceptable}
    qualifiers_of = {edge.edge_key: edge.qualifiers_pass for edge in acceptable}
    if not matchings:
        chosen: frozenset = frozenset()
        ambiguous = False
    else:
        # 不同 maximum matching 若造成不同的 (matched gold, label, qualifiers)
        # 或不同 matched outputs,即為影響分數的 tie。
        outcomes = {
            frozenset(
                (gold_id, label_of[(gold_id, key)], qualifiers_of[(gold_id, key)])
                for gold_id, key in matching
            )
            | frozenset(("output", key) for _, key in matching)
            for matching in matchings
        }
        ambiguous = len(outcomes) > 1
        chosen = sorted(
            matchings,
            key=lambda matching: tuple(sorted(matching)),
        )[0]
    matched_gold = {gold_id for gold_id, _ in chosen}
    matched_outputs = {key for _, key in chosen}
    unmatched_gold = tuple(
        item.gold_id
        for item in gold.observations
        if item.gold_id not in matched_gold
    )
    unmatched_outputs = tuple(
        proposal.proposal_key
        for proposal in output.observations
        if proposal.proposal_key not in matched_outputs
    )
    return MatchingResult(
        pairs=tuple(sorted(chosen)),
        ambiguous=ambiguous,
        unmatched_gold_ids=unmatched_gold,
        unmatched_proposal_keys=unmatched_outputs,
    )


# ── Metrics(§13.3/§13.4)────────────────────────────────────────────────────


@dataclass(frozen=True)
class TrialMetrics:
    raw_precision: MetricResult
    committed_precision: MetricResult
    recall: MetricResult
    qualifier_exactness: MetricResult
    expected_no_evidence_passed: bool | None
    signals_pass: bool
    insufficiency_pass: bool
    matched_pairs: tuple[tuple[str, str], ...]
    false_positive_keys: tuple[str, ...]
    missed_required_gold_ids: tuple[str, ...]
    prevented_by_verifier_keys: tuple[str, ...]
    review_incomplete: bool


def compute_trial_metrics(
    *,
    gold: TurnEvalGold,
    output: TurnInterpretOutput | None,
    edges: Sequence[CandidateEdge],
    decisions: Mapping[tuple[str, str], ReviewDecisionLabel],
    accepted_proposal_keys: frozenset[str],
) -> TrialMetrics:
    scorable_required = [
        item
        for item in gold.observations
        if item.requirement == GoldRequirement.REQUIRED
        and item.label_status in _SCORABLE_LABELS
    ]
    gold_by_id = {item.gold_id: item for item in gold.observations}

    if output is None:
        # refusal/parse failure:視為 quality failure(§9.4);required gold 全漏
        return TrialMetrics(
            raw_precision=MetricResult.compute(0, 0),
            committed_precision=MetricResult.compute(0, 0),
            recall=MetricResult.compute(0, len(scorable_required)),
            qualifier_exactness=MetricResult.compute(0, 0),
            expected_no_evidence_passed=(
                None if gold.expected_commit != ExpectedCommit.NO_OP else False
            ),
            signals_pass=False,
            insufficiency_pass=False,
            matched_pairs=(),
            false_positive_keys=(),
            missed_required_gold_ids=tuple(
                item.gold_id for item in scorable_required
            ),
            prevented_by_verifier_keys=(),
            review_incomplete=False,
        )

    matching = match_edges(edges, decisions, gold=gold, output=output)
    review_incomplete = matching.ambiguous
    # 每個 output observation 都必須有裁決:有 edge 的看 edge decision;
    # 無 edge 的必須有 (\"__unmatched__\", key) 裁決(broader/different)。
    for proposal in output.observations:
        has_edge_decision = any(
            (edge.gold_id, proposal.proposal_key) in decisions
            for edge in edges
            if edge.proposal_key == proposal.proposal_key
        )
        if not has_edge_decision and (
            "__unmatched__", proposal.proposal_key
        ) not in decisions:
            review_incomplete = True

    matched_pairs = matching.pairs
    matched_output_keys = {key for _, key in matched_pairs}

    all_keys = [proposal.proposal_key for proposal in output.observations]
    raw_denominator = len(all_keys)
    raw_numerator = len(matched_output_keys)
    committed_keys = [key for key in all_keys if key in accepted_proposal_keys]
    committed_numerator = len(
        [key for key in matched_output_keys if key in accepted_proposal_keys]
    )

    recall_numerator = 0
    missed: list[str] = []
    for item in scorable_required:
        pair = next(
            (pair for pair in matched_pairs if pair[0] == item.gold_id), None
        )
        if pair is None:
            missed.append(item.gold_id)
            continue
        label = decisions.get(pair)
        qualifiers_ok = next(
            edge.qualifiers_pass
            for edge in edges
            if edge.edge_key == pair
        )
        if label == ReviewDecisionLabel.EQUIVALENT and qualifiers_ok:
            recall_numerator += 1
        elif label == ReviewDecisionLabel.NARROWER_BUT_VALID and qualifiers_ok:
            # narrower 不漏 material qualifier 才算 recall(§13.2)
            recall_numerator += 1
        else:
            missed.append(item.gold_id)

    qualifier_correct = 0
    qualifier_applicable = 0
    proposal_by_key = {p.proposal_key: p for p in output.observations}
    for gold_id, key in matched_pairs:
        gold_item = gold_by_id[gold_id]
        if gold_item.label_status not in _SCORABLE_LABELS:
            continue
        correct, applicable, _ = qualifier_field_scores(
            gold_item, proposal_by_key[key]
        )
        qualifier_correct += correct
        qualifier_applicable += applicable

    if gold.expected_commit == ExpectedCommit.NO_OP and not gold.observations:
        expected_no_evidence = len(output.observations) == 0
        raw_precision = MetricResult.compute(0, 0)
        committed_precision = MetricResult.compute(0, 0)
        # 若模型輸出了 observation,不填 precision=1,用 expected_no_evidence fail
        if output.observations:
            raw_precision = MetricResult.compute(0, len(output.observations))
            committed_precision = MetricResult.compute(0, len(committed_keys))
    else:
        expected_no_evidence = None
        raw_precision = MetricResult.compute(raw_numerator, raw_denominator)
        committed_precision = MetricResult.compute(
            committed_numerator, len(committed_keys)
        )

    signals_pass = (
        output.user_signal in gold.allowed_user_signals
        and output.episode_signal in gold.allowed_episode_signals
    )
    produced = {item.reason_code for item in output.insufficiencies}
    required_set = set(gold.required_insufficiencies)
    allowed_set = set(gold.allowed_insufficiencies)
    insufficiency_pass = required_set <= produced and not (
        produced - required_set - allowed_set
    )

    prevented = tuple(
        sorted(
            key
            for key in all_keys
            if key not in accepted_proposal_keys and key not in matched_output_keys
        )
    )
    return TrialMetrics(
        raw_precision=raw_precision,
        committed_precision=committed_precision,
        recall=MetricResult.compute(recall_numerator, len(scorable_required)),
        qualifier_exactness=MetricResult.compute(
            qualifier_correct, qualifier_applicable
        ),
        expected_no_evidence_passed=expected_no_evidence,
        signals_pass=signals_pass,
        insufficiency_pass=insufficiency_pass,
        matched_pairs=matched_pairs,
        false_positive_keys=tuple(
            key for key in all_keys if key not in matched_output_keys
        ),
        missed_required_gold_ids=tuple(missed),
        prevented_by_verifier_keys=prevented,
        review_incomplete=review_incomplete,
    )


def split_gap_within_limit(
    development: MetricResult, challenge: MetricResult, *, limit: Decimal
) -> bool | None:
    """§15.4:development - challenge <= limit;任一無適用分母回 None
    (batch 標 REVIEW_INCOMPLETE,不能假設通過)。"""

    if development.value is None or challenge.value is None:
        return None
    return (development.value - challenge.value) <= limit
