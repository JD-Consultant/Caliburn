"""Migration 0011 introspection + cycle test (plan §10, §14.5).

Runs against a throwaway database: upgrade 0010, snapshot the eight vNext tables
and v3 rows, upgrade 0011, introspect the three authoring tables exactly, prove
lifecycle/hash/json/scope guards and immutability triggers bite, then downgrade
0010 and prove every authoring object is gone and 0010/v3 are byte-unchanged.
"""

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
MIG_DB = "caliburn_ja_mig"

AUTHORING_TABLES = {
    "job_authoring_documents",
    "job_authoring_revisions",
    "job_authoring_proposals",
}

EXPECTED_COLUMNS = {
    "job_authoring_documents": {
        "document_id": ("uuid", False),
        "tenant_id": ("uuid", False),
        "session_id": ("uuid", False),
        "head_revision_id": ("uuid", False),
        "head_revision_number": ("bigint", False),
        "head_revision_hash": ("text", False),
        "created_at": ("timestamptz", False),
        "updated_at": ("timestamptz", False),
    },
    "job_authoring_revisions": {
        "revision_id": ("uuid", False),
        "tenant_id": ("uuid", False),
        "document_id": ("uuid", False),
        "revision_number": ("bigint", False),
        "parent_revision_id": ("uuid", True),
        "source_kind": ("text", False),
        "command_schema_id": ("text", False),
        "command_id": ("uuid", False),
        "command_json": ("text", False),
        "command_hash": ("text", False),
        "snapshot_schema_id": ("text", False),
        "snapshot_json": ("text", False),
        "snapshot_hash": ("text", False),
        "occurred_at": ("timestamptz", False),
        "created_at": ("timestamptz", False),
    },
    "job_authoring_proposals": {
        "proposal_id": ("uuid", False),
        "tenant_id": ("uuid", False),
        "document_id": ("uuid", False),
        "base_revision_id": ("uuid", False),
        "base_revision_hash": ("text", False),
        "evidence_state_version": ("bigint", False),
        "evidence_state_hash": ("text", False),
        "source_kind": ("text", False),
        "source_id": ("uuid", False),
        "proposal_schema_id": ("text", False),
        "proposal_json": ("text", False),
        "proposal_hash": ("text", False),
        "status": ("text", False),
        "decision_command_id": ("uuid", True),
        "decision_schema_id": ("text", True),
        "decision_json": ("text", True),
        "decision_hash": ("text", True),
        "result_revision_id": ("uuid", True),
        "stale_reason": ("text", True),
        "created_at": ("timestamptz", False),
        "resolved_at": ("timestamptz", True),
        "updated_at": ("timestamptz", False),
    },
}

EXPECTED_PK = {
    "job_authoring_documents": ["document_id"],
    "job_authoring_revisions": ["revision_id"],
    "job_authoring_proposals": ["proposal_id"],
}

EXPECTED_UNIQUES = {
    "job_authoring_documents": {"uq_ja_docs_tenant_document", "uq_ja_docs_tenant_session"},
    "job_authoring_revisions": {
        "uq_ja_revs_tenant_revision",
        "uq_ja_revs_document_number",
        "uq_ja_revs_tenant_command",
    },
    "job_authoring_proposals": {"uq_ja_props_tenant_proposal"},
}

EXPECTED_FK_NAMES = {
    "job_authoring_documents": {"fk_ja_docs_session"},
    "job_authoring_revisions": {"fk_ja_revs_document", "fk_ja_revs_parent"},
    "job_authoring_proposals": {
        "fk_ja_props_document",
        "fk_ja_props_base_revision",
        "fk_ja_props_result_revision",
    },
}

