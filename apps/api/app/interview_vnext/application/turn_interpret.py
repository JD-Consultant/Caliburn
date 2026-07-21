"""Pure mapping and semantic verification for the turn.interpret operation."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid5

from pydantic import ValidationError

from app.interview_vnext.domain.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceQualifiers,
    EvidenceStatus,
    FrequencyQualifier,
    FrequencyUnit,
)
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.support import QuoteMatch, QuoteSpan
from app.interview_vnext.domain.transcript import TranscriptRole
from app.interview_vnext.llm.context import (
    INJECTION_BOUNDARY,
    ContextEvidenceItem,
    TurnInterpretContextPacket,
)
from app.interview_vnext.llm.turn_interpret import (
    ObservationProposal,
    ObservationVerification,
    EmergentTopicVerification,
    TurnInputContradiction,
    TurnInputEpisode,
    TurnInputEvidence,
    TurnInputTurn,
    TurnInterpretInput,
    TurnInterpretOutput,
    TurnInterpretRejectCode,
    TurnInterpretVerificationReport,
    TURN_INTERPRET_VERIFIER_POLICY_V1,
    canonical_reject_codes,
)


_NUMBER = re.compile(TURN_INTERPRET_VERIFIER_POLICY_V1.number_pattern)
_NON_ATOMIC = re.compile(
    TURN_INTERPRET_VERIFIER_POLICY_V1.non_atomic_pattern, re.IGNORECASE
)
_REFERENCE_MARKERS = TURN_INTERPRET_VERIFIER_POLICY_V1.reference_markers


def _input_turn(turn) -> TurnInputTurn:
    return TurnInputTurn(
        turn_id=turn.turn_id,
        sequence=turn.sequence,
        locale=turn.locale,
        text=turn.text,
    )


def _input_evidence(item: ContextEvidenceItem) -> TurnInputEvidence:
    evidence = item.evidence
    return TurnInputEvidence(
        evidence_id=evidence.evidence_id,
        source_turn_id=evidence.turn_id,
        subject=evidence.subject,
        kind=evidence.kind,
        claim=evidence.claim,
        quote=evidence.quote,
        qualifiers=evidence.qualifiers,
    )


def turn_interpret_input_from_context(
    context: TurnInterpretContextPacket,
) -> TurnInterpretInput:
    """Project only the fields visible to the turn interpreter."""

    context = TurnInterpretContextPacket.model_validate(context.model_dump())
    return TurnInterpretInput(
        input_boundary=INJECTION_BOUNDARY,
        preceding_question=(
            _input_turn(context.preceding_consultant_turn)
            if context.preceding_consultant_turn is not None
            else None
        ),
        current_turn=_input_turn(context.current_employee_turn),
        active_episode=(
            TurnInputEpisode(
                episode_id=context.active_episode.episode_id,
                target=context.active_episode.target,
                status=context.active_episode.status,
            )
            if context.active_episode is not None
            else None
        ),
        contradictions=tuple(
            TurnInputContradiction(
                gap_id=item.gap.gap_id,
                status=item.gap.status,
                question_goal=item.gap.question_goal,
                supporting_evidence_ids=item.gap.supporting_evidence_ids,
            )
            for item in context.contradictions
        ),
        correction_candidates=tuple(
            _input_evidence(item) for item in context.correction_candidates
        ),
        recent_active_evidence=tuple(
            _input_evidence(item) for item in context.recent_active_evidence
        ),
    )


def derive_evidence_id(operation_id: UUID, proposal_key: str) -> UUID:
    """Stable UUIDv5 ID; the model never chooses a domain identifier."""

    return uuid5(operation_id, f"observation/{proposal_key}")


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


def _unsupported_quantification(proposal: ObservationProposal) -> bool:
    quote_numbers = set(_NUMBER.findall(proposal.quote))
    if not set(_NUMBER.findall(proposal.claim)) <= quote_numbers:
        return True
    value = proposal.qualifiers.frequency.value
    return value is not None and value not in proposal.quote


def _reference_leakage(claim: str) -> bool:
    folded = claim.casefold()
    return any(marker in folded for marker in _REFERENCE_MARKERS)


def verify_turn_interpret_output(
    *,
    output: TurnInterpretOutput,
    context: TurnInterpretContextPacket,
    operation_id: UUID,
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

    candidate_by_id = {
        item.evidence.evidence_id: item.evidence
        for item in context.correction_candidates
    }
    target_claim_counts: dict[UUID, int] = {}
    for proposal in output.observations:
        if proposal.kind != EvidenceKind.CORRECTION:
            continue
        for target in set(proposal.correction_target_evidence_ids):
            target_claim_counts[target] = target_claim_counts.get(target, 0) + 1
    multiply_claimed_targets = {
        target for target, count in target_claim_counts.items() if count > 1
    }
    decisions: list[ObservationVerification] = []
    for index, proposal in enumerate(output.observations, 1):
        reasons: set[TurnInterpretRejectCode] = set()
        span, quote_error = _exact_span(
            context.current_employee_turn.text,
            proposal.quote,
            proposal.quote_occurrence,
        )
        if quote_error == "not_found":
            reasons.add(TurnInterpretRejectCode.QUOTE_NOT_FOUND)
        elif quote_error == "occurrence_out_of_range":
            reasons.add(TurnInterpretRejectCode.QUOTE_OCCURRENCE_OUT_OF_RANGE)

        qualifiers, qualifiers_valid = _qualifiers(proposal)
        if not qualifiers_valid:
            reasons.add(TurnInterpretRejectCode.INVALID_QUALIFIER)

        targets = proposal.correction_target_evidence_ids
        if len(targets) != len(set(targets)):
            reasons.add(TurnInterpretRejectCode.INCOHERENT_CORRECTION)
        if set(targets) & multiply_claimed_targets:
            reasons.add(TurnInterpretRejectCode.INCOHERENT_CORRECTION)
        foreign_targets = set(targets) - candidate_by_id.keys()
        if foreign_targets:
            reasons.add(TurnInterpretRejectCode.FOREIGN_CORRECTION_TARGET)
        if any(
            candidate_by_id[target].status != EvidenceStatus.ACTIVE
            for target in targets
            if target in candidate_by_id
        ):
            reasons.add(TurnInterpretRejectCode.INACTIVE_CORRECTION_TARGET)
        if proposal.kind == EvidenceKind.CORRECTION:
            if bool(targets) == proposal.correction_target_unknown:
                reasons.add(TurnInterpretRejectCode.INCOHERENT_CORRECTION)
        elif targets or proposal.correction_target_unknown:
            reasons.add(TurnInterpretRejectCode.INCOHERENT_CORRECTION)

        if _unsupported_quantification(proposal):
            reasons.add(TurnInterpretRejectCode.UNSUPPORTED_QUANTIFICATION)
        if _reference_leakage(proposal.claim):
            reasons.add(TurnInterpretRejectCode.REFERENCE_LEAKAGE)
        if _NON_ATOMIC.search(proposal.claim):
            reasons.add(TurnInterpretRejectCode.NON_ATOMIC_CLAIM)

        evidence = None
        if not reasons and span is not None and qualifiers is not None:
            try:
                evidence = Evidence(
                    evidence_id=derive_evidence_id(operation_id, proposal.proposal_key),
                    session_id=context.session_id,
                    turn_id=context.current_employee_turn.turn_id,
                    episode_id=(
                        context.active_episode.episode_id
                        if context.active_episode is not None
                        else None
                    ),
                    subject=proposal.subject,
                    kind=proposal.kind,
                    claim=proposal.claim,
                    quote=proposal.quote,
                    span=span,
                    quote_match=QuoteMatch.EXACT,
                    qualifiers=qualifiers,
                    supersedes=targets,
                    correction_target_unknown=proposal.correction_target_unknown,
                    extractor_operation_id=operation_id,
                )
            except (ValidationError, ValueError):
                reasons.add(TurnInterpretRejectCode.DOMAIN_INVARIANT_FAILED)

        accepted = not reasons and evidence is not None
        decisions.append(
            ObservationVerification(
                proposal_index=index,
                proposal_key=proposal.proposal_key,
                accepted=accepted,
                reason_codes=canonical_reject_codes(reasons),
                computed_span=span,
                evidence=evidence if accepted else None,
            )
        )

    accepted = tuple(item for item in decisions if item.accepted)
    topic_decisions = []
    for index, proposal in enumerate(output.emergent_topics, 1):
        span, quote_error = _exact_span(
            context.current_employee_turn.text,
            proposal.quote,
            proposal.quote_occurrence,
        )
        reasons: set[TurnInterpretRejectCode] = set()
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
    return TurnInterpretVerificationReport(
        operation_id=operation_id,
        operation_definition_hash=context.operation_definition_hash,
        verifier_policy_name=TURN_INTERPRET_VERIFIER_POLICY_V1.name,
        verifier_policy_version=TURN_INTERPRET_VERIFIER_POLICY_V1.version,
        verifier_policy_hash=TURN_INTERPRET_VERIFIER_POLICY_V1.policy_hash,
        session_id=context.session_id,
        turn_id=context.current_employee_turn.turn_id,
        context_packet_hash=canonical_hash(context),
        output_hash=canonical_hash(output),
        user_signal=output.user_signal,
        episode_signal=output.episode_signal,
        decisions=tuple(decisions),
        accepted_evidence_ids=tuple(item.evidence.evidence_id for item in accepted),
        emergent_topic_decisions=tuple(topic_decisions),
        insufficiencies=output.insufficiencies,
        accepted_count=len(accepted),
        dropped_count=len(decisions) - len(accepted),
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
    return tuple(
        item.evidence for item in report.decisions if item.accepted
    )
