"""Immutable execution artifacts and an in-memory contract implementation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from threading import RLock
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.hashing import canonical_json
from app.interview_vnext.domain.identifiers import NonEmptyText, Sha256, StableName, UtcDatetime


class ArtifactStorage(StrEnum):
    INLINE = "inline"
    EXTERNAL = "external"


class RedactionStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    APPLIED = "applied"
    UNKNOWN = "unknown"


class ArtifactRef(DomainModel):
    """Portable pointer that always carries the content integrity fields."""

    artifact_id: UUID
    kind: StableName
    media_type: NonEmptyText
    schema_id: NonEmptyText | None = None
    content_hash: Sha256
    byte_size: int = Field(ge=0)


class ArtifactRecord(DomainModel):
    """Immutable artifact metadata plus exactly one storage location."""

    schema_version: Literal["execution_artifact.v1"] = "execution_artifact.v1"
    ref: ArtifactRef
    run_id: UUID
    session_id: UUID | None = None
    turn_id: UUID | None = None
    operation_id: UUID | None = None
    attempt_id: UUID | None = None
    created_at: UtcDatetime
    storage: ArtifactStorage
    inline_content: str | None = None
    external_uri: NonEmptyText | None = None
    retention_class: StableName = "standard"
    redaction_status: RedactionStatus = RedactionStatus.UNKNOWN
    contains_test_data: bool = False

    @model_validator(mode="after")
    def storage_location_is_exclusive(self) -> "ArtifactRecord":
        if self.storage == ArtifactStorage.INLINE:
            if self.inline_content is None or self.external_uri is not None:
                raise ValueError("inline artifact requires only inline_content")
            if _content_hash(self.inline_content) != self.ref.content_hash:
                raise ValueError("inline artifact content hash mismatch")
            if len(self.inline_content.encode("utf-8")) != self.ref.byte_size:
                raise ValueError("inline artifact byte size mismatch")
        elif self.external_uri is None or self.inline_content is not None:
            raise ValueError("external artifact requires only external_uri")
        return self


class ArtifactConflict(ValueError):
    """Raised when an existing immutable artifact ID is reused with new content."""


class ArtifactNotFound(KeyError):
    """Raised when a referenced artifact does not exist."""


class ArtifactStore(Protocol):
    def put(self, record: ArtifactRecord) -> ArtifactRecord: ...

    def get(self, artifact_id: UUID) -> ArtifactRecord: ...


def _content_hash(content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def canonical_artifact_content(payload: Any, *, media_type: str) -> str:
    """Return the exact UTF-8 content whose bytes are hashed and persisted."""

    if media_type == "application/json":
        if isinstance(payload, str):
            payload = json.loads(payload)
        return canonical_json(payload)
    if media_type.startswith("text/"):
        if not isinstance(payload, str):
            raise TypeError("text artifact payload must be a string")
        return payload
    if isinstance(payload, BaseModel):
        return canonical_json(payload)
    raise TypeError(f"unsupported inline artifact media type: {media_type}")


def build_inline_artifact(
    *,
    artifact_id: UUID,
    kind: str,
    media_type: str,
    payload: Any,
    run_id: UUID,
    created_at,
    schema_id: str | None = None,
    session_id: UUID | None = None,
    turn_id: UUID | None = None,
    operation_id: UUID | None = None,
    attempt_id: UUID | None = None,
    retention_class: str = "standard",
    redaction_status: RedactionStatus = RedactionStatus.UNKNOWN,
    contains_test_data: bool = False,
) -> ArtifactRecord:
    content = canonical_artifact_content(payload, media_type=media_type)
    ref = ArtifactRef(
        artifact_id=artifact_id,
        kind=kind,
        media_type=media_type,
        schema_id=schema_id,
        content_hash=_content_hash(content),
        byte_size=len(content.encode("utf-8")),
    )
    return ArtifactRecord(
        ref=ref,
        run_id=run_id,
        session_id=session_id,
        turn_id=turn_id,
        operation_id=operation_id,
        attempt_id=attempt_id,
        created_at=created_at,
        storage=ArtifactStorage.INLINE,
        inline_content=content,
        retention_class=retention_class,
        redaction_status=redaction_status,
        contains_test_data=contains_test_data,
    )


class InMemoryArtifactStore:
    """Thread-safe fake with the same immutable-ID semantics required of persistence."""

    def __init__(self, records: Mapping[UUID, ArtifactRecord] | None = None) -> None:
        self._records: dict[UUID, ArtifactRecord] = {}
        for artifact_id, record in (records or {}).items():
            validated = ArtifactRecord.model_validate(record.model_dump())
            if validated.storage == ArtifactStorage.EXTERNAL:
                raise ValueError("in-memory artifact store cannot verify external content")
            if artifact_id != validated.ref.artifact_id:
                raise ArtifactConflict("artifact mapping key does not match record ID")
            self._records[artifact_id] = validated
        self._lock = RLock()

    def put(self, record: ArtifactRecord) -> ArtifactRecord:
        record = ArtifactRecord.model_validate(record.model_dump())
        if record.storage == ArtifactStorage.EXTERNAL:
            raise ValueError("in-memory artifact store cannot verify external content")
        with self._lock:
            existing = self._records.get(record.ref.artifact_id)
            if existing is None:
                self._records[record.ref.artifact_id] = record
                return record
            if existing != record:
                raise ArtifactConflict(
                    f"artifact {record.ref.artifact_id} already exists with different content"
                )
            return existing

    def get(self, artifact_id: UUID) -> ArtifactRecord:
        with self._lock:
            try:
                return self._records[artifact_id]
            except KeyError as exc:
                raise ArtifactNotFound(str(artifact_id)) from exc

    def all(self) -> tuple[ArtifactRecord, ...]:
        with self._lock:
            return tuple(sorted(self._records.values(), key=lambda item: str(item.ref.artifact_id)))
