"""R5-A pure domain contract tests: grounded short-answer QuestionFrame,
Evidence support union, interpretation receipt, and hashing helpers.

These cover intra-model coherence only. Cross-state gates (a frame target being
supported by active employee Evidence, reducer lifecycle transitions) are the
R5-B/R5-C reducer surface and are not exercised here.
"""

from __future__ import annotations

import hashlib

from app.interview_vnext.domain.hashing import (
    canonical_hash,
    canonical_hash_excluding,
    sha256_utf8_text,
)


# ---------------------------------------------------------------------------
# Batch A: hashing helpers
# ---------------------------------------------------------------------------


def test_sha256_utf8_text_is_the_raw_utf8_digest():
    text = "每週整理缺貨資料"
    expected = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert sha256_utf8_text(text) == expected


def test_sha256_utf8_text_does_not_normalize_newlines():
    assert sha256_utf8_text("a\r\nb") != sha256_utf8_text("a\nb")


def test_sha256_utf8_text_does_not_trim_surrounding_whitespace():
    assert sha256_utf8_text(" 每週 ") != sha256_utf8_text("每週")


def test_sha256_utf8_text_does_not_nfkc_fold():
    # Fullwidth digit vs ASCII digit must stay distinct (no NFKC).
    assert sha256_utf8_text("１") != sha256_utf8_text("1")


def test_canonical_hash_excluding_matches_canonical_hash_of_remainder():
    payload = {"a": 1, "self_hash": "sha256:" + "0" * 64, "b": "每週"}
    assert canonical_hash_excluding(payload, exclude="self_hash") == canonical_hash(
        {"a": 1, "b": "每週"}
    )


def test_canonical_hash_excluding_is_insensitive_to_the_excluded_field_value():
    low = {"a": 1, "self_hash": "sha256:" + "0" * 64}
    high = {"a": 1, "self_hash": "sha256:" + "f" * 64}
    assert canonical_hash_excluding(low, exclude="self_hash") == canonical_hash_excluding(
        high, exclude="self_hash"
    )


# ---------------------------------------------------------------------------
# Batch B: enums, QuestionSourceRef, QuestionProposition
# ---------------------------------------------------------------------------

import pytest
from pydantic import ValidationError

from app.interview_vnext.domain.evidence import (
    EvidenceKind,
    EvidenceQualifiers,
    EvidenceSubject,
    Importance,
)
from app.interview_vnext.domain.question_frame import (
    QuestionDimension,
    QuestionFrameStaleReason,
    QuestionFrameStatus,
    QuestionMode,
    QuestionProposition,
    QuestionSlotKind,
    QuestionSourceKind,
    QuestionSourceRef,
    QuestionTargetKind,
)


HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


def _source_ref(kind=QuestionSourceKind.CONSULTANT_HYPOTHESIS, ref="hypo-1", h=HASH_A):
    return QuestionSourceRef(source_kind=kind, source_ref=ref, source_hash=h)


def test_question_enum_members_cover_the_spec():
    assert set(QuestionMode) >= {
        QuestionMode.OPEN_NARRATIVE,
        QuestionMode.ATOMIC_CONFIRMATION,
        QuestionMode.SLOT_REQUEST,
        QuestionMode.CHOICE,
        QuestionMode.CORRECTION_CHECK,
    }
    assert set(QuestionFrameStatus) == {
        QuestionFrameStatus.ACTIVE,
        QuestionFrameStatus.CONSUMED,
        QuestionFrameStatus.SUPERSEDED,
        QuestionFrameStatus.STALE,
    }
    assert QuestionTargetKind.PROPOSITION.value == "proposition"
    assert QuestionSlotKind.FREQUENCY.value == "frequency"
    assert QuestionDimension.FREQUENCY.value == "frequency"
    assert QuestionFrameStaleReason.ANSWER_NOT_IMMEDIATE.value == "answer_not_immediate"


def test_question_source_ref_rejects_bad_hash():
    with pytest.raises(ValidationError):
        QuestionSourceRef(
            source_kind=QuestionSourceKind.EMPLOYEE_EVIDENCE,
            source_ref="ev-1",
            source_hash="not-a-hash",
        )


