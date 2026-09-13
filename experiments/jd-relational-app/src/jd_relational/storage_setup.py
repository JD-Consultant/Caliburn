"""Explicit, bounded initialization of an already configured local database.

No configuration writes, database creation, model calls or automatic repairs.
The caller persists the initialization phase and owns the native host lease.
"""
from pathlib import Path
import json
import re

from alembic import command
from alembic.config import Config
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from caliburn_memory.publication import Base as MemoryPublicationBase
from psycopg import Connection, sql
from psycopg.rows import dict_row
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from .local_configuration import LocalConfiguration, encode_configuration
from .storage.schema import metadata
from .windows_host import HostLease
from . import storage_memory_profile as memory_profile


REVISION = "20260913_0001"
SAVER_VERSION_COUNT = 10


class StorageSetupError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code="schema_mismatch"):
    if not condition:
        raise StorageSetupError(code)


def _settings(value, phase):
    try:
        _require(type(value) is LocalConfiguration, "invalid_setup_configuration")
        encode_configuration(value)
    except Exception:
        raise StorageSetupError("invalid_setup_configuration") from None
    _require(value.phase == phase, "initialization_required")


def _lease(lease, settings):
    try:
        _require(isinstance(lease, HostLease), "host_lease_invalid")
        lease.require_previous_stopped()
        _require(lease._instance_key == settings.installation_id, "host_lease_invalid")
    except Exception:
        raise StorageSetupError("host_lease_invalid") from None


def _schema_name(value):
    _require(type(value) is str and re.fullmatch(r"[a-z][a-z0-9_]{0,62}", value)
        and not value.startswith("pg_") and value not in {"public", "information_schema"},
        "invalid_setup_configuration")


def _connect(settings):
    return Connection.connect(host=settings.host, port=settings.port,
        dbname=settings.database, user=settings.username, password=settings.password,
        connect_timeout=5, autocommit=True, row_factory=dict_row, prepare_threshold=0,
        options="-csearch_path=pg_catalog")


def _identity(connection, settings=None):
    row = connection.execute("SELECT current_database() AS db, current_user AS usr, "
        "current_setting('server_version_num')::integer AS v").fetchone()
    _require(row["v"] == 180006)
    if settings is not None:
        _require(row["db"] == settings.database and row["usr"] == settings.username)


def _namespaces(connection):
    return {row["nspname"] for row in connection.execute(
        "SELECT nspname FROM pg_catalog.pg_namespace "
        "WHERE nspname !~ '^pg_' AND nspname <> 'information_schema'")}


def _other_objects(connection, schemas):
    # Composite row and array types generated for ordinary tables are expected.
    rows = connection.execute("SELECT 1 FROM pg_catalog.pg_proc p "
        "JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname = ANY(%s) UNION ALL "
        "SELECT 1 FROM pg_catalog.pg_type t JOIN pg_catalog.pg_namespace n ON n.oid=t.typnamespace "
        "WHERE n.nspname = ANY(%s) AND t.typrelid=0 AND t.typelem=0 UNION ALL "
        "SELECT 1 FROM pg_catalog.pg_trigger g JOIN pg_catalog.pg_class c ON c.oid=g.tgrelid "
        "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname = ANY(%s) AND NOT g.tgisinternal UNION ALL "
        "SELECT 1 FROM pg_catalog.pg_extension WHERE extname <> 'plpgsql' LIMIT 1",
        (list(schemas), list(schemas), list(schemas))).fetchone()
    return rows is not None


