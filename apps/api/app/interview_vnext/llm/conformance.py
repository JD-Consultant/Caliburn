"""Application-owned conformance policy(ADR 0036 D2/D4/D5;V3-5A §6.6)。

Adapter 保存 normalized execution evidence,application 再依 binding 與該 evidence
判定「此結果是否可用於指定用途」。`attribution-strict/1.0.0`:exact
model/provider/endpoint、direct、upstream attempt 1、pipeline empty、cache
absent/miss;任何 unknown 都 ineligible。這裡沒有 provider parser——只讀已 normalize
的 facts,fail closed。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.identifiers import SemVer, Sha256, StableName

from .binding import ProviderBinding
from .execution import (
    CacheStatus,
    ProviderExecutionEvidence,
    TransformationStatus,
)
from .operation import ContractIdentity
from .result import ModelOutcome


class ConformanceReasonCode(StrEnum):
    ADAPTER_MISMATCH = "conformance.adapter_mismatch"
    BINDING_MISMATCH = "conformance.binding_mismatch"
    CACHE_INELIGIBLE = "conformance.cache_ineligible"
    GATEWAY_MISMATCH = "conformance.gateway_mismatch"
    GATEWAY_MODEL_MISMATCH = "conformance.gateway_model_mismatch"
    PIPELINE_NOT_EMPTY = "conformance.pipeline_not_empty"
    ROUTE_METADATA_MISSING = "conformance.route_metadata_missing"
    ROUTE_STRATEGY_MISMATCH = "conformance.route_strategy_mismatch"
    TRANSFORMATION_INELIGIBLE = "conformance.transformation_ineligible"
    UPSTREAM_ATTEMPT_MISMATCH = "conformance.upstream_attempt_mismatch"
    UPSTREAM_ENDPOINT_MISMATCH = "conformance.upstream_endpoint_mismatch"
    UPSTREAM_MODEL_MISMATCH = "conformance.upstream_model_mismatch"
    UPSTREAM_PROVIDER_MISMATCH = "conformance.upstream_provider_mismatch"
    WIRE_NOT_SUCCEEDED = "conformance.wire_not_succeeded"


class ConformancePolicyDefinition(DomainModel):
    schema_version: Literal["conformance_policy.v1"] = "conformance_policy.v1"
    name: StableName
    version: SemVer
    require_route_strategy_direct: Literal[True] = True
    require_single_upstream_attempt: Literal[True] = True
    require_empty_pipeline: Literal[True] = True
    eligible_cache_statuses: tuple[CacheStatus, ...] = (
        CacheStatus.ABSENT,
        CacheStatus.MISS,
    )

    @model_validator(mode="after")
    def cache_statuses_are_canonical(self) -> "ConformancePolicyDefinition":
        values = self.eligible_cache_statuses
        if len(values) != len(set(values)):
            raise ValueError("eligible cache statuses must be unique")
        if any(
            status in (CacheStatus.HIT, CacheStatus.UNKNOWN) for status in values
        ):
            raise ValueError("strict cache eligibility excludes hit/unknown")
        return self


class ConformancePolicy(ConformancePolicyDefinition):
    policy_hash: Sha256

    @model_validator(mode="after")
    def hash_matches_definition(self) -> "ConformancePolicy":
        definition = ConformancePolicyDefinition.model_validate(
            self.model_dump(exclude={"policy_hash"})
        )
        if canonical_hash(definition) != self.policy_hash:
            raise ValueError("conformance policy hash mismatch")
        return self


def define_conformance_policy(**values) -> ConformancePolicy:
    definition = ConformancePolicyDefinition(**values)
    return ConformancePolicy(
        **definition.model_dump(), policy_hash=canonical_hash(definition)
    )


ATTRIBUTION_STRICT_POLICY_V1 = define_conformance_policy(
    name="attribution-strict",
    version="1.0.0",
)


class ConformanceReportDefinition(DomainModel):
    schema_version: Literal["provider_conformance_report.v1"] = (
        "provider_conformance_report.v1"
    )
    policy_name: StableName
    policy_version: SemVer
    policy_hash: Sha256
    binding_id: StableName
    binding_hash: Sha256
    execution_evidence_hash: Sha256
    wire_outcome: ModelOutcome
    eligible: bool
    reason_codes: tuple[ConformanceReasonCode, ...]
    transformation_status: TransformationStatus

    @model_validator(mode="after")
    def report_is_coherent(self) -> "ConformanceReportDefinition":
        if tuple(sorted(set(self.reason_codes))) != self.reason_codes:
            raise ValueError("conformance reason codes must be unique and sorted")
        if self.eligible and self.reason_codes:
            raise ValueError("an eligible report cannot carry reason codes")
        if not self.eligible and not self.reason_codes:
            raise ValueError("an ineligible report requires at least one reason code")
        return self


class ConformanceReport(ConformanceReportDefinition):
    report_hash: Sha256

    @model_validator(mode="after")
    def hash_matches_definition(self) -> "ConformanceReport":
        definition = ConformanceReportDefinition.model_validate(
            self.model_dump(exclude={"report_hash"})
        )
        if canonical_hash(definition) != self.report_hash:
            raise ValueError("conformance report hash mismatch")
        return self


def _attribution_strict_reasons(
    *,
    policy: ConformancePolicy,
    binding: ProviderBinding,
    evidence: ProviderExecutionEvidence,
) -> list[ConformanceReasonCode]:
    reasons: set[ConformanceReasonCode] = set()

    if (
        evidence.binding_id != binding.binding_id
        or evidence.binding_hash != binding.binding_hash
    ):
        reasons.add(ConformanceReasonCode.BINDING_MISMATCH)
    if (
        evidence.adapter_id != binding.adapter_id
        or evidence.adapter_version != binding.adapter_version
    ):
        reasons.add(ConformanceReasonCode.ADAPTER_MISMATCH)
    if evidence.gateway_provider != binding.gateway_provider:
        reasons.add(ConformanceReasonCode.GATEWAY_MISMATCH)

    if evidence.gateway_resolved_model is None:
        reasons.add(ConformanceReasonCode.ROUTE_METADATA_MISSING)
    elif evidence.gateway_resolved_model not in binding.accepted_gateway_models:
        reasons.add(ConformanceReasonCode.GATEWAY_MODEL_MISMATCH)

    if evidence.upstream_provider is None:
        reasons.add(ConformanceReasonCode.ROUTE_METADATA_MISSING)
    elif evidence.upstream_provider != binding.upstream_provider:
        reasons.add(ConformanceReasonCode.UPSTREAM_PROVIDER_MISMATCH)

    if evidence.upstream_endpoint is None:
        reasons.add(ConformanceReasonCode.ROUTE_METADATA_MISSING)
    elif evidence.upstream_endpoint != binding.upstream_endpoint:
        reasons.add(ConformanceReasonCode.UPSTREAM_ENDPOINT_MISMATCH)

    if evidence.upstream_model is None:
        reasons.add(ConformanceReasonCode.ROUTE_METADATA_MISSING)
    elif evidence.upstream_model not in binding.accepted_upstream_models:
        reasons.add(ConformanceReasonCode.UPSTREAM_MODEL_MISMATCH)

    if evidence.route_strategy is None:
        reasons.add(ConformanceReasonCode.ROUTE_METADATA_MISSING)
    elif evidence.route_strategy != "direct":
        reasons.add(ConformanceReasonCode.ROUTE_STRATEGY_MISMATCH)

    if evidence.upstream_attempt_count is None:
        reasons.add(ConformanceReasonCode.ROUTE_METADATA_MISSING)
    elif evidence.upstream_attempt_count != 1:
        reasons.add(ConformanceReasonCode.UPSTREAM_ATTEMPT_MISMATCH)

    if evidence.pipeline_stages:
        reasons.add(ConformanceReasonCode.PIPELINE_NOT_EMPTY)
    if evidence.transformation_status != TransformationStatus.CLEAN:
        reasons.add(ConformanceReasonCode.TRANSFORMATION_INELIGIBLE)

    if evidence.cache_status not in policy.eligible_cache_statuses:
        reasons.add(ConformanceReasonCode.CACHE_INELIGIBLE)

    if evidence.raw_routing_artifact is None:
        reasons.add(ConformanceReasonCode.ROUTE_METADATA_MISSING)

    return sorted(reasons)


class ConformanceMismatch(ValueError):
    """A conformance policy identity or persisted report does not exactly match."""


# 已核准的 conformance policies;unknown identity 一律 fail closed(§6.3)。
_CONFORMANCE_POLICY_REGISTRY: tuple[ConformancePolicy, ...] = (
    ATTRIBUTION_STRICT_POLICY_V1,
)


def resolve_conformance_policy(identity: ContractIdentity) -> ConformancePolicy:
    """Resolve a binding's ``ContractIdentity`` to the exact registered policy."""

    for policy in _CONFORMANCE_POLICY_REGISTRY:
        if (
            identity.name == policy.name
            and identity.version == policy.version
            and identity.content_hash == policy.policy_hash
        ):
            return policy
    raise ConformanceMismatch(
        "conformance policy identity is not a registered active policy: "
        f"{identity.name}/{identity.version}/{identity.content_hash}"
    )


