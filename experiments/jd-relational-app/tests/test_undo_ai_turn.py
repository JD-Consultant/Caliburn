"""Undoing one AI turn's JD changes, on real PostgreSQL.

One press takes back everything that turn wrote to the JD, not just its last
edit. The employee never supplies where to go back to: the server derives it
from the turn's own committed operations and refuses whenever that scope
cannot be proven, rather than guessing a range from timestamps or origin.

Only the JD moves. The turn, its operations and receipts, the conversation and
Memory all stay exactly as they were, and undoing is itself a new revision.
"""
import os
from uuid import uuid4

import pytest
import sqlalchemy as sa

from jd_relational.memory_context import build_consultant_tools
from jd_relational.snapshots import snapshot_digest
from jd_relational.storage import schema as db
from jd_relational.transport import MODELS, TransportError, manual_command, model_command

from test_storage_postgres import engine  # noqa: F401
from test_storage_service import (  # noqa: F401
    FakeAuthority, change, current, insert_item, intent_for, store, task_args,
)


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")


def turn(store, current, run_id, *edits):
    """One AI turn writing several JD changes, as a real turn would."""
    for tool, args in edits:
        current, _, _ = change(store, current, tool, args, origin="ai", ai_run_id=run_id)
    return current


def undo(store, current, run_id, expected_result, **options):
    intent = intent_for(store, current, "undo_ai_turn",
                        {"ai_run_id": run_id,
                         "expected_result_revision_id": str(expected_result)}, **options)
    return intent, store.execute(intent)


def operations(engine, document_id):
    with engine.connect() as connection:
        return connection.execute(sa.select(
            db.jd_operation.c.operation_id, db.jd_operation.c.status,
            db.jd_operation.c.ai_run_id, db.jd_operation.c.result_revision_id).where(
            db.jd_operation.c.document_id == document_id)).mappings().all()


def test_the_consultant_is_never_given_undoing_as_a_tool():
    """Taking back a turn is the employee's judgement, not the turn's own."""
    assert "undo_ai_turn" not in MODELS
    assert "undo_ai_turn" not in {tool.name for tool in build_consultant_tools()}
    with pytest.raises(TransportError, match="^unknown_tool$"):
        model_command("undo_ai_turn", {"ai_run_id": str(uuid4()),
                                       "expected_result_revision_id": str(uuid4())})
    assert manual_command({"tool": "undo_ai_turn", "arguments": {
        "ai_run_id": str(uuid4()), "expected_result_revision_id": str(uuid4())}})["tool"] == "undo_ai_turn"


def test_one_press_takes_back_the_whole_turn_and_keeps_its_record(store, current, engine):
    """A turn that created a task and then added a duty goes back together."""
    run, before = str(uuid4()), current
    after = turn(store, current, run,
                 ("jd_create_task", task_args()),
                 ("jd_insert_item", insert_item("duty", name="同輪新增的職責", scope_text=None)))
    assert after.domain["tasks"] and after.domain["duties"]

    _, result = undo(store, after, run, after.revision_id)
    assert result.confirmed and result.status == "committed"
    undone = store.read_current(current.document_id)
    assert snapshot_digest(undone.snapshot) == snapshot_digest(before.snapshot)
    assert not undone.domain["tasks"] and not undone.domain["duties"]
    assert undone.revision_number == after.revision_number + 1, "undoing is a new revision"
    # The turn's own record is untouched: still two committed AI operations.
    saved = [row for row in operations(engine, current.document_id) if row["ai_run_id"] == run]
    assert len(saved) == 2 and {row["status"] for row in saved} == {"committed"}


def test_a_turn_that_wrote_nothing_to_the_jd_has_nothing_to_take_back(store, current):
    """A pure interview turn is not an undoable effect."""
    _, result = undo(store, current, str(uuid4()), current.revision_id)
    assert result.confirmed and result.status == "target_missing"
    assert store.read_current(current.document_id).revision_id == current.revision_id


def test_a_later_edit_by_anyone_else_makes_the_shortcut_unavailable(store, current):
    """Undoing must never quietly discard work done after the turn."""
    run = str(uuid4())
    after = turn(store, current, run, ("jd_create_task", task_args()))
    later, _, _ = change(store, after, "jd_insert_item",
                         insert_item("duty", name="之後的人工工作", scope_text=None))
    _, result = undo(store, later, run, after.revision_id)
    assert result.confirmed and result.status == "stale_view"
    assert store.read_current(current.document_id).revision_id == later.revision_id


def test_a_turn_interrupted_by_another_edit_is_refused_rather_than_guessed(store, current):
    """Interleaved history cannot be undone as one range, so it is not offered."""
    run = str(uuid4())
    started = turn(store, current, run, ("jd_create_task", task_args()))
    interleaved, _, _ = change(store, started, "jd_insert_item",
                               insert_item("duty", name="中途插入的人工工作", scope_text=None))
    finished = turn(store, interleaved, run,
                    ("jd_insert_item", insert_item("skill", name="同輪稍後的技能", description=None)))
    _, result = undo(store, finished, run, finished.revision_id)
    assert result.confirmed and result.status == "stale_view"
    assert store.read_current(current.document_id).revision_id == finished.revision_id


def test_an_expected_result_that_is_not_the_turns_own_end_is_refused(store, current):
    """The App's view of where the turn ended has to match the record."""
    run = str(uuid4())
    after = turn(store, current, run, ("jd_create_task", task_args()))
    _, result = undo(store, after, run, current.revision_id)
    assert result.confirmed and result.status == "stale_view"
    assert store.read_current(current.document_id).revision_id == after.revision_id


def test_pressing_undo_twice_answers_from_the_first_operation(store, current, engine):
    """A lost reply is answered from the record, and never undoes twice."""
    run = str(uuid4())
    after = turn(store, current, run, ("jd_create_task", task_args()))
    key = uuid4()
    intent, first = undo(store, after, run, after.revision_id, operation_id=key)
    again = store.execute(intent)
    assert again == first and again.status == "committed"
    undone = store.read_current(current.document_id)
    assert undone.revision_id == first.receipt.result_revision_id
    # A fresh key cannot undo the same turn again: its end is no longer current.
    _, third = undo(store, undone, run, after.revision_id)
    assert third.confirmed and third.status == "stale_view"
    assert store.read_current(current.document_id).revision_id == undone.revision_id


def test_a_turn_whose_writes_cancelled_out_reports_no_change(store, current):
    """Nothing net to take back is a real answer, not a fabricated undo."""
    run = str(uuid4())
    after = turn(store, current, run,
                 ("jd_insert_item", insert_item("duty", name="先新增", scope_text=None)))
    duty = next(iter(after.domain["duties"]))
    removed = turn(store, after, run,
                   ("jd_delete_item", {"target_ref": f"duty:{duty}", "content_changes": []}))
    _, result = undo(store, removed, run, removed.revision_id)
    assert result.confirmed and result.status == "no_change"
    assert store.read_current(current.document_id).revision_id == removed.revision_id
