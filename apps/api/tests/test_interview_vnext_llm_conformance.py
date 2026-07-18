"""V3-5A R2:execution evidence 與 attribution-strict conformance(§6.4/§6.6/§14.3)。

Evidence 只 normalize facts,不表達 eligibility;`attribution-strict/1.0.0` 由
application 對 (binding, evidence, wire outcome) 判定,unknown 一律 ineligible、
reason codes 固定排序、report hash-addressed 且不含 wall-clock 欄位。
"""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

import pytest
from pydantic import ValidationError

from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.llm.binding import define_provider_binding
from app.interview_vnext.llm.conformance import (
    ATTRIBUTION_STRICT_POLICY_V1,
    ConformanceReasonCode,
    ConformanceReport,
    evaluate_conformance,
)
from app.interview_vnext.llm.execution import (
    CacheStatus,
    ProviderExecutionEvidence,
    ProviderExecutionEvidenceDefinition,
    ProviderPipelineStage,
    TransformationStatus,
    define_provider_execution_evidence,
)
from app.interview_vnext.llm.operation import ContractIdentity
from app.interview_vnext.llm.result import ModelOutcome, TokenUsage
from app.interview_vnext.observability.artifacts import ArtifactRef


SHA = "sha256:" + "d" * 64


def make_binding():
    return define_provider_binding(
        binding_id="turn-interpret-c1-openrouter-attribution-strict",
        operation_name="turn.interpret",
        quality_profile="turn-interpret-c1-high-precision",
        adapter_id="openrouter.chat-completions",
        adapter_version="2.0.0",
        gateway_provider="openrouter",
        requested_model="anthropic/claude-sonnet-5",
        accepted_gateway_models=("anthropic/claude-sonnet-5",),
        upstream_provider="Anthropic",
        upstream_endpoint="anthropic",
        accepted_upstream_models=(
            "anthropic/claude-sonnet-5",
            "claude-sonnet-5-20250929",
        ),
        required_capabilities=(
            "routing-metadata",
            "single-choice",
            "structured-output.native-json-schema",
            "usage.cost",
            "usage.tokens",
        ),
        schema_projection_policy=ContractIdentity(
            name="portable-strict-output", version="2.0.0",
            content_hash="sha256:" + "1" * 64,
        ),
        conformance_policy=ContractIdentity(
            name="attribution-strict", version="1.0.0",
            content_hash=ATTRIBUTION_STRICT_POLICY_V1.policy_hash,
        ),
        storage_policy="stateless-no-provider-store",
        cache_policy="disabled",
        reasoning_policy="medium-excluded",
        data_collection_policy="deny",
        provider_config_hash="sha256:" + "3" * 64,
    )


def routing_artifact_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id=uuid5(NAMESPACE_URL, "conformance-test:routing"),
        kind="provider.openrouter.routing",
        media_type="application/json",
        content_hash=SHA,
        byte_size=64,
    )


def full_usage() -> TokenUsage:
    return TokenUsage(
        input_tokens=800, output_tokens=120, cache_read_tokens=0,
        cache_write_tokens=0, reasoning_tokens=0,
    )


def evidence_values(binding, **overrides) -> dict:
    values = dict(
        binding_id=binding.binding_id,
        binding_hash=binding.binding_hash,
        adapter_id=binding.adapter_id,
        adapter_version=binding.adapter_version,
        gateway_provider=binding.gateway_provider,
        requested_model=binding.requested_model,
        gateway_resolved_model=binding.requested_model,
        upstream_provider="Anthropic",
        upstream_model="claude-sonnet-5-20250929",
        upstream_endpoint="anthropic",
        route_strategy="direct",
        upstream_attempt_count=1,
        transformation_status=TransformationStatus.CLEAN,
        pipeline_stages=(),
        cache_status=CacheStatus.ABSENT,
        provider_request_id="req-0001",
        generation_id="gen-0001",
        usage=full_usage(),
        cost_decimal="0.001234",
        limitations=(),
        raw_routing_artifact=routing_artifact_ref(),
    )
    values.update(overrides)
    return values


