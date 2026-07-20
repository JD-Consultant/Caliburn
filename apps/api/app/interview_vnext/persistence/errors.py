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


class ExternalArtifactStoreUnavailable(PersistenceError):
    """V2-B only accepts inline artifact writes; external needs a verifying store."""

    code = "external_artifact_store_unavailable"
