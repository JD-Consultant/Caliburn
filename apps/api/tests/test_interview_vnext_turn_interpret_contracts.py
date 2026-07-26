"""C2 contract vectors for turn interpretation identity, policy and report shape.

These are *pure* contract tests (corrective plan §7.1–§7.3): deterministic
identity derivation, the single sealed marker authority, and the enriched
verification report items. Full verifier behaviour vectors (false specificity,
duplicate all-drop, system insufficiency) belong to C3 and to the rewritten
``test_interview_vnext_turn_interpret`` end-to-end suite.
"""

from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.interview_vnext.application.turn_interpret import (
    _FREQUENCY_MATCHERS,
    _OWNERSHIP_MATCHERS,
    _TIME_SCOPE_MATCHERS,
    _TYPICALITY_MATCHERS,
    _sole_marker,
)
from app.interview_vnext.domain.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceSubject,
    FrequencyUnit,
    Ownership,
    Polarity,
    TimeScope,
    Typicality,
)
from app.interview_vnext.domain.support import (
    LiteralEmployeeSpanSupport,
    QuoteMatch,
    QuoteSpan,
)
from app.interview_vnext.domain.turn_identity import (
    contextual_evidence_id,
    derive_binding_ref,
    derive_proposal_ref,
    literal_evidence_id,
)
from app.interview_vnext.llm.turn_interpret import (
    TURN_INTERPRET_VERIFIER_POLICY_V2,
    AnswerBindingVerification,
    EmergentTopicVerification,
    EmergentTopicProposal,
    ObservationVerification,
    TurnInterpretRejectCode,
    TurnInterpretVerifierPolicy,
    TurnInterpretVerifierPolicyDefinition,
    compile_marker,
)

_OPERATION = UUID("11111111-1111-5111-8111-111111111111")
_SESSION = UUID("22222222-2222-5222-8222-222222222222")
_TURN = UUID("33333333-3333-5333-8333-333333333333")

_POLICY_PATH = (
    Path(__file__).resolve().parents[1]
    / "app/interview_vnext/llm/verifier_policies/turn-interpret-verifier.2.0.0.json"
)


# --- deterministic identity -------------------------------------------------


def test_refs_are_zero_padded_and_index_based() -> None:
    assert derive_proposal_ref(1) == "p0001"
    assert derive_binding_ref(1) == "b0001"
    assert derive_proposal_ref(42) == "p0042"
    assert derive_binding_ref(9999) == "b9999"


@pytest.mark.parametrize("index", [0, -1, 10000])
def test_refs_reject_out_of_range_indices(index: int) -> None:
    with pytest.raises(ValueError):
        derive_proposal_ref(index)
    with pytest.raises(ValueError):
        derive_binding_ref(index)


# --- sealed marker policy ---------------------------------------------------


def test_reject_order_is_the_whole_enum_in_declaration_order() -> None:
    assert TURN_INTERPRET_VERIFIER_POLICY_V2.reject_order == tuple(TurnInterpretRejectCode)
    assert len(tuple(TurnInterpretRejectCode)) == 26


def test_policy_seals_all_six_marker_dimensions_from_amendment_11() -> None:
    policy = TURN_INTERPRET_VERIFIER_POLICY_V2
    assert set(policy.frequency_markers[FrequencyUnit.PER_DAY]) >= {"每天", "每日", "daily"}
    assert "只有.*才" in policy.typicality_markers[Typicality.EXCEPTION]
    assert "我和.*共同" in policy.ownership_markers[Ownership.SHARED]
    assert "與.*共同" in policy.ownership_markers[Ownership.SHARED]
    assert "支援.*處理" in policy.ownership_markers[Ownership.ASSISTS]
    # Owner markers must NOT include the bare pronouns: those are a slot-only
    # exact allowance (§10.5), never a general ownership marker.
    assert "我" not in policy.ownership_markers[Ownership.OWNER]
    assert "我自己" not in policy.ownership_markers[Ownership.OWNER]
    # Polarity keeps only the negative/uncertain markers; affirmed is inferred
    # from the absence of them, so it has no marker entry.
    assert set(policy.polarity_markers) == {Polarity.DENIED, Polarity.UNCERTAIN}
    assert set(policy.time_scope_markers[TimeScope.CURRENT]) >= {"目前", "currently"}