def clean_evidence(binding, **overrides) -> ProviderExecutionEvidence:
    return define_provider_execution_evidence(**evidence_values(binding, **overrides))


def stage(
    index: int,
    status: TransformationStatus,
    *,
    stage_type: str = "moderation",
) -> ProviderPipelineStage:
    return ProviderPipelineStage(
        index=index,
        stage_type=stage_type,
        name="stage-name",
        status="completed",
        transformation_status=status,
        details_hash=SHA,
    )


# ── ProviderExecutionEvidence.v1(§6.4)──────────────────────────────────────


def test_evidence_hash_matches_definition_and_forgery_is_rejected():
    binding = make_binding()
    evidence = clean_evidence(binding)
    definition = ProviderExecutionEvidenceDefinition(**evidence_values(binding))
    assert evidence.evidence_hash == canonical_hash(definition)
    with pytest.raises(ValidationError, match="hash"):
        ProviderExecutionEvidence(
            **evidence_values(binding), evidence_hash="sha256:" + "0" * 64
        )


@pytest.mark.parametrize("indices", [(2,), (1, 3), (1, 1)])
def test_pipeline_stage_indices_must_be_contiguous_from_one(indices):
    binding = make_binding()
    stages = tuple(
        stage(index, TransformationStatus.INSPECTED) for index in indices
    )
    with pytest.raises(ValidationError, match="contiguous|sequential"):
        clean_evidence(
            binding,
            pipeline_stages=stages,
            transformation_status=TransformationStatus.INSPECTED,
        )


def test_clean_requires_an_empty_pipeline():
    binding = make_binding()
    with pytest.raises(ValidationError, match="clean"):
        clean_evidence(
            binding,
            pipeline_stages=(stage(1, TransformationStatus.INSPECTED),),
            transformation_status=TransformationStatus.CLEAN,
        )


@pytest.mark.parametrize(
    "stage_statuses,expected",
    [
        ((TransformationStatus.INSPECTED,), TransformationStatus.INSPECTED),
        (
            (TransformationStatus.INSPECTED, TransformationStatus.MUTATED),
            TransformationStatus.MUTATED,
        ),
        (
            (TransformationStatus.MUTATED, TransformationStatus.UNKNOWN),
            TransformationStatus.UNKNOWN,
        ),
    ],
)
def test_overall_transformation_status_is_derived_from_stages(
    stage_statuses, expected
):
    binding = make_binding()
    stages = tuple(
        stage(index, status) for index, status in enumerate(stage_statuses, 1)
    )
    evidence = clean_evidence(
        binding, pipeline_stages=stages, transformation_status=expected
    )
    assert evidence.transformation_status == expected
    wrong = (
        TransformationStatus.INSPECTED
        if expected != TransformationStatus.INSPECTED
        else TransformationStatus.MUTATED
    )
    with pytest.raises(ValidationError, match="transformation"):
        clean_evidence(
            binding, pipeline_stages=stages, transformation_status=wrong
        )


@pytest.mark.parametrize("cost", ["1e-3", "-0.5", "NaN", "Infinity", "abc", "00.5"])
def test_cost_must_be_a_canonical_non_negative_decimal_string(cost):
    binding = make_binding()
    with pytest.raises(ValidationError, match="cost"):
        clean_evidence(binding, cost_decimal=cost)


def test_missing_route_or_cost_requires_a_limitation():
    binding = make_binding()
    with pytest.raises(ValidationError, match="limitation"):
        clean_evidence(binding, gateway_resolved_model=None)
    with pytest.raises(ValidationError, match="limitation"):
        clean_evidence(binding, cost_decimal=None)
    evidence = clean_evidence(
        binding,
        cost_decimal=None,
        limitations=("cost not exposed by provider",),
    )
    assert evidence.cost_decimal is None


