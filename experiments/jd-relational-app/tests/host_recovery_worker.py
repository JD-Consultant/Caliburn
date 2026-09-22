"""Test-only dedicated host. CRASH/STOP controls are never product endpoints."""

from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from threading import Event
import traceback
from uuid import UUID, uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph
import sqlalchemy as sa

from jd_relational.host_runtime import open_manual_host
from jd_relational.intents import bind_edit
from jd_relational.reads import ReadService, command_context
from jd_relational.references import ReferenceCodec
from jd_relational.storage import schema as db
from jd_relational.storage.history import HistoryReader


SCHEMA = "jd_host_test"
WORKER_CRASH_CODE = 73
DATABASE_URL = "postgresql+psycopg://jd_test:jd-local-test-only@127.0.0.1:55436/caliburn_jd_relational_test"


def write(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def child_graph():
    def forbidden(state):
        raise AssertionError("Host recovery must not invoke a consultant or model.")
    child = StateGraph(MessagesState)
    child.add_node("synthetic", forbidden)
    child.add_edge(START, "synthetic")
    child.add_edge("synthetic", END)
    return child.compile()


def original_receipt(receipt):
    if receipt is None:
        return None
    result = asdict(receipt)
    result["body"] = receipt.body.model_dump(mode="json")
    for key in ("operation_id", "base_revision_id", "result_revision_id"):
        result[key] = str(result[key]) if result[key] is not None else None
    result["created_at"] = result["created_at"].isoformat()
    return result


def state(host, document, operation):
    storage = host.runtime.storage
    current = storage.read_current(document)
    messages = host.graph.get_state({"configurable": {"thread_id": document}}).values.get("messages", [])
    with host.engine.connect() as conn:
        counts = {table.name: conn.execute(sa.select(sa.func.count()).select_from(table).where(
            table.c.document_id == document)).scalar_one() for table in (db.jd_revision, db.jd_operation)}
    pending = host.checkpoints.read(document)
    return {"document_id": document, "snapshot": current.snapshot, "archived": current.archived,
            "messages": [message.model_dump(mode="json") for message in messages],
            "receipt": original_receipt(storage.get_operation(document, operation)),
            "pending": str(pending.operation_id) if pending else None,
            "revision_count": counts["jd_revision"], "operation_count": counts["jd_operation"]}


def prepare(host, *, archived=False):
    storage = host.runtime.storage
    document = storage.create_document(uuid4(), "合成 Windows 重啟工作")
    current = storage.read_current(document)
    codec = ReferenceCodec(b"synthetic-host-recovery-signing-key", "synthetic-host-recovery")
    page = ReadService(storage, HistoryReader(host.engine), codec).read(document,
        {"view": "current", "target_ref": None, "cursor": None})
    field = next(row for row in page["records"] if row["type"] == "field" and row["name"] == "purpose")
    command = {"tool": "jd_set_text", "arguments": {"target_field_ref": field["field_ref"],
        "text": "繁中原次工作😀\n保留精確原文與空白  ", "basis_refs": []}}
    def no_sources(*args):
        raise AssertionError("Empty source list must not invoke a source owner.")
    context = command_context(current.domain, command, codec, no_sources, lambda: str(uuid4()))
    intent = bind_edit(uuid4(), "manual", None, command, context)
    messages = [HumanMessage(content="原始員工問答\n不得回退", id="original-human"),
        AIMessage(content=[{"type": "reasoning", "encrypted_content": "synthetic-opaque"},
                           {"type": "compaction", "encrypted_content": "synthetic-compaction"},
                           {"type": "text", "text": "原始顧問內容"}], id="original-assistant",
                  tool_calls=[{"name": "synthetic", "args": {"keep": True}, "id": "original-call", "type": "tool_call"}]),
        ToolMessage(content="原始工具結果", tool_call_id="original-call", id="original-tool")]
    host.graph.update_state({"configurable": {"thread_id": document}}, {"messages": messages}, as_node="consultant")
    if archived:
        # Isolated fixture construction only; exercise startup's all-catalog
        # obligation even for a restored/archived root with pending metadata.
        with host.engine.begin() as conn:
            conn.execute(db.jd_document.update().where(db.jd_document.c.id == document).values(archived=True))
    return intent


def main(mode, installation, manifest, report):
    if sys.platform != "win32" or os.environ.get("JD_RELATIONAL_TEST_DB") != "1":
        raise RuntimeError("explicit isolated Windows/PostgreSQL opt-in required")
    common = {"pid": os.getpid(), "parent_pid": os.getppid()}
    write(report.with_suffix(".boot.json"), common)
    if mode == "contend":
        from unittest.mock import patch
        import jd_relational.host_runtime as module
        attempts = []
        def forbidden(*args, **kwargs):
            attempts.append("attempted")
            raise AssertionError("Busy second host must be refused before opening DB resources.")
        with patch.object(module.sa, "create_engine", forbidden), patch.object(module.Connection, "connect", forbidden):
            try:
                module.open_manual_host(installation, DATABASE_URL, checkpoint_schema=SCHEMA, consultant=child_graph())
            except Exception as error:
                write(report, {**common, "event": "blocked", "error": getattr(error, "code", type(error).__name__),
                               "db_attempts": len(attempts)})
                return
        raise AssertionError("A live installation admitted a second host")

    host = open_manual_host(installation, DATABASE_URL, checkpoint_schema=SCHEMA, consultant=child_graph())
    ready_before = host.runtime.ready
    assert ready_before is False
    recovered = host.runtime.finish_startup(timeout=30)
    assert host.runtime.ready
    release, handles = Event(), []
    if mode == "recover":
        original = json.loads(manifest.read_text(encoding="utf-8"))
        rows = [state(host, row["identity"]["document_id"], UUID(row["identity"]["operation_id"]))
                for row in original["documents"]]
        write(report, {**common, "event": "recovered", "ready_before": ready_before,
                       "ready_after": host.runtime.ready, "recovered_count": recovered, "documents": rows})
    else:
        assert recovered == 0, "Test host schema must have no unresolved descriptor from another scenario."
        intents = [prepare(host)]
        if mode == "two_pending":
            intents.append(prepare(host, archived=True))
        entered = {intent.operation_id: Event() for intent in intents}
        original_execute = host.runtime.storage.execute
        if mode in {"before_sql", "two_pending"}:
            def blocked_execute(intent):
                entered[intent.operation_id].set()
                assert release.wait(90), "Harness must stop or release its own worker."
                return original_execute(intent)
            host.runtime.storage.execute = blocked_execute
            handles = [host.runtime.submit(intent) for intent in intents]
            assert all(event.wait(10) for event in entered.values())
            effect = "not_submitted"
        else:
            assert mode == "commit_loss"
            actual_commit, commits = host.engine.dialect.do_commit, []
            def lost_commit(connection):
                actual_commit(connection)
                commits.append(True)
                raise OSError("synthetic commit acknowledgement lost")
            def uncertain_execute(intent):
                host.engine.dialect.do_commit = lost_commit
                try:
                    return original_execute(intent)
                finally:
                    host.engine.dialect.do_commit = actual_commit
            host.runtime.storage.execute = uncertain_execute
            handle = host.runtime.submit(intents[0])
            result = handle.wait(10)
            assert commits and result.observation is not None and not result.observation.confirmed
            assert result.observation.unresolved_effect == "unknown" and not result.checkpoint_closed
            effect = result.observation.unresolved_effect
        rows = []
        for intent in intents:
            row = state(host, intent.document_id, intent.operation_id)
            assert row["pending"] == str(intent.operation_id)
            identity = asdict(intent.identity)
            for key in ("operation_id", "base_revision_id"):
                identity[key] = str(identity[key])
            rows.append({**row, "identity": identity})
        write(manifest, {"documents": rows})
        write(report, {**common, "event": "pending", "effect": effect, "original_recovered": recovered})

    command = sys.stdin.readline().strip()
    if command == "CRASH":
        os._exit(WORKER_CRASH_CODE)  # Abrupt self-exit: no Python cleanup or runtime proof injection.
    if command not in {"COMPLETE", "STOP", ""}:
        raise AssertionError("Unexpected test-only command")
    release.set()
    statuses = [handle.wait(10).observation.status for handle in handles]
    closed = host.close(timeout=10)
    write(report.with_suffix(".finished.json"), {**common, "closed": closed, "statuses": statuses})
    assert closed


if __name__ == "__main__":
    assert len(sys.argv) == 5
    mode, installation, manifest, report = sys.argv[1:]
    try:
        main(mode, installation, Path(manifest), Path(report))
    except BaseException as error:
        write(Path(report), {"pid": os.getpid(), "parent_pid": os.getppid(), "event": "worker_failed",
              "error": getattr(error, "code", type(error).__name__),
              "line": traceback.extract_tb(error.__traceback__)[-1].lineno})
        raise