def test_marker_map_rejects_a_markerless_key() -> None:
    base = TURN_INTERPRET_VERIFIER_POLICY_V2.model_dump(mode="json", exclude={"policy_hash"})
    base["time_scope_markers"] = {**base["time_scope_markers"], "unknown": ["目前"]}
    with pytest.raises(ValidationError):
        TurnInterpretVerifierPolicyDefinition.model_validate(base)


def test_marker_map_rejects_an_invalid_regex() -> None:
    base = TURN_INTERPRET_VERIFIER_POLICY_V2.model_dump(mode="json", exclude={"policy_hash"})
    base["ownership_markers"] = {**base["ownership_markers"], "owner": ["("]}
    with pytest.raises(ValidationError):
        TurnInterpretVerifierPolicyDefinition.model_validate(base)


def test_marker_map_rejects_an_empty_pattern_tuple() -> None:
    base = TURN_INTERPRET_VERIFIER_POLICY_V2.model_dump(mode="json", exclude={"policy_hash"})
    base["frequency_markers"] = {**base["frequency_markers"], "per_day": []}
    with pytest.raises(ValidationError):
        TurnInterpretVerifierPolicyDefinition.model_validate(base)


def test_marker_map_rejects_a_missing_required_semantic_key() -> None:
    base = TURN_INTERPRET_VERIFIER_POLICY_V2.model_dump(mode="json", exclude={"policy_hash"})
    del base["frequency_markers"]["per_month"]
    with pytest.raises(ValidationError):
        TurnInterpretVerifierPolicyDefinition.model_validate(base)


def test_marker_map_rejects_duplicate_patterns() -> None:
    base = TURN_INTERPRET_VERIFIER_POLICY_V2.model_dump(mode="json", exclude={"policy_hash"})
    base["frequency_markers"]["per_day"] = ["每天", "每天"]
    with pytest.raises(ValidationError):
        TurnInterpretVerifierPolicyDefinition.model_validate(base)


def test_truncated_reject_order_is_rejected() -> None:
    base = TURN_INTERPRET_VERIFIER_POLICY_V2.model_dump(mode="json", exclude={"policy_hash"})
    base["reject_order"] = base["reject_order"][:-1]
    with pytest.raises(ValidationError):
        TurnInterpretVerifierPolicyDefinition.model_validate(base)


def test_policy_hash_tamper_is_rejected() -> None:
    base = TURN_INTERPRET_VERIFIER_POLICY_V2.model_dump(mode="json", exclude={"policy_hash"})
    with pytest.raises(ValidationError):
        TurnInterpretVerifierPolicy.model_validate({**base, "policy_hash": "sha256:" + "0" * 64})


def test_sealed_json_reconstructs_to_the_runtime_authority() -> None:
    loaded = TurnInterpretVerifierPolicy.model_validate_json(
        _POLICY_PATH.read_text(encoding="utf-8")
    )
    assert loaded.policy_hash == TURN_INTERPRET_VERIFIER_POLICY_V2.policy_hash
    assert loaded.ownership_markers == TURN_INTERPRET_VERIFIER_POLICY_V2.ownership_markers


# --- marker matcher mechanism ----------------------------------------------


def test_compile_marker_folds_case_only_for_ascii() -> None:
    assert compile_marker("weekly").flags & re.IGNORECASE
    assert not (compile_marker("每週").flags & re.IGNORECASE)


