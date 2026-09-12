"""Real transaction integration with a synthetic runtime authority, no App/LLM.

Worker death/admission are simulated here; row-lock/COMMIT behavior is real PG.
The production runtime must still supply independently verified lifecycle proof.
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, replace
import logging
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Event
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

from test_storage_postgres import engine
from jd_relational.domain import CommandContext, Ref, Source
from jd_relational.intents import AdmittedIdentity, BoundEdit, bind_edit
from jd_relational.selection import Selection
from jd_relational.snapshots import snapshot_from_domain
from jd_relational.storage import schema as db
from jd_relational.storage.service import JdStorage, StorageError


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
                               reason="explicit isolated PostgreSQL test opt-in required")


class FakeAuthority:
    def __init__(self):
        self.bound = {}
        self.stopped = set()

    def admit(self, intent):
        self.bound[intent.operation_id] = intent.request_digest

    def require_bound(self, intent):
        assert isinstance(intent, BoundEdit)
        if self.bound.get(intent.operation_id) != intent.request_digest:
            raise ValueError("not_bound")

    def require_stopped(self, identity):
        assert isinstance(identity, AdmittedIdentity)
        if identity.operation_id not in self.stopped:
            raise ValueError("writer_may_run")


@pytest.fixture
def store(engine):
    return JdStorage(engine, FakeAuthority())


@pytest.fixture
def current(store):
    return store.read_current(store.create_document(uuid4(), "合成個人工作"))


def refs_for(current):
    doc, rev, state = current.document_id, str(current.revision_id), current.domain
    refs = {f"profile.{field}": Ref(doc, rev, "profile", field=field) for field in state["profile"]}
    for kind, collection in (("duty", "duties"), ("task", "tasks"), ("detail", "details"),
                             ("capability", "capabilities"), ("condition", "conditions"), ("collaborator", "collaborators")):
        for identity, row in state[collection].items():
            refs[f"{kind}:{identity}"] = Ref(doc, rev, kind, identity)
            for field in ("name", "scope_text", "description", "text"):
                if field in row:
                    refs[f"{kind}:{identity}.{field}"] = Ref(doc, rev, kind, identity, field=field)
    for kind in ("duty", "collaborator", "knowledge", "skill", "task", "qualification"):
        refs[f"container:{kind}"] = Ref(doc, rev, "container", child_kind=kind)
    for identity in state["duties"]:
        refs[f"tasks:{identity}"] = Ref(doc, rev, "container", identity, child_kind="task")
    return refs


def intent_for(store, current, tool, args, *, operation_id=None, origin="manual", ai_run_id=None, selections=None):
    context = CommandContext(current.document_id, str(current.revision_id), refs_for(current),
        {"qa:1": Source(current.document_id), "qa:2": Source(current.document_id)},
        lambda: str(uuid4()), selections or {})
    intent = bind_edit(operation_id=operation_id or uuid4(), origin=origin, ai_run_id=ai_run_id,
                       command={"tool": tool, "arguments": args}, context=context)
    store.authority.admit(intent)
    return intent


def change(store, current, tool, args, **options):
    intent = intent_for(store, current, tool, args, **options)
    result = store.execute(intent)
    assert result.confirmed and result.status == "committed"
    return store.read_current(current.document_id), intent, result


def insert_item(kind, **extra):
    return {"item": {"kind": kind, "container_ref": f"container:{kind}", "after_ref": None,
                     "basis_refs": [], **extra}}


def task_args(container="container:task"):
    return dict(container_ref=container, after_ref=None, name="每月檢查", description="檢查合約內系統",
        basis_refs=["qa:1"], outcomes=[{"text": "檢查紀錄", "basis_refs": []}],
        requirements=[{"text": "僅限合約範圍", "basis_refs": ["qa:2"]}], capabilities=[])


def test_creation_is_atomic_and_replayed_by_original_key(store, engine):
    key = uuid4()
    doc = store.create_document(key, "初稿")
    assert store.create_document(key, "初稿") == doc == store.lookup_creation(key, "初稿")
    with pytest.raises(StorageError, match="operation_conflict"):
        store.create_document(key, "不同意圖")
    current = store.read_current(doc)
    assert current.revision_number == 1 and not current.domain["tasks"]
    assert current.domain["profile"]["purpose"] is None
    with engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(db.jd_revision).where(db.jd_revision.c.document_id == doc)).scalar_one() == 1


def test_eight_shared_commands_reach_current_snapshot_and_receipt(store, current):
    current, _, _ = change(store, current, "jd_insert_item", insert_item("duty", name="維護", scope_text=None))
    duty = next(iter(current.domain["duties"]))
    current, _, _ = change(store, current, "jd_insert_item", insert_item("skill", name="診斷", description=None))
    cap = next(iter(current.domain["capabilities"]))
    args = task_args(f"tasks:{duty}")
    args["capabilities"] = [{"capability_ref": f"capability:{cap}", "basis_refs": ["qa:2"]}]
    current, _, ai_result = change(store, current, "jd_create_task", args, origin="ai", ai_run_id="synthetic-run")
    task = next(iter(current.domain["tasks"]))
    assert ai_result.receipt.ai_run_id == "synthetic-run"
    current, _, _ = change(store, current, "jd_set_text", {"target_field_ref": "profile.purpose", "text": "忠實記錄工作", "basis_refs": []})
    current, _, _ = change(store, current, "jd_revise_work", {"changes": [
        {"kind": "set_field", "target_field_ref": f"task:{task}.description", "text": "核對合約內系統", "basis_refs": ["qa:1"]},
        {"kind": "add_task_detail", "task_ref": f"task:{task}", "detail_kind": "outcome", "after_ref": None,
         "text": "異常轉交資訊", "basis_refs": []}]})
    field = f"task:{task}.description"
    selection = Selection(field, "核對合約內系統", 0, 2, "核對")
    current, _, _ = change(store, current, "jd_replace_selection", {"selection_ref": "selection:1", "replacement_text": "檢查", "basis_refs": []},
                            selections={"selection:1": selection})
    current, _, _ = change(store, current, "jd_move_item", {"target_ref": f"task:{task}",
        "destination_container_ref": "container:task", "after_ref": None, "content_changes": []})
    current, _, _ = change(store, current, "jd_set_task_capability", {"task_ref": f"task:{task}",
        "capability_ref": f"capability:{cap}", "mode": "unlink", "basis_refs": []})
    current, _, _ = change(store, current, "jd_delete_item", {"target_ref": f"duty:{duty}", "content_changes": []})
    state = current.domain
    assert state["tasks"][task]["description"] == "檢查合約內系統"
    assert state["tasks"][task]["duty_id"] is None and len(state["details"]) == 3
    assert not state["duties"] and not state["task_capabilities"] and cap in state["capabilities"]
    assert current.snapshot == snapshot_from_domain(state)


def test_no_change_records_receipt_without_revision_and_replay_ignores_new_head(store, current, engine):
    args = {"target_field_ref": "profile.purpose", "text": None, "basis_refs": []}
    intent = intent_for(store, current, "jd_set_text", args)
    result = store.execute(intent)
    assert result.confirmed and result.status == "no_change"
    assert result.receipt.result_revision_id == current.revision_id
    later, _, _ = change(store, current, "jd_set_text", {**args, "text": "新內容"})
    store.authority.bound.pop(intent.operation_id)
    replay = store.execute(intent)
    assert replay.receipt == result.receipt and store.read_current(current.document_id).revision_id == later.revision_id
    conflicting = intent_for(store, current, "jd_set_text", {**args, "text": "不同"}, operation_id=intent.operation_id)
    with pytest.raises(StorageError, match="operation_conflict"):
        store.execute(conflicting)


def test_domain_rejection_and_stale_base_are_confirmed_without_changing_content(store, current):
    stale = intent_for(store, current, "jd_set_text", {"target_field_ref": "profile.purpose", "text": "舊意圖", "basis_refs": []})
    current, _, _ = change(store, current, "jd_insert_item", insert_item("duty", name="有效工作", scope_text=None))
    duty = next(iter(current.domain["duties"]))
    invalid = intent_for(store, current, "jd_set_text", {"target_field_ref": f"duty:{duty}.name", "text": None, "basis_refs": []})
    invalid_result = store.execute(invalid)
    stale_result = store.execute(stale)
    assert invalid_result.confirmed and invalid_result.status == "invalid_input"
    assert stale_result.confirmed and stale_result.status == "stale_view"
    assert store.read_current(current.document_id).snapshot == current.snapshot


@contextmanager
def fail_statement(engine, marker, *, after=False):
    triggered = []
    def fault(conn, cursor, statement, parameters, context, executemany):
        if marker in statement:
            triggered.append(statement)
            raise RuntimeError("SyntheticPrivatePayload")
    event = "after_cursor_execute" if after else "before_cursor_execute"
    sa.event.listen(engine, event, fault)
    try:
        yield
    finally:
        sa.event.remove(engine, event, fault)
    assert len(triggered) == 1, "The requested SQL failure point must actually execute once."


@pytest.mark.parametrize("marker", ["INSERT INTO jd_task ", "INSERT INTO jd_revision ", "INSERT INTO jd_operation ", "UPDATE jd_head "])
def test_partial_sql_failure_rolls_back_and_requires_failure_only_reconciliation(store, current, engine, marker):
    intent = intent_for(store, current, "jd_create_task", task_args())
    with fail_statement(engine, marker, after=True):
        result = store.execute(intent)
    assert not result.confirmed and result.unresolved_effect == "unchanged" and result.next_action == "reconcile_operation"
    assert store.get_operation(current.document_id, intent.operation_id) is None
    assert store.read_current(current.document_id).snapshot == current.snapshot
    with pytest.raises(StorageError, match="writer_not_stopped"):
        store.reconcile_stopped(intent.identity)
    store.authority.stopped.add(intent.operation_id)  # synthetic runtime proof; not an OS death test
    closed = store.reconcile_stopped(intent.identity)
    assert closed.confirmed and closed.status == "save_failed"
    assert store.execute(intent).receipt == closed.receipt  # failure-only closure must not replay edit
    assert store.read_current(current.document_id).revision_id == current.revision_id


def test_lost_commit_reply_reads_original_success_without_duplicate_task(store, current, engine, monkeypatch):
    intent = intent_for(store, current, "jd_create_task", task_args())
    original = engine.dialect.do_commit
    def lose_reply(connection):
        original(connection)
        raise RuntimeError("Synthetic lost COMMIT acknowledgment")
    with monkeypatch.context() as scope:
        scope.setattr(engine.dialect, "do_commit", lose_reply)
        result = store.execute(intent)
    assert not result.confirmed and result.status == "outcome_unknown"
    def cannot_connect(**kwargs):
        raise OSError("Synthetic connection failure during retry lookup")
    with monkeypatch.context() as scope:
        scope.setattr(store, "_connection", cannot_connect)
        retry_observation = store.execute(intent)
    assert not retry_observation.confirmed and retry_observation.unresolved_effect == "unknown"
    saved = store.get_operation(current.document_id, intent.operation_id)
    assert saved.status == "committed"
    store.authority.stopped.add(intent.operation_id)
    assert store.reconcile_stopped(AdmittedIdentity(**asdict(intent.identity))).receipt == saved
    state = store.read_current(current.document_id)
    assert len(state.domain["tasks"]) == 1 and state.revision_number == 2


def test_failure_receipt_commit_loss_stays_unchanged_then_reads_original_failure(store, current, engine, monkeypatch):
    current, _, _ = change(store, current, "jd_insert_item", insert_item("duty", name="工作", scope_text=None))
    duty = next(iter(current.domain["duties"]))
    intent = intent_for(store, current, "jd_set_text", {"target_field_ref": f"duty:{duty}.name", "text": None, "basis_refs": []})
    original = engine.dialect.do_commit
    def lose_reply(connection):
        original(connection)
        raise RuntimeError("Synthetic lost failure receipt acknowledgment")
    with monkeypatch.context() as scope:
        scope.setattr(engine.dialect, "do_commit", lose_reply)
        result = store.execute(intent)
    assert not result.confirmed and result.unresolved_effect == "unchanged"
    assert result.next_action == "reconcile_operation"
    assert store.get_operation(current.document_id, intent.operation_id).status == "invalid_input"
    assert store.read_current(current.document_id).snapshot == current.snapshot


def test_two_same_base_edits_have_one_success_and_one_stale(store, current):
    intents = [intent_for(store, current, "jd_set_text", {"target_field_ref": "profile.purpose", "text": text, "basis_refs": []})
               for text in ("第一筆", "第二筆")]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(store.execute, intents))
    assert sorted(result.status for result in results) == ["committed", "stale_view"]
    assert all(result.confirmed for result in results)
    assert store.read_current(current.document_id).revision_number == 2


def test_duplicate_original_operation_has_one_receipt_and_one_task(store, current):
    intent = intent_for(store, current, "jd_create_task", task_args())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(store.execute, [intent, intent]))
    assert all(result.confirmed for result in results)
    assert results[0].receipt == results[1].receipt
    assert len(store.read_current(current.document_id).domain["tasks"]) == 1


def test_creation_failure_after_initial_rows_rolls_back_whole_document(store, engine):
    key = uuid4()
    with fail_statement(engine, "INSERT INTO jd_head ", after=True):
        with pytest.raises(StorageError, match="create_unconfirmed"):
            store.create_document(key, "建立故障測試")
    assert store.lookup_creation(key, "建立故障測試") is None


def test_new_process_reads_saved_content_and_operation_without_writer_permission(store, current):
    current, intent, result = change(store, current, "jd_create_task", task_args())
    code = """
