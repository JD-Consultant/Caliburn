"""The current-only migration chain builds and removes only current tables."""

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
MIG_DB = "caliburn_current_only_mig"

CURRENT_TABLES = {
    "consultant_documents",
    "job_analysis_documents",
    "job_analysis_jd_duties",
    "job_analysis_jd_tasks",
    "job_analysis_proposals",
    "job_analysis_journal",
    "job_analysis_opks_items",
    "job_analysis_opks_proposals",
}
CURRENT_COLUMNS = {
    "consultant_documents": {
        "document_id",
        "thread_id",
        "title",
        "created_at",
        "updated_at",
        "deleted_at",
    },
    "job_analysis_documents": {
        "document_id", "title", "work_model_schema_id", "work_model_json",
        "active_question_json", "authority_generation", "created_at", "updated_at",
        "jd_header_schema_id", "jd_header_json",
    },
    "job_analysis_jd_duties": {
        "document_id", "duty_id", "statement", "display_order", "created_at", "updated_at",
    },
    "job_analysis_jd_tasks": {
        "document_id", "task_id", "statement", "purpose_result", "context",
        "frequency_text", "responsibility_role", "enablers_json", "display_order",
        "created_at", "updated_at", "duty_id", "competency_level",
    },
    "job_analysis_proposals": {
        "document_id", "proposal_id", "status", "base_authority_generation",
        "proposal_schema_id", "proposal_payload", "caused_by_decision_id",
        "created_at", "resolved_at",
    },
    "job_analysis_journal": {
        "journal_sequence", "document_id", "entry_id", "kind", "payload_schema_id",
        "payload", "created_at",
    },
    "job_analysis_opks_items": {
        "document_id", "entity_id", "entity_kind", "item_schema_id", "item_payload",
        "created_at", "updated_at", "display_order",
    },
    "job_analysis_opks_proposals": {
        "document_id", "proposal_id", "operation_id", "entity_id", "entity_kind",
        "action", "status", "base_authority_generation", "proposal_schema_id",
        "proposal_payload", "created_at", "resolved_at",
    },
}


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


def test_alembic_has_current_only_root_and_single_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_heads() == ["0018"]
    assert scripts.get_revision("0012").down_revision is None
    current_revisions = {
        "0012",
        "0013",
        "0014",
        "0015",
        "0016",
        "0017",
        "0018",
    }
    assert set(scripts.revision_map._revision_map) >= current_revisions
    assert not any(
        revision and revision not in current_revisions
        for revision in scripts.revision_map._revision_map
        if revision != "<base>"
    )


@pytest.mark.usefixtures("require_postgres")
def test_current_only_migration_cycle_builds_and_drops_current_tables():
    admin = sa.create_engine(_sync_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(sa.text(f"DROP DATABASE IF EXISTS {MIG_DB} WITH (FORCE)"))
        connection.execute(sa.text(f"CREATE DATABASE {MIG_DB}"))
    engine = sa.create_engine(_sync_url(MIG_DB))
    try:
        _alembic("upgrade", "head", _async_url(MIG_DB))
        inspector = sa.inspect(engine)
        tables = set(inspector.get_table_names(schema="public"))
        assert tables == CURRENT_TABLES | {"alembic_version"}
        assert not any(table.startswith(("users", "job_profiles", "document_versions", "interview_", "job_authoring_")) for table in tables)

        for table, expected_columns in CURRENT_COLUMNS.items():
            assert {column["name"] for column in inspector.get_columns(table)} == expected_columns

        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == "0018"

        _alembic("downgrade", "base", _async_url(MIG_DB))
        assert set(sa.inspect(engine).get_table_names(schema="public")) == {"alembic_version"}
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(sa.text(f"DROP DATABASE IF EXISTS {MIG_DB} WITH (FORCE)"))
        admin.dispose()
