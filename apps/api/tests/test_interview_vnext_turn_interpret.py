from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
from pydantic import ValidationError

from app.interview_vnext.application.turn_interpret import (
    accepted_evidence,
    turn_interpret_input_from_context,
    verify_turn_interpret_output,
)
from app.interview_vnext.domain.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceQualifiers,
    EvidenceStatus,
    EvidenceSubject,
    FrequencyQualifier,
    FrequencyUnit,
    Importance,
    Ownership,
    Polarity,
    TimeScope,
    Typicality,
)
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.interpretation import (
    DialogueAct,
    EpisodeSignal,
    TurnInsufficiencyCode,
)
from app.interview_vnext.domain.question_frame import (
    QuestionDimension,
    QuestionFrame,
    QuestionFrameStatus,
    QuestionMode,
    QuestionProposition,
    QuestionSlotKind,
    QuestionSourceKind,
    QuestionSourceRef,
    build_choice_option,
    build_choice_target,
    build_proposition_target,
    build_question_frame_definition,
    build_slot_target,
)
from app.interview_vnext.domain.support import (
    LiteralEmployeeSpanSupport,
    QuoteMatch,
    QuoteSpan,
)
from app.interview_vnext.domain.transcript import TranscriptRole, TranscriptTurn
from app.interview_vnext.domain.turn_identity import (
    contextual_evidence_id,
    derive_binding_ref,
    derive_proposal_ref,
    literal_evidence_id,
)
from app.interview_vnext.llm.context import (
    INJECTION_BOUNDARY,
    TURN_INTERPRET_CONTEXT_POLICY_V2,
    TURN_INTERPRET_SECTION_ORDER,
    ContextEvidenceItem,
    ContextQuestionFrame,
    ContextSourceRef,
    ContextSourceType,
    QuestionFrameLimitation,
    TurnInterpretContextPacket,
)
from app.interview_vnext.llm.turn_interpret import (
    AnswerBindingKind,
    AnswerBindingProposal,
    AnswerBindingResolution,
    CorrectionProposal,
    EmergentTopicProposal,
    EvidenceQualifiersProposal,
    FrequencyQualifierProposal,
    ObservationProposal,
    TurnInterpretOutput,
    TurnInterpretRejectCode,
)


NOW = datetime(2026, 7, 22, 10, 0, tzinfo=UTC)
STATE_HASH = "sha256:" + "1" * 64
DEFINITION_HASH = "sha256:" + "2" * 64
SOURCE_HASH = "sha256:" + "3" * 64
OPERATION_ID = UUID("12345678-1234-5678-9234-567812345678")


def uid(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"caliburn-turn-interpret-v2:{name}")


def transcript_turn(
    *, sequence: int, role: TranscriptRole, text: str, previous_turn_id: UUID | None
) -> TranscriptTurn:
    return TranscriptTurn(
        turn_id=uid(f"turn-{sequence}-{role.value}-{text}"),
        session_id=uid("session"),
        client_turn_id=f"client-{sequence}",
        sequence=sequence,
        role=role,
        text=text,
        previous_turn_id=previous_turn_id,
        occurred_at=NOW,
        received_at=NOW,
    )


def question_source() -> tuple[QuestionSourceRef, ...]:
    return (
        QuestionSourceRef(
            source_kind=QuestionSourceKind.CONSULTANT_HYPOTHESIS,
            source_ref="consultant-hypothesis-1",
            source_hash=SOURCE_HASH,
        ),
    )


def proposition_target():
    proposition = QuestionProposition(
        subject=EvidenceSubject.EMPLOYEE,
        kind=EvidenceKind.ACTION,
        claim="核對訂單",
        qualifiers=EvidenceQualifiers(),
        source_refs=question_source(),
    )
    return build_proposition_target(
        target_ordinal=1,
        proposition=proposition,
        introduced_dimensions=(QuestionDimension.POLARITY,),
    )


