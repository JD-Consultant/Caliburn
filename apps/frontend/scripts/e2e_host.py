"""以正式 Host、離線 SDK 和獨立合成 PostgreSQL schemas 執行前端 E2E。"""

import argparse
import asyncio
import json
import logging
import os
import socket
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy import URL

BACKEND = Path(__file__).resolve().parents[2] / "backend"


def prepare(
    *, database_url: URL, port: int, pdf_font: Path, chromium: Path, output: Path
) -> tuple[FastAPI, str]:
    """每次建立新 schema；不讀 .env、不刪除或重用既有 schema。"""
    import httpx2
    from alembic import command
    from alembic.config import Config
    from caliburn.host.agent_settings import AgentConfiguration
    from caliburn.host.app import build_app
    from caliburn.modules.job_description.infrastructure.pdf_renderer import PdfConfiguration
    from caliburn.shared.infrastructure.persistence.database import (
        create_database_engine,
    )
    from e2e_scenario import respond
    from psycopg.conninfo import make_conninfo
    from sqlalchemy import text
    from tests.integration.agent.test_host_reconstruction_journey import BUNDLES
    from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION
    from tests.unit.modules.agent.offline_openai import MODEL_REQUEST, offline_client

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))
    base = create_database_engine(database_url)
    schema = "frontend_e2e_" + uuid4().hex
    checkpoints = "frontend_checkpoint_" + uuid4().hex
    try:
        with base.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'CREATE SCHEMA "{checkpoints}"'))
        url = base.url.update_query_dict({"options": f"-csearch_path={schema}"})
        engine = create_database_engine(url)
        try:
            config = Config(str(BACKEND / "alembic.ini"))
            with engine.begin() as connection:
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
        finally:
            engine.dispose()
        conninfo = make_conninfo(
            base.url.set(drivername="postgresql").render_as_string(hide_password=False),
            options=f"-csearch_path={checkpoints}",
        )
        app = build_app(
            database_url=url.render_as_string(hide_password=False),
            reference_configuration=HOST_REFERENCE_CONFIGURATION,
            agent_configuration=AgentConfiguration(
                agent_id="frontend-legacy-offline",
                resume_version="frontend-offline-v1",
                checkpoint_conninfo=conninfo,
                model_settings=MODEL_REQUEST,
                bundles=BUNDLES,
                client_factory=lambda: offline_client(httpx2.MockTransport(respond)),
            ),
            pdf_configuration=PdfConfiguration(
                font_path=pdf_font, executable_path=chromium
            ),
        )
        output.write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "host": "127.0.0.1",
                    "port": port,
                    "business_schema": schema,
                    "checkpoint_schema": checkpoints,
                    "synthetic_model": True,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return app, conninfo
    finally:
        base.dispose()


async def initialize(conninfo: str) -> None:
    from caliburn.modules.agent.infrastructure.persistence import postgres_checkpointer

    async with postgres_checkpointer.open_postgres_checkpointer(
        conninfo, initialize=True
    ):
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True, help="Loopback HTTP port")
    parser.add_argument(
        "--pdf-font", type=Path, required=True, help="Readable CJK font"
    )
    parser.add_argument(
        "--chromium", type=Path, required=True, help="Installed Chromium executable"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Process/schema JSON output; this file is not a readiness signal",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    for name, path in (("--pdf-font", args.pdf_font), ("--chromium", args.chromium)):
        try:
            with path.open("rb"):
                pass
        except OSError:
            parser.error(f"{name} must name a readable file")
    raw_url = os.environ.get("CALIBURN_E2E_DATABASE_URL")
    if not raw_url:
        parser.error(
            "Set CALIBURN_E2E_DATABASE_URL to a dedicated loopback *_test database"
        )

    sys.path[:0] = [str(BACKEND), str(BACKEND / "src")]
    import pytest
    import uvicorn
    from tests.database_configuration import validated_test_database_url

    try:
        url = validated_test_database_url(raw_url)
    except Exception, pytest.fail.Exception:
        parser.error(
            "CALIBURN_E2E_DATABASE_URL must be a loopback *_test URL without "
            "query parameters; unset PGHOSTADDR and PGSERVICE"
        )
    if url.drivername != "postgresql+psycopg":
        parser.error("CALIBURN_E2E_DATABASE_URL must use postgresql+psycopg")
    os.environ.pop("OPENAI_CUSTOM_HEADERS", None)
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    logging.basicConfig(level=logging.INFO)
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        app, conninfo = prepare(
            database_url=url,
            port=args.port,
            pdf_font=args.pdf_font.resolve(),
            chromium=args.chromium.resolve(),
            output=args.output,
        )
        # 與正式 caliburn.server 相同的 Windows Psycopg 平台設定。
        asyncio.run(
            initialize(conninfo),
            loop_factory=asyncio.SelectorEventLoop if sys.platform == "win32" else None,
        )
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=args.port,
            loop="asyncio:SelectorEventLoop" if sys.platform == "win32" else "auto",
        )
    except Exception as error:
        # 連線設定可能含憑證；CLI 不輸出原始連線例外或 cause chain。
        parser.exit(
            1,
            f"E2E Host failed ({type(error).__name__}); "
            "check the explicit local configuration.\n",
        )


if __name__ == "__main__":
    main()
