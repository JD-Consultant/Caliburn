"""Opt-in real PG, native Saver and owned manual writer service integration.

The existing dedicated database/runtime schema must be initialized explicitly.
Each test keeps fresh synthetic documents; no provider, HTTP or OS proof is used.
"""

from copy import deepcopy
import json
import os
from threading import Event
from uuid import UUID, uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
import pytest
import sqlalchemy as sa

from jd_relational.domain import Source
from jd_relational.manual_service import ManualError, ManualService
from jd_relational.reads import ReadService
from jd_relational.references import ReferenceCodec
from jd_relational.storage import schema as db
from jd_relational.storage.history import HistoryReader
from test_manual_runtime_postgres import config, counts, persisted_pending, runtime_factory
from test_storage_postgres import engine


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")


@pytest.fixture
def app(runtime_factory):
    owner, graph, observed, calls = runtime_factory()
    codec = ReferenceCodec(b"synthetic-manual-service-signing-key", "synthetic-manual-service-dataset")

    def forbidden_source(*args):
        raise AssertionError("Empty source lists must not call a source owner.")

    service = ManualService(owner, HistoryReader(owner.storage.engine), codec,
        source_resolver=forbidden_source, wait_timeout=5)
    document = owner.storage.create_document(uuid4(), "合成人工服务工作")
    reads = ReadService(owner.storage, HistoryReader(owner.storage.engine), codec)
    return service, owner, graph, observed, calls, document, reads, codec


def current_page(app):
    return app[6].read(app[5], {"view": "current", "target_ref": None, "cursor": None})


def field(page, name):
    return next(row["field_ref"] for row in page["records"] if row["type"] == "field" and row["name"] == name)


def edit(app, text="繁中實際工作😀\n精確保留空白  ", *, page=None, operation=None):
    page = page or current_page(app)
    return {"operation_id": str(operation or uuid4()), "base_revision_ref": page["revision_ref"],
        "command": {"tool": "jd_set_text", "arguments": {
            "target_field_ref": field(page, "purpose"), "text": text, "basis_refs": []}}}


def test_save_reads_real_current_and_preserves_native_original_messages(app, engine):
    service, owner, graph, _, calls, document, _, codec = app
    messages = [HumanMessage(content="原始員工話\n不隨 JD 倒退", id="human-original"),
        AIMessage(content=[{"type": "reasoning", "encrypted_content": "synthetic-opaque"},
            {"type": "compaction", "encrypted_content": "synthetic-compaction"},
            {"type": "text", "text": "原顧問工作理解"}], id="ai-original", tool_calls=[
                {"name": "synthetic", "args": {"keep": True}, "id": "call-original", "type": "tool_call"}]),
        ToolMessage(content="原始工具結果", tool_call_id="call-original", id="tool-original")]
    graph.update_state(config(document), {"messages": messages}, as_node="consultant")
    original = [message.model_dump() for message in graph.get_state(config(document)).values["messages"]]
    envelope = edit(app)
    result = service.save(document, json.dumps(envelope, ensure_ascii=False))
    assert result["status"] == "committed" and result["receipt_durability"] == "confirmed"
    assert owner.storage.read_current(document).domain["profile"]["purpose"] == envelope["command"]["arguments"]["text"]
    operation = codec.resolve(result["operation_ref"], document_id=document,
        roles={"operation"}, purposes={"observation"})
    assert operation.entity_id == envelope["operation_id"]
    receipt = owner.storage.get_operation(document, UUID(envelope["operation_id"]))
    assert receipt.origin == "manual" and receipt.ai_run_id is None
    assert [message.model_dump() for message in graph.get_state(config(document)).values["messages"]] == original
    assert calls == [] and counts(engine, document) == (2, 1) and persisted_pending(document) is None


def test_same_operation_after_head_advance_returns_original_but_changed_payload_conflicts(app, engine):
    service, owner, _, _, calls, document, _, _ = app
    first = edit(app, "原次保存")
    result = service.save(document, first)
    saved = owner.storage.get_operation(document, UUID(first["operation_id"]))
    assert service.save(document, edit(app, "後來的新工作"))["status"] == "committed"
    assert service.save(document, deepcopy(first)) == result
    assert owner.storage.get_operation(document, UUID(first["operation_id"])) == saved
    changed = deepcopy(first)
    changed["command"]["arguments"]["text"] = "同 key 偷換內容"
    with pytest.raises(ManualError, match="^operation_conflict$"):
        service.save(document, changed)
    assert owner.storage.read_current(document).domain["profile"]["purpose"] == "後來的新工作"
    assert calls == [] and counts(engine, document) == (3, 2)


