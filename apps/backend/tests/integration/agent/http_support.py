"""正式 HTTP lifespan、離線模型與真 PG 的共用測試組裝。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx2
from fastapi import FastAPI
from sqlalchemy import Engine

from caliburn.host.agent_settings import AgentConfiguration
from caliburn.host.app import build_app
from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION
from tests.unit.modules.agent.offline_openai import MODEL_REQUEST, offline_client


@asynccontextmanager
async def api_app(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    transport: httpx2.MockTransport,
    *,
    bundles: tuple[BundleConfig, ...] = (),
    max_active_turns: int = 8,
    resume_version: str = "v1",
    agent_id: str = "http-test",
) -> AsyncIterator[FastAPI]:
    async with open_postgres_checkpointer(checkpoint_conninfo, initialize=True):
        pass
    app = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url=pg_engine.url.render_as_string(hide_password=False),
        agent_configuration=AgentConfiguration(
            agent_id=agent_id,
            resume_version=resume_version,
            checkpoint_conninfo=checkpoint_conninfo,
            model_settings=MODEL_REQUEST,
            bundles=bundles,
            max_active_turns=max_active_turns,
            client_factory=lambda: offline_client(transport),
        ),
    )
    async with app.router.lifespan_context(app):
        yield app


@asynccontextmanager
async def api_client(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    transport: httpx2.MockTransport,
    *,
    bundles: tuple[BundleConfig, ...] = (),
    max_active_turns: int = 8,
    resume_version: str = "v1",
    agent_id: str = "http-test",
) -> AsyncIterator[httpx2.AsyncClient]:
    async with (
        api_app(
            pg_engine,
            checkpoint_conninfo,
            transport,
            bundles=bundles,
            max_active_turns=max_active_turns,
            resume_version=resume_version,
            agent_id=agent_id,
        ) as app,
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url="http://testserver"
        ) as client,
    ):
        yield client
