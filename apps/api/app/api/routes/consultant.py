"""Purpose-first HTTP surface for the durable professional consultant."""

from __future__ import annotations

import asyncio
import json
from hashlib import sha256
from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID, uuid5

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Response
from fastapi.sse import EventSourceResponse, ServerSentEvent
from job_analysis_contract import (
    ApprovedJobDocumentWrite,
    ConsultantDocumentCatalog,
    ConsultantDocumentCatalogItem,
    ConsultantDocumentCreate,
    ConsultantRunAccepted,
    ConsultantSnapshotEvent,
    ConsultantSnapshotView,
    DirectDocumentEditWrite,
    DocumentReviewDecisionWrite,
    EmployeeAnswerWrite,
    RequiredClarificationAnswerWrite,
    UnderstandingCalibrationDecisionWrite,
)

from app.adapters.langgraph.postgres import DocumentNotFound, PostgresConsultantRuntime
from app.adapters.xlsx import XLSX_MEDIA_TYPE, render_xlsx
from app.api.consultant_mapper import to_consultant_snapshot_view
from app.api.deps import get_consultant_runtime, get_consultant_turn_processor
from app.api.problems import (
    EXPORT_CONFIRMATION_REQUIRED,
    INVALID_REQUEST,
    consultant_runtime_error_response,
    problem_response,
)
from app.consultant.run_service import ConsultantTurnProcessor
from app.consultant.state import ApprovedJobDocument, CommandReceipt, RunReceipt
from app.consultant.workspace_authority import (
    WorkspaceDecisionKind,
    WorkspaceReviewCommand,
)
from app.export import assemble_approved_export_document


router = APIRouter(
    prefix="/job-analysis/consultant-documents",
    tags=["job-analysis-consultant"],
)
_DOCUMENT_ID_NAMESPACE = UUID("b7953e5e-4bf0-51b5-a498-d543cc98f301")
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=200),
]
ExpectedRevision = Annotated[
    int,
    Header(alias="X-Expected-Revision", ge=0),
]
OptionalExpectedRevision = Annotated[
    int | None,
    Header(alias="X-Expected-Revision", ge=0),
]


def _command_id(document_id: UUID, channel: str, key: str) -> UUID:
    return uuid5(document_id, f"consultant-http:{channel}:{key}")


def _command_receipt(
    document_id: UUID,
    command_kind: str,
    key: str,
    payload: dict[str, Any],
) -> CommandReceipt:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return CommandReceipt(
        command_id=_command_id(document_id, f"{command_kind}-command", key),
        command_kind=command_kind,
        payload_sha256=sha256(canonical).hexdigest(),
    )


def _approved_document_from_edit(
    body: ApprovedJobDocumentWrite,
    current: ApprovedJobDocument,
    source_id: UUID,
) -> ApprovedJobDocument:
    """Restore server-owned evidence and attach this edit to changed OPKS text."""

    payload = body.model_dump(mode="json")
    existing = {str(item.item_id): item for item in current.opks}
    for item in payload["opks"]:
        previous = existing.get(str(item["item_id"]))
        evidence = (
            list(previous.evidence_source_ids)
            if previous is not None
            else []
        )
        if previous is None or item["text"] != previous.text:
            if source_id not in evidence:
                evidence.append(source_id)
        item["evidence_source_ids"] = evidence
    return ApprovedJobDocument.model_validate(payload)


def _catalog_item(value) -> ConsultantDocumentCatalogItem:
    return ConsultantDocumentCatalogItem.model_validate(
        value.model_dump(mode="json")
    )


async def _snapshot_view(
    runtime: PostgresConsultantRuntime,
    snapshot,
) -> ConsultantSnapshotView:
    return to_consultant_snapshot_view(
        snapshot,
        employee_sources=await runtime.list_sources(snapshot.document_id),
    )


async def _accept_answer(
    *,
    document_id: UUID,
    text: str,
    supersedes_source_id: UUID | None,
    idempotency_key: str,
    runtime: PostgresConsultantRuntime,
    processor: ConsultantTurnProcessor,
    background_tasks: BackgroundTasks,
) -> ConsultantRunAccepted:
    run_id = _command_id(document_id, "answer-run", idempotency_key)
    source_id = _command_id(document_id, "answer-source", idempotency_key)
    snapshot, _ = await runtime.admit_employee_answer(
        document_id=document_id,
        run_id=run_id,
        source_id=source_id,
        text=text,
        supersedes_source_id=supersedes_source_id,
    )
    receipt = RunReceipt.model_validate(snapshot.latest_run)
    if receipt.status.value == "source_saved" and await processor.claim(
        document_id, run_id
    ):
        background_tasks.add_task(
            processor.process_claimed,
            document_id,
            run_id,
            source_id,
            runtime,
        )
    return ConsultantRunAccepted(
        run_id=run_id,
        source_id=source_id,
        status=receipt.status.value,
    )


