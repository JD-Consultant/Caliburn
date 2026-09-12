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
