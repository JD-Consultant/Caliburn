"""Run the real backend against a scripted provider, for browser journeys only.

The isolated database and schema come from CALIBURN_DATABASE_URL and CALIBURN_DATABASE_SCHEMA
(a ``_test`` database you initialized with Alembic); nothing is migrated or erased here. Only
the SDK's HTTP transport is replaced, so routers, Graph, saver, supervisors and PostgreSQL are
the product's own. The control routes under /__script exist on this process alone.

Usage (from apps/api): python -m tests.fixtures.scripted_backend --port 8101
"""

import argparse
from dataclasses import replace

import httpx2
import uvicorn
from fastapi import FastAPI
from openai import AsyncOpenAI

from caliburn.adapters.openai_responses import create_responses_client
from caliburn.app_composition import AppComposition
from caliburn.bootstrap import create_app
from caliburn.settings import ModelSettings, Settings
from tests.fixtures.scripted_model import ScriptedModel

SYNTHETIC_KEY = "synthetic-not-a-real-key"


def create_scripted_app(settings: Settings, model: ScriptedModel) -> FastAPI:
    """Route the app's SDK client to the scripted model instead of the network."""

    def create_scripted_client(configured: ModelSettings) -> AsyncOpenAI:
        return create_responses_client(
            api_key=configured.api_key,
            timeout_seconds=configured.request_timeout_seconds,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(model.handle)),
        )

    app = create_app(
        replace(settings, model=ModelSettings(api_key=SYNTHETIC_KEY)),
        composition=AppComposition(create_responses_client=create_scripted_client),
    )
    app.include_router(model.control_router())
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8101)
    arguments = parser.parse_args()
    settings = Settings.from_environment()
    if settings.database is None:
        parser.error("Configure CALIBURN_DATABASE_URL for an isolated test database.")
    if not settings.database.url.rstrip("/").endswith("_test"):
        parser.error("The scripted backend only runs against a database whose name ends in _test.")
    uvicorn.run(
        create_scripted_app(settings, ScriptedModel()),
        host="127.0.0.1",
        port=arguments.port,
        loop="asyncio:SelectorEventLoop",
    )


if __name__ == "__main__":
    main()