def test_new_operation_from_stale_base_gets_confirmed_rejection_without_rebasing(app, engine):
    service, owner, _, _, calls, document, _, _ = app
    old_page = current_page(app)
    assert service.save(document, edit(app, "先保存的工作", page=old_page))["status"] == "committed"
    stale = edit(app, "不准自動改用新版", page=old_page)
    result = service.save(document, stale)
    assert result["status"] == "stale_view" and result["receipt_durability"] == "confirmed"
    assert result["effect"] == "unchanged" and result["result_revision_ref"] is None
    assert result["next_action"] == "reread_current"
    assert owner.storage.get_operation(document, UUID(stale["operation_id"])).status == "stale_view"
    assert owner.storage.read_current(document).domain["profile"]["purpose"] == "先保存的工作"
    assert calls == [] and counts(engine, document) == (2, 2)


def test_no_change_is_persisted_and_looked_up_without_new_revision(app, engine):
    service, owner, _, _, calls, document, _, _ = app
    envelope = edit(app, None)
    result = service.save(document, envelope)
    assert result["status"] == "no_change" and result["receipt_durability"] == "confirmed"
    assert result["change_ref"] is None and result["result_revision_ref"] is not None
    looked_up = service.lookup(document, envelope["operation_id"])
    assert looked_up["presence"] == "observed" and looked_up["result"] == result
    assert not looked_up["write_state"]["write_blocked"]
    assert owner.storage.read_current(document).revision_number == 1
    assert calls == [] and counts(engine, document) == (1, 1)


def test_checkpoint_cleanup_loss_does_not_downgrade_success_and_recovery_only_cleans(app, engine, monkeypatch):
    service, owner, _, observed, calls, document, _, _ = app
    observed.lose, observed.unreadable_after_loss = "close", True
    envelope = edit(app)
    result = service.save(document, envelope)
    assert result["status"] == "committed" and result["receipt_durability"] == "confirmed"
    assert service.status(document)["write_blocked"]
    assert persisted_pending(document) is None
    saved = owner.storage.get_operation(document, UUID(envelope["operation_id"]))

    def forbidden(*args):
        raise AssertionError("Known receipt plus cleared checkpoint requires no JD replay or reconciliation SQL.")

    monkeypatch.setattr(owner.storage, "execute", forbidden)
    monkeypatch.setattr(owner.storage, "reconcile_stopped", forbidden)
    observed.unreadable = False
    recovered = service.recover(document, envelope["operation_id"])
    assert recovered["presence"] == "observed" and recovered["result"] == result
    assert not recovered["write_state"]["write_blocked"]
    assert owner.storage.get_operation(document, UUID(envelope["operation_id"])) == saved
    assert calls == [] and counts(engine, document) == (2, 1)


def test_wait_timeout_and_lookup_leave_actual_writer_and_native_pending_untouched(app, engine, monkeypatch):
    _, owner, _, observed, calls, document, _, codec = app
    service = ManualService(owner, HistoryReader(engine), codec, wait_timeout=0.01)
    entered, release = Event(), Event()
    executed, handles = [], []
    original_execute, original_submit = owner.storage.execute, owner.submit

    def blocked(intent):
        executed.append(intent.operation_id)
        entered.set()
        assert release.wait(10), "The test must release its own writer."
        return original_execute(intent)

    def submit(intent):
        handle = original_submit(intent)
        handles.append(handle)
        return handle

    monkeypatch.setattr(owner.storage, "execute", blocked)
    monkeypatch.setattr(owner, "submit", submit)
    envelope = edit(app)
    try:
        result = service.save(document, envelope)
        assert entered.wait(3)
        assert result["status"] == "outcome_unknown" and result["next_action"] == "reconcile_operation"
        pending_before = persisted_pending(document)
        updates_before = deepcopy(observed.updates)
        view = service.lookup(document, envelope["operation_id"])
        assert view["presence"] == "pending" and view["write_state"]["running"]
        assert view["write_state"]["write_blocked"]
        assert persisted_pending(document) == pending_before and observed.updates == updates_before
        assert counts(engine, document) == (1, 0) and executed == [UUID(envelope["operation_id"])]
    finally:
        release.set()
    assert handles[0].wait(5).checkpoint_closed
    found = service.lookup(document, envelope["operation_id"])
    assert found["presence"] == "observed" and found["result"]["status"] == "committed"
    assert executed == [UUID(envelope["operation_id"])] and calls == [] and counts(engine, document) == (2, 1)


