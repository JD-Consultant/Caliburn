"""Composition root: the single wiring source for the REST app (ADR 0017).

``configure(app)`` attaches tracing, the aggregated ``api_router``, CORS, and
the ``/healthz`` readiness endpoint. T12(ADR 0030)後唯一入口=``app.main``
(tests 與 production 同一顆;run_live.py 直起 ``app.main:app``)。
"""
from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from job_analysis_contract import ProblemFieldError
from sqlalchemy import text

from app.api.problems import INVALID_REQUEST, problem_response
from app.api.router import api_router
from app.config import settings
from app.database import AsyncSessionLocal
from app.observability import setup_tracing


async def _request_validation_error(
    request: Request,
    exc: RequestValidationError,
):
    if not request.url.path.startswith("/api/v1/job-analysis/"):
        return await request_validation_exception_handler(request, exc)
    errors = [
        ProblemFieldError(
            field=".".join(str(part) for part in error["loc"] if part != "body"),
            message=error["msg"],
        )
        for error in exc.errors()
    ]
    return problem_response(
        type_uri=INVALID_REQUEST,
        title="Invalid request",
        status=422,
        errors=errors,
    )


def configure(app: FastAPI) -> FastAPI:
    setup_tracing()   # 冪等;T12 後 live app 不再自呼,tracing 起點統一在此(ADR 0030 T6)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(RequestValidationError, _request_validation_error)
    app.include_router(api_router)

    @app.get("/healthz")
    async def healthz():
        """Readiness: process is up AND Postgres reachable. K8s ``healthz`` is
        deprecated (→ livez/readyz); we keep it until containerization (ADR 0017)."""
        db_ok = False
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            db_ok = True
        except Exception:
            pass
        return {
            "status": "ok" if db_ok else "degraded",
            "db": db_ok,
            "app": settings.app_name,
        }

    return app
