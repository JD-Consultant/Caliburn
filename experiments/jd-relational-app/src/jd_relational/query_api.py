"""Read/change HTTP adapter for the local JD App, with no mutation routes.

The host supplies resources through the native lifespan. This adapter does not
open DB connections, initialize tables, read environment/key files or create a
writer. Blocking read services run in FastAPI's native sync endpoint threadpool.
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
import logging
from time import perf_counter
from typing import Annotated, Protocol
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.middleware.body_limit import RequestBodyLimitMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from .generated.query_http import QueryProblem
from .generated.reads import (
    ChangeReadInput, ChangeReadPage, ReadInput, ReadPage, RestorePreviewInput, RestorePreviewPage,
)
from .query_http import query_problem
from .read_transport import parse_read_arguments
from .change_transport import parse_change_arguments, parse_restore_preview_arguments
from .reads import ReadError

LOG = logging.getLogger("caliburn.jd.http")


class QueryReader(Protocol):
    def read(self, document_id: str, arguments: dict) -> dict: ...


@dataclass(frozen=True)
class QueryServices:
    reads: QueryReader
    changes: QueryReader


def _problem(scope, code):
    result = query_problem(code, request_id=scope["jd.request_id"])
    return JSONResponse(
        result.body,
        status_code=result.status_code,
        media_type=result.media_type,
        headers=result.headers,
    )


class QueryBoundary:
    """Fixed diagnostics and safe exceptions before Starlette's server logger.

    Starlette's generic 500 handler re-raises its original exception. This
    boundary consumes pre-response exceptions without forwarding private args.
    It handles transport failures without creating or changing a write outcome.
    """

    def __init__(self, app):
        self.app = app

    routes = frozenset({
        "/api/documents/{document_id}/jd/read",
        "/api/documents/{document_id}/jd/changes/read",
    })
    interrupted_message = "jd_query_response_interrupted"
    event_name = "jd.http.query"
    log_message = "JD query completed"

    def failure_response(self, scope, error):
        code = error.code if isinstance(error, ReadError) else "read_failed"
        return _problem(scope, code)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = uuid4()
        scope["jd.request_id"] = request_id
        started, response_started, status = perf_counter(), False, 500

        async def send_safe(message):
            nonlocal response_started, status
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() not in {b"cache-control", b"x-request-id"}
                ]
                message = {
                    **message,
                    "headers": headers
                    + [
                        (b"cache-control", b"no-store"),
                        (b"x-request-id", str(request_id).encode("ascii")),
                        (b"x-content-type-options", b"nosniff"),
                    ],
                }
            await send(message)

        try:
            await self.app(scope, receive, send_safe)
        except Exception as error:
            if response_started:
                # Never emit a second response; a transport loss says nothing
                # about JD writes. Suppress the private cause in server logs.
                raise RuntimeError(self.interrupted_message) from None
            await self.failure_response(scope, error)(scope, receive, send_safe)
        finally:
            try:
                route = getattr(scope.get("route"), "path", None)
                LOG.log(
                    logging.INFO if status < 500 else logging.WARNING,
                    self.log_message,
                    extra={
                        "event_name": self.event_name,
                        "request_id": str(request_id),
                        "route": (
                            route
                            if route
                            in self.routes
                            else "unmatched"
                        ),
                        "status_code": status,
                        "duration_ms": round((perf_counter() - started) * 1000, 3),
                    },
                )
            except Exception:
                pass


def create_query_app(
    resources: Callable[[], AbstractAsyncContextManager[QueryServices]],
    *,
    allowed_origins: tuple[str, ...] = (),
    _body_limit: int = 16384,
    _boundary_factory=QueryBoundary,
    _allowed_methods: tuple[str, ...] = ("POST",),
    _allowed_headers: tuple[str, ...] = ("Content-Type",),
    _expose_headers: tuple[str, ...] = ("X-Request-ID",),
) -> FastAPI:
    try:
        for origin in allowed_origins:
            url = urlsplit(origin)
            if (
                url.scheme not in {"http", "https"}
                or url.hostname not in {"127.0.0.1", "localhost"}
                or url.username is not None
                or url.password is not None
                or url.path
                or url.query
                or url.fragment
            ):
                raise ValueError("invalid_origin")
            _ = url.port
    except (ValueError, TypeError):
        raise ValueError("explicit_local_origins_required") from None

    @asynccontextmanager
    async def lifespan(app):
        phase = "startup"
        try:
            async with resources() as services:
                app.state.jd_queries = services
                phase = "shutdown"
                try:
                    yield
                finally:
                    del app.state.jd_queries
        except Exception:
            # Starlette reports lifespan exceptions to the server logger. Keep
            # native cleanup, but never forward private driver/configuration
            # arguments or their chained traceback to that boundary.
            raise RuntimeError(f"jd_query_{phase}_failed") from None

    app = FastAPI(
        title="Caliburn JD queries",
        version="0.1.0",
        debug=False,
        lifespan=lifespan,
        strict_content_type=True,
        docs_url=None,
        redoc_url=None,
    )
    # Native body limiter, explicitly installed: FastAPI does not forward the
    # new Starlette constructor's max_body_size argument in this pinned version.
    app.add_middleware(RequestBodyLimitMiddleware, max_body_size=_body_limit)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"], www_redirect=False
    )
    app.add_middleware(_boundary_factory)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(allowed_origins),
        allow_methods=list(_allowed_methods),
        allow_headers=list(_allowed_headers),
        allow_credentials=False,
        expose_headers=list(_expose_headers),
    )

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, error):
        # Do not serialize errors(), body, ctx or raw exception args.
        return _problem(request.scope, "invalid_input")

    async def read_arguments(request: Request, body: ReadInput):
        # FastAPI owns generated request/OpenAPI validation. Recheck original
        # bytes with the shared parser so duplicate JSON keys cannot disappear.
        try:
            return parse_read_arguments((await request.body()).decode("utf-8"))
        except UnicodeError:
            raise ReadError("invalid_input") from None

    async def change_arguments(request: Request, body: ChangeReadInput):
        try:
            return parse_change_arguments((await request.body()).decode("utf-8"))
        except UnicodeError:
            raise ReadError("invalid_input") from None

    async def preview_arguments(request: Request, body: RestorePreviewInput):
        try:
            return parse_restore_preview_arguments((await request.body()).decode("utf-8"))
        except UnicodeError:
            raise ReadError("invalid_input") from None

    errors = {
        status: {"model": QueryProblem, "content": {"application/problem+json": {}}}
        for status in (404, 409, 422, 500)
    }

    @app.post("/api/documents/{document_id}/jd/read", response_model=ReadPage, responses=errors)
    def read(
        document_id: UUID, request: Request, arguments: Annotated[dict, Depends(read_arguments)]
    ):
        return request.app.state.jd_queries.reads.read(str(document_id), arguments)

    @app.post(
        "/api/documents/{document_id}/jd/changes/read",
        response_model=ChangeReadPage,
        responses=errors,
    )
    def changes(
        document_id: UUID, request: Request, arguments: Annotated[dict, Depends(change_arguments)]
    ):
        return request.app.state.jd_queries.changes.read(str(document_id), arguments)

    @app.post(
        "/api/documents/{document_id}/jd/restore/preview",
        response_model=RestorePreviewPage,
        responses=errors,
    )
    def restore_preview(
        document_id: UUID, request: Request, arguments: Annotated[dict, Depends(preview_arguments)]
    ):
        """Reading only: this says what a restore would change, and writes nothing."""
        return request.app.state.jd_queries.changes.preview_restore(str(document_id), arguments)

    # Keep schemas generated from the DTOs. FastAPI associates the default JSON
    # media type with every additional response model; these four responses use
    # RFC 9457, so relocate only that generated media entry via its public hook.
    default_openapi = app.openapi

    def query_openapi():
        schema = default_openapi()
        for path in (
            "/api/documents/{document_id}/jd/read",
            "/api/documents/{document_id}/jd/changes/read",
            "/api/documents/{document_id}/jd/restore/preview",
        ):
            for status in errors:
                content = schema["paths"][path]["post"]["responses"][str(status)]["content"]
                if "application/json" in content:
                    content["application/problem+json"] = content.pop("application/json")
        return schema

    app.openapi = query_openapi
    return app
