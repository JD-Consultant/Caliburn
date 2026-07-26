"""Deterministic semantic gates that do not call an LLM."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from uuid import UUID

from .errors import DomainViolation
from .evidence import (
    Evidence,
    EvidenceStatus,
    EvidenceSubject,
    Ownership,
    Polarity,
    TimeScope,
)
from .job_model import CandidateJobItem, CandidateKind, CandidateStatus
from .reason_codes import ReasonCode
from .support import LiteralEmployeeSpanSupport, QuoteMatch
from .transcript import TranscriptRole, TranscriptTurn


QUOTE_NORMALIZATION_VERSION = "quote_nfkc_ws.v1"
_WHITESPACE = re.compile(r"\s+")
_EXPLICIT_THRESHOLD = re.compile(
    r"(?:[<>≤≥]=?\s*)?\d+(?:\.\d+)?\s*(?:%|％|分鐘|小時|天|日|週|周|月|年|次|件|筆)"
)


def normalize_quote(value: str) -> str:
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", value)).strip()


def assert_evidence_matches_turn(evidence: Evidence, turn: TranscriptTurn) -> None:
    """Both support kinds anchor a span in the same employee turn.

    A literal support quotes the claim itself; a contextual support quotes only
    the short answer (是 / 每週) that resolved a QuestionFrame target. Either way
    the span must exist verbatim in the turn — the difference in what the quote
    *means* is the support kind's job, not this gate's (ADR 0037 §4).
    """

    if turn.role != TranscriptRole.EMPLOYEE:
        raise DomainViolation(
            ReasonCode.EVIDENCE_REQUIRES_EMPLOYEE_TURN,
            "evidence may only quote an employee turn",
            details={"turn_id": str(turn.turn_id)},
        )
    if evidence.session_id != turn.session_id or evidence.source_turn_id != turn.turn_id:
        raise DomainViolation(
            ReasonCode.EVIDENCE_TURN_MISMATCH,
            "evidence session/turn IDs do not match the quoted turn",
            details={"evidence_id": str(evidence.evidence_id)},
        )

    support = evidence.support
    if isinstance(support, LiteralEmployeeSpanSupport):
        span = support.span
        quote = support.quote
        quote_match = support.quote_match
        normalization_version = support.normalization_version
    else:
        span = support.answer_span
        quote = support.answer_quote
        quote_match = QuoteMatch.EXACT
        normalization_version = None

    if span.end > len(turn.text):
        raise DomainViolation(
            ReasonCode.QUOTE_SPAN_OUT_OF_RANGE,
            "quote span exceeds the employee turn",
            details={"text_length": len(turn.text), "span_end": span.end},
        )

    source = turn.text[span.start : span.end]
    if quote_match == QuoteMatch.EXACT:
        matches = source == quote
    else:
        if normalization_version != QUOTE_NORMALIZATION_VERSION:
            raise DomainViolation(
                ReasonCode.NORMALIZATION_VERSION_INVALID,
                "unsupported quote normalization version",
                details={"normalization_version": normalization_version},
            )
        matches = normalize_quote(source) == normalize_quote(quote)
    if not matches:
        raise DomainViolation(
            ReasonCode.QUOTE_MISMATCH,
            "evidence quote does not match its transcript span",
            details={"evidence_id": str(evidence.evidence_id)},
        )


def assert_model_may_replace_candidate(candidate: CandidateJobItem) -> None:
    if candidate.status in {CandidateStatus.ACCEPTED, CandidateStatus.REJECTED}:
        raise DomainViolation(
            ReasonCode.HUMAN_DECISION_PROTECTED,
            "a model operation cannot replace a human-decided candidate",
            details={"candidate_id": str(candidate.candidate_id)},
        )


def assert_candidate_projectable(
    candidate: CandidateJobItem,
    evidence_by_id: Mapping[UUID, Evidence],
) -> None:
    linked = assert_candidate_lineage(candidate, evidence_by_id)

    has_current_employee_support = any(
        item.subject in {EvidenceSubject.EMPLOYEE, EvidenceSubject.EMPLOYEE_TEAM}
        and item.qualifiers.time_scope == TimeScope.CURRENT
        and item.qualifiers.polarity == Polarity.AFFIRMED
        and item.qualifiers.ownership in {Ownership.OWNER, Ownership.SHARED, Ownership.ASSISTS}
        for item in linked
    )
    if not has_current_employee_support:
        raise DomainViolation(
            ReasonCode.CANDIDATE_CURRENT_SCOPE_INVALID,
            "candidate lacks affirmed current employee/team evidence",
        )

    if candidate.kind in {CandidateKind.ABILITY, CandidateKind.ATTITUDE} and candidate.status in {
        CandidateStatus.VERIFIED,
        CandidateStatus.PROJECTED,
    }:
        episode_ids = {item.episode_id for item in linked if item.episode_id is not None}
        if len(episode_ids) < 2:
            raise DomainViolation(
                ReasonCode.ABILITY_CROSS_EPISODE_EVIDENCE_REQUIRED,
                "verified ability/attitude requires evidence from two episodes",
            )

    if (
        candidate.kind == CandidateKind.BEHAVIOR_INDICATOR
        and _EXPLICIT_THRESHOLD.search(candidate.statement)
        and not candidate.thresholds
    ):
        raise DomainViolation(
            ReasonCode.NUMERIC_THRESHOLD_SOURCE_REQUIRED,
            "quantitative behavior threshold requires an explicit source",
        )


def assert_candidate_lineage(
    candidate: CandidateJobItem,
    evidence_by_id: Mapping[UUID, Evidence],
) -> list[Evidence]:
    linked: list[Evidence] = []
    for evidence_id in candidate.evidence_ids:
        item = evidence_by_id.get(evidence_id)
        if item is None:
            raise DomainViolation(
                ReasonCode.REFERENCE_ONLY_CANDIDATE,
                "candidate has no employee evidence closure",
                details={"candidate_id": str(candidate.candidate_id)},
            )
        linked.append(item)

    if not linked:
        raise DomainViolation(
            ReasonCode.REFERENCE_ONLY_CANDIDATE,
            "candidate has no employee evidence",
        )
    if any(item.status != EvidenceStatus.ACTIVE for item in linked):
        raise DomainViolation(
            ReasonCode.CANDIDATE_EVIDENCE_INACTIVE,
            "candidate references superseded or withdrawn evidence",
        )

    for threshold in candidate.thresholds:
        if threshold.evidence_id is not None:
            source = evidence_by_id.get(threshold.evidence_id)
            if (
                source is None
                or source.status != EvidenceStatus.ACTIVE
                or threshold.evidence_id not in candidate.evidence_ids
            ):
                raise DomainViolation(
                    ReasonCode.NUMERIC_THRESHOLD_SOURCE_REQUIRED,
                    "threshold evidence must be active and linked by the candidate",
                    details={"source_id": threshold.source_id},
                )
    return linked


def active_evidence(items: Iterable[Evidence]) -> dict[UUID, Evidence]:
    return {item.evidence_id: item for item in items if item.status == EvidenceStatus.ACTIVE}