def test_real_commit_ack_loss_lookup_and_recovery_preserve_original_without_replay(app, engine, monkeypatch):
    service, owner, _, _, calls, document, _, _ = app
    original_commit, original_execute = engine.dialect.do_commit, owner.storage.execute
    committed, executions = [], []

    def lose_ack(connection):
        original_commit(connection)
        committed.append(True)
        raise OSError("synthetic private SQL acknowledgement detail")

    def execute(intent):
        executions.append(intent.operation_id)
        with monkeypatch.context() as scope:
            scope.setattr(engine.dialect, "do_commit", lose_ack)
            return original_execute(intent)

    monkeypatch.setattr(owner.storage, "execute", execute)
    envelope = edit(app)
    result = service.save(document, envelope)
    assert committed and result["status"] == "outcome_unknown"
    saved = owner.storage.get_operation(document, UUID(envelope["operation_id"]))
    assert saved.status == "committed"
    found = service.lookup(document, envelope["operation_id"])
    assert found["presence"] == "observed" and found["result"]["status"] == "committed"
    assert found["write_state"]["write_blocked"] and persisted_pending(document) is not None

    def forbidden(*args):
        raise AssertionError("Original receipt recovery must never replay the command.")

    monkeypatch.setattr(owner.storage, "execute", forbidden)
    recovered = service.recover(document, envelope["operation_id"])
    assert recovered["result"] == found["result"] and not recovered["write_state"]["write_blocked"]
    assert owner.storage.get_operation(document, UUID(envelope["operation_id"])) == saved
    assert executions == [UUID(envelope["operation_id"])] and calls == [] and counts(engine, document) == (2, 1)


def test_operation_lookup_after_archive_does_not_revisit_sources_or_historical_refs(app, engine, monkeypatch):
    _, owner, _, _, calls, document, _, codec = app
    resolutions = []
    unavailable = False

    def source(token, scope):
        assert not unavailable, "Original result lookup must not reread current source availability."
        resolutions.append((token, scope))
        return Source(scope)

    history = HistoryReader(engine)
    service = ManualService(owner, history, codec, source_resolver=source, wait_timeout=5)
    envelope = edit(app)
    envelope["command"]["arguments"]["basis_refs"] = ["synthetic-interview:service-source"]
    result = service.save(document, envelope)
    assert result["status"] == "committed"
    assert resolutions == [("synthetic-interview:service-source", document)]
    unavailable = True

    def forbidden(*args):
        raise AssertionError("A key-only operation lookup must not reconstruct the historical command.")

    monkeypatch.setattr(history, "read_revision", forbidden)
    with engine.begin() as conn:
        conn.execute(db.jd_document.update().where(db.jd_document.c.id == document).values(archived=True))
    found = service.lookup(document, envelope["operation_id"])
    assert found["presence"] == "observed" and found["result"] == result
    assert found["write_state"]["archived"] and found["write_state"]["write_blocked"]
    assert len(resolutions) == 1 and calls == [] and counts(engine, document) == (2, 1)


def test_nonempty_sources_without_owner_are_rejected_before_admission(app, engine):
    _, owner, _, observed, calls, document, _, codec = app
    service = ManualService(owner, HistoryReader(engine), codec, wait_timeout=5)
    envelope = edit(app)
    envelope["command"]["arguments"]["basis_refs"] = ["synthetic-source:without-owner"]
    with pytest.raises(ManualError, match="^invalid_ref$"):
        service.save(document, envelope)
    assert observed.updates == [] and persisted_pending(document) is None
    assert calls == [] and counts(engine, document) == (1, 0)


