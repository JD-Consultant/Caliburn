from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.app_factory import configure
from app.config import settings
from app.database import engine
from app.logging_config import setup_logging

setup_logging(debug=settings.debug)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is managed by Alembic (alembic upgrade head) — no create_all here.
    yield
    await engine.dispose()


# REST-only entry (tests / docker). Wiring comes from the single composition
# root in app_factory.configure; the live app adds /copilotkit on top (ADR 0017).
app = configure(
    FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="企業崗位知識萃取與職務說明書生成 AI",
        lifespan=lifespan,
    )
)
