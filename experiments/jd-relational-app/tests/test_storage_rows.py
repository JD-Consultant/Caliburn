"""Fixed current-row mapper tests; PostgreSQL cases require explicit synthetic-DB opt-in."""

from copy import deepcopy
from contextlib import contextmanager
import os
from uuid import uuid4

import pytest
import sqlalchemy as sa

from jd_relational.storage.rows import RowMappingError, read_domain, write_candidate
from jd_relational.snapshots import empty_domain, snapshot_from_domain
from jd_relational.domain import CommandContext, Ref, Source, build_candidate
from jd_relational.storage import schema as db
from test_storage_postgres import engine, conn, document


pg = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
                        reason="explicit isolated PostgreSQL test opt-in required")


def full_domain(doc, revision):
    ids = {name: str(uuid4()) for name in ("co", "d1", "d2", "t1", "t2", "out", "req", "k", "s", "condition",
                                          "source_task", "source_detail", "source_relation", "source_condition",
                                          "source_profile", "source_collaborator", "source_duty", "source_capability")}
    value = empty_domain(doc, revision)
    value["profile"].update(job_title="工程師", organization_unit="技術組", employee_name=None,
                            reports_to="組長", purpose="保存實際工作😀\n確切範圍")
    value["collaborators"][ids["co"]] = {"collaborator_id": ids["co"], "name": "服務窗口", "scope_text": "對外承諾", "position": 0}
    for name, position in (("d1", 0), ("d2", 1)):
        value["duties"][ids[name]] = {"duty_id": ids[name], "name": name, "scope_text": "依約定範圍", "position": position}
    for task, duty in (("t1", "d1"), ("t2", "d2")):
        value["tasks"][ids[task]] = {"task_id": ids[task], "duty_id": ids[duty], "name": task,
                                    "description": "處理本人範圍內工作", "position": 0}
    for name, kind in (("out", "outcome"), ("req", "requirement")):
        value["details"][ids[name]] = {"detail_id": ids[name], "task_id": ids["t1"], "kind": kind, "text": name, "position": 0}
    for name, kind in (("k", "knowledge"), ("s", "skill")):
        value["capabilities"][ids[name]] = {"capability_id": ids[name], "kind": kind, "name": name, "description": None, "position": 0}
    value["conditions"][ids["condition"]] = {"condition_id": ids["condition"], "kind": "shared_authority", "text": "依授權處理", "position": 0}
    value["task_capabilities"] = [{"task_id": ids["t1"], "capability_id": ids["k"], "position": 0},
                                  {"task_id": ids["t1"], "capability_id": ids["s"], "position": 1},
                                  {"task_id": ids["t2"], "capability_id": ids["s"], "position": 0}]
    targets = {"source_task": {"task_id": ids["t1"]}, "source_detail": {"detail_id": ids["out"]},
               "source_relation": {"linked_task_id": ids["t1"], "linked_capability_id": ids["s"]},
               "source_condition": {"condition_id": ids["condition"]}, "source_profile": {"profile_field": "purpose"},
               "source_collaborator": {"collaborator_id": ids["co"]}, "source_duty": {"duty_id": ids["d1"]},
               "source_capability": {"capability_id": ids["k"]}}
    for name, target in targets.items():
        value["source_links"].append({"source_link_id": ids[name], "source_ref": "synthetic:qa1", "basis_digest": "a" * 64, "position": 0,
            **dict.fromkeys(("profile_field", "collaborator_id", "duty_id", "task_id", "detail_id", "capability_id",
                             "condition_id", "linked_task_id", "linked_capability_id")), **target})
    return value, ids


class NoSQL:
    def in_transaction(self):
        return True

    def execute(self, *args, **kwargs):
        pytest.fail("Invalid or unchanged candidates must not emit SQL.")


@contextmanager
def statements(connection):
    calls = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        calls.append((statement, parameters, executemany))

    sa.event.listen(connection, "before_cursor_execute", capture)
    try:
        yield calls
    finally:
        sa.event.remove(connection, "before_cursor_execute", capture)


def test_no_change_candidate_emits_no_sql():
    before, _ = full_domain(str(uuid4()), str(uuid4()))
    write_candidate(NoSQL(), before, deepcopy(before))


def test_writer_requires_a_caller_owned_transaction_before_sql():
    class OutsideTransaction(NoSQL):
        def in_transaction(self):
            return False

    before, _ = full_domain(str(uuid4()), str(uuid4()))
    with pytest.raises(RowMappingError, match="caller_transaction_required"):
        write_candidate(OutsideTransaction(), before, deepcopy(before))


@pytest.mark.parametrize("change", ["document", "revision", "dict_key", "row_document", "unknown_field"])
def test_scope_shape_and_identity_are_rejected_before_sql(change):
    before, ids = full_domain(str(uuid4()), str(uuid4()))
    after = deepcopy(before)
    if change == "document":
        after["document_id"] = str(uuid4())
    elif change == "revision":
        after["revision"] = str(uuid4())
    elif change == "dict_key":
        after["tasks"][str(uuid4())] = after["tasks"].pop(ids["t1"])
    elif change == "row_document":
        after["tasks"][ids["t1"]]["document_id"] = "another-document"
    else:
        after["tasks"][ids["t1"]]["invented"] = "not a storage field"
    with pytest.raises(ValueError):
        write_candidate(NoSQL(), before, after)