def require_conformance_report(
    *,
    policy: ConformancePolicy,
    binding: ProviderBinding,
    evidence: ProviderExecutionEvidence,
    wire_outcome: ModelOutcome,
    report: ConformanceReport,
) -> None:
    """Exact-validate a persisted report against a deterministic re-evaluation.

    §5.4:binding ID/hash、evidence hash、wire outcome 逐項 exact,之後重新
    `evaluate_conformance()` 並要求**完整 report equality**(Pydantic model
    equality,不只 `eligible`);自我 hash 合法但非重新評估結果的 report 一律拒絕。
    """

    if report.binding_id != binding.binding_id or report.binding_hash != binding.binding_hash:
        raise ConformanceMismatch(
            "conformance report binding identity does not match the binding"
        )
    if report.execution_evidence_hash != evidence.evidence_hash:
        raise ConformanceMismatch(
            "conformance report evidence hash does not match the execution evidence"
        )
    if report.wire_outcome != wire_outcome:
        raise ConformanceMismatch(
            "conformance report wire outcome does not match the result outcome"
        )
    if (
        report.policy_name != policy.name
        or report.policy_version != policy.version
        or report.policy_hash != policy.policy_hash
    ):
        raise ConformanceMismatch(
            "conformance report policy identity does not match the resolved policy"
        )
    expected = evaluate_conformance(
        policy=policy, binding=binding, evidence=evidence, wire_outcome=wire_outcome
    )
    if report != expected:
        raise ConformanceMismatch(
            "conformance report does not equal its deterministic re-evaluation"
        )


