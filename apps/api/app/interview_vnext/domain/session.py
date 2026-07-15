"""Interview session aggregate metadata and legal lifecycle states."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from .base import DomainModel
from .identifiers import NonEmptyText, SemVer, UtcDatetime


ARCHITECTURE_ID = "interview-vnext-evidence-workflow"


class SessionStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    PAUSED = "paused"
    FINISHING = "finishing"
    COMPLETED = "completed"
    FAILED = "failed"


TERMINAL_SESSION_STATUSES = frozenset({SessionStatus.COMPLETED, SessionStatus.FAILED})


class InterviewSession(DomainModel):
    schema_version: Literal["interview_session.v1"] = "interview_session.v1"
    session_id: UUID
    profile_id: UUID
    tenant_id: UUID
    architecture_id: Literal["interview-vnext-evidence-workflow"] = ARCHITECTURE_ID
    workflow_version: SemVer
    status: SessionStatus = SessionStatus.PLANNED
    state_version: int = Field(default=0, ge=0)
    active_episode_id: UUID | None = None
    turn_count: int = Field(default=0, ge=0)
    stop_reason: str | None = None
    reference_snapshot_id: NonEmptyText
    created_at: UtcDatetime
    updated_at: UtcDatetime

    @model_validator(mode="after")
    def lifecycle_fields_are_coherent(self) -> "InterviewSession":
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        if self.stop_reason is not None and not self.stop_reason.strip():
            raise ValueError("stop_reason cannot be blank")
        if self.status in TERMINAL_SESSION_STATUSES and self.stop_reason is None:
            raise ValueError("terminal sessions require stop_reason")
        if self.status == SessionStatus.COMPLETED and self.active_episode_id is not None:
            raise ValueError("completed sessions cannot retain an active episode")
        return self


LEGAL_SESSION_TRANSITIONS: dict[SessionStatus, frozenset[SessionStatus]] = {
    SessionStatus.PLANNED: frozenset({SessionStatus.ACTIVE, SessionStatus.FAILED}),
    SessionStatus.ACTIVE: frozenset(
        {SessionStatus.PAUSED, SessionStatus.FINISHING, SessionStatus.FAILED}
    ),
    SessionStatus.PAUSED: frozenset(
        {SessionStatus.ACTIVE, SessionStatus.FINISHING, SessionStatus.FAILED}
    ),
    SessionStatus.FINISHING: frozenset({SessionStatus.COMPLETED, SessionStatus.FAILED}),
    SessionStatus.COMPLETED: frozenset(),
    SessionStatus.FAILED: frozenset(),
}


def session_at(
    *,
    session_id: UUID,
    profile_id: UUID,
    tenant_id: UUID,
    workflow_version: str,
    reference_snapshot_id: str,
    now: datetime,
) -> InterviewSession:
    """Create a planned session without hiding its required identifiers."""

    return InterviewSession(
        session_id=session_id,
        profile_id=profile_id,
        tenant_id=tenant_id,
        workflow_version=workflow_version,
        reference_snapshot_id=reference_snapshot_id,
        created_at=now,
        updated_at=now,
    )