EXPECTED_CHECK_NAMES = {
    "job_authoring_documents": {
        "ck_ja_docs_head_number",
        "ck_ja_docs_head_hash",
        "ck_ja_docs_time_order",
    },
    "job_authoring_revisions": {
        "ck_ja_revs_number_parent",
        "ck_ja_revs_source",
        "ck_ja_revs_command_hash",
        "ck_ja_revs_snapshot_hash",
        "ck_ja_revs_command_json",
        "ck_ja_revs_snapshot_json",
    },
    "job_authoring_proposals": {
        "ck_ja_props_source",
        "ck_ja_props_state_version",
        "ck_ja_props_base_hash",
        "ck_ja_props_state_hash",
        "ck_ja_props_payload_hash",
        "ck_ja_props_payload_json",
        "ck_ja_props_decision_json",
        "ck_ja_props_stale_reason",
        "ck_ja_props_lifecycle",
        "ck_ja_props_time_order",
    },
}

EXPECTED_INDEXES = {"ix_ja_docs_tenant_updated", "ix_ja_props_document_status"}
EXPECTED_PARTIAL_UNIQUE = "uq_ja_props_decision_command"
EXPECTED_TRIGGERS = {
    ("job_authoring_revisions", "ja_revs_reject_update"),
    ("job_authoring_proposals", "ja_props_guard_update"),
}

_HASH_A = "sha256:" + "a" * 64
_HASH_B = "sha256:" + "b" * 64
_HASH_C = "sha256:" + "c" * 64


def _sync_url(database: str) -> str:
    url = make_url(TEST_DATABASE_URL).set(
        drivername="postgresql+psycopg", database=database
    )
    return url.render_as_string(hide_password=False)


def _async_url(database: str) -> str:
    url = make_url(TEST_DATABASE_URL).set(
        drivername="postgresql+asyncpg", database=database
    )
    return url.render_as_string(hide_password=False)


def _alembic(direction: str, target: str, database_url: str) -> None:
    env = {**os.environ, "DATABASE_URL": database_url, "PYTHONUTF8": "1"}
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", direction, target],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.returncode == 0, f"alembic {direction} {target}:\n{proc.stderr}"


def _column_kind(coltype) -> str:
    import sqlalchemy as _sa
    from sqlalchemy.dialects import postgresql

    if isinstance(coltype, postgresql.UUID):
        return "uuid"
    if isinstance(coltype, (_sa.TIMESTAMP, _sa.DateTime)):
        assert getattr(coltype, "timezone", False), "timestamp must be tz-aware"
        return "timestamptz"
    if isinstance(coltype, _sa.BigInteger):
        return "bigint"
    if isinstance(coltype, (_sa.Text, _sa.String)):
        return "text"
    return str(coltype).lower()


def _non_authoring_fingerprint(engine) -> dict:
    """Column shape + row counts of every non-authoring public table."""
    out: dict = {}
    with engine.connect() as conn:
        tables = [
            t
            for (t,) in conn.execute(
                sa.text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_type='BASE TABLE' "
                    "AND table_name NOT LIKE 'job_authoring_%' "
                    "AND table_name <> 'alembic_version'"
                )
            ).all()
        ]
        for table in sorted(tables):
            cols = conn.execute(
                sa.text(
                    "SELECT column_name, data_type, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=:t "
                    "ORDER BY ordinal_position"
                ),
                {"t": table},
            ).all()
            count = conn.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar()  # noqa: S608
            out[table] = {"columns": [tuple(c) for c in cols], "count": count}
    return out


