"""Durable operation checkpoint contract and explicit transition functions."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.identifiers import NonEmptyText, Sha256, StableName, UtcDatetime

from .artifacts import ArtifactRef


class CheckpointStatus(StrEnum):
    PREPARED = "prepared"
    CALLING = "calling"
    PROVIDER_COMPLETED = "provider_completed"
    VERIFIED = "verified"
    COMMITTED = "committed"
    FAILED = "failed"


class OperationCheckpoint(DomainModel):
    schema_version: Literal["operation_checkpoint.v1"] = "operation_checkpoint.v1"
    checkpoint_id: UUID
    run_id: UUID
    session_id: UUID
    turn_id: UUID | None = None
    operation_id: UUID
    operation_name: StableName
    operation_definition_hash: Sha256
    idempotency_key: NonEmptyText
    status: CheckpointStatus = CheckpointStatus.PREPARED
    revision: int = Field(default=0, ge=0)
    request_artifact: ArtifactRef
    active_attempt_id: UUID | None = None
    active_attempt: int | None = Field(default=None, ge=1)
    attempt_result_artifacts: tuple[ArtifactRef, ...] = ()
    provider_result_artifact: ArtifactRef | None = None
    verification_artifact: ArtifactRef | None = None
    domain_result_artifact: ArtifactRef | None = None
    response_artifact: ArtifactRef | None = None
    failure_artifact: ArtifactRef | None = None
    failure_reason_code: StableName | None = None
    state_before_hash: Sha256
    state_after_hash: Sha256 | None = None
    created_at: UtcDatetime
    updated_at: UtcDatetime

    @model_validator(mode="after")
    def required_artifacts_match_status(self) -> "OperationCheckpoint":
        if self.updated_at < self.created_at:
            raise ValueError("checkpoint updated_at cannot precede created_at")
        if (self.active_attempt_id is None) != (self.active_attempt is None):
            raise ValueError("active attempt ID and number must be set together")
        if len({ref.artifact_id for ref in self.attempt_result_artifacts}) != len(
            self.attempt_result_artifacts
        ):
            raise ValueError("attempt result artifact IDs must be unique")
        if self.status == CheckpointStatus.PREPARED:
            if self.active_attempt_id is not None or self.attempt_result_artifacts:
                raise ValueError("prepared checkpoint cannot have attempt state")
        else:
            if self.active_attempt_id is None:
                raise ValueError("non-prepared checkpoint requires an active attempt")
            completed_attempts = len(self.attempt_result_artifacts)
            if self.status == CheckpointStatus.CALLING:
                if completed_attempts != self.active_attempt - 1:
                    raise ValueError("calling checkpoint must preserve every prior attempt result")
            elif completed_attempts != self.active_attempt:
                raise ValueError("non-calling checkpoint requires the active attempt result")
        if self.status in {
            CheckpointStatus.PROVIDER_COMPLETED,
            CheckpointStatus.VERIFIED,
            CheckpointStatus.COMMITTED,
        } and self.provider_result_artifact is None:
            raise ValueError("checkpoint status requires provider result artifact")
        if self.status in {CheckpointStatus.PREPARED, CheckpointStatus.CALLING}:
            if self.provider_result_artifact is not None:
                raise ValueError("checkpoint has provider result before provider completion")
        if self.provider_result_artifact is not None:
            if (
                not self.attempt_result_artifacts
                or self.attempt_result_artifacts[-1] != self.provider_result_artifact
            ):
                raise ValueError("provider result must be the final attempt result artifact")
        if self.status in {CheckpointStatus.VERIFIED, CheckpointStatus.COMMITTED}:
            if self.verification_artifact is None:
                raise ValueError("checkpoint status requires verification artifact")
        if self.status in {
            CheckpointStatus.PREPARED,
            CheckpointStatus.CALLING,
            CheckpointStatus.PROVIDER_COMPLETED,
        } and self.verification_artifact is not None:
            raise ValueError("checkpoint has verification before verified status")
        if self.status == CheckpointStatus.COMMITTED:
            if (
                self.domain_result_artifact is None
                or self.response_artifact is None
                or self.state_after_hash is None
            ):
                raise ValueError("committed checkpoint requires domain/response artifacts and state hash")
        elif (
            self.domain_result_artifact is not None
            or self.response_artifact is not None
            or self.state_after_hash is not None
        ):
            raise ValueError("only committed checkpoint may set domain outcome fields")
        if self.status == CheckpointStatus.FAILED:
            if self.failure_artifact is None or not (self.failure_reason_code or "").strip():
                raise ValueError("failed checkpoint requires failure artifact and reason code")
        elif self.failure_artifact is not None or self.failure_reason_code is not None:
            raise ValueError("only failed checkpoint may set failure fields")
        return self


class CheckpointTransitionError(ValueError):
    pass


def mark_calling(
    checkpoint: OperationCheckpoint,
    *,
    attempt_id: UUID,
    attempt: int,
    occurred_at,
) -> OperationCheckpoint:
    if checkpoint.status == CheckpointStatus.CALLING:
        if checkpoint.active_attempt_id == attempt_id and checkpoint.active_attempt == attempt:
            return checkpoint
        raise CheckpointTransitionError("checkpoint already calls another attempt")
    _require_status(checkpoint, CheckpointStatus.PREPARED)
    if attempt != 1:
        raise CheckpointTransitionError("first operation attempt must be 1")
    return _updated(
        checkpoint,
        occurred_at=occurred_at,
        status=CheckpointStatus.CALLING,
        active_attempt_id=attempt_id,
        active_attempt=attempt,
    )


def start_next_attempt(
    checkpoint: OperationCheckpoint,
    *,
    previous_attempt_result: ArtifactRef,
    attempt_id: UUID,
    attempt: int,
    occurred_at,
) -> OperationCheckpoint:
    """Persist one failed/incomplete attempt before activating the next one."""

    _require_status(checkpoint, CheckpointStatus.CALLING)
    assert checkpoint.active_attempt is not None
    if (
        checkpoint.active_attempt == attempt
        and checkpoint.active_attempt_id == attempt_id
        and checkpoint.attempt_result_artifacts
        and checkpoint.attempt_result_artifacts[-1] == previous_attempt_result
    ):
        return checkpoint
    if attempt != checkpoint.active_attempt + 1:
        raise CheckpointTransitionError("next attempt number must increment by one")
    if attempt_id == checkpoint.active_attempt_id:
        raise CheckpointTransitionError("next attempt requires a new attempt ID")
    if previous_attempt_result in checkpoint.attempt_result_artifacts:
        raise CheckpointTransitionError("attempt result artifact is already recorded")
    return _updated(
        checkpoint,
        occurred_at=occurred_at,
        active_attempt_id=attempt_id,
        active_attempt=attempt,
        attempt_result_artifacts=(
            *checkpoint.attempt_result_artifacts,
            previous_attempt_result,
        ),
    )


def mark_provider_completed(
    checkpoint: OperationCheckpoint,
    *,
    result_artifact: ArtifactRef,
    occurred_at,
) -> OperationCheckpoint:
    if checkpoint.status == CheckpointStatus.PROVIDER_COMPLETED:
        if checkpoint.provider_result_artifact == result_artifact:
            return checkpoint
        raise CheckpointTransitionError("checkpoint already has another provider result")
    _require_status(checkpoint, CheckpointStatus.CALLING)
    return _updated(
        checkpoint,
        occurred_at=occurred_at,
        status=CheckpointStatus.PROVIDER_COMPLETED,
        attempt_result_artifacts=(
            *checkpoint.attempt_result_artifacts,
            result_artifact,
        ),
        provider_result_artifact=result_artifact,
    )


def mark_verified(
    checkpoint: OperationCheckpoint,
    *,
    verification_artifact: ArtifactRef,
    occurred_at,
) -> OperationCheckpoint:
    if checkpoint.status == CheckpointStatus.VERIFIED:
        if checkpoint.verification_artifact == verification_artifact:
            return checkpoint
        raise CheckpointTransitionError("checkpoint already has another verification")
    _require_status(checkpoint, CheckpointStatus.PROVIDER_COMPLETED)
    return _updated(
        checkpoint,
        occurred_at=occurred_at,
        status=CheckpointStatus.VERIFIED,
        verification_artifact=verification_artifact,
    )


def mark_committed(
    checkpoint: OperationCheckpoint,
    *,
    domain_result_artifact: ArtifactRef,
    response_artifact: ArtifactRef,
    state_after_hash: str,
    occurred_at,
) -> OperationCheckpoint:
    if checkpoint.status == CheckpointStatus.COMMITTED:
        expected = (domain_result_artifact, response_artifact, state_after_hash)
        actual = (
            checkpoint.domain_result_artifact,
            checkpoint.response_artifact,
            checkpoint.state_after_hash,
        )
        if actual == expected:
            return checkpoint
        raise CheckpointTransitionError("checkpoint already committed another outcome")
    _require_status(checkpoint, CheckpointStatus.VERIFIED)
    return _updated(
        checkpoint,
        occurred_at=occurred_at,
        status=CheckpointStatus.COMMITTED,
        domain_result_artifact=domain_result_artifact,
        response_artifact=response_artifact,
        state_after_hash=state_after_hash,
    )


def mark_failed(
    checkpoint: OperationCheckpoint,
    *,
    failure_artifact: ArtifactRef,
    reason_code: str,
    occurred_at,
) -> OperationCheckpoint:
    if checkpoint.status == CheckpointStatus.FAILED:
        if (
            checkpoint.failure_artifact == failure_artifact
            and checkpoint.failure_reason_code == reason_code
        ):
            return checkpoint
        raise CheckpointTransitionError("checkpoint already failed for another reason")
    if checkpoint.status == CheckpointStatus.COMMITTED:
        raise CheckpointTransitionError("committed checkpoint is terminal")
    if checkpoint.status == CheckpointStatus.PREPARED:
        raise CheckpointTransitionError(
            "prepared checkpoint must record an attempt before terminal failure"
        )
    attempt_results = checkpoint.attempt_result_artifacts
    if checkpoint.status == CheckpointStatus.CALLING:
        attempt_results = (*attempt_results, failure_artifact)
    return _updated(
        checkpoint,
        occurred_at=occurred_at,
        status=CheckpointStatus.FAILED,
        attempt_result_artifacts=attempt_results,
        failure_artifact=failure_artifact,
        failure_reason_code=reason_code,
    )


def _require_status(checkpoint: OperationCheckpoint, expected: CheckpointStatus) -> None:
    if checkpoint.status != expected:
        raise CheckpointTransitionError(
            f"checkpoint transition requires {expected}, got {checkpoint.status}"
        )


def _updated(checkpoint: OperationCheckpoint, *, occurred_at, **changes) -> OperationCheckpoint:
    if occurred_at < checkpoint.updated_at:
        raise CheckpointTransitionError("checkpoint time cannot regress")
    candidate = checkpoint.model_copy(
        update={
            **changes,
            "revision": checkpoint.revision + 1,
            "updated_at": occurred_at,
        }
    )
    return OperationCheckpoint.model_validate(candidate.model_dump())