def test_question_source_ref_rejects_blank_ref():
    with pytest.raises(ValidationError):
        QuestionSourceRef(
            source_kind=QuestionSourceKind.EMPLOYEE_EVIDENCE,
            source_ref="   ",
            source_hash=HASH_A,
        )


def _proposition(**overrides):
    base = dict(
        subject=EvidenceSubject.EMPLOYEE,
        kind=EvidenceKind.ACTION,
        claim="整理缺貨資料",
        qualifiers=EvidenceQualifiers(importance=Importance.EXPLICIT_CORE),
        source_refs=(_source_ref(),),
    )
    base.update(overrides)
    return QuestionProposition(**base)


def test_proposition_accepts_sorted_unique_source_refs():
    prop = _proposition(
        source_refs=(
            _source_ref(kind=QuestionSourceKind.CONSULTANT_HYPOTHESIS, ref="a", h=HASH_A),
            _source_ref(kind=QuestionSourceKind.EMPLOYEE_EVIDENCE, ref="a", h=HASH_A),
        )
    )
    assert len(prop.source_refs) == 2


def test_proposition_rejects_unsorted_source_refs():
    with pytest.raises(ValidationError):
        _proposition(
            source_refs=(
                _source_ref(kind=QuestionSourceKind.EMPLOYEE_EVIDENCE, ref="a", h=HASH_A),
                _source_ref(kind=QuestionSourceKind.CONSULTANT_HYPOTHESIS, ref="a", h=HASH_A),
            )
        )


def test_proposition_rejects_duplicate_source_refs():
    with pytest.raises(ValidationError):
        _proposition(source_refs=(_source_ref(), _source_ref()))


def test_proposition_rejects_duplicate_supersedes_ids():
    from uuid import uuid4

    dup = uuid4()
    with pytest.raises(ValidationError):
        _proposition(supersedes_evidence_ids=(dup, dup))


# ---------------------------------------------------------------------------
# Batch C: targets and builders
# ---------------------------------------------------------------------------

from app.interview_vnext.domain.evidence import Ownership
from app.interview_vnext.domain.hashing import canonical_hash_excluding
from app.interview_vnext.domain.question_frame import (
    ChoiceOption,
    ChoiceQuestionTarget,
    PropositionQuestionTarget,
    SlotQuestionTarget,
    build_choice_option,
    build_choice_target,
    build_proposition_target,
    build_slot_target,
)


def test_build_proposition_target_seals_a_verifiable_hash():
    target = build_proposition_target(
        target_ordinal=1,
        proposition=_proposition(),
        introduced_dimensions=(QuestionDimension.IMPORTANCE,),
    )
    assert target.target_kind is QuestionTargetKind.PROPOSITION
    assert target.target_hash == canonical_hash_excluding(target, exclude="target_hash")


def test_proposition_target_rejects_forged_hash():
    with pytest.raises(ValidationError):
        PropositionQuestionTarget(
            target_ordinal=1,
            proposition=_proposition(),
            introduced_dimensions=(QuestionDimension.IMPORTANCE,),
            target_hash=HASH_A,
        )


def test_proposition_target_rejects_ordinal_out_of_range():
    with pytest.raises(ValidationError):
        build_proposition_target(
            target_ordinal=17,
            proposition=_proposition(),
            introduced_dimensions=(QuestionDimension.IMPORTANCE,),
        )


def _slot_kwargs(**overrides):
    base = dict(
        target_ordinal=1,
        slot_kind=QuestionSlotKind.FREQUENCY,
        subject=EvidenceSubject.EMPLOYEE,
        evidence_kind=EvidenceKind.FREQUENCY,
        base_claim="整理缺貨資料的頻率",
        claim_template="整理缺貨資料的頻率是{value}",
        base_qualifiers=EvidenceQualifiers(),
        source_refs=(_source_ref(kind=QuestionSourceKind.EMPLOYEE_EVIDENCE, ref="ev-1"),),
    )
    base.update(overrides)
    return base


def test_build_slot_target_derives_introduced_dimension_from_slot_kind():
    target = build_slot_target(**_slot_kwargs())
    assert target.introduced_dimension is QuestionDimension.FREQUENCY
    assert target.target_hash == canonical_hash_excluding(target, exclude="target_hash")


def test_slot_target_rejects_claim_template_without_placeholder():
    with pytest.raises(ValidationError):
        build_slot_target(**_slot_kwargs(claim_template="整理缺貨資料的頻率固定"))