def _snapshot(connection, schema):
    relations = connection.execute("SELECT c.relname AS name, c.relkind AS kind "
        "FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname=%s", (schema,)).fetchall()
    _require(all(row["kind"] in {"r", "i"} for row in relations))
    tables = {row["name"]: {"columns": {}, "defaults": {}, "constraints": {}, "indexes": {}}
        for row in relations if row["kind"] == "r"}
    columns = connection.execute("SELECT c.relname AS tbl, a.attname AS name, "
        "pg_catalog.format_type(a.atttypid,a.atttypmod) AS typ, a.attnotnull AS required, "
        "pg_catalog.pg_get_expr(d.adbin,d.adrelid) AS default_value "
        "FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid "
        "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
        "LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum "
        "WHERE n.nspname=%s AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped",
        (schema,)).fetchall()
    for row in columns:
        tables[row["tbl"]]["columns"][row["name"]] = (row["typ"], row["required"])
        if row["default_value"] is not None:
            tables[row["tbl"]]["defaults"][row["name"]] = row["default_value"]
    constraints = connection.execute("SELECT t.relname AS tbl, c.conname AS name, "
        "c.contype AS kind, c.convalidated AS valid, c.condeferrable AS deferred, "
        "pg_catalog.pg_get_constraintdef(c.oid,false) AS definition, "
        "ARRAY(SELECT a.attname FROM unnest(c.conkey) WITH ORDINALITY k(num,ord) "
        "JOIN pg_catalog.pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.num ORDER BY k.ord) AS cols, "
        "rn.nspname AS refschema, rt.relname AS reftable, c.confdeltype AS ondelete, "
        "ARRAY(SELECT a.attname FROM unnest(c.confkey) WITH ORDINALITY k(num,ord) "
        "JOIN pg_catalog.pg_attribute a ON a.attrelid=c.confrelid AND a.attnum=k.num ORDER BY k.ord) AS refcols "
        "FROM pg_catalog.pg_constraint c JOIN pg_catalog.pg_class t ON t.oid=c.conrelid "
        "JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace "
        "LEFT JOIN pg_catalog.pg_class rt ON rt.oid=c.confrelid "
        "LEFT JOIN pg_catalog.pg_namespace rn ON rn.oid=rt.relnamespace WHERE n.nspname=%s",
        (schema,)).fetchall()
    for row in constraints:
        _require(row["valid"] and not row["deferred"])
        # PG18 materializes NOT NULL constraints; column nullability above is SSOT.
        if row["kind"] == "n":
            continue
        item = (row["kind"], tuple(row["cols"]))
        if row["kind"] == "f":
            item += (row["refschema"], row["reftable"], tuple(row["refcols"]), row["ondelete"])
        if row["kind"] == "c":
            item = ("c", row["definition"])
        tables[row["tbl"]]["constraints"][row["name"]] = item
    indexes = connection.execute("SELECT t.relname AS tbl, x.relname AS name, "
        "i.indisvalid AS valid, i.indisready AS ready, i.indislive AS live, "
        "i.indisunique AS uniq, am.amname AS method, "
        "pg_catalog.pg_get_expr(i.indpred,i.indrelid,false) AS predicate, "
        "i.indexprs IS NOT NULL AS expression, i.indnatts=i.indnkeyatts AS no_include, "
        "ARRAY(SELECT a.attname FROM unnest(i.indkey::smallint[]) WITH ORDINALITY k(num,ord) "
        "LEFT JOIN pg_catalog.pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.num ORDER BY k.ord) AS cols "
        "FROM pg_catalog.pg_index i JOIN pg_catalog.pg_class x ON x.oid=i.indexrelid "
        "JOIN pg_catalog.pg_class t ON t.oid=i.indrelid "
        "JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace "
        "JOIN pg_catalog.pg_am am ON am.oid=x.relam WHERE n.nspname=%s", (schema,)).fetchall()
    for row in indexes:
        _require(row["valid"] and row["ready"] and row["live"], "initialization_recovery_required")
        _require(row["method"] == "btree" and not row["expression"] and row["no_include"])
        tables[row["tbl"]]["indexes"][row["name"]] = (
            tuple(row["cols"]), row["uniq"], row["predicate"])
    _require({r["name"] for r in relations if r["kind"] == "i"}
        == {name for table in tables.values() for name in table["indexes"]})
    return tables


