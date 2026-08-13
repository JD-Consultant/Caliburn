"""Deterministic LangGraph authority channel for consultant document facts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from app.consultant.clarification import interrupt_for_required_clarification
from app.consultant.document_review import (
    apply_review_command,
    revalidate_after_direct_edit,
)
from app.consultant.interview import (
    VerifiedConsultantCommit,
    apply_source_correction,
    apply_verified_consultant_commit,
    normalize_current_work,
)
from app.consultant.state import (
    ApprovedJobDocument,
    CalibrationDecision,
    ConsultantCommandContext,
    ConsultantThreadState,
    SourceReference,
    initial_thread_state,
)
from app.consultant.understanding import decide_calibration, invalidate_sufficiency


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


def _source_state_update(
    state: ConsultantThreadState,
    source_reference: SourceReference | None,
) -> ConsultantThreadState:
    if source_reference is None:
        return {}
    supersessions = dict(state.get("source_supersessions", {}))
    if source_reference.supersedes_source_id is not None:
        supersessions[str(source_reference.supersedes_source_id)] = str(
            source_reference.source_id
        )
    return {
        "source_count": state.get("source_count", 0) + 1,
        "latest_source_id": str(source_reference.source_id),
        "source_supersessions": supersessions,
    }


def _apply_command(
    state: ConsultantThreadState,
    runtime: Runtime[ConsultantCommandContext],
) -> ConsultantThreadState:
    command = runtime.context
    action = command["action"]
    document_id = UUID(command["document_id"])

    if action == "initialize":
        if state.get("document_id") is not None:
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
    update: ConsultantThreadState = {
        "revision": expected_revision + 1,
    }
    if action == "register_source":
        if source_reference is None:
            raise ValueError("register_source requires a source reference")
        update.update(_source_state_update(state, source_reference))
        if source_reference.supersedes_source_id is not None:
            update.update(
                apply_source_correction(
                    state,
                    document_id=document_id,
                    superseded_source_id=source_reference.supersedes_source_id,
                    correction_source_id=source_reference.source_id,
                    revision=expected_revision + 1,
                )
            )
        invalidated = invalidate_sufficiency(
            state,
            revision=expected_revision + 1,
        )
        if invalidated is not None:
            update["sufficiency"] = invalidated
        return update
    if action == "direct_edit":
        before = ApprovedJobDocument.model_validate(state["approved_document"])
        approved = ApprovedJobDocument.model_validate(command["approved_document"])
        if approved.document_id != document_id:
            raise ValueError("approved document does not match thread document_id")
        update.update(_source_state_update(state, source_reference))
        update["approved_document"] = approved.model_dump(mode="json")
        update.update(
            revalidate_after_direct_edit(
                state,
                before=before,
                after=approved,
                revision=expected_revision + 1,
            )
        )
        work, current_work_id = normalize_current_work(
            update.get("interview_work", state.get("interview_work", {})),
            preferred_work_id=(
                UUID(state["current_work_id"])
                if state.get("current_work_id") is not None
                else None
            ),
            revision=expected_revision + 1,
        )
        update["interview_work"] = work
        update["current_work_id"] = current_work_id
        invalidated = invalidate_sufficiency(
            state,
            revision=expected_revision + 1,
        )
        if invalidated is not None:
            update["sufficiency"] = invalidated
        return update
    if action in {
        "accept_changes",
        "edit_and_accept_changes",
        "reject_changes",
        "defer_changes",
    }:
        reviewed = apply_review_command(
            state,
            action=action,
            changeset_id=UUID(command["changeset_id"]),
            action_ids=tuple(UUID(item) for item in command["action_ids"]),
            revision=expected_revision + 1,
            edited_after_by_action_id={
                UUID(key): value
                for key, value in command.get(
                    "edited_after_by_action_id", {}
                ).items()
            },
            rejection_reason=command.get("rejection_reason"),
            source_reference=source_reference,
        )
        update.update(_source_state_update(state, source_reference))
        update.update(reviewed)
        work, current_work_id = normalize_current_work(
            reviewed["interview_work"],
            preferred_work_id=(
                UUID(state["current_work_id"])
                if state.get("current_work_id") is not None
                else None
            ),
            revision=expected_revision + 1,
        )
        update["interview_work"] = work
        update["current_work_id"] = current_work_id
        invalidated = invalidate_sufficiency(
            state,
            revision=expected_revision + 1,
        )
        if invalidated is not None:
            update["sufficiency"] = invalidated
        return update
    if action == "commit_consultant_result":
        if source_reference is not None:
            raise ValueError("model semantic commit cannot mint employee evidence")
        commit = VerifiedConsultantCommit.model_validate(command["semantic_commit"])
        update.update(
            apply_verified_consultant_commit(
                state,
                document_id=document_id,
                revision=expected_revision + 1,
                commit=commit,
            )
        )
        return update
    if action == "decide_understanding_calibration":
        calibration_id = UUID(command["calibration_id"])
        decision = CalibrationDecision(command["calibration_decision"])
        calibrations, understanding, work, latest = decide_calibration(
            state=state,
            calibration_id=calibration_id,
            decision=decision,
            source_reference=source_reference,
            revision=expected_revision + 1,
        )
        update.update(_source_state_update(state, source_reference))
        work, current_work_id = normalize_current_work(
            work,
            preferred_work_id=(
                UUID(state["current_work_id"])
                if state.get("current_work_id") is not None
                else None
            ),
            revision=expected_revision + 1,
        )
        update.update(
            {
                "understanding_calibrations": calibrations,
                "latest_calibration_id": latest,
                "understanding": understanding,
                "interview_work": work,
                "current_work_id": current_work_id,
            }
        )
        return update
    raise ValueError(f"unsupported consultant command: {action}")


def build_consultant_graph(checkpointer: Any, store: Any) -> Any:
    builder = StateGraph(
        ConsultantThreadState,
        context_schema=ConsultantCommandContext,
    )
    builder.add_node("apply_command", _apply_command)
    builder.add_node(
        "required_clarification",
        interrupt_for_required_clarification,
    )
    builder.add_edge(START, "apply_command")
    builder.add_edge("apply_command", "required_clarification")
    builder.add_edge("required_clarification", END)
    return builder.compile(checkpointer=checkpointer, store=store)
