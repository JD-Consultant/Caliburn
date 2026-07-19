"""Strict scripted provider fake for application and recovery contract tests.

V3-5A §8.4:the scripted port consumes a ``ResolvedModelCall`` and returns a v2
``ModelCallEnvelope`` (wire result + execution evidence). By default it produces
an attribution-strict-eligible clean route bound to the call's binding; a step
may override ``execution_evidence`` to drive conformance-failure paths. The
default clean evidence is explicit (built here, referencing a scripted routing
artifact), never a silently-fabricated clean route.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import timedelta
from threading import RLock
from uuid import uuid5

from pydantic import Field

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.identifiers import NonEmptyText
from app.interview_vnext.observability.artifacts import (
    ArtifactRecord,
    ArtifactRef,
    build_inline_artifact,
)

from .binding import ProviderBinding, define_provider_binding
from .conformance import ATTRIBUTION_STRICT_POLICY_V1
from .execution import (
    CacheStatus,
    ProviderExecutionEvidence,
    TransformationStatus,
    define_provider_execution_evidence,
)
from .operation import ContractIdentity
from .portable_schema import PORTABLE_STRICT_OUTPUT_POLICY_V2
from .port import LlmPort, ModelCallEnvelope, ModelCallRequest, ResolvedModelCall
from .result import (
    FinishReason,
    ModelCallResult,
    ModelFailure,
    ModelOutcome,
    ModelRefusal,
    StructuredPayload,
    TokenUsage,
)


SCRIPTED_MODEL = "scripted-reference"
SCRIPTED_PROVIDER_CONFIG: dict = {
    "schema_version": "scripted_provider_config.v1",
    "adapter": "scripted",
}
SCRIPTED_ROUTING_KIND = "provider.scripted.routing"
SCRIPTED_ROUTING_LABEL = "artifact/scripted/routing/v1"


def scripted_provider_config() -> dict:
    return dict(SCRIPTED_PROVIDER_CONFIG)


def scripted_turn_binding(
    *,
    operation_name: str = "turn.interpret",
    binding_id: str = "turn-interpret-scripted",
) -> ProviderBinding:
    """A scripted binding whose policies match the active runtime policies."""

    return define_provider_binding(
        binding_id=binding_id,
        operation_name=operation_name,
        quality_profile="turn-interpret-scripted",
        adapter_id="scripted",
        adapter_version="1.0.0",
        gateway_provider="scripted",
        requested_model=SCRIPTED_MODEL,
        accepted_gateway_models=(SCRIPTED_MODEL,),
        upstream_provider="scripted",
        upstream_endpoint="scripted",
        accepted_upstream_models=(SCRIPTED_MODEL,),
        required_capabilities=(
            "routing-metadata",
            "single-choice",
            "structured-output.native-json-schema",
            "usage.cost",
            "usage.tokens",
        ),
        schema_projection_policy=ContractIdentity(
            name=PORTABLE_STRICT_OUTPUT_POLICY_V2.name,
            version=PORTABLE_STRICT_OUTPUT_POLICY_V2.version,
            content_hash=PORTABLE_STRICT_OUTPUT_POLICY_V2.policy_hash,
        ),
        conformance_policy=ContractIdentity(
            name=ATTRIBUTION_STRICT_POLICY_V1.name,
            version=ATTRIBUTION_STRICT_POLICY_V1.version,
            content_hash=ATTRIBUTION_STRICT_POLICY_V1.policy_hash,
        ),
        storage_policy="stateless-no-provider-store",
        cache_policy="disabled",
        reasoning_policy="excluded",
        data_collection_policy="deny",
        provider_config_hash=canonical_hash(SCRIPTED_PROVIDER_CONFIG),
    )


def scripted_execution_evidence(
    binding: ProviderBinding,
    *,
    usage: TokenUsage,
    raw_routing_artifact: ArtifactRef,
    provider_request_id: str | None = None,
    generation_id: str | None = None,
    cost_decimal: str | None = "0",
) -> ProviderExecutionEvidence:
    """A clean, attribution-strict-eligible evidence bound to ``binding``."""

    return define_provider_execution_evidence(
        binding_id=binding.binding_id,
        binding_hash=binding.binding_hash,
        adapter_id=binding.adapter_id,
        adapter_version=binding.adapter_version,
        gateway_provider=binding.gateway_provider,
        requested_model=binding.requested_model,
        gateway_resolved_model=binding.accepted_gateway_models[0],
        upstream_provider=binding.upstream_provider,
        upstream_model=binding.accepted_upstream_models[0],
        upstream_endpoint=binding.upstream_endpoint,
        route_strategy="direct",
        upstream_attempt_count=1,
        transformation_status=TransformationStatus.CLEAN,
        pipeline_stages=(),
        cache_status=CacheStatus.ABSENT,
        provider_request_id=provider_request_id,
        generation_id=generation_id,
        usage=usage,
        cost_decimal=cost_decimal,
        limitations=(),
        raw_routing_artifact=raw_routing_artifact,
    )


class ScriptedStep(DomainModel):
    expected_attempt: int = Field(ge=1)
    outcome: ModelOutcome
    finish_reason: FinishReason
    resolved_model: NonEmptyText | None = None
    provider_request_id: str | None = None
    provider_conversation_id: str | None = None
    provider_finish_reason: str | None = None
    parsed_output: StructuredPayload | None = None
    visible_response_artifact: ArtifactRef | None = None
    supporting_artifacts: tuple[ArtifactRecord, ...] = ()
    refusal: ModelRefusal | None = None
    failure: ModelFailure | None = None
    usage: TokenUsage
    latency_ms: int = Field(default=1, ge=0)
    execution_evidence: ProviderExecutionEvidence | None = None


class ScriptedLlmPort(LlmPort):
    """Consumes one declared step per operation call and records resolved calls."""

    def __init__(
        self,
        scripts: Mapping[str, Iterable[ScriptedStep]],
    ) -> None:
        self._scripts = {name: tuple(steps) for name, steps in scripts.items()}
        self._positions: dict[str, int] = defaultdict(int)
        self._calls: list[ResolvedModelCall] = []
        self._lock = RLock()

    @property
    def calls(self) -> tuple[ResolvedModelCall, ...]:
        with self._lock:
            return tuple(self._calls)

    @property
    def requests(self) -> tuple[ModelCallRequest, ...]:
        with self._lock:
            return tuple(call.request for call in self._calls)

    def assert_exhausted(self) -> None:
        remaining = {
            name: len(steps) - self._positions[name]
            for name, steps in self._scripts.items()
            if len(steps) != self._positions[name]
        }
        if remaining:
            raise AssertionError(f"scripted LLM responses remain: {remaining}")

    async def generate_structured(self, call: ResolvedModelCall) -> ModelCallEnvelope:
        request = call.request
        binding = call.binding
        with self._lock:
            try:
                steps = self._scripts[request.operation_name]
            except KeyError as exc:
                raise AssertionError(
                    f"unexpected LLM operation: {request.operation_name}"
                ) from exc
            position = self._positions[request.operation_name]
            if position >= len(steps):
                raise AssertionError(
                    f"script exhausted for operation: {request.operation_name}"
                )
            step = steps[position]
            if request.attempt != step.expected_attempt:
                raise AssertionError(
                    f"expected attempt {step.expected_attempt}, got {request.attempt}"
                )
            self._positions[request.operation_name] += 1
            self._calls.append(call)

        completed_at = request.created_at + timedelta(milliseconds=step.latency_ms)
        result = ModelCallResult(
            run_id=request.run_id,
            session_id=request.session_id,
            turn_id=request.turn_id,
            operation_id=request.operation_id,
            attempt_id=request.attempt_id,
            attempt=request.attempt,
            operation_name=request.operation_name,
            operation_definition_hash=request.operation_definition_hash,
            binding_id=binding.binding_id,
            binding_hash=binding.binding_hash,
            gateway_provider=binding.gateway_provider,
            requested_model=binding.requested_model,
            resolved_model=step.resolved_model or binding.requested_model,
            provider_request_id=step.provider_request_id,
            provider_conversation_id=step.provider_conversation_id,
            outcome=step.outcome,
            finish_reason=step.finish_reason,
            provider_finish_reason=step.provider_finish_reason,
            parsed_output=step.parsed_output,
            visible_response_artifact=step.visible_response_artifact,
            refusal=step.refusal,
            failure=step.failure,
            usage=step.usage,
            latency_ms=step.latency_ms,
            started_at=request.created_at,
            completed_at=completed_at,
            prompt_hash=request.prompt_hash,
            output_schema_id=request.output_schema_id,
            output_schema_hash=request.output_schema_hash,
            context_hash=request.context_hash,
        )
        if step.execution_evidence is not None:
            return ModelCallEnvelope(
                result=result,
                execution_evidence=step.execution_evidence,
                supporting_artifacts=step.supporting_artifacts,
            )
        routing = build_inline_artifact(
            artifact_id=uuid5(request.attempt_id, SCRIPTED_ROUTING_LABEL),
            kind=SCRIPTED_ROUTING_KIND,
            media_type="application/json",
            payload={
                "schema_version": "scripted_routing.v1",
                "strategy": "direct",
                "upstream_attempt_count": 1,
            },
            run_id=request.run_id,
            session_id=request.session_id,
            turn_id=request.turn_id,
            operation_id=request.operation_id,
            attempt_id=request.attempt_id,
            created_at=completed_at,
            contains_test_data=True,
        )
        evidence = scripted_execution_evidence(
            binding,
            usage=step.usage,
            raw_routing_artifact=routing.ref,
            provider_request_id=step.provider_request_id,
        )
        return ModelCallEnvelope(
            result=result,
            execution_evidence=evidence,
            supporting_artifacts=(*step.supporting_artifacts, routing),
        )
