"""Search and fixed source reads through HTTP with a real in-memory Qdrant SDK."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, closing

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from caliburn.modules.occupation_reference.application.errors import (
    ReferenceIndexError,
    ReferenceNotFoundError,
    ReferenceProviderError,
    ReferenceQueryError,
    ReferenceUnavailableError,
    RetrievalBusy,
    RetrievalUnavailable,
)
from caliburn.modules.occupation_reference.application.search import (
    Candidate,
    ReferenceSearch,
)
from caliburn.modules.occupation_reference.domain.source import ReferenceDocument
from caliburn.modules.occupation_reference.infrastructure.execution import (
    RetrievalWorker,
)
from caliburn.modules.occupation_reference.infrastructure.qdrant.store import (
    QdrantReferenceStore,
    index_references,
)
from caliburn.modules.occupation_reference.presentation.api.router import (
    build_reference_router,
)
from caliburn.shared.presentation.api.app import build_http_app
from caliburn.shared.presentation.api.diagnostics import logger as diagnostics_logger
from tests.unit.modules.occupation_reference.source_support import (
    FixedEmbedder,
    FixedReranker,
    source_document,
)

pytestmark = pytest.mark.filterwarnings("ignore:Payload indexes have no effect")


def reference_app(service: ReferenceSearch) -> FastAPI:
    worker = RetrievalWorker()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await worker.aclose()

    return build_http_app(
        build_reference_router(lambda: service, lambda: worker), lifespan=lifespan
    )


def test_http_search_and_complete_pinned_reads_share_the_public_contract() -> None:
    document = source_document()
    embedder = FixedEmbedder()
    with closing(QdrantClient(":memory:")) as database:
        index_references(database, "references", [document], embedder)
        service = ReferenceSearch(
            QdrantReferenceStore(database, "references", embedder.signature),
            embedder,
            FixedReranker(),
        )
        with TestClient(reference_app(service)) as client:
            response = client.post(
                "/occupation-references:search", json={"query": "維護網頁"}
            )
            assert response.status_code == 200, response.text
            result = response.json()
            reference = result["references"][0]["reference"]
            assert len(reference["units"][0]["tasks"]) == 3
            assert result["retrieval_policy"]["candidate_count"] == 1
            assert result["retrieval_policy"]["fusion"] == "full_union_before_rerank"
            base = f"/occupation-references/{document.reference_id}"
            assert client.get(base).json() == reference
            detail = client.get(base + "/tasks/u1-t1").json()
            assert len(detail["names"]) == 3
            assert len(detail["competency_blocks"]) == 2
            assert detail["competency_blocks"][0]["knowledge"] == [
                {"code": None, "name": "工程識圖"}
            ]
            assert client.get(base + "/tasks/u1-t3").status_code == 200
            assert client.get(base + "/tasks/u9-t1").status_code == 404
            assert client.get("/occupation-references/bad-locator").status_code == 404
            schema = client.get("/openapi.json").json()
            request = schema["components"]["schemas"]["ReferenceSearchRequest"]
            assert request["additionalProperties"] is False
            assert set(request["properties"]) == {"query", "limit"}
        assert database.count("references", exact=True).count == 6


class UnavailableStore:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def validate_index(self) -> None:
        raise self.error

    def search(self, dense: list[float], *, route: str, limit: int) -> list[Candidate]:
        raise AssertionError("invalid index must be rejected before search")

    def read(self, reference_id: str) -> ReferenceDocument:
        raise self.error


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (ReferenceIndexError("private"), 409, "reference_index_incompatible"),
        (ReferenceProviderError("private"), 502, "reference_provider_invalid_response"),
        (ReferenceQueryError("private"), 422, "reference_query_invalid"),
        (ReferenceNotFoundError("private"), 404, "reference_not_found"),
        (ReferenceUnavailableError("private"), 503, "reference_service_unavailable"),
        (RetrievalBusy("private"), 503, "retrieval_busy"),
        (RetrievalUnavailable("private"), 503, "retrieval_unavailable"),
    ],
)
def test_http_failures_keep_their_meaning_without_leaking_content(
    error: Exception, status: int, code: str, caplog: pytest.LogCaptureFixture
) -> None:
    service = ReferenceSearch(UnavailableStore(error), FixedEmbedder(), FixedReranker())
    with TestClient(reference_app(service)) as client:
        response = client.post(
            "/occupation-references:search", json={"query": "employee-private-content"}
        )
        assert response.status_code == status
        assert response.json()["detail"]["code"] == code
        assert "private" not in response.text
        if type(error) not in {ReferenceProviderError, ReferenceUnavailableError}:
            assert not any(
                record.name == diagnostics_logger.name for record in caplog.records
            )


@pytest.mark.parametrize(
    ("error_type", "status"),
    [(ReferenceProviderError, 502), (ReferenceUnavailableError, 503)],
)
@pytest.mark.parametrize("operation", ["search", "read", "read_task"])
def test_external_failures_have_correlated_safe_diagnostics(
    error_type: type[RuntimeError],
    status: int,
    operation: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    error = error_type("S:\\private_employee\\source.json underlying-secret-message")
    service = ReferenceSearch(UnavailableStore(error), FixedEmbedder(), FixedReranker())
    with TestClient(reference_app(service)) as client:
        if operation == "search":
            response = client.post(
                "/occupation-references:search",
                json={"query": "employee-private-query"},
            )
        else:
            path = "/occupation-references/private-reference-id"
            if operation == "read_task":
                path += "/tasks/private-task-id"
            response = client.get(path)
    assert response.status_code == status
    records = [
        record for record in caplog.records if record.name == diagnostics_logger.name
    ]
    assert len(records) == 1
    recorded = json.loads(records[0].message)
    assert recorded["request_id"] == response.headers["X-Request-ID"]
    assert recorded["error_type"] == error_type.__name__
    assert recorded["status_code"] == status
    assert recorded["frames"]
    assert all(
        set(frame) == {"file", "function", "line"} for frame in recorded["frames"]
    )
    assert all(
        "/" not in frame["file"] and "\\" not in frame["file"]
        for frame in recorded["frames"]
    )
    for secret in (
        "private_employee",
        "source.json",
        "underlying-secret-message",
        "employee-private-query",
        "private-reference-id",
        "private-task-id",
    ):
        assert secret not in caplog.text
        assert secret not in response.text