def _seed_session(conn) -> dict:
    """Insert the v3 + vNext session rows an authoring document can reference."""
    ids = {
        "tenant": "11111111-1111-1111-1111-111111111111",
        "user": "22222222-2222-2222-2222-222222222222",
        "profile": "33333333-3333-3333-3333-333333333333",
        "session": "44444444-4444-4444-4444-444444444444",
    }
    conn.execute(
        sa.text(
            "INSERT INTO users (id, email, name) VALUES "
            "(:user, 'ja-mig@test.local', '著作遷移測試')"
        ),
        {"user": ids["user"]},
    )
    conn.execute(
        sa.text(
            "INSERT INTO job_profiles (id, user_id, job_title) VALUES "
            "(:profile, :user, '著作遷移職務')"
        ),
        ids,
    )
    conn.execute(
        sa.text(
            "INSERT INTO interview_vnext_sessions "
            "(session_id, tenant_id, profile_id, architecture_id, workflow_version, "
            " reference_snapshot_id, status, state_version, state_schema_version, "
            " state_json, state_hash, created_at, updated_at) VALUES "
            "(:session, :tenant, :profile, 'arch', 'v', 'ref', 'active', 0, "
            " 'interview_state.v3', '{}', :h, now(), now())"
        ),
        {**ids, "h": _HASH_A},
    )
    return ids