def test_limitations_must_be_unique_and_sorted():
    binding = make_binding()
    with pytest.raises(ValidationError, match="limitation"):
        clean_evidence(
            binding,
            cost_decimal=None,
            limitations=("z-limitation", "cost not exposed by provider"),
        )


def test_wire_failure_evidence_is_constructible_with_unknowns():
    binding = make_binding()
    evidence = clean_evidence(
        binding,
        gateway_resolved_model=None,
        upstream_provider=None,
        upstream_model=None,
        upstream_endpoint=None,
        route_strategy=None,
        upstream_attempt_count=None,
        transformation_status=TransformationStatus.UNKNOWN,
        cache_status=CacheStatus.UNKNOWN,
        provider_request_id=None,
        generation_id=None,
        usage=TokenUsage(limitations=("no usage after timeout",)),
        cost_decimal=None,
        limitations=(
            "cost unavailable after transport failure",
            "route metadata unavailable after transport failure",
        ),
        raw_routing_artifact=None,
    )
    assert evidence.transformation_status == TransformationStatus.UNKNOWN


# ── attribution-strict/1.0.0(§6.6)──────────────────────────────────────────


def test_clean_exact_execution_is_eligible():
    binding = make_binding()
    report = evaluate_conformance(
        policy=ATTRIBUTION_STRICT_POLICY_V1,
        binding=binding,
        evidence=clean_evidence(binding),
        wire_outcome=ModelOutcome.SUCCEEDED,
    )
    assert report.eligible is True
    assert report.reason_codes == ()
    assert report.policy_name == "attribution-strict"
    assert report.policy_version == "1.0.0"
    assert report.policy_hash == ATTRIBUTION_STRICT_POLICY_V1.policy_hash
    assert report.binding_id == binding.binding_id
    assert report.transformation_status == TransformationStatus.CLEAN
    definition_hash = canonical_hash(
        report.model_dump(exclude={"report_hash"})
    )
    assert report.report_hash == definition_hash


@pytest.mark.parametrize(
    "wire_outcome",
    [ModelOutcome.FAILED, ModelOutcome.REFUSED, ModelOutcome.INCOMPLETE],
)
def test_wire_not_succeeded_is_the_only_reason_for_failed_wire(wire_outcome):
    binding = make_binding()
    report = evaluate_conformance(
        policy=ATTRIBUTION_STRICT_POLICY_V1,
        binding=binding,
        evidence=clean_evidence(binding),
        wire_outcome=wire_outcome,
    )
    assert report.eligible is False
    assert report.reason_codes == (ConformanceReasonCode.WIRE_NOT_SUCCEEDED,)