def slot_target(slot_kind: QuestionSlotKind):
    return build_slot_target(
        target_ordinal=1,
        slot_kind=slot_kind,
        subject=EvidenceSubject.EMPLOYEE,
        evidence_kind=(
            EvidenceKind.FREQUENCY
            if slot_kind == QuestionSlotKind.FREQUENCY
            else EvidenceKind.ACTION
        ),
        base_claim="核對訂單",
        claim_template="核對訂單：{value}",
        base_qualifiers=EvidenceQualifiers(),
        source_refs=question_source(),
    )


def choice_target():
    options = tuple(
        build_choice_option(
            option_ordinal=index,
            label=label,
            proposition=QuestionProposition(
                subject=EvidenceSubject.EMPLOYEE,
                kind=EvidenceKind.OUTPUT,
                claim=claim,
                qualifiers=EvidenceQualifiers(),
                source_refs=question_source(),
            ),
        )
        for index, (label, claim) in enumerate(
            (("日報", "產出日報"), ("月報", "產出月報")), 1
        )
    )
    return build_choice_target(
        target_ordinal=1,
        multi_select=True,
        introduced_dimension=QuestionDimension.OUTPUT,
        options=options,
    )


def target_evidence(*, status: EvidenceStatus = EvidenceStatus.ACTIVE) -> Evidence:
    source_turn_id = uid("prior-employee-turn")
    return Evidence(
        evidence_id=uid("target-evidence"),
        session_id=uid("session"),
        subject=EvidenceSubject.EMPLOYEE,
        kind=EvidenceKind.FREQUENCY,
        claim="每週核對訂單",
        support=LiteralEmployeeSpanSupport(
            employee_turn_id=source_turn_id,
            quote="每週核對訂單",
            span=QuoteSpan(start=0, end=6),
            quote_match=QuoteMatch.EXACT,
        ),
        qualifiers=EvidenceQualifiers(
            frequency=FrequencyQualifier(unit=FrequencyUnit.PER_WEEK, verbatim="每週")
        ),
        status=status,
        superseded_by=(uid("replacement") if status == EvidenceStatus.SUPERSEDED else None),
        extractor_operation_id=uid("prior-operation"),
    )


def context(
    text: str,
    *,
    target=None,
    limitation: QuestionFrameLimitation | None = None,
    correction_candidate: Evidence | None = None,
) -> TurnInterpretContextPacket:
    question_text = "請說明或確認這項工作。"
    consultant = transcript_turn(
        sequence=1,
        role=TranscriptRole.CONSULTANT,
        text=question_text,
        previous_turn_id=None,
    )
    employee = transcript_turn(
        sequence=2,
        role=TranscriptRole.EMPLOYEE,
        text=text,
        previous_turn_id=consultant.turn_id,
    )
    context_frame = None
    if target is not None:
        if target.target_kind.value == "proposition":
            mode = QuestionMode.ATOMIC_CONFIRMATION
        elif target.target_kind.value == "slot":
            mode = QuestionMode.SLOT_REQUEST
        else:
            mode = QuestionMode.CHOICE
        frame = QuestionFrame(
            question_frame_id=uid(f"frame-{target.target_kind.value}"),
            session_id=uid("session"),
            consultant_turn_id=consultant.turn_id,
            definition=build_question_frame_definition(
                mode=mode,
                question_text=question_text,
                targets=(target,),
            ),
            status=QuestionFrameStatus.ACTIVE,
            opened_state_version=1,
            opened_at=NOW,
            answer_turn_id=employee.turn_id,
        )
        context_frame = ContextQuestionFrame(
            source=ContextSourceRef(
                source_type=ContextSourceType.QUESTION_FRAME,
                source_id=str(frame.question_frame_id),
                state_hash=STATE_HASH,
                content_hash=canonical_hash(frame),
            ),
            frame=frame,
        )
    candidate_items = ()
    if correction_candidate is not None:
        candidate_items = (
            ContextEvidenceItem(
                source=ContextSourceRef(
                    source_type=ContextSourceType.EVIDENCE,
                    source_id=str(correction_candidate.evidence_id),
                    state_hash=STATE_HASH,
                    content_hash=canonical_hash(correction_candidate),
                ),
                turn_sequence=1,
                evidence=correction_candidate,
            ),
        )
    return TurnInterpretContextPacket(
        operation_name="turn.interpret",
        operation_definition_hash=DEFINITION_HASH,
        context_policy_name=TURN_INTERPRET_CONTEXT_POLICY_V2.name,
        context_policy_version=TURN_INTERPRET_CONTEXT_POLICY_V2.version,
        context_policy_hash=TURN_INTERPRET_CONTEXT_POLICY_V2.policy_hash,
        session_id=uid("session"),
        turn_id=employee.turn_id,
        operation_id=OPERATION_ID,
        state_hash=STATE_HASH,
        state_version=3,
        reference_snapshot_hash=None,
        section_order=TURN_INTERPRET_SECTION_ORDER,
        injection_boundary=INJECTION_BOUNDARY,
        preceding_consultant_turn=consultant,
        current_employee_turn=employee,
        question_frame=context_frame,
        question_frame_limitation=(
            None
            if context_frame is not None
            else limitation or QuestionFrameLimitation.MISSING
        ),
        active_episode=None,
        correction_candidates=candidate_items,
    )


