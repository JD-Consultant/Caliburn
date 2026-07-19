"""Normalized result and failure semantics for all LLM providers."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.domain.identifiers import NonEmptyText, Sha256, StableName, UtcDatetime
from app.interview_vnext.observability.artifacts import ArtifactRef


class ModelOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    REFUSED = "refused"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


class FinishReason(StrEnum):
    COMPLETED = "completed"
    MAX_OUTPUT_TOKENS = "max_output_tokens"
    CONTEXT_WINDOW_EXCEEDED = "context_window_exceeded"
    STOP_SEQUENCE = "stop_sequence"
    TOOL_USE = "tool_use"
    PAUSED = "paused"
    SAFETY_REFUSAL = "safety_refusal"
    CANCELLED = "cancelled"
    PROVIDER_ERROR = "provider_error"
    UNKNOWN = "unknown"


class FailureKind(StrEnum):
    TRANSPORT_TIMEOUT = "transport_timeout"
    TRANSPORT_ERROR = "transport_error"
    RATE_LIMITED = "rate_limited"
    AUTHENTICATION_FAILED = "authentication_failed"
    INVALID_REQUEST = "invalid_request"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    CANCELLED = "cancelled"
    OUTPUT_SCHEMA_INVALID = "output_schema_invalid"
    OUTPUT_PARSE_FAILED = "output_parse_failed"
    RESOLVED_MODEL_MISMATCH = "resolved_model_mismatch"
    UNKNOWN_PROVIDER_FAILURE = "unknown_provider_failure"


class StructuredPayload(DomainModel):
    """Immutable canonical JSON returned after provider-level schema validation."""

    schema_id: NonEmptyText
    canonical_json: NonEmptyText
    content_hash: Sha256

    @field_validator("canonical_json")
    @classmethod
    def value_is_canonical_json(cls, value: str) -> str:
        parsed = json.loads(value)
        if canonical_json(parsed) != value:
            raise ValueError("structured payload must use canonical JSON")
        return value

    @model_validator(mode="after")
    def content_hash_matches(self) -> "StructuredPayload":
        if canonical_hash(json.loads(self.canonical_json)) != self.content_hash:
            raise ValueError("structured payload content hash mismatch")
        return self

    def load(self):
        """Return a fresh JSON value so callers cannot mutate the stored representation."""

        return json.loads(self.canonical_json)


def build_structured_payload(*, schema_id: str, value) -> StructuredPayload:
    content = canonical_json(value)
    return StructuredPayload(
        schema_id=schema_id,
        canonical_json=content,
        content_hash=canonical_hash(value),
    )


class TokenUsage(DomainModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cache_read_tokens: int | None = Field(default=None, ge=0)
    cache_write_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    limitations: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def missing_values_have_a_limitation(self) -> "TokenUsage":
        values = (
            self.input_tokens,
            self.output_tokens,
            self.cache_read_tokens,
            self.cache_write_tokens,
            self.reasoning_tokens,
        )
        if any(value is None for value in values) and not self.limitations:
            raise ValueError("null token usage requires at least one limitation")
        if tuple(sorted(set(self.limitations))) != self.limitations:
            raise ValueError("token usage limitations must be unique and sorted")
        return self


class ModelRefusal(DomainModel):
    reason_code: StableName
    safe_message: NonEmptyText
    provider_category: str | None = None


class ModelFailure(DomainModel):
    kind: FailureKind
    reason_code: StableName
    retryable: bool
    safe_message: NonEmptyText
    provider_error_code: str | None = None
    error_artifact: ArtifactRef | None = None


class ModelCallResult(DomainModel):
    schema_version: Literal["model_call_result.v2"] = "model_call_result.v2"
    run_id: UUID
    session_id: UUID
    turn_id: UUID | None = None
    operation_id: UUID
    attempt_id: UUID
    attempt: int = Field(ge=1)
    operation_name: StableName
    operation_definition_hash: Sha256
    binding_id: StableName
    binding_hash: Sha256
    gateway_provider: StableName
    requested_model: NonEmptyText
    resolved_model: NonEmptyText
    provider_request_id: str | None = None
    provider_conversation_id: str | None = None
    outcome: ModelOutcome
    finish_reason: FinishReason
    provider_finish_reason: str | None = None
    parsed_output: StructuredPayload | None = None
    visible_response_artifact: ArtifactRef | None = None
    refusal: ModelRefusal | None = None
    failure: ModelFailure | None = None
    usage: TokenUsage
    latency_ms: int = Field(ge=0)
    started_at: UtcDatetime
    completed_at: UtcDatetime
    prompt_hash: Sha256
    output_schema_id: NonEmptyText
    output_schema_hash: Sha256
    context_hash: Sha256

    @model_validator(mode="after")
    def outcome_fields_are_exclusive(self) -> "ModelCallResult":
        if self.completed_at < self.started_at:
            raise ValueError("model result completed_at cannot precede started_at")
        if self.parsed_output is not None:
            StructuredPayload.model_validate(self.parsed_output.model_dump())
            if self.parsed_output.schema_id != self.output_schema_id:
                raise ValueError("parsed output schema identity mismatch")
        if self.outcome == ModelOutcome.SUCCEEDED:
            if self.parsed_output is None or self.failure is not None or self.refusal is not None:
                raise ValueError("succeeded result requires only parsed_output")
            if self.finish_reason != FinishReason.COMPLETED:
                raise ValueError("succeeded result requires completed finish reason")
            if self.visible_response_artifact is None:
                raise ValueError("succeeded result requires visible response artifact")
        elif self.outcome == ModelOutcome.REFUSED:
            if self.refusal is None or self.parsed_output is not None or self.failure is not None:
                raise ValueError("refused result requires only refusal")
            if self.finish_reason != FinishReason.SAFETY_REFUSAL:
                raise ValueError("refused result requires safety_refusal finish reason")
            if self.visible_response_artifact is None:
                raise ValueError("refused result requires visible response artifact")
        elif self.outcome == ModelOutcome.INCOMPLETE:
            if self.parsed_output is not None or self.failure is not None or self.refusal is not None:
                raise ValueError("incomplete result cannot contain commit-ready output")
            if self.finish_reason in {FinishReason.COMPLETED, FinishReason.SAFETY_REFUSAL}:
                raise ValueError("incomplete result requires a non-terminal-completion reason")
            if self.visible_response_artifact is None:
                raise ValueError("incomplete result requires visible partial response artifact")
        elif self.failure is None or self.parsed_output is not None or self.refusal is not None:
            raise ValueError("failed result requires only failure")
        elif (
            self.failure.kind
            in {
                FailureKind.OUTPUT_SCHEMA_INVALID,
                FailureKind.OUTPUT_PARSE_FAILED,
                FailureKind.RESOLVED_MODEL_MISMATCH,
            }
            and self.visible_response_artifact is None
        ):
            raise ValueError("output-related failure requires visible response artifact")
        return self