def test_slot_target_rejects_claim_template_with_extra_braces():
    with pytest.raises(ValidationError):
        build_slot_target(**_slot_kwargs(claim_template="{value}{extra}"))


def test_slot_target_rejects_mismatched_introduced_dimension():
    with pytest.raises(ValidationError):
        SlotQuestionTarget(
            target_ordinal=1,
            slot_kind=QuestionSlotKind.FREQUENCY,
            subject=EvidenceSubject.EMPLOYEE,
            evidence_kind=EvidenceKind.FREQUENCY,
            base_claim="c",
            claim_template="c {value}",
            base_qualifiers=EvidenceQualifiers(),
            source_refs=(_source_ref(),),
            introduced_dimension=QuestionDimension.OWNERSHIP,
            target_hash=HASH_A,
        )


def _ownership_option(ordinal, ownership, label):
    return build_choice_option(
        option_ordinal=ordinal,
        label=label,
        proposition=_proposition(
            kind=EvidenceKind.OWNERSHIP,
            claim=f"負責型態:{label}",
            qualifiers=EvidenceQualifiers(ownership=ownership),
        ),
    )


def test_build_choice_target_seals_option_and_target_hashes():
    target = build_choice_target(
        target_ordinal=1,
        multi_select=False,
        introduced_dimension=QuestionDimension.OWNERSHIP,
        options=(
            _ownership_option(1, Ownership.OWNER, "我負責"),
            _ownership_option(2, Ownership.SHARED, "共同負責"),
        ),
    )
    assert target.target_hash == canonical_hash_excluding(target, exclude="target_hash")
    for option in target.options:
        assert option.option_hash == canonical_hash_excluding(option, exclude="option_hash")


def test_choice_target_rejects_single_option():
    with pytest.raises(ValidationError):
        build_choice_target(
            target_ordinal=1,
            multi_select=False,
            introduced_dimension=QuestionDimension.OWNERSHIP,
            options=(_ownership_option(1, Ownership.OWNER, "我負責"),),
        )


def test_choice_target_rejects_noncontiguous_option_ordinals():
    with pytest.raises(ValidationError):
        build_choice_target(
            target_ordinal=1,
            multi_select=False,
            introduced_dimension=QuestionDimension.OWNERSHIP,
            options=(
                _ownership_option(1, Ownership.OWNER, "我負責"),
                _ownership_option(3, Ownership.SHARED, "共同負責"),
            ),
        )


# ---------------------------------------------------------------------------
# Batch D: QuestionFrameDefinition + mode matrix
# ---------------------------------------------------------------------------

from uuid import uuid4

from app.interview_vnext.domain.hashing import sha256_utf8_text
from app.interview_vnext.domain.question_frame import (
    QuestionFrameDefinition,
    build_question_frame_definition,
)


def _atomic_target(introduced=(QuestionDimension.IMPORTANCE,)):
    return build_proposition_target(
        target_ordinal=1, proposition=_proposition(), introduced_dimensions=introduced
    )


def _slot_target():
    return build_slot_target(**_slot_kwargs())


def _choice_target():
    return build_choice_target(
        target_ordinal=1,
        multi_select=False,
        introduced_dimension=QuestionDimension.OWNERSHIP,
        options=(
            _ownership_option(1, Ownership.OWNER, "我負責"),
            _ownership_option(2, Ownership.SHARED, "共同負責"),
        ),
    )


def _correction_target():
    return build_proposition_target(
        target_ordinal=1,
        proposition=_proposition(supersedes_evidence_ids=(uuid4(),)),
        introduced_dimensions=(QuestionDimension.POLARITY,),
    )


def test_build_definition_seals_text_and_definition_hashes():
    text = "你目前每週整理缺貨資料，對嗎？"
    definition = build_question_frame_definition(
        mode=QuestionMode.ATOMIC_CONFIRMATION, question_text=text, targets=(_atomic_target(),)
    )
    assert definition.question_text_hash == sha256_utf8_text(text)
    assert definition.definition_hash == canonical_hash_excluding(
        definition, exclude="definition_hash"
    )


