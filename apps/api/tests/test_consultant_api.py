from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from openpyxl import load_workbook

import app.app_factory as app_factory
from app.adapters.langgraph.postgres import (
    ActiveConsultantRun,
    ConsultantDocumentCatalogEntry,
    ConsultantRunAlreadyActive,
    DocumentNotFound,
)
from app.api.deps import get_consultant_runtime, get_consultant_turn_processor
from app.api.problems import AUTHORITY_CONFLICT, CONSULTANT_RUN_ACTIVE, INVALID_REQUEST
from app.api.routes import consultant
from app.consultant.state import (
    EmployeeSource,
    EmployeeSourceKind,
    DocumentChangeSet,
    DocumentPatchAction,
    DocumentPatchOperation,
    DocumentPathRead,
    RunReceipt,
    RunStatus,
    initial_thread_state,
)
from app.consultant.document_commands import DocumentCommandBlastRadius
from app.consultant.views import (
    document_review_projection_from_workspace,
    snapshot_from_state,
)
from app.consultant.workspace_review import WorkspaceReviewGroup, WorkspaceReviewProjection
from app.consultant.workspace_state import WorkspaceValidationStatus


pytestmark = pytest.mark.asyncio
BASE = "/api/v1/job-analysis/consultant-documents"


def _snapshot(
    document_id: UUID,
    *,
    revision: int = 0,
    run: RunReceipt | None = None,
):
    state = initial_thread_state(document_id)
    state["revision"] = revision
    if run is not None:
        state["latest_run"] = run.model_dump(mode="json")
        state["latest_source_id"] = str(run.source_id)
        state["source_count"] = 1
    return _store_enriched_snapshot(state)


def _store_enriched_snapshot(state):
    snapshot = snapshot_from_state(state)
    review = document_review_projection_from_workspace(
        state,
        workspace_generation=1,
        validation_status=WorkspaceValidationStatus.VALID,
        workspace_review=WorkspaceReviewProjection(workspace_digest="a" * 64),
    )
    return snapshot.model_copy(
        update={
            "current_document": snapshot.approved_document,
            "document_review": review,
        }
    )


