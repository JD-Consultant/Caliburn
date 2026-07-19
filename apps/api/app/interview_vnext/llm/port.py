"""Provider-neutral structured generation request, resolved call and port (v2).

V3-5A §6.3/§6.5:caller 不再自由填 provider/model。composition root 或 eval
wiring 先解析唯一 `ProviderBinding`,executor 把 binding snapshot 與 schema
projection 存成 immutable artifacts,再建 `ResolvedModelCall` 交給 adapter;
adapter 回 `ModelCallEnvelope`(wire result + normalized execution evidence)。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.identifiers import NonEmptyText, Sha256, StableName, UtcDatetime
from app.interview_vnext.observability.artifacts import ArtifactRecord, ArtifactRef

from .binding import ProviderBinding
from .execution import ProviderExecutionEvidence
from .portable_schema import SchemaProjectionReport
from .result import ModelCallResult


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ModelMessage(DomainModel):
    role: MessageRole
    text: NonEmptyText


class ModelCallRequest(DomainModel):
    schema_version: Literal["model_call_request.v2"] = "model_call_request.v2"
    run_id: UUID
    session_id: UUID
    turn_id: UUID | None = None
    operation_id: UUID
    attempt_id: UUID
    attempt: int = Field(ge=1)
    operation_name: StableName
    operation_definition_hash: Sha256
    idempotency_key: NonEmptyText
    binding_id: StableName
    binding_hash: Sha256
    requested_model: NonEmptyText
    instructions: NonEmptyText
    messages: tuple[ModelMessage, ...]
    prompt_artifact: ArtifactRef
    output_schema_id: NonEmptyText
    output_schema_artifact: ArtifactRef
    context_artifact: ArtifactRef
    selection_manifest_artifact: ArtifactRef
    binding_artifact: ArtifactRef
    provider_config_artifact: ArtifactRef
    schema_projection_artifact: ArtifactRef
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


class ResolvedModelCall(DomainModel):
    """The immutable, fully-resolved call an adapter executes.

    caller 解析唯一 binding 後打包 request + binding + schema projection;
    adapter 只能照這裡執行,不得自行選 fallback 或改 model。fresh-process
    recovery 從 request 的 artifact refs 讀回這些 object,不重呼叫 resolver。
    """

    schema_version: Literal["resolved_model_call.v1"] = "resolved_model_call.v1"
    request: ModelCallRequest
    binding: ProviderBinding
    schema_projection: SchemaProjectionReport

    @model_validator(mode="after")
    def call_is_internally_consistent(self) -> "ResolvedModelCall":
        request, binding, projection = self.request, self.binding, self.schema_projection
        if (
            request.binding_id != binding.binding_id
            or request.binding_hash != binding.binding_hash
        ):
            raise ValueError("resolved call request/binding identity mismatch")
        if request.requested_model != binding.requested_model:
            raise ValueError("resolved call request model does not match binding")
        if request.operation_name != binding.operation_name:
            raise ValueError("resolved call operation does not match binding")
        if request.binding_artifact.content_hash != canonical_hash(binding):
            raise ValueError("binding artifact content hash does not match the binding")
        if request.schema_projection_artifact.content_hash != canonical_hash(projection):
            raise ValueError(
                "schema projection artifact content hash does not match the report"
            )
        if request.provider_config_artifact.content_hash != binding.provider_config_hash:
            raise ValueError(
                "provider config artifact content hash does not match the binding config hash"
            )
        if projection.projected_schema_hash != request.output_schema_hash:
            raise ValueError("projected schema hash does not match the request output schema")
        if projection.target_profile != binding.schema_projection_policy.name and (
            projection.policy_name != binding.schema_projection_policy.name
        ):
            raise ValueError("schema projection policy does not match the binding")
        return self


class ModelCallEnvelope(DomainModel):
    """Normalized result, its execution evidence and every referenced artifact."""

    schema_version: Literal["model_call_envelope.v2"] = "model_call_envelope.v2"
    result: ModelCallResult
    execution_evidence: ProviderExecutionEvidence
    supporting_artifacts: tuple[ArtifactRecord, ...]

    @model_validator(mode="after")
    def refs_exist_and_scope_matches_result(self) -> "ModelCallEnvelope":
        artifact_ids = tuple(
            item.ref.artifact_id for item in self.supporting_artifacts
        )
        if len(set(artifact_ids)) != len(artifact_ids):
            raise ValueError("model envelope supporting artifact IDs must be unique")
        by_ref = {item.ref: item for item in self.supporting_artifacts}
        required = tuple(
            ref
            for ref in (
                self.result.visible_response_artifact,
                self.result.failure.error_artifact if self.result.failure else None,
                self.execution_evidence.raw_routing_artifact,
            )
            if ref is not None
        )
        if any(ref not in by_ref for ref in required):
            raise ValueError("model envelope is missing a referenced supporting artifact")
        for record in self.supporting_artifacts:
            if (
                record.run_id != self.result.run_id
                or record.session_id != self.result.session_id
                or record.turn_id != self.result.turn_id
                or record.operation_id != self.result.operation_id
                or record.attempt_id != self.result.attempt_id
            ):
                raise ValueError("model envelope artifact scope does not match result")
        evidence = self.execution_evidence
        if (
            evidence.binding_id != self.result.binding_id
            or evidence.binding_hash != self.result.binding_hash
        ):
            raise ValueError("execution evidence binding does not match result")
        if evidence.gateway_provider != self.result.gateway_provider:
            raise ValueError("execution evidence gateway provider does not match result")
        if evidence.requested_model != self.result.requested_model:
            raise ValueError("execution evidence requested model does not match result")
        if (
            evidence.gateway_resolved_model is not None
            and evidence.gateway_resolved_model != self.result.resolved_model
        ):
            raise ValueError("execution evidence resolved model does not match result")
        return self


class LlmPort(Protocol):
    async def generate_structured(self, call: ResolvedModelCall) -> ModelCallEnvelope: ...
