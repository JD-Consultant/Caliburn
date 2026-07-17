"""Strict scripted provider fake for application and recovery contract tests."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import timedelta
from threading import RLock

from pydantic import Field

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.identifiers import NonEmptyText
from app.interview_vnext.observability.artifacts import ArtifactRecord, ArtifactRef

from .port import LlmPort, ModelCallEnvelope, ModelCallRequest
from .result import (
    FinishReason,
    ModelCallResult,
    ModelFailure,
    ModelOutcome,
    ModelRefusal,
    StructuredPayload,
    TokenUsage,
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


class ScriptedLlmPort(LlmPort):
    """Consumes one declared step per operation call and records immutable requests."""

    def __init__(
        self,
        scripts: Mapping[str, Iterable[ScriptedStep]],
    ) -> None:
        self._scripts = {name: tuple(steps) for name, steps in scripts.items()}
        self._positions: dict[str, int] = defaultdict(int)
        self._requests: list[ModelCallRequest] = []
        self._lock = RLock()

    @property
    def requests(self) -> tuple[ModelCallRequest, ...]:
        with self._lock:
            return tuple(self._requests)

    def assert_exhausted(self) -> None:
        remaining = {
            name: len(steps) - self._positions[name]
            for name, steps in self._scripts.items()
            if len(steps) != self._positions[name]
        }
        if remaining:
            raise AssertionError(f"scripted LLM responses remain: {remaining}")

    async def generate_structured(self, request: ModelCallRequest) -> ModelCallEnvelope:
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
            self._requests.append(request)

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
            provider=request.provider,
            requested_model=request.requested_model,
            resolved_model=step.resolved_model or request.requested_model,
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
        return ModelCallEnvelope(
            result=result,
            supporting_artifacts=step.supporting_artifacts,
        )
