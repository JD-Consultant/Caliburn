"""Synthetic dedicated Windows AI host; never a product endpoint or initializer.

All SDK traffic uses the existing MockTransport fixture. Restart uses the real
native inspection Agent, HostLease and PG Saver. CRASH is an owned self-exit,
not a claim that a timeout killed another process or a surviving child group.
"""

from contextlib import ExitStack
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from threading import Event, local
import traceback
from uuid import UUID, uuid4

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import START
import pytest
import sqlalchemy as sa

from jd_relational.ai_checkpoints import AiRunCheckpoints
from jd_relational.ai_runtime import AiRuntime
from jd_relational.consultant_context import build_consultant_node
from jd_relational.consultant_tools import AiToolMiddleware, AiToolSession, build_jd_tools
from jd_relational.host_runtime import open_manual_host
from jd_relational.inspection_model import build_inspection_consultant_node
from jd_relational.references import ReferenceCodec
from jd_relational.storage import schema as db
from jd_relational.storage.service import JdStorage
from test_ai_runtime_postgres import _create, _final, _last_page, _offline_model, _read, _task_field


SCHEMA = "jd_ai_host_test"
INSTALLATION = "bbbe5c26-462b-48de-a937-975891920f54"
DATASET = "079d33f1-5b44-497e-b6c6-33cfd8da09b9"
SIGNER = b"synthetic-ai-host-fixed-signing-key"
WORKER_CRASH_CODE = 73
DATABASE_URL = "postgresql+psycopg://jd_test:jd-local-test-only@127.0.0.1:55436/caliburn_jd_relational_test"


def write(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, default=str), encoding="utf-8")
    temporary.replace(path)


def _receipt(value):
    if value is None:
        return None
    result = asdict(value)
    result["body"] = value.body.model_dump(mode="json")
    return json.loads(json.dumps(result, default=str))


def state(host, document):
    current = host.runtime.storage.read_current(document)
    observed = AiRunCheckpoints(host.graph).discover(document, DATASET)
    latest = host.graph.get_state({"configurable": {"thread_id": document}}, subgraphs=True)
    # An unpinned latest snapshot may overlay pending START writes. Report the
    # same exact saved root selected by the production observer, not that view.
    fixed_config = observed.root_config if observed is not None else latest.config
    fixed = (host.graph.get_state(fixed_config, subgraphs=True)
             if fixed_config and fixed_config.get("configurable", {}).get("checkpoint_id") else latest)
    with host.engine.connect() as conn:
        revisions = conn.execute(sa.select(sa.func.count()).select_from(db.jd_revision).where(
            db.jd_revision.c.document_id == document)).scalar_one()
        operation_ids = conn.execute(sa.select(db.jd_operation.c.operation_id).where(
            db.jd_operation.c.document_id == document).order_by(db.jd_operation.c.created_at,
                db.jd_operation.c.operation_id)).scalars().all()
    ai = None if observed is None else {
        "record": observed.record.model_dump(mode="json"), "closed": observed.closed,
        "messages": [m.model_dump(mode="json") for m in observed.messages],
        "bindings": observed.bindings, "model_view": observed.model_view,
        "read_binding": observed.read_binding, "root_config": observed.root_config,
        "source_config": observed.source_config}
    return {"document_id": document, "snapshot": current.snapshot,
        "revision_id": str(current.revision_id), "revision_number": current.revision_number,
        "archived": current.archived, "revision_count": revisions,
        "receipts": [_receipt(host.runtime.storage.get_operation(document, UUID(str(op)))) for op in operation_ids],
        "ai": ai, "root_next": list(fixed.next),
        "root_config": fixed.config, "root_metadata": fixed.metadata}


def _second_write(payload):
    return "jd_set_text", {"target_field_ref": _task_field(_last_page(payload), "description")["field_ref"],
        "text": "僅檢查約定設備；異常時交接，不維修外包設備。", "basis_refs": []}


def _guard_counters(monkeypatch, counts):
    def no_setup(*args, **kwargs):
        counts["setup"] += 1
        raise AssertionError("setup_forbidden")
    monkeypatch.setattr(PostgresSaver, "setup", no_setup)
    original_tool = AiToolSession.execute
    def counted_tool(self, name, arguments, runtime):
        counts["tools"] += 1
        return original_tool(self, name, arguments, runtime)
    monkeypatch.setattr(AiToolSession, "execute", counted_tool)


