"""Offline PostgreSQL DDL evidence; no database connection or executed constraints."""

from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path
import re

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import AddConstraint, CreateColumn, CreateIndex

from jd_relational.storage.schema import metadata


ROOT = Path(__file__).resolve().parents[1]
DIALECT = postgresql.dialect()
TABLES = {"jd_document", "jd_profile", "jd_collaborator", "jd_duty", "jd_task", "jd_task_detail",
          "jd_capability", "jd_task_capability", "jd_condition", "jd_source_link", "jd_head", "jd_revision", "jd_operation"}


def sql(value):
    return re.sub(r"\s+", " ", str(value)).strip().rstrip(";")


def checks(table):
    return {constraint.name: sql(constraint.sqltext) for constraint in metadata.tables[table].constraints
            if isinstance(constraint, CheckConstraint)}


def foreign_keys(table):
    return {constraint.name: constraint for constraint in metadata.tables[table].constraints
            if isinstance(constraint, ForeignKeyConstraint)}


def indexes(table):
    return {index.name: index for index in metadata.tables[table].indexes}


def test_exact_thirteen_business_tables_and_history_only_jsonb():
    assert set(metadata.tables) == TABLES
    assert "alembic_version" not in metadata.tables
    json_columns = {(table.name, column.name) for table in metadata.tables.values() for column in table.columns
                    if isinstance(column.type, postgresql.JSONB)}
    assert json_columns == {("jd_revision", "snapshot"), ("jd_operation", "receipt")}
    assert all(table.schema is None for table in metadata.tables.values())


@pytest.mark.parametrize("table,keys", [
    ("jd_document", ["id"]), ("jd_profile", ["document_id"]), ("jd_head", ["document_id"]),
    ("jd_collaborator", ["document_id", "collaborator_id"]), ("jd_duty", ["document_id", "duty_id"]),
    ("jd_task", ["document_id", "task_id"]), ("jd_task_detail", ["document_id", "detail_id"]),
    ("jd_capability", ["document_id", "capability_id"]),
    ("jd_task_capability", ["document_id", "task_id", "capability_id"]),
    ("jd_condition", ["document_id", "condition_id"]), ("jd_source_link", ["document_id", "source_link_id"]),
    ("jd_revision", ["document_id", "revision_id"]), ("jd_operation", ["document_id", "operation_id"]),
])
def test_scope_identity_is_in_primary_key(table, keys):
    assert [column.name for column in metadata.tables[table].primary_key.columns] == keys


@pytest.mark.parametrize("table,name,local,remote,ondelete", [
    ("jd_task", "fk_jd_task_duty", ["document_id", "duty_id"], ["jd_duty.document_id", "jd_duty.duty_id"], "RESTRICT"),
    ("jd_task_detail", "fk_jd_task_detail_task", ["document_id", "task_id"], ["jd_task.document_id", "jd_task.task_id"], "CASCADE"),
    ("jd_task_capability", "fk_jd_task_capability_task", ["document_id", "task_id"], ["jd_task.document_id", "jd_task.task_id"], "CASCADE"),
    ("jd_task_capability", "fk_jd_task_capability_capability", ["document_id", "capability_id"],
     ["jd_capability.document_id", "jd_capability.capability_id"], "RESTRICT"),
    ("jd_revision", "fk_jd_revision_parent", ["document_id", "parent_revision_id"],
     ["jd_revision.document_id", "jd_revision.revision_id"], "RESTRICT"),
    ("jd_head", "fk_jd_head_revision", ["document_id", "current_revision_id"],
     ["jd_revision.document_id", "jd_revision.revision_id"], "RESTRICT"),
    ("jd_operation", "fk_jd_operation_base", ["document_id", "base_revision_id"],
     ["jd_revision.document_id", "jd_revision.revision_id"], "RESTRICT"),
    ("jd_operation", "fk_jd_operation_result", ["document_id", "result_revision_id"],
     ["jd_revision.document_id", "jd_revision.revision_id"], "RESTRICT"),
    ("jd_source_link", "fk_jd_source_link_relation", ["document_id", "linked_task_id", "linked_capability_id"],
     ["jd_task_capability.document_id", "jd_task_capability.task_id", "jd_task_capability.capability_id"], "CASCADE"),
])
def test_foreign_keys_pair_document_with_identity_and_preserve_delete_policy(table, name, local, remote, ondelete):
    fk = foreign_keys(table)[name]
    assert list(fk.column_keys) == local
    assert [element.target_fullname for element in fk.elements] == remote
    assert fk.ondelete == ondelete
    assert fk.match in (None, "SIMPLE")  # MATCH FULL would reject legitimate nullable targets.


