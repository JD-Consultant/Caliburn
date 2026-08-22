"""Deterministic LangGraph authority channel for consultant document facts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from app.consultant.clarification import interrupt_for_required_clarification
from app.consultant.interview import (
    VerifiedConsultantCommit,
    apply_source_correction,
    apply_verified_consultant_commit,
    normalize_current_work,
)
from app.consultant.state import (
    ApprovedJobDocument,
    CalibrationDecision,
    CommandReceipt,
    ConsultantCommandContext,
    ConsultantThreadState,
    RunReceipt,
    RunStatus,
    SourceReference,
    attach_command_receipt,
    initial_thread_state,
    inspect_command_receipt,
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
    receipt_payload = command.get("command_receipt")
    command_receipt = (
        CommandReceipt.model_validate(receipt_payload)
        if receipt_payload is not None
        else None
    )
    if (
        command_receipt is not None
        and inspect_command_receipt(state, command_receipt) == "replay"
    ):
        return {}
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
    if command_receipt is not None:
        update["command_receipts"] = attach_command_receipt(
            state,
            command_receipt,
        )
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
        run_payload = command.get("run_receipt")
        if run_payload is not None:
            receipt = RunReceipt.model_validate(run_payload)
            if (
                receipt.status is not RunStatus.SOURCE_SAVED
                or receipt.source_id != source_reference.source_id
            ):
                raise ValueError(
                    "registered answer requires a source-saved run receipt"
                )
            update["latest_run"] = receipt.model_dump(mode="json")
        return update
    if action == "restart_consultant_run":
        receipt = RunReceipt.model_validate(command["run_receipt"])
        previous_payload = state.get("latest_run")
        if previous_payload is None:
            raise ValueError("no failed consultant run is available to retry")
        previous = RunReceipt.model_validate(previous_payload)
        if (
            previous.status is not RunStatus.FAILED
            or receipt.status is not RunStatus.SOURCE_SAVED
            or receipt.run_id != previous.run_id
            or receipt.source_id != previous.source_id
        ):
            raise ValueError("consultant retry does not match the failed run")
        update["latest_run"] = receipt.model_dump(mode="json")
        return update
    if action == "mark_consultant_run_failed":
        receipt = RunReceipt.model_validate(command["run_receipt"])
        previous_payload = state.get("latest_run")
        if previous_payload is None:
            raise ValueError("no consultant run is available to fail")
        previous = RunReceipt.model_validate(previous_payload)
        if (
            previous.status is not RunStatus.SOURCE_SAVED
            or receipt.status is not RunStatus.FAILED
            or receipt.run_id != previous.run_id
            or receipt.source_id != previous.source_id
        ):
            raise ValueError(
                "failed receipt does not match the active consultant run"
            )
        update["latest_run"] = receipt.model_dump(mode="json")
        return update
    if action == "workspace_authority_commit":
        if command_receipt is None:
            raise ValueError("workspace authority commit requires a command receipt")
        if source_reference is not None:
            update.update(_source_state_update(state, source_reference))
        approved = ApprovedJobDocument.model_validate(command["approved_document"])
        if approved.document_id != document_id:
            raise ValueError("approved document does not match thread document_id")
        update["approved_document"] = approved.model_dump(mode="json")
        invalidated = invalidate_sufficiency(
            state,
            revision=expected_revision + 1,
        )
        if invalidated is not None:
            update["sufficiency"] = invalidated
        return update
    if action == "direct_edit":
        approved = ApprovedJobDocument.model_validate(command["approved_document"])
        if approved.document_id != document_id:
            raise ValueError("approved document does not match thread document_id")
        update.update(_source_state_update(state, source_reference))
        update["approved_document"] = approved.model_dump(mode="json")
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