def qualifier_proposal(**updates) -> EvidenceQualifiersProposal:
    values = dict(
        time_scope=TimeScope.UNKNOWN,
        time_scope_support=None,
        typicality=Typicality.UNKNOWN,
        typicality_support=None,
        polarity=Polarity.AFFIRMED,
        polarity_support=None,
        frequency=FrequencyQualifierProposal(
            value=None,
            unit=FrequencyUnit.UNKNOWN,
            verbatim=None,
        ),
        importance=Importance.NOT_STATED,
        importance_support=None,
        ownership=Ownership.UNKNOWN,
        ownership_support=None,
    )
    values.update(updates)
    return EvidenceQualifiersProposal(**values)


def observation(**updates) -> ObservationProposal:
    values = dict(
        subject=EvidenceSubject.EMPLOYEE,
        kind=EvidenceKind.ACTION,
        claim="核對訂單",
        quote="核對訂單",
        quote_occurrence=1,
        qualifiers=qualifier_proposal(),
        correction=CorrectionProposal(),
        insufficiency_codes=(),
    )
    values.update(updates)
    return ObservationProposal(**values)


def binding(**updates) -> AnswerBindingProposal:
    values = dict(
        target_ordinal=1,
        binding_kind=AnswerBindingKind.PROPOSITION,
        resolution=AnswerBindingResolution.AFFIRMED,
        answer_quote="是",
        answer_quote_occurrence=1,
        value_text=None,
        selected_choice_ordinals=(),
        insufficiency_codes=(),
    )
    values.update(updates)
    return AnswerBindingProposal(**values)


def output(
    *,
    observations: tuple[ObservationProposal, ...] = (),
    bindings: tuple[AnswerBindingProposal, ...] = (),
    topics: tuple[EmergentTopicProposal, ...] = (),
    dialogue_act: DialogueAct = DialogueAct.STANDALONE_ANSWER,
    insufficiency_codes: tuple[TurnInsufficiencyCode, ...] = (),
) -> TurnInterpretOutput:
    return TurnInterpretOutput(
        schema_version="turn_interpret_output.v2",
        dialogue_act=dialogue_act,
        episode_signal=EpisodeSignal.CONTINUE,
        literal_observations=observations,
        answer_bindings=bindings,
        emergent_topics=topics,
        turn_insufficiency_codes=insufficiency_codes,
    )


def verify(result: TurnInterpretOutput, packet: TurnInterpretContextPacket):
    return verify_turn_interpret_output(
        output=result,
        context=packet,
        operation_id=OPERATION_ID,
    )