@pytest.mark.parametrize("change", ["detail_owner", "detail_kind", "capability_kind", "condition_kind", "source_target", "source_ref"])
def test_normal_edit_cannot_retarget_existing_component_identity(change):
    before, ids = full_domain(str(uuid4()), str(uuid4()))
    after = deepcopy(before)
    if change == "detail_owner":
        after["details"][ids["out"]]["task_id"] = ids["t2"]
    elif change == "detail_kind":
        after["details"][ids["out"]]["kind"] = "requirement"
    elif change == "capability_kind":
        after["capabilities"][ids["k"]]["kind"] = "skill"
    elif change == "condition_kind":
        after["conditions"][ids["condition"]]["kind"] = "schedule_travel"
    elif change == "source_target":
        after["source_links"][0]["task_id"] = ids["t2"]
    else:
        after["source_links"][0]["source_ref"] = "synthetic:qa2"
    with pytest.raises(RowMappingError):
        write_candidate(NoSQL(), before, after)


@pg
def test_roundtrip_all_nine_current_groups_and_uuid_strings(conn):
    doc, revision = document(conn)
    before = read_domain(conn, doc, str(revision))
    after, ids = full_domain(doc, str(revision))
    original = deepcopy(after)
    write_candidate(conn, before, after)
    with statements(conn) as calls:
        result = read_domain(conn, doc, str(revision))
    assert snapshot_from_domain(result) == snapshot_from_domain(after)
    assert result["tasks"][ids["t1"]]["duty_id"] == ids["d1"]
    assert all(isinstance(row["source_link_id"], str) for row in result["source_links"])
    assert len(calls) == 9
    assert all("WHERE" in statement and "document_id" in statement for statement, _, _ in calls)
    assert all(doc in parameters.values() and not many for _, parameters, many in calls)
    assert after == original and conn.in_transaction()


@pg
def test_one_changed_row_only_updates_it_and_preserves_same_ids_in_another_document(conn):
    doc, revision = document(conn)
    other_doc, other_revision = document(conn)
    after, ids = full_domain(doc, str(revision))
    write_candidate(conn, read_domain(conn, doc, str(revision)), after)
    other = deepcopy(after)
    other.update(document_id=other_doc, revision=str(other_revision))
    write_candidate(conn, read_domain(conn, other_doc, str(other_revision)), other)
    before = read_domain(conn, doc, str(revision))
    changed = deepcopy(before)
    changed["tasks"][ids["t1"]]["description"] = "更正技術診斷範圍"
    with statements(conn) as calls:
        write_candidate(conn, before, changed)
    assert len(calls) == 1 and calls[0][0].startswith("UPDATE jd_task SET")
    assert "document_id" in calls[0][0].split("WHERE")[1]
    assert doc in calls[0][1].values() and not calls[0][2]
    assert snapshot_from_domain(read_domain(conn, other_doc, str(other_revision))) == snapshot_from_domain(other)
    assert snapshot_from_domain(read_domain(conn, doc, str(revision))) == snapshot_from_domain(changed)


def context_for(value, ids):
    doc, rev = value["document_id"], value["revision"]
    return CommandContext(doc, rev, {
        "duty": Ref(doc, rev, "duty", ids["d1"]), "task": Ref(doc, rev, "task", ids["t1"]),
        "dest": Ref(doc, rev, "container", ids["d2"], child_kind="task"),
        "body": Ref(doc, rev, "task", ids["t1"], field="description"),
        "knowledge": Ref(doc, rev, "capability", ids["k"]),
    }, {"synthetic:qa1": Source(doc)}, lambda: str(uuid4()))


@pg
@pytest.mark.parametrize("operation", ["duty_delete", "move", "unlink_delete", "task_delete"])
def test_domain_structural_candidate_applies_in_foreign_key_order(conn, operation):
    doc, revision = document(conn)
    initial, ids = full_domain(doc, str(revision))
    write_candidate(conn, read_domain(conn, doc, str(revision)), initial)
    before = read_domain(conn, doc, str(revision))
    context = context_for(before, ids)
    if operation == "duty_delete":
        after = build_candidate(before, {"tool": "jd_delete_item", "arguments": {"target_ref": "duty", "content_changes": [
            {"kind": "add_task_detail", "task_ref": "task", "detail_kind": "requirement", "after_ref": None,
             "text": "保留維修前安全隔離", "basis_refs": []}]}}, context)
    elif operation == "move":
        after = build_candidate(before, {"tool": "jd_move_item", "arguments": {"target_ref": "task",
            "destination_container_ref": "dest", "after_ref": None, "content_changes": [
                {"kind": "set_field", "target_field_ref": "body", "text": "仍限本人約定範圍", "basis_refs": []}]}}, context)
    elif operation == "unlink_delete":
        after = build_candidate(before, {"tool": "jd_set_task_capability", "arguments": {"task_ref": "task",
            "capability_ref": "knowledge", "mode": "unlink", "basis_refs": []}}, context)
        after = build_candidate(after, {"tool": "jd_delete_item", "arguments": {"target_ref": "knowledge", "content_changes": []}}, context)
    else:
        after = build_candidate(before, {"tool": "jd_delete_item", "arguments": {"target_ref": "task", "content_changes": []}}, context)
    write_candidate(conn, before, after)
    assert snapshot_from_domain(read_domain(conn, doc, str(revision))) == snapshot_from_domain(after)
    if operation == "task_delete":
        assert ids["t1"] not in after["tasks"] and not after["details"]
        assert set(after["capabilities"]) == {ids["k"], ids["s"]}
        assert after["task_capabilities"] == [{"task_id": ids["t2"], "capability_id": ids["s"], "position": 0}]
    else:
        assert ids["t1"] in after["tasks"]