def test_source_targets_have_exactly_one_and_complete_relation_pair_checks():
    source = metadata.tables["jd_source_link"]
    constraints = checks(source.name)
    assert constraints["ck_jd_source_link_relation_pair"] == "(linked_task_id IS NULL) = (linked_capability_id IS NULL)"
    assert constraints["ck_jd_source_link_one_target"] == (
        "num_nonnulls(profile_field, collaborator_id, duty_id, task_id, detail_id, capability_id, condition_id, linked_task_id) = 1")
    assert "profile_field IN ('job_title', 'organization_unit', 'employee_name', 'reports_to', 'purpose')" in constraints["ck_jd_source_link_profile_field"]
    for target, parent, identity in [("collaborator", "jd_collaborator", "collaborator_id"),
            ("duty", "jd_duty", "duty_id"), ("task", "jd_task", "task_id"), ("detail", "jd_task_detail", "detail_id"),
            ("capability", "jd_capability", "capability_id"), ("condition", "jd_condition", "condition_id")]:
        fk = foreign_keys(source.name)[f"fk_jd_source_link_{target}"]
        assert list(fk.column_keys) == ["document_id", identity]
        assert [element.target_fullname for element in fk.elements] == [f"{parent}.document_id", f"{parent}.{identity}"]
        assert fk.ondelete == "CASCADE" and fk.match in (None, "SIMPLE")
        assert source.c[identity].nullable
    assert all(column.nullable for column in [source.c.linked_task_id, source.c.linked_capability_id])


def test_revision_has_one_initial_and_no_second_successor_of_any_parent():
    revision = metadata.tables["jd_revision"]
    unique = {tuple(column.name for column in constraint.columns) for constraint in revision.constraints
              if isinstance(constraint, UniqueConstraint)}
    assert ("document_id", "revision_number") in unique
    assert ("document_id", "parent_revision_id") in unique
    initial = indexes(revision.name)["uq_jd_revision_initial"]
    assert initial.unique and [column.name for column in initial.columns] == ["document_id"]
    assert sql(initial.dialect_options["postgresql"]["where"]) == "origin = 'initial'"
    assert checks(revision.name)["ck_jd_revision_initial_parent"] == "(origin = 'initial') = (parent_revision_id IS NULL)"
    assert checks(revision.name)["ck_jd_revision_format_version"] == "format_version = 3"
    assert checks(revision.name)["ck_jd_revision_engine_profile"] == "engine_profile = 'jd-relational-v1'"


def test_operation_only_stores_terminal_status_and_consistent_origin_run_and_result():
    constraints = checks("jd_operation")
    assert constraints["ck_jd_operation_origin_run"] == "(origin = 'ai') = (ai_run_id IS NOT NULL)"
    assert constraints["ck_jd_operation_origin"] == "origin IN ('manual', 'ai')"
    status = constraints["ck_jd_operation_status"]
    for name in ("committed", "no_change", "invalid_input", "target_missing", "stale_view", "relationship_conflict", "dependent_items", "save_failed"):
        assert f"'{name}'" in status
    for name in ("outcome_unknown", "operation_conflict", "busy", "archived", "prepared"):
        assert f"'{name}'" not in status
    assert "base_revision_id IS NOT NULL" in constraints["ck_jd_operation_result"]
    assert "result_revision_id <> base_revision_id" in constraints["ck_jd_operation_result"]
    assert "result_revision_id = base_revision_id" in constraints["ck_jd_operation_result"]
    assert "result_revision_id IS NULL" in constraints["ck_jd_operation_result"]
    producer = indexes("jd_operation")["uq_jd_operation_committed_result"]
    assert producer.unique
    assert [column.name for column in producer.columns] == ["document_id", "result_revision_id"]
    assert sql(producer.dialect_options["postgresql"]["where"]) == "status = 'committed'"