def main(mode, manifest, report):
    if sys.platform != "win32" or os.environ.get("JD_RELATIONAL_TEST_DB") != "1":
        raise RuntimeError("explicit_isolated_windows_postgres_opt_in_required")
    common = {"pid": os.getpid(), "parent_pid": os.getppid(),
              "installation_id": INSTALLATION, "dataset_id": DATASET, "schema": SCHEMA}
    write(report.with_suffix(".boot.json"), common)
    counts = {"model": 0, "tools": 0, "execute": 0, "setup": 0}
    release, entered, start_entered = Event(), Event(), Event()
    handles, documents, witness = [], [], {}
    with ExitStack() as stack:
        monkeypatch = stack.enter_context(pytest.MonkeyPatch.context())
        _guard_counters(monkeypatch, counts)
        if mode == "contend":
            import jd_relational.host_runtime as host_module
            attempts = []
            def forbidden(*args, **kwargs):
                attempts.append(1)
                raise AssertionError("busy_host_reached_db")
            monkeypatch.setattr(host_module.sa, "create_engine", forbidden)
            monkeypatch.setattr(host_module.Connection, "connect", forbidden)
            try:
                open_manual_host(INSTALLATION, DATABASE_URL, checkpoint_schema=SCHEMA,
                                 consultant=build_inspection_consultant_node())
            except Exception as error:
                write(report, {**common, "event": "blocked", "error": getattr(error, "code", type(error).__name__),
                    "db_attempts": len(attempts), "counts": counts})
                return
            raise AssertionError("live_host_admitted_contender")

        requests = []
        if mode == "recover":
            from jd_relational.inspection_model import InspectionGuard, InspectionOnly
            def no_model(*args, **kwargs):
                counts["model"] += 1
                raise AssertionError("recovery_model_forbidden")
            def no_tool(*args, **kwargs):
                counts["tools"] += 1
                raise AssertionError("recovery_tool_forbidden")
            def no_execute(*args, **kwargs):
                counts["execute"] += 1
                raise AssertionError("recovery_execute_forbidden")
            monkeypatch.setattr(InspectionOnly, "_generate", no_model)
            monkeypatch.setattr(InspectionGuard, "wrap_model_call", no_model)
            monkeypatch.setattr(InspectionGuard, "wrap_tool_call", no_tool)
            monkeypatch.setattr(JdStorage, "execute", no_execute)
            child = build_inspection_consultant_node()
        else:
            plans = {"normal": [_read, _create, _final], "sql_pending": [_read, _create],
                "commit_loss": [_read, _create, _read, _second_write],
                "two_boundaries": [_final, _read, _create]}
            model, requests = stack.enter_context(_offline_model(monkeypatch, plans[mode]))
            child = build_consultant_node(model, tools=build_jd_tools(),
                guidance="合成重啟驗收；只記錄員工描述的真實工作。", extra_middleware=[AiToolMiddleware()])
        host = open_manual_host(INSTALLATION, DATABASE_URL, checkpoint_schema=SCHEMA, consultant=child)
        runtime = AiRuntime(host.runtime, ReferenceCodec(SIGNER, DATASET))
        ready_before = host.runtime.ready
        assert ready_before is False
        recovered = host.runtime.finish_startup(timeout=30)
        assert host.runtime.ready
        if mode == "recover":
            original = json.loads(manifest.read_text(encoding="utf-8"))
            assert original["dataset_id"] == DATASET and original["installation_id"] == INSTALLATION
            documents = [row["document_id"] for row in original["documents"]]
            write(report, {**common, "event": "recovered", "ready_before": ready_before,
                "ready_after": host.runtime.ready, "recovered_count": recovered,
                "counts": counts, "documents": [state(host, doc) for doc in documents]})
        else:
            assert recovered == 0, "previous_scenario_requires_recovery_first"
            document = host.runtime.create_document(uuid4(), "合成 AI 宿主重啟工作")
            documents.append(document)
            original_execute = host.runtime.storage.execute
            active = local()
            def counted_execute(intent):
                counts["execute"] += 1
                active.intent, active.index = intent, counts["execute"]
                try:
                    return original_execute(intent)
                finally:
                    active.intent = None
            monkeypatch.setattr(host.runtime.storage, "execute", counted_execute)
            original_commit = host.engine.dialect.do_commit
            if mode in {"sql_pending", "commit_loss"}:
                def fault_commit(connection):
                    intent = getattr(active, "intent", None)
                    if intent is not None and mode == "sql_pending":
                        # This same actual SQL transaction sees the candidate and
                        # receipt before commit; another connection cannot see it.
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT count(*) FROM public.jd_revision WHERE document_id=%s", (document,))
                            witness["transaction_revision_count"] = cursor.fetchone()[0]
                            cursor.execute("SELECT count(*) FROM public.jd_operation WHERE document_id=%s", (document,))
                            witness["transaction_operation_count"] = cursor.fetchone()[0]
                            cursor.execute("SELECT pg_backend_pid()")
                            witness["transaction_backend_pid"] = cursor.fetchone()[0]
                        witness["identity"] = asdict(intent.identity)
                        entered.set()
                        assert release.wait(90), "owned_sql_barrier_expired"
                    result = original_commit(connection)
                    if intent is not None and mode == "commit_loss" and active.index == 2:
                        witness["identity"] = asdict(intent.identity)
                        witness["real_commit_ack_lost"] = True
                        raise OSError("synthetic_commit_ack_lost")
                    return result
                monkeypatch.setattr(host.engine.dialect, "do_commit", fault_commit)
            if mode == "commit_loss":
                def suppress_local_closure(attempt):
                    # Test fault after the real Agent Future ends, before any
                    # coordinator reconciliation. New host must do the work.
                    witness["local_closure_suppressed"] = True
                    entered.set()
                monkeypatch.setattr(runtime, "_finish_automatically", suppress_local_closure)
            if mode == "two_boundaries":
                second = host.runtime.create_document(uuid4(), "合成 START 保留先前問答")
                documents.append(second)
                previous = runtime.start(second, str(uuid4()), "先前已完成原話；不得刪除。\r\n  保留空白😀")
                assert previous.wait(20).status == "completed"
                witness["previous_second"] = state(host, second)["ai"]
                original_put = host.graph.checkpointer.put
                def pause_checkpoint(config, checkpoint, metadata, new_versions):
                    scope = config["configurable"]
                    if (scope["thread_id"] == second and not scope.get("checkpoint_ns")
                            and metadata.get("source") == "loop"):
                        # Original native input put has completed; first loop
                        # put has not. The real Agent has not reached its model.
                        start_entered.set()
                        assert release.wait(90), "owned_start_barrier_expired"
                    result = original_put(config, checkpoint, metadata, new_versions)
                    if (scope["thread_id"] == document and scope.get("checkpoint_ns", "").startswith("consultant:")
                            and checkpoint["channel_values"].get("jd_ai_bindings") and not entered.is_set()):
                        witness["after_model_binding_put_confirmed"] = True
                        entered.set()
                        assert release.wait(90), "owned_binding_barrier_expired"
                    return result
                monkeypatch.setattr(host.graph.checkpointer, "put", pause_checkpoint)
            handles.append(runtime.start(document, str(uuid4()), "收到通知檢查約定設備，留下記錄並交接異常；不修理外包設備。"))
            if mode == "normal":
                assert handles[0].wait(25).status == "completed"
                archived = host.runtime.create_document(uuid4(), "合成封存空稿")
                host.runtime.update_catalog(archived, 1, archived=True)
                documents.append(archived)
            else:
                assert entered.wait(25), "requested_fault_boundary_not_reached"
                if mode == "two_boundaries":
                    handles.append(runtime.start(second, str(uuid4()), "新回合尚未進模型的完整原話。\r\n原樣保留😀"))
                    assert start_entered.wait(15), "native_start_boundary_not_reached"
                    latest = host.graph.get_state({"configurable": {"thread_id": second}}, subgraphs=True)
                    saved = host.graph.checkpointer.get_tuple(latest.config)
                    assert saved.metadata["source"] == "input" and START in saved.checkpoint["channel_values"]
                    incoming = saved.checkpoint["channel_values"][START]
                    witness["native_start"] = {"checkpoint_id": saved.checkpoint["id"],
                        "record": incoming["jd_ai_run"],
                        "messages": [m.model_dump(mode="json") for m in incoming["messages"]]}
            counts["model"] = len(requests)
            original = {**common, "mode": mode, "counts": counts, "witness": witness,
                        "documents": [state(host, doc) for doc in documents]}
            write(manifest, original)
            write(report, {**common, "event": "completed" if mode == "normal" else "pending",
                "original_recovered": recovered, "counts": counts, "witness": witness})
        command = sys.stdin.readline().strip()
        if command == "CRASH":
            os._exit(WORKER_CRASH_CODE)  # Owned actual process, no graceful SQL/Saver cleanup.
        if command != "STOP":
            raise AssertionError("unknown_test_control")
        release.set()
        for handle in handles:
            try:
                handle.wait(10)
            except Exception:
                pass  # Final close, not wait(), owns the resource-safety verdict.
        closed = host.close(timeout=10)
        write(report.with_suffix(".finished.json"), {**common, "closed": closed, "counts": counts})
        assert closed, "owned_host_did_not_drain"


if __name__ == "__main__":
    report = Path(sys.argv[3])
    try:
        main(sys.argv[1], Path(sys.argv[2]), report)
    except BaseException as error:
        # Safe diagnostic locations only: no exception repr, SQL parameters,
        # provider settings, original request content or external credentials.
        write(report, {"pid": os.getpid(), "parent_pid": os.getppid(), "event": "error",
            "error": getattr(error, "code", type(error).__name__),
            "locations": [{"file": Path(frame.filename).name, "line": frame.lineno, "name": frame.name}
                          for frame in traceback.extract_tb(error.__traceback__)]})
        os._exit(1)