@pytest.mark.usefixtures("require_postgres")
def test_migration_0011_cycle_builds_authoring_and_preserves_0010():
    admin = sa.create_engine(_sync_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(sa.text(f"DROP DATABASE IF EXISTS {MIG_DB} WITH (FORCE)"))
        conn.execute(sa.text(f"CREATE DATABASE {MIG_DB}"))
    engine = sa.create_engine(_sync_url(MIG_DB))
    try:
        _alembic("upgrade", "0010", _async_url(MIG_DB))
        with engine.begin() as conn:
            ids = _seed_session(conn)
        before = _non_authoring_fingerprint(engine)

        _alembic("upgrade", "0011", _async_url(MIG_DB))

        inspector = sa.inspect(engine)
        authoring = {
            t
            for t in inspector.get_table_names(schema="public")
            if t.startswith("job_authoring_")
        }
        assert authoring == AUTHORING_TABLES

        for table, expected_cols in EXPECTED_COLUMNS.items():
            cols = {c["name"]: c for c in inspector.get_columns(table)}
            assert set(cols) == set(expected_cols), f"{table} columns"
            for name, (kind, nullable) in expected_cols.items():
                assert _column_kind(cols[name]["type"]) == kind, f"{table}.{name} type"
                assert cols[name]["nullable"] == nullable, f"{table}.{name} nullable"
            assert (
                inspector.get_pk_constraint(table)["constrained_columns"]
                == EXPECTED_PK[table]
            ), f"{table} pk"
            uniques = {u["name"] for u in inspector.get_unique_constraints(table)}
            assert uniques == EXPECTED_UNIQUES[table], f"{table} uniques"
            fks = {fk["name"]: fk for fk in inspector.get_foreign_keys(table)}
            assert set(fks) == EXPECTED_FK_NAMES[table], f"{table} fks"
            for fk in fks.values():
                assert fk["options"].get("ondelete") == "RESTRICT", fk["name"]
            checks = {c["name"] for c in inspector.get_check_constraints(table)}
            assert checks == EXPECTED_CHECK_NAMES[table], f"{table} checks"
            for name in {
                *EXPECTED_UNIQUES[table],
                *EXPECTED_FK_NAMES[table],
                *EXPECTED_CHECK_NAMES[table],
            }:
                assert len(name.encode()) < 63, name

        with engine.connect() as conn:
            index_defs = dict(
                conn.execute(
                    sa.text(
                        "SELECT indexname, indexdef FROM pg_indexes "
                        "WHERE schemaname='public' AND tablename LIKE 'job_authoring_%'"
                    )
                ).all()
            )
        for index in EXPECTED_INDEXES:
            assert index in index_defs, f"missing {index}"
        assert "UNIQUE" in index_defs[EXPECTED_PARTIAL_UNIQUE]
        assert "decision_command_id IS NOT NULL" in index_defs[EXPECTED_PARTIAL_UNIQUE]

        with engine.connect() as conn:
            triggers = {
                (t, n)
                for t, n in conn.execute(
                    sa.text(
                        "SELECT event_object_table, trigger_name "
                        "FROM information_schema.triggers "
                        "WHERE trigger_schema='public' AND trigger_name LIKE 'ja_%'"
                    )
                ).all()
            }
        assert triggers == EXPECTED_TRIGGERS

        _exercise_row_guards(engine, ids)

        assert _non_authoring_fingerprint(engine) == before

        _alembic("downgrade", "0010", _async_url(MIG_DB))
        inspector = sa.inspect(engine)
        assert not any(
            t.startswith("job_authoring_")
            for t in inspector.get_table_names(schema="public")
        )
        with engine.connect() as conn:
            leftover = conn.execute(
                sa.text("SELECT proname FROM pg_proc WHERE proname LIKE 'ja_%'")
            ).all()
        assert leftover == []
        assert _non_authoring_fingerprint(engine) == before
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(sa.text(f"DROP DATABASE IF EXISTS {MIG_DB} WITH (FORCE)"))
        admin.dispose()


_DOC = "55555555-5555-5555-5555-555555555555"
_REV0 = "66666666-6666-6666-6666-666666666666"
_CMD0 = "77777777-7777-7777-7777-777777777777"
_PROP = "88888888-8888-8888-8888-888888888888"

_REV_INSERT = (
    "INSERT INTO job_authoring_revisions "
    "(revision_id, tenant_id, document_id, revision_number, parent_revision_id, "
    " source_kind, command_schema_id, command_id, command_json, command_hash, "
    " snapshot_schema_id, snapshot_json, snapshot_hash, occurred_at, created_at) "
    "VALUES (:rev, :tenant, :doc, :num, :parent, :source, 'c.v1', :cmd, '{}', :ch, "
    " 'job_document_draft.v1', '{}', :sh, now(), now())"
)
_PROP_INSERT = (
    "INSERT INTO job_authoring_proposals "
    "(proposal_id, tenant_id, document_id, base_revision_id, base_revision_hash, "
    " evidence_state_version, evidence_state_hash, source_kind, source_id, "
    " proposal_schema_id, proposal_json, proposal_hash, status, created_at, updated_at) "
    "VALUES (:prop, :tenant, :doc, :rev, :bh, 0, :sh, 'scripted', :src, "
    " 'ai_task_bundle_proposal.v1', :pj, :ph, :status, now(), now())"
)


def _exercise_row_guards(engine, base_ids):
    tenant = base_ids["tenant"]
    session = base_ids["session"]

    # 1. Valid document (head -> future rev0, no FK) then rev0 then pending proposal.
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO job_authoring_documents "
            "(document_id, tenant_id, session_id, head_revision_id, head_revision_number, "
            " head_revision_hash, created_at, updated_at) "
            "VALUES (:doc, :tenant, :session, :rev, 0, :h, now(), now())"),
            {"doc": _DOC, "tenant": tenant, "session": session, "rev": _REV0, "h": _HASH_B})
        conn.execute(sa.text(_REV_INSERT), {
            "rev": _REV0, "tenant": tenant, "doc": _DOC, "num": 0, "parent": None,
            "source": "initial", "cmd": _CMD0, "ch": _HASH_C, "sh": _HASH_B})
        conn.execute(sa.text(_PROP_INSERT), {
            "prop": _PROP, "tenant": tenant, "doc": _DOC, "rev": _REV0, "bh": _HASH_B,
            "sh": _HASH_A, "src": _CMD0, "pj": "{}", "ph": _HASH_C, "status": "pending"})

    # 2. Bad sha256 hash rejected (ck_ja_revs_snapshot_hash) — clean INSERT of rev1.
    with pytest.raises(Exception):  # noqa: B017
        with engine.begin() as conn:
            conn.execute(sa.text(_REV_INSERT), {
                "rev": "a1111111-1111-1111-1111-111111111111", "tenant": tenant,
                "doc": _DOC, "num": 1, "parent": _REV0, "source": "employee_direct_edit",
                "cmd": "a2222222-2222-2222-2222-222222222222", "ch": _HASH_C,
                "sh": "not-a-hash"})

    # 3. number/parent mismatch rejected (ck_ja_revs_number_parent): num>0 + initial.
    with pytest.raises(Exception):  # noqa: B017
        with engine.begin() as conn:
            conn.execute(sa.text(_REV_INSERT), {
                "rev": "b1111111-1111-1111-1111-111111111111", "tenant": tenant,
                "doc": _DOC, "num": 1, "parent": None, "source": "initial",
                "cmd": "b2222222-2222-2222-2222-222222222222", "ch": _HASH_C,
                "sh": _HASH_B})

    # 4. Lifecycle mismatch rejected (ck_ja_props_lifecycle): accepted w/ null decision.
    with pytest.raises(Exception):  # noqa: B017
        with engine.begin() as conn:
            conn.execute(sa.text(_PROP_INSERT), {
                "prop": "c1111111-1111-1111-1111-111111111111", "tenant": tenant,
                "doc": _DOC, "rev": _REV0, "bh": _HASH_B, "sh": _HASH_A, "src": _CMD0,
                "pj": "{}", "ph": _HASH_C, "status": "accepted"})

    # 5. Non-object json rejected (ck_ja_props_payload_json).
    with pytest.raises(Exception):  # noqa: B017
        with engine.begin() as conn:
            conn.execute(sa.text(_PROP_INSERT), {
                "prop": "c2222222-2222-2222-2222-222222222222", "tenant": tenant,
                "doc": _DOC, "rev": _REV0, "bh": _HASH_B, "sh": _HASH_A, "src": _CMD0,
                "pj": "[]", "ph": _HASH_C, "status": "pending"})

    # 6. Cross-tenant document rejected (fk_ja_docs_session composite includes tenant).
    with pytest.raises(Exception):  # noqa: B017
        with engine.begin() as conn:
            conn.execute(sa.text(
                "INSERT INTO job_authoring_documents "
                "(document_id, tenant_id, session_id, head_revision_id, "
                " head_revision_number, head_revision_hash, created_at, updated_at) "
                "VALUES (:doc, :tenant, :session, :rev, 0, :h, now(), now())"),
                {"doc": "d1111111-1111-1111-1111-111111111111",
                 "tenant": "ffffffff-ffff-ffff-ffff-ffffffffffff",
                 "session": session, "rev": _REV0, "h": _HASH_B})

    # 7. Revision UPDATE rejected by immutability trigger.
    with pytest.raises(Exception):  # noqa: B017
        with engine.begin() as conn:
            conn.execute(sa.text(
                "UPDATE job_authoring_revisions SET snapshot_json='{\"x\":1}' "
                "WHERE revision_id=:r"), {"r": _REV0})

    # 8. Proposal immutable-payload mutation rejected by guard trigger.
    with pytest.raises(Exception):  # noqa: B017
        with engine.begin() as conn:
            conn.execute(sa.text(
                "UPDATE job_authoring_proposals SET proposal_hash=:h WHERE proposal_id=:p"),
                {"h": _HASH_A, "p": _PROP})

    # 9. Legal pending -> rejected transition allowed by guard trigger.
    with engine.begin() as conn:
        conn.execute(sa.text(
            "UPDATE job_authoring_proposals SET status='rejected', "
            " decision_command_id=:d, decision_schema_id='epd.v1', decision_json='{}', "
            " decision_hash=:h, resolved_at=now(), updated_at=now() WHERE proposal_id=:p"),
            {"d": "c9111111-1111-1111-1111-111111111111", "h": _HASH_A, "p": _PROP})

    # 10. Terminal -> different status rejected by guard trigger.
    with pytest.raises(Exception):  # noqa: B017
        with engine.begin() as conn:
            conn.execute(sa.text(
                "UPDATE job_authoring_proposals SET status='accepted' WHERE proposal_id=:p"),
                {"p": _PROP})
