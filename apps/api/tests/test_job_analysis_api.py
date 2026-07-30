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


class _Tasks:
    def __init__(self, store: _Store) -> None:
        self.store = store

    async def list(self, document_id: UUID):
        return self.store.tasks


class _Proposals:
    async def list(self, document_id: UUID, *, statuses=None):
        return ()


class _Journal:
    async def list_recent_turns(self, document_id: UUID, *, limit):
        return ()


class _UnitOfWork:
    def __init__(self, store: _Store) -> None:
        self.documents = _Documents(store)
        self.tasks = _Tasks(store)
        self.proposals = _Proposals()
        self.journal = _Journal()

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