def _column_type(column):
    value = column.type.compile(dialect=postgresql.dialect()).lower()
    return value.replace("varchar", "character varying").replace("char(", "character(")


def _ddl_profile():
    # PG18.6's own canonical output from this fixed migration. Fail closed on
    # another profile; do not parse SQL or infer semantic equivalence locally.
    path = Path(__file__).with_name("storage") / "ddl_profile_v1.json"
    profile = json.loads(path.read_text(encoding="utf-8"))
    _require(profile["profile_version"] == 1 and profile["postgresql_server_version_num"] == 180006
        and profile["alembic_revision"] == REVISION)
    expected_checks = {(table.name, constraint.name) for table in metadata.tables.values()
        for constraint in table.constraints if isinstance(constraint, sa.CheckConstraint)}
    expected_partials = {(table.name, index.name) for table in metadata.tables.values()
        for index in table.indexes if index.dialect_options["postgresql"]["where"] is not None}
    _require({(table, name) for table, values in profile["checks"].items() for name in values} == expected_checks)
    _require({(table, name) for table, values in profile["partial_indexes"].items() for name in values} == expected_partials)
    return profile


def _jd_expected():
    tables = {}
    profile = _ddl_profile()
    actions = {"RESTRICT": "r", "CASCADE": "c", "SET NULL": "n", "NO ACTION": "a"}
    for table in metadata.tables.values():
        item = {"columns": {c.name: (_column_type(c), not c.nullable) for c in table.columns},
            "defaults": {c.name: str(c.server_default.arg) for c in table.columns if c.server_default is not None},
            "constraints": {}, "indexes": {}}
        for constraint in table.constraints:
            if isinstance(constraint, sa.CheckConstraint):
                item["constraints"][constraint.name] = ("c", profile["checks"][table.name][constraint.name])
            elif isinstance(constraint, sa.ForeignKeyConstraint):
                item["constraints"][constraint.name] = ("f", tuple(c.name for c in constraint.columns),
                    "public", constraint.referred_table.name,
                    tuple(e.column.name for e in constraint.elements), actions[constraint.ondelete or "NO ACTION"])
            elif isinstance(constraint, (sa.PrimaryKeyConstraint, sa.UniqueConstraint)):
                kind = "p" if isinstance(constraint, sa.PrimaryKeyConstraint) else "u"
                cols = tuple(c.name for c in constraint.columns)
                item["constraints"][constraint.name] = (kind, cols)
                item["indexes"][constraint.name] = (cols, True, None)
        for index in table.indexes:
            cols = tuple(column.name for column in index.columns)
            predicate = profile["partial_indexes"].get(table.name, {}).get(index.name)
            item["indexes"][index.name] = (cols, bool(index.unique), predicate)
        tables[table.name] = item
    tables["alembic_version"] = {"columns": {"version_num": ("character varying(32)", True)}, "defaults": {},
        "constraints": {"alembic_version_pkc": ("p", ("version_num",))},
        "indexes": {"alembic_version_pkc": (("version_num",), True, None)}}
    return tables


