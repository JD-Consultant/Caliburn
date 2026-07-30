"""Local Web transport contract for greenfield job-analysis documents."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
import pytest_asyncio

from app.api import deps
from app.job_analysis.application import DocumentRecord, DocumentSummary
from app.job_analysis.domain import CurrentWorkModel, JdTask
from app.main import app


pytestmark = pytest.mark.asyncio
NOW = datetime(2026, 7, 30, 9, 0, tzinfo=UTC)
DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000045")


class _Store:
    def __init__(self) -> None:
        self.document: DocumentRecord | None = None
        self.tasks: tuple[JdTask, ...] = ()
        self.proposals = ()
        self.journal = {}
        self.allow_authority_update = True


class _Documents:
    def __init__(self, store: _Store) -> None:
        self.store = store

    async def create(self, record: DocumentRecord) -> None:
        self.store.document = record

    async def get(self, document_id: UUID, *, for_update: bool = False):
        if self.store.document is None:
            return None
        return self.store.document if self.store.document.document_id == document_id else None

    async def list(self):
        if self.store.document is None:
            return ()
        record = self.store.document
        return (
            DocumentSummary(
                document_id=record.document_id,
                title=record.title,
                task_count=len(self.store.tasks),
                updated_at=record.updated_at,
            ),
        )

    async def update_title(
        self,
        document_id: UUID,
        *,
        title: str,
        updated_at: datetime,
    ) -> bool:
        record = await self.get(document_id)
        if record is None:
            return False
        self.store.document = replace(record, title=title, updated_at=updated_at)
        return True

    async def update_authority(
        self,
        document_id: UUID,
        *,
        expected_generation: int,
        work_model,
        active_question,
        updated_at: datetime,
    ) -> bool:
        record = await self.get(document_id)
        if (
            record is None
            or not self.store.allow_authority_update
            or record.authority_generation != expected_generation
        ):
            return False
        self.store.document = replace(
            record,
            work_model=work_model,
            active_question=active_question,
            authority_generation=expected_generation + 1,
            updated_at=updated_at,
        )
        return True


class _Tasks:
    def __init__(self, store: _Store) -> None:
        self.store = store

    async def list(self, document_id: UUID):
        return self.store.tasks

    async def replace(self, document_id: UUID, tasks) -> None:
        self.store.tasks = tasks


class _Proposals:
    def __init__(self, store: _Store) -> None:
        self.store = store

    async def list(self, document_id: UUID, *, statuses=None):
        return self.store.proposals

    async def replace(self, document_id: UUID, proposals) -> None:
        self.store.proposals = proposals


class _Journal:
    def __init__(self, store: _Store) -> None:
        self.store = store

    async def get(self, document_id: UUID, entry_id: str):
        return self.store.journal.get(entry_id)

    async def add(self, entry) -> None:
        self.store.journal[entry.entry_id] = entry

    async def list_conversation_turns(self, document_id: UUID):
        turns = []
        for entry in self.store.journal.values():
            payload = entry.payload
            if hasattr(payload, "consultant_turn") and not hasattr(
                payload, "employee_turn"
            ):
                turns.append(payload.consultant_turn)
            elif hasattr(payload, "employee_turn"):
                turns.extend((payload.employee_turn, payload.consultant_turn))
        return tuple(turns)


class _UnitOfWork:
    def __init__(self, store: _Store) -> None:
        self.documents = _Documents(store)
        self.tasks = _Tasks(store)
        self.proposals = _Proposals(store)
        self.journal = _Journal(store)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def commit(self) -> None:
        return None


@pytest_asyncio.fixture
async def api_client():
    store = _Store()
    dependency = getattr(deps, "get_job_analysis_uow_factory", None)
    if dependency is not None:
        app.dependency_overrides[dependency] = lambda: lambda: _UnitOfWork(store)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, store
    app.dependency_overrides.clear()


async def test_put_creates_then_replaces_only_document_metadata(api_client):
    client, store = api_client

    created = await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}",
        json={"title": "門市營運專員"},
    )
    renamed = await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}",
        json={"title": "資深門市營運專員"},
    )

    assert created.status_code == 201
    assert renamed.status_code == 200
    assert set(renamed.json()) == {"document_id", "title", "updated_at"}
    assert renamed.json()["title"] == "資深門市營運專員"
    assert store.document is not None
    assert store.document.authority_generation == 0
    assert store.document.active_question is not None
    assert store.document.active_question.text == (
        "先不用照職稱回答：你這個職位最主要替誰解決什麼問題？"
    )
    assert len(store.journal) == 1
    opening = next(iter(store.journal.values()))
    assert opening.kind == "consultant_opening"


async def test_list_and_open_return_only_the_current_jd_projection(api_client):
    client, store = api_client
    await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}",
        json={"title": "門市營運專員"},
    )
    store.tasks = (
        JdTask(
            task_id="task-1",
            statement="每週彙整營運週報",
            display_order=0,
        ),
    )

    listed = await client.get("/api/v1/job-analysis/documents")
    opened = await client.get(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}"
    )

    assert listed.status_code == 200
    assert listed.json()[0]["task_count"] == 1
    assert opened.status_code == 200
    assert set(opened.json()) == {"document_id", "title", "updated_at", "tasks"}
    assert opened.json()["tasks"][0]["statement"] == "每週彙整營運週報"
    forbidden = {"authority_generation", "work_model", "journal", "proposals"}
    assert forbidden.isdisjoint(opened.json())


async def test_missing_document_uses_the_stable_problem_type(api_client):
    client, _ = api_client

    response = await client.get(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}"
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == (
        "https://caliburn.dev/problems/job-analysis/document-not-found"
    )


@pytest.mark.parametrize("payload", [{}, {"title": "   "}])
async def test_invalid_document_metadata_uses_problem_details(api_client, payload):
    client, _ = api_client

    response = await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}",
        json=payload,
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )
    assert response.json()["type"] == (
        "https://caliburn.dev/problems/job-analysis/invalid-request"
    )
    assert response.json()["errors"]


async def test_legacy_validation_error_shape_is_unchanged(api_client):
    client, _ = api_client

    response = await client.get("/api/v1/occupations")

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")
    assert "type" not in response.json()
    assert isinstance(response.json()["detail"], list)


def _task_payload(statement: str = " 每週彙整營運週報 "):
    return {
        "statement": statement,
        "purpose_result": " 讓主管掌握營運狀況 ",
        "context": "   ",
        "frequency_text": " 每週一次 ",
        "responsibility_role": "primary",
        "enablers": [{"kind": "tool_system", "name": " Excel "}],
    }


async def test_task_mutations_share_the_authoring_use_cases(api_client):
    client, _ = api_client
    await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}",
        json={"title": "門市營運專員"},
    )

    created = await client.post(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks",
        headers={"Idempotency-Key": "add-1"},
        json=_task_payload(),
    )
    replay = await client.post(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks",
        headers={"Idempotency-Key": "add-1"},
        json=_task_payload(),
    )
    task_id = created.json()["task_id"]
    edited = await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks/{task_id}",
        headers={"Idempotency-Key": "edit-1"},
        json=_task_payload("每週彙整並檢查營運週報"),
    )
    reordered = await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/task-order",
        headers={"Idempotency-Key": "order-1"},
        json={"ordered_task_ids": [task_id]},
    )
    deleted = await client.delete(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks/{task_id}",
        headers={"Idempotency-Key": "delete-1"},
    )
    delete_replay = await client.delete(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks/{task_id}",
        headers={"Idempotency-Key": "delete-1"},
    )

    assert created.status_code == 201
    assert replay.json() == created.json()
    assert created.json()["statement"] == "每週彙整營運週報"
    assert created.json()["context"] is None
    assert created.json()["enablers"][0]["name"] == "Excel"
    assert edited.status_code == 200
    assert edited.json()["statement"] == "每週彙整並檢查營運週報"
    assert reordered.status_code == 200
    assert [item["task_id"] for item in reordered.json()] == [task_id]
    assert deleted.status_code == 204
    assert delete_replay.status_code == 204


@pytest.mark.parametrize(
    ("method", "path", "headers", "payload", "status", "problem_type"),
    [
        (
            "post",
            f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks",
            {},
            _task_payload(),
            422,
            "invalid-request",
        ),
        (
            "post",
            f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks",
            {"Idempotency-Key": "blank"},
            _task_payload("   "),
            422,
            "invalid-request",
        ),
        (
            "post",
            "/api/v1/job-analysis/documents/00000000-0000-0000-0000-000000000099/tasks",
            {"Idempotency-Key": "missing-doc"},
            _task_payload(),
            404,
            "document-not-found",
        ),
        (
            "put",
            f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks/missing-task",
            {"Idempotency-Key": "missing-task"},
            _task_payload(),
            404,
            "task-not-found",
        ),
        (
            "put",
            f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/task-order",
            {"Idempotency-Key": "bad-order"},
            {"ordered_task_ids": ["not-current"]},
            422,
            "invalid-task-order",
        ),
    ],
)
async def test_task_mutation_failures_use_stable_problem_types(
    api_client,
    method,
    path,
    headers,
    payload,
    status,
    problem_type,
):
    client, _ = api_client
    await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}",
        json={"title": "門市營運專員"},
    )

    response = await client.request(method, path, headers=headers, json=payload)

    assert response.status_code == status
    assert response.headers["content-type"].startswith(
        "application/problem+json"
    )
    assert response.json()["type"].endswith(f"/{problem_type}")


async def test_idempotency_conflict_and_authority_conflict_are_distinct(api_client):
    client, store = api_client
    await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}",
        json={"title": "門市營運專員"},
    )
    await client.post(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks",
        headers={"Idempotency-Key": "same-key"},
        json=_task_payload("工作一"),
    )
    idempotency = await client.post(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks",
        headers={"Idempotency-Key": "same-key"},
        json=_task_payload("工作二"),
    )
    store.allow_authority_update = False
    authority = await client.post(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks",
        headers={"Idempotency-Key": "new-key"},
        json=_task_payload("工作三"),
    )

    assert idempotency.status_code == 409
    assert idempotency.json()["type"].endswith("/idempotency-conflict")
    assert authority.status_code == 409
    assert authority.json()["type"].endswith("/authority-conflict")


async def test_delete_with_a_new_key_after_deletion_is_not_found(api_client):
    client, _ = api_client
    await client.put(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}",
        json={"title": "門市營運專員"},
    )
    created = await client.post(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks",
        headers={"Idempotency-Key": "add-delete"},
        json=_task_payload(),
    )
    task_id = created.json()["task_id"]
    await client.delete(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks/{task_id}",
        headers={"Idempotency-Key": "delete-old"},
    )

    response = await client.delete(
        f"/api/v1/job-analysis/documents/{DOCUMENT_ID}/tasks/{task_id}",
        headers={"Idempotency-Key": "delete-new"},
    )

    assert response.status_code == 404
    assert response.json()["type"].endswith("/task-not-found")
