"""Real PG Saver + JD SQL + managed manual writers, with synthetic fault injection.

Run scripts/init_test_runtime.py explicitly first, then opt in with
JD_RELATIONAL_TEST_DB=1. No provider, automatic initialization, graph resume,
cross-process death proof, or deletion of persisted test evidence is performed.
"""

from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Event
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import interrupt
from psycopg import Connection
from psycopg.rows import dict_row
import pytest
import sqlalchemy as sa

from jd_relational.intents import bind_edit
from jd_relational.manual_runtime import ManualRuntime, RuntimeFailure
from jd_relational.reads import ReadService, command_context
from jd_relational.references import ReferenceCodec
from jd_relational.runtime_checkpoints import DocumentCheckpoints, build_document_graph
from jd_relational.storage.history import HistoryReader
from jd_relational.storage import schema as db
from jd_relational.storage.service import JdStorage
from test_storage_postgres import engine


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")

RUNTIME_SCHEMA = "jd_runtime_test"
NATIVE_TABLES = {"checkpoint_migrations", "checkpoints", "checkpoint_blobs", "checkpoint_writes"}
CONNECTION = dict(host="127.0.0.1", port=55436, dbname="caliburn_jd_relational_test",
    user="jd_test", password="jd-local-test-only", connect_timeout=5,
    options="-csearch_path=jd_runtime_test,public")


def config(document):
    return {"configurable": {"thread_id": document}}


def native_graph(saver, *, paused=False):
    calls = []

    def synthetic_consultant(state):
        calls.append("entered")
        if paused:
            interrupt("synthetic native pending work")
        raise AssertionError("Manual operations must never invoke the consultant.")

    child = StateGraph(MessagesState)
    child.add_node("synthetic", synthetic_consultant)
    child.add_edge(START, "synthetic")
    child.add_edge("synthetic", END)
    return build_document_graph(child.compile(), saver), calls


def connect():
    return Connection.connect(**CONNECTION, autocommit=True,
                              row_factory=dict_row, prepare_threshold=0)


class ObservedGraph:
    """Lose acknowledgements/read availability around the real persisted graph."""

    def __init__(self, graph):
        self.graph = graph
        self.lose = None
        self.unreadable_after_loss = False
        self.unreadable = False
        self.updates = []

    def get_state(self, supplied, **kwargs):
        if self.unreadable:
            raise OSError("synthetic private checkpoint transport detail")
        return self.graph.get_state(supplied, **kwargs)

    def update_state(self, supplied, values, **kwargs):
        self.updates.append(values.copy())
        result = self.graph.update_state(supplied, values, **kwargs)
        phase = "close" if values["jd_manual_pending"] is None else "admit"
        if self.lose == phase:
            self.unreadable = self.unreadable_after_loss
            raise OSError("synthetic private checkpoint acknowledgement detail")
        return result


