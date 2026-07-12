"""Composition root: the single wiring source for the REST app (ADR 0017).

``configure(app)`` attaches the aggregated ``api_router``, CORS, and the
``/healthz`` readiness endpoint. Both entry modules call it, so wiring can't
drift. Each entry keeps its OWN lifespan — ``main`` (tests/docker) just disposes
the engine; ``copilotkit_live_app`` (production) additionally opens the PG
checkpointer and mounts ``/copilotkit``. Lifespans legitimately differ; only the
router/CORS/health wiring is unified here.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.config import settings
from app.database import AsyncSessionLocal
from app.observability import setup_tracing


def configure(app: FastAPI) -> FastAPI:
    setup_tracing()   # 冪等;T12 後 live app 不再自呼,tracing 起點統一在此(ADR 0030 T6)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
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
