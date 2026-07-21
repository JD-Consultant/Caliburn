"""Employee evidence and explicitly separate inference contracts."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .base import DomainModel
from .identifiers import NonEmptyText, ReferenceUrn, Sha256, StableName
from .support import QuoteMatch, QuoteSpan


class EvidenceSubject(StrEnum):
    EMPLOYEE = "employee"
    EMPLOYEE_TEAM = "employee_team"
    OTHER_ROLE = "other_role"
    ORGANIZATION = "organization"
    UNKNOWN = "unknown"


class EvidenceKind(StrEnum):
    ACTION = "action"
    INPUT = "input"
    OUTPUT = "output"
    PURPOSE = "purpose"
    CONDITION = "condition"
    STANDARD = "standard"
    FREQUENCY = "frequency"
    IMPORTANCE = "importance"
    OWNERSHIP = "ownership"
    TOOL = "tool"
    RECIPIENT = "recipient"
    DEPENDENCY = "dependency"
    EXCEPTION = "exception"
    NEGATION = "negation"
    CORRECTION = "correction"
    PREFERENCE = "preference"


class TimeScope(StrEnum):
    CURRENT = "current"
    PAST = "past"
    FUTURE = "future"
    HYPOTHETICAL = "hypothetical"
    UNKNOWN = "unknown"


class Typicality(StrEnum):
    TYPICAL = "typical"
    OCCASIONAL = "occasional"
    EXCEPTION = "exception"
    UNKNOWN = "unknown"


class Polarity(StrEnum):
    AFFIRMED = "affirmed"
    DENIED = "denied"
    UNCERTAIN = "uncertain"


class Importance(StrEnum):
    EXPLICIT_CORE = "explicit_core"
    EXPLICIT_SUPPORTING = "explicit_supporting"
    NOT_STATED = "not_stated"


class Ownership(StrEnum):
    OWNER = "owner"
    SHARED = "shared"
    ASSISTS = "assists"
    RECEIVES = "receives"
    NOT_RESPONSIBLE = "not_responsible"
    UNKNOWN = "unknown"


class FrequencyUnit(StrEnum):
    PER_DAY = "per_day"
    PER_WEEK = "per_week"
    PER_MONTH = "per_month"
    PER_QUARTER = "per_quarter"
    PER_YEAR = "per_year"
    IRREGULAR = "irregular"
    UNKNOWN = "unknown"


class FrequencyQualifier(DomainModel):
    value: Annotated[Decimal, Field(ge=0)] | None = None
    unit: FrequencyUnit = FrequencyUnit.UNKNOWN
    verbatim: str | None = None

    @model_validator(mode="after")
    def numeric_value_has_a_numeric_unit(self) -> "FrequencyQualifier":
        if self.verbatim is not None and not self.verbatim.strip():
            raise ValueError("frequency verbatim cannot be blank")
        if self.value is not None and self.unit in {
            FrequencyUnit.UNKNOWN,
            FrequencyUnit.IRREGULAR,
        }:
            raise ValueError("numeric frequency requires a periodic unit")
        return self


class EvidenceQualifiers(DomainModel):
    time_scope: TimeScope = TimeScope.UNKNOWN
    typicality: Typicality = Typicality.UNKNOWN
    polarity: Polarity = Polarity.UNCERTAIN
    frequency: FrequencyQualifier = Field(default_factory=FrequencyQualifier)
    importance: Importance = Importance.NOT_STATED
    ownership: Ownership = Ownership.UNKNOWN


class EvidenceStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class Evidence(DomainModel):
    schema_version: Literal["evidence.v2"] = "evidence.v2"
    evidence_id: UUID
    session_id: UUID
    turn_id: UUID
    episode_id: UUID | None = None
    subject: EvidenceSubject
    kind: EvidenceKind
    claim: NonEmptyText
    quote: NonEmptyText
    span: QuoteSpan
    quote_match: QuoteMatch = QuoteMatch.EXACT
    normalization_version: Literal["quote_nfkc_ws.v1"] | None = None
    qualifiers: EvidenceQualifiers = Field(default_factory=EvidenceQualifiers)
    status: EvidenceStatus = EvidenceStatus.ACTIVE
    supersedes: tuple[UUID, ...] = ()
    superseded_by: UUID | None = None
    withdrawn_reason: str | None = None
    withdrawn_by_turn_id: UUID | None = None
    correction_target_unknown: bool = False
    extractor_operation_id: UUID

    @field_validator("claim", "quote")
    @classmethod
    def semantic_text_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("claim and quote cannot be blank")
        return value

    @model_validator(mode="after")
    def status_and_lineage_are_coherent(self) -> "Evidence":
        if len(self.supersedes) != len(set(self.supersedes)):
            raise ValueError("supersedes IDs must be unique")
        if self.evidence_id in self.supersedes:
            raise ValueError("evidence cannot supersede itself")
        if self.status == EvidenceStatus.SUPERSEDED and self.superseded_by is None:
            raise ValueError("superseded evidence requires superseded_by")
        if self.status != EvidenceStatus.SUPERSEDED and self.superseded_by is not None:
            raise ValueError("only superseded evidence may set superseded_by")
        if self.status == EvidenceStatus.WITHDRAWN:
            if self.withdrawn_reason is None or not self.withdrawn_reason.strip():
                raise ValueError("withdrawn evidence requires withdrawn_reason")
            if self.withdrawn_by_turn_id is None:
                raise ValueError("withdrawn evidence requires withdrawn_by_turn_id")
        elif self.withdrawn_reason is not None or self.withdrawn_by_turn_id is not None:
            raise ValueError("only withdrawn evidence may set withdrawal fields")
        if self.quote_match == QuoteMatch.NORMALIZED and self.normalization_version is None:
            raise ValueError("normalized quotes require normalization_version")
        if self.quote_match == QuoteMatch.EXACT and self.normalization_version is not None:
            raise ValueError("exact quotes cannot set normalization_version")
        if self.correction_target_unknown and self.kind != EvidenceKind.CORRECTION:
            raise ValueError("correction_target_unknown requires correction kind")
        if self.kind == EvidenceKind.CORRECTION and not (
            self.supersedes or self.correction_target_unknown
        ):
            raise ValueError("correction evidence requires a target or target_unknown")
        return self


class InferenceStatus(StrEnum):
    CANDIDATE = "candidate"
    CONFIRMED_BY_EMPLOYEE = "confirmed_by_employee"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    INSUFFICIENT = "insufficient"


class InferenceMethod(StrEnum):
    LLM = "llm"
    RULE = "rule"
    HUMAN = "human"


class Inference(DomainModel):
    schema_version: Literal["inference.v2"] = "inference.v2"
    inference_id: UUID
    session_id: UUID
    type: StableName
    statement: NonEmptyText
    supporting_evidence_ids: Annotated[tuple[UUID, ...], Field(min_length=1)]
    contradicting_evidence_ids: tuple[UUID, ...] = ()
    reference_urns: tuple[ReferenceUrn, ...] = ()
    status: InferenceStatus = InferenceStatus.CANDIDATE
    method: InferenceMethod
    operation_name: StableName
    operation_definition_hash: Sha256
    supersedes: tuple[UUID, ...] = ()
    superseded_by: UUID | None = None
    decision_evidence_id: UUID | None = None
    uncertainty_reason: str | None = None

    @model_validator(mode="after")
    def evidence_sets_are_valid(self) -> "Inference":
        if len(self.supporting_evidence_ids) != len(set(self.supporting_evidence_ids)):
            raise ValueError("supporting evidence IDs must be unique")
        if len(self.contradicting_evidence_ids) != len(set(self.contradicting_evidence_ids)):
            raise ValueError("contradicting evidence IDs must be unique")
        if set(self.supporting_evidence_ids) & set(self.contradicting_evidence_ids):
            raise ValueError("supporting and contradicting evidence must be disjoint")
        if len(self.supersedes) != len(set(self.supersedes)):
            raise ValueError("superseded inference IDs must be unique")
        if self.inference_id in self.supersedes:
            raise ValueError("inference cannot supersede itself")
        if self.status == InferenceStatus.SUPERSEDED and self.superseded_by is None:
            raise ValueError("superseded inference requires superseded_by")
        if self.status != InferenceStatus.SUPERSEDED and self.superseded_by is not None:
            raise ValueError("only superseded inference may set superseded_by")
        human_decided = self.status in {
            InferenceStatus.CONFIRMED_BY_EMPLOYEE,
            InferenceStatus.REJECTED,
        }
        if human_decided and self.decision_evidence_id is None:
            raise ValueError("employee-decided inference requires decision_evidence_id")
        if not human_decided and self.decision_evidence_id is not None:
            raise ValueError("only employee-decided inference may set decision_evidence_id")
        if (
            self.status == InferenceStatus.CONFIRMED_BY_EMPLOYEE
            and self.decision_evidence_id not in self.supporting_evidence_ids
        ):
            raise ValueError("confirmation evidence must support the inference")
        if (
            self.status == InferenceStatus.REJECTED
            and self.decision_evidence_id not in self.contradicting_evidence_ids
        ):
            raise ValueError("rejection evidence must contradict the inference")
        if self.uncertainty_reason is not None and not self.uncertainty_reason.strip():
            raise ValueError("uncertainty_reason cannot be blank")
        return self