def test_open_narrative_forbids_targets():
    build_question_frame_definition(
        mode=QuestionMode.OPEN_NARRATIVE, question_text="請談談你的工作", targets=()
    )
    with pytest.raises(ValidationError):
        build_question_frame_definition(
            mode=QuestionMode.OPEN_NARRATIVE, question_text="x", targets=(_atomic_target(),)
        )


def test_atomic_confirmation_requires_single_proposition_single_dimension():
    build_question_frame_definition(
        mode=QuestionMode.ATOMIC_CONFIRMATION, question_text="x", targets=(_atomic_target(),)
    )
    with pytest.raises(ValidationError):
        build_question_frame_definition(
            mode=QuestionMode.ATOMIC_CONFIRMATION,
            question_text="x",
            targets=(_atomic_target(introduced=(QuestionDimension.IMPORTANCE, QuestionDimension.FREQUENCY)),),
        )
    with pytest.raises(ValidationError):
        build_question_frame_definition(
            mode=QuestionMode.ATOMIC_CONFIRMATION, question_text="x", targets=(_slot_target(),)
        )


def test_slot_request_requires_single_slot_target():
    build_question_frame_definition(
        mode=QuestionMode.SLOT_REQUEST, question_text="多久做一次？", targets=(_slot_target(),)
    )
    with pytest.raises(ValidationError):
        build_question_frame_definition(
            mode=QuestionMode.SLOT_REQUEST, question_text="x", targets=(_atomic_target(),)
        )


def test_choice_mode_requires_single_choice_target():
    build_question_frame_definition(
        mode=QuestionMode.CHOICE, question_text="你的負責型態？", targets=(_choice_target(),)
    )
    with pytest.raises(ValidationError):
        build_question_frame_definition(
            mode=QuestionMode.CHOICE, question_text="x", targets=(_atomic_target(),)
        )


def test_correction_check_requires_polarity_and_nonempty_supersedes():
    build_question_frame_definition(
        mode=QuestionMode.CORRECTION_CHECK, question_text="其實不是每週？", targets=(_correction_target(),)
    )
    # introduced dimension other than polarity
    with pytest.raises(ValidationError):
        build_question_frame_definition(
            mode=QuestionMode.CORRECTION_CHECK,
            question_text="x",
            targets=(
                build_proposition_target(
                    target_ordinal=1,
                    proposition=_proposition(supersedes_evidence_ids=(uuid4(),)),
                    introduced_dimensions=(QuestionDimension.FREQUENCY,),
                ),
            ),
        )
    # empty supersedes
    with pytest.raises(ValidationError):
        build_question_frame_definition(
            mode=QuestionMode.CORRECTION_CHECK,
            question_text="x",
            targets=(_atomic_target(introduced=(QuestionDimension.POLARITY,)),),
        )


def test_definition_rejects_forged_definition_hash():
    definition = build_question_frame_definition(
        mode=QuestionMode.ATOMIC_CONFIRMATION, question_text="x", targets=(_atomic_target(),)
    )
    with pytest.raises(ValidationError):
        QuestionFrameDefinition(
            mode=definition.mode,
            question_text_hash=definition.question_text_hash,
            targets=definition.targets,
            definition_hash=HASH_A,
        )


# ---------------------------------------------------------------------------
# Batch E: QuestionFrame lifecycle
# ---------------------------------------------------------------------------

from datetime import UTC, datetime

from app.interview_vnext.domain.question_frame import QuestionFrame

NOW = datetime(2026, 7, 20, 0, 0, tzinfo=UTC)


def _frame(**overrides):
    base = dict(
        question_frame_id=uuid4(),
        session_id=uuid4(),
        consultant_turn_id=uuid4(),
        definition=build_question_frame_definition(
            mode=QuestionMode.ATOMIC_CONFIRMATION, question_text="x", targets=(_atomic_target(),)
        ),
        status=QuestionFrameStatus.ACTIVE,
        opened_state_version=1,
        opened_at=NOW,
        answer_turn_id=None,
        consumed_operation_id=None,
        superseded_by_frame_id=None,
        stale_reason=None,
        closed_at=None,
    )
    base.update(overrides)
    return QuestionFrame(**base)


def test_active_frame_without_answer_is_valid():
    frame = _frame()
    assert frame.status is QuestionFrameStatus.ACTIVE


def test_active_frame_with_bound_answer_is_valid():
    frame = _frame(answer_turn_id=uuid4())
    assert frame.answer_turn_id is not None


