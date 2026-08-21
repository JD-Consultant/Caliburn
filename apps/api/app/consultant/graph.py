"""Deterministic LangGraph authority channel for consultant document facts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from app.consultant.clarification import interrupt_for_required_clarification
from app.consultant.candidate_workspace import (
    CandidateWorkspace,
    VerifiedCandidateStage,
    materialize_candidate_workspace,
)
from app.consultant.document_review import (
    apply_review_command,
    revalidate_after_direct_edit,
)
from app.consultant.interview import (
    VerifiedConsultantCommit,
    _publish_persisted_changeset,
    apply_source_correction,
    apply_verified_consultant_commit,
    normalize_current_work,
)
from app.consultant.state import (
    ApprovedJobDocument,
    CalibrationDecision,
    CommandReceipt,
    CheckedCandidateReceipt,
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
    if action == "check_candidate_document":
        expected_revision = command.get("expected_revision")
        if not isinstance(expected_revision, int):
            raise ValueError("candidate check requires the current revision")
        _require_revision(state, expected_revision)
        receipt = CheckedCandidateReceipt.model_validate(
            command["checked_candidate"]
        )
        latest_payload = state.get("latest_run")
        if latest_payload is None:
            raise ValueError("candidate check requires an active consultant run")
        latest = RunReceipt.model_validate(latest_payload)
        if latest.run_id != receipt.run_id or latest.status is not RunStatus.SOURCE_SAVED:
            raise ValueError("candidate check does not match the active consultant run")
        if receipt.baseline_revision != expected_revision:
            raise ValueError("candidate check baseline revision is stale")
        return {"checked_candidate": receipt.model_dump(mode="json")}
    if action == "stage_candidate_revision":
        stage = VerifiedCandidateStage.model_validate(command["candidate_stage"])
        latest_payload = state.get("latest_run")
        if latest_payload is None:
            raise ValueError("candidate staging requires an active consultant run")
        latest = RunReceipt.model_validate(latest_payload)
        if latest.run_id != stage.run_id or latest.status is not RunStatus.SOURCE_SAVED:
            raise ValueError("candidate staging does not match the active consultant run")
        workspace, _ = materialize_candidate_workspace(state, stage)
        return {"active_candidate": workspace.model_dump(mode="json")}
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
    if action == "publish_checked_candidate":
        receipt_payload = state.get("checked_candidate")
        if receipt_payload is None:
            raise ValueError("candidate publication has no checked candidate receipt")
        receipt = CheckedCandidateReceipt.model_validate(receipt_payload)
        requested_run_id = command.get("run_id")
        if requested_run_id is not None and receipt.run_id != UUID(requested_run_id):
            raise ValueError("candidate publication belongs to another consultant run")
        if receipt.baseline_revision != expected_revision:
            raise ValueError("candidate publication baseline revision is stale")
        review_queue, interview_work = _publish_persisted_changeset(
            document_id=document_id,
            run_id=receipt.run_id,
            read_revision=expected_revision,
            state=state,
            published_changeset=receipt.changeset,
            interview_work=dict(state.get("interview_work", {})),
        )
        work, current_work_id = normalize_current_work(
            interview_work,
            preferred_work_id=(
                UUID(state["current_work_id"])
                if state.get("current_work_id") is not None
                else None
            ),
            revision=expected_revision + 1,
        )
        update: ConsultantThreadState = {"revision": expected_revision + 1}
        update.update(
            {
                "review_queue": review_queue,
                "interview_work": work,
                "current_work_id": current_work_id,
                "checked_candidate": None,
            }
        )
        return update
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
        update["active_candidate"] = None
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
        active_payload = state.get("active_candidate")
        if active_payload is not None:
            active = CandidateWorkspace.model_validate(active_payload)
            if active.run_id != receipt.run_id:
                update["active_candidate"] = None
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
    if action == "direct_edit":
        before = ApprovedJobDocument.model_validate(state["approved_document"])
        approved = ApprovedJobDocument.model_validate(command["approved_document"])
        if approved.document_id != document_id:
            raise ValueError("approved document does not match thread document_id")
        update.update(_source_state_update(state, source_reference))
        update["approved_document"] = approved.model_dump(mode="json")
        update["active_candidate"] = None
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
        update["active_candidate"] = None
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
        published_changeset = _published_candidate_changeset(
            state,
            commit=commit,
            expected_revision=expected_revision,
        )
        update.update(
            apply_verified_consultant_commit(
                state,
                document_id=document_id,
                revision=expected_revision + 1,
                commit=commit,
                published_changeset=published_changeset,
            )
        )
        update["active_candidate"] = None
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


def _published_candidate_changeset(
    state: ConsultantThreadState,
    *,
    commit: VerifiedConsultantCommit,
    expected_revision: int,
):
    publication = commit.result.candidate_publication
    if publication is None:
        return None
    active_payload = state.get("active_candidate")
    if active_payload is None:
        raise ValueError("candidate publication has no active candidate workspace")
    active = CandidateWorkspace.model_validate(active_payload)
    if active.run_id != commit.run_id:
        raise ValueError("candidate publication belongs to another consultant run")
    if active.baseline_revision != expected_revision:
        raise ValueError("candidate publication baseline revision is stale")
    if active.candidate_revision != publication.candidate_revision:
        raise ValueError("candidate publication does not reference the latest revision")
    if active.revision_digest != publication.revision_digest:
        raise ValueError("candidate publication digest does not match latest revision")
    action_ids = tuple(action.action_id for action in active.changeset.actions)
    if action_ids != publication.action_ids:
        raise ValueError("candidate publication action handles do not match latest revision")
    if not set(active.used_skill_ids) <= set(commit.result.used_skill_ids):
        raise ValueError("candidate publication used Skills missing from final result")
    return active.changeset


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