def test_projection_is_provider_minimal_and_omits_application_frame_limitation() -> None:
    packet = context("是", target=proposition_target())
    projected = turn_interpret_input_from_context(packet)
    assert projected.current_turn.text == "是"
    assert projected.question_frame is not None
    assert not hasattr(projected, "question_frame_limitation")
    assert not hasattr(projected.question_frame, "question_frame_id")
    assert not hasattr(projected.question_frame.targets[0], "target_hash")


def test_literal_identity_quote_occurrence_and_unicode_span_are_deterministic() -> None:
    text = "重複✅，Cafe\u0301，再說一次重複✅。"
    proposal = observation(claim="重複確認", quote="重複✅", quote_occurrence=2)
    first = verify(output(observations=(proposal,)), context(text))
    second = verify(output(observations=(proposal,)), context(text))
    decision = first.decisions[0]
    expected_start = text.find("重複✅", text.find("重複✅") + 1)
    assert decision.accepted
    assert decision.proposal_ref == derive_proposal_ref(1) == "p0001"
    assert decision.candidate_evidence_id == literal_evidence_id(OPERATION_ID, 1)
    assert decision.computed_span == QuoteSpan(
        start=expected_start, end=expected_start + len("重複✅")
    )
    assert first == second


@pytest.mark.parametrize(
    ("text", "qualifiers"),
    [
        (
            "以前核對訂單",
            qualifier_proposal(
                time_scope=TimeScope.CURRENT, time_scope_support="以前"
            ),
        ),
        (
            "我不負責核對訂單",
            qualifier_proposal(
                ownership=Ownership.OWNER, ownership_support="我不負責"
            ),
        ),
        (
            "協助性核對訂單",
            qualifier_proposal(
                importance=Importance.EXPLICIT_CORE,
                importance_support="協助性",
            ),
        ),
        (
            "目前核對訂單",
            qualifier_proposal(
                time_scope=TimeScope.UNKNOWN, time_scope_support="目前"
            ),
        ),
    ],
)
def test_false_specific_qualifiers_are_dropped(text, qualifiers) -> None:
    report = verify(
        output(
            observations=(
                observation(claim=text, quote=text, qualifiers=qualifiers),
            )
        ),
        context(text),
    )
    assert not report.decisions[0].accepted
    assert TurnInterpretRejectCode.FALSE_SPECIFIC_QUALIFIER in report.decisions[0].reason_codes


@pytest.mark.parametrize(
    ("text", "qualifiers", "expected_time"),
    [
        (
            "每週核對訂單",
            qualifier_proposal(
                frequency=FrequencyQualifierProposal(
                    value=None, unit=FrequencyUnit.PER_WEEK, verbatim="每週"
                )
            ),
            TimeScope.UNKNOWN,
        ),
        (
            "以前每週核對訂單",
            qualifier_proposal(
                time_scope=TimeScope.PAST,
                time_scope_support="以前",
                frequency=FrequencyQualifierProposal(
                    value=None, unit=FrequencyUnit.PER_WEEK, verbatim="每週"
                ),
            ),
            TimeScope.PAST,
        ),
    ],
)
def test_frequency_does_not_invent_current_time_scope(text, qualifiers, expected_time) -> None:
    report = verify(
        output(observations=(observation(claim=text, quote=text, qualifiers=qualifiers),)),
        context(text),
    )
    decision = report.decisions[0]
    assert decision.accepted
    assert decision.evidence.qualifiers.time_scope == expected_time
    assert decision.evidence.qualifiers.frequency.unit == FrequencyUnit.PER_WEEK


def test_literal_duplicate_fingerprint_drops_every_duplicate_without_renumbering() -> None:
    proposal = observation()
    report = verify(
        output(observations=(proposal, proposal)),
        context("核對訂單"),
    )
    assert report.accepted_count == 0
    assert tuple(item.proposal_ref for item in report.decisions) == ("p0001", "p0002")
    assert tuple(item.candidate_evidence_id for item in report.decisions) == (
        literal_evidence_id(OPERATION_ID, 1),
        literal_evidence_id(OPERATION_ID, 2),
    )
    assert all(
        TurnInterpretRejectCode.DUPLICATE_OBSERVATION in item.reason_codes
        for item in report.decisions
    )