class FakeRuntime:
    def __init__(self) -> None:
        self.document_id: UUID | None = None
        self.title = "採購職務"
        self.deleted = False
        self.snapshot = None
        self.active_conflict = False
        self.model_mutation_busy = False
        self.employee_admission_entries = 0
        self.busy_preflight_calls = 0
        self.calls: list[tuple[str, dict]] = []
        self.sources: list[EmployeeSource] = []
        self.review_changeset_id: UUID | None = None
        self.review_action_id: UUID | None = None

    async def list_documents(self):
        if self.document_id is None or self.deleted:
            return ()
        now = datetime(2026, 8, 14, tzinfo=UTC)
        return (
            ConsultantDocumentCatalogEntry(
                document_id=self.document_id,
                title=self.title,
                created_at=now,
                updated_at=now,
            ),
        )

    async def get_document_catalog_entry(self, document_id: UUID):
        assert document_id == self.document_id
        return (await self.list_documents())[0]

    async def create_document(self, document_id: UUID, *, title: str):
        self.document_id = document_id
        self.title = title
        self.snapshot = _snapshot(document_id)
        return self.snapshot

    async def reopen_document(self, document_id: UUID):
        assert document_id == self.document_id
        if self.model_mutation_busy:
            self.busy_preflight_calls += 1
        return self.snapshot

    @asynccontextmanager
    async def employee_mutation_admission(self, document_id: UUID):
        assert document_id == self.document_id
        self.employee_admission_entries += 1
        if self.model_mutation_busy:
            raise ConsultantRunAlreadyActive(document_id)
        yield

    async def list_sources(self, document_id: UUID):
        assert document_id == self.document_id
        return tuple(self.sources)

    async def get_source(self, document_id: UUID, source_id: UUID):
        assert document_id == self.document_id
        return next(item for item in self.sources if item.source_id == source_id)

    async def admit_employee_answer(self, **kwargs):
        if self.active_conflict:
            raise ActiveConsultantRun("another run is recoverable")
        self.calls.append(("answer", kwargs))
        if not any(item.source_id == kwargs["source_id"] for item in self.sources):
            self.sources.append(
                EmployeeSource.pending(
                    source_id=kwargs["source_id"],
                    document_id=kwargs["document_id"],
                    kind=EmployeeSourceKind.EMPLOYEE_TURN,
                    text=kwargs["text"],
                    supersedes_source_id=kwargs["supersedes_source_id"],
                )
            )
        run = RunReceipt(
            run_id=kwargs["run_id"],
            status=RunStatus.SOURCE_SAVED,
            source_id=kwargs["source_id"],
            started_at=datetime.now(UTC),
        )
        self.snapshot = _snapshot(
            kwargs["document_id"],
            revision=self.snapshot.revision + 1,
            run=run,
        )
        return self.snapshot, True

    async def workspace_review_context(self, document_id: UUID):
        assert document_id == self.document_id
        if self.model_mutation_busy:
            self.busy_preflight_calls += 1
        changeset_id = self.review_changeset_id or uuid4()
        action_id = self.review_action_id or uuid4()
        action = DocumentPatchAction(
            action_id=action_id,
            operation=DocumentPatchOperation.REVISE,
            path="/job_title",
            target_key="/job_title",
            before=self.snapshot.approved_document.job_title,
            after="候選職稱",
            source_ids=(uuid4(),),
            read_set=(
                DocumentPathRead(path="/job_title", value_sha256="0" * 64),
            ),
        )
        changeset = DocumentChangeSet(
            changeset_id=changeset_id,
            summary="工作區語意審查",
            actions=(action,),
            source_ids=action.source_ids,
            created_revision=self.snapshot.revision,
        )
        digest = "a" * 64
        group = WorkspaceReviewGroup(
            changeset=changeset,
            group_digest=digest,
            semantic_fingerprint=digest,
            evidence_digest=digest,
            employee_request_digest=digest,
            boundary_digest=digest,
        )
        return (
            self.snapshot,
            None,
            SimpleNamespace(
                manifest=SimpleNamespace(
                    generation=0,
                    resource_digest="a" * 64,
                )
            ),
            WorkspaceReviewProjection(workspace_digest="a" * 64, groups=(group,)),
        )

    async def decide_workspace_changes(self, command):
        if self.model_mutation_busy:
            raise ConsultantRunAlreadyActive(command.document_id)
        self.calls.append(("review", command.model_dump(mode="json")))
        return self.snapshot

    async def decide_understanding_calibration(self, **kwargs):
        self.calls.append(("calibration", kwargs))
        return self.snapshot

    async def answer_required_clarification(self, **kwargs):
        self.calls.append(("clarification", kwargs))
        return self.snapshot

    async def apply_direct_edit(self, **kwargs):
        if self.model_mutation_busy:
            raise ConsultantRunAlreadyActive(kwargs["document_id"])
        self.calls.append(("direct_edit", kwargs))
        self.snapshot = self.snapshot.model_copy(
            update={"approved_document": kwargs["document"]}
        )
        return self.snapshot

    async def apply_current_document_edit(self, **kwargs):
        if self.model_mutation_busy:
            raise ConsultantRunAlreadyActive(kwargs["document_id"])
        self.calls.append(("current_document_edit", kwargs))
        self.snapshot = self.snapshot.model_copy(
            update={
                "current_document": kwargs["document"],
                "approved_document": kwargs["document"],
            }
        )
        return self.snapshot

    async def preview_document_structure_command(self, **kwargs):
        self.calls.append(("document_command_preview", kwargs))
        return DocumentCommandBlastRadius(
            preview_digest="b" * 64,
            confirmation_required=True,
            duty_count=1,
            task_count=2,
            affected_names=("法遵管理", "追蹤修法"),
        )

    async def apply_document_structure_command(self, **kwargs):
        if self.model_mutation_busy:
            raise ConsultantRunAlreadyActive(kwargs["document_id"])
        self.calls.append(("document_command", kwargs))
        return self.snapshot, "undo-token-1"

    async def delete_document(self, document_id: UUID):
        assert document_id == self.document_id
        self.deleted = True


class FakeProcessor:
    def __init__(self) -> None:
        self.claimed: set[tuple[UUID, UUID]] = set()
        self.processed: list[tuple[UUID, UUID, UUID]] = []

    async def claim(self, document_id: UUID, run_id: UUID) -> bool:
        key = (document_id, run_id)
        if key in self.claimed:
            return False
        self.claimed.add(key)
        return True

    async def process_claimed(
        self, document_id: UUID, run_id: UUID, source_id: UUID, runtime=None
    ) -> None:
        assert runtime is not None
        self.processed.append((document_id, run_id, source_id))


