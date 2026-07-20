"""Single source for canonical text ↔ Pydantic conversion (V2-B reference §4.2).

Every repository dump/load goes through here so no adapter invents its own JSON
handling. Writes: Pydantic validate → ``canonical_json()`` → hash. Reads:
``json.loads`` → strict Pydantic validation → recompute canonical text/hash and
compare with what the row claims. Any mismatch — canonical text, hash, or a
normalized identity column — is ``PersistedDataCorruption``; loads never
tolerate unknown fields, backfill defaults, or repair timestamps.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.observability.artifacts import ArtifactRecord, ArtifactRef
from app.interview_vnext.observability.checkpoint import OperationCheckpoint
from app.interview_vnext.observability.events import ExecutionEvent

from .errors import PersistedDataCorruption


def dump_model(model: DomainModel) -> str:
    """Exact canonical UTF-8 text whose bytes are hashed and persisted as TEXT."""

    return canonical_json(model)


def _validated(model_type: type, text: str, label: str, **ids: object) -> Any:
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise PersistedDataCorruption(
            f"persisted {label} is not valid JSON", **ids
        ) from exc
    try:
        return model_type.model_validate(payload)
    except ValidationError as exc:
        raise PersistedDataCorruption(
            f"persisted {label} failed strict validation", **ids
        ) from exc


def _require_canonical(model: DomainModel, text: str, label: str, **ids: object) -> None:
    if canonical_json(model) != text:
        raise PersistedDataCorruption(
            f"persisted {label} text is not the canonical serialization", **ids
        )


def load_state(
    text: str,
    expected_hash: str,
    *,
    session_id: UUID | None = None,
    state_version: int | None = None,
) -> InterviewState:
    """Hydrate ``InterviewState`` and verify canonical text, hash, and the
    normalized row identity the caller already read (§6.4 dual check)."""

    state: InterviewState = _validated(InterviewState, text, "interview state",
                                       session_id=session_id)
    ids = {"session_id": state.session.session_id}
    _require_canonical(state, text, "interview state", **ids)
    if canonical_hash(state) != expected_hash:
        raise PersistedDataCorruption("interview state hash mismatch", **ids)
    if session_id is not None and state.session.session_id != session_id:
        raise PersistedDataCorruption(
            "interview state nested session identity does not match row",
            row_session_id=session_id, **ids)
    if state_version is not None and state.session.state_version != state_version:
        raise PersistedDataCorruption(
            "interview state nested version does not match row state_version",
            row_state_version=state_version, **ids)
    return state


def load_event(
    text: str,
    expected_hash: str,
    *,
    event_id: UUID | None = None,
    run_id: UUID | None = None,
    sequence: int | None = None,
) -> ExecutionEvent:
    event: ExecutionEvent = _validated(ExecutionEvent, text, "execution event",
                                       event_id=event_id)
    ids = {"event_id": event.event_id, "run_id": event.run_id}
    _require_canonical(event, text, "execution event", **ids)
    if event.event_hash != expected_hash:
        raise PersistedDataCorruption("execution event hash mismatch", **ids)
    if event_id is not None and event.event_id != event_id:
        raise PersistedDataCorruption(
            "execution event identity does not match row event_id",
            row_event_id=event_id, **ids)
    if run_id is not None and event.run_id != run_id:
        raise PersistedDataCorruption(
            "execution event run does not match row run_id", row_run_id=run_id, **ids)
    if sequence is not None and event.sequence != sequence:
        raise PersistedDataCorruption(
            "execution event sequence does not match row sequence",
            row_sequence=sequence, **ids)
    return event


def load_checkpoint(
    text: str,
    *,
    operation_id: UUID | None = None,
    revision: int | None = None,
) -> OperationCheckpoint:
    checkpoint: OperationCheckpoint = _validated(
        OperationCheckpoint, text, "operation checkpoint", operation_id=operation_id)
    ids = {"operation_id": checkpoint.operation_id,
           "checkpoint_id": checkpoint.checkpoint_id}
    _require_canonical(checkpoint, text, "operation checkpoint", **ids)
    if operation_id is not None and checkpoint.operation_id != operation_id:
        raise PersistedDataCorruption(
            "checkpoint operation identity does not match row operation_id",
            row_operation_id=operation_id, **ids)
    if revision is not None and checkpoint.revision != revision:
        raise PersistedDataCorruption(
            "checkpoint nested revision does not match row revision",
            row_revision=revision, **ids)
    return checkpoint


def load_artifact(row: Any) -> ArtifactRecord:
    """Rebuild an ``ArtifactRecord`` from a §5.3-shaped row (duck-typed columns).
    The Pydantic validator re-verifies inline content hash/byte size, so a
    tampered ``inline_content`` or hash column surfaces as corruption here."""

    ids = {"artifact_id": getattr(row, "artifact_id", None)}
    try:
        ref = ArtifactRef(
            artifact_id=row.artifact_id,
            kind=row.kind,
            media_type=row.media_type,
            schema_id=row.schema_id,
            content_hash=row.content_hash,
            byte_size=row.byte_size,
        )
        return ArtifactRecord(
            schema_version=row.record_schema_version,
            ref=ref,
            run_id=row.run_id,
            session_id=row.session_id,
            turn_id=row.turn_id,
            operation_id=row.operation_id,
            attempt_id=row.attempt_id,
            created_at=row.created_at,
            storage=row.storage,
            inline_content=row.inline_content,
            external_uri=row.external_uri,
            retention_class=row.retention_class,
            redaction_status=row.redaction_status,
            contains_test_data=row.contains_test_data,
        )
    except ValidationError as exc:
        raise PersistedDataCorruption(
            "persisted artifact row failed strict validation", **ids
        ) from exc