import json, sys
from uuid import UUID
import sqlalchemy as sa
from jd_relational.storage.service import JdReader
from jd_relational.storage.history import HistoryReader
engine = sa.create_engine('postgresql+psycopg://jd_test:jd-local-test-only@127.0.0.1:55436/caliburn_jd_relational_test', hide_parameters=True)
store = JdReader(engine)
current = store.read_current(sys.argv[1])
receipt = HistoryReader(engine).read_change(sys.argv[1], UUID(sys.argv[2])).receipt
print(json.dumps({'revision':str(current.revision_id), 'task_count':len(current.domain['tasks']), 'status':receipt.status}))
engine.dispose()
"""
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    process = subprocess.run([sys.executable, "-c", code, current.document_id, str(intent.operation_id)],
                             env=env, capture_output=True, text=True, timeout=15)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == {"revision": str(result.receipt.result_revision_id), "task_count": 1, "status": "committed"}


def test_savepoint_rejection_retains_document_and_head_locks_until_receipt_commit(store, current, engine):
    current, _, _ = change(store, current, "jd_insert_item", insert_item("duty", name="工作", scope_text=None))
    duty = next(iter(current.domain["duties"]))
    intent = intent_for(store, current, "jd_set_text", {"target_field_ref": f"duty:{duty}.name", "text": None, "basis_refs": []})
    checked = []
    def check_locks(conn, cursor, statement, parameters, context, executemany):
        if "INSERT INTO jd_operation " not in statement:
            return
        for table, column in ((db.jd_document, db.jd_document.c.id), (db.jd_head, db.jd_head.c.document_id)):
            with pytest.raises(OperationalError) as failure:
                with engine.connect() as other, other.begin():
                    other.execute(sa.select(table).where(column == current.document_id).with_for_update(nowait=True)).all()
            assert failure.value.orig.sqlstate == "55P03"
            checked.append(table.name)
    sa.event.listen(engine, "before_cursor_execute", check_locks)
    try:
        result = store.execute(intent)
    finally:
        sa.event.remove(engine, "before_cursor_execute", check_locks)
    assert result.confirmed and result.status == "invalid_input"
    assert checked == ["jd_document", "jd_head"]


def test_storage_diagnostics_are_fixed_metadata_and_sink_failure_cannot_replace_commit(store, current, caplog):
    secret = "SyntheticPrivateWorkText"
    intent = intent_for(store, current, "jd_set_text", {"target_field_ref": "profile.purpose", "text": secret, "basis_refs": []})
    with caplog.at_level(logging.INFO, logger="caliburn.jd.storage"):
        result = store.execute(intent)
    records = [record for record in caplog.records if record.name == "caliburn.jd.storage"]
    assert result.confirmed and len(records) == 1
    assert records[0].outcome == "committed" and records[0].phase == "committed"
    assert not records[0].exc_info and secret not in repr(records[0].__dict__)
    class BrokenHandler(logging.Handler):
        def emit(self, record):
            raise RuntimeError("Broken synthetic sink")
    logger = logging.getLogger("caliburn.jd.storage")
    handler = BrokenHandler()
    logger.addHandler(handler)
    previous_level = logger.level
    logger.setLevel(logging.INFO)
    try:
        assert store.execute(intent).receipt == result.receipt
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)


def test_different_documents_do_not_share_a_global_mutex(store, current, engine):
    other = store.read_current(store.create_document(uuid4(), "另一份工作"))
    intent = intent_for(store, other, "jd_set_text", {"target_field_ref": "profile.purpose", "text": "獨立保存", "basis_refs": []})
    with engine.connect() as conn, conn.begin():
        conn.execute(sa.select(db.jd_document).where(db.jd_document.c.id == current.document_id).with_for_update()).all()
        conn.execute(sa.select(db.jd_head).where(db.jd_head.c.document_id == current.document_id).with_for_update()).all()
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(store.execute, intent).result(timeout=3).status == "committed"


def test_read_snapshot_stays_consistent_when_another_writer_commits(store, current, engine):
    intent = intent_for(store, current, "jd_create_task", task_args())
    reader_started, writer_finished = Event(), Event()
    reader_connection = []
    def interleave(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT jd_document.") and not reader_started.is_set():
            reader_connection.append(conn)
            reader_started.set()
            assert writer_finished.wait(timeout=8)
    sa.event.listen(engine, "after_cursor_execute", interleave)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            read = pool.submit(store.read_current, current.document_id)
            assert reader_started.wait(timeout=3)
            result = store.execute(intent)
            writer_finished.set()
            assert result.status == "committed"
            old = read.result(timeout=3)
        assert old.revision_id == current.revision_id and not old.domain["tasks"]
    finally:
        writer_finished.set()
        sa.event.remove(engine, "after_cursor_execute", interleave)
    assert len(store.read_current(current.document_id).domain["tasks"]) == 1


def test_failure_only_recovery_needs_no_command_refs_sources_or_candidate(store, current, monkeypatch):
    import jd_relational.intents as intents
    import jd_relational.storage.service as service
    intent = intent_for(store, current, "jd_create_task", task_args(), origin="ai", ai_run_id="synthetic-run")
    identity = intents.AdmittedIdentity(**asdict(intent.identity))
    store.authority.stopped.add(identity.operation_id)  # Synthetic proof only.
    def forbidden(*args, **kwargs):
        pytest.fail("Failure-only closure must not read or rebuild an edit candidate.")
    monkeypatch.setattr(service, "prepare_edit", forbidden)
    monkeypatch.setattr(service, "read_domain", forbidden)
    monkeypatch.setattr(intents, "_semantic_command", forbidden)
    monkeypatch.setattr(intents, "_freeze_context", forbidden)
    monkeypatch.setattr(service.JdStorage, "_edit_locked", forbidden)
    result = store.reconcile_stopped(identity)
    assert result.confirmed and result.status == "save_failed"
    assert result.receipt.body.command_kind == "jd_create_task"
    assert result.receipt.request_digest == identity.request_digest
    assert result.receipt.ai_run_id == "synthetic-run"
    assert store.reconcile_stopped(identity).receipt == result.receipt
    assert store.execute(intent).receipt == result.receipt


def test_reader_needs_no_authority_and_has_no_write_operations(engine, current):
    from jd_relational.storage.service import JdReader
    reader = JdReader(engine)
    assert reader.read_current(current.document_id) == current
    for name in ("authority", "execute", "create_document", "reconcile_stopped"):
        assert not hasattr(reader, name)
    with reader._connection() as conn, conn.begin():
        assert conn.execute(sa.text("SHOW transaction_read_only")).scalar_one() == "on"
        assert conn.execute(sa.text("SHOW transaction_isolation")).scalar_one() == "repeatable read"
    with pytest.raises(ValueError, match="WriterAuthority is required"):
        JdStorage(engine, None)


@pytest.mark.parametrize("change", ["digest", "base", "origin", "run", "command_kind"])
def test_recovery_identity_must_match_original_receipt_without_rewriting_it(store, current, change):
    intent = intent_for(store, current, "jd_create_task", task_args(), origin="ai", ai_run_id="original-run")
    saved = store.execute(intent)
    assert saved.status == "committed"
    changes = {
        "digest": {"request_digest": "a" * 64}, "base": {"base_revision_id": uuid4()},
        "origin": {"origin": "manual", "ai_run_id": None}, "run": {"ai_run_id": "different-run"},
        "command_kind": {"command_kind": "jd_set_text"},
    }
    wrong = replace(intent.identity, **changes[change])
    store.authority.stopped.add(intent.operation_id)
    with pytest.raises(StorageError, match="operation_conflict"):
        store.reconcile_stopped(wrong)
    assert store.get_operation(current.document_id, intent.operation_id) == saved.receipt
    assert store.reconcile_stopped(intent.identity).receipt == saved.receipt
    current_after = store.read_current(current.document_id)
    assert len(current_after.domain["tasks"]) == 1 and current_after.revision_number == 2


def test_unknown_base_failure_remains_readable_by_original_identity(store, current):
    unknown_base = uuid4()
    context = CommandContext(current.document_id, str(unknown_base),
        {"field": Ref(current.document_id, str(unknown_base), "profile", field="purpose")}, {}, lambda: str(uuid4()))
    intent = bind_edit(uuid4(), "manual", None,
        {"tool": "jd_set_text", "arguments": {"target_field_ref": "field", "text": "晚到", "basis_refs": []}}, context)
    store.authority.admit(intent)
    saved = store.execute(intent)
    assert saved.status == "stale_view" and saved.receipt.base_revision_id is None
    store.authority.stopped.add(intent.operation_id)
    assert store.reconcile_stopped(intent.identity).receipt == saved.receipt
    assert store.read_current(current.document_id) == current


@pytest.mark.parametrize("committed", [False, True], ids=["failure-only", "original-success"])
def test_new_process_recovers_from_identity_without_any_edit_material(store, current, committed):
    intent = intent_for(store, current, "jd_create_task", task_args(), origin="ai", ai_run_id="synthetic-restart-run")
    original = store.execute(intent).receipt if committed else None
    payload = asdict(intent.identity)
    payload["operation_id"] = str(payload["operation_id"])
    payload["base_revision_id"] = str(payload["base_revision_id"])
    code = """