def test_invalid_literal_does_not_roll_back_independent_valid_neighbour() -> None:
    valid = observation()
    invalid = observation(claim="不存在", quote="不存在")
    report = verify(
        output(observations=(valid, invalid)),
        context("核對訂單"),
    )
    assert report.accepted_count == 1
    assert report.dropped_count == 1
    assert report.decisions[0].accepted
    assert report.decisions[1].reason_codes == (
        TurnInterpretRejectCode.QUOTE_NOT_FOUND,
    )


def test_correction_ordinal_materializes_active_target_and_unknown_adds_system_code() -> None:
    target = target_evidence()
    known = observation(
        kind=EvidenceKind.CORRECTION,
        claim="更正為每天核對訂單",
        quote="更正為每天核對訂單",
        correction=CorrectionProposal(target_candidate_ordinals=(1,)),
    )
    known_report = verify(
        output(observations=(known,), dialogue_act=DialogueAct.CORRECTION),
        context("更正為每天核對訂單", correction_candidate=target),
    )
    assert known_report.decisions[0].accepted
    assert known_report.decisions[0].evidence.supersedes == (target.evidence_id,)

    unknown = observation(
        kind=EvidenceKind.CORRECTION,
        claim="要更正但不確定是哪一筆",
        quote="要更正但不確定是哪一筆",
        correction=CorrectionProposal(target_unknown=True),
    )
    unknown_report = verify(
        output(observations=(unknown,), dialogue_act=DialogueAct.CORRECTION),
        context("要更正但不確定是哪一筆"),
    )
    assert unknown_report.decisions[0].accepted
    assert unknown_report.system_insufficiency_codes == (
        TurnInsufficiencyCode.CORRECTION_TARGET_UNKNOWN,
    )


def test_inactive_and_out_of_range_correction_targets_fail_closed() -> None:
    inactive = target_evidence(status=EvidenceStatus.SUPERSEDED)
    proposal = observation(
        kind=EvidenceKind.CORRECTION,
        correction=CorrectionProposal(target_candidate_ordinals=(1,)),
    )
    inactive_report = verify(
        output(observations=(proposal,)),
        context("核對訂單", correction_candidate=inactive),
    )
    assert TurnInterpretRejectCode.INACTIVE_CORRECTION_TARGET in inactive_report.decisions[0].reason_codes

    foreign = proposal.model_copy(
        update={"correction": CorrectionProposal(target_candidate_ordinals=(2,))}
    )
    foreign_report = verify(
        output(observations=(foreign,)),
        context("核對訂單", correction_candidate=target_evidence()),
    )
    assert TurnInterpretRejectCode.FOREIGN_CORRECTION_TARGET in foreign_report.decisions[0].reason_codes


def test_frequency_slot_accepts_exact_count_and_rejects_hidden_second_count() -> None:
    target = slot_target(QuestionSlotKind.FREQUENCY)
    valid = binding(
        binding_kind=AnswerBindingKind.SLOT,
        resolution=AnswerBindingResolution.SUPPLIED,
        answer_quote="每月2次",
        value_text="每月2次",
    )
    valid_report = verify(output(bindings=(valid,)), context("每月2次", target=target))
    assert valid_report.binding_decisions[0].accepted
    assert valid_report.binding_decisions[0].materialized_evidence[0].qualifiers.frequency == FrequencyQualifier(
        value=2, unit=FrequencyUnit.PER_MONTH, verbatim="每月"
    )

    conflict = valid.model_copy(update={"answer_quote": "每月2次或3次"})
    report = verify(
        output(bindings=(conflict,)),
        context("每月2次或3次", target=target),
    )
    assert report.binding_decisions[0].reason_codes == (
        TurnInterpretRejectCode.BINDING_VALUE_NOT_SUPPORTED,
    )
    assert TurnInsufficiencyCode.AMBIGUOUS_FREQUENCY in report.system_insufficiency_codes


