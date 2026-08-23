from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.app_factory import configure
from app.adapters.langgraph.postgres import open_postgres_consultant_runtime
from app.adapters.openrouter.langchain import build_openrouter_chat_model
from app.config import settings
from app.consultant.run_service import ConsultantTurnProcessor
from app.database import engine
from app.logging_config import setup_logging

setup_logging(debug=settings.debug)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is managed by Alembic (alembic upgrade head) — no create_all here.
    async with open_postgres_consultant_runtime(settings.database_url) as runtime:
        app.state.consultant_runtime = runtime
        app.state.consultant_turn_processor = ConsultantTurnProcessor(
            settings,
            model_factory=lambda execution: build_openrouter_chat_model(
                execution,
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
            ),
        )
        yield
    await engine.dispose()


# REST-only entry (tests / docker). Wiring comes from the single composition
# root in app_factory.configure(T12 後唯一入口;run_live.py 直起本 app,ADR 0017/0030).
app = configure(
    FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="企業崗位知識萃取與職務說明書生成 AI",
        lifespan=lifespan,
    )
)
