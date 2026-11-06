"""唯讀檢查已配置資源；不啟動 Agent、不執行模型或遷移。"""

import json
import os
from pathlib import Path
from typing import TypedDict

import psycopg
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from langgraph.checkpoint.postgres import PostgresSaver
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.engine import make_url

from caliburn.migrate import migration_config
from caliburn.modules.occupation_reference.bootstrap import open_reference_resources
from caliburn.modules.occupation_reference.configuration import (
    load_reference_configuration,
)
from caliburn.shared.infrastructure.persistence.database import create_database_engine


class ResourceStatus(TypedDict):
    status: str


def database_status(database_url: str | None) -> ResourceStatus:
    if not database_url:
        return {"status": "not_configured"}
    try:
        url = make_url(database_url).update_query_dict({"connect_timeout": "5"})
        engine = create_database_engine(url)
        try:
            with engine.connect() as connection:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                current = MigrationContext.configure(connection).get_current_heads()
                expected = ScriptDirectory.from_config(migration_config()).get_heads()
                return {
                    "status": "ready"
                    if set(current) == set(expected)
                    else "migration_required"
                }
        finally:
            engine.dispose()
    except Exception:
        return {"status": "unavailable"}


def checkpoint_status(conninfo: str | None, *, required: bool) -> ResourceStatus:
    if not conninfo:
        return {"status": "not_configured" if required else "disabled"}
    try:
        with psycopg.connect(conninfo, connect_timeout=5) as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            exists = connection.execute(
                "SELECT to_regclass('checkpoint_migrations')"
            ).fetchone()
            if not exists or exists[0] is None:
                return {"status": "migration_required"}
            row = connection.execute(
                "SELECT max(v) FROM checkpoint_migrations"
            ).fetchone()
            return {
                "status": "ready"
                if row and row[0] == len(PostgresSaver.MIGRATIONS) - 1
                else "migration_required"
            }
    except Exception:
        return {"status": "unavailable"}


def reference_status(config_path: str | None) -> ResourceStatus:
    if not config_path:
        return {"status": "not_configured"}
    try:
        configuration = load_reference_configuration(Path(config_path))
    except OSError, ValidationError:
        return {"status": "invalid_configuration"}
    try:
        with open_reference_resources(configuration) as resources:
            resources.search.store.validate_index()
        return {"status": "ready"}
    except Exception:
        return {"status": "unavailable"}


def main() -> int:
    resources = {
        "database": database_status(os.environ.get("CALIBURN_REBUILD_DATABASE_URL")),
        "checkpoints": checkpoint_status(
            os.environ.get("CALIBURN_REBUILD_AGENT_CHECKPOINT_CONNINFO"),
            required=bool(os.environ.get("CALIBURN_REBUILD_AGENT_CONFIG")),
        ),
        "reference": reference_status(
            os.environ.get("CALIBURN_REBUILD_REFERENCE_CONFIG")
        ),
    }
    ready = all(item["status"] in {"ready", "disabled"} for item in resources.values())
    print(json.dumps({"status": "ready" if ready else "not_ready", **resources}))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