@router.get("", response_model=ConsultantDocumentCatalog)
async def list_consultant_documents(
    runtime: PostgresConsultantRuntime = Depends(get_consultant_runtime),
):
    return ConsultantDocumentCatalog(
        documents=[_catalog_item(item) for item in await runtime.list_documents()]
    )


@router.post("", response_model=ConsultantDocumentCatalogItem, status_code=201)
async def create_consultant_document(
    body: ConsultantDocumentCreate,
    idempotency_key: IdempotencyKey,
    runtime: PostgresConsultantRuntime = Depends(get_consultant_runtime),
):
    try:
        document_id = uuid5(
            _DOCUMENT_ID_NAMESPACE,
            f"consultant-document:{idempotency_key}",
        )
        await runtime.create_document(document_id, title=body.title)
        return _catalog_item(await runtime.get_document_catalog_entry(document_id))
    except Exception as error:
        return consultant_runtime_error_response(error)


@router.get("/{document_id}", response_model=ConsultantDocumentCatalogItem)
async def get_consultant_document(
    document_id: UUID,
    runtime: PostgresConsultantRuntime = Depends(get_consultant_runtime),
):
    try:
        return _catalog_item(await runtime.get_document_catalog_entry(document_id))
    except Exception as error:
        return consultant_runtime_error_response(error)


@router.delete("/{document_id}", status_code=204)
async def delete_consultant_document(
    document_id: UUID,
    runtime: PostgresConsultantRuntime = Depends(get_consultant_runtime),
):
    try:
        await runtime.delete_document(document_id)
        return Response(status_code=204)
    except Exception as error:
        return consultant_runtime_error_response(error)


@router.post(
    "/{document_id}/answers",
    response_model=ConsultantRunAccepted,
    status_code=202,
)
async def submit_employee_answer(
    document_id: UUID,
    body: EmployeeAnswerWrite,
    idempotency_key: IdempotencyKey,
    background_tasks: BackgroundTasks,
    runtime: PostgresConsultantRuntime = Depends(get_consultant_runtime),
    processor: ConsultantTurnProcessor = Depends(get_consultant_turn_processor),
):
    try:
        return await _accept_answer(
            document_id=document_id,
            text=body.text,
            supersedes_source_id=body.supersedes_source_id,
            idempotency_key=idempotency_key,
            runtime=runtime,
            processor=processor,
            background_tasks=background_tasks,
        )
    except Exception as error:
        return consultant_runtime_error_response(error)


@router.post(
    "/{document_id}/runs/{run_id}/retry",
    response_model=ConsultantRunAccepted,
    status_code=202,
)
async def retry_consultant_run(
    document_id: UUID,
    run_id: UUID,
    background_tasks: BackgroundTasks,
    runtime: PostgresConsultantRuntime = Depends(get_consultant_runtime),
    processor: ConsultantTurnProcessor = Depends(get_consultant_turn_processor),
):
    try:
        snapshot = await runtime.reopen_document(document_id)
        receipt = (
            RunReceipt.model_validate(snapshot.latest_run)
            if snapshot.latest_run is not None
            else None
        )
        if receipt is None or receipt.run_id != run_id:
            raise ValueError("retry run does not match the current durable run")
        source = await runtime.get_source(document_id, receipt.source_id)
        restarted, _ = await runtime.admit_employee_answer(
            document_id=document_id,
            run_id=receipt.run_id,
            source_id=source.source_id,
            text=source.text,
            supersedes_source_id=source.supersedes_source_id,
        )
        active = RunReceipt.model_validate(restarted.latest_run)
        if active.status.value == "source_saved" and await processor.claim(
            document_id, active.run_id
        ):
            background_tasks.add_task(
                processor.process_claimed,
                document_id,
                active.run_id,
                active.source_id,
                runtime,
            )
        return ConsultantRunAccepted(
            run_id=active.run_id,
            source_id=active.source_id,
            status=active.status.value,
        )
    except Exception as error:
        return consultant_runtime_error_response(error)


@router.get("/{document_id}/snapshot", response_model=ConsultantSnapshotView)
async def get_consultant_snapshot(
    document_id: UUID,
    runtime: PostgresConsultantRuntime = Depends(get_consultant_runtime),
):
    try:
        snapshot = await runtime.reopen_document(document_id)
        return await _snapshot_view(
            runtime,
            snapshot,
        )
    except Exception as error:
        return consultant_runtime_error_response(error)


