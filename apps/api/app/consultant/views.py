"""Read-only projections from framework-owned consultant checkpoints."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from app.consultant.state import (
    ApprovedJobDocument,
    DurableModel,
    ConsultantThreadState,
)


class ConsultantSnapshot(DurableModel):
    document_id: UUID
    revision: int = Field(ge=0)
    source_count: int = Field(ge=0)
    latest_source_id: UUID | None = None
    source_supersessions: dict[UUID, UUID] = Field(default_factory=dict)
    interview_work: dict[str, dict] = Field(default_factory=dict)
    understanding: dict[str, dict] = Field(default_factory=dict)
    gaps: dict[str, dict] = Field(default_factory=dict)
    review_queue: dict[str, dict] = Field(default_factory=dict)
    approved_document: ApprovedJobDocument
    required_clarification: dict | None = None
    latest_run: dict | None = None


def snapshot_from_state(state: ConsultantThreadState) -> ConsultantSnapshot:
    if not state or "document_id" not in state:
        raise ValueError("consultant thread state is empty")
    return ConsultantSnapshot.model_validate(
        {
            "document_id": state["document_id"],
            "revision": state.get("revision", 0),
            "source_count": state.get("source_count", 0),
            "latest_source_id": state.get("latest_source_id"),
            "source_supersessions": state.get("source_supersessions", {}),
            "interview_work": state.get("interview_work", {}),
            "understanding": state.get("understanding", {}),
            "gaps": state.get("gaps", {}),
            "review_queue": state.get("review_queue", {}),
            "approved_document": state["approved_document"],
            "required_clarification": state.get("required_clarification"),
            "latest_run": state.get("latest_run"),
        }
    )
