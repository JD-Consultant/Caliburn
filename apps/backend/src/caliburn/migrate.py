"""明示升級業務 schema；checkpoint setup 只在指定時執行。"""

import argparse
import json
import os

from alembic import command
from alembic.config import Config
from langgraph.checkpoint.postgres import PostgresSaver

from caliburn.shared.infrastructure.persistence.database import create_database_engine


def migration_config() -> Config:
    """同一份遷移資源供原始碼與已安裝 wheel 使用。"""
    config = Config()
    config.set_main_option("script_location", "caliburn:migrations")
    return config


def upgrade_database(database_url: str) -> None:
    engine = create_database_engine(database_url)
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["upgrade"])
    parser.add_argument("revision", choices=["head"])
    parser.add_argument(
        "--with-checkpoints", action="store_true", help="同時執行官方 checkpoint setup"
    )
    args = parser.parse_args()
    database_url = os.environ.get("CALIBURN_REBUILD_DATABASE_URL")
    checkpoint_conninfo = os.environ.get("CALIBURN_REBUILD_AGENT_CHECKPOINT_CONNINFO")
    if not database_url or (args.with_checkpoints and not checkpoint_conninfo):
        print(json.dumps({"status": "not_configured"}))
        return 1
    try:
        upgrade_database(database_url)
    except Exception:
        print(json.dumps({"status": "failed", "resource": "database"}))
        return 1
    if args.with_checkpoints and checkpoint_conninfo:
        try:
            with PostgresSaver.from_conn_string(checkpoint_conninfo) as saver:
                saver.setup()
        except Exception:
            print(json.dumps({"status": "failed", "resource": "checkpoints"}))
            return 1
    print(json.dumps({"status": "upgraded", "checkpoints": args.with_checkpoints}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
