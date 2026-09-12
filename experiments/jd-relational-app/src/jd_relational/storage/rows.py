"""Fixed mapping of the nine current-content tables, using the caller's transaction.

The service owns document/head locks, isolation, savepoints and commit. These
functions neither resolve revisions nor persist history, receipts or references.
Normal edits preserve component identities; history restore is a separate scope.
"""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from ..snapshots import domain_from_snapshot, empty_domain, snapshot_from_domain
from . import schema as db


class RowMappingError(ValueError):
    """The complete candidate cannot be mapped to the expected current rows."""


# This is a closed JD projection, not a configurable repository or write engine.
_GROUPS = {
    "collaborators": (db.jd_collaborator, ("collaborator_id",)),
    "duties": (db.jd_duty, ("duty_id",)),
    "tasks": (db.jd_task, ("task_id",)),
    "details": (db.jd_task_detail, ("detail_id",)),
    "capabilities": (db.jd_capability, ("capability_id",)),
    "conditions": (db.jd_condition, ("condition_id",)),
    "task_capabilities": (db.jd_task_capability, ("task_id", "capability_id")),
    "source_links": (db.jd_source_link, ("source_link_id",)),
}
_SOURCE_TARGETS = ("profile_field", "collaborator_id", "duty_id", "task_id", "detail_id",
                   "capability_id", "condition_id", "linked_task_id", "linked_capability_id")
_IMMUTABLE = {
    "details": ("task_id", "kind"),
    "capabilities": ("kind",),
    "conditions": ("kind",),
    "source_links": (*_SOURCE_TARGETS, "source_ref"),
}
_PARENTS = ("collaborators", "duties", "capabilities", "conditions")


def _domain_row(row) -> dict:
    return {name: str(value) if isinstance(value, UUID) else value
            for name, value in row.items() if name != "document_id"}


def read_domain(connection: Connection, document_id: str, revision_id: str) -> dict:
    """Read the nine current groups under the caller's consistent-read boundary.

    revision_id is the caller's resolved head, not a request to read old content.
    UUIDs become canonical strings, while exact text and nulls are preserved.
    """
    value = empty_domain(document_id, revision_id)
    profile = connection.execute(sa.select(db.jd_profile).where(
        db.jd_profile.c.document_id == document_id)).mappings().one_or_none()
    if profile is None:
        raise RowMappingError("current_profile_missing")
    value["profile"] = _domain_row(profile)
    for name, (table, identities) in _GROUPS.items():
        rows = [_domain_row(row) for row in connection.execute(
            sa.select(table).where(table.c.document_id == document_id)
            .order_by(table.c.position, *(table.c[key] for key in identities))).mappings()]
        value[name] = rows if name in ("task_capabilities", "source_links") else {
            row[identities[0]]: row for row in rows}
    return domain_from_snapshot(snapshot_from_domain(value), revision_id)


def _indexed(value: dict, name: str) -> dict:
    rows = value[name]
    if isinstance(rows, dict):
        return rows
    identities = _GROUPS[name][1]
    return {tuple(row[key] for key in identities): row for row in rows}


def _sql_values(table: sa.Table, row: dict) -> dict:
    return {key: UUID(value) if value is not None and isinstance(table.c[key].type, sa.Uuid) else value
            for key, value in row.items()}


def _where(table: sa.Table, document_id: str, row: dict):
    return sa.and_(table.c.document_id == document_id, *(
        table.c[column.name] == _sql_values(table, {column.name: row[column.name]})[column.name]
        for column in table.primary_key.columns if column.name != "document_id"))


def _execute_one(connection: Connection, statement) -> None:
    result = connection.execute(statement)
    # SQLAlchemy only preserves rowcount by default for UPDATE / DELETE.
    # These plain one-row INSERTs rely on their constraints, with no conflict
    # suppression; a successful INSERT does not have to report rowcount == 1.
    if not statement.is_insert and result.rowcount != 1:
        raise RowMappingError("current_row_count_mismatch")


def write_candidate(connection: Connection, before: dict, after: dict) -> None:
    """Incrementally apply one complete normal-edit candidate; never commit it.

    Both values must use the same document and base revision. The caller must
    already hold the document/head lock and a transaction. Any error requires
    caller rollback; no partial-success receipt is produced here.
    """
    old_snapshot, new_snapshot = snapshot_from_domain(before), snapshot_from_domain(after)
    if (before["document_id"], before["revision"]) != (after["document_id"], after["revision"]):
        raise RowMappingError("candidate_scope_mismatch")
    old = domain_from_snapshot(old_snapshot, before["revision"])
    new = domain_from_snapshot(new_snapshot, after["revision"])
    old_groups = {name: _indexed(old, name) for name in _GROUPS}
    new_groups = {name: _indexed(new, name) for name in _GROUPS}
    for name, fields in _IMMUTABLE.items():
        for key in old_groups[name].keys() & new_groups[name].keys():
            if any(old_groups[name][key][field] != new_groups[name][key][field] for field in fields):
                raise RowMappingError("normal_edit_identity_changed")
    if not connection.in_transaction():
        raise RowMappingError("caller_transaction_required")
    document_id = before["document_id"]

    def remove(name):
        table = _GROUPS[name][0]
        for key in sorted(old_groups[name].keys() - new_groups[name].keys()):
            _execute_one(connection, table.delete().where(_where(table, document_id, old_groups[name][key])))

    def add_or_update(name):
        table = _GROUPS[name][0]
        old_rows, new_rows = old_groups[name], new_groups[name]
        primary = set(table.primary_key.columns.keys())
        for key in sorted(new_rows):
            row = new_rows[key]
            if key not in old_rows:
                _execute_one(connection, table.insert().values(document_id=document_id, **_sql_values(table, row)))
            elif row != old_rows[key]:
                # Apply the complete final row in one statement, including nulls.
                # Unchanged rows receive no UPDATE and retain their identities.
                values = _sql_values(table, {field: value for field, value in row.items() if field not in primary})
                _execute_one(connection, table.update().where(_where(table, document_id, row)).values(**values))

    # Remove explicitly absent dependants before any possible parent deletion.
    remove("source_links")
    remove("task_capabilities")
    if old["profile"] != new["profile"]:
        _execute_one(connection, db.jd_profile.update().where(db.jd_profile.c.document_id == document_id)
                     .values(**new["profile"]))
    for name in _PARENTS:
        add_or_update(name)
    # D01 and cross-duty moves must update surviving tasks before old duties go.
    add_or_update("tasks")
    remove("details")
    remove("tasks")
    for name in _PARENTS:
        remove(name)
    for name in ("details", "task_capabilities", "source_links"):
        add_or_update(name)
