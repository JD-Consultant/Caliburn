"""Opt-in PG18 setup faults on newly created, retained synthetic databases.

The lease is a branch adapter here, not Windows ownership evidence. Separate
configured-host tests exercise the real Windows process capability. No database
or table removal; two synthetic faults replace one CHECK or index definition.
"""
import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from psycopg import Connection, errors, sql
from psycopg.rows import dict_row
import pytest
import sqlalchemy as sa

from jd_relational.local_configuration import configuration_phase, new_configuration
from jd_relational import storage_setup as setup
from jd_relational.windows_host import HostLease


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL opt-in required")
APP = Path(__file__).resolve().parents[1]


def connect(database):
    return Connection.connect(host="127.0.0.1", port=55436, dbname=database,
        user="jd_test", password="jd-local-test-only", autocommit=True,
        row_factory=dict_row, prepare_threshold=0, connect_timeout=5)


@pytest.fixture
def database(monkeypatch):
    name = "caliburn_jd_setup_test_" + uuid4().hex
    # Only this confirmed dedicated fixture is allowed to CREATE a test DB.
    with connect("caliburn_jd_relational_test") as admin:
        assert admin.execute("SELECT current_database() AS db, current_user AS usr, "
            "current_setting('server_version_num')::integer AS v").fetchone() == {
                "db": "caliburn_jd_relational_test", "usr": "jd_test", "v": 180006}
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
    value = new_configuration(host="127.0.0.1", port=55436, database=name,
        username="jd_test", password="jd-local-test-only", checkpoint_schema="jd_runtime",
        api_port=3002, allowed_origins=("http://127.0.0.1:3001",))
    lease = object.__new__(HostLease)
    lease._instance_key = value.installation_id
    monkeypatch.setattr(HostLease, "require_previous_stopped", lambda self: None)
    with connect(name) as connection:
        yield value, lease, connection
    print("retained synthetic database:", name)