def test_sole_marker_reads_sealed_matchers_for_a_single_value() -> None:
    assert _sole_marker("每週整理", _FREQUENCY_MATCHERS) == (FrequencyUnit.PER_WEEK, True)
    # English marker matches case-insensitively.
    assert _sole_marker("WEEKLY report", _FREQUENCY_MATCHERS) == (FrequencyUnit.PER_WEEK, True)


def test_sole_marker_matches_sealed_regex_patterns() -> None:
    assert _sole_marker("只有月底才處理", _TYPICALITY_MATCHERS) == (Typicality.EXCEPTION, True)
    assert _sole_marker("我和同事共同負責", _OWNERSHIP_MATCHERS) == (Ownership.SHARED, True)


def test_sole_marker_reports_incoherence_on_conflicting_markers() -> None:
    value, coherent = _sole_marker("我負責但我協助", _OWNERSHIP_MATCHERS)
    assert value is None and coherent is False


def test_sole_marker_reports_absence_as_coherent_none() -> None:
    assert _sole_marker("隨便寫寫", _TIME_SCOPE_MATCHERS) == (None, True)


# --- enriched verification report items ------------------------------------


def _literal_evidence(index: int) -> Evidence:
    return Evidence(
        evidence_id=literal_evidence_id(_OPERATION, index),
        session_id=_SESSION,
        subject=EvidenceSubject.EMPLOYEE,
        kind=EvidenceKind.ACTION,
        claim="處理客訴",
        support=LiteralEmployeeSpanSupport(
            employee_turn_id=_TURN,
            quote="處理客訴",
            span=QuoteSpan(start=0, end=4),
            quote_match=QuoteMatch.EXACT,
        ),
        extractor_operation_id=_OPERATION,
    )


def test_accepted_observation_binds_candidate_to_materialized_evidence() -> None:
    evidence = _literal_evidence(1)
    decision = ObservationVerification(
        proposal_index=1,
        proposal_ref=derive_proposal_ref(1),
        candidate_evidence_id=evidence.evidence_id,
        accepted=True,
        reason_codes=(),
        computed_span=QuoteSpan(start=0, end=4),
        evidence=evidence,
    )
    assert decision.candidate_evidence_id == literal_evidence_id(_OPERATION, 1)


def test_rejected_observation_keeps_candidate_and_has_no_evidence() -> None:
    decision = ObservationVerification(
        proposal_index=2,
        proposal_ref=derive_proposal_ref(2),
        candidate_evidence_id=literal_evidence_id(_OPERATION, 2),
        accepted=False,
        reason_codes=(TurnInterpretRejectCode.QUOTE_NOT_FOUND,),
        computed_span=None,
        evidence=None,
    )
    assert decision.candidate_evidence_id == literal_evidence_id(_OPERATION, 2)
    assert decision.evidence is None


def test_observation_ref_must_match_its_index() -> None:
    with pytest.raises(ValidationError):
        ObservationVerification(
            proposal_index=1,
            proposal_ref="p0002",
            candidate_evidence_id=literal_evidence_id(_OPERATION, 1),
            accepted=False,
            reason_codes=(TurnInterpretRejectCode.QUOTE_NOT_FOUND,),
            computed_span=None,
            evidence=None,
        )


def test_observation_rejects_a_binding_namespace_code() -> None:
    with pytest.raises(ValidationError):
        ObservationVerification(
            proposal_index=1,
            proposal_ref=derive_proposal_ref(1),
            candidate_evidence_id=literal_evidence_id(_OPERATION, 1),
            accepted=False,
            reason_codes=(TurnInterpretRejectCode.BINDING_KIND_MISMATCH,),
            computed_span=None,
            evidence=None,
        )


