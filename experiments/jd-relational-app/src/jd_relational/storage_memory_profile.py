"""Bounded PG18.6 profile: PostgresStore 3.1.2 and adopted Memory core 0.1.0.

This is a compatibility check, not a migration or Store implementation. DDL is
executed only by official PostgresStore.setup and the adopted publication ORM.
No vectors, embedding indexes or TTL sweeper are configured by this App.
"""
STORE_VERSION_COUNT = 4
STORE_TABLES = {"store_migrations", "store"}
PUBLICATION_TABLES = {"q019_document_memory_head", "q019_memory_publication_receipt"}


def _table(name, columns, primary, *, defaults=None):
    return {"columns": columns, "defaults": defaults or {},
        "constraints": {name + "_pkey": ("p", primary)},
        "indexes": {name + "_pkey": (primary, True, None)}}


def store_expected(version):
    # Official setup creates this table before migration 0, outside MIGRATIONS.
    result = {"store_migrations": _table("store_migrations", {"v": ("integer", True)}, ("v",))}
    if version < 0:
        return result
    result["store"] = _table("store", {"prefix": ("text", True), "key": ("text", True),
        "value": ("jsonb", True), "created_at": ("timestamp with time zone", False),
        "updated_at": ("timestamp with time zone", False)}, ("prefix", "key"),
        defaults={"created_at": "CURRENT_TIMESTAMP", "updated_at": "CURRENT_TIMESTAMP"})
    if version >= 1:
        result["store"]["indexes"]["store_prefix_idx"] = (("prefix",), False, None)
    if version >= 2:
        result["store"]["columns"].update({"expires_at": ("timestamp with time zone", False),
            "ttl_minutes": ("integer", False)})
    if version >= 3:
        result["store"]["indexes"]["idx_store_expires_at"] = (("expires_at",), False, "(expires_at IS NOT NULL)")
    return result


def publication_expected():
    text, integer = ("character varying", True), ("integer", True)
    return {
        "q019_document_memory_head": _table("q019_document_memory_head", {
            "document_id": text, "revision": integer, "memory_version": text,
            "processed_source": ("text", False), "last_operation_id": text}, ("document_id",)),
        "q019_memory_publication_receipt": _table("q019_memory_publication_receipt", {
            "document_id": text, "operation_id": text, "request_digest": ("character varying(64)", True),
            "base_revision": integer, "result_revision": integer, "memory_version": text,
            "processed_source": ("text", False), "kind": text, "repair_sources": ("json", True)},
            ("document_id", "operation_id")),
    }


def index_options_expected(snapshot):
    # A same-name btree on prefix using text_ops is not the official prefix
    # pattern index. All of these pinned indexes are ASC/default null ordering.
    options = {"store_migrations_pkey": ("int4_ops",), "store_pkey": ("text_ops", "text_ops"),
        "store_prefix_idx": ("text_pattern_ops",), "idx_store_expires_at": ("timestamptz_ops",),
        "q019_document_memory_head_pkey": ("text_ops",),
        "q019_memory_publication_receipt_pkey": ("text_ops", "text_ops")}
    return {name: (tuple(("pg_catalog", op) for op in options[name]), (0,) * len(options[name]))
        for table in snapshot.values() for name in table["indexes"]}


def read_index_options(connection, schema):
    rows = connection.execute("SELECT x.relname AS name, "
        "ARRAY(SELECT n.nspname || '.' || o.opcname FROM unnest(i.indclass::oid[]) "
        "WITH ORDINALITY k(id,ord) JOIN pg_catalog.pg_opclass o ON o.oid=k.id "
        "JOIN pg_catalog.pg_namespace n ON n.oid=o.opcnamespace ORDER BY k.ord) AS classes, "
        "i.indoption::smallint[] AS options FROM pg_catalog.pg_index i "
        "JOIN pg_catalog.pg_class x ON x.oid=i.indexrelid "
        "JOIN pg_catalog.pg_class t ON t.oid=i.indrelid "
        "JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace "
        "WHERE n.nspname=%s AND t.relname=ANY(%s)",
        (schema, sorted(STORE_TABLES | PUBLICATION_TABLES))).fetchall()
    return {row["name"]: (tuple(tuple(name.split(".", 1)) for name in row["classes"]),
        tuple(row["options"])) for row in rows}
