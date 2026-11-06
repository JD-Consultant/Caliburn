"""Serve the built SPA and the same application API from one process."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class _SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            if (
                error.status_code != 404
                or Path(path).suffix
                or "text/html" not in Headers(scope=scope).get("accept", "")
            ):
                raise
            return await super().get_response("index.html", scope)


async def health() -> dict[str, str]:
    """Application liveness only; resource readiness belongs to the status command."""
    return {"status": "ok"}


async def _redirect_api_root(request: Request) -> RedirectResponse:
    return RedirectResponse(request.url.path + "/")


def build_web_app(api: FastAPI, directory: Path) -> FastAPI:
    """Mount API before static files; retain the API-owned resource lifetime."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with api.router.lifespan_context(api):
            yield

    app = FastAPI(lifespan=lifespan, openapi_url=None, docs_url=None, redoc_url=None)
    app.add_api_route("/health", health)
    app.add_route("/api", _redirect_api_root)
    app.mount("/api", api)
    app.mount("/", _SPAStaticFiles(directory=directory, html=True))
    return app