@pytest.fixture
def runtime_factory(engine):
    stack, owners = ExitStack(), []

    def create(*, paused=False):
        conn = stack.enter_context(connect())
        assert conn.execute("SELECT current_database() AS db, current_user AS usr, "
            "current_setting('server_version_num')::integer AS version").fetchone() == {
                "db": "caliburn_jd_relational_test", "usr": "jd_test", "version": 180006}
        tables = {row["tablename"] for row in conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = %s", (RUNTIME_SCHEMA,))}
        assert tables == NATIVE_TABLES, "Run scripts/init_test_runtime.py explicitly first."
        assert conn.execute("SHOW search_path").fetchone()["search_path"] == "jd_runtime_test,public"
        saver = PostgresSaver(conn, serde=JsonPlusSerializer(allowed_msgpack_modules=None))
        graph, calls = native_graph(saver, paused=paused)
        observed = ObservedGraph(graph)
        checkpoints = DocumentCheckpoints(observed)
        owner = ManualRuntime(checkpoints, lambda authority: JdStorage(engine, authority), max_workers=2)
        owners.append(owner)
        return owner, graph, observed, calls

    try:
        yield create
    finally:
        for owner in reversed(owners):
            assert owner.close(timeout=5), "Test-owned writer must drain before its Saver closes."
        stack.close()


def prepare(owner, *, document=None, text="忠實呈現實際工作"):
    document = document or owner.storage.create_document(uuid4(), "合成持久 writer 驗收")
    current = owner.storage.read_current(document)
    codec = ReferenceCodec(b"synthetic-manual-runtime-test-key", "synthetic-manual-runtime-dataset")
    reads = ReadService(owner.storage, HistoryReader(owner.storage.engine), codec)
    page = reads.read(document, {"view": "current", "target_ref": None, "cursor": None})
    field = next(row for row in page["records"] if row["type"] == "field" and row["name"] == "purpose")
    command = {"tool": "jd_set_text", "arguments": {
        "target_field_ref": field["field_ref"], "text": text, "basis_refs": []}}

    def no_source_io(*args):
        raise AssertionError("Empty manual basis must not read sources.")

    context = command_context(current.domain, command, codec, no_source_io, lambda: str(uuid4()))
    return bind_edit(uuid4(), "manual", None, command, context)


def persisted_pending(document):
    with connect() as conn:
        graph, calls = native_graph(PostgresSaver(conn,
            serde=JsonPlusSerializer(allowed_msgpack_modules=None)))
        result = DocumentCheckpoints(graph).read(document)
        assert calls == []
        return result


def counts(engine, document):
    with engine.connect() as conn:
        return tuple(conn.execute(sa.select(sa.func.count()).select_from(table).where(
            table.c.document_id == document)).scalar_one() for table in (db.jd_revision, db.jd_operation))


def test_native_descriptor_precedes_sql_and_manual_preserves_native_messages(runtime_factory, engine):
    owner, graph, _, calls = runtime_factory()
    value = prepare(owner)
    messages = [HumanMessage(content="原始問答\n不可重建", id="original-human"),
        AIMessage(content=[{"type": "reasoning", "id": "synthetic-native-reasoning",
            "encrypted_content": "synthetic-opaque"},
            {"type": "compaction", "encrypted_content": "synthetic-compaction"},
            {"type": "text", "text": "原始模型內容"}], id="original-ai", tool_calls=[
                {"name": "synthetic_tool", "args": {"keep": True}, "id": "original-call", "type": "tool_call"}]),
        ToolMessage(content="原始結果", tool_call_id="original-call", id="original-tool")]
    graph.update_state(config(value.document_id), {"messages": messages}, as_node="consultant")
    before = [message.model_dump() for message in graph.get_state(config(value.document_id)).values["messages"]]
    observed = []

    def before_jd_mutation(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE jd_profile "):
            observed.append(persisted_pending(value.document_id))

    sa.event.listen(engine, "before_cursor_execute", before_jd_mutation)
    try:
        result = owner.submit(value).wait(5)
    finally:
        sa.event.remove(engine, "before_cursor_execute", before_jd_mutation)
    assert result.observation.status == "committed" and result.checkpoint_closed
    assert observed == [value.identity] and persisted_pending(value.document_id) is None
    assert [message.model_dump() for message in graph.get_state(config(value.document_id)).values["messages"]] == before
    assert calls == [] and counts(engine, value.document_id) == (2, 1)
    assert owner.submit(value).wait(5).observation == result.observation
    assert counts(engine, value.document_id) == (2, 1)


def test_native_interrupted_child_blocks_manual_without_rewriting_history(runtime_factory, engine):
    owner, graph, observed, calls = runtime_factory(paused=True)
    value = prepare(owner)
    graph.invoke({"messages": [HumanMessage(content="合成中斷", id="paused-original")]},
                 config(value.document_id), durability="sync")
    before = graph.get_state(config(value.document_id), subgraphs=True)
    assert before.tasks and before.next
    with pytest.raises(RuntimeFailure, match="^document_busy$"):
        owner.submit(value)
    status = owner.status(value.document_id)
    assert status.error == "document_busy" and status.write_blocked
    assert graph.get_state(config(value.document_id), subgraphs=True) == before
    assert calls == ["entered"] and observed.updates == []
    assert counts(engine, value.document_id) == (1, 0)


def test_admission_ack_loss_is_confirmed_once_by_real_readback(runtime_factory, engine):
    owner, _, observed, calls = runtime_factory()
    value = prepare(owner)
    observed.lose = "admit"
    result = owner.submit(value).wait(5)
    assert result.observation.status == "committed" and result.checkpoint_closed
    assert sum(row["jd_manual_pending"] is not None for row in observed.updates) == 1
    assert calls == [] and counts(engine, value.document_id) == (2, 1)


def test_unconfirmed_admission_has_zero_sql_and_failure_only_recovery(runtime_factory, engine, monkeypatch):
    owner, _, observed, calls = runtime_factory()
    value = prepare(owner)
    observed.lose, observed.unreadable_after_loss = "admit", True

    def forbidden_execute(*args):
        raise AssertionError("Unconfirmed admission must not execute or replay JD edits.")

    monkeypatch.setattr(owner.storage, "execute", forbidden_execute)
    result = owner.submit(value).wait(5)
    assert result.error == "checkpoint_unavailable" and result.observation is None
    assert persisted_pending(value.document_id) == value.identity
    assert counts(engine, value.document_id) == (1, 0)
    observed.unreadable = False
    recovered = owner.recover(value.document_id, timeout=5)
    assert recovered.observation.status == "save_failed" and recovered.checkpoint_closed
    assert owner.storage.read_current(value.document_id).domain["profile"]["purpose"] is None
    assert calls == [] and counts(engine, value.document_id) == (1, 1)


def test_real_sql_commit_ack_loss_recovers_original_receipt_without_replay(runtime_factory, engine, monkeypatch):
    owner, _, _, calls = runtime_factory()
    value = prepare(owner)
    original_commit, lost = engine.dialect.do_commit, []

    def lose_once(connection):
        original_commit(connection)
        lost.append(True)
        raise OSError("synthetic committed SQL acknowledgement lost")

    # The runtime's receipt lookup is read-only but commits its read transaction;
    # inject only once actual write execution has begun, not before admission.
    original_execute = owner.storage.execute

    def execute_with_lost_commit(intent):
        with monkeypatch.context() as scope:
            scope.setattr(engine.dialect, "do_commit", lose_once)
            return original_execute(intent)

    monkeypatch.setattr(owner.storage, "execute", execute_with_lost_commit)
    result = owner.submit(value).wait(5)
    assert lost and not result.observation.confirmed and not result.checkpoint_closed
    assert result.observation.unresolved_effect == "unknown"
    saved = owner.storage.get_operation(value.document_id, value.operation_id)
    assert saved.status == "committed" and persisted_pending(value.document_id) == value.identity

    def forbidden_replay(*args):
        raise AssertionError("Recovery must not call execute again.")

    monkeypatch.setattr(owner.storage, "execute", forbidden_replay)
    recovered = owner.recover(value.document_id, timeout=5)
    assert recovered.observation.receipt == saved and recovered.checkpoint_closed
    assert owner.storage.get_operation(value.document_id, value.operation_id) == saved
    assert calls == [] and counts(engine, value.document_id) == (2, 1)


def test_close_ack_and_read_loss_keeps_receipt_then_only_clears_local_gate(runtime_factory, engine, monkeypatch):
    owner, _, observed, calls = runtime_factory()
    value = prepare(owner)
    observed.lose, observed.unreadable_after_loss = "close", True
    result = owner.submit(value).wait(5)
    assert result.observation.status == "committed" and not result.checkpoint_closed
    assert result.error == "checkpoint_unavailable"
    assert persisted_pending(value.document_id) is None
    saved = owner.storage.get_operation(value.document_id, value.operation_id)

    def forbidden_sql(*args):
        raise AssertionError("Already committed and cleared checkpoint needs no SQL recovery.")

    monkeypatch.setattr(owner.storage, "execute", forbidden_sql)
    monkeypatch.setattr(owner.storage, "reconcile_stopped", forbidden_sql)
    observed.unreadable = False
    recovered = owner.recover(value.document_id, timeout=5)
    assert recovered.observation.receipt == saved and recovered.checkpoint_closed
    assert not owner.status(value.document_id).write_blocked
    assert calls == [] and counts(engine, value.document_id) == (2, 1)


def test_same_document_is_blocked_but_other_document_can_save(runtime_factory, engine, monkeypatch):
    owner, _, _, calls = runtime_factory()
    one, two = prepare(owner), prepare(owner)
    conflict = prepare(owner, document=one.document_id, text="同份其他意圖")
    entered, release = Event(), Event()
    original = owner.storage.execute

    def wait_for_first(intent):
        if intent.document_id == one.document_id:
            entered.set()
            assert release.wait(5), "Test must release its own running writer."
        return original(intent)

    monkeypatch.setattr(owner.storage, "execute", wait_for_first)
    handle = owner.submit(one)
    try:
        assert entered.wait(3) and persisted_pending(one.document_id) == one.identity
        assert owner.submit(one) is handle
        with pytest.raises(RuntimeFailure, match="^document_busy$"):
            owner.submit(conflict)
        with pytest.raises(RuntimeFailure, match="^writer_not_stopped$"):
            owner.recover(one.document_id)
        assert owner.submit(two).wait(3).checkpoint_closed
        assert counts(engine, one.document_id) == (1, 0)
    finally:
        release.set()
    assert handle.wait(5).checkpoint_closed
    assert calls == [] and counts(engine, one.document_id) == counts(engine, two.document_id) == (2, 1)


def test_new_connection_and_process_read_pending_without_inventing_writer_death(runtime_factory, engine):
    original_owner, _, observed, calls = runtime_factory()
    value = prepare(original_owner)
    observed.lose, observed.unreadable_after_loss = "admit", True
    assert original_owner.submit(value).wait(5).error == "checkpoint_unavailable"
    other, _, _, other_calls = runtime_factory()
    assert other.checkpoints.read(value.document_id) == value.identity
    with pytest.raises(RuntimeFailure, match="^writer_not_stopped$"):
        other.recover(value.document_id)
    with pytest.raises(RuntimeFailure, match="^document_busy$"):
        other.submit(value)
    assert other.status(value.document_id).write_blocked
    code = '''
import json, sys
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import StateGraph, MessagesState, START, END
from psycopg import Connection
from psycopg.rows import dict_row
from jd_relational.runtime_checkpoints import build_document_graph, DocumentCheckpoints
def forbidden(state): raise AssertionError("Reader must not invoke or resume graph.")
child = StateGraph(MessagesState)
child.add_node("synthetic", forbidden)
child.add_edge(START, "synthetic")
child.add_edge("synthetic", END)
with Connection.connect(host="127.0.0.1", port=55436, dbname="caliburn_jd_relational_test",
    user="jd_test", password="jd-local-test-only", connect_timeout=5,
    options="-csearch_path=jd_runtime_test,public", autocommit=True, row_factory=dict_row,
    prepare_threshold=0) as conn:
    conn.execute("SET default_transaction_read_only = on")
    graph = build_document_graph(child.compile(), PostgresSaver(conn,
        serde=JsonPlusSerializer(allowed_msgpack_modules=None)))
    pending = DocumentCheckpoints(graph).read(sys.argv[1])
    count = conn.execute("SELECT count(*) AS n FROM public.jd_operation WHERE document_id = %s",
                         (sys.argv[1],)).fetchone()["n"]
    print(json.dumps({"operation":str(pending.operation_id), "digest":pending.request_digest,
                      "origin":pending.origin, "run":pending.ai_run_id, "receipts":count}))
'''
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    process = subprocess.run([sys.executable, "-c", code, value.document_id],
        env=env, capture_output=True, text=True, timeout=15)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == {"operation": str(value.operation_id), "digest": value.request_digest,
        "origin": "manual", "run": None, "receipts": 0}
    assert calls == other_calls == [] and counts(engine, value.document_id) == (1, 0)
    # This original process knows it never scheduled SQL. A fresh owner did not.
    observed.unreadable = False
    assert original_owner.recover(value.document_id, timeout=5).observation.status == "save_failed"
