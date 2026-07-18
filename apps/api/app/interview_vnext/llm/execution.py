"""Normalized provider execution evidence(ADR 0036 D4;V3-5A §6.4)。

Adapter 對每次 attempt 保存 route/pipeline/cache/usage/cost 的 normalized facts,
即使 timeout/connection failure 也要建 evidence(已知欄位照填、未知欄位 null +
limitation)。Evidence 只描述「發生了什麼」;eligibility 由 application 的
conformance policy 判定,adapter 不得依 policy 刪 metadata 或把 inspected 改稱
clean。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.identifiers import (
    NonEmptyText,
    SemVer,
    Sha256,
    StableName,
)
from app.interview_vnext.observability.artifacts import ArtifactRef

from .result import TokenUsage


class TransformationStatus(StrEnum):
    CLEAN = "clean"
    INSPECTED = "inspected"
    MUTATED = "mutated"
    UNKNOWN = "unknown"


class CacheStatus(StrEnum):
    ABSENT = "absent"
    MISS = "miss"
    HIT = "hit"
    UNKNOWN = "unknown"


class ProviderPipelineStage(DomainModel):
    index: int = Field(ge=1)
    stage_type: NonEmptyText
    name: NonEmptyText | None = None
    status: NonEmptyText | None = None
    transformation_status: TransformationStatus
    details_hash: Sha256

    @model_validator(mode="after")
    def stage_is_never_clean(self) -> "ProviderPipelineStage":
        if self.transformation_status == TransformationStatus.CLEAN:
            raise ValueError("a present pipeline stage cannot be clean")
        return self


def derive_transformation_status(
    stages: tuple[ProviderPipelineStage, ...],
) -> TransformationStatus:
    """Non-empty stages 的整體狀態:unknown > mutated > inspected(§6.4)。"""

    statuses = {stage.transformation_status for stage in stages}
    if TransformationStatus.UNKNOWN in statuses:
        return TransformationStatus.UNKNOWN
    if TransformationStatus.MUTATED in statuses:
        return TransformationStatus.MUTATED
    return TransformationStatus.INSPECTED


_ROUTE_METADATA_FIELDS = (
    "gateway_resolved_model",
    "upstream_provider",
    "upstream_model",
    "upstream_endpoint",
    "route_strategy",
    "upstream_attempt_count",
)


class ProviderExecutionEvidenceDefinition(DomainModel):
    schema_version: Literal["provider_execution_evidence.v1"] = (
        "provider_execution_evidence.v1"
    )
    binding_id: StableName
    binding_hash: Sha256
    adapter_id: StableName
    adapter_version: SemVer
    gateway_provider: StableName
    requested_model: NonEmptyText
    gateway_resolved_model: NonEmptyText | None
    upstream_provider: NonEmptyText | None
    upstream_model: NonEmptyText | None
    upstream_endpoint: NonEmptyText | None
    route_strategy: NonEmptyText | None
    upstream_attempt_count: int | None = Field(default=None, ge=0)
    transformation_status: TransformationStatus
    pipeline_stages: tuple[ProviderPipelineStage, ...]
    cache_status: CacheStatus
    provider_request_id: str | None
    generation_id: str | None
    usage: TokenUsage
    cost_decimal: str | None
    limitations: tuple[NonEmptyText, ...]
    raw_routing_artifact: ArtifactRef | None

    @model_validator(mode="after")
    def evidence_is_canonical(self) -> "ProviderExecutionEvidenceDefinition":
        indices = tuple(stage.index for stage in self.pipeline_stages)
        if indices != tuple(range(1, len(indices) + 1)):
            raise ValueError("pipeline stage indices must be contiguous from 1")
        if self.pipeline_stages:
            if self.transformation_status == TransformationStatus.CLEAN:
                raise ValueError(
                    "clean transformation requires an empty pipeline"
                )
            derived = derive_transformation_status(self.pipeline_stages)
            if self.transformation_status != derived:
                raise ValueError(
                    "transformation status must match the pipeline stages"
                )
        elif self.transformation_status in (
            TransformationStatus.INSPECTED,
            TransformationStatus.MUTATED,
        ):
            raise ValueError(
                "inspected/mutated transformation requires pipeline stages; "
                "clean requires an empty pipeline"
            )
        if self.cost_decimal is not None:
            try:
                cost = Decimal(self.cost_decimal)
            except InvalidOperation as exc:
                raise ValueError("cost must be a decimal string") from exc
            if not cost.is_finite() or cost < 0:
                raise ValueError("cost must be a finite non-negative decimal")
            if format(cost, "f") != self.cost_decimal:
                raise ValueError("cost must use the canonical decimal string")
        if tuple(sorted(set(self.limitations))) != self.limitations:
            raise ValueError("limitations must be unique and sorted")
        missing_route = any(
            getattr(self, field_name) is None
            for field_name in _ROUTE_METADATA_FIELDS
        )
        if (missing_route or self.cost_decimal is None) and not self.limitations:
            raise ValueError(
                "missing route metadata or cost requires an explicit limitation"
            )
        return self


class ProviderExecutionEvidence(ProviderExecutionEvidenceDefinition):
    evidence_hash: Sha256

    @model_validator(mode="after")
    def hash_matches_definition(self) -> "ProviderExecutionEvidence":
        definition = ProviderExecutionEvidenceDefinition.model_validate(
            self.model_dump(exclude={"evidence_hash"})
        )
        if canonical_hash(definition) != self.evidence_hash:
            raise ValueError("provider execution evidence hash mismatch")
        return self


def define_provider_execution_evidence(**values) -> ProviderExecutionEvidence:
    definition = ProviderExecutionEvidenceDefinition(**values)
    return ProviderExecutionEvidence(
        **definition.model_dump(), evidence_hash=canonical_hash(definition)
    )