def prepare_jd(settings):
    engine = sa.create_engine(settings.database_url(), hide_parameters=True,
        connect_args={"connect_timeout": 5, "options": "-csearch_path=public"})
    try:
        with engine.begin() as connection:
            config = Config(str(APP / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, setup.REVISION)
    finally:
        engine.dispose()


def prepare_native(connection, last, *, ahead=False):
    connection.execute("CREATE SCHEMA jd_runtime AUTHORIZATION CURRENT_USER")
    connection.execute("SET search_path TO jd_runtime")
    for version in range(last + 1):
        connection.execute(PostgresSaver.MIGRATIONS[version])
        connection.execute("INSERT INTO checkpoint_migrations(v) VALUES (%s)", (version,))
    if ahead:
        connection.execute(PostgresSaver.MIGRATIONS[last + 1])


def test_explicit_setup_commits_native_schema_and_can_finish_lost_ready_publication(database):
    settings, lease, connection = database
    setup.check_empty_database(settings)
    initializing = configuration_phase(settings, "initializing")
    setup.setup_database(initializing, lease)
    setup.check_installed(connection, settings.checkpoint_schema)
    assert len(setup._snapshot(connection, settings.checkpoint_schema)) == 8
    setup.setup_database(initializing, lease)
    setup.check_installed(connection, settings.checkpoint_schema)
    assert settings.phase == "initialization_pending" and initializing.phase == "initializing"
    with pytest.raises(setup.StorageSetupError, match="^database_not_empty$"):
        setup.check_empty_database(settings)


@pytest.mark.parametrize("ddl", [
    "CREATE TABLE public.existing_work(id integer)",
    "CREATE VIEW public.existing_work AS SELECT 1 AS id",
    "CREATE SCHEMA existing_owner",
    "CREATE FUNCTION public.existing_work() RETURNS integer LANGUAGE SQL AS 'SELECT 1'",
])
def test_pending_rejects_unknown_database_without_adopting_or_deleting(database, ddl):
    settings, _, connection = database
    connection.execute(ddl)
    with pytest.raises(setup.StorageSetupError):
        setup.check_empty_database(settings)
    assert connection.execute("SELECT to_regclass('public.alembic_version') AS value").fetchone()["value"] is None


@pytest.mark.parametrize("last,ahead", [(0, False), (3, False), (5, True), (8, True)])
def test_native_prefix_and_next_ddl_before_receipt_resume_without_data_loss(database, last, ahead):
    settings, lease, connection = database
    setup.check_empty_database(settings)
    prepare_jd(settings)
    prepare_native(connection, last, ahead=ahead)
    setup.setup_database(configuration_phase(settings, "initializing"), lease)
    setup.check_installed(connection, settings.checkpoint_schema)
    assert connection.execute("SELECT count(*) AS n FROM jd_runtime.checkpoints").fetchone()["n"] == 0


@pytest.mark.parametrize("fault", ["hole", "future", "wrong_column", "wrong_index", "wrong_default"])
def test_unknown_native_shape_never_blindly_runs_setup(database, fault):
    settings, lease, connection = database
    prepare_jd(settings)
    prepare_native(connection, 5)
    if fault == "hole":
        connection.execute("DELETE FROM checkpoint_migrations WHERE v=1")
    elif fault == "future":
        connection.execute("INSERT INTO checkpoint_migrations(v) VALUES (10)")
    elif fault == "wrong_column":
        connection.execute("ALTER TABLE checkpoint_writes ALTER COLUMN idx TYPE bigint")
    elif fault == "wrong_default":
        connection.execute("ALTER TABLE checkpoints ALTER COLUMN metadata SET DEFAULT '[]'::jsonb")
    else:
        connection.execute("CREATE INDEX checkpoints_thread_id_idx ON checkpoints(checkpoint_id)")
    before = connection.execute("SELECT v FROM checkpoint_migrations ORDER BY v").fetchall()
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup.setup_database(configuration_phase(settings, "initializing"), lease)
    assert connection.execute("SELECT v FROM checkpoint_migrations ORDER BY v").fetchall() == before


def test_failed_real_concurrent_index_remains_invalid_and_is_not_marked_finished(database):
    settings, lease, connection = database
    prepare_jd(settings)
    prepare_native(connection, 5)
    connection.execute("INSERT INTO checkpoints(thread_id,checkpoint_ns,checkpoint_id,checkpoint) "
        "VALUES ('duplicate','', '1','{}'), ('duplicate','', '2','{}')")
    with pytest.raises(errors.UniqueViolation):
        connection.execute("CREATE UNIQUE INDEX CONCURRENTLY checkpoints_thread_id_idx ON checkpoints(thread_id)")
    with pytest.raises(setup.StorageSetupError, match="^initialization_recovery_required$"):
        setup.setup_database(configuration_phase(settings, "initializing"), lease)
    assert connection.execute("SELECT indisvalid FROM pg_index "
        "WHERE indexrelid='jd_runtime.checkpoints_thread_id_idx'::regclass").fetchone() == {"indisvalid": False}
    assert connection.execute("SELECT max(v) AS v FROM checkpoint_migrations").fetchone() == {"v": 5}
    assert connection.execute("SELECT count(*) AS n FROM checkpoints").fetchone() == {"n": 2}


def test_installed_check_does_not_repair_missing_index(database):
    settings, lease, connection = database
    initializing = configuration_phase(settings, "initializing")
    setup.setup_database(initializing, lease)
    # Rename preserves the object and its data; no DROP is needed for this fault.
    connection.execute("ALTER INDEX jd_runtime.checkpoints_thread_id_idx RENAME TO unexpected_index")
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup.check_installed(connection, settings.checkpoint_schema)
    assert connection.execute("SELECT to_regclass('jd_runtime.checkpoints_thread_id_idx') AS x").fetchone() == {"x": None}


@pytest.mark.parametrize("fault", ["same_name_wrong_check", "same_name_wrong_predicate"])
def test_same_name_different_business_rule_is_not_installed(database, fault):
    settings, lease, connection = database
    setup.setup_database(configuration_phase(settings, "initializing"), lease)
    # This connection targets only this test's newly-created empty database.
    # Replace one rule while preserving its name, columns and object count.
    if fault == "same_name_wrong_check":
        connection.execute("ALTER TABLE public.jd_revision "
            "DROP CONSTRAINT ck_jd_revision_format_version, "
            "ADD CONSTRAINT ck_jd_revision_format_version CHECK (format_version = 4)")
    else:
        with connection.transaction():
            connection.execute("DROP INDEX public.uq_jd_revision_initial")
            connection.execute("CREATE UNIQUE INDEX uq_jd_revision_initial "
                "ON public.jd_revision(document_id) WHERE origin = 'manual'")
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup.check_installed(connection, settings.checkpoint_schema)


def prepare_store(connection, last, monkeypatch, *, ahead=False):
    original = PostgresStore.MIGRATIONS
    # Use official setup to create its version table and a bounded prefix;
    # optional next native DDL models commit before its version receipt.
    with monkeypatch.context() as scoped:
        scoped.setattr(PostgresStore, "MIGRATIONS", original[:last + 1])
        PostgresStore(connection).setup()
    if ahead:
        connection.execute(original[last + 1])


def test_saver_only_existing_database_is_not_installed_or_auto_upgraded(database):
    settings, _, connection = database
    prepare_jd(settings)
    prepare_native(connection, 9)
    before = setup._snapshot(connection, settings.checkpoint_schema)
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup.check_installed(connection, settings.checkpoint_schema)
    assert setup._snapshot(connection, settings.checkpoint_schema) == before
    assert len(before) == 4


@pytest.mark.parametrize("last,ahead", [(-1, False), (-1, True), (0, True), (1, True), (2, True), (3, False)])
def test_official_store_prefix_resumes_to_all_eight_tables(database, monkeypatch, last, ahead):
    settings, lease, connection = database
    prepare_jd(settings)
    prepare_native(connection, 9)
    prepare_store(connection, last, monkeypatch, ahead=ahead)
    setup.setup_database(configuration_phase(settings, "initializing"), lease)
    setup.check_installed(connection, settings.checkpoint_schema)
    assert connection.execute("SELECT v FROM store_migrations ORDER BY v").fetchall() == [{"v": v} for v in range(4)]
    assert connection.execute("SELECT count(*) AS n FROM store").fetchone() == {"n": 0}
    assert len(setup._snapshot(connection, settings.checkpoint_schema)) == 8


@pytest.mark.parametrize("fault", ["prefix_opclass", "prefix_descending", "ttl_predicate", "store_default", "publication_column"])
def test_same_name_wrong_memory_shape_stops_without_automatic_repair(database, fault):
    settings, lease, connection = database
    setup.setup_database(configuration_phase(settings, "initializing"), lease)
    connection.execute("SET search_path TO jd_runtime")
    # Only this test's newly-created empty DB; preserve tables and version rows.
    if fault in {"prefix_opclass", "prefix_descending"}:
        connection.execute("DROP INDEX store_prefix_idx")
        expression = "prefix" if fault == "prefix_opclass" else "prefix text_pattern_ops DESC"
        connection.execute("CREATE INDEX store_prefix_idx ON store (" + expression + ")")
    elif fault == "ttl_predicate":
        connection.execute("DROP INDEX idx_store_expires_at")
        connection.execute("CREATE INDEX idx_store_expires_at ON store(expires_at) WHERE expires_at IS NULL")
    elif fault == "store_default":
        connection.execute("ALTER TABLE store ALTER COLUMN created_at SET DEFAULT now()")
    else:
        connection.execute("ALTER TABLE q019_document_memory_head ALTER COLUMN revision TYPE bigint")
    before = setup._snapshot(connection, settings.checkpoint_schema)
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup.check_installed(connection, settings.checkpoint_schema)
    with pytest.raises(setup.StorageSetupError, match="^schema_mismatch$"):
        setup.setup_database(configuration_phase(settings, "initializing"), lease)
    assert setup._snapshot(connection, settings.checkpoint_schema) == before
    assert connection.execute("SELECT v FROM store_migrations ORDER BY v").fetchall() == [{"v": v} for v in range(4)]


@pytest.mark.parametrize("table", ["store", "q019_document_memory_head"])
def test_initializing_cannot_adopt_existing_memory_data(database, table):
    settings, lease, connection = database
    setup.setup_database(configuration_phase(settings, "initializing"), lease)
    if table == "store":
        connection.execute("INSERT INTO jd_runtime.store(prefix,key,value) VALUES ('synthetic','memory','{}')")
    else:
        connection.execute("INSERT INTO jd_runtime.q019_document_memory_head "
            "(document_id,revision,memory_version,last_operation_id) VALUES ('synthetic',1,'version','operation')")
    setup.check_installed(connection, settings.checkpoint_schema)  # ordinary ready reads allow real data
    with pytest.raises(setup.StorageSetupError, match="^initialization_recovery_required$"):
        setup.setup_database(configuration_phase(settings, "initializing"), lease)
    assert connection.execute(sql.SQL("SELECT count(*) AS n FROM jd_runtime.{}").format(
        sql.Identifier(table))).fetchone() == {"n": 1}


def test_publication_tables_are_created_in_one_transaction_and_resume_after_failure(database, monkeypatch):
    settings, lease, connection = database
    original = sa.create_engine
    failed = []

    def create(*args, **kwargs):
        engine = original(*args, **kwargs)
        def fail_second(_conn, _cursor, statement, _parameters, _context, _executemany):
            if "CREATE TABLE jd_runtime.q019_memory_publication_receipt" in statement and not failed:
                failed.append(True)
                raise RuntimeError("synthetic publication DDL failure")
        sa.event.listen(engine, "before_cursor_execute", fail_second)
        return engine

    monkeypatch.setattr(sa, "create_engine", create)
    with pytest.raises(setup.StorageSetupError, match="^storage_unavailable$"):
        setup.setup_database(configuration_phase(settings, "initializing"), lease)
    assert failed == [True]
    assert set(setup._snapshot(connection, settings.checkpoint_schema)) == {
        "checkpoint_migrations", "checkpoints", "checkpoint_blobs", "checkpoint_writes", "store_migrations", "store"}
    setup.setup_database(configuration_phase(settings, "initializing"), lease)
    setup.check_installed(connection, settings.checkpoint_schema)
