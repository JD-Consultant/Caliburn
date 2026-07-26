"""Pure mapping and semantic verification for the turn.interpret operation.

Two independent materialization paths meet here. A *literal observation* quotes
the claim itself out of the current employee turn. An *answer binding* resolves a
QuestionFrame target from a short answer (「是」/「每週」) — the employee never
stated the claim verbatim, so the evidence records the answer span and the frame
it answered instead of pretending the claim was quoted (ADR 0037 §4).

Nothing is repaired: a proposal that fails a gate is dropped with a stable reason
and its neighbours are unaffected (plan §11.1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import UUID

from pydantic import ValidationError

from app.interview_vnext.domain.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceQualifiers,
    EvidenceStatus,
    FrequencyQualifier,
    FrequencyUnit,
    Importance,
    Ownership,
    Polarity,
    TimeScope,
    Typicality,
)
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.question_frame import (
    ChoiceQuestionTarget,
    PropositionQuestionTarget,
    QuestionSlotKind,
    QuestionTargetKind,
    SlotQuestionTarget,
)
from app.interview_vnext.domain.support import (
    ContextualAnswerSupport,
    ContextualBindingKind,
    ContextualResolution,
    LiteralEmployeeSpanSupport,
    QuoteMatch,
    QuoteSpan,
)
from app.interview_vnext.domain.transcript import TranscriptRole
from app.interview_vnext.domain.interpretation import TurnInsufficiencyCode
from app.interview_vnext.domain.turn_identity import (
    contextual_evidence_id,
    derive_binding_ref,
    derive_proposal_ref,
    literal_evidence_id,
)
from app.interview_vnext.llm.context import (
    INJECTION_BOUNDARY,
    ContextEvidenceItem,
    QuestionFrameLimitation,
    TurnInterpretContextPacket,
)
from app.interview_vnext.llm.turn_interpret import (
    AnswerBindingKind,
    AnswerBindingProposal,
    AnswerBindingResolution,
    AnswerBindingVerification,
    EmergentTopicVerification,
    ObservationProposal,
    ObservationVerification,
    TurnInputChoiceOption,
    TurnInputContradiction,
    TurnInputEpisode,
    TurnInputEvidence,
    TurnInputQuestionFrame,
    TurnInputQuestionTarget,
    TurnInputTurn,
    TurnInterpretInput,
    TurnInterpretOutput,
    TurnInterpretRejectCode,
    TurnInterpretVerificationReport,
    TURN_INTERPRET_VERIFIER_POLICY_V2,
    canonical_reject_codes,
    compile_marker,
)


_POLICY = TURN_INTERPRET_VERIFIER_POLICY_V2
_NUMBER = re.compile(_POLICY.number_pattern)
_NON_ATOMIC = re.compile(_POLICY.non_atomic_pattern, re.IGNORECASE)
_REFERENCE_MARKERS = _POLICY.reference_markers


def _compiled_matchers(
    mapping: dict[object, tuple[str, ...]],
) -> dict[object, tuple[re.Pattern[str], ...]]:
    """Compile a sealed marker map for matching.

    The pattern strings live *only* in the sealed policy; this compiles the
    single authority for use, it does not keep a second copy of the data
    (amendment §7.3).
    """

    return {
        value: tuple(compile_marker(pattern) for pattern in patterns)
        for value, patterns in mapping.items()
    }


_FREQUENCY_MATCHERS = _compiled_matchers(_POLICY.frequency_markers)
_OWNERSHIP_MATCHERS = _compiled_matchers(_POLICY.ownership_markers)
_IMPORTANCE_MATCHERS = _compiled_matchers(_POLICY.importance_markers)
_TIME_SCOPE_MATCHERS = _compiled_matchers(_POLICY.time_scope_markers)
_TYPICALITY_MATCHERS = _compiled_matchers(_POLICY.typicality_markers)
_POLARITY_MATCHERS = _compiled_matchers(_POLICY.polarity_markers)

_CJK_COUNTS = {
    "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}
_ASCII_COUNT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:次|times)", re.IGNORECASE)
_CJK_COUNT = re.compile(r"([一二兩三四五六七八九十])次")
_COUNT_RANGE = re.compile(
    r"(?:\d+(?:\.\d+)?|[一二兩三四五六七八九十])\s*"
    r"(?:-|–|—|~|～|至|到|或)\s*"
    r"(?:\d+(?:\.\d+)?|[一二兩三四五六七八九十])\s*(?:次|times)",
    re.IGNORECASE,
)

_TYPED_SLOT_KINDS = frozenset(
    {
        QuestionSlotKind.FREQUENCY,
        QuestionSlotKind.OWNERSHIP,
        QuestionSlotKind.IMPORTANCE,
        QuestionSlotKind.TIME_SCOPE,
        QuestionSlotKind.TYPICALITY,
    }
)


@dataclass(frozen=True)
class TurnInterpretProjection:
    """The provider-facing input plus the ordinal→domain map it hides.

    The map never leaves the application: it lives in memory and in the durable
    input artifact, never in the provider request (plan §10.1).
    """

    input: TurnInterpretInput
    correction_candidate_ids: tuple[UUID, ...]
    recent_evidence_ids: tuple[UUID, ...]


def _input_turn(turn) -> TurnInputTurn:
    return TurnInputTurn(sequence=turn.sequence, locale=turn.locale, text=turn.text)


def _input_evidence(ordinal: int, item: ContextEvidenceItem) -> TurnInputEvidence:
    evidence = item.evidence
    support = evidence.support
    if isinstance(support, LiteralEmployeeSpanSupport):
        quote = support.quote
    else:
        # The short answer, not a verbatim statement of the claim.
        quote = support.answer_quote
    return TurnInputEvidence(
        ordinal=ordinal,
        subject=evidence.subject,
        kind=evidence.kind,
        claim=evidence.claim,
        support_kind=support.support_kind,
        quote=quote,
        qualifiers=evidence.qualifiers,
    )


def _input_question_target(target) -> TurnInputQuestionTarget:
    if isinstance(target, PropositionQuestionTarget):
        return TurnInputQuestionTarget(
            target_ordinal=target.target_ordinal,
            target_kind=QuestionTargetKind.PROPOSITION,
            claim=target.proposition.claim,
        )
    if isinstance(target, SlotQuestionTarget):
        return TurnInputQuestionTarget(
            target_ordinal=target.target_ordinal,
            target_kind=QuestionTargetKind.SLOT,
            slot_kind=target.slot_kind,
            claim_template=target.claim_template,
        )
    return TurnInputQuestionTarget(
        target_ordinal=target.target_ordinal,
        target_kind=QuestionTargetKind.CHOICE,
        options=tuple(
            TurnInputChoiceOption(
                option_ordinal=option.option_ordinal, label=option.label
            )
            for option in target.options
        ),
    )


def turn_interpret_projection(
    context: TurnInterpretContextPacket,
) -> TurnInterpretProjection:
    """Project only the fields visible to the turn interpreter."""

    context = TurnInterpretContextPacket.model_validate(context.model_dump())
    frame = None
    if context.question_frame is not None and context.preceding_consultant_turn is not None:
        definition = context.question_frame.frame.definition
        frame = TurnInputQuestionFrame(
            mode=definition.mode,
            question_text=context.preceding_consultant_turn.text,
            targets=tuple(_input_question_target(item) for item in definition.targets),
        )
    payload = TurnInterpretInput(
        input_boundary=INJECTION_BOUNDARY,
        preceding_question=(
            _input_turn(context.preceding_consultant_turn)
            if context.preceding_consultant_turn is not None
            else None
        ),
        current_turn=_input_turn(context.current_employee_turn),
        question_frame=frame,
        active_episode=(
            TurnInputEpisode(
                target=context.active_episode.target,
                status=context.active_episode.status,
            )
            if context.active_episode is not None
            else None
        ),
        contradictions=tuple(
            TurnInputContradiction(
                contradiction_ordinal=ordinal,
                status=item.gap.status,
                question_goal=item.gap.question_goal,
            )
            for ordinal, item in enumerate(context.contradictions, 1)
        ),
        correction_candidates=tuple(
            _input_evidence(ordinal, item)
            for ordinal, item in enumerate(context.correction_candidates, 1)
        ),
        recent_active_evidence=tuple(
            _input_evidence(ordinal, item)
            for ordinal, item in enumerate(context.recent_active_evidence, 1)
        ),
    )
    return TurnInterpretProjection(
        input=payload,
        correction_candidate_ids=tuple(
            item.evidence.evidence_id for item in context.correction_candidates
        ),
        recent_evidence_ids=tuple(
            item.evidence.evidence_id for item in context.recent_active_evidence
        ),
    )


def turn_interpret_input_from_context(
    context: TurnInterpretContextPacket,
) -> TurnInterpretInput:
    return turn_interpret_projection(context).input


def _exact_span(text: str, quote: str, occurrence: int) -> tuple[QuoteSpan | None, str | None]:
    positions: list[int] = []
    start = 0
    while True:
        found = text.find(quote, start)
        if found < 0:
            break
        positions.append(found)
        start = found + 1
    if not positions:
        return None, "not_found"
    if occurrence < 1 or occurrence > len(positions):
        return None, "occurrence_out_of_range"
    start = positions[occurrence - 1]
    return QuoteSpan(start=start, end=start + len(quote)), None


def _qualifier_supports_are_in_quote(proposal: ObservationProposal) -> bool:
    supports = (
        proposal.qualifiers.time_scope_support,
        proposal.qualifiers.typicality_support,
        proposal.qualifiers.polarity_support,
        proposal.qualifiers.importance_support,
        proposal.qualifiers.ownership_support,
    )
    return all(item is None or item in proposal.quote for item in supports)


def _qualifiers(
    proposal: ObservationProposal,
) -> tuple[EvidenceQualifiers | None, bool]:
    source = proposal.qualifiers
    frequency = source.frequency
    value: Decimal | None = None
    if frequency.value is not None:
        if not frequency.value or frequency.value != frequency.value.strip():
            return None, False
        try:
            value = Decimal(frequency.value)
        except InvalidOperation:
            return None, False
        if not value.is_finite() or value < 0:
            return None, False
        if frequency.unit in {FrequencyUnit.UNKNOWN, FrequencyUnit.IRREGULAR}:
            return None, False
    if frequency.verbatim is not None:
        if not frequency.verbatim.strip() or frequency.verbatim not in proposal.quote:
            return None, False
    try:
        qualifiers = EvidenceQualifiers(
            time_scope=source.time_scope,
            typicality=source.typicality,
            polarity=source.polarity,
            frequency=FrequencyQualifier(
                value=value,
                unit=frequency.unit,
                verbatim=frequency.verbatim,
            ),
            importance=source.importance,
            ownership=source.ownership,
        )
    except ValidationError:
        return None, False
    return qualifiers, True


def _specific_marker_is_supported(
    *,
    value: object,
    markerless_value: object,
    support: str | None,
    matchers: dict[object, tuple[re.Pattern[str], ...]],
) -> bool:
    if value == markerless_value:
        return support is None
    if support is None:
        return False
    matched, coherent = _sole_marker(support, matchers)
    return coherent and matched == value


def _qualifier_specificity_is_supported(proposal: ObservationProposal) -> bool:
    """Require each specific qualifier to be proven by its own exact support."""

    source = proposal.qualifiers
    if not _specific_marker_is_supported(
        value=source.time_scope,
        markerless_value=TimeScope.UNKNOWN,
        support=source.time_scope_support,
        matchers=_TIME_SCOPE_MATCHERS,
    ):
        return False
    if not _specific_marker_is_supported(
        value=source.typicality,
        markerless_value=Typicality.UNKNOWN,
        support=source.typicality_support,
        matchers=_TYPICALITY_MATCHERS,
    ):
        return False
    if not _specific_marker_is_supported(
        value=source.importance,
        markerless_value=Importance.NOT_STATED,
        support=source.importance_support,
        matchers=_IMPORTANCE_MATCHERS,
    ):
        return False
    if not _specific_marker_is_supported(
        value=source.ownership,
        markerless_value=Ownership.UNKNOWN,
        support=source.ownership_support,
        matchers=_OWNERSHIP_MATCHERS,
    ):
        return False

    polarity_support = source.polarity_support
    if source.polarity == Polarity.AFFIRMED:
        if polarity_support is not None:
            matched, coherent = _sole_marker(polarity_support, _POLARITY_MATCHERS)
            if not coherent or matched is not None:
                return False
    elif not _specific_marker_is_supported(
        value=source.polarity,
        markerless_value=Polarity.AFFIRMED,
        support=polarity_support,
        matchers=_POLARITY_MATCHERS,
    ):
        return False

    frequency = source.frequency
    if frequency.unit == FrequencyUnit.UNKNOWN:
        return frequency.value is None and frequency.verbatim is None
    if frequency.verbatim is None:
        return False
    matched_unit, coherent = _sole_marker(frequency.verbatim, _FREQUENCY_MATCHERS)
    return coherent and matched_unit == frequency.unit


def _unsupported_quantification(proposal: ObservationProposal) -> bool:
    quote_numbers = set(_NUMBER.findall(proposal.quote))
    if not set(_NUMBER.findall(proposal.claim)) <= quote_numbers:
        return True
    value = proposal.qualifiers.frequency.value
    return value is not None and value not in proposal.quote


def _reference_leakage(claim: str) -> bool:
    folded = claim.casefold()
    return any(marker in folded for marker in _REFERENCE_MARKERS)


def _sole_marker(
    text: str, matchers: dict[object, tuple[re.Pattern[str], ...]]
) -> tuple[object | None, bool]:
    """Return the single canonical value the text supports.

    The second element is False when the text supports two mutually exclusive
    values — the model must not be able to hide a contradiction by quoting only
    part of the answer (amendment plan §10.5). Patterns come compiled from the
    sealed policy, so matching honours the ASCII-only case-fold rule (§7.3).
    """

    matched = {
        value
        for value, patterns in matchers.items()
        for pattern in patterns
        if pattern.search(text)
    }
    if len(matched) != 1:
        return None, not matched
    return next(iter(matched)), True


def _matched_marker_text(text: str, patterns: tuple[re.Pattern[str], ...]) -> str:
    """The exact substring a sealed marker matched — never a normalized form."""

    for pattern in patterns:
        found = pattern.search(text)
        if found is not None:
            return found.group(0)
    raise ValueError("no sealed marker matched the text")


def _parse_frequency(value_text: str, answer_quote: str) -> FrequencyQualifier | None:
    unit, coherent = _sole_marker(value_text, _FREQUENCY_MATCHERS)
    if unit is None or not coherent:
        return None
    answer_unit, answer_coherent = _sole_marker(answer_quote, _FREQUENCY_MATCHERS)
    if not answer_coherent or answer_unit != unit:
        return None
    verbatim = _matched_marker_text(value_text, _FREQUENCY_MATCHERS[unit])
    if _COUNT_RANGE.search(value_text) or _COUNT_RANGE.search(answer_quote):
        return None
    value_counts = tuple(Decimal(item) for item in _ASCII_COUNT.findall(value_text)) + tuple(
        Decimal(_CJK_COUNTS[item]) for item in _CJK_COUNT.findall(value_text)
    )
    answer_counts = tuple(Decimal(item) for item in _ASCII_COUNT.findall(answer_quote)) + tuple(
        Decimal(_CJK_COUNTS[item]) for item in _CJK_COUNT.findall(answer_quote)
    )
    if len(value_counts) > 1 or answer_counts != value_counts:
        return None
    count = value_counts[0] if value_counts else None
    if count is not None:
        # v1 fails closed rather than converting an interval into a rate.
        if count <= 0 or unit == FrequencyUnit.IRREGULAR:
            return None
    try:
        return FrequencyQualifier(value=count, unit=unit, verbatim=verbatim)
    except ValidationError:
        return None


def _slot_qualifiers(
    target: SlotQuestionTarget, value_text: str, answer_quote: str
) -> EvidenceQualifiers | None:
    base = target.base_qualifiers
    if target.slot_kind == QuestionSlotKind.FREQUENCY:
        frequency = _parse_frequency(value_text, answer_quote)
        if frequency is None:
            return None
        return base.model_copy(update={"frequency": frequency})
    typed = {
        QuestionSlotKind.OWNERSHIP: ("ownership", _OWNERSHIP_MATCHERS),
        QuestionSlotKind.IMPORTANCE: ("importance", _IMPORTANCE_MATCHERS),
        QuestionSlotKind.TIME_SCOPE: ("time_scope", _TIME_SCOPE_MATCHERS),
        QuestionSlotKind.TYPICALITY: ("typicality", _TYPICALITY_MATCHERS),
    }
    if target.slot_kind in typed:
        field, matchers = typed[target.slot_kind]
        bare_owner = (
            target.slot_kind == QuestionSlotKind.OWNERSHIP
            and value_text in {"我", "我自己"}
        )
        value, coherent = (
            (Ownership.OWNER, True)
            if bare_owner
            else _sole_marker(value_text, matchers)
        )
        if value is None or not coherent:
            return None
        answer_value, answer_coherent = _sole_marker(answer_quote, matchers)
        if not answer_coherent or (
            answer_value is not None and answer_value != value
        ) or (not bare_owner and answer_value != value):
            return None
        return base.model_copy(update={field: value})
    # Free-text slots substitute the template only; no qualifier is inferred.
    return base


def _materialize_binding(
    *,
    proposal: AnswerBindingProposal,
    binding_index: int,
    frame,
    span: QuoteSpan,
    context: TurnInterpretContextPacket,
    operation_id: UUID,
) -> tuple[tuple[Evidence, ...], set[TurnInterpretRejectCode]]:
    reasons: set[TurnInterpretRejectCode] = set()
    definition = frame.definition
    target = next(
        (
            item
            for item in definition.targets
            if item.target_ordinal == proposal.target_ordinal
        ),
        None,
    )
    if target is None:
        return (), {TurnInterpretRejectCode.BINDING_TARGET_OUT_OF_RANGE}

    expected_kind = {
        QuestionTargetKind.PROPOSITION: AnswerBindingKind.PROPOSITION,
        QuestionTargetKind.SLOT: AnswerBindingKind.SLOT,
        QuestionTargetKind.CHOICE: AnswerBindingKind.CHOICE,
    }[target.target_kind]
    if proposal.binding_kind != expected_kind:
        return (), {TurnInterpretRejectCode.BINDING_KIND_MISMATCH}

    episode_id = (
        context.active_episode.episode_id if context.active_episode is not None else None
    )
    common = dict(
        session_id=context.session_id,
        episode_id=episode_id,
        extractor_operation_id=operation_id,
    )
    support_common = dict(
        employee_turn_id=context.current_employee_turn.turn_id,
        answer_quote=proposal.answer_quote,
        answer_span=span,
        question_frame_id=frame.question_frame_id,
        question_frame_definition_hash=definition.definition_hash,
        target_ordinal=target.target_ordinal,
        target_hash=target.target_hash,
    )

    materialized: list[Evidence] = []
    try:
        if proposal.binding_kind == AnswerBindingKind.PROPOSITION:
            denied = proposal.resolution == AnswerBindingResolution.DENIED
            proposition = target.proposition
            qualifiers = proposition.qualifiers
            if denied:
                qualifiers = qualifiers.model_copy(update={"polarity": Polarity.DENIED})
            # Only a correction_check denial supersedes: an atomic confirmation
            # denial states a new fact, it does not retract a recorded one.
            supersedes = (
                proposition.supersedes_evidence_ids
                if denied and definition.mode.value == "correction_check"
                else ()
            )
            materialized.append(
                Evidence(
                    **common,
                    evidence_id=contextual_evidence_id(operation_id, binding_index, 1),
                    subject=proposition.subject,
                    kind=proposition.kind,
                    claim=proposition.claim,
                    qualifiers=qualifiers,
                    supersedes=supersedes,
                    support=ContextualAnswerSupport(
                        **support_common,
                        binding_kind=(
                            ContextualBindingKind.DENIAL
                            if denied
                            else ContextualBindingKind.AFFIRMATION
                        ),
                        resolution=(
                            ContextualResolution.DENIED
                            if denied
                            else ContextualResolution.AFFIRMED
                        ),
                    ),
                )
            )
        elif proposal.binding_kind == AnswerBindingKind.SLOT:
            value_text = proposal.value_text or ""
            if value_text not in proposal.answer_quote:
                return (), {TurnInterpretRejectCode.BINDING_VALUE_NOT_SUPPORTED}
            qualifiers = _slot_qualifiers(target, value_text, proposal.answer_quote)
            if qualifiers is None:
                return (), {TurnInterpretRejectCode.BINDING_VALUE_NOT_SUPPORTED}
            materialized.append(
                Evidence(
                    **common,
                    evidence_id=contextual_evidence_id(operation_id, binding_index, 1),
                    subject=target.subject,
                    kind=target.evidence_kind,
                    claim=target.claim_template.replace("{value}", value_text),
                    qualifiers=qualifiers,
                    supersedes=target.supersedes_evidence_ids,
                    support=ContextualAnswerSupport(
                        **support_common,
                        binding_kind=ContextualBindingKind.SLOT_VALUE,
                        resolution=ContextualResolution.SUPPLIED,
                        value_text=value_text,
                    ),
                )
            )
        else:
            options = {item.option_ordinal: item for item in target.options}
            if not set(proposal.selected_choice_ordinals) <= options.keys():
                return (), {TurnInterpretRejectCode.CHOICE_SELECTION_INVALID}
            # Numbered by option ordinal so identity does not depend on the
            # order the model happened to list the selections in (plan §7.4).
            for index, ordinal in enumerate(sorted(proposal.selected_choice_ordinals), 1):
                option = options[ordinal]
                materialized.append(
                    Evidence(
                        **common,
                        evidence_id=contextual_evidence_id(
                            operation_id, binding_index, index
                        ),
                        subject=option.proposition.subject,
                        kind=option.proposition.kind,
                        claim=option.proposition.claim,
                        qualifiers=option.proposition.qualifiers,
                        supersedes=option.proposition.supersedes_evidence_ids,
                        support=ContextualAnswerSupport(
                            **support_common,
                            binding_kind=ContextualBindingKind.CHOICE_SELECTION,
                            resolution=ContextualResolution.SELECTED,
                            choice_option_ordinal=ordinal,
                        ),
                    )
                )
    except (ValidationError, ValueError):
        reasons.add(TurnInterpretRejectCode.CONTEXTUAL_MATERIALIZATION_FAILED)
        return (), reasons
    return tuple(materialized), reasons


def _literal_fingerprint(proposal: ObservationProposal) -> tuple[object, ...]:
    return (
        proposal.subject,
        proposal.kind,
        proposal.claim,
        proposal.quote,
        proposal.quote_occurrence,
        proposal.correction.target_candidate_ordinals,
        proposal.correction.target_unknown,
    )


def _binding_fingerprint(proposal: AnswerBindingProposal) -> tuple[object, ...]:
    return (
        proposal.target_ordinal,
        proposal.binding_kind,
        proposal.resolution,
        proposal.answer_quote,
        proposal.answer_quote_occurrence,
        proposal.value_text,
        proposal.selected_choice_ordinals,
    )


def _duplicates(values: tuple[tuple[object, ...], ...]) -> frozenset[tuple[object, ...]]:
    counts: dict[tuple[object, ...], int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return frozenset(value for value, count in counts.items() if count > 1)


def _canonical_insufficiency_codes(
    values: set[TurnInsufficiencyCode],
) -> tuple[TurnInsufficiencyCode, ...]:
    positions = {
        value: index for index, value in enumerate(TurnInsufficiencyCode)
    }
    return tuple(sorted(values, key=positions.__getitem__))


def _frame_failure(
    limitation: QuestionFrameLimitation | None,
) -> tuple[TurnInterpretRejectCode, TurnInsufficiencyCode]:
    if limitation in {None, QuestionFrameLimitation.MISSING}:
        return (
            TurnInterpretRejectCode.BINDING_WITHOUT_QUESTION_FRAME,
            TurnInsufficiencyCode.QUESTION_FRAME_MISSING,
        )
    if limitation in {
        QuestionFrameLimitation.ANSWER_NOT_BOUND,
        QuestionFrameLimitation.NOT_IMMEDIATE,
    }:
        return (
            TurnInterpretRejectCode.QUESTION_FRAME_NOT_ELIGIBLE,
            TurnInsufficiencyCode.QUESTION_FRAME_NOT_IMMEDIATE,
        )
    if limitation in {
        QuestionFrameLimitation.TEXT_HASH_MISMATCH,
        QuestionFrameLimitation.SOURCE_HASH_MISMATCH,
    }:
        return (
            TurnInterpretRejectCode.QUESTION_FRAME_HASH_MISMATCH,
            TurnInsufficiencyCode.QUESTION_FRAME_STALE,
        )
    return (
        TurnInterpretRejectCode.QUESTION_FRAME_NOT_ELIGIBLE,
        TurnInsufficiencyCode.QUESTION_FRAME_STALE,
    )


def _binding_insufficiency(
    *,
    frame,
    proposal: AnswerBindingProposal,
    reasons: set[TurnInterpretRejectCode],
) -> TurnInsufficiencyCode | None:
    if TurnInterpretRejectCode.CHOICE_SELECTION_INVALID in reasons:
        return TurnInsufficiencyCode.CHOICE_SELECTION_AMBIGUOUS
    if TurnInterpretRejectCode.BINDING_VALUE_NOT_SUPPORTED not in reasons or frame is None:
        return None
    target = next(
        (
            item
            for item in frame.definition.targets
            if item.target_ordinal == proposal.target_ordinal
        ),
        None,
    )
    if not isinstance(target, SlotQuestionTarget):
        return None
    return {
        QuestionSlotKind.FREQUENCY: TurnInsufficiencyCode.AMBIGUOUS_FREQUENCY,
        QuestionSlotKind.OWNERSHIP: TurnInsufficiencyCode.AMBIGUOUS_OWNERSHIP,
        QuestionSlotKind.TIME_SCOPE: TurnInsufficiencyCode.AMBIGUOUS_TIME_SCOPE,
    }.get(target.slot_kind)


def verify_turn_interpret_output(
    *,
    output: TurnInterpretOutput,
    context: TurnInterpretContextPacket,
    operation_id: UUID,
    projection: TurnInterpretProjection | None = None,
) -> TurnInterpretVerificationReport:
    """Verify proposals without repairing or mutating model-provided content."""

    output = TurnInterpretOutput.model_validate(output.model_dump())
    context = TurnInterpretContextPacket.model_validate(context.model_dump())
    if context.operation_name != "turn.interpret":
        raise ValueError("turn interpreter requires turn.interpret context")
    if context.operation_id != operation_id:
        raise ValueError("operation_id does not match context")
    if context.current_employee_turn.role != TranscriptRole.EMPLOYEE:
        raise ValueError("turn interpreter context must contain an employee turn")
    if projection is None:
        projection = turn_interpret_projection(context)

    candidate_ids = projection.correction_candidate_ids
    candidate_by_id = {
        item.evidence.evidence_id: item.evidence for item in context.correction_candidates
    }
    turn_text = context.current_employee_turn.text
    model_insufficiency = set(output.turn_insufficiency_codes)
    system_insufficiency: set[TurnInsufficiencyCode] = set()
    literal_duplicates = _duplicates(
        tuple(_literal_fingerprint(item) for item in output.literal_observations)
    )

    decisions: list[ObservationVerification] = []
    for index, proposal in enumerate(output.literal_observations, 1):
        reasons: set[TurnInterpretRejectCode] = set()
        candidate_evidence_id = literal_evidence_id(operation_id, index)
        span, quote_error = _exact_span(
            turn_text, proposal.quote, proposal.quote_occurrence
        )
        if quote_error == "not_found":
            reasons.add(TurnInterpretRejectCode.QUOTE_NOT_FOUND)
        elif quote_error == "occurrence_out_of_range":
            reasons.add(TurnInterpretRejectCode.QUOTE_OCCURRENCE_OUT_OF_RANGE)

        qualifiers, qualifiers_valid = _qualifiers(proposal)
        if not qualifiers_valid:
            reasons.add(TurnInterpretRejectCode.INVALID_QUALIFIER)
        if not _qualifier_supports_are_in_quote(proposal):
            reasons.add(TurnInterpretRejectCode.QUALIFIER_SUPPORT_NOT_IN_QUOTE)
        if not _qualifier_specificity_is_supported(proposal):
            reasons.add(TurnInterpretRejectCode.FALSE_SPECIFIC_QUALIFIER)

        ordinals = proposal.correction.target_candidate_ordinals
        out_of_range = [item for item in ordinals if item > len(candidate_ids)]
        if out_of_range:
            reasons.add(TurnInterpretRejectCode.FOREIGN_CORRECTION_TARGET)
        targets = tuple(
            candidate_ids[item - 1] for item in ordinals if item <= len(candidate_ids)
        )
        if any(
            candidate_by_id[target].status != EvidenceStatus.ACTIVE for target in targets
        ):
            reasons.add(TurnInterpretRejectCode.INACTIVE_CORRECTION_TARGET)
        if proposal.kind == EvidenceKind.CORRECTION:
            if bool(ordinals) == proposal.correction.target_unknown:
                reasons.add(TurnInterpretRejectCode.INCOHERENT_CORRECTION)
            if proposal.correction.target_unknown:
                system_insufficiency.add(
                    TurnInsufficiencyCode.CORRECTION_TARGET_UNKNOWN
                )
        elif ordinals or proposal.correction.target_unknown:
            reasons.add(TurnInterpretRejectCode.INCOHERENT_CORRECTION)

        if _unsupported_quantification(proposal):
            reasons.add(TurnInterpretRejectCode.UNSUPPORTED_QUANTIFICATION)
        if _reference_leakage(proposal.claim):
            reasons.add(TurnInterpretRejectCode.REFERENCE_LEAKAGE)
        if _NON_ATOMIC.search(proposal.claim):
            reasons.add(TurnInterpretRejectCode.NON_ATOMIC_CLAIM)
        if _literal_fingerprint(proposal) in literal_duplicates:
            reasons.add(TurnInterpretRejectCode.DUPLICATE_OBSERVATION)

        scoped_insufficiency = set(proposal.insufficiency_codes)
        if not scoped_insufficiency <= model_insufficiency:
            reasons.add(TurnInterpretRejectCode.INSUFFICIENCY_INCOHERENT)
        if (
            proposal.qualifiers.frequency.unit != FrequencyUnit.UNKNOWN
            and TurnInsufficiencyCode.AMBIGUOUS_FREQUENCY in scoped_insufficiency
        ) or (
            proposal.qualifiers.ownership != Ownership.UNKNOWN
            and TurnInsufficiencyCode.AMBIGUOUS_OWNERSHIP in scoped_insufficiency
        ) or (
            proposal.qualifiers.time_scope != TimeScope.UNKNOWN
            and TurnInsufficiencyCode.AMBIGUOUS_TIME_SCOPE in scoped_insufficiency
        ):
            reasons.add(TurnInterpretRejectCode.INSUFFICIENCY_INCOHERENT)

        evidence = None
        if not reasons and span is not None and qualifiers is not None:
            try:
                evidence = Evidence(
                    evidence_id=candidate_evidence_id,
                    session_id=context.session_id,
                    episode_id=(
                        context.active_episode.episode_id
                        if context.active_episode is not None
                        else None
                    ),
                    subject=proposal.subject,
                    kind=proposal.kind,
                    claim=proposal.claim,
                    support=LiteralEmployeeSpanSupport(
                        employee_turn_id=context.current_employee_turn.turn_id,
                        quote=proposal.quote,
                        span=span,
                        quote_match=QuoteMatch.EXACT,
                    ),
                    qualifiers=qualifiers,
                    supersedes=targets,
                    correction_target_unknown=proposal.correction.target_unknown,
                    extractor_operation_id=operation_id,
                )
            except (ValidationError, ValueError):
                reasons.add(TurnInterpretRejectCode.DOMAIN_INVARIANT_FAILED)

        accepted = not reasons and evidence is not None
        decisions.append(
            ObservationVerification(
                proposal_index=index,
                proposal_ref=derive_proposal_ref(index),
                candidate_evidence_id=candidate_evidence_id,
                accepted=accepted,
                reason_codes=canonical_reject_codes(reasons),
                computed_span=span,
                evidence=evidence if accepted else None,
            )
        )

    frame = context.question_frame.frame if context.question_frame is not None else None
    binding_duplicates = _duplicates(
        tuple(_binding_fingerprint(item) for item in output.answer_bindings)
    )
    bound_ordinals: dict[int, int] = {}
    for proposal in output.answer_bindings:
        if proposal.resolution not in {
            AnswerBindingResolution.AMBIGUOUS,
            AnswerBindingResolution.UNKNOWN,
        }:
            bound_ordinals[proposal.target_ordinal] = (
                bound_ordinals.get(proposal.target_ordinal, 0) + 1
            )
    binding_decisions: list[AnswerBindingVerification] = []
    for index, proposal in enumerate(output.answer_bindings, 1):
        reasons = set()
        unresolved = proposal.resolution in {
            AnswerBindingResolution.AMBIGUOUS,
            AnswerBindingResolution.UNKNOWN,
        }
        # Candidate ids are derived from the proposal's *shape*, before any gate,
        # so a dropped binding never renumbers a survivor (amendment §10.1). An
        # ambiguous/unknown binding materializes nothing and so has none.
        candidate_count = (
            0
            if unresolved
            else len(proposal.selected_choice_ordinals)
            if proposal.binding_kind == AnswerBindingKind.CHOICE
            else 1
        )
        candidate_evidence_ids = tuple(
            contextual_evidence_id(operation_id, index, materialization)
            for materialization in range(1, candidate_count + 1)
        )

        span, quote_error = _exact_span(
            turn_text, proposal.answer_quote, proposal.answer_quote_occurrence
        )
        if quote_error == "not_found":
            reasons.add(TurnInterpretRejectCode.BINDING_QUOTE_NOT_FOUND)
        elif quote_error == "occurrence_out_of_range":
            reasons.add(TurnInterpretRejectCode.BINDING_QUOTE_OCCURRENCE_OUT_OF_RANGE)
        target = None
        if frame is None:
            frame_reason, frame_insufficiency = _frame_failure(
                context.question_frame_limitation
            )
            reasons.add(frame_reason)
            system_insufficiency.add(frame_insufficiency)
        else:
            target = next(
                (
                    item
                    for item in frame.definition.targets
                    if item.target_ordinal == proposal.target_ordinal
                ),
                None,
            )
            if target is None:
                reasons.add(TurnInterpretRejectCode.BINDING_TARGET_OUT_OF_RANGE)
            else:
                expected_kind = {
                    QuestionTargetKind.PROPOSITION: AnswerBindingKind.PROPOSITION,
                    QuestionTargetKind.SLOT: AnswerBindingKind.SLOT,
                    QuestionTargetKind.CHOICE: AnswerBindingKind.CHOICE,
                }[target.target_kind]
                if proposal.binding_kind != expected_kind:
                    reasons.add(TurnInterpretRejectCode.BINDING_KIND_MISMATCH)
        if (
            _binding_fingerprint(proposal) in binding_duplicates
            or (
                not unresolved
                and bound_ordinals.get(proposal.target_ordinal, 0) > 1
            )
        ):
            reasons.add(TurnInterpretRejectCode.DUPLICATE_BINDING_TARGET)

        materialized: tuple[Evidence, ...] = ()
        if not reasons and span is not None and frame is not None and not unresolved:
            materialized, extra = _materialize_binding(
                proposal=proposal,
                binding_index=index,
                frame=frame,
                span=span,
                context=context,
                operation_id=operation_id,
            )
            reasons |= extra

        binding_insufficiency = _binding_insufficiency(
            frame=frame, proposal=proposal, reasons=reasons
        )
        if binding_insufficiency is not None:
            system_insufficiency.add(binding_insufficiency)

        accepted = not reasons and span is not None
        if accepted and unresolved:
            system_insufficiency.add(
                TurnInsufficiencyCode.ANSWER_BINDING_AMBIGUOUS
            )
        binding_decisions.append(
            AnswerBindingVerification(
                binding_index=index,
                binding_ref=derive_binding_ref(index),
                candidate_evidence_ids=candidate_evidence_ids,
                accepted=accepted,
                reason_codes=canonical_reject_codes(reasons),
                computed_span=span,
                materialized_evidence=materialized if accepted else (),
            )
        )

    topic_decisions = []
    for index, proposal in enumerate(output.emergent_topics, 1):
        span, quote_error = _exact_span(
            turn_text, proposal.quote, proposal.quote_occurrence
        )
        reasons = set()
        if quote_error == "not_found":
            reasons.add(TurnInterpretRejectCode.QUOTE_NOT_FOUND)
        elif quote_error == "occurrence_out_of_range":
            reasons.add(TurnInterpretRejectCode.QUOTE_OCCURRENCE_OUT_OF_RANGE)
        topic_decisions.append(
            EmergentTopicVerification(
                topic_index=index,
                proposal=proposal,
                accepted=not reasons and span is not None,
                reason_codes=canonical_reject_codes(reasons),
                computed_span=span,
            )
        )

    accepted_observations = tuple(item for item in decisions if item.accepted)
    accepted_bindings = tuple(item for item in binding_decisions if item.accepted)
    accepted_ids = tuple(
        item.evidence.evidence_id for item in accepted_observations
    ) + tuple(
        evidence.evidence_id
        for item in accepted_bindings
        for evidence in item.materialized_evidence
    )
    return TurnInterpretVerificationReport(
        operation_id=operation_id,
        operation_definition_hash=context.operation_definition_hash,
        verifier_policy_name=TURN_INTERPRET_VERIFIER_POLICY_V2.name,
        verifier_policy_version=TURN_INTERPRET_VERIFIER_POLICY_V2.version,
        verifier_policy_hash=TURN_INTERPRET_VERIFIER_POLICY_V2.policy_hash,
        session_id=context.session_id,
        turn_id=context.current_employee_turn.turn_id,
        question_frame_id=frame.question_frame_id if frame is not None else None,
        context_packet_hash=canonical_hash(context),
        output_hash=canonical_hash(output),
        dialogue_act=output.dialogue_act,
        episode_signal=output.episode_signal,
        decisions=tuple(decisions),
        binding_decisions=tuple(binding_decisions),
        accepted_evidence_ids=accepted_ids,
        emergent_topic_decisions=tuple(topic_decisions),
        model_insufficiency_codes=output.turn_insufficiency_codes,
        system_insufficiency_codes=_canonical_insufficiency_codes(
            system_insufficiency
        ),
        accepted_count=len(accepted_observations) + len(accepted_bindings),
        dropped_count=(
            len(decisions)
            - len(accepted_observations)
            + len(binding_decisions)
            - len(accepted_bindings)
        ),
    )


def accepted_evidence(
    *,
    report: TurnInterpretVerificationReport,
    session_id: UUID,
    turn_id: UUID,
    operation_id: UUID,
) -> tuple[Evidence, ...]:
    """Read accepted immutable Evidence after revalidating the expected scope."""

    report = TurnInterpretVerificationReport.model_validate(report.model_dump())
    if (
        report.session_id != session_id
        or report.turn_id != turn_id
        or report.operation_id != operation_id
    ):
        raise ValueError("verification report scope mismatch")
    return tuple(item.evidence for item in report.decisions if item.accepted) + tuple(
        evidence
        for item in report.binding_decisions
        if item.accepted
        for evidence in item.materialized_evidence
    )
