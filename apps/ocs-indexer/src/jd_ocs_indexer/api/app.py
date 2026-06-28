"""create_app() factory + lifespan.

Lifespan loads BGE-M3 + the Qdrant client once into app.state. Tests inject
fakes via create_app(embedder=..., client=...) so no 2GB model / live Qdrant.
The factory is also the extension point for future middleware (auth / CORS).
"""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from jd_ocs_indexer.api import routes
from jd_ocs_indexer.config import Settings


def create_app(*, settings: Settings | None = None, embedder=None, client=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        from jd_ocs_indexer.config import load_settings

        s = settings or load_settings()
        app.state.settings = s

        if embedder is not None:
            app.state.embedder = embedder
        else:
            from jd_ocs_indexer.embeddings.factory import make_embedder

            app.state.embedder = make_embedder(s, batch_size=1)

        if client is not None:
            app.state.client = client
        else:
            from jd_ocs_indexer.store.qdrant_client import make_client

            app.state.client = make_client(
                url=s.qdrant_url, api_key=s.qdrant_api_key, timeout=s.qdrant_timeout
            )

        # Guards the BGE-M3 call only (not thread-safe). Scroll endpoints must
        # NOT take this lock, or all reads would serialize behind embedding.
        app.state.embed_lock = threading.Lock()
        yield

    app = FastAPI(title="jd-ocs-indexer query API", version="1.0", lifespan=lifespan)

    @app.exception_handler(UnexpectedResponse)
    async def _qdrant_unexpected(request, exc):  # noqa: ANN001
        return JSONResponse(status_code=502, content={"detail": f"qdrant error: {exc}"})

    @app.exception_handler(ResponseHandlingException)
    async def _qdrant_unreachable(request, exc):  # noqa: ANN001
        return JSONResponse(status_code=503, content={"detail": f"qdrant unreachable: {exc}"})

    from jd_ocs_indexer.embeddings.base import EmbeddingMismatchError

    @app.exception_handler(EmbeddingMismatchError)
    async def _embed_mismatch(request, exc):  # noqa: ANN001
        return JSONResponse(status_code=409, content={"detail": f"embedding mismatch: {exc}"})

    app.include_router(routes.router)
    return app
