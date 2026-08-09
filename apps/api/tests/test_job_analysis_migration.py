"""Migration 0016: greenfield Current State with employee-owned Duties.

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
    "job_analysis_jd_duties",
    "job_analysis_jd_tasks",
    "job_analysis_proposals",
    "job_analysis_journal",
    "job_analysis_opks_items",
    "job_analysis_opks_proposals",
}

EXPECTED_COLUMNS = {
    "job_analysis_documents": {
        "document_id": ("uuid", False),
        "title": ("text", False),
        "jd_header_schema_id": ("text", False),
        "jd_header_json": ("jsonb", False),
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
        "duty_id": ("text", True),
        "competency_level": ("bigint", True),
        "display_order": ("bigint", False),
        "created_at": ("timestamptz", False),
        "updated_at": ("timestamptz", False),
    },
    "job_analysis_jd_duties": {
        "document_id": ("uuid", False),
        "duty_id": ("text", False),
        "statement": ("text", False),
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
    "job_analysis_opks_items": {
        "document_id": ("uuid", False),
        "entity_id": ("text", False),
        "entity_kind": ("text", False),
        "item_schema_id": ("text", False),
        "item_payload": ("jsonb", False),
        "created_at": ("timestamptz", False),
        "updated_at": ("timestamptz", False),
    },
    "job_analysis_opks_proposals": {
        "document_id": ("uuid", False),
        "proposal_id": ("text", False),
        "operation_id": ("text", False),
        "entity_id": ("text", False),
        "entity_kind": ("text", False),
        "action": ("text", False),
        "status": ("text", False),
        "base_authority_generation": ("bigint", False),
        "proposal_schema_id": ("text", False),
        "proposal_payload": ("jsonb", False),
        "created_at": ("timestamptz", False),
        "resolved_at": ("timestamptz", True),
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
    "job_analysis_jd_duties": (
        "ja2_pk_jd_duties",
        ["document_id", "duty_id"],
    ),
    "job_analysis_proposals": (
        "ja2_pk_proposals",
        ["document_id", "proposal_id"],
    ),
    "job_analysis_journal": (
        "ja2_pk_journal",
        ["journal_sequence"],
    ),
    "job_analysis_opks_items": (
        "ja2_pk_opks_items",
        ["document_id", "entity_id"],
    ),
    "job_analysis_opks_proposals": (
        "ja2_pk_opks_proposals",
        ["document_id", "proposal_id"],
    ),
}

EXPECTED_UNIQUES = {
    "job_analysis_documents": set(),
    "job_analysis_jd_tasks": {"ja2_uq_jd_tasks_order"},
    "job_analysis_jd_duties": {"ja2_uq_jd_duties_order"},
    "job_analysis_proposals": set(),
    "job_analysis_journal": {"ja2_uq_journal_entry"},
    "job_analysis_opks_items": set(),
    "job_analysis_opks_proposals": set(),
}

EXPECTED_FKS = {
    "job_analysis_documents": set(),
    "job_analysis_jd_tasks": {
        "ja2_fk_jd_tasks_document",
        "ja2_fk_jd_tasks_duty",
    },
    "job_analysis_jd_duties": {"ja2_fk_jd_duties_document"},
    "job_analysis_proposals": {"ja2_fk_proposals_document"},
    "job_analysis_journal": {"ja2_fk_journal_document"},
    "job_analysis_opks_items": {"ja2_fk_opks_items_document"},
    "job_analysis_opks_proposals": {"ja2_fk_opks_proposals_document"},
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
        "ja2_ck_jd_tasks_duty_id",
        "ja2_ck_jd_tasks_competency_level",
        "ja2_ck_jd_tasks_display_order",
        "ja2_ck_jd_tasks_time_order",
    },
    "job_analysis_jd_duties": {
        "ja2_ck_jd_duties_id",
        "ja2_ck_jd_duties_statement",
        "ja2_ck_jd_duties_display_order",
        "ja2_ck_jd_duties_time_order",
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
    "job_analysis_opks_items": {
        "ja2_ck_opks_items_id",
        "ja2_ck_opks_items_kind",
        "ja2_ck_opks_items_schema",
        "ja2_ck_opks_items_payload",
        "ja2_ck_opks_items_time_order",
    },
    "job_analysis_opks_proposals": {
        "ja2_ck_opks_proposals_id",
        "ja2_ck_opks_proposals_operation_id",
        "ja2_ck_opks_proposals_entity_id",
        "ja2_ck_opks_proposals_kind",
        "ja2_ck_opks_proposals_action",
        "ja2_ck_opks_proposals_status",
        "ja2_ck_opks_proposals_generation",
        "ja2_ck_opks_proposals_schema",
        "ja2_ck_opks_proposals_payload",
        "ja2_ck_opks_proposals_lifecycle",
    },
}

EXPECTED_INDEXES = {
    "ja2_ix_documents_updated",
    "ja2_ix_proposals_document_status",
    "ja2_uq_proposals_replacement",
    "ja2_ix_journal_document_sequence",
    "ja2_ix_opks_items_document_created",
    "ja2_ix_opks_proposals_document_status",
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


def test_alembic_has_0017_as_its_single_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))

    assert ScriptDirectory.from_config(config).get_heads() == ["0017"]


@pytest.mark.usefixtures("require_postgres")
def test_migration_0016_cycle_builds_greenfield_tables_and_preserves_0011():
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

        _alembic("upgrade", "0014", _async_url(MIG_DB))
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO job_analysis_documents ("
                    "document_id, title, work_model_schema_id, work_model_json, "
                    "active_question_json, authority_generation, created_at, updated_at"
                    ") VALUES ("
                    "'00000000-0000-0000-0000-000000000015', "
                    "'既有文件', 'job-analysis-work-model/1', '{}'::jsonb, "
                    "NULL, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP"
                    ")"
                )
            )

        _alembic("upgrade", "0015", _async_url(MIG_DB))
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO job_analysis_jd_tasks ("
                    "document_id, task_id, statement, purpose_result, context, "
                    "frequency_text, responsibility_role, enablers_json, "
                    "display_order, created_at, updated_at"
                    ") VALUES ("
                    "'00000000-0000-0000-0000-000000000015', "
                    "'legacy-task', '既有任務', NULL, NULL, NULL, NULL, "
                    "'[]'::jsonb, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP"
                    ")"
                )
            )
        _alembic("upgrade", "0016", _async_url(MIG_DB))
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
            for name, foreign_key in foreign_keys.items():
                if name == "ja2_fk_jd_tasks_duty":
                    assert foreign_key["constrained_columns"] == [
                        "document_id",
                        "duty_id",
                    ]
                    assert foreign_key["referred_table"] == "job_analysis_jd_duties"
                    assert foreign_key["options"].get("deferrable") is True
                    assert foreign_key["options"].get("initially") == "DEFERRED"
                else:
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

        with engine.connect() as connection:
            migrated_document_row = connection.execute(
                sa.text(
                    "SELECT jd_header_schema_id, jd_header_json "
                    "FROM job_analysis_documents "
                    "WHERE document_id = '00000000-0000-0000-0000-000000000015'"
                )
            ).mappings().one()
        assert migrated_document_row["jd_header_schema_id"] == (
            "job-analysis-jd-header/1"
        )
        assert migrated_document_row["jd_header_json"] == {}

        with engine.connect() as connection:
            legacy_task_row = connection.execute(
                sa.text(
                    "SELECT duty_id, competency_level FROM job_analysis_jd_tasks "
                    "WHERE document_id = '00000000-0000-0000-0000-000000000015' "
                    "AND task_id = 'legacy-task'"
                )
            ).mappings().one()
        assert legacy_task_row == {"duty_id": None, "competency_level": None}

        with engine.connect() as connection:
            journal_kind_check = connection.scalar(
                sa.text(
                    "SELECT pg_get_constraintdef(oid) "
                    "FROM pg_constraint WHERE conname = 'ja2_ck_journal_kind'"
                )
            )
        assert journal_kind_check is not None
        assert "consultant_opening" in journal_kind_check
        assert "opks_generation" in journal_kind_check

        with engine.connect() as connection:
            opks_status_check = connection.scalar(
                sa.text(
                    "SELECT pg_get_constraintdef(oid) "
                    "FROM pg_constraint "
                    "WHERE conname = 'ja2_ck_opks_proposals_status'"
                )
            )
            opks_lifecycle_check = connection.scalar(
                sa.text(
                    "SELECT pg_get_constraintdef(oid) "
                    "FROM pg_constraint "
                    "WHERE conname = 'ja2_ck_opks_proposals_lifecycle'"
                )
            )
        assert opks_status_check is not None
        for status in (
            "pending",
            "deferred",
            "accepted",
            "edited",
            "rejected",
            "stale",
        ):
            assert status in opks_status_check
        assert "revision_requested" not in opks_status_check
        assert opks_lifecycle_check is not None
        assert "resolved_at IS NULL" in opks_lifecycle_check
        assert "resolved_at IS NOT NULL" in opks_lifecycle_check

        _alembic("downgrade", "0015", _async_url(MIG_DB))
        downgraded_columns = {
            column["name"]
            for column in sa.inspect(engine).get_columns("job_analysis_jd_tasks")
        }
        assert "job_analysis_jd_duties" not in set(
            sa.inspect(engine).get_table_names(schema="public")
        )
        assert "duty_id" not in downgraded_columns
        assert "competency_level" not in downgraded_columns

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
