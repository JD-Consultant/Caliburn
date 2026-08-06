"""0017 的回填必須等於 migration 前的讀取順序（切片 A T2）。

這是本次 migration **唯一有資料遺失風險的地方**：0017 之前 OPKS 的呈現順序是
`(created_at, entity_id)`，之後改由 `display_order` 決定。若回填算錯，既有文件的
工作產出、知識、技能會在升級後**默默換位置**，而匯出的 `O1.1.1`／`K01` 位置碼
正是由這個順序推出來的。
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa


API_DIR = Path(__file__).parents[1]
MIG_DB = "caliburn_opks_backfill_test"
BASE = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/caliburn",
)


def _url(database: str, *, sync: bool) -> str:
    head = BASE.rsplit("/", 1)[0]
    if sync:
        head = head.replace("postgresql+asyncpg", "postgresql+psycopg")
    return f"{head}/{database}"


def _alembic(*args: str) -> None:
    env = {**os.environ, "DATABASE_URL": _url(MIG_DB, sync=False), "PYTHONUTF8": "1"}
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API_DIR,
        env=env,
        check=True,
        capture_output=True,
    )


@pytest.mark.usefixtures("require_postgres")
def test_backfill_reproduces_the_pre_migration_read_order():
    admin = sa.create_engine(_url("postgres", sync=True), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(sa.text(f"DROP DATABASE IF EXISTS {MIG_DB} WITH (FORCE)"))
        connection.execute(sa.text(f"CREATE DATABASE {MIG_DB}"))

    engine = sa.create_engine(_url(MIG_DB, sync=True))
    document_id = uuid4()
    now = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
    # 刻意讓「插入順序」與「created_at 順序」不一致，否則測不出排序是否真的照 created_at
    seeded = [
        ("output-b", "output", now + timedelta(minutes=2)),
        ("output-a", "output", now),
        ("knowledge-b", "knowledge", now + timedelta(minutes=3)),
        ("knowledge-a", "knowledge", now + timedelta(minutes=1)),
        ("skill-only", "skill", now + timedelta(minutes=4)),
    ]
    try:
        _alembic("upgrade", "0016")
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO job_analysis_documents "
                    "(document_id, title, work_model_schema_id, work_model_json, "
                    " jd_header_schema_id, jd_header_json, active_question_json, "
                    " authority_generation, created_at, updated_at) VALUES "
                    "(:d, 'x', 'job-analysis-work-model/1', '{}'::jsonb, "
                    " 'job-analysis-jd-header/1', '{}'::jsonb, NULL, 0, :t, :t)"
                ),
                {"d": document_id, "t": now},
            )
            for entity_id, kind, created in seeded:
                connection.execute(
                    sa.text(
                        "INSERT INTO job_analysis_opks_items "
                        "(document_id, entity_id, entity_kind, item_schema_id, "
                        " item_payload, created_at, updated_at) VALUES "
                        "(:d, :e, :k, 'job-analysis-opks-item/1', "
                        " '{}'::jsonb, :c, :c)"
                    ),
                    {"d": document_id, "e": entity_id, "k": kind, "c": created},
                )

        with engine.connect() as connection:
            before = list(
                connection.execute(
                    sa.text(
                        "SELECT entity_kind, entity_id FROM job_analysis_opks_items "
                        "WHERE document_id = :d ORDER BY created_at, entity_id"
                    ),
                    {"d": document_id},
                )
            )

        _alembic("upgrade", "0017")

        with engine.connect() as connection:
            after = list(
                connection.execute(
                    sa.text(
                        "SELECT entity_kind, entity_id FROM job_analysis_opks_items "
                        "WHERE document_id = :d "
                        "ORDER BY entity_kind, display_order"
                    ),
                    {"d": document_id},
                )
            )
            orders = dict(
                connection.execute(
                    sa.text(
                        "SELECT entity_id, display_order "
                        "FROM job_analysis_opks_items WHERE document_id = :d"
                    ),
                    {"d": document_id},
                ).all()
            )

        # 每個 kind 內的相對順序必須與升級前逐項相同
        def by_kind(rows):
            grouped: dict[str, list[str]] = {}
            for kind, entity_id in rows:
                grouped.setdefault(kind, []).append(entity_id)
            return grouped

        assert by_kind(after) == by_kind(before)
        # 每個 kind 各自從 0 起連續編號
        assert orders["output-a"] == 0 and orders["output-b"] == 1
        assert orders["knowledge-a"] == 0 and orders["knowledge-b"] == 1
        assert orders["skill-only"] == 0
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(
                sa.text(f"DROP DATABASE IF EXISTS {MIG_DB} WITH (FORCE)")
            )
        admin.dispose()
