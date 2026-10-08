"""Start one isolated, frozen product App with the established batch spend fence."""

import json
import sys
import zipfile
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path

FROZEN = Path("/tmp/frozen")
with zipfile.ZipFile("/witness/freeze/sources.zip") as archive:
    for name in archive.namelist():
        if name.startswith("apps/api/src/"):
            archive.extract(name, FROZEN)
resource_archive = Path("/witness/resource-freeze/sources.zip")
if resource_archive.exists():
    with zipfile.ZipFile(resource_archive) as archive:
        for name in archive.namelist():
            if name.startswith("apps/api/src/"):
                archive.extract(name, FROZEN)
sys.path.insert(0, str(FROZEN / "apps/api/src"))
sys.path.insert(0, "/shared")

import httpx2
import uvicorn
from alembic import command
from alembic.config import Config
from batch_guard import BatchGuard, GuardedTransport
from caliburn import bootstrap
from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.settings import ModelSettings, Settings

continuation = Path("/witness/continuation-state.json")
if Path("/witness/continuation-state-02.json").exists():
    continuation = Path("/witness/continuation-state-02.json")
if continuation.exists():
    state = json.loads(continuation.read_text(encoding="utf-8"))
    guard = BatchGuard.restore(
        state,
        "/witness/provider-trace.jsonl",
        limit=Decimal(state["approved_total_limit_usd"]),
        deadline=datetime.fromisoformat(state["approved_deadline_at"]),
    )
else:
    guard = BatchGuard(limit=Decimal("0.30"), seconds=3600)


def guarded_client(*, api_key, timeout_seconds):
    transport = GuardedTransport(
        guard, httpx2.AsyncHTTPTransport(retries=0), "/witness/provider-trace.jsonl"
    )
    client = httpx2.AsyncClient(
        transport=transport,
        timeout=timeout_seconds,
        follow_redirects=False,
        trust_env=False,
    )
    return create_responses_client(
        api_key=api_key, timeout_seconds=timeout_seconds, http_client=client
    )


if __name__ == "__main__":
    configuration = Config("/opt/caliburn/alembic.ini")
    command.upgrade(configuration, "head")
    configured = replace(
        Settings.from_environment(),
        model=ModelSettings(api_key=read_openai_api_key(Path("/secret/openai.env"))),
    )
    bootstrap.create_responses_client = guarded_client
    uvicorn.run(
        bootstrap.create_app(configured), host="0.0.0.0", port=8100, log_level="warning"
    )