class FiniteEventRuntime(FakeRuntime):
    """End the production SSE stream after one snapshot event."""

    def __init__(self) -> None:
        super().__init__()
        self.reopen_calls = 0

    async def reopen_document(self, document_id: UUID):
        self.reopen_calls += 1
        if self.reopen_calls > 1:
            raise DocumentNotFound(document_id)
        return await super().reopen_document(document_id)


@pytest_asyncio.fixture
async def api():
    runtime = FakeRuntime()
    processor = FakeProcessor()
    app = FastAPI()
    app.include_router(consultant.router, prefix="/api/v1")
    app.dependency_overrides[get_consultant_runtime] = lambda: runtime
    app.dependency_overrides[get_consultant_turn_processor] = lambda: processor
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client, runtime, processor


async def _create(client: httpx.AsyncClient):
    return await client.post(
        BASE,
        headers={"Idempotency-Key": "create-1"},
        json={"title": "採購職務"},
    )


async def test_http_command_receipt_binds_key_kind_and_canonical_payload() -> None:
    document_id = uuid4()
    first = consultant._command_receipt(
        document_id,
        "document_review",
        "review-key",
        {"decision": {"command": "accept_changes"}, "changeset_id": "one"},
    )
    reordered = consultant._command_receipt(
        document_id,
        "document_review",
        "review-key",
        {"changeset_id": "one", "decision": {"command": "accept_changes"}},
    )
    changed = consultant._command_receipt(
        document_id,
        "document_review",
        "review-key",
        {"changeset_id": "one", "decision": {"command": "reject_changes"}},
    )

    assert reordered == first
    assert changed.command_id == first.command_id
    assert changed.payload_sha256 != first.payload_sha256


async def test_catalog_create_read_snapshot_and_delete(api) -> None:
    client, runtime, _ = api
    created = await _create(client)

    assert created.status_code == 201
    document_id = UUID(created.json()["document_id"])
    assert runtime.document_id == document_id
    assert (await client.get(BASE)).json()["documents"][0]["title"] == "採購職務"
    assert (await client.get(f"{BASE}/{document_id}")).status_code == 200
    snapshot = await client.get(f"{BASE}/{document_id}/snapshot")
    assert snapshot.json()["document_id"] == str(document_id)
    assert "pause" not in snapshot.text
    assert "finish" not in snapshot.text

    deleted = await client.delete(f"{BASE}/{document_id}")
    assert deleted.status_code == 204
    assert runtime.deleted is True


async def test_snapshot_returns_typed_authority_conflict_without_valid_current_document(
    api,
) -> None:
    client, runtime, _ = api
    document_id = UUID((await _create(client)).json()["document_id"])
    runtime.snapshot = runtime.snapshot.model_copy(update={"current_document": None})

    response = await client.get(f"{BASE}/{document_id}/snapshot")

    assert response.status_code == 409
    assert response.json()["type"] == AUTHORITY_CONFLICT


async def test_snapshot_events_encode_native_sse_from_production_route() -> None:
    runtime = FiniteEventRuntime()
    document_id = uuid4()
    await runtime.create_document(document_id, title="採購職務")
    app = FastAPI()
    app.include_router(consultant.router, prefix="/api/v1")
    app.dependency_overrides[get_consultant_runtime] = lambda: runtime

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"{BASE}/{document_id}/events")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    lines = response.text.splitlines()
    assert [line for line in lines if line.startswith("event:")] == [
        "event: snapshot",
        "event: snapshot",
    ]
    assert [line for line in lines if line.startswith("id:")] == [
        "id: 0",
        "id: 0",
    ]
    assert [line for line in lines if line.startswith("retry:")] == [
        "retry: 1000"
    ]
    assert [
        json.loads(line.removeprefix("data: "))
        for line in lines
        if line.startswith("data: ")
    ] == [
        {
            "event": "snapshot_changed",
            "document_id": str(document_id),
            "revision": 0,
            "run_id": None,
        },
        {
            "event": "document_deleted",
            "document_id": str(document_id),
            "revision": 0,
            "run_id": None,
        },
    ]


async def test_snapshot_events_resume_without_replaying_seen_revision() -> None:
    runtime = FiniteEventRuntime()
    document_id = uuid4()
    await runtime.create_document(document_id, title="採購職務")
    app = FastAPI()
    app.include_router(consultant.router, prefix="/api/v1")
    app.dependency_overrides[get_consultant_runtime] = lambda: runtime

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"{BASE}/{document_id}/events",
            headers={"Last-Event-ID": "0"},
        )

    assert response.status_code == 200
    assert '"event": "snapshot_changed"' not in response.text
    assert '"event": "document_deleted"' in response.text
    assert "id: 0" in response.text
    assert "retry:" not in response.text


