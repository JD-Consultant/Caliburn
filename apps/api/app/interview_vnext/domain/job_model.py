"""Evidence-backed Candidate Job Model contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .base import DomainModel
from .evidence import EvidenceQualifiers
from .identifiers import NonEmptyText, ReferenceUrn, StableName


class CandidateKind(StrEnum):
    TASK = "task"
    OUTPUT = "output"
    KNOWLEDGE = "knowledge"
    SKILL = "skill"
    ABILITY = "ability"
    ATTITUDE = "attitude"
    BEHAVIOR_INDICATOR = "behavior_indicator"


class CandidateStatus(StrEnum):
    DRAFT = "draft"
    VERIFIED = "verified"
    INSUFFICIENT = "insufficient"
    CONFLICTED = "conflicted"
    PROJECTED = "projected"
    REJECTED = "rejected"
    ACCEPTED = "accepted"


class ThresholdSourceType(StrEnum):
    EMPLOYEE_EVIDENCE = "employee_evidence"
    APPROVED_POLICY = "approved_policy"
    HUMAN = "human"


class QuantitativeThreshold(DomainModel):
    expression: NonEmptyText
    source_type: ThresholdSourceType
    source_id: NonEmptyText
    evidence_id: UUID | None = None

    @model_validator(mode="after")
    def employee_threshold_has_evidence(self) -> "QuantitativeThreshold":
        if self.source_type == ThresholdSourceType.EMPLOYEE_EVIDENCE and self.evidence_id is None:
            raise ValueError("employee threshold requires evidence_id")
        return self


class CandidateJobItem(DomainModel):
    schema_version: Literal["candidate_job_item.v1"] = "candidate_job_item.v1"
    candidate_id: UUID
    session_id: UUID
    kind: CandidateKind
    statement: NonEmptyText
    evidence_ids: Annotated[tuple[UUID, ...], Field(min_length=1)]
    inference_ids: tuple[UUID, ...] = ()
    reference_urns: tuple[ReferenceUrn, ...] = ()
    qualifiers: EvidenceQualifiers = Field(default_factory=EvidenceQualifiers)
    thresholds: tuple[QuantitativeThreshold, ...] = ()
    status: CandidateStatus = CandidateStatus.DRAFT
    created_by_operation: StableName
    review_decision_id: UUID | None = None

    @field_validator("statement")
    @classmethod
    def statement_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("candidate statement cannot be blank")
        return value

    @model_validator(mode="after")
    def lineage_and_review_state_are_coherent(self) -> "CandidateJobItem":
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("candidate evidence IDs must be unique")
        if len(self.inference_ids) != len(set(self.inference_ids)):
            raise ValueError("candidate inference IDs must be unique")
        human_status = self.status in {CandidateStatus.ACCEPTED, CandidateStatus.REJECTED}
        if human_status and self.review_decision_id is None:
            raise ValueError("accepted/rejected candidate requires review_decision_id")
        if not human_status and self.review_decision_id is not None:
            raise ValueError("only accepted/rejected candidate may set review_decision_id")
        return self
