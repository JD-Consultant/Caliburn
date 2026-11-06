"""發布版查讀公開表達固定版本，不依賴 Agent 或可變工作稿。"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from caliburn.modules.memory.application.errors import (
    MemoryDataError,
    MemoryVersionNotFoundError,
    WorkspaceNotFoundError,
)
from caliburn.modules.memory.application.results import (
    MemoryInterviewMessage,
)
from caliburn.modules.memory.domain.content import MemoryContent
from caliburn.modules.memory.domain.snapshot import MemorySnapshot
from caliburn.modules.memory.domain.work_memory import WorkMemory
from caliburn.shared.presentation.api.app import build_http_app


class PublishedReader:
    def __init__(self) -> None:
        self.memory = WorkMemory.create(workspace_id=uuid4())
        self.snapshots: dict[int, MemorySnapshot] = {}
        self.failure: Exception | None = None

    def get_current(self, *, workspace_id: UUID) -> WorkMemory:
        if self.failure is not None:
            raise self.failure
        if workspace_id != self.memory.workspace_id:
            raise WorkspaceNotFoundError()
        return self.memory

    def get_published(
        self, *, workspace_id: UUID, published_version: int | None
    ) -> MemorySnapshot | None:
        self.get_current(workspace_id=workspace_id)
        if published_version is None:
            return None
        try:
            return self.snapshots[published_version]
        except KeyError as error:
            raise MemoryVersionNotFoundError() from error

    def list_analysis_sources(
        self, *, workspace_id: UUID, analysis_id: UUID
    ) -> tuple[MemoryInterviewMessage, ...]:
        raise AssertionError("Published HTTP must not read a working analysis")


def client_for(reader: PublishedReader) -> TestClient:
    from caliburn.modules.memory.presentation.api.router import build_memory_router

    return TestClient(build_http_app(build_memory_router(reader)))


def test_empty_memory_read_does_not_create_or_expose_working_content() -> None:
    reader = PublishedReader()
    reader.memory.create_situation(
        content=MemoryContent(title="未發布", description="草稿", body="秘密草稿")
    )
    with client_for(reader) as client:
        response = client.get(f"/workspaces/{reader.memory.workspace_id}/memory")
    assert response.status_code == 200
    assert response.json() == {
        "workspace_id": str(reader.memory.workspace_id),
        "published_version": None,
        "covered_through_message_id": None,
        "items": [],
    }
    assert response.headers["cache-control"] == "no-store"
    assert reader.memory.version == 1


def test_explicit_publication_preserves_original_content_and_source_ids() -> None:
    reader = PublishedReader()
    source_id = uuid4()
    item_id = reader.memory.create_situation(
        content=MemoryContent(title="情境", description="導覽", body="原文"),
        interview_message_ids=(source_id,),
    )
    snapshot = reader.memory.publish(
        covered_through_message_id=source_id, published_at=datetime.now(UTC)
    )
    reader.snapshots[snapshot.version] = snapshot
    reader.memory.revise_situation(
        item_id=item_id,
        content=MemoryContent(title="改名", description="新版", body="新版正文"),
        interview_message_ids=(),
    )
    base = f"/workspaces/{reader.memory.workspace_id}/memory"
    with client_for(reader) as client:
        navigation = client.get(base)
        item = client.get(f"{base}/versions/{snapshot.version}/items/{item_id}")
        explicit = client.get(f"{base}/versions/{snapshot.version}")
    assert navigation.json() == explicit.json()
    assert navigation.json()["items"][0]["title"] == "情境"
    assert "body" not in navigation.json()["items"][0]
    assert item.json()["body"] == "原文"
    assert item.json()["source_ids"] == [str(source_id)]
    assert item.json()["published_version"] == snapshot.version


def test_missing_scope_version_and_item_have_distinct_not_found_results() -> None:
    reader = PublishedReader()
    base = f"/workspaces/{reader.memory.workspace_id}/memory"
    snapshot = reader.memory.publish(
        covered_through_message_id=uuid4(), published_at=datetime.now(UTC)
    )
    reader.snapshots[snapshot.version] = snapshot
    with client_for(reader) as client:
        assert (
            client.get(f"/workspaces/{uuid4()}/memory").json()["detail"]["code"]
            == "workspace_not_found"
        )
        assert (
            client.get(f"{base}/versions/99").json()["detail"]["code"]
            == "memory_version_not_found"
        )
        assert (
            client.get(f"{base}/versions/{snapshot.version}/items/{uuid4()}").json()[
                "detail"
            ]["code"]
            == "memory_item_not_found"
        )
        assert client.post(base, json={}).status_code == 405


@pytest.mark.parametrize("path", ["", "/versions/1"])
def test_corrupt_read_is_failure_with_safe_diagnostics(path: str) -> None:
    reader = PublishedReader()
    reader.failure = MemoryDataError("private-memory-body")
    with client_for(reader) as client:
        response = client.get(f"/workspaces/{reader.memory.workspace_id}/memory{path}")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "memory_unavailable"
    assert "private-memory-body" not in response.text
    assert response.headers["x-request-id"]
