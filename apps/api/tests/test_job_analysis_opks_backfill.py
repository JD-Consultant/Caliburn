"""Migration 0017: backfill employee OPKS display order by prior read order."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url


API_DIR = Path(__file__).parents[1]
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
MIG_DB = "caliburn_ja2_opks_order_mig"


def _sync_url(database: str) -> str:
    return make_url(TEST_DATABASE_URL).set(
        drivername="postgresql+psycopg",
        database=database,
    ).render_as_string(hide_password=False)


def _async_url(database: str) -> str:
    return make_url(TEST_DATABASE_URL).set(
        drivername="postgresql+asyncpg",
        database=database,
    ).render_as_string(hide_password=False)


def _alembic(direction: str, target: str, database_url: str) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", direction, target],
        cwd=API_DIR,
        env={**os.environ, "DATABASE_URL": database_url, "PYTHONUTF8": "1"},
        capture_output=True,
        text=True,
        timeout=180,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.returncode == 0, f"alembic {direction} {target}:\n{proc.stderr}"


@pytest.mark.usefixtures("require_postgres")
def test_migration_0017_backfills_order_per_document_and_kind():
    admin = sa.create_engine(_sync_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(sa.text(f"DROP DATABASE IF EXISTS {MIG_DB} WITH (FORCE)"))
        connection.execute(sa.text(f"CREATE DATABASE {MIG_DB}"))
    engine = sa.create_engine(_sync_url(MIG_DB))
    try:
        _alembic("upgrade", "0016", _async_url(MIG_DB))
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO job_analysis_documents ("
                    "document_id, title, jd_header_schema_id, jd_header_json, "
                    "work_model_schema_id, work_model_json, active_question_json, "
                    "authority_generation, created_at, updated_at"
                    ") VALUES ("
                    "'00000000-0000-0000-0000-000000000017', 'OPKS 順序', "
                    "'job-analysis-jd-header/1', '{}'::jsonb, "
                    "'job-analysis-work-model/1', '{}'::jsonb, NULL, 0, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP), ("
                    "'00000000-0000-0000-0000-000000000018', '另一份文件', "
                    "'job-analysis-jd-header/1', '{}'::jsonb, "
                    "'job-analysis-work-model/1', '{}'::jsonb, NULL, 0, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO job_analysis_opks_items ("
                    "document_id, entity_id, entity_kind, item_schema_id, "
                    "item_payload, created_at, updated_at"
                    ") VALUES "
                    "('00000000-0000-0000-0000-000000000017', 'knowledge-b', 'knowledge', "
                    "'job-analysis-opks-item/1', '{\"text\":\"B\",\"task_refs\":[],"
                    "\"indicator_refs\":[],\"evidence_links\":[{\"source_ref\":{"
                    "\"kind\":\"direct_edit\",\"id\":\"b\"}}]}'::jsonb, "
                    "'2026-08-01T08:00:00+00:00', '2026-08-01T08:00:00+00:00'), "
                    "('00000000-0000-0000-0000-000000000017', 'knowledge-a', 'knowledge', "
                    "'job-analysis-opks-item/1', '{\"text\":\"A\",\"task_refs\":[],"
                    "\"indicator_refs\":[],\"evidence_links\":[{\"source_ref\":{"
                    "\"kind\":\"direct_edit\",\"id\":\"a\"}}]}'::jsonb, "
                    "'2026-08-01T08:00:00+00:00', '2026-08-01T08:00:00+00:00'), "
                    "('00000000-0000-0000-0000-000000000017', 'skill-a', 'skill', "
                    "'job-analysis-opks-item/1', '{\"text\":\"S\",\"task_refs\":[],"
                    "\"indicator_refs\":[],\"evidence_links\":[{\"source_ref\":{"
                    "\"kind\":\"direct_edit\",\"id\":\"s\"}}]}'::jsonb, "
                    "'2026-08-01T08:00:00+00:00', '2026-08-01T08:00:00+00:00'), "
                    "('00000000-0000-0000-0000-000000000018', 'knowledge-z', 'knowledge', "
                    "'job-analysis-opks-item/1', '{\"text\":\"Z\",\"task_refs\":[],"
                    "\"indicator_refs\":[],\"evidence_links\":[{\"source_ref\":{"
                    "\"kind\":\"direct_edit\",\"id\":\"z\"}}]}'::jsonb, "
                    "'2026-08-01T08:00:00+00:00', '2026-08-01T08:00:00+00:00')"
                )
            )

        _alembic("upgrade", "0017", _async_url(MIG_DB))
        with engine.connect() as connection:
            rows = connection.execute(
                sa.text(
                    "SELECT document_id::text, entity_kind, entity_id, display_order "
                    "FROM job_analysis_opks_items "
                    "ORDER BY document_id, entity_kind, display_order"
                )
            ).mappings().all()

        assert [
            (row["document_id"], row["entity_kind"], row["entity_id"], row["display_order"])
            for row in rows
        ] == [
            ("00000000-0000-0000-0000-000000000017", "knowledge", "knowledge-a", 0),
            ("00000000-0000-0000-0000-000000000017", "knowledge", "knowledge-b", 1),
            ("00000000-0000-0000-0000-000000000017", "skill", "skill-a", 0),
            ("00000000-0000-0000-0000-000000000018", "knowledge", "knowledge-z", 0),
        ]
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(sa.text(f"DROP DATABASE IF EXISTS {MIG_DB} WITH (FORCE)"))
        admin.dispose()