def _native_expected(version):
    tables = {}
    definitions = [
        ("checkpoint_migrations", {"v": ("integer", True)}, ("v",)),
        ("checkpoints", {**{name: ("text", True) for name in ("thread_id", "checkpoint_ns", "checkpoint_id")},
            "parent_checkpoint_id": ("text", False), "type": ("text", False),
            "checkpoint": ("jsonb", True), "metadata": ("jsonb", True)},
            ("thread_id", "checkpoint_ns", "checkpoint_id")),
        ("checkpoint_blobs", {**{name: ("text", True) for name in ("thread_id", "checkpoint_ns", "channel", "version", "type")},
            "blob": ("bytea", False)}, ("thread_id", "checkpoint_ns", "channel", "version")),
        ("checkpoint_writes", {**{name: ("text", True) for name in ("thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "channel")},
            "idx": ("integer", True), "type": ("text", False), "blob": ("bytea", True)},
            ("thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "idx")),
    ]
    for step, (name, columns, primary) in enumerate(definitions):
        if step > version:
            break
        defaults = {} if step == 0 else {"checkpoint_ns": "''::text"}
        if step == 1:
            defaults["metadata"] = "'{}'::jsonb"
        tables[name] = {"columns": columns, "defaults": defaults, "constraints": {name + "_pkey": ("p", primary)},
            "indexes": {name + "_pkey": (primary, True, None)}}
    for step, name in enumerate(("checkpoints", "checkpoint_blobs", "checkpoint_writes"), 6):
        if version >= step:
            tables[name]["indexes"][name + "_thread_id_idx"] = (("thread_id",), False, None)
    if version >= 9:
        tables["checkpoint_writes"]["columns"]["task_path"] = ("text", True)
        tables["checkpoint_writes"]["defaults"]["task_path"] = "''::text"
    return tables


def _native_versions(connection, schema, snapshot):
    if "checkpoint_migrations" not in snapshot:
        return []
    return [row["v"] for row in connection.execute(sql.SQL(
        "SELECT v FROM {}.checkpoint_migrations ORDER BY v").format(sql.Identifier(schema)))]


def _require_native(snapshot, versions, *, complete):
    _require(len(PostgresSaver.MIGRATIONS) == SAVER_VERSION_COUNT)
    _require(all(type(v) is int for v in versions) and versions == list(range(len(versions)))
        and len(versions) <= SAVER_VERSION_COUNT)
    if complete:
        _require(len(versions) == SAVER_VERSION_COUNT and snapshot == _native_expected(9))
    else:
        last = len(versions) - 1
        candidates = [_native_expected(last), _native_expected(min(last + 1, 9))]
        _require(snapshot in candidates)


def _require_jd(connection, snapshot, *, allow_empty):
    if not snapshot and allow_empty:
        return
    _require(snapshot == _jd_expected())
    rows = connection.execute("SELECT version_num FROM public.alembic_version").fetchall()
    _require(rows == [{"version_num": REVISION}])


def _store_versions(connection, schema, snapshot):
    if "store_migrations" not in snapshot:
        return []
    return [row["v"] for row in connection.execute(sql.SQL(
        "SELECT v FROM {}.store_migrations ORDER BY v").format(sql.Identifier(schema)))]


def _require_store(snapshot, versions, *, complete):
    _require(len(PostgresStore.MIGRATIONS) == memory_profile.STORE_VERSION_COUNT)
    _require(all(type(v) is int for v in versions) and versions == list(range(len(versions)))
        and len(versions) <= memory_profile.STORE_VERSION_COUNT)
    if complete:
        _require(len(versions) == 4 and snapshot == memory_profile.store_expected(3))
    else:
        last = len(versions) - 1
        candidates = [memory_profile.store_expected(last), memory_profile.store_expected(min(last + 1, 3))]
        if not versions:
            candidates.append({})
        _require(snapshot in candidates)


def _require_runtime(connection, schema, snapshot, *, complete):
    native_names = set(_native_expected(9))
    _require(set(snapshot) <= native_names | memory_profile.STORE_TABLES | memory_profile.PUBLICATION_TABLES)
    native = {name: table for name, table in snapshot.items() if name in native_names}
    store = {name: table for name, table in snapshot.items() if name in memory_profile.STORE_TABLES}
    publication = {name: table for name, table in snapshot.items() if name in memory_profile.PUBLICATION_TABLES}
    # The explicit sequence is Saver -> Store -> publication. Do not adopt
    # unrelated later objects behind an unfinished earlier native setup.
    _require_native(native, _native_versions(connection, schema, native),
        complete=complete or bool(store) or bool(publication))
    _require_store(store, _store_versions(connection, schema, store), complete=complete or bool(publication))
    _require(publication == memory_profile.publication_expected() if complete or publication else True)
    memory = {**store, **publication}
    _require(memory_profile.read_index_options(connection, schema) == memory_profile.index_options_expected(memory))


def check_installed(connection, checkpoint_schema) -> None:
    """Read-only prerequisite check on an existing psycopg dict-row connection."""
    try:
        _schema_name(checkpoint_schema)
        _identity(connection)
        _require_jd(connection, _snapshot(connection, "public"), allow_empty=False)
        native = _snapshot(connection, checkpoint_schema)
        _require_runtime(connection, checkpoint_schema, native, complete=True)
        _require(not _other_objects(connection, {"public", checkpoint_schema}))
    except StorageSetupError:
        raise
    except Exception:
        raise StorageSetupError("storage_unavailable") from None


def check_empty_database(settings) -> None:
    """Only a pending configuration may claim an empty, existing database."""
    _settings(settings, "initialization_pending")
    try:
        with _connect(settings) as connection:
            _identity(connection, settings)
            namespaces = _namespaces(connection)
            _require(namespaces <= {"public"}, "database_not_empty")
            _require(not _snapshot(connection, "public"), "database_not_empty")
            _require(not _other_objects(connection, namespaces), "database_not_empty")
    except StorageSetupError:
        raise
    except Exception:
        raise StorageSetupError("storage_unavailable") from None


def _require_no_data(connection, schema, snapshot):
    for name in snapshot:
        if name in {"alembic_version", "checkpoint_migrations", "store_migrations"}:
            continue
        row = connection.execute(sql.SQL("SELECT 1 FROM {}.{} LIMIT 1").format(
            sql.Identifier(schema), sql.Identifier(name))).fetchone()
        _require(row is None, "initialization_recovery_required")


def setup_database(settings, lease) -> None:
    """Resume known native setup under the original installation's real lease."""
    _settings(settings, "initializing")
    _lease(lease, settings)
    engine = None
    try:
        with _connect(settings) as connection:
            _identity(connection, settings)
            _require(_namespaces(connection) <= {"public", settings.checkpoint_schema})
            _require(not _other_objects(connection, {"public", settings.checkpoint_schema}))
            jd = _snapshot(connection, "public")
            _require_jd(connection, jd, allow_empty=True)
            native = _snapshot(connection, settings.checkpoint_schema)
            _require_runtime(connection, settings.checkpoint_schema, native, complete=False)
            _require(settings.checkpoint_schema not in _namespaces(connection) or bool(jd))
            _require_no_data(connection, "public", jd)
            _require_no_data(connection, settings.checkpoint_schema, native)
            if not jd:
                _lease(lease, settings)
                engine = sa.create_engine(settings.database_url(), hide_parameters=True,
                    connect_args={"connect_timeout": 5, "options": "-csearch_path=public"})
                with engine.begin() as transaction:
                    _lease(lease, settings)
                    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
                    config.attributes["connection"] = transaction
                    command.upgrade(config, REVISION)
                _require_jd(connection, _snapshot(connection, "public"), allow_empty=False)
            _lease(lease, settings)
            if settings.checkpoint_schema not in _namespaces(connection):
                connection.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION CURRENT_USER").format(
                    sql.Identifier(settings.checkpoint_schema)))
            _lease(lease, settings)
            connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(settings.checkpoint_schema)))
            _lease(lease, settings)
            PostgresSaver(connection).setup()
            _lease(lease, settings)
            PostgresStore(connection).setup()
            _lease(lease, settings)
            if engine is None:
                engine = sa.create_engine(settings.database_url(), hide_parameters=True,
                    connect_args={"connect_timeout": 5, "options": "-csearch_path=public"})
            with engine.begin() as transaction:
                _lease(lease, settings)
                MemoryPublicationBase.metadata.create_all(transaction.execution_options(
                    schema_translate_map={None: settings.checkpoint_schema}))
            _lease(lease, settings)
            check_installed(connection, settings.checkpoint_schema)
    except StorageSetupError:
        raise
    except Exception:
        raise StorageSetupError("storage_unavailable") from None
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                pass