def test_full_revision_has_no_partial_write_and_accepts_valid_final_name_to_description(app, engine):
    service, owner, _, _, calls, document, _, _ = app
    page = current_page(app)
    container = next(row["container_ref"] for row in page["records"]
        if row["type"] == "container" and row["child_kind"] == "task" and row["owner_ref"] is None)
    create = {"operation_id": str(uuid4()), "base_revision_ref": page["revision_ref"],
        "command": {"tool": "jd_create_task", "arguments": {
            "container_ref": container, "after_ref": None, "name": "維修診斷", "description": None,
            "basis_refs": [], "outcomes": [{"text": "診斷紀錄", "basis_refs": []}],
            "requirements": [{"text": "維修前安全隔離", "basis_refs": []}], "capabilities": []}}}
    assert service.save(document, create)["status"] == "committed"
    page = current_page(app)
    before = owner.storage.read_current(document)
    changes = [{"kind": "set_field", "target_field_ref": field(page, "purpose"), "text": "不可半保存", "basis_refs": []},
        {"kind": "set_field", "target_field_ref": field(page, "name"), "text": None, "basis_refs": []}]
    correction = {"operation_id": str(uuid4()), "base_revision_ref": page["revision_ref"],
        "command": {"tool": "jd_revise_work", "arguments": {"changes": changes}}}
    result = service.save(document, correction)
    assert result["status"] == "invalid_input" and result["receipt_durability"] == "confirmed"
    after = owner.storage.read_current(document)
    assert after.snapshot == before.snapshot and after.revision_id == before.revision_id
    assert counts(engine, document) == (2, 2)
    valid = deepcopy(correction)
    valid["operation_id"] = str(uuid4())
    valid["command"]["arguments"]["changes"].append({"kind": "set_field",
        "target_field_ref": field(page, "description"), "text": "實际負責設備技術診斷", "basis_refs": []})
    assert service.save(document, valid)["status"] == "committed"
    current = owner.storage.read_current(document)
    task = next(iter(current.domain["tasks"].values()))
    assert task["name"] is None and task["description"] == "實际負責設備技術診斷"
    assert current.domain["details"] == before.domain["details"]
    assert calls == [] and counts(engine, document) == (3, 3)


def test_unknown_operation_is_only_not_found_and_get_does_not_close_or_write(app, engine):
    service, _, _, observed, calls, document, _, _ = app
    operation = str(uuid4())
    state = service.lookup(document, operation)
    assert state["operation_id"] == operation and state["presence"] == "not_found" and state["result"] is None
    assert state["write_state"]["ready"] and state["write_state"]["operation_id"] is None
    assert observed.updates == [] and calls == [] and counts(engine, document) == (1, 0)


def test_recovery_for_old_key_cannot_clear_another_pending_operation(app, engine):
    service, owner, _, observed, calls, document, _, _ = app
    first = edit(app, "操作 A")
    assert service.save(document, first)["status"] == "committed"
    observed.lose, observed.unreadable_after_loss = "close", True
    second = edit(app, "操作 B")
    assert service.save(document, second)["status"] == "committed"
    assert service.status(document)["operation_id"] == second["operation_id"]
    with pytest.raises(ManualError, match="^operation_conflict$"):
        service.recover(document, first["operation_id"])
    assert service.status(document)["operation_id"] == second["operation_id"]
    observed.unreadable = False
    result = service.recover(document, second["operation_id"])
    assert result["result"]["status"] == "committed" and not result["write_state"]["write_blocked"]
    assert owner.storage.read_current(document).domain["profile"]["purpose"] == "操作 B"
    assert calls == [] and counts(engine, document) == (3, 2)


def test_the_employee_can_restore_a_revision_and_take_back_an_ai_turn(app, engine):
    """Both manual-only entries reach the writer over the same save route.

    The employee names revisions by issued reference, never by raw identity,
    and the model has no way to ask for either of them.
    """
    service, owner, _, _, _, document, _, _ = app
    first = current_page(app)
    assert service.save(document, edit(app, "原本的工作目的。", page=first))["status"] == "committed"
    changed = current_page(app)
    assert changed["revision_ref"] != first["revision_ref"]

    restored = service.save(document, {"operation_id": str(uuid4()),
        "base_revision_ref": changed["revision_ref"],
        "command": {"tool": "restore_revision",
                    "arguments": {"target_revision_ref": first["revision_ref"]}}})
    assert restored["status"] == "committed"
    assert owner.storage.read_current(document).domain["profile"]["purpose"] is None

    # Undoing reaches the writer over the same route and by the same kind of
    # reference. A turn that wrote nothing has nothing to take back, which is
    # what proves the reference really became the identity the writer checked.
    now = current_page(app)
    nothing = service.save(document, {"operation_id": str(uuid4()),
        "base_revision_ref": now["revision_ref"],
        "command": {"tool": "undo_ai_turn",
                    "arguments": {"ai_run_id": str(uuid4()),
                                  "expected_result_ref": now["revision_ref"]}}})
    assert nothing["status"] == "target_missing"
    assert current_page(app)["revision_ref"] == now["revision_ref"]