async def test_snapshot_events_reject_invalid_resume_header_as_problem() -> None:
    runtime = FakeRuntime()
    app = app_factory.configure(FastAPI())
    app.dependency_overrides[get_consultant_runtime] = lambda: runtime

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"{BASE}/{uuid4()}/events",
            headers={"Last-Event-ID": "invalid"},
        )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )
    assert response.json()["type"] == INVALID_REQUEST


async def test_answer_is_source_first_202_idempotent_and_background_owned(api) -> None:
    client, runtime, processor = api
    document_id = UUID((await _create(client)).json()["document_id"])

    accepted = await client.post(
        f"{BASE}/{document_id}/answers",
        headers={"Idempotency-Key": "answer-1"},
        json={"text": "我每天整理採購需求。", "supersedes_source_id": None},
    )
    assert accepted.status_code == 202
    payload = accepted.json()
    assert payload["status"] == "source_saved"
    assert processor.processed == [
        (document_id, UUID(payload["run_id"]), UUID(payload["source_id"]))
    ]
    reopened = await client.get(f"{BASE}/{document_id}/snapshot")
    assert reopened.json()["employee_messages"] == [
        {
            "source_id": payload["source_id"],
            "text": "我每天整理採購需求。",
            "created_at": reopened.json()["employee_messages"][0]["created_at"],
            "processing_status": "pending",
            "validity": "current",
            "supersedes_source_id": None,
            "superseded_by_source_id": None,
        }
    ]

    runtime.active_conflict = True
    blocked = await client.post(
        f"{BASE}/{document_id}/answers",
        headers={"Idempotency-Key": "answer-2"},
        json={"text": "另一則回答", "supersedes_source_id": None},
    )
    assert blocked.status_code == 409
    assert blocked.json()["type"].endswith("/consultant-run-active")
    assert (await client.get(f"{BASE}/{document_id}/snapshot")).status_code == 200


async def test_failed_run_retries_the_same_durable_source_after_reopening(api) -> None:
    client, runtime, processor = api
    document_id = UUID((await _create(client)).json()["document_id"])
    accepted = await client.post(
        f"{BASE}/{document_id}/answers",
        headers={"Idempotency-Key": "answer-to-retry"},
        json={"text": "這段原話不能重複建立。", "supersedes_source_id": None},
    )
    run_id = UUID(accepted.json()["run_id"])
    source_id = UUID(accepted.json()["source_id"])
    runtime.snapshot = _snapshot(
        document_id,
        revision=2,
        run=RunReceipt(
            run_id=run_id,
            status=RunStatus.FAILED,
            source_id=source_id,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            error_code="provider_timeout",
        ),
    )
    processor.processed.clear()
    processor.claimed.clear()

    retried = await client.post(f"{BASE}/{document_id}/runs/{run_id}/retry")

    assert retried.status_code == 202, retried.text
    assert retried.json()["source_id"] == str(source_id)
    assert processor.processed == [(document_id, run_id, source_id)]
    assert len(runtime.sources) == 1


async def test_employee_review_calibration_clarification_and_direct_edit_are_distinct(api) -> None:
    client, runtime, processor = api
    document_id = UUID((await _create(client)).json()["document_id"])
    changeset_id = uuid4()
    action_id = uuid4()
    runtime.review_changeset_id = changeset_id
    runtime.review_action_id = action_id
    calibration_id = uuid4()
    clarification_id = uuid4()

    review = await client.post(
        f"{BASE}/{document_id}/reviews/{changeset_id}",
        headers={"Idempotency-Key": "review-1", "X-Expected-Revision": "0"},
        json={
            "command": "accept_changes",
            "action_ids": [str(action_id)],
            "edited_after_by_action_id": {},
            "rejection_reason": None,
        },
    )
    assert review.status_code == 200, review.text
    assert runtime.calls[-1][0] == "review"

    confirmed = await client.post(
        f"{BASE}/{document_id}/calibrations/{calibration_id}",
        headers={"Idempotency-Key": "calibration-1", "X-Expected-Revision": "0"},
        json={"decision": "confirm", "employee_text": "我確認上述理解正確"},
    )
    assert confirmed.status_code == 200
    assert runtime.calls[-1][0] == "calibration"

    correction = await client.post(
        f"{BASE}/{document_id}/calibrations/{calibration_id}",
        headers={"Idempotency-Key": "calibration-correction"},
        json={"decision": "direct_correction", "employee_text": "應改成每週整理"},
    )
    assert correction.status_code == 202
    assert runtime.calls[-1][0] == "answer"
    assert processor.processed

    clarified = await client.post(
        f"{BASE}/{document_id}/clarifications/{clarification_id}",
        headers={"Idempotency-Key": "clarify-1", "X-Expected-Revision": "1"},
        json={"choice": "主要負責", "text": "這是我主要負責的工作"},
    )
    assert clarified.status_code == 200
    assert runtime.calls[-1][0] == "clarification"

    document = runtime.snapshot.approved_document.model_dump(mode="json")
    document["job_title"] = "採購專員"
    edited = await client.put(
        f"{BASE}/{document_id}/approved-document",
        headers={"Idempotency-Key": "edit-1", "X-Expected-Revision": "1"},
        json={"document": document},
    )
    assert edited.status_code == 200, edited.text
    assert runtime.calls[-1][0] == "direct_edit"


