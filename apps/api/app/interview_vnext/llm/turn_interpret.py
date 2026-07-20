"""Provider-neutral turn interpretation and verification contracts."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import field_validator, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.episode import EpisodeStatus, GapStatus
from app.interview_vnext.domain.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceQualifiers,
    EvidenceSubject,
    FrequencyUnit,
    Importance,
    Ownership,
    Polarity,
    QuoteSpan,
    TimeScope,
    Typicality,
)
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.identifiers import (
    Locale,
    NonEmptyText,
    SemVer,
    Sha256,
    StableName,
)
from app.interview_vnext.llm.context import INJECTION_BOUNDARY


_PROPOSAL_KEY = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


class UserSignal(StrEnum):
    ANSWER = "answer"
    CLARIFICATION = "clarification"
    CORRECTION = "correction"
    DONT_KNOW = "dont_know"
    DECLINE = "decline"
    STOP = "stop"
    OFF_TOPIC = "off_topic"
    MIXED = "mixed"


class EpisodeSignal(StrEnum):
    CONTINUE = "continue"
    POSSIBLE_SHIFT = "possible_shift"
    EXPLICIT_SHIFT = "explicit_shift"
    POSSIBLE_CLOSE = "possible_close"


class InsufficiencyReason(StrEnum):
    AMBIGUOUS_FREQUENCY = "ambiguous_frequency"
    AMBIGUOUS_OWNERSHIP = "ambiguous_ownership"
    AMBIGUOUS_SUBJECT = "ambiguous_subject"
    AMBIGUOUS_TIME_SCOPE = "ambiguous_time_scope"
    CONTRADICTION_UNRESOLVED = "contradiction_unresolved"
    CORRECTION_TARGET_UNKNOWN = "correction_target_unknown"
    INSUFFICIENT_DETAIL = "insufficient_detail"
    NO_WORK_FACT = "no_work_fact"


class TurnInputTurn(DomainModel):
    turn_id: UUID
    sequence: int
    locale: Locale
    text: NonEmptyText


class TurnInputEpisode(DomainModel):
    episode_id: UUID
    target: NonEmptyText
    status: EpisodeStatus


class TurnInputContradiction(DomainModel):
    gap_id: UUID
    status: GapStatus
    question_goal: NonEmptyText
    supporting_evidence_ids: tuple[UUID, ...]


class TurnInputEvidence(DomainModel):
    evidence_id: UUID
    source_turn_id: UUID
    subject: EvidenceSubject
    kind: EvidenceKind
    claim: NonEmptyText
    quote: NonEmptyText
    qualifiers: EvidenceQualifiers


class TurnInterpretInput(DomainModel):
    schema_version: Literal["turn_interpret_input.v1"] = "turn_interpret_input.v1"
    input_boundary: Literal[INJECTION_BOUNDARY]
    preceding_question: TurnInputTurn | None
    current_turn: TurnInputTurn
    active_episode: TurnInputEpisode | None
    contradictions: tuple[TurnInputContradiction, ...]
    correction_candidates: tuple[TurnInputEvidence, ...]
    recent_active_evidence: tuple[TurnInputEvidence, ...]


class FrequencyQualifierProposal(DomainModel):
    """Provider-facing frequency with decimal text preserved losslessly."""

    value: str | None
    unit: FrequencyUnit
    verbatim: str | None


class EvidenceQualifiersProposal(DomainModel):
    time_scope: TimeScope
    typicality: Typicality
    polarity: Polarity
    frequency: FrequencyQualifierProposal
    importance: Importance
    ownership: Ownership


class ObservationProposal(DomainModel):
    proposal_key: str
    subject: EvidenceSubject
    kind: EvidenceKind
    claim: NonEmptyText
    quote: NonEmptyText
    quote_occurrence: int
    qualifiers: EvidenceQualifiersProposal
    correction_target_evidence_ids: tuple[UUID, ...]
    correction_target_unknown: bool

    @field_validator("proposal_key")
    @classmethod
    def proposal_key_is_ascii_and_stable(cls, value: str) -> str:
        if not _PROPOSAL_KEY.fullmatch(value):
            raise ValueError("proposal_key must be a lowercase ASCII stable key")
        return value


class EmergentTopicProposal(DomainModel):
    topic: NonEmptyText
    quote: NonEmptyText
    quote_occurrence: int


class InsufficiencyProposal(DomainModel):
    reason_code: InsufficiencyReason
    observation_proposal_keys: tuple[str, ...]

    @field_validator("observation_proposal_keys")
    @classmethod
    def keys_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("insufficiency observation keys must be unique")
        return value


class TurnInterpretOutput(DomainModel):
    schema_version: Literal["turn_interpret_output.v1"]
    observations: tuple[ObservationProposal, ...]
    user_signal: UserSignal
    episode_signal: EpisodeSignal
    emergent_topics: tuple[EmergentTopicProposal, ...]
    insufficiencies: tuple[InsufficiencyProposal, ...]

    @model_validator(mode="after")
    def proposal_identity_and_links_are_valid(self) -> "TurnInterpretOutput":
        keys = tuple(item.proposal_key for item in self.observations)
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate_proposal_key")
        known = set(keys)
        for item in self.insufficiencies:
            if not set(item.observation_proposal_keys) <= known:
                raise ValueError("insufficiency references unknown proposal key")
        return self


class TurnInterpretRejectCode(StrEnum):
    DUPLICATE_PROPOSAL_KEY = "duplicate_proposal_key"
    QUOTE_NOT_FOUND = "quote_not_found"
    QUOTE_OCCURRENCE_OUT_OF_RANGE = "quote_occurrence_out_of_range"
    INVALID_QUALIFIER = "invalid_qualifier"
    FOREIGN_CORRECTION_TARGET = "foreign_correction_target"
    INACTIVE_CORRECTION_TARGET = "inactive_correction_target"
    INCOHERENT_CORRECTION = "incoherent_correction"
    UNSUPPORTED_QUANTIFICATION = "unsupported_quantification"
    REFERENCE_LEAKAGE = "reference_leakage"
    NON_ATOMIC_CLAIM = "non_atomic_claim"
    DOMAIN_INVARIANT_FAILED = "domain_invariant_failed"


class TurnInterpretVerifierPolicyDefinition(DomainModel):
    schema_version: Literal["turn_interpret_verifier_policy.v1"] = (
        "turn_interpret_verifier_policy.v1"
    )
    name: StableName
    version: SemVer
    quote_match: Literal["exact"]
    span_unit: Literal["unicode_code_point"]
    duplicate_correction_target_policy: Literal["reject_all"]
    number_pattern: NonEmptyText
    non_atomic_pattern: NonEmptyText
    reference_markers: tuple[NonEmptyText, ...]
    reject_order: tuple[TurnInterpretRejectCode, ...]

    @model_validator(mode="after")
    def policy_is_canonical(self) -> "TurnInterpretVerifierPolicyDefinition":
        if tuple(sorted(set(self.reference_markers))) != self.reference_markers:
            raise ValueError("verifier reference markers must be unique and sorted")
        if self.reject_order != tuple(TurnInterpretRejectCode):
            raise ValueError("verifier reject order must include the exact v1 enum order")
        for value in (self.number_pattern, self.non_atomic_pattern):
            try:
                re.compile(value)
            except re.error as exc:
                raise ValueError("verifier policy contains an invalid regex") from exc
        return self


class TurnInterpretVerifierPolicy(TurnInterpretVerifierPolicyDefinition):
    policy_hash: Sha256

    @model_validator(mode="after")
    def hash_matches_definition(self) -> "TurnInterpretVerifierPolicy":
        definition = TurnInterpretVerifierPolicyDefinition.model_validate(
            self.model_dump(exclude={"policy_hash"})
        )
        if canonical_hash(definition) != self.policy_hash:
            raise ValueError("turn interpreter verifier policy hash mismatch")
        return self


def define_turn_interpret_verifier_policy(
    **values,
) -> TurnInterpretVerifierPolicy:
    definition = TurnInterpretVerifierPolicyDefinition(**values)
    return TurnInterpretVerifierPolicy(
        **definition.model_dump(), policy_hash=canonical_hash(definition)
    )


TURN_INTERPRET_VERIFIER_POLICY_V1 = define_turn_interpret_verifier_policy(
    name="turn-interpret-verifier",
    version="1.0.0",
    quote_match="exact",
    span_unit="unicode_code_point",
    duplicate_correction_target_policy="reject_all",
    number_pattern=r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?",
    non_atomic_pattern=(
        r"(?:[;；\n]|，(?:並且|並|以及|而且)|,\s*(?:and|also)\b)"
    ),
    reference_markers=tuple(
        sorted(
            (
                "according to the taxonomy",
                "job description",
                "o*net",
                "onet",
                "urn:",
                "依據職業分類",
                "標準職稱",
                "職務說明書",
            )
        )
    ),
    reject_order=tuple(TurnInterpretRejectCode),
)


class ObservationVerification(DomainModel):
    proposal_index: int
    proposal_key: str
    accepted: bool
    reason_codes: tuple[TurnInterpretRejectCode, ...]
    computed_span: QuoteSpan | None
    evidence: Evidence | None

    @model_validator(mode="after")
    def outcome_is_coherent(self) -> "ObservationVerification":
        if self.proposal_index < 1:
            raise ValueError("proposal_index must be 1-based")
        if self.accepted:
            if self.reason_codes or self.computed_span is None or self.evidence is None:
                raise ValueError("accepted proposal requires span/evidence and no reasons")
        elif not self.reason_codes or self.evidence is not None:
            raise ValueError("rejected proposal requires reasons and no evidence")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("verification reason codes must be unique")
        return self


class EmergentTopicVerification(DomainModel):
    topic_index: int
    proposal: EmergentTopicProposal
    accepted: bool
    reason_codes: tuple[TurnInterpretRejectCode, ...]
    computed_span: QuoteSpan | None

    @model_validator(mode="after")
    def outcome_is_coherent(self) -> "EmergentTopicVerification":
        if self.topic_index < 1:
            raise ValueError("topic_index must be 1-based")
        if self.accepted != (not self.reason_codes and self.computed_span is not None):
            raise ValueError("emergent topic verification outcome is inconsistent")
        allowed = {
            TurnInterpretRejectCode.QUOTE_NOT_FOUND,
            TurnInterpretRejectCode.QUOTE_OCCURRENCE_OUT_OF_RANGE,
        }
        if not set(self.reason_codes) <= allowed:
            raise ValueError("emergent topic has an invalid reason code")
        return self


class TurnInterpretVerificationReport(DomainModel):
    schema_version: Literal["turn_interpret_verification_report.v1"] = (
        "turn_interpret_verification_report.v1"
    )
    operation_id: UUID
    operation_definition_hash: Sha256
    verifier_policy_name: StableName
    verifier_policy_version: SemVer
    verifier_policy_hash: Sha256
    session_id: UUID
    turn_id: UUID
    context_packet_hash: Sha256
    output_hash: Sha256
    user_signal: UserSignal
    episode_signal: EpisodeSignal
    decisions: tuple[ObservationVerification, ...]
    accepted_evidence_ids: tuple[UUID, ...]
    emergent_topic_decisions: tuple[EmergentTopicVerification, ...]
    insufficiencies: tuple[InsufficiencyProposal, ...]
    accepted_count: int
    dropped_count: int

    @model_validator(mode="after")
    def counts_identity_and_evidence_are_coherent(
        self,
    ) -> "TurnInterpretVerificationReport":
        policy = TURN_INTERPRET_VERIFIER_POLICY_V1
        if (
            self.verifier_policy_name != policy.name
            or self.verifier_policy_version != policy.version
            or self.verifier_policy_hash != policy.policy_hash
        ):
            raise ValueError("verification report has an unknown verifier policy identity")
        indices = tuple(item.proposal_index for item in self.decisions)
        if indices != tuple(range(1, len(indices) + 1)):
            raise ValueError("verification decisions must preserve proposal order")
        keys = tuple(item.proposal_key for item in self.decisions)
        if len(keys) != len(set(keys)):
            raise ValueError("verification proposal keys must be unique")
        topic_indices = tuple(
            item.topic_index for item in self.emergent_topic_decisions
        )
        if topic_indices != tuple(range(1, len(topic_indices) + 1)):
            raise ValueError("emergent topic decisions must preserve output order")
        accepted = tuple(item for item in self.decisions if item.accepted)
        if self.accepted_count != len(accepted):
            raise ValueError("accepted_count does not match decisions")
        if self.dropped_count != len(self.decisions) - len(accepted):
            raise ValueError("dropped_count does not match decisions")
        evidence_ids = tuple(item.evidence.evidence_id for item in accepted)
        if self.accepted_evidence_ids != evidence_ids:
            raise ValueError("accepted evidence IDs do not match decisions")
        for item in accepted:
            if (
                item.evidence.session_id != self.session_id
                or item.evidence.turn_id != self.turn_id
                or item.evidence.extractor_operation_id != self.operation_id
            ):
                raise ValueError("accepted evidence identity does not match report")
        return self


def turn_interpret_output_schema() -> dict:
    """Return the local full schema before provider portability projection."""

    return TurnInterpretOutput.model_json_schema()


TURN_INTERPRET_REJECT_ORDER = TURN_INTERPRET_VERIFIER_POLICY_V1.reject_order
TURN_INTERPRET_REJECT_ORDER_INDEX = {
    code: index for index, code in enumerate(TURN_INTERPRET_REJECT_ORDER)
}


def canonical_reject_codes(
    values: set[TurnInterpretRejectCode],
) -> tuple[TurnInterpretRejectCode, ...]:
    return tuple(sorted(values, key=TURN_INTERPRET_REJECT_ORDER_INDEX.__getitem__))
