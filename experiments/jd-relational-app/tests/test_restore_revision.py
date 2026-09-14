"""Restoring a whole JD to one of its own saved revisions, on real PostgreSQL.

Restoring is a new edit, not a rewind: it writes a new revision whose content
is the historical one, and everything that happened in between stays in
history. Item identities come back as themselves, and source links come back
as they were recorded rather than being re-approved.

It is a manual business operation. The consultant is never given it as a tool,
because taking a whole document back is the employee's decision, not a model's.
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


def restore(store, current, target_revision_id, **options):
    intent = intent_for(store, current, "restore_revision",
                        {"target_revision_id": str(target_revision_id)}, **options)
    return intent, store.execute(intent)


def revisions(engine, document_id):
    with engine.connect() as connection:
        return connection.execute(sa.select(db.jd_revision.c.revision_id).where(
            db.jd_revision.c.document_id == document_id)).scalars().all()


def test_the_consultant_is_never_given_restoring_as_a_tool():
    """Taking a whole document back is the employee's decision."""
    assert "restore_revision" not in MODELS
    assert "restore_revision" not in {tool.name for tool in build_consultant_tools()}
    with pytest.raises(TransportError, match="^unknown_tool$"):
        model_command("restore_revision", {"target_revision_id": str(uuid4())})
    # The manual entry accepts it, because that is who may ask for it.
    assert manual_command({"tool": "restore_revision",
                           "arguments": {"target_revision_id": str(uuid4())}})["tool"] == "restore_revision"


def test_restoring_writes_a_new_revision_and_keeps_what_happened_since(store, current):
    """A task added after the target is gone from current but stays in history."""
    after_task, _, _ = change(store, current, "jd_create_task", task_args())
    target = after_task.revision_id
    with_extra, _, _ = change(store, after_task, "jd_insert_item", insert_item("duty", name="後來新增的職責", scope_text=None))
    assert with_extra.domain["duties"], "the later work really exists first"

    _, result = restore(store, with_extra, target)
    assert result.confirmed and result.status == "committed"
    restored = store.read_current(current.document_id)
    assert restored.revision_id not in {target, with_extra.revision_id}, "restoring is a new revision"
    assert restored.revision_number == with_extra.revision_number + 1
    assert snapshot_digest(restored.snapshot) == snapshot_digest(after_task.snapshot)
    assert not restored.domain["duties"] and restored.domain["tasks"]
    # Identity, not a copy: the restored task is the task it was.
    assert set(restored.domain["tasks"]) == set(after_task.domain["tasks"])
    assert set(revisions(store.engine, current.document_id)) >= {
        target, with_extra.revision_id, restored.revision_id}


def test_restoring_to_content_that_is_already_current_changes_nothing(store, current):
    """Nothing to undo is a real answer, not an empty revision."""
    after_task, _, _ = change(store, current, "jd_create_task", task_args())
    _, result = restore(store, after_task, after_task.revision_id)
    assert result.confirmed and result.status == "no_change"
    assert store.read_current(current.document_id).revision_id == after_task.revision_id
    assert len(revisions(store.engine, current.document_id)) == 2


def test_a_restore_prepared_against_an_older_head_is_refused(store, current):
    """Consent given to one comparison is not consent to a different one."""
    after_task, _, _ = change(store, current, "jd_create_task", task_args())
    stale_view = after_task
    moved, _, _ = change(store, after_task, "jd_insert_item", insert_item("duty", name="他人後來的工作", scope_text=None))
    _, result = restore(store, stale_view, current.revision_id)
    assert result.confirmed and result.status == "stale_view"
    assert store.read_current(current.document_id).revision_id == moved.revision_id


def test_another_documents_revision_is_never_restored_here(store, current):
    """A revision identity is only meaningful inside its own document."""
    other = store.read_current(store.create_document(uuid4(), "另一份工作"))
    _, result = restore(store, current, other.revision_id)
    assert result.confirmed and result.status == "target_missing"
    assert store.read_current(current.document_id).revision_id == current.revision_id


def test_a_repeated_restore_returns_the_original_result_once(store, current):
    """A lost reply is answered from the recorded operation, not by restoring twice."""
    after_task, _, _ = change(store, current, "jd_create_task", task_args())
    with_extra, _, _ = change(store, after_task, "jd_insert_item", insert_item("duty", name="後來新增的職責", scope_text=None))
    key = uuid4()
    intent, first = restore(store, with_extra, after_task.revision_id, operation_id=key)
    again = store.execute(intent)
    assert again == first and again.status == "committed"
    assert len(revisions(store.engine, current.document_id)) == 4
    assert store.read_current(current.document_id).revision_id == first.receipt.result_revision_id


def test_restored_source_links_come_back_as_they_were_recorded(store, current):
    """Old basis is carried over, not re-approved against newer interviews."""
    after_task, _, _ = change(store, current, "jd_create_task", task_args())
    links = {row["source_ref"] for row in after_task.domain["source_links"]}
    assert links, "the created task really recorded its basis"
    cleared, _, _ = change(store, after_task, "jd_delete_item",
                           {"target_ref": f"task:{next(iter(after_task.domain['tasks']))}",
                            "content_changes": []})
    assert not cleared.domain["source_links"]
    _, result = restore(store, cleared, after_task.revision_id)
    assert result.status == "committed"
    restored = store.read_current(current.document_id)
    assert {row["source_ref"] for row in restored.domain["source_links"]} == links