@router.get("/{document_id}/events", response_class=EventSourceResponse)
async def stream_consultant_snapshot_events(
    document_id: UUID,
    last_event_id: Annotated[
        int | None,
        Header(alias="Last-Event-ID"),
    ] = None,
    runtime: PostgresConsultantRuntime = Depends(get_consultant_runtime),
):
    seen = last_event_id if last_event_id is not None else -1
    quiet_ticks = 0
    while True:
        try:
            snapshot = await runtime.reopen_document(document_id)
        except DocumentNotFound:
            event = ConsultantSnapshotEvent(
                event="document_deleted",
                document_id=document_id,
                revision=max(seen, 0),
                run_id=None,
            )
            yield ServerSentEvent(
                data=event.model_dump(mode="json"),
                event="snapshot",
                id=str(max(seen, 0)),
            )
            return
        if snapshot.revision > seen:
            receipt = (
                RunReceipt.model_validate(snapshot.latest_run)
                if snapshot.latest_run is not None
                else None
            )
            event = ConsultantSnapshotEvent(
                event="snapshot_changed",
                document_id=document_id,
                revision=snapshot.revision,
                run_id=receipt.run_id if receipt is not None else None,
            )
            seen = snapshot.revision
            quiet_ticks = 0
            yield ServerSentEvent(
                data=event.model_dump(mode="json"),
                event="snapshot",
                id=str(snapshot.revision),
                retry=1000,
            )
        else:
            quiet_ticks += 1
            if quiet_ticks >= 15:
                quiet_ticks = 0
                yield ServerSentEvent(comment="keepalive")
        await asyncio.sleep(1)


@router.post(
    "/{document_id}/reviews/{changeset_id}",
    response_model=ConsultantSnapshotView,
)
async def review_document_changes(
    document_id: UUID,
    changeset_id: UUID,
    body: DocumentReviewDecisionWrite,
    idempotency_key: IdempotencyKey,
    expected_revision: ExpectedRevision,
    runtime: PostgresConsultantRuntime = Depends(get_consultant_runtime),
):
    try:
        edited = {
            UUID(key): value
            for key, value in body.edited_after_by_action_id.items()
        }
        _, _, workspace_snapshot, projection = await runtime.workspace_review_context(
            document_id
        )
        groups = [
            group
            for group in projection.groups
            if group.changeset.changeset_id == changeset_id
        ]
        if len(groups) != 1:
            raise ValueError(f"workspace changeset {changeset_id} is stale")
        decision = {
            "accept_changes": WorkspaceDecisionKind.ACCEPT,
            "edit_and_accept_changes": WorkspaceDecisionKind.EDIT_ACCEPT,
            "reject_changes": WorkspaceDecisionKind.REJECT,
            "defer_changes": WorkspaceDecisionKind.DEFER,
        }[body.command.value]
        command = WorkspaceReviewCommand(
            command_id=_command_id(document_id, "workspace-review", idempotency_key),
            document_id=document_id,
            decision=decision,
            approved_revision=expected_revision,
            workspace_generation=workspace_snapshot.manifest.generation,
            workspace_digest=workspace_snapshot.manifest.resource_digest,
            changeset_id=changeset_id,
            group_digest=groups[0].group_digest,
            selected_action_ids=tuple(body.action_ids),
            edited_after_by_action_id=edited,
            reason=body.rejection_reason,
        )
        snapshot = await runtime.decide_workspace_changes(command)
        return await _snapshot_view(runtime, snapshot)
    except Exception as error:
        return consultant_runtime_error_response(error)


@router.post(
    "/{document_id}/calibrations/{calibration_id}",
    response_model=ConsultantSnapshotView | ConsultantRunAccepted,
    responses={202: {"model": ConsultantRunAccepted}},
)
async def decide_understanding_calibration(
    document_id: UUID,
    calibration_id: UUID,
    body: UnderstandingCalibrationDecisionWrite,
    idempotency_key: IdempotencyKey,
    background_tasks: BackgroundTasks,
    expected_revision: OptionalExpectedRevision = None,
    runtime: PostgresConsultantRuntime = Depends(get_consultant_runtime),
    processor: ConsultantTurnProcessor = Depends(get_consultant_turn_processor),
):
    try:
        decision = body.decision.value
        if decision == "direct_correction":
            if not body.employee_text or not body.employee_text.strip():
                raise ValueError("direct correction requires employee text")
            response = await _accept_answer(
                document_id=document_id,
                text=body.employee_text,
                supersedes_source_id=None,
                idempotency_key=f"calibration:{calibration_id}:{idempotency_key}",
                runtime=runtime,
                processor=processor,
                background_tasks=background_tasks,
            )
            return Response(
                content=response.model_dump_json(),
                status_code=202,
                media_type="application/json",
            )
        if expected_revision is None:
            raise ValueError("calibration decision requires X-Expected-Revision")
        if decision == "confirm":
            if not body.employee_text or not body.employee_text.strip():
                raise ValueError("confirmation requires employee text")
            employee_text = body.employee_text
            source_id = _command_id(
                document_id, "calibration-source", idempotency_key
            )
        else:
            if body.employee_text is not None:
                raise ValueError("later decision must not carry employee text")
            employee_text = None
            source_id = None
        snapshot = await runtime.decide_understanding_calibration(
            document_id=document_id,
            expected_revision=expected_revision,
            calibration_id=calibration_id,
            decision=decision,
            employee_text=employee_text,
            source_id=source_id,
            command_receipt=_command_receipt(
                document_id,
                "understanding_calibration",
                idempotency_key,
                {
                    "calibration_id": str(calibration_id),
                    "decision": body.model_dump(mode="json"),
                },
            ),
        )
        return await _snapshot_view(runtime, snapshot)
    except Exception as error:
        return consultant_runtime_error_response(error)