def test_active_frame_rejects_closure_fields():
    with pytest.raises(ValidationError):
        _frame(closed_at=NOW)


def test_active_frame_rejects_opened_state_version_below_one():
    with pytest.raises(ValidationError):
        _frame(opened_state_version=0)


def test_consumed_frame_requires_answer_operation_and_closed_at():
    _frame(
        status=QuestionFrameStatus.CONSUMED,
        answer_turn_id=uuid4(),
        consumed_operation_id=uuid4(),
        closed_at=NOW,
    )
    with pytest.raises(ValidationError):
        _frame(
            status=QuestionFrameStatus.CONSUMED,
            answer_turn_id=None,
            consumed_operation_id=uuid4(),
            closed_at=NOW,
        )


def test_superseded_frame_forbids_bound_answer():
    _frame(status=QuestionFrameStatus.SUPERSEDED, superseded_by_frame_id=uuid4(), closed_at=NOW)
    with pytest.raises(ValidationError):
        _frame(
            status=QuestionFrameStatus.SUPERSEDED,
            superseded_by_frame_id=uuid4(),
            closed_at=NOW,
            answer_turn_id=uuid4(),
        )


def test_stale_frame_requires_reason_and_allows_answer():
    _frame(
        status=QuestionFrameStatus.STALE,
        stale_reason=QuestionFrameStaleReason.ANSWER_NOT_IMMEDIATE,
        closed_at=NOW,
        answer_turn_id=uuid4(),
    )
    with pytest.raises(ValidationError):
        _frame(status=QuestionFrameStatus.STALE, stale_reason=None, closed_at=NOW)


# ---------------------------------------------------------------------------
# Batch F: Evidence support union
# ---------------------------------------------------------------------------

from app.interview_vnext.domain.evidence import QuoteMatch, QuoteSpan
from app.interview_vnext.domain.support import (
    ContextualAnswerSupport,
    ContextualBindingKind,
    ContextualResolution,
    LiteralEmployeeSpanSupport,
)


def test_literal_support_exact_forbids_normalization_version():
    LiteralEmployeeSpanSupport(
        employee_turn_id=uuid4(),
        quote="每週整理缺貨資料",
        span=QuoteSpan(start=0, end=8),
        quote_match=QuoteMatch.EXACT,
    )
    with pytest.raises(ValidationError):
        LiteralEmployeeSpanSupport(
            employee_turn_id=uuid4(),
            quote="每週整理缺貨資料",
            span=QuoteSpan(start=0, end=8),
            quote_match=QuoteMatch.EXACT,
            normalization_version="quote_nfkc_ws.v1",
        )


def test_literal_support_normalized_requires_version():
    with pytest.raises(ValidationError):
        LiteralEmployeeSpanSupport(
            employee_turn_id=uuid4(),
            quote="每週整理缺貨資料",
            span=QuoteSpan(start=0, end=8),
            quote_match=QuoteMatch.NORMALIZED,
        )


def _contextual(**overrides):
    base = dict(
        employee_turn_id=uuid4(),
        answer_quote="是",
        answer_span=QuoteSpan(start=0, end=1),
        question_frame_id=uuid4(),
        question_frame_definition_hash=HASH_A,
        target_ordinal=1,
        target_hash=HASH_B,
        binding_kind=ContextualBindingKind.AFFIRMATION,
        resolution=ContextualResolution.AFFIRMED,
        value_text=None,
        choice_option_ordinal=None,
    )
    base.update(overrides)
    return ContextualAnswerSupport(**base)


def test_contextual_affirmation_is_valid_without_value_or_option():
    support = _contextual()
    assert support.binding_kind is ContextualBindingKind.AFFIRMATION


def test_contextual_affirmation_rejects_value_text():
    with pytest.raises(ValidationError):
        _contextual(value_text="每週")


def test_contextual_slot_value_requires_value_substring_of_answer():
    _contextual(
        answer_quote="每週，月底加做月報",
        answer_span=QuoteSpan(start=0, end=9),
        binding_kind=ContextualBindingKind.SLOT_VALUE,
        resolution=ContextualResolution.SUPPLIED,
        value_text="每週",
    )
    with pytest.raises(ValidationError):
        _contextual(
            answer_quote="每週",
            answer_span=QuoteSpan(start=0, end=2),
            binding_kind=ContextualBindingKind.SLOT_VALUE,
            resolution=ContextualResolution.SUPPLIED,
            value_text="每天",
        )