def evaluate_conformance(
    *,
    policy: ConformancePolicy,
    binding: ProviderBinding,
    evidence: ProviderExecutionEvidence,
    wire_outcome: ModelOutcome,
) -> ConformanceReport:
    """Deterministically decide eligibility from a binding and normalized evidence.

    wire 非 ``succeeded`` 時只回 ``wire_not_succeeded``;wire succeeded 才逐項檢查
    attribution。executor 的 retry 分類先看 wire failure,conformance 不改
    retryability(§6.6)。
    """

    if wire_outcome != ModelOutcome.SUCCEEDED:
        reasons: tuple[ConformanceReasonCode, ...] = (
            ConformanceReasonCode.WIRE_NOT_SUCCEEDED,
        )
    else:
        reasons = tuple(
            _attribution_strict_reasons(
                policy=policy, binding=binding, evidence=evidence
            )
        )
    definition = ConformanceReportDefinition(
        policy_name=policy.name,
        policy_version=policy.version,
        policy_hash=policy.policy_hash,
        binding_id=binding.binding_id,
        binding_hash=binding.binding_hash,
        execution_evidence_hash=evidence.evidence_hash,
        wire_outcome=wire_outcome,
        eligible=not reasons,
        reason_codes=reasons,
        transformation_status=evidence.transformation_status,
    )
    return ConformanceReport(
        **definition.model_dump(), report_hash=canonical_hash(definition)
    )