def test_observation_reason_codes_must_follow_policy_order() -> None:
    with pytest.raises(ValidationError, match="policy reject order"):
        ObservationVerification(
            proposal_index=1,
            proposal_ref=derive_proposal_ref(1),
            candidate_evidence_id=literal_evidence_id(_OPERATION, 1),
            accepted=False,
            reason_codes=(
                TurnInterpretRejectCode.NON_ATOMIC_CLAIM,
                TurnInterpretRejectCode.QUOTE_NOT_FOUND,
            ),
            computed_span=None,
            evidence=None,
        )


def test_ambiguous_binding_accepts_with_no_candidates() -> None:
    decision = AnswerBindingVerification(
        binding_index=1,
        binding_ref=derive_binding_ref(1),
        candidate_evidence_ids=(),
        accepted=True,
        reason_codes=(),
        computed_span=QuoteSpan(start=0, end=1),
        materialized_evidence=(),
    )
    assert decision.candidate_evidence_ids == ()
    assert decision.materialized_evidence == ()


def test_rejected_binding_keeps_pre_derived_candidates() -> None:
    candidates = (
        contextual_evidence_id(_OPERATION, 3, 1),
        contextual_evidence_id(_OPERATION, 3, 2),
    )
    decision = AnswerBindingVerification(
        binding_index=3,
        binding_ref=derive_binding_ref(3),
        candidate_evidence_ids=candidates,
        accepted=False,
        reason_codes=(TurnInterpretRejectCode.CHOICE_SELECTION_INVALID,),
        computed_span=QuoteSpan(start=0, end=1),
        materialized_evidence=(),
    )
    assert decision.candidate_evidence_ids == candidates


def test_binding_ref_must_match_its_index() -> None:
    with pytest.raises(ValidationError):
        AnswerBindingVerification(
            binding_index=2,
            binding_ref="b0001",
            candidate_evidence_ids=(),
            accepted=False,
            reason_codes=(TurnInterpretRejectCode.BINDING_WITHOUT_QUESTION_FRAME,),
            computed_span=None,
            materialized_evidence=(),
        )


def test_binding_rejects_an_observation_namespace_code() -> None:
    with pytest.raises(ValidationError):
        AnswerBindingVerification(
            binding_index=1,
            binding_ref=derive_binding_ref(1),
            candidate_evidence_ids=(),
            accepted=False,
            reason_codes=(TurnInterpretRejectCode.QUOTE_NOT_FOUND,),
            computed_span=None,
            materialized_evidence=(),
        )


def test_binding_reason_codes_must_follow_policy_order() -> None:
    with pytest.raises(ValidationError, match="policy reject order"):
        AnswerBindingVerification(
            binding_index=1,
            binding_ref=derive_binding_ref(1),
            candidate_evidence_ids=(),
            accepted=False,
            reason_codes=(
                TurnInterpretRejectCode.CHOICE_SELECTION_INVALID,
                TurnInterpretRejectCode.BINDING_KIND_MISMATCH,
            ),
            computed_span=None,
            materialized_evidence=(),
        )


def test_emergent_topic_reason_codes_must_follow_policy_order() -> None:
    with pytest.raises(ValidationError, match="policy reject order"):
        EmergentTopicVerification(
            topic_index=1,
            proposal=EmergentTopicProposal(
                topic="新的工作主題",
                quote="新的工作主題",
                quote_occurrence=1,
            ),
            accepted=False,
            reason_codes=(
                TurnInterpretRejectCode.QUOTE_OCCURRENCE_OUT_OF_RANGE,
                TurnInterpretRejectCode.QUOTE_NOT_FOUND,
            ),
            computed_span=None,
        )


def test_accepted_binding_without_materialized_evidence_is_incoherent() -> None:
    with pytest.raises(ValidationError):
        AnswerBindingVerification(
            binding_index=1,
            binding_ref=derive_binding_ref(1),
            candidate_evidence_ids=(contextual_evidence_id(_OPERATION, 1, 1),),
            accepted=True,
            reason_codes=(),
            computed_span=QuoteSpan(start=0, end=1),
            materialized_evidence=(),
        )