def test_contextual_slot_value_requires_value_text_present():
    with pytest.raises(ValidationError):
        _contextual(
            binding_kind=ContextualBindingKind.SLOT_VALUE,
            resolution=ContextualResolution.SUPPLIED,
            value_text=None,
        )


def test_contextual_choice_selection_requires_option_and_no_value():
    _contextual(
        binding_kind=ContextualBindingKind.CHOICE_SELECTION,
        resolution=ContextualResolution.SELECTED,
        choice_option_ordinal=2,
    )
    with pytest.raises(ValidationError):
        _contextual(
            binding_kind=ContextualBindingKind.CHOICE_SELECTION,
            resolution=ContextualResolution.SELECTED,
            choice_option_ordinal=2,
            value_text="x",
        )
    with pytest.raises(ValidationError):
        _contextual(
            binding_kind=ContextualBindingKind.CHOICE_SELECTION,
            resolution=ContextualResolution.SELECTED,
            choice_option_ordinal=None,
        )


def test_contextual_rejects_binding_resolution_mismatch():
    with pytest.raises(ValidationError):
        _contextual(
            binding_kind=ContextualBindingKind.AFFIRMATION,
            resolution=ContextualResolution.DENIED,
        )


# ---------------------------------------------------------------------------
# Batch G: interpretation record
# ---------------------------------------------------------------------------

from app.interview_vnext.domain.interpretation import (
    DialogueAct,
    EpisodeSignal,
    TurnInsufficiencyCode,
    TurnInterpretationRecord,
)

HASH_C = "sha256:" + "c" * 64
HASH_D = "sha256:" + "d" * 64


def _record(**overrides):
    base = dict(
        interpretation_id=uuid4(),
        session_id=uuid4(),
        employee_turn_id=uuid4(),
        operation_id=uuid4(),
        question_frame_id=uuid4(),
        question_frame_definition_hash=HASH_A,
        context_packet_hash=HASH_B,
        output_hash=HASH_C,
        verification_report_hash=HASH_D,
        accepted_evidence_ids=(),
        dialogue_act=DialogueAct.AFFIRM,
        episode_signal=EpisodeSignal.CONTINUE,
        insufficiency_codes=(),
        applied_at=NOW,
    )
    base.update(overrides)
    return TurnInterpretationRecord(**base)


def test_record_with_frame_needs_both_id_and_hash():
    _record()
    with pytest.raises(ValidationError):
        _record(question_frame_definition_hash=None)
    with pytest.raises(ValidationError):
        _record(question_frame_id=None)


def test_record_without_frame_has_both_null():
    record = _record(question_frame_id=None, question_frame_definition_hash=None)
    assert record.question_frame_id is None


def test_zero_evidence_record_is_valid():
    record = _record(dialogue_act=DialogueAct.DONT_KNOW, accepted_evidence_ids=())
    assert record.accepted_evidence_ids == ()


def test_record_rejects_duplicate_accepted_evidence_ids():
    dup = uuid4()
    with pytest.raises(ValidationError):
        _record(accepted_evidence_ids=(dup, dup))


def test_insufficiency_codes_must_follow_enum_declaration_order():
    # no_work_fact is declared before answer_binding_ambiguous, so this order is valid
    # even though it is not alphabetical.
    record = _record(
        insufficiency_codes=(
            TurnInsufficiencyCode.NO_WORK_FACT,
            TurnInsufficiencyCode.ANSWER_BINDING_AMBIGUOUS,
        )
    )
    assert record.insufficiency_codes[0] is TurnInsufficiencyCode.NO_WORK_FACT
    with pytest.raises(ValidationError):
        _record(
            insufficiency_codes=(
                TurnInsufficiencyCode.ANSWER_BINDING_AMBIGUOUS,
                TurnInsufficiencyCode.NO_WORK_FACT,
            )
        )


def test_insufficiency_codes_reject_duplicates():
    with pytest.raises(ValidationError):
        _record(
            insufficiency_codes=(
                TurnInsufficiencyCode.NO_WORK_FACT,
                TurnInsufficiencyCode.NO_WORK_FACT,
            )
        )
