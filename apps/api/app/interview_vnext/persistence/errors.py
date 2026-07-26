"""Stable persistence adapter exceptions (V2-B reference §10).

Application code asserts on these types/codes only — never on SQLSTATE or
PostgreSQL constraint message text. Adapters translate named constraint /
SQLSTATE failures into exactly one of these, attaching the identifiers a log
line needs (tenant/session/run/operation IDs), never full transcripts.
"""

from __future__ import annotations

from typing import ClassVar


class PersistenceError(Exception):
    """Base class; ``code`` is the stable machine-readable identity."""

    code: ClassVar[str] = "persistence_error"

    def __init__(self, message: str, /, **identifiers: object) -> None:
        super().__init__(message)
        self.identifiers: dict[str, str] = {
            key: str(value) for key, value in identifiers.items() if value is not None
        }

    def __str__(self) -> str:  # log-friendly: code + message + scoped IDs
        base = super().__str__()
        if not self.identifiers:
            return f"[{self.code}] {base}"
        ids = ", ".join(f"{k}={v}" for k, v in sorted(self.identifiers.items()))
        return f"[{self.code}] {base} ({ids})"


class SessionNotFound(PersistenceError):
    """Tenant-scoped session does not exist."""

    code = "session_not_found"


class StateVersionConflict(PersistenceError):
    """Session CAS matched 0 rows and the command is not a duplicate."""

    code = "state_version_conflict"


class StateContextStale(PersistenceError):
    """The persisted state moved beyond the exact context shown to the model."""

    code = "state_context_stale"

    def __init__(
        self,
        message: str,
        /,
        *,
        expected_state_version: int,
        expected_state_hash: str,
        actual_state_version: int | None = None,
        actual_state_hash: str | None = None,
        **identifiers: object,
    ) -> None:
        super().__init__(
            message,
            expected_state_version=expected_state_version,
            expected_state_hash=expected_state_hash,
            actual_state_version=actual_state_version,
            actual_state_hash=actual_state_hash,
            **identifiers,
        )
        self.expected_state_version = expected_state_version
        self.expected_state_hash = expected_state_hash
        self.actual_state_version = actual_state_version
        self.actual_state_hash = actual_state_hash


class IdempotencyConflict(PersistenceError):
    """Same command ID / request key with a different canonical hash."""

    code = "idempotency_conflict"


class ArtifactConflict(PersistenceError):
    """Same artifact ID reused with a different full record."""

    code = "artifact_conflict"


class ArtifactNotFound(PersistenceError):
    """Required artifact ref missing, or ref metadata does not match the row."""

    code = "artifact_not_found"


class RunConflict(PersistenceError):
    """Run identity or terminal chain mismatch."""

    code = "run_conflict"


class ExecutionEventConflict(PersistenceError):
    """Event ID reused with a different logical payload."""

    code = "execution_event_conflict"


class CheckpointConflict(PersistenceError):
    """Checkpoint idempotency / revision / transition conflict."""

    code = "checkpoint_conflict"


class OutboxLeaseConflict(PersistenceError):
    """Lease owner / status / expiry precondition failed (0 rows)."""

    code = "outbox_lease_conflict"


class PersistedDataCorruption(PersistenceError):
    """Canonical JSON, Pydantic validation, hash, or normalized column mismatch.
    Never "repaired" on read — the row is evidence, surfacing beats guessing."""

    code = "persisted_data_corruption"


class UnsupportedPersistedSchemaVersion(PersistenceError):
    """The row is intact but written by a major version this build cannot read.

    Kept distinct from corruption on purpose: a well-formed ``interview_state.v2``
    row is not damaged data, and reporting it as corruption would hide a clean
    migration signal behind a data-integrity alarm (plan §8.1).
    """

    code = "unsupported_persisted_schema_version"

    def __init__(
        self,
        message: str,
        /,
        *,
        expected: str,
        actual: str | None,
        **identifiers: object,
    ) -> None:
        super().__init__(message, expected=expected, actual=actual, **identifiers)
        self.expected = expected
        self.actual = actual


class ExternalArtifactStoreUnavailable(PersistenceError):
    """V2-B only accepts inline artifact writes; external needs a verifying store."""

    code = "external_artifact_store_unavailable"