@pytest.mark.parametrize(
    "overrides,expected",
    [
        (
            {"binding_hash": "sha256:" + "9" * 64},
            (ConformanceReasonCode.BINDING_MISMATCH,),
        ),
        (
            {"adapter_version": "9.9.9"},
            (ConformanceReasonCode.ADAPTER_MISMATCH,),
        ),
        (
            {"gateway_provider": "othergateway"},
            (ConformanceReasonCode.GATEWAY_MISMATCH,),
        ),
        (
            {"gateway_resolved_model": "anthropic/other-model"},
            (ConformanceReasonCode.GATEWAY_MODEL_MISMATCH,),
        ),
        (
            {
                "gateway_resolved_model": None,
                "limitations": ("resolved model absent",),
            },
            (ConformanceReasonCode.ROUTE_METADATA_MISSING,),
        ),
        (
            {"upstream_provider": "OpenAI"},
            (ConformanceReasonCode.UPSTREAM_PROVIDER_MISMATCH,),
        ),
        (
            {"upstream_endpoint": "anthropic-eu"},
            (ConformanceReasonCode.UPSTREAM_ENDPOINT_MISMATCH,),
        ),
        (
            {"upstream_model": "claude-haiku-4-5"},
            (ConformanceReasonCode.UPSTREAM_MODEL_MISMATCH,),
        ),
        (
            {"route_strategy": "fallback"},
            (ConformanceReasonCode.ROUTE_STRATEGY_MISMATCH,),
        ),
        (
            {"upstream_attempt_count": 0},
            (ConformanceReasonCode.UPSTREAM_ATTEMPT_MISMATCH,),
        ),
        (
            {"upstream_attempt_count": 2},
            (ConformanceReasonCode.UPSTREAM_ATTEMPT_MISMATCH,),
        ),
        (
            {"cache_status": CacheStatus.HIT},
            (ConformanceReasonCode.CACHE_INELIGIBLE,),
        ),
        (
            {"cache_status": CacheStatus.UNKNOWN},
            (ConformanceReasonCode.CACHE_INELIGIBLE,),
        ),
        (
            {"raw_routing_artifact": None},
            (ConformanceReasonCode.ROUTE_METADATA_MISSING,),
        ),
    ],
)
def test_single_dimension_violations_have_exact_reasons(overrides, expected):
    binding = make_binding()
    report = evaluate_conformance(
        policy=ATTRIBUTION_STRICT_POLICY_V1,
        binding=binding,
        evidence=clean_evidence(binding, **overrides),
        wire_outcome=ModelOutcome.SUCCEEDED,
    )
    assert report.eligible is False
    assert report.reason_codes == expected


@pytest.mark.parametrize(
    "pipeline_status",
    [
        TransformationStatus.INSPECTED,
        TransformationStatus.MUTATED,
        TransformationStatus.UNKNOWN,
    ],
)
def test_any_pipeline_stage_is_ineligible_even_if_only_inspected(pipeline_status):
    binding = make_binding()
    report = evaluate_conformance(
        policy=ATTRIBUTION_STRICT_POLICY_V1,
        binding=binding,
        evidence=clean_evidence(
            binding,
            pipeline_stages=(stage(1, pipeline_status),),
            transformation_status=pipeline_status,
        ),
        wire_outcome=ModelOutcome.SUCCEEDED,
    )
    assert report.eligible is False
    assert report.reason_codes == (
        ConformanceReasonCode.PIPELINE_NOT_EMPTY,
        ConformanceReasonCode.TRANSFORMATION_INELIGIBLE,
    )


def test_reason_codes_are_sorted_and_report_is_deterministic():
    binding = make_binding()
    evidence = clean_evidence(
        binding,
        gateway_resolved_model="anthropic/other-model",
        route_strategy="fallback",
        cache_status=CacheStatus.HIT,
        upstream_attempt_count=3,
    )
    first = evaluate_conformance(
        policy=ATTRIBUTION_STRICT_POLICY_V1,
        binding=binding,
        evidence=evidence,
        wire_outcome=ModelOutcome.SUCCEEDED,
    )
    second = evaluate_conformance(
        policy=ATTRIBUTION_STRICT_POLICY_V1,
        binding=binding,
        evidence=evidence,
        wire_outcome=ModelOutcome.SUCCEEDED,
    )
    assert first.report_hash == second.report_hash
    assert first.reason_codes == tuple(sorted(first.reason_codes))
    assert first.execution_evidence_hash == evidence.evidence_hash


def test_report_has_no_wall_clock_field_and_forged_hash_is_rejected():
    binding = make_binding()
    report = evaluate_conformance(
        policy=ATTRIBUTION_STRICT_POLICY_V1,
        binding=binding,
        evidence=clean_evidence(binding),
        wire_outcome=ModelOutcome.SUCCEEDED,
    )
    assert "checked_at" not in ConformanceReport.model_fields
    with pytest.raises(ValidationError, match="hash"):
        ConformanceReport.model_validate(
            {**report.model_dump(), "report_hash": "sha256:" + "0" * 64}
        )