import json, sys
from uuid import UUID
import sqlalchemy as sa
import jd_relational.intents as intents
import jd_relational.storage.service as service
def forbidden(*args, **kwargs):
    raise AssertionError('No candidate, refs or source reconstruction is allowed.')
class SyntheticStoppedOwner:
    # This isolates cross-process metadata recovery, not actual OS death proof.
    def require_bound(self, intent): forbidden()
    def require_stopped(self, identity):
        assert type(identity) is intents.AdmittedIdentity
payload = json.loads(sys.argv[1])
payload['operation_id'] = UUID(payload['operation_id'])
payload['base_revision_id'] = UUID(payload['base_revision_id'])
intents._freeze_context = forbidden
intents._semantic_command = forbidden
service.prepare_edit = forbidden
service.read_domain = forbidden
identity = intents.AdmittedIdentity(**payload)
engine = sa.create_engine('postgresql+psycopg://jd_test:jd-local-test-only@127.0.0.1:55436/caliburn_jd_relational_test', hide_parameters=True)
result = service.JdStorage(engine, SyntheticStoppedOwner()).reconcile_stopped(identity)
assert result.confirmed
print(json.dumps({'operation':str(result.operation_id), 'status':result.status,
    'digest':result.receipt.request_digest, 'command_kind':result.receipt.body.command_kind}))
engine.dispose()
"""
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    process = subprocess.run([sys.executable, "-c", code, json.dumps(payload)],
                             env=env, capture_output=True, text=True, timeout=15)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == {"operation": str(intent.operation_id),
        "status": "committed" if committed else "save_failed",
        "digest": intent.request_digest, "command_kind": "jd_create_task"}
    saved = store.get_operation(current.document_id, intent.operation_id)
    if original is not None:
        assert saved == original
    after = store.read_current(current.document_id)
    assert len(after.domain["tasks"]) == int(committed)
    assert after.revision_number == current.revision_number + int(committed)
