"""Deterministic LangGraph authority channel for consultant document facts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from app.consultant.state import (
    ApprovedJobDocument,
    ConsultantCommandContext,
    ConsultantThreadState,
    SourceReference,
    initial_thread_state,
)


class StaleThreadRevision(RuntimeError):
    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(f"expected revision {expected}, found {actual}")
        self.expected = expected
        self.actual = actual


def _require_document(
    state: ConsultantThreadState, document_id: UUID
) -> ConsultantThreadState:
    existing = state.get("document_id")
    if existing is None:
        raise RuntimeError("consultant thread has not been initialized")
    if existing != str(document_id):
        raise ValueError("thread document_id does not match command scope")
    return state


def _require_revision(state: ConsultantThreadState, expected: int) -> None:
    actual = state.get("revision", 0)
    if actual != expected:
        raise StaleThreadRevision(expected, actual)


def _apply_command(
    state: ConsultantThreadState,
    runtime: Runtime[ConsultantCommandContext],
) -> ConsultantThreadState:
    command = runtime.context
    action = command["action"]
    document_id = UUID(command["document_id"])

    if action == "initialize":
        if state:
            _require_document(state, document_id)
            return {}
        return initial_thread_state(document_id)

    _require_document(state, document_id)
    expected_revision = command["expected_revision"]
    _require_revision(state, expected_revision)

    source_reference_payload = command.get("source_reference")
    source_reference = (
        SourceReference.model_validate(source_reference_payload)
        if source_reference_payload is not None
        else None
    )
    source_count = state.get("source_count", 0)
    latest_source_id = state.get("latest_source_id")
    supersessions = dict(state.get("source_supersessions", {}))
    if source_reference is not None:
        source_count += 1
        latest_source_id = str(source_reference.source_id)
        if source_reference.supersedes_source_id is not None:
            supersessions[str(source_reference.supersedes_source_id)] = str(
                source_reference.source_id
            )

    update: ConsultantThreadState = {
        "revision": expected_revision + 1,
        "source_count": source_count,
        "latest_source_id": latest_source_id,
        "source_supersessions": supersessions,
    }
    if action == "register_source":
        return update
    if action == "direct_edit":
        approved = ApprovedJobDocument.model_validate(command["approved_document"])
        if approved.document_id != document_id:
            raise ValueError("approved document does not match thread document_id")
        update["approved_document"] = approved.model_dump(mode="json")
        return update
    raise ValueError(f"unsupported consultant command: {action}")


def build_consultant_graph(checkpointer: Any, store: Any) -> Any:
    builder = StateGraph(
        ConsultantThreadState,
        context_schema=ConsultantCommandContext,
    )
    builder.add_node("apply_command", _apply_command)
    builder.add_edge(START, "apply_command")
    builder.add_edge("apply_command", END)
    return builder.compile(checkpointer=checkpointer, store=store)