@pytest.mark.parametrize("value", ["每兩週一次", "每月2-3次", "不定期2次"])
def test_frequency_slot_fails_closed_on_unsupported_interval_range_or_irregular_count(value) -> None:
    proposal = binding(
        binding_kind=AnswerBindingKind.SLOT,
        resolution=AnswerBindingResolution.SUPPLIED,
        answer_quote=value,
        value_text=value,
    )
    report = verify(
        output(bindings=(proposal,)),
        context(value, target=slot_target(QuestionSlotKind.FREQUENCY)),
    )
    assert report.binding_decisions[0].reason_codes == (
        TurnInterpretRejectCode.BINDING_VALUE_NOT_SUPPORTED,
    )


def test_ownership_slot_accepts_bare_pronoun_but_scans_full_answer_for_conflict() -> None:
    target = slot_target(QuestionSlotKind.OWNERSHIP)
    bare = binding(
        binding_kind=AnswerBindingKind.SLOT,
        resolution=AnswerBindingResolution.SUPPLIED,
        answer_quote="我自己",
        value_text="我自己",
    )
    accepted = verify(output(bindings=(bare,)), context("我自己", target=target))
    assert accepted.binding_decisions[0].accepted
    assert accepted.binding_decisions[0].materialized_evidence[0].qualifiers.ownership == Ownership.OWNER

    conflict = bare.model_copy(
        update={"answer_quote": "我自己，但我協助同事"}
    )
    rejected = verify(
        output(bindings=(conflict,)),
        context("我自己，但我協助同事", target=target),
    )
    assert rejected.binding_decisions[0].reason_codes == (
        TurnInterpretRejectCode.BINDING_VALUE_NOT_SUPPORTED,
    )
    assert TurnInsufficiencyCode.AMBIGUOUS_OWNERSHIP in rejected.system_insufficiency_codes


@pytest.mark.parametrize(
    ("slot_kind", "answer", "field", "expected"),
    [
        (
            QuestionSlotKind.IMPORTANCE,
            "這是核心工作",
            "importance",
            Importance.EXPLICIT_CORE,
        ),
        (
            QuestionSlotKind.TIME_SCOPE,
            "目前負責",
            "time_scope",
            TimeScope.CURRENT,
        ),
        (
            QuestionSlotKind.TYPICALITY,
            "通常會做",
            "typicality",
            Typicality.TYPICAL,
        ),
    ],
)
def test_other_typed_slots_materialize_only_sealed_exact_markers(
    slot_kind, answer, field, expected
) -> None:
    proposal = binding(
        binding_kind=AnswerBindingKind.SLOT,
        resolution=AnswerBindingResolution.SUPPLIED,
        answer_quote=answer,
        value_text=answer,
    )
    report = verify(
        output(bindings=(proposal,)),
        context(answer, target=slot_target(slot_kind)),
    )
    assert report.binding_decisions[0].accepted
    qualifiers = report.binding_decisions[0].materialized_evidence[0].qualifiers
    assert getattr(qualifiers, field) == expected


def test_proposition_denial_materializes_contextual_denial_without_literal_claim() -> None:
    proposal = binding(
        resolution=AnswerBindingResolution.DENIED,
        answer_quote="不是",
    )
    report = verify(
        output(bindings=(proposal,), dialogue_act=DialogueAct.DENY),
        context("不是", target=proposition_target()),
    )
    evidence = report.binding_decisions[0].materialized_evidence[0]
    assert evidence.claim == "核對訂單"
    assert evidence.qualifiers.polarity == Polarity.DENIED
    assert evidence.support.answer_quote == "不是"


