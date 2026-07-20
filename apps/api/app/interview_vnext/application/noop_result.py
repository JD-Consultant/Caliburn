"""Typed domain outcome for a verified operation that intentionally mutates no state."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.identifiers import Sha256, StableName
from app.interview_vnext.observability.artifacts import ArtifactRef


OPERATION_NOOP_RESULT_SCHEMA_ID = (
    "https://caliburn.local/schemas/operation-noop-result.v1.schema.json"
)


class OperationNoopResult(DomainModel):
    """A successful verified operation whose accepted proposal set is empty."""

    schema_version: Literal["operation_noop_result.v1"] = "operation_noop_result.v1"
    operation_id: UUID
    completion_event_id: UUID
    reason_code: StableName
    state_before_hash: Sha256
    state_after_hash: Sha256
    accepted_count: Literal[0] = 0
    dropped_count: int = Field(ge=0)
    verification_artifact: ArtifactRef

    @model_validator(mode="after")
    def state_is_unchanged(self) -> "OperationNoopResult":
        if self.state_after_hash != self.state_before_hash:
            raise ValueError("no-op result requires identical before/after state hashes")
        return self