def test_read_indexes_include_partial_unassigned_sources_run_and_reverse_usage():
    assert [column.name for column in indexes("jd_task_capability")["ix_jd_task_capability_reverse"].columns] == ["document_id", "capability_id", "task_id"]
    assert sql(indexes("jd_task")["ix_jd_task_unassigned"].dialect_options["postgresql"]["where"]) == "duty_id IS NULL"
    assert sql(indexes("jd_operation")["ix_jd_operation_ai_run"].dialect_options["postgresql"]["where"]) == "ai_run_id IS NOT NULL"
    source_indexes = indexes("jd_source_link")
    assert len(source_indexes) == 8
    assert all(index.dialect_options["postgresql"]["where"] is not None for index in source_indexes.values())
    ddl = str(CreateIndex(indexes("jd_revision")["ix_jd_revision_number"]).compile(dialect=DIALECT))
    assert "revision_number DESC" in ddl


def test_nullable_partial_text_stays_in_app_while_database_guards_missing_items():
    for table, content in [("jd_duty", "scope_text"), ("jd_collaborator", "scope_text"), ("jd_task", "description"), ("jd_capability", "description")]:
        assert metadata.tables[table].c.name.nullable and metadata.tables[table].c[content].nullable
        assert f"name IS NOT NULL OR {content} IS NOT NULL" in checks(table).values()
    all_checks = " ".join(value for table in TABLES for value in checks(table).values()).lower()
    assert "trim(" not in all_checks  # Python whitespace/LF semantics are not silently replaced by SQL trim.
    for table in ("jd_collaborator", "jd_duty", "jd_task", "jd_task_detail", "jd_capability", "jd_task_capability", "jd_condition", "jd_source_link"):
        assert "position >= 0" in checks(table).values()


def test_initial_migration_is_frozen_and_compiles_same_ddl_as_metadata(monkeypatch):
    path = ROOT / "migrations" / "versions" / "0001_jd_relational_initial.py"
    source = path.read_text(encoding="utf-8")
    assert "jd_relational.storage" not in source and "create_all" not in source
    spec = spec_from_file_location("jd_initial_migration_test", path)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "20260913_0001" and migration.down_revision is None
    output = StringIO()
    context = MigrationContext.configure(dialect=DIALECT, opts={"as_sql": True, "output_buffer": output})
    captured = {}
    original_create = Operations.create_table

    def capture_create(operations, *args, **kwargs):
        table = original_create(operations, *args, **kwargs)
        captured[table.name] = table
        return table

    monkeypatch.setattr(Operations, "create_table", capture_create)
    with Operations.context(context):
        migration.upgrade()
    assert set(captured) == TABLES
    for name, frozen in captured.items():
        live = metadata.tables[name]
        assert [sql(CreateColumn(column).compile(dialect=DIALECT)) for column in frozen.columns] == [
            sql(CreateColumn(column).compile(dialect=DIALECT)) for column in live.columns]
        # Constraint declaration order is immaterial; names, expressions and FK actions are exact.
        assert {sql(AddConstraint(constraint, isolate_from_table=False).compile(dialect=DIALECT)) for constraint in frozen.constraints} == {
            sql(AddConstraint(constraint, isolate_from_table=False).compile(dialect=DIALECT)) for constraint in live.constraints}
    expected_indexes = {sql(CreateIndex(index).compile(dialect=DIALECT)) for table in metadata.tables.values() for index in table.indexes}
    actual_indexes = {sql(statement) for statement in output.getvalue().split(";") if sql(statement).startswith(("CREATE INDEX", "CREATE UNIQUE INDEX"))}
    assert actual_indexes == expected_indexes


def test_alembic_offline_upgrade_and_downgrade_need_no_connection(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline DDL must not open a database connection.")
    monkeypatch.setattr("sqlalchemy.create_engine", forbidden)
    monkeypatch.setattr("sqlalchemy.engine_from_config", forbidden)
    output = StringIO()
    config = Config(str(ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    ddl = output.getvalue()
    assert ddl.count("CREATE TABLE jd_") == 13
    assert "CREATE TABLE alembic_version" in ddl
    assert "BEGIN;" in ddl and "COMMIT;" in ddl
    assert "MATCH FULL" not in ddl
    output.seek(0)
    output.truncate()
    command.downgrade(config, "20260913_0001:base", sql=True)
    assert output.getvalue().count("DROP TABLE jd_") == 13


def test_online_migration_requires_explicit_connection_instead_of_loading_credentials():
    config = Config(str(ROOT / "alembic.ini"))
    with pytest.raises(RuntimeError, match="explicit PostgreSQL Connection"):
        command.upgrade(config, "head")
