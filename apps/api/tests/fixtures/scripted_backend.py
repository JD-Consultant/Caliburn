"""Run the real backend against a scripted provider, for browser journeys only.

The isolated database and schema come from CALIBURN_DATABASE_URL and CALIBURN_DATABASE_SCHEMA
(a ``_test`` database you initialized with Alembic); nothing is migrated or erased here. Only
the SDK's HTTP transport is replaced, so routers, Graph, saver, supervisors and PostgreSQL are
the product's own. The control routes under /__script exist on this process alone.

Usage (from apps/api): python -m tests.fixtures.scripted_backend --port 8101
"""

import argparse
from dataclasses import replace
from typing import Any

import httpx2
import uvicorn
from fastapi import FastAPI

from caliburn import bootstrap
from caliburn.settings import ModelSettings, Settings
from tests.fixtures.scripted_model import ScriptedModel

SYNTHETIC_KEY = "synthetic-not-a-real-key"


def create_scripted_app(settings: Settings, model: ScriptedModel) -> FastAPI:
    """Route the app's SDK client to the scripted model instead of the network."""
    create_direct_client = bootstrap.create_responses_client

    def create_scripted_client(*, api_key: str, timeout_seconds: float, **_unused: Any) -> Any:
        return create_direct_client(
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(model.handle)),
        )

    bootstrap.create_responses_client = create_scripted_client
    app = bootstrap.create_app(replace(settings, model=ModelSettings(api_key=SYNTHETIC_KEY)))
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
