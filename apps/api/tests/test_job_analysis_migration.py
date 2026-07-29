"""Migration 0012: greenfield local Current State tables.

The cycle runs in a disposable database and proves the migration neither
rewrites nor removes the older 0011 authoring tables.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url


API_DIR = Path(__file__).parents[1]
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
MIG_DB = "caliburn_ja2_mig"

TABLES = {
    "job_analysis_documents",
    "job_analysis_jd_tasks",
    "job_analysis_proposals",
    "job_analysis_journal",
}

EXPECTED_COLUMNS = {
    "job_analysis_documents": {
        "document_id": ("uuid", False),
        "title": ("text", False),
        "work_model_schema_id": ("text", False),
        "work_model_json": ("jsonb", False),
        "active_question_json": ("jsonb", True),
        "authority_generation": ("bigint", False),
        "created_at": ("timestamptz", False),
        "updated_at": ("timestamptz", False),
    },
    "job_analysis_jd_tasks": {
        "document_id": ("uuid", False),
        "task_id": ("text", False),
        "statement": ("text", False),
        "purpose_result": ("text", True),
        "context": ("text", True),
        "frequency_text": ("text", True),
        "responsibility_role": ("text", True),
        "enablers_json": ("jsonb", False),
        "display_order": ("bigint", False),
        "created_at": ("timestamptz", False),
        "updated_at": ("timestamptz", False),
    },
    "job_analysis_proposals": {
        "document_id": ("uuid", False),
        "proposal_id": ("text", False),
        "status": ("text", False),
        "base_authority_generation": ("bigint", False),
        "proposal_schema_id": ("text", False),
        "proposal_payload": ("jsonb", False),
        "caused_by_decision_id": ("text", True),
        "created_at": ("timestamptz", False),
        "resolved_at": ("timestamptz", True),
    },
    "job_analysis_journal": {
        "journal_sequence": ("bigint", False),
        "document_id": ("uuid", False),
        "entry_id": ("text", False),
        "kind": ("text", False),
        "payload_schema_id": ("text", False),
        "payload": ("jsonb", False),
        "created_at": ("timestamptz", False),
    },
}

EXPECTED_PK = {
    "job_analysis_documents": (
        "ja2_pk_documents",
        ["document_id"],
    ),
    "job_analysis_jd_tasks": (
        "ja2_pk_jd_tasks",
        ["document_id", "task_id"],
    ),
    "job_analysis_proposals": (
        "ja2_pk_proposals",
        ["document_id", "proposal_id"],
    ),
    "job_analysis_journal": (
        "ja2_pk_journal",
        ["journal_sequence"],
    ),
}

EXPECTED_UNIQUES = {
    "job_analysis_documents": set(),
    "job_analysis_jd_tasks": {"ja2_uq_jd_tasks_order"},
    "job_analysis_proposals": set(),
    "job_analysis_journal": {"ja2_uq_journal_entry"},
}

EXPECTED_FKS = {
    "job_analysis_documents": set(),
    "job_analysis_jd_tasks": {"ja2_fk_jd_tasks_document"},
    "job_analysis_proposals": {"ja2_fk_proposals_document"},
    "job_analysis_journal": {"ja2_fk_journal_document"},
}

EXPECTED_CHECKS = {
    "job_analysis_documents": {
        "ja2_ck_documents_title",
        "ja2_ck_documents_work_model_schema",
        "ja2_ck_documents_work_model_json",
        "ja2_ck_documents_active_question_json",
        "ja2_ck_documents_generation",
        "ja2_ck_documents_time_order",
    },
    "job_analysis_jd_tasks": {
        "ja2_ck_jd_tasks_task_id",
        "ja2_ck_jd_tasks_statement",
        "ja2_ck_jd_tasks_role",
        "ja2_ck_jd_tasks_enablers_json",
        "ja2_ck_jd_tasks_display_order",
        "ja2_ck_jd_tasks_time_order",
    },
    "job_analysis_proposals": {
        "ja2_ck_proposals_id",
        "ja2_ck_proposals_status",
        "ja2_ck_proposals_generation",
        "ja2_ck_proposals_schema",
        "ja2_ck_proposals_payload",
        "ja2_ck_proposals_lifecycle",
    },
    "job_analysis_journal": {
        "ja2_ck_journal_entry_id",
        "ja2_ck_journal_kind",
        "ja2_ck_journal_schema",
        "ja2_ck_journal_payload",
    },
}

EXPECTED_INDEXES = {
    "ja2_ix_documents_updated",
    "ja2_ix_proposals_document_status",
    "ja2_uq_proposals_replacement",
    "ja2_ix_journal_document_sequence",
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


def _column_kind(column_type) -> str:
    if isinstance(column_type, postgresql.UUID):
        return "uuid"
    if isinstance(column_type, postgresql.JSONB):
        return "jsonb"
    if isinstance(column_type, (sa.TIMESTAMP, sa.DateTime)):
        assert getattr(column_type, "timezone", False)
        return "timestamptz"
    if isinstance(column_type, sa.BigInteger):
        return "bigint"
    if isinstance(column_type, (sa.Text, sa.String)):
        return "text"
    return str(column_type).lower()


def test_alembic_has_0012_as_its_single_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))

    assert ScriptDirectory.from_config(config).get_heads() == ["0012"]


@pytest.mark.usefixtures("require_postgres")
def test_migration_0012_cycle_builds_greenfield_tables_and_preserves_0011():
    admin = sa.create_engine(_sync_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(sa.text(f"DROP DATABASE IF EXISTS {MIG_DB} WITH (FORCE)"))
        connection.execute(sa.text(f"CREATE DATABASE {MIG_DB}"))
    engine = sa.create_engine(_sync_url(MIG_DB))
    try:
        _alembic("upgrade", "0011", _async_url(MIG_DB))
        before = {
            table
            for table in sa.inspect(engine).get_table_names(schema="public")
            if table.startswith("job_authoring_")
        }
        assert before == {
            "job_authoring_documents",
            "job_authoring_revisions",
            "job_authoring_proposals",
        }

        _alembic("upgrade", "0012", _async_url(MIG_DB))
        inspector = sa.inspect(engine)
        assert TABLES <= set(inspector.get_table_names(schema="public"))

        for table in TABLES:
            columns = {column["name"]: column for column in inspector.get_columns(table)}
            assert set(columns) == set(EXPECTED_COLUMNS[table])
            for name, (kind, nullable) in EXPECTED_COLUMNS[table].items():
                assert _column_kind(columns[name]["type"]) == kind
                assert columns[name]["nullable"] is nullable

            pk = inspector.get_pk_constraint(table)
            expected_pk_name, expected_pk_columns = EXPECTED_PK[table]
            assert pk["name"] == expected_pk_name
            assert pk["constrained_columns"] == expected_pk_columns

            assert {
                unique["name"] for unique in inspector.get_unique_constraints(table)
            } == EXPECTED_UNIQUES[table]
            foreign_keys = {
                foreign_key["name"]: foreign_key
                for foreign_key in inspector.get_foreign_keys(table)
            }
            assert set(foreign_keys) == EXPECTED_FKS[table]
            for foreign_key in foreign_keys.values():
                assert foreign_key["options"].get("ondelete") == "CASCADE"
            assert {
                check["name"] for check in inspector.get_check_constraints(table)
            } == EXPECTED_CHECKS[table]

        with engine.connect() as connection:
            index_names = {
                name
                for (name,) in connection.execute(
                    sa.text(
                        "SELECT indexname FROM pg_indexes "
                        "WHERE schemaname='public' "
                        "AND tablename LIKE 'job_analysis_%'"
                    )
                )
            }
        assert EXPECTED_INDEXES <= index_names

        _alembic("downgrade", "0011", _async_url(MIG_DB))
        remaining = set(sa.inspect(engine).get_table_names(schema="public"))
        assert not (TABLES & remaining)
        assert before <= remaining
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(
                sa.text(f"DROP DATABASE IF EXISTS {MIG_DB} WITH (FORCE)")
            )
        admin.dispose()
