"""V2-B-2:migration 0010 的 upgrade/downgrade/introspection gate(plan §5.4)。

在**可拋棄的獨立資料庫**跑完整循環(不碰共享 dev DB):
0009 → 插 v3 fixture → 快照 → 0010 → introspect 八張表(columns/nullability/
PK/FK/unique/CHECK/partial index/trigger)→ v3 快照不變 → downgrade 0009 →
vNext objects 全移除、v3 快照仍不變。

alembic 以 subprocess 執行(env.py 是 asyncio.run 的 async 腳本,不能在
pytest event loop 內呼叫;subprocess 也順便驗「乾淨環境 + DATABASE_URL」路徑)。
autogenerate 不擁有 CHECK/trigger 真相,introspection 才是 gate(§11)。
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
MIG_DB = "caliburn_vnext_migration_test"

VNEXT_TABLES = {
    "interview_vnext_sessions",
    "interview_vnext_runs",
    "interview_vnext_artifacts",
    "interview_vnext_commands",
    "interview_vnext_execution_events",
    "interview_vnext_outbox",
    "interview_vnext_operation_checkpoints",
    "interview_vnext_operation_attempts",
}

V3_SNAPSHOT_TABLES = ("users", "job_profiles", "interview_sessions", "interview_turns")


# ── 八張表的欄位契約(§5;kind ∈ uuid/text/timestamptz/bigint/integer/boolean)──

_SESSIONS = {
    "session_id": ("uuid", False), "tenant_id": ("uuid", False),
    "profile_id": ("uuid", False), "architecture_id": ("text", False),
    "workflow_version": ("text", False), "reference_snapshot_id": ("text", False),
    "status": ("text", False), "state_version": ("bigint", False),
    "state_schema_version": ("text", False), "state_json": ("text", False),
    "state_hash": ("text", False), "initial_state_artifact_id": ("uuid", True),
    "created_at": ("timestamptz", False), "updated_at": ("timestamptz", False),
}
_RUNS = {
    "run_id": ("uuid", False), "tenant_id": ("uuid", False),
    "session_id": ("uuid", False), "architecture_id": ("text", False),
    "workflow_version": ("text", False), "taxonomy_id": ("text", False),
    "taxonomy_version": ("text", False), "taxonomy_hash": ("text", False),
    "status": ("text", False), "event_count": ("bigint", False),
    "first_event_hash": ("text", True), "last_event_hash": ("text", True),
    "manifest_artifact_id": ("uuid", True), "started_at": ("timestamptz", False),
    "completed_at": ("timestamptz", True),
}
_ARTIFACTS = {
    "artifact_id": ("uuid", False), "tenant_id": ("uuid", False),
    "record_schema_version": ("text", False), "run_id": ("uuid", False),
    "session_id": ("uuid", True), "turn_id": ("uuid", True),
    "operation_id": ("uuid", True), "attempt_id": ("uuid", True),
    "kind": ("text", False), "media_type": ("text", False),
    "schema_id": ("text", True), "content_hash": ("text", False),
    "byte_size": ("bigint", False), "storage": ("text", False),
    "inline_content": ("text", True), "external_uri": ("text", True),
    "retention_class": ("text", False), "redaction_status": ("text", False),
    "contains_test_data": ("boolean", False), "created_at": ("timestamptz", False),
}
_COMMANDS = {
    "command_id": ("uuid", False), "tenant_id": ("uuid", False),
    "session_id": ("uuid", False), "run_id": ("uuid", False),
    "request_idempotency_key": ("text", True), "command_schema_id": ("text", False),
    "command_artifact_id": ("uuid", False), "command_hash": ("text", False),
    "reduction_artifact_id": ("uuid", False), "reduction_hash": ("text", False),
    "expected_state_version": ("bigint", False),
    "result_state_version": ("bigint", False), "result_state_hash": ("text", False),
    "result_reason_code": ("text", False), "occurred_at": ("timestamptz", False),
    "committed_at": ("timestamptz", False),
}
_EVENTS = {
    "event_id": ("uuid", False), "tenant_id": ("uuid", False),
    "run_id": ("uuid", False), "session_id": ("uuid", False),
    "turn_id": ("uuid", True), "operation_id": ("uuid", True),
    "parent_operation_id": ("uuid", True), "attempt_id": ("uuid", True),
    "attempt": ("integer", True), "event_schema_version": ("text", False),
    "event_type": ("text", False), "stage": ("text", False),
    "status": ("text", False), "sequence": ("bigint", False),
    "previous_event_hash": ("text", True), "event_hash": ("text", False),
    "event_json": ("text", False), "occurred_at": ("timestamptz", False),
    "created_at": ("timestamptz", False),
}
_OUTBOX = {
    "message_id": ("uuid", False), "tenant_id": ("uuid", False),
    "run_id": ("uuid", False), "event_sequence": ("bigint", False),
    "event_hash": ("text", False), "event_json": ("text", False),
    "status": ("text", False), "delivery_attempts": ("integer", False),
    "lease_owner": ("text", True), "lease_expires_at": ("timestamptz", True),
    "next_attempt_at": ("timestamptz", True), "delivered_at": ("timestamptz", True),
    "last_error_code": ("text", True), "created_at": ("timestamptz", False),
    "updated_at": ("timestamptz", False),
}
_CHECKPOINTS = {
    "checkpoint_id": ("uuid", False), "tenant_id": ("uuid", False),
    "run_id": ("uuid", False), "session_id": ("uuid", False),
    "turn_id": ("uuid", True), "operation_id": ("uuid", False),
    "operation_name": ("text", False), "operation_definition_hash": ("text", False),
    "idempotency_key": ("text", False), "status": ("text", False),
    "revision": ("bigint", False), "checkpoint_schema_version": ("text", False),
    "checkpoint_json": ("text", False), "request_artifact_id": ("uuid", False),
    "active_attempt_id": ("uuid", True), "active_attempt": ("integer", True),
    "provider_result_artifact_id": ("uuid", True),
    "verification_artifact_id": ("uuid", True),
    "domain_result_artifact_id": ("uuid", True), "response_artifact_id": ("uuid", True),
    "failure_artifact_id": ("uuid", True), "failure_reason_code": ("text", True),
    "state_before_hash": ("text", False), "state_after_hash": ("text", True),
    "created_at": ("timestamptz", False), "updated_at": ("timestamptz", False),
}
_ATTEMPTS = {
    "attempt_id": ("uuid", False), "tenant_id": ("uuid", False),
    "run_id": ("uuid", False), "session_id": ("uuid", False),
    "operation_id": ("uuid", False), "attempt": ("integer", False),
    "status": ("text", False), "request_artifact_id": ("uuid", False),
    "result_artifact_id": ("uuid", True), "provider": ("text", False),
    "requested_model": ("text", False), "provider_execution_ref_kind": ("text", True),
    "provider_execution_ref": ("text", True), "deadline_at": ("timestamptz", False),
    "started_at": ("timestamptz", False), "updated_at": ("timestamptz", False),
    "completed_at": ("timestamptz", True),
}

EXPECTED_COLUMNS = {
    "interview_vnext_sessions": _SESSIONS,
    "interview_vnext_runs": _RUNS,
    "interview_vnext_artifacts": _ARTIFACTS,
    "interview_vnext_commands": _COMMANDS,
    "interview_vnext_execution_events": _EVENTS,
    "interview_vnext_outbox": _OUTBOX,
    "interview_vnext_operation_checkpoints": _CHECKPOINTS,
    "interview_vnext_operation_attempts": _ATTEMPTS,
}

EXPECTED_PK = {
    "interview_vnext_sessions": ["session_id"],
    "interview_vnext_runs": ["run_id"],
    "interview_vnext_artifacts": ["artifact_id"],
    "interview_vnext_commands": ["command_id"],
    "interview_vnext_execution_events": ["event_id"],
    "interview_vnext_outbox": ["message_id"],
    "interview_vnext_operation_checkpoints": ["checkpoint_id"],
    "interview_vnext_operation_attempts": ["attempt_id"],
}

EXPECTED_UNIQUES = {
    "interview_vnext_sessions": {"uq_ivn_sessions_tenant_session"},
    "interview_vnext_runs": {"uq_ivn_runs_tenant_run"},
    "interview_vnext_artifacts": {"uq_ivn_artifacts_tenant_artifact"},
    "interview_vnext_commands": {"uq_ivn_commands_tenant_session_command"},
    "interview_vnext_execution_events": {"uq_ivn_events_tenant_run_sequence"},
    "interview_vnext_outbox": {"uq_ivn_outbox_tenant_run_sequence"},
    "interview_vnext_operation_checkpoints": {
        "uq_ivn_ckpt_tenant_operation", "uq_ivn_ckpt_idempotency"},
    "interview_vnext_operation_attempts": {
        "uq_ivn_attempts_tenant_attempt", "uq_ivn_attempts_operation_attempt"},
}

EXPECTED_FK_NAMES = {
    "interview_vnext_sessions": {"fk_ivn_sessions_profile", "fk_ivn_sessions_initial_state"},
    "interview_vnext_runs": {"fk_ivn_runs_session", "fk_ivn_runs_manifest_artifact"},
    "interview_vnext_artifacts": {"fk_ivn_artifacts_run", "fk_ivn_artifacts_session"},
    "interview_vnext_commands": {
        "fk_ivn_commands_session", "fk_ivn_commands_run",
        "fk_ivn_commands_command_artifact", "fk_ivn_commands_reduction_artifact"},
    "interview_vnext_execution_events": {"fk_ivn_events_run", "fk_ivn_events_session"},
    "interview_vnext_outbox": {"fk_ivn_outbox_event", "fk_ivn_outbox_run"},
    "interview_vnext_operation_checkpoints": {
        "fk_ivn_ckpt_run", "fk_ivn_ckpt_session", "fk_ivn_ckpt_request_artifact",
        "fk_ivn_ckpt_provider_result", "fk_ivn_ckpt_verification",
        "fk_ivn_ckpt_domain_result", "fk_ivn_ckpt_response", "fk_ivn_ckpt_failure"},
    "interview_vnext_operation_attempts": {
        "fk_ivn_attempts_checkpoint", "fk_ivn_attempts_run", "fk_ivn_attempts_session",
        "fk_ivn_attempts_request_artifact", "fk_ivn_attempts_result_artifact"},
}

EXPECTED_CHECK_NAMES = {
    "interview_vnext_sessions": {
        "ck_ivn_sessions_status", "ck_ivn_sessions_state_version",
        "ck_ivn_sessions_state_hash", "ck_ivn_sessions_state_json_object",
        "ck_ivn_sessions_time_order"},
    "interview_vnext_runs": {
        "ck_ivn_runs_status", "ck_ivn_runs_event_count",
        "ck_ivn_runs_event_hash_coherence", "ck_ivn_runs_lifecycle",
        "ck_ivn_runs_first_hash", "ck_ivn_runs_last_hash", "ck_ivn_runs_taxonomy_hash"},
    "interview_vnext_artifacts": {
        "ck_ivn_artifacts_storage_location", "ck_ivn_artifacts_redaction",
        "ck_ivn_artifacts_content_hash", "ck_ivn_artifacts_byte_size",
        "ck_ivn_artifacts_kind_name", "ck_ivn_artifacts_retention_name"},
    "interview_vnext_commands": {
        "ck_ivn_commands_command_hash", "ck_ivn_commands_reduction_hash",
        "ck_ivn_commands_result_hash", "ck_ivn_commands_version_increment",
        "ck_ivn_commands_reason_name"},
    "interview_vnext_execution_events": {
        "ck_ivn_events_status", "ck_ivn_events_sequence_positive",
        "ck_ivn_events_chain_link", "ck_ivn_events_attempt_pair",
        "ck_ivn_events_event_hash", "ck_ivn_events_previous_hash",
        "ck_ivn_events_event_json_object"},
    "interview_vnext_outbox": {
        "ck_ivn_outbox_status", "ck_ivn_outbox_attempts", "ck_ivn_outbox_sequence",
        "ck_ivn_outbox_event_hash", "ck_ivn_outbox_event_json_object",
        "ck_ivn_outbox_lease_shape", "ck_ivn_outbox_retry_shape",
        "ck_ivn_outbox_delivered_shape", "ck_ivn_outbox_error_shape",
        "ck_ivn_outbox_time_order"},
    "interview_vnext_operation_checkpoints": {
        "ck_ivn_ckpt_status", "ck_ivn_ckpt_revision", "ck_ivn_ckpt_attempt_shape",
        "ck_ivn_ckpt_provider_shape", "ck_ivn_ckpt_verification_shape",
        "ck_ivn_ckpt_committed_shape", "ck_ivn_ckpt_failed_shape",
        "ck_ivn_ckpt_definition_hash", "ck_ivn_ckpt_before_hash",
        "ck_ivn_ckpt_after_hash", "ck_ivn_ckpt_json_object", "ck_ivn_ckpt_time_order"},
    "interview_vnext_operation_attempts": {
        "ck_ivn_attempts_status", "ck_ivn_attempts_number",
        "ck_ivn_attempts_result_shape", "ck_ivn_attempts_ref_pair",
        "ck_ivn_attempts_provider", "ck_ivn_attempts_time_order"},
}

# partial index → 必含的 WHERE 片段(predicate 與 lease query status 完全相同)
EXPECTED_PARTIAL_INDEXES = {
    "ix_ivn_outbox_pending": "WHERE (status = 'pending'",
    "ix_ivn_outbox_retry": "WHERE (status = 'retry_wait'",
    "ix_ivn_outbox_expired": "WHERE (status = 'leased'",
    "uq_ivn_commands_request_key": "WHERE (request_idempotency_key IS NOT NULL",
}

EXPECTED_TRIGGERS = {
    ("interview_vnext_artifacts", "ivn_artifacts_reject_update"),
    ("interview_vnext_execution_events", "ivn_events_reject_update"),
    ("interview_vnext_commands", "ivn_commands_reject_update"),
    ("interview_vnext_outbox", "ivn_outbox_guard_update"),
}


def _sync_url(database: str) -> str:
    url = make_url(TEST_DATABASE_URL).set(drivername="postgresql+psycopg",
                                          database=database)
    return url.render_as_string(hide_password=False)


def _async_url(database: str) -> str:
    url = make_url(TEST_DATABASE_URL).set(drivername="postgresql+asyncpg",
                                          database=database)
    return url.render_as_string(hide_password=False)


def _alembic(direction: str, target: str, database_url: str) -> None:
    env = {**os.environ, "DATABASE_URL": database_url, "PYTHONUTF8": "1"}
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", direction, target],
        cwd=API_DIR, env=env, capture_output=True, text=True, timeout=180,
        encoding="utf-8", errors="replace")   # Windows console 預設 cp950,顯式 UTF-8
    assert proc.returncode == 0, f"alembic {direction} {target} failed:\n{proc.stderr}"


def _snapshot_v3(engine) -> dict:
    """v3 tables 的 columns + row content hash(遷移前後必須 byte 級不變)。"""
    out: dict = {}
    with engine.connect() as conn:
        for table in V3_SNAPSHOT_TABLES:
            cols = conn.execute(sa.text(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :t "
                "ORDER BY ordinal_position"), {"t": table}).all()
            rows = conn.execute(sa.text(
                f"SELECT count(*), coalesce(string_agg(md5(t::text), ','"  # noqa: S608
                f" ORDER BY md5(t::text)), '') FROM {table} t")).one()
            out[table] = {"columns": [tuple(c) for c in cols],
                          "count": rows[0], "content": rows[1]}
    return out


def _column_kind(coltype) -> str:
    if isinstance(coltype, postgresql.UUID):
        return "uuid"
    if isinstance(coltype, (sa.TIMESTAMP, sa.DateTime)):
        assert getattr(coltype, "timezone", False), "timestamp must be timezone-aware"
        return "timestamptz"
    if isinstance(coltype, sa.BigInteger):
        return "bigint"
    if isinstance(coltype, sa.Boolean):
        return "boolean"
    if isinstance(coltype, sa.Integer):
        return "integer"
    if isinstance(coltype, (sa.Text, sa.String)):
        return "text"
    return str(coltype).lower()


def test_alembic_has_single_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert heads == ["0016"]


@pytest.mark.usefixtures("require_postgres")
def test_migration_0010_cycle_preserves_v3_and_builds_exact_schema():
    admin = sa.create_engine(_sync_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(sa.text(f"DROP DATABASE IF EXISTS {MIG_DB} WITH (FORCE)"))
        conn.execute(sa.text(f"CREATE DATABASE {MIG_DB}"))
    engine = sa.create_engine(_sync_url(MIG_DB))
    try:
        # 1–2. upgrade 0009 + v3 fixture + 快照
        _alembic("upgrade", "0009", _async_url(MIG_DB))
        with engine.begin() as conn:
            conn.execute(sa.text(
                "INSERT INTO users (id, email, name) "
                "VALUES ('11111111-1111-1111-1111-111111111111', "
                "'mig@test.local', '遷移測試使用者')"))
            conn.execute(sa.text(
                "INSERT INTO job_profiles (id, user_id, job_title) "
                "VALUES ('22222222-2222-2222-2222-222222222222', "
                "'11111111-1111-1111-1111-111111111111', '遷移測試職務')"))
            conn.execute(sa.text(
                "INSERT INTO interview_sessions (id, job_profile_id) "
                "VALUES ('33333333-3333-3333-3333-333333333333', "
                "'22222222-2222-2222-2222-222222222222')"))
            conn.execute(sa.text(
                "INSERT INTO interview_turns (id, session_id, seq, role, text) "
                "VALUES ('44444444-4444-4444-4444-444444444444', "
                "'33333333-3333-3333-3333-333333333333', 1, 'employee', "
                "'遷移前的逐字稿內容')"))
        before = _snapshot_v3(engine)

        # 3. upgrade the vNext migration under test (not the repository head)
        _alembic("upgrade", "0010", _async_url(MIG_DB))

        # 4. introspection:八張表,不多不少
        inspector = sa.inspect(engine)
        actual_vnext = {t for t in inspector.get_table_names(schema="public")
                        if t.startswith("interview_vnext_")}
        assert actual_vnext == VNEXT_TABLES

        for table, expected_cols in EXPECTED_COLUMNS.items():
            cols = {c["name"]: c for c in inspector.get_columns(table)}
            assert set(cols) == set(expected_cols), f"{table} column set mismatch"
            for name, (kind, nullable) in expected_cols.items():
                assert _column_kind(cols[name]["type"]) == kind, f"{table}.{name} type"
                assert cols[name]["nullable"] == nullable, f"{table}.{name} nullability"

            assert inspector.get_pk_constraint(table)["constrained_columns"] == \
                EXPECTED_PK[table], f"{table} primary key"

            uniques = {u["name"] for u in inspector.get_unique_constraints(table)}
            assert uniques == EXPECTED_UNIQUES[table], f"{table} unique constraints"

            fks = {fk["name"]: fk for fk in inspector.get_foreign_keys(table)}
            assert set(fks) == EXPECTED_FK_NAMES[table], f"{table} foreign keys"
            for fk in fks.values():
                assert fk["options"].get("ondelete") == "RESTRICT", \
                    f"{table} FK {fk['name']} must be ON DELETE RESTRICT"
                assert fk["referred_table"].startswith("interview_vnext_") or \
                    fk["referred_table"] == "job_profiles"

            checks = {c["name"] for c in inspector.get_check_constraints(table)}
            assert checks == EXPECTED_CHECK_NAMES[table], f"{table} check constraints"

            for name in ({*EXPECTED_UNIQUES[table], *EXPECTED_FK_NAMES[table],
                          *EXPECTED_CHECK_NAMES[table]}):
                assert len(name.encode()) < 63, f"identifier too long: {name}"

        # partial indexes:predicate 必須與 lease/idempotency 查詢一致
        with engine.connect() as conn:
            index_defs = dict(conn.execute(sa.text(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE schemaname = 'public' AND tablename LIKE 'interview_vnext_%'"
            )).all())
            for index, fragment in EXPECTED_PARTIAL_INDEXES.items():
                assert index in index_defs, f"missing index {index}"
                assert fragment in index_defs[index], f"{index} predicate mismatch"
            assert "UNIQUE" in index_defs["uq_ivn_commands_request_key"]
            for plain in ("ix_ivn_sessions_tenant_profile",
                          "ix_ivn_runs_tenant_session_started",
                          "ix_ivn_artifacts_tenant_session_created",
                          "ix_ivn_artifacts_operation_attempt",
                          "ix_ivn_events_tenant_session_occurred",
                          "ix_ivn_events_operation_attempt",
                          "ix_ivn_outbox_run_ordering"):
                assert plain in index_defs, f"missing index {plain}"

            triggers = set(conn.execute(sa.text(
                "SELECT event_object_table, trigger_name "
                "FROM information_schema.triggers "
                "WHERE trigger_schema = 'public' AND trigger_name LIKE 'ivn_%'"
            )).all())
            assert {(t, n) for t, n in triggers} == EXPECTED_TRIGGERS

        # 5. v3 完全不變
        assert _snapshot_v3(engine) == before

        # 6–7. downgrade 0009:vNext objects 全移除、v3 不變
        _alembic("downgrade", "0009", _async_url(MIG_DB))
        inspector = sa.inspect(engine)
        assert not any(t.startswith("interview_vnext_")
                       for t in inspector.get_table_names(schema="public"))
        with engine.connect() as conn:
            leftover_functions = conn.execute(sa.text(
                "SELECT proname FROM pg_proc WHERE proname LIKE 'ivn_%'")).all()
            assert leftover_functions == []
        assert _snapshot_v3(engine) == before
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(sa.text(f"DROP DATABASE IF EXISTS {MIG_DB} WITH (FORCE)"))
        admin.dispose()
