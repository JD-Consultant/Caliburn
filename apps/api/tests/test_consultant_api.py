from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from openpyxl import load_workbook

from app.adapters.langgraph.postgres import (
    ActiveConsultantRun,
    ConsultantDocumentCatalogEntry,
)
from app.api.deps import get_consultant_runtime, get_consultant_turn_processor
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
from app.consultant.views import snapshot_from_state


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
    return snapshot_from_state(state)


class FakeRuntime:
    def __init__(self) -> None:
        self.document_id: UUID | None = None
        self.title = "採購職務"
        self.deleted = False
        self.snapshot = None
        self.active_conflict = False
        self.calls: list[tuple[str, dict]] = []
        self.sources: list[EmployeeSource] = []

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
        return self.snapshot

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

    async def decide_document_changes(self, **kwargs):
        self.calls.append(("review", kwargs))
        return self.snapshot

    async def decide_understanding_calibration(self, **kwargs):
        self.calls.append(("calibration", kwargs))
        return self.snapshot

    async def answer_required_clarification(self, **kwargs):
        self.calls.append(("clarification", kwargs))
        return self.snapshot

    async def apply_direct_edit(self, **kwargs):
        self.calls.append(("direct_edit", kwargs))
        self.snapshot = self.snapshot.model_copy(
            update={"approved_document": kwargs["document"]}
        )
        return self.snapshot

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
    assert review.status_code == 200
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


async def test_export_requires_explicit_force_when_readiness_has_gaps(api) -> None:
    client, runtime, _ = api
    document_id = UUID((await _create(client)).json()["document_id"])

    source_id = uuid4()
    changeset_id = uuid4()
    action = DocumentPatchAction(
        action_id=uuid4(),
        operation=DocumentPatchOperation.REVISE,
        path="/job_title",
        target_key="/job_title",
        before="已核准名稱",
        after="尚待審核名稱",
        source_ids=(source_id,),
        read_set=(
            DocumentPathRead(path="/job_title", value_sha256="0" * 64),
        ),
    )
    changeset = DocumentChangeSet(
        changeset_id=changeset_id,
        summary="修改職務名稱",
        actions=(action,),
        source_ids=(source_id,),
        created_revision=0,
    )
    state = initial_thread_state(document_id)
    state["approved_document"]["job_title"] = "已核准名稱"
    state["review_queue"] = {
        str(changeset_id): changeset.model_dump(mode="json")
    }
    runtime.snapshot = snapshot_from_state(state)

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
