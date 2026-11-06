"""以專用合成 PostgreSQL 核對 CLI 實際遷移及唯讀狀態。"""

import json
import os
import subprocess
import sys
from pathlib import Path

from alembic import command
from sqlalchemy import Engine, inspect

from caliburn.migrate import migration_config
from caliburn.status import checkpoint_status, database_status


def test_explicit_upgrade_and_checkpoint_setup_are_visible_to_read_only_status(
    pg_engine: Engine, tmp_path: Path
) -> None:
    config = migration_config()
    with pg_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
    database_url = pg_engine.url.render_as_string(hide_password=False)
    conninfo = pg_engine.url.set(drivername="postgresql").render_as_string(
        hide_password=False
    )
    before = inspect(pg_engine).get_table_names()
    assert database_status(database_url) == {"status": "migration_required"}
    assert checkpoint_status(conninfo, required=True) == {
        "status": "migration_required"
    }
    assert inspect(pg_engine).get_table_names() == before

    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("CALIBURN_REBUILD_")
    }
    environment["CALIBURN_REBUILD_DATABASE_URL"] = database_url
    args = [
        sys.executable,
        "-X",
        "utf8",
        "-m",
        "caliburn.migrate",
        "upgrade",
        "head",
        "--with-checkpoints",
    ]
    missing = subprocess.run(
        args,
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert missing.returncode == 1
    assert json.loads(missing.stdout) == {"status": "not_configured"}
    assert inspect(pg_engine).get_table_names() == before

    environment["CALIBURN_REBUILD_AGENT_CHECKPOINT_CONNINFO"] = conninfo
    result = subprocess.run(
        args,
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"status": "upgraded", "checkpoints": True}
    after = inspect(pg_engine).get_table_names()
    assert "workspaces" in after
    assert "checkpoints" in after
    assert database_status(database_url) == {"status": "ready"}
    assert checkpoint_status(conninfo, required=True) == {"status": "ready"}
    assert inspect(pg_engine).get_table_names() == after


def test_migration_does_not_log_invalid_checkpoint_credentials(
    pg_engine: Engine, tmp_path: Path
) -> None:
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("CALIBURN_REBUILD_")
    }
    environment["CALIBURN_REBUILD_DATABASE_URL"] = pg_engine.url.render_as_string(
        hide_password=False
    )
    environment["CALIBURN_REBUILD_AGENT_CHECKPOINT_CONNINFO"] = "secret-credential"
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-m",
            "caliburn.migrate",
            "upgrade",
            "head",
            "--with-checkpoints",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        encoding="utf-8",
        check=False,
        timeout=45,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"status": "failed", "resource": "checkpoints"}
    assert "secret-credential" not in result.stdout + result.stderr