def test_free_text_slot_substitutes_exact_value_without_inventing_qualifiers() -> None:
    target = slot_target(QuestionSlotKind.TOOL)
    proposal = binding(
        binding_kind=AnswerBindingKind.SLOT,
        resolution=AnswerBindingResolution.SUPPLIED,
        answer_quote="使用ERP系統",
        value_text="ERP系統",
    )
    report = verify(
        output(bindings=(proposal,)),
        context("使用ERP系統", target=target),
    )
    evidence = report.binding_decisions[0].materialized_evidence[0]
    assert evidence.claim == "核對訂單：ERP系統"
    assert evidence.qualifiers == target.base_qualifiers


def test_choice_materialization_uses_option_order_and_invalid_selection_is_ambiguous() -> None:
    target = choice_target()
    selected = binding(
        binding_kind=AnswerBindingKind.CHOICE,
        resolution=AnswerBindingResolution.SELECTED,
        answer_quote="日報和月報",
        selected_choice_ordinals=(1, 2),
    )
    report = verify(
        output(bindings=(selected,), dialogue_act=DialogueAct.CHOOSE),
        context("日報和月報", target=target),
    )
    decision = report.binding_decisions[0]
    assert decision.accepted
    assert decision.binding_ref == derive_binding_ref(1)
    assert decision.candidate_evidence_ids == (
        contextual_evidence_id(OPERATION_ID, 1, 1),
        contextual_evidence_id(OPERATION_ID, 1, 2),
    )
    assert tuple(item.claim for item in decision.materialized_evidence) == (
        "產出日報",
        "產出月報",
    )

    invalid = selected.model_copy(update={"selected_choice_ordinals": (3,)})
    invalid_report = verify(
        output(bindings=(invalid,), dialogue_act=DialogueAct.CHOOSE),
        context("日報和月報", target=target),
    )
    assert TurnInterpretRejectCode.CHOICE_SELECTION_INVALID in invalid_report.binding_decisions[0].reason_codes
    assert TurnInsufficiencyCode.CHOICE_SELECTION_AMBIGUOUS in invalid_report.system_insufficiency_codes


def test_binding_duplicate_fingerprint_and_resolved_target_claims_drop_all() -> None:
    target = proposition_target()
    exact = binding()
    duplicate_report = verify(
        output(bindings=(exact, exact)),
        context("是", target=target),
    )
    assert duplicate_report.accepted_count == 0
    assert tuple(item.binding_ref for item in duplicate_report.binding_decisions) == (
        "b0001",
        "b0002",
    )
    assert all(
        TurnInterpretRejectCode.DUPLICATE_BINDING_TARGET in item.reason_codes
        for item in duplicate_report.binding_decisions
    )

    first = exact
    second = exact.model_copy(update={"answer_quote": "確定", "answer_quote_occurrence": 1})
    target_report = verify(
        output(bindings=(first, second)),
        context("是，確定", target=target),
    )
    assert all(
        TurnInterpretRejectCode.DUPLICATE_BINDING_TARGET in item.reason_codes
        for item in target_report.binding_decisions
    )


def test_ambiguous_binding_accepts_zero_evidence_and_does_not_claim_resolved_target() -> None:
    ambiguous = binding(resolution=AnswerBindingResolution.AMBIGUOUS)
    resolved = binding(answer_quote="確定")
    report = verify(
        output(bindings=(ambiguous, resolved)),
        context("是，確定", target=proposition_target()),
    )
    assert report.binding_decisions[0].accepted
    assert report.binding_decisions[0].candidate_evidence_ids == ()
    assert report.binding_decisions[0].materialized_evidence == ()
    assert report.binding_decisions[1].accepted
    assert TurnInsufficiencyCode.ANSWER_BINDING_AMBIGUOUS in report.system_insufficiency_codes