async def test_review_and_document_edits_return_clear_busy_conflict_during_model_mutation(
    api,
) -> None:
    client, runtime, _ = api
    document_id = UUID((await _create(client)).json()["document_id"])
    changeset_id = uuid4()
    action_id = uuid4()
    runtime.review_changeset_id = changeset_id
    runtime.review_action_id = action_id
    runtime.model_mutation_busy = True

    review = await client.post(
        f"{BASE}/{document_id}/reviews/{changeset_id}",
        headers={"Idempotency-Key": "busy-review", "X-Expected-Revision": "0"},
        json={
            "command": "accept_changes",
            "action_ids": [str(action_id)],
            "edited_after_by_action_id": {},
            "rejection_reason": None,
        },
    )
    document = runtime.snapshot.approved_document.model_dump(mode="json")
    document["job_title"] = "忙碌時不得交錯寫入"
    direct_edit = await client.put(
        f"{BASE}/{document_id}/approved-document",
        headers={"Idempotency-Key": "busy-edit", "X-Expected-Revision": "0"},
        json={"document": document},
    )
    current_edit = await client.put(
        f"{BASE}/{document_id}/current-document",
        headers={"Idempotency-Key": "busy-current", "X-Expected-Revision": "0"},
        json={
            "document": document,
            "workspace_generation": 1,
            "workspace_digest": "a" * 64,
        },
    )

    for response in (review, direct_edit, current_edit):
        assert response.status_code == 409
        assert response.json()["type"] == CONSULTANT_RUN_ACTIVE
        assert response.json()["title"] == "Document is busy with an active consultant run"
    assert runtime.calls == []
    assert runtime.employee_admission_entries == 3
    assert runtime.busy_preflight_calls == 0


async def test_direct_edit_server_mints_opks_evidence_instead_of_trusting_the_browser(api) -> None:
    client, runtime, _ = api
    document_id = UUID((await _create(client)).json()["document_id"])
    document = runtime.snapshot.approved_document.model_dump(mode="json")
    document["opks"] = [
        {
            "item_id": str(uuid4()),
            "kind": "attitude",
            "text": "謹慎",
            "display_order": 0,
            "task_ids": [],
            "indicator_ids": [],
        }
    ]

    edited = await client.put(
        f"{BASE}/{document_id}/approved-document",
        headers={"Idempotency-Key": "edit-opks-1", "X-Expected-Revision": "0"},
        json={"document": document},
    )

    assert edited.status_code == 200, edited.text
    passed_document = runtime.calls[-1][1]["document"]
    assert passed_document.opks[0].evidence_source_ids == (
        consultant._command_id(document_id, "direct-edit-source", "edit-opks-1"),
    )


async def test_current_document_edit_forwards_full_server_stale_guards(api) -> None:
    client, runtime, _ = api
    document_id = UUID((await _create(client)).json()["document_id"])
    document = runtime.snapshot.current_document.model_dump(mode="json")
    document["job_title"] = "資深採購專員"

    response = await client.put(
        f"{BASE}/{document_id}/current-document",
        headers={
            "Idempotency-Key": "current-edit-1",
            "X-Expected-Revision": "0",
        },
        json={
            "document": document,
            "workspace_generation": 1,
            "workspace_digest": "a" * 64,
        },
    )

    assert response.status_code == 200, response.text
    call = next(item for item in runtime.calls if item[0] == "current_document_edit")
    assert call[1]["workspace_generation"] == 1
    assert call[1]["workspace_digest"] == "a" * 64
    assert response.json()["current_document"]["job_title"] == "資深採購專員"


