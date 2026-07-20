"""Logical key -> trial-scoped UUIDv5 mapping (V3-5 §6.3/§9.2).

Pure functions, no DB/network. Every trial derives a fully fresh identity set
from its ``trial_id``; case files never contain runtime UUIDs, so two trials of
the same case can never share tenant/session/run/turn/evidence rows.
"""

from __future__ import annotations

from uuid import UUID, uuid5

from app.interview_vnext.domain.base import DomainModel


class TrialScopedIds(DomainModel):
    """Fresh per-trial identity set (§6.3 logical identity mapping)."""

    trial_id: UUID
    tenant_id: UUID
    user_id: UUID
    profile_id: UUID
    session_id: UUID
    run_id: UUID
    operation_id: UUID


def trial_scoped_ids(trial_id: UUID) -> TrialScopedIds:
    return TrialScopedIds(
        trial_id=trial_id,
        tenant_id=uuid5(trial_id, "tenant"),
        user_id=uuid5(trial_id, "user"),
        profile_id=uuid5(trial_id, "profile"),
        session_id=uuid5(trial_id, "session"),
        run_id=uuid5(trial_id, "run"),
        operation_id=uuid5(trial_id, "operation/turn-interpret"),
    )


def turn_uuid(trial_id: UUID, turn_key: str) -> UUID:
    return uuid5(trial_id, f"turn/{turn_key}")


def episode_uuid(trial_id: UUID, episode_key: str) -> UUID:
    return uuid5(trial_id, f"episode/{episode_key}")


def prior_evidence_uuid(trial_id: UUID, evidence_key: str) -> UUID:
    return uuid5(trial_id, f"evidence/{evidence_key}")


def slot_uuid(batch_id: UUID, case_id: str, slot_index: int) -> UUID:
    """§9.2:slot_id = uuid5(batch_id, "case/<case_id>/slot/<1..3>")。"""

    if not 1 <= slot_index <= 3:
        raise ValueError("slot_index must be between 1 and 3")
    return uuid5(batch_id, f"case/{case_id}/slot/{slot_index}")


def trial_uuid(slot_id: UUID, trial_attempt: int) -> UUID:
    """§9.2:trial_id = uuid5(slot_id, "trial-attempt/<1..3>")。"""

    if not 1 <= trial_attempt <= 3:
        raise ValueError("trial_attempt must be between 1 and 3")
    return uuid5(slot_id, f"trial-attempt/{trial_attempt}")
