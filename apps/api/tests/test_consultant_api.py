from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from app.adapters.langgraph.postgres import (
    ActiveConsultantRun,
    ConsultantDocumentCatalogEntry,
)
from app.api.deps import get_consultant_runtime, get_consultant_turn_processor
from app.api.routes import consultant
from app.consultant.state import RunReceipt, RunStatus, initial_thread_state
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

    async def admit_employee_answer(self, **kwargs):
        if self.active_conflict:
            raise ActiveConsultantRun("another run is recoverable")
        self.calls.append(("answer", kwargs))
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

    runtime.active_conflict = True
    blocked = await client.post(
        f"{BASE}/{document_id}/answers",
        headers={"Idempotency-Key": "answer-2"},
        json={"text": "另一則回答", "supersedes_source_id": None},
    )
    assert blocked.status_code == 409
    assert blocked.json()["type"].endswith("/consultant-run-active")
    assert (await client.get(f"{BASE}/{document_id}/snapshot")).status_code == 200


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
    assert edited.status_code == 200
    assert runtime.calls[-1][0] == "direct_edit"


async def test_export_requires_explicit_force_when_readiness_has_gaps(api) -> None:
    client, _, _ = api
    document_id = UUID((await _create(client)).json()["document_id"])

    blocked = await client.get(f"{BASE}/{document_id}/export")
    assert blocked.status_code == 409
    assert blocked.json()["type"].endswith("/export-confirmation-required")

    forced = await client.get(f"{BASE}/{document_id}/export?force=true")
    assert forced.status_code == 200
    assert forced.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


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