async def test_document_structure_preview_is_server_derived_and_read_only(api) -> None:
    client, runtime, _ = api
    document_id = UUID((await _create(client)).json()["document_id"])

    response = await client.post(
        f"{BASE}/{document_id}/current-document/commands/preview",
        headers={"X-Expected-Revision": "0"},
        json={
            "command": {
                "operation": "cascade_delete_duty",
                "duty_id": str(uuid4()),
            },
            "workspace_generation": 1,
            "workspace_digest": "a" * 64,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["confirmation_required"] is True
    assert response.json()["task_count"] == 2
    call = runtime.calls[-1]
    assert call[0] == "document_command_preview"
    assert call[1]["command"].operation == "cascade_delete_duty"
    assert runtime.employee_admission_entries == 0


async def test_document_structure_execute_returns_one_bounded_undo_token(api) -> None:
    client, runtime, _ = api
    document_id = UUID((await _create(client)).json()["document_id"])

    response = await client.post(
        f"{BASE}/{document_id}/current-document/commands",
        headers={
            "Idempotency-Key": "create-duty-1",
            "X-Expected-Revision": "0",
        },
        json={
            "command": {"operation": "create_duty", "name": "法遵管理"},
            "workspace_generation": 1,
            "workspace_digest": "a" * 64,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["undo_token"] == "undo-token-1"
    assert response.json()["snapshot"]["document_id"] == str(document_id)
    call = runtime.calls[-1]
    assert call[0] == "document_command"
    assert call[1]["command"].operation == "create_duty"
    assert call[1]["source_id"] != call[1]["command_receipt"].command_id
    assert runtime.employee_admission_entries == 1


async def test_document_structure_api_maps_indicator_wire_kind_to_domain_p(api) -> None:
    client, runtime, _ = api
    document_id = UUID((await _create(client)).json()["document_id"])

    response = await client.post(
        f"{BASE}/{document_id}/current-document/commands",
        headers={
            "Idempotency-Key": "create-indicator-1",
            "X-Expected-Revision": "0",
        },
        json={
            "command": {
                "operation": "create_opks",
                "task_id": str(uuid4()),
                "kind": "indicator",
                "text": "每週完成一次更新",
            },
            "workspace_generation": 1,
            "workspace_digest": "a" * 64,
        },
    )

    assert response.status_code == 200, response.text
    command = runtime.calls[-1][1]["command"]
    assert command.kind.value == "indicator"


async def test_export_requires_explicit_force_when_readiness_has_gaps(api) -> None:
    client, runtime, _ = api
    document_id = UUID((await _create(client)).json()["document_id"])

    state = initial_thread_state(document_id)
    state["approved_document"]["job_title"] = "已核准名稱"
    gap_id = uuid4()
    state["gaps"] = {
        str(gap_id): {
            "gap_id": str(gap_id),
            "reason": "work_coverage_missing",
            "description": "仍有工作內容待補齊。",
            "subject_kind": "task",
            "subject_id": None,
            "blocks_dependent_analysis": False,
            "status": "active",
            "source_ids": [str(uuid4())],
            "last_changed_revision": 0,
        }
    }
    runtime.snapshot = _store_enriched_snapshot(state)

    blocked = await client.get(f"{BASE}/{document_id}/export")
    assert blocked.status_code == 409
    assert blocked.json()["type"].endswith("/export-confirmation-required")

    forced = await client.get(f"{BASE}/{document_id}/export?force=true")
    assert forced.status_code == 200
    assert forced.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    workbook = load_workbook(BytesIO(forced.content), data_only=False)
    values = {
        str(cell.value)
        for row in workbook.active.iter_rows()
        for cell in row
        if cell.value is not None
    }
    assert any("已核准名稱" in value for value in values)
    assert all("尚待審核名稱" not in value for value in values)


async def test_invalid_client_fields_and_pause_finish_routes_are_rejected(api) -> None:
    client, _, _ = api
    document_id = UUID((await _create(client)).json()["document_id"])

    invalid = await client.post(
        f"{BASE}/{document_id}/answers",
        headers={"Idempotency-Key": "bad"},
        json={"text": "回答", "role": "system"},
    )
    assert invalid.status_code == 422
    assert (await client.post(f"{BASE}/{document_id}/pause")).status_code == 404
    assert (await client.post(f"{BASE}/{document_id}/finish")).status_code == 404