@pytest.mark.parametrize(
    ("limitation", "reason", "insufficiency"),
    [
        (
            QuestionFrameLimitation.MISSING,
            TurnInterpretRejectCode.BINDING_WITHOUT_QUESTION_FRAME,
            TurnInsufficiencyCode.QUESTION_FRAME_MISSING,
        ),
        (
            QuestionFrameLimitation.NOT_IMMEDIATE,
            TurnInterpretRejectCode.QUESTION_FRAME_NOT_ELIGIBLE,
            TurnInsufficiencyCode.QUESTION_FRAME_NOT_IMMEDIATE,
        ),
        (
            QuestionFrameLimitation.TEXT_HASH_MISMATCH,
            TurnInterpretRejectCode.QUESTION_FRAME_HASH_MISMATCH,
            TurnInsufficiencyCode.QUESTION_FRAME_STALE,
        ),
    ],
)
def test_frame_limitation_maps_to_typed_reason_and_system_insufficiency(
    limitation, reason, insufficiency
) -> None:
    literal = observation(claim="新增工作", quote="新增工作")
    report = verify(
        output(observations=(literal,), bindings=(binding(),)),
        context("是，新增工作", limitation=limitation),
    )
    assert report.decisions[0].accepted
    assert report.binding_decisions[0].reason_codes == (reason,)
    assert insufficiency in report.system_insufficiency_codes


def test_model_insufficiency_scope_conflict_drops_only_its_observation() -> None:
    proposal = observation(
        qualifiers=qualifier_proposal(
            frequency=FrequencyQualifierProposal(
                value=None, unit=FrequencyUnit.PER_WEEK, verbatim="每週"
            )
        ),
        claim="每週核對訂單",
        quote="每週核對訂單",
        insufficiency_codes=(TurnInsufficiencyCode.AMBIGUOUS_FREQUENCY,),
    )
    report = verify(
        output(
            observations=(proposal,),
            insufficiency_codes=(TurnInsufficiencyCode.AMBIGUOUS_FREQUENCY,),
        ),
        context("每週核對訂單"),
    )
    assert report.decisions[0].reason_codes == (
        TurnInterpretRejectCode.INSUFFICIENCY_INCOHERENT,
    )
    assert report.model_insufficiency_codes == (
        TurnInsufficiencyCode.AMBIGUOUS_FREQUENCY,
    )


def test_emergent_topics_are_verified_independently() -> None:
    report = verify(
        output(
            topics=(
                EmergentTopicProposal(topic="報表", quote="產出報表", quote_occurrence=1),
                EmergentTopicProposal(topic="臆測", quote="不存在", quote_occurrence=1),
            )
        ),
        context("另外會產出報表"),
    )
    assert report.emergent_topic_decisions[0].accepted
    assert report.emergent_topic_decisions[1].reason_codes == (
        TurnInterpretRejectCode.QUOTE_NOT_FOUND,
    )


def test_accepted_evidence_scope_and_report_policy_identity_are_sealed() -> None:
    report = verify(
        output(observations=(observation(),)),
        context("核對訂單"),
    )
    evidence = accepted_evidence(
        report=report,
        session_id=uid("session"),
        turn_id=report.turn_id,
        operation_id=OPERATION_ID,
    )
    assert len(evidence) == 1
    assert report.verifier_policy_version == "2.0.0"
    with pytest.raises(ValueError, match="scope mismatch"):
        accepted_evidence(
            report=report,
            session_id=uuid4(),
            turn_id=report.turn_id,
            operation_id=OPERATION_ID,
        )
    with pytest.raises(ValidationError, match="unknown verifier policy"):
        type(report).model_validate(
            {
                **report.model_dump(),
                "verifier_policy_hash": "sha256:" + "0" * 64,
            }
        )


def test_provider_output_rejects_forged_domain_identity_fields() -> None:
    forged = observation().model_dump(mode="json")
    forged["evidence_id"] = str(uuid4())
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ObservationProposal.model_validate(forged)


def test_operation_identity_mismatch_is_rejected_before_semantic_work() -> None:
    with pytest.raises(ValueError, match="operation_id"):
        verify_turn_interpret_output(
            output=output(observations=(observation(),)),
            context=context("核對訂單"),
            operation_id=uuid4(),
        )
