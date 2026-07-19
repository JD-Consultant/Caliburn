"""Provider-neutral execution events, taxonomies, and hash-chain validation."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.domain.identifiers import (
    NonEmptyText,
    SemVer,
    Sha256,
    StableName,
    UtcDatetime,
)

from .artifacts import ArtifactRef, ArtifactStore


class ExecutionStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class ExecutionTaxonomy(DomainModel):
    """Versioned allowlist; event fields remain open strings rather than Literals."""

    schema_version: Literal["execution_taxonomy.v1"] = "execution_taxonomy.v1"
    taxonomy_id: StableName
    version: SemVer
    event_types: tuple[StableName, ...]
    stages: tuple[StableName, ...]

    @model_validator(mode="after")
    def entries_are_unique_and_sorted(self) -> "ExecutionTaxonomy":
        for label, values in (("event_types", self.event_types), ("stages", self.stages)):
            if not values:
                raise ValueError(f"{label} cannot be empty")
            if tuple(sorted(set(values))) != values:
                raise ValueError(f"{label} must be unique and lexicographically sorted")
        return self

    @property
    def identity(self) -> str:
        return f"{self.taxonomy_id}.v{self.version.split('.', 1)[0]}"

    @property
    def content_hash(self) -> str:
        return canonical_hash(self)

    def validate_names(self, *, event_type: str, stage: str) -> None:
        if event_type not in self.event_types:
            raise ValueError(f"event type is not registered in {self.identity}: {event_type}")
        if stage not in self.stages:
            raise ValueError(f"stage is not registered in {self.identity}: {stage}")


class ExecutionEventBody(DomainModel):
    event_schema_version: Literal["execution_event.v1"] = "execution_event.v1"
    event_id: UUID
    occurred_at: UtcDatetime
    architecture_id: StableName
    workflow_version: SemVer
    taxonomy_id: StableName
    taxonomy_version: SemVer
    taxonomy_hash: Sha256
    run_id: UUID
    session_id: UUID | None = None
    turn_id: UUID | None = None
    operation_id: UUID | None = None
    parent_operation_id: UUID | None = None
    attempt_id: UUID | None = None
    event_type: StableName
    stage: StableName
    attempt: int | None = Field(default=None, ge=1)
    status: ExecutionStatus
    sequence: int = Field(ge=1)
    previous_event_hash: Sha256 | None = None
    input_artifacts: tuple[ArtifactRef, ...] = ()
    output_artifacts: tuple[ArtifactRef, ...] = ()
    state_before_hash: Sha256 | None = None
    state_after_hash: Sha256 | None = None
    metadata_json: str = "{}"

    @field_validator("metadata_json")
    @classmethod
    def metadata_is_canonical_json_object(cls, value: str) -> str:
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("metadata_json must encode an object")
        canonical = canonical_json(parsed)
        if value != canonical:
            raise ValueError("metadata_json must use canonical JSON")
        return value

    @model_validator(mode="after")
    def sequence_links_previous_hash(self) -> "ExecutionEventBody":
        if self.sequence == 1 and self.previous_event_hash is not None:
            raise ValueError("first execution event cannot have previous_event_hash")
        if self.sequence > 1 and self.previous_event_hash is None:
            raise ValueError("non-first execution event requires previous_event_hash")
        if self.attempt is None and self.attempt_id is not None:
            raise ValueError("attempt_id requires attempt")
        if self.attempt is not None and self.attempt_id is None:
            raise ValueError("attempt requires attempt_id")
        if self.attempt is not None and self.operation_id is None:
            raise ValueError("attempt requires operation_id")
        return self


class ExecutionEvent(ExecutionEventBody):
    event_hash: Sha256

    @model_validator(mode="after")
    def event_hash_matches_body(self) -> "ExecutionEvent":
        body = ExecutionEventBody.model_validate(self.model_dump(exclude={"event_hash"}))
        if canonical_hash(body) != self.event_hash:
            raise ValueError("execution event hash mismatch")
        return self


def build_execution_event(body: ExecutionEventBody) -> ExecutionEvent:
    return ExecutionEvent(**body.model_dump(), event_hash=canonical_hash(body))


class RunManifest(DomainModel):
    schema_version: Literal["capture_run_manifest.v1"] = "capture_run_manifest.v1"
    architecture_id: StableName
    workflow_version: SemVer
    taxonomy_id: StableName
    taxonomy_version: SemVer
    taxonomy_hash: Sha256
    run_id: UUID
    session_id: UUID | None = None
    started_at: UtcDatetime
    completed_at: UtcDatetime
    event_count: int = Field(ge=1)
    first_event_hash: Sha256
    last_event_hash: Sha256
    root_artifacts: tuple[ArtifactRef, ...] = ()
    limitations: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def completion_is_not_before_start(self) -> "RunManifest":
        if self.completed_at < self.started_at:
            raise ValueError("run manifest completed_at cannot precede started_at")
        if len({ref.artifact_id for ref in self.root_artifacts}) != len(self.root_artifacts):
            raise ValueError("run manifest root artifact IDs must be unique")
        if tuple(sorted(set(self.limitations))) != self.limitations:
            raise ValueError("run manifest limitations must be unique and sorted")
        return self


def validate_event_chain(
    events: tuple[ExecutionEvent, ...],
    *,
    taxonomy: ExecutionTaxonomy,
    artifact_store: ArtifactStore | None = None,
    manifest: RunManifest | None = None,
) -> None:
    if not events:
        raise ValueError("execution event chain cannot be empty")
    validated_events = tuple(
        ExecutionEvent.model_validate(event.model_dump()) for event in events
    )
    first = validated_events[0]
    previous_hash: str | None = None
    seen_event_ids: set[UUID] = set()
    for expected_sequence, event in enumerate(validated_events, start=1):
        if event.event_id in seen_event_ids:
            raise ValueError(f"duplicate execution event ID: {event.event_id}")
        seen_event_ids.add(event.event_id)
        if event.sequence != expected_sequence:
            raise ValueError("execution event sequence is not contiguous")
        if event.previous_event_hash != previous_hash:
            raise ValueError("execution event previous hash mismatch")
        if event.run_id != first.run_id or event.session_id != first.session_id:
            raise ValueError("execution event identity changed inside one chain")
        if (
            event.taxonomy_id != taxonomy.taxonomy_id
            or event.taxonomy_version != taxonomy.version
            or event.taxonomy_hash != taxonomy.content_hash
        ):
            raise ValueError("execution event taxonomy identity mismatch")
        taxonomy.validate_names(event_type=event.event_type, stage=event.stage)
        if artifact_store is not None:
            for ref in (*event.input_artifacts, *event.output_artifacts):
                stored = artifact_store.get(ref.artifact_id)
                if stored.ref != ref:
                    raise ValueError(f"artifact reference mismatch: {ref.artifact_id}")
        previous_hash = event.event_hash

    if manifest is not None:
        if manifest.run_id != first.run_id or manifest.session_id != first.session_id:
            raise ValueError("run manifest identity mismatch")
        if (
            manifest.architecture_id != first.architecture_id
            or manifest.workflow_version != first.workflow_version
            or manifest.taxonomy_id != taxonomy.taxonomy_id
            or manifest.taxonomy_version != taxonomy.version
        ):
            raise ValueError("run manifest architecture or taxonomy identity mismatch")
        if manifest.event_count != len(validated_events):
            raise ValueError("run manifest event count mismatch")
        if manifest.first_event_hash != validated_events[0].event_hash:
            raise ValueError("run manifest first hash mismatch")
        if manifest.last_event_hash != validated_events[-1].event_hash:
            raise ValueError("run manifest last hash mismatch")
        if manifest.taxonomy_hash != taxonomy.content_hash:
            raise ValueError("run manifest taxonomy hash mismatch")
        if artifact_store is not None:
            for ref in manifest.root_artifacts:
                stored = artifact_store.get(ref.artifact_id)
                if stored.ref != ref:
                    raise ValueError(
                        f"root artifact reference mismatch: {ref.artifact_id}"
                    )