@router.post(
    "/{document_id}/clarifications/{clarification_id}",
    response_model=ConsultantSnapshotView,
)
async def answer_required_clarification(
    document_id: UUID,
    clarification_id: UUID,
    body: RequiredClarificationAnswerWrite,
    idempotency_key: IdempotencyKey,
    expected_revision: ExpectedRevision,
    runtime: PostgresConsultantRuntime = Depends(get_consultant_runtime),
):
    try:
        snapshot = await runtime.answer_required_clarification(
            document_id=document_id,
            expected_revision=expected_revision,
            clarification_id=clarification_id,
            choice=body.choice,
            text=body.text,
            source_id=_command_id(
                document_id, "clarification-source", idempotency_key
            ),
            command_receipt=_command_receipt(
                document_id,
                "required_clarification",
                idempotency_key,
                {
                    "clarification_id": str(clarification_id),
                    "answer": body.model_dump(mode="json"),
                },
            ),
        )
        return await _snapshot_view(runtime, snapshot)
    except Exception as error:
        return consultant_runtime_error_response(error)


@router.put(
    "/{document_id}/approved-document",
    response_model=ConsultantSnapshotView,
)
async def edit_approved_document(
    document_id: UUID,
    body: DirectDocumentEditWrite,
    idempotency_key: IdempotencyKey,
    expected_revision: ExpectedRevision,
    runtime: PostgresConsultantRuntime = Depends(get_consultant_runtime),
):
    try:
        source_id = _command_id(
            document_id, "direct-edit-source", idempotency_key
        )
        current = (await runtime.reopen_document(document_id)).approved_document
        document = _approved_document_from_edit(
            body.document,
            current,
            source_id,
        )
        snapshot = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=expected_revision,
            document=document,
            source_id=source_id,
            command_receipt=_command_receipt(
                document_id,
                "direct_document_edit",
                idempotency_key,
                {"document": body.document.model_dump(mode="json")},
            ),
        )
        return await _snapshot_view(runtime, snapshot)
    except Exception as error:
        return consultant_runtime_error_response(error)


def _export_filename(title: str) -> str:
    safe_title = "".join(
        "_" if character in '<>:/\\|?*"\r\n' else character
        for character in title.strip()
    ).rstrip(" .") or "職務說明書"
    return f"{safe_title}.xlsx"


@router.get("/{document_id}/export")
async def export_approved_document(
    document_id: UUID,
    force: Annotated[bool, Query()] = False,
    runtime: PostgresConsultantRuntime = Depends(get_consultant_runtime),
):
    try:
        snapshot = await runtime.reopen_document(document_id)
        view = to_consultant_snapshot_view(snapshot)
        if view.readiness.requires_force_confirmation and not force:
            return problem_response(
                type_uri=EXPORT_CONFIRMATION_REQUIRED,
                title="Export requires explicit confirmation",
                status=409,
                detail="Review the reported gaps, then explicitly force export if desired.",
            )
        catalog = await runtime.get_document_catalog_entry(document_id)
        export_document = assemble_approved_export_document(
            snapshot.approved_document,
            title=catalog.title,
        )
        filename = _export_filename(catalog.title)
        return Response(
            content=render_xlsx(export_document),
            media_type=XLSX_MEDIA_TYPE,
            headers={
                "Content-Disposition": (
                    'attachment; filename="job-description.xlsx"; '
                    f"filename*=UTF-8''{quote(filename, safe='')}"
                )
            },
        )
    except Exception as error:
        return consultant_runtime_error_response(error)


__all__ = ["router"]
