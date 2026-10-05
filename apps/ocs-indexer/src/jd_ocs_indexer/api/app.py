"""create_app() factory + lifespan.

Lifespan loads BGE-M3 + the Qdrant client once into app.state. Tests inject
fakes via create_app(embedder=..., client=...) so no 2GB model / live Qdrant.
The factory is also the extension point for future middleware (auth / CORS).
"""

from __future__ import annotations

import threading
from contextlib import ExitStack, asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from jd_ocs_indexer.api import reference_routes, routes
from jd_ocs_indexer.config import Settings
from jd_ocs_indexer.references.errors import (
    ReferenceIndexError,
    ReferenceNotFoundError,
    ReferenceProviderError,
    ReferenceQueryError,
)
from jd_ocs_indexer.references.service import ReferenceSearch


def create_app(
    *,
    settings: Settings | None = None,
    embedder=None,
    client=None,
    reference_search: ReferenceSearch | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from jd_ocs_indexer.config import load_settings

        s = settings or load_settings()
        app.state.settings = s

        with ExitStack() as resources:
            if embedder is not None:
                app.state.embedder = embedder
            else:
                from jd_ocs_indexer.embeddings.factory import make_embedder

                app.state.embedder = make_embedder(s, batch_size=1)
                resources.callback(app.state.embedder.close)
            if client is not None:
                app.state.client = client
            else:
                from jd_ocs_indexer.store.qdrant_client import make_client

                app.state.client = make_client(
                    url=s.qdrant_url, api_key=s.qdrant_api_key, timeout=s.qdrant_timeout
                )
                resources.callback(app.state.client.close)
            app.state.reference_search = reference_search
            if reference_search is None and s.reference_collection:
                from jd_ocs_indexer.references.store import QdrantReferenceStore
                from jd_ocs_indexer.reranking.http_reranker import HttpReranker

                ranker = HttpReranker(s.reranker_url or s.embedder_url)
                resources.callback(ranker.close)
                app.state.reference_search = ReferenceSearch(
                    QdrantReferenceStore(
                        app.state.client,
                        s.reference_collection,
                        app.state.embedder.signature,
                    ),
                    app.state.embedder,
                    ranker,
                    candidate_limit=s.reference_candidate_limit,
                )
            # GPU query calls share a bounded, serialized model lane. Reads do not hold it.
            app.state.embed_lock = threading.Lock()
            yield

    app = FastAPI(title="jd-ocs-indexer query API", version="1.0", lifespan=lifespan)

    @app.exception_handler(UnexpectedResponse)
    async def _qdrant_unexpected(request, exc):  # noqa: ANN001
        return JSONResponse(status_code=502, content={"detail": "qdrant error"})

    @app.exception_handler(ResponseHandlingException)
    async def _qdrant_unreachable(request, exc):  # noqa: ANN001
        return JSONResponse(status_code=503, content={"detail": "qdrant unreachable"})

    from jd_ocs_indexer.embeddings.base import (
        EmbeddingMismatchError,
        EmbeddingResponseError,
    )

    @app.exception_handler(EmbeddingMismatchError)
    async def _embed_mismatch(request, exc):  # noqa: ANN001
        return JSONResponse(status_code=409, content={"detail": f"embedding mismatch: {exc}"})

    def reference_handler(status: int, code: str):
        async def handle(request, exc):
            return JSONResponse(status_code=status, content={"detail": {"code": code}})

        return handle

    for error, status, code in (
        (ReferenceNotFoundError, 404, "reference_not_found"),
        (ReferenceIndexError, 409, "reference_index_incompatible"),
        (ReferenceProviderError, 502, "reference_provider_invalid_response"),
        (EmbeddingResponseError, 502, "embedding_provider_invalid_response"),
        (ReferenceQueryError, 422, "reference_query_invalid"),
        (httpx.HTTPError, 503, "model_service_unavailable"),
    ):
        app.add_exception_handler(error, reference_handler(status, code))

    app.include_router(routes.router)
    app.include_router(reference_routes.router)
    return app
