"""Provider-neutral structured generation request and port."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.identifiers import NonEmptyText, Sha256, StableName, UtcDatetime
from app.interview_vnext.observability.artifacts import ArtifactRef

from .result import ModelCallResult


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ModelMessage(DomainModel):
    role: MessageRole
    text: NonEmptyText


class ModelCallRequest(DomainModel):
    schema_version: Literal["model_call_request.v1"] = "model_call_request.v1"
    run_id: UUID
    session_id: UUID
    turn_id: UUID | None = None
    operation_id: UUID
    attempt_id: UUID
    attempt: int = Field(ge=1)
    operation_name: StableName
    operation_definition_hash: Sha256
    idempotency_key: NonEmptyText
    provider: StableName
    requested_model: NonEmptyText
    quality_profile: StableName
    instructions: NonEmptyText
    messages: tuple[ModelMessage, ...]
    prompt_artifact: ArtifactRef
    output_schema_id: NonEmptyText
    output_schema_artifact: ArtifactRef
    context_artifact: ArtifactRef
    selection_manifest_artifact: ArtifactRef
    deadline_at: UtcDatetime
    created_at: UtcDatetime
    max_output_tokens: int = Field(ge=1)

    @model_validator(mode="after")
    def request_is_executable(self) -> "ModelCallRequest":
        if not self.messages:
            raise ValueError("model request requires at least one message")
        if self.messages[0].role != MessageRole.USER:
            raise ValueError("model request must start with a user message")
        if any(
            previous.role == current.role
            for previous, current in zip(self.messages, self.messages[1:], strict=False)
        ):
            raise ValueError("model request messages must alternate user and assistant roles")
        if self.messages[-1].role != MessageRole.USER:
            raise ValueError("model request must end with a user message")
        if self.deadline_at <= self.created_at:
            raise ValueError("model request deadline must be after creation")
        return self

    @property
    def prompt_hash(self) -> str:
        return self.prompt_artifact.content_hash

    @property
    def output_schema_hash(self) -> str:
        return self.output_schema_artifact.content_hash

    @property
    def context_hash(self) -> str:
        return self.context_artifact.content_hash


class LlmPort(Protocol):
    async def generate_structured(self, request: ModelCallRequest) -> ModelCallResult: ...