@pg
def test_complete_final_rows_update_all_groups_and_nullable_text_in_one_statement_each(conn):
    doc, revision = document(conn)
    initial, ids = full_domain(doc, str(revision))
    write_candidate(conn, read_domain(conn, doc, str(revision)), initial)
    before = read_domain(conn, doc, str(revision))
    after = deepcopy(before)
    after["profile"]["job_title"] = None
    for group, item, body in (("collaborators", "co", "scope_text"), ("duties", "d1", "scope_text"),
                               ("tasks", "t1", "description"), ("capabilities", "k", "description")):
        after[group][ids[item]].update(name=None, **{body: "保留正文😀\n不要求先保留名稱"})
    after["details"][ids["out"]]["text"] = "交付可驗收的成果"
    after["conditions"][ids["condition"]]["text"] = "依明確授權處理"
    after["task_capabilities"][0]["position"] = 20
    after["source_links"][0]["basis_digest"] = "c" * 64
    with statements(conn) as calls:
        write_candidate(conn, before, after)
    assert len(calls) == 9
    assert all(statement.startswith("UPDATE ") and "document_id" in statement.split("WHERE")[1]
               and doc in parameters.values() and not many for statement, parameters, many in calls)
    assert snapshot_from_domain(read_domain(conn, doc, str(revision))) == snapshot_from_domain(after)


@pg
def test_removal_of_every_collection_preserves_same_ids_in_another_document(conn):
    doc, revision = document(conn)
    other_doc, other_revision = document(conn)
    initial, _ = full_domain(doc, str(revision))
    write_candidate(conn, read_domain(conn, doc, str(revision)), initial)
    other = deepcopy(initial)
    other.update(document_id=other_doc, revision=str(other_revision))
    write_candidate(conn, read_domain(conn, other_doc, str(other_revision)), other)
    before = read_domain(conn, doc, str(revision))
    after = empty_domain(doc, str(revision))
    with statements(conn) as calls:
        write_candidate(conn, before, after)
    assert any(statement.startswith("DELETE ") for statement, _, _ in calls)
    assert all("document_id" in statement.split("WHERE")[1] and doc in parameters.values() and not many
               for statement, parameters, many in calls)
    assert snapshot_from_domain(read_domain(conn, doc, str(revision))) == snapshot_from_domain(after)
    assert snapshot_from_domain(read_domain(conn, other_doc, str(other_revision))) == snapshot_from_domain(other)


@pg
def test_source_basis_refresh_does_not_drop_unmentioned_links(conn):
    doc, revision = document(conn)
    initial, _ = full_domain(doc, str(revision))
    write_candidate(conn, read_domain(conn, doc, str(revision)), initial)
    before = read_domain(conn, doc, str(revision))
    after = deepcopy(before)
    after["source_links"][0]["basis_digest"] = "b" * 64
    with statements(conn) as calls:
        write_candidate(conn, before, after)
    assert len(calls) == 1 and calls[0][0].startswith("UPDATE jd_source_link SET")
    assert snapshot_from_domain(read_domain(conn, doc, str(revision))) == snapshot_from_domain(after)


@pg
def test_late_failure_rolls_back_only_when_caller_rolls_back_savepoint(conn):
    doc, revision = document(conn)
    before = read_domain(conn, doc, str(revision))
    after, _ = full_domain(doc, str(revision))

    class InjectedFailure(RuntimeError):
        pass

    def fail_at_sources(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO jd_source_link"):
            raise InjectedFailure("Synthetic failure after parent and child writes.")

    sa.event.listen(conn, "before_cursor_execute", fail_at_sources)
    try:
        with pytest.raises(InjectedFailure):
            with conn.begin_nested():
                write_candidate(conn, before, after)
    finally:
        sa.event.remove(conn, "before_cursor_execute", fail_at_sources)
    assert conn.in_transaction()
    assert snapshot_from_domain(read_domain(conn, doc, str(revision))) == snapshot_from_domain(before)


@pg
def test_read_missing_profile_does_not_invent_an_empty_document(conn):
    with pytest.raises(RowMappingError):
        read_domain(conn, str(uuid4()), str(uuid4()))
