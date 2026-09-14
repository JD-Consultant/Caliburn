"""Real PG/Saver/Store and SDK wire; fixed responses, zero provider calls.

Memory publishing here is a test fixture, not model B1/B2/C execution. Resource
reopen uses new connections in this process, not a foreign-host death proof.
"""
from contextlib import contextmanager
import json
import os
from threading import Event
from uuid import uuid4

from caliburn_memory import MemoryArtifacts, PublicationStore
from caliburn_memory.publication import PublicationUncertain
from caliburn_memory.repair import RepairWorkflow
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.store.postgres import PostgresStore
from psycopg import Connection
from psycopg.rows import dict_row
import pytest

from jd_relational.ai_checkpoints import AiRunCheckpoints
from jd_relational.ai_runtime import AiRuntime, AiRuntimeError
from jd_relational.consultant_context import build_consultant_node
from jd_relational.consultant_tools import AiToolMiddleware
from jd_relational.conversation_sources import ConversationSourceCodec, ConversationSourceService
from jd_relational.inspection_model import build_inspection_consultant_node
from jd_relational.manual_runtime import ManualRuntime
from jd_relational.memory_context import build_consultant_tools
from jd_relational.memory_repair_session import MemoryRepairSession
from jd_relational.memory_sources import MemorySourceReader
from jd_relational.references import ReferenceCodec
from jd_relational.runtime_checkpoints import DocumentCheckpoints, build_document_graph
from jd_relational.storage.service import JdStorage
from test_ai_runtime_postgres import _create, _failure, _final, _offline_model, _read, _state
from test_manual_runtime_postgres import connect
from test_memory_core_postgres import SCHEMA, TABLES
from test_storage_postgres import engine

pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")
KEY = b"synthetic-memory-tools-key-32-bytes"


@contextmanager
def opened(engine, model, dataset):
    with connect() as saver_connection, Connection.connect(host="127.0.0.1", port=55436,
        dbname="caliburn_jd_relational_test", user="jd_test", password="jd-local-test-only",
        options=f"-csearch_path={SCHEMA},public", connect_timeout=5,
        autocommit=True, row_factory=dict_row, prepare_threshold=0) as store_connection:
        assert store_connection.execute("SELECT current_database() AS db, current_user AS usr, "
            "current_setting('server_version_num')::integer AS version").fetchone() == {
                "db": "caliburn_jd_relational_test", "usr": "jd_test", "version": 180006}
        assert {row["tablename"] for row in store_connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname=%s", (SCHEMA,))} == TABLES
        store = PostgresStore(store_connection)
        saver = PostgresSaver(saver_connection, serde=JsonPlusSerializer(allowed_msgpack_modules=None))
        child = (build_inspection_consultant_node() if model is None else build_consultant_node(
            model, tools=build_consultant_tools(), guidance="合成驗收：核對原話後撰寫真實工作。",
            extra_middleware=[AiToolMiddleware()]))
        graph = build_document_graph(child, saver, store=store)
        owner = ManualRuntime(DocumentCheckpoints(graph), lambda authority: JdStorage(engine, authority), max_workers=2)
        codec = ReferenceCodec(KEY, dataset)
        sources = ConversationSourceService(AiRunCheckpoints(graph), ConversationSourceCodec(KEY, dataset))
        memory_engine = engine.execution_options(schema_translate_map={None: SCHEMA})
        runtime = AiRuntime(owner, codec, conversation_sources=sources, memory_engine=memory_engine,
                            execution_enabled=model is not None)
        try:
            yield runtime, owner, graph, store, memory_engine, sources
        finally:
            assert owner.close(timeout=10)


def notice(payload):
    candidates = []
    for block in payload["system"]:
        try: value = json.loads(block["text"])
        except (ValueError, KeyError): continue
        if isinstance(value, dict) and value.get("type") == "memory_guide": candidates.append(value)
    assert len(candidates) == 1
    return candidates[0]


def conversation_notice(payload):
    candidates = []
    for block in payload["system"]:
        try: value = json.loads(block["text"])
        except (ValueError, KeyError): continue
        if isinstance(value, dict) and value.get("type") == "conversation_source_notice":
            candidates.append(value)
    assert len(candidates) == 1
    return candidates[0]


def last_tool(payload):
    return [block for message in payload["messages"] if isinstance(message["content"], list)
        for block in message["content"] if block["type"] == "tool_result"][-1]["content"]


def test_sdk_reads_fixed_memory_summary_original_then_writes_and_reopens(monkeypatch, engine):
    dataset = str(uuid4())
    fixture = {}
    def publish_later(payload):
        assert notice(payload)["revision"] == 1
        fixture["publish"](1, "只做檢查；維修由外包負責。")
        return "read_file", {"file_path": "/memory/knowledge.md", "offset": 0, "limit": 100}
    def read_summary(payload):
        assert "收到通知後檢查約定設備" in last_tool(payload)
        assert "維修由外包" not in last_tool(payload)
        return "read_file", {"file_path": fixture["summary"], "offset": 0, "limit": 100}
    def read_original(payload):
        assert "合成詳記" in last_tool(payload)
        return "read_conversation", {"reference": fixture["summary"], "offset": 0, "part": "source"}
    def check_original_then_jd(payload):
        page = json.loads(last_tool(payload))
        assert page["reference"] == fixture["source"] and page["next_offset"] is None
        assert page["segments"] == [{"message_id": fixture["first_run"], "role": "user",
            "text": fixture["original"], "text_offset": 0}]
        return _read(payload)
    def create(payload):
        name, args = _create(payload)
        args["basis_refs"] = [fixture["source"]]
        return name, args
    def read_latest(payload):
        assert notice(payload)["revision"] == 2 and "維修由外包" in notice(payload)["guide"]
        return "read_file", {"file_path": "/memory/knowledge.md", "offset": 0, "limit": 100}
    def latest_final(payload):
        assert "維修由外包" in last_tool(payload)
        return _final(payload)
    plan = [_final, publish_later, read_summary, read_original, check_original_then_jd,
            create, _final, read_latest, latest_final]
    with _offline_model(monkeypatch, plan, expected_tools=build_consultant_tools()) as (model, requests):
        with opened(engine, model, dataset) as (runtime, owner, graph, store, memory_engine, sources):
            document = owner.create_document(uuid4(), "合成Memory按需讀取驗收")
            fixture["first_run"] = str(uuid4())
            fixture["original"] = "收到通知後檢查約定設備。\r\n  先確認隔離，留檢查記錄並交接異常。"
            base = owner.storage.read_current(document).revision_id
            first = runtime.start(document, fixture["first_run"], fixture["original"], expected_revision_id=base)
            assert first.wait(20).status == "completed", _failure(first)
            assert notice(requests[0])["published"] is False
            fixture["source"] = sources.capture(document, fixture["first_run"]).source_ref
            artifacts = MemoryArtifacts(store, document, source=MemorySourceReader(sources, document))
            pub = PublicationStore(memory_engine, artifacts)
            files = artifacts.save_extraction(summary="合成詳記：收到通知檢查約定設備。", candidates="合成候選",
                slug="約定設備", source_reference=fixture["source"])
            fixture["summary"] = files.summary_path
            def publish(expected, text):
                version = artifacts.save_memory(knowledge=f"{text}\n[詳記]({files.summary_path})",
                    guide=f"{text}→[詳記]({files.summary_path})")
                return pub.publish(pub.prepare(version, expected_revision=expected,
                    kind="consolidation", processed_source=fixture["source"]))
            fixture["publish"] = publish
            first_head = publish(0, "收到通知後檢查約定設備。")
            second_run = str(uuid4())
            second = runtime.start(document, second_run, "請先核對早期工作，再整理JD。", expected_revision_id=base)
            assert second.wait(30).status == "completed", _failure(second)
            assert len(requests) == 7
            assert all(notice(p)["revision"] == 1 for p in requests[1:])
            saved = _state(graph, document)
            assert saved.values["jd_memory_view"]["version_id"] == first_head.memory.version_id
            assert len(saved.values["jd_ai_bindings"]) == 1
            current = owner.storage.read_current(document)
            assert current.revision_number == 2 and len(current.domain["tasks"]) == 1
            third_run = str(uuid4())
            third = runtime.start(document, third_run, "維修由外包負責，請記得這個界線。",
                expected_revision_id=current.revision_id)
            assert third.wait(20).status == "completed", _failure(third)
            original_observation = runtime.checkpoints.observe(document, third_run, dataset)
            original_messages = original_observation.messages
            original_view = original_observation.memory_view
            assert original_view["revision"] == 2 and len(requests) == 9
            assert owner.storage.read_current(document).revision_id == current.revision_id
        with opened(engine, None, dataset) as (runtime, owner, graph, store, _, sources):
            def no_read(*args, **kwargs): pytest.fail("recovery must not reread Memory or replay tools")
            monkeypatch.setattr(store, "get", no_read)
            recovered = runtime.checkpoints.observe(document, third_run, dataset)
            assert recovered.messages == original_messages and recovered.memory_view == original_view
            assert runtime.lookup(document, third_run).wait().status == "completed"
            assert sources.read(fixture["source"], document).messages[0].text == fixture["original"]
            assert len(requests) == 9


def test_sdk_repairs_memory_from_this_turn_then_reads_the_applied_version(monkeypatch, engine):
    dataset = str(uuid4())
    fixture = {}

    def repair(payload):
        assert notice(payload)["revision"] == 1
        source = conversation_notice(payload)
        assert source["messages"][-1] == {"message_id": fixture["run"], "role": "user"}
        fixture["repair_source"] = source["source_ref"]
        return "repair_memory", {"edits": [{"path": "/memory/knowledge.md",
            "diff": "@@\n-只做初步確認。\n+只通報異常，維修由外包負責。"}]}

    def read_applied(payload):
        result = json.loads(last_tool(payload))
        assert result["status"] == "applied" and result["retryable"] is False
        assert "operation_id" not in result
        return "read_file", {"file_path": "/memory/knowledge.md", "offset": 0, "limit": 100}

    def finish(payload):
        assert "只通報異常，維修由外包負責。" in last_tool(payload)
        return _final(payload)

    with _offline_model(monkeypatch, [_final, repair, read_applied, finish], expected_tools=build_consultant_tools()) as (model, requests):
        with opened(engine, model, dataset) as (runtime, owner, graph, store, memory_engine, sources):
            document = owner.create_document(uuid4(), "合成本輪Memory更正")
            first_run = str(uuid4())
            current = owner.storage.read_current(document)
            assert runtime.start(document, first_run, "我只做初步確認。",
                expected_revision_id=current.revision_id).wait(20).status == "completed"
            original_source = sources.capture(document, first_run).source_ref
            artifacts = MemoryArtifacts(store, document, source=MemorySourceReader(sources, document))
            publication = PublicationStore(memory_engine, artifacts)
            version = artifacts.save_memory(knowledge="只做初步確認。", guide="初步確認")
            publication.publish(publication.prepare(version, expected_revision=0,
                kind="consolidation", processed_source=original_source))

            fixture["run"] = str(uuid4())
            result = runtime.start(document, fixture["run"], "更正：我只通報異常，維修由外包負責。",
                expected_revision_id=current.revision_id).wait(30)
            assert result.status == "completed" and len(requests) == 4
            assert publication.current().revision == 2
            observed = runtime.checkpoints.observe(document, fixture["run"], dataset)
            assert observed.memory_view["revision"] == 1 and len(observed.repair_bindings) == 1
            binding = observed.repair_bindings[0]
            assert binding["source_reference"] == fixture["repair_source"] != original_source
            excerpt = sources.read(fixture["repair_source"], document)
            assert excerpt.messages[-1].message_id == fixture["run"]
            repair_message = next(m for m in observed.messages
                if isinstance(m, ToolMessage) and m.name == "repair_memory")
            assert repair_message.artifact["request"]["repair_sources"] == [fixture["repair_source"]]
            assert owner.storage.read_current(document).revision_id == current.revision_id


def test_repair_commit_reply_loss_reconciles_original_request_without_replay(monkeypatch, engine):
    dataset = str(uuid4())
    fixture = {}

    def repair(payload):
        fixture["source"] = conversation_notice(payload)["source_ref"]
        return "repair_memory", {"edits": [{"path": "/memory/knowledge.md",
            "diff": "@@\n-原本只檢查。\n+只通報異常，維修由外包負責。"}]}

    with _offline_model(monkeypatch, [_final, repair], expected_tools=build_consultant_tools()) as (model, requests):
        with opened(engine, model, dataset) as (runtime, owner, graph, store, memory_engine, sources):
            document = owner.create_document(uuid4(), "合成Memory提交回覆遺失")
            first_run = str(uuid4())
            current = owner.storage.read_current(document)
            assert runtime.start(document, first_run, "原本只檢查。",
                expected_revision_id=current.revision_id).wait(20).status == "completed"
            original_source = sources.capture(document, first_run).source_ref
            artifacts = MemoryArtifacts(store, document, source=MemorySourceReader(sources, document))
            publication = PublicationStore(memory_engine, artifacts)
            version = artifacts.save_memory(knowledge="原本只檢查。", guide="原本只檢查")
            publication.publish(publication.prepare(version, expected_revision=0,
                kind="consolidation", processed_source=original_source))

            original_publish = PublicationStore.publish
            calls = []
            def commit_then_lose_reply(instance, request):
                result = original_publish(instance, request)
                if request.kind == "repair":
                    calls.append(request.operation_id)
                    raise PublicationUncertain("synthetic lost commit reply")
                return result
            monkeypatch.setattr(PublicationStore, "publish", commit_then_lose_reply)
            fixture["run"] = str(uuid4())
            result = runtime.start(document, fixture["run"],
                "更正：我只通報異常，維修由外包負責。",
                expected_revision_id=current.revision_id).wait(30)
            assert result.status == "failed" and result.input_saved and result.response_message_id is None
            assert len(calls) == 1 and len(requests) == 2 and publication.current().revision == 2
            observed = runtime.checkpoints.observe(document, fixture["run"], dataset)
            repair_message = next(m for m in observed.messages
                if isinstance(m, ToolMessage) and m.name == "repair_memory")
            assert observed.closed and repair_message.status == "success"
            assert repair_message.artifact["request"]["operation_id"] == calls[0]
            assert repair_message.artifact["request"]["repair_sources"] == [fixture["source"]]
            assert runtime.lookup(document, fixture["run"]).wait() == result

    with opened(engine, None, dataset) as (runtime, owner, graph, store, memory_engine, sources):
        reopened = runtime.lookup(document, fixture["run"])
        assert reopened is not None and reopened.wait().status == "failed"
        assert PublicationStore(memory_engine,
            MemoryArtifacts(store, document, source=MemorySourceReader(sources, document))).current().revision == 2
        assert len(calls) == 1 and len(requests) == 2


def test_unknown_repair_result_keeps_the_gate_until_the_original_receipt_appears(monkeypatch, engine):
    dataset = str(uuid4())

    def repair(_payload):
        return "repair_memory", {"edits": [{"path": "/memory/knowledge.md",
            "diff": "@@\n-只做檢查。\n+只通報異常，維修由外包負責。"}]}

    with _offline_model(monkeypatch, [_final, repair], expected_tools=build_consultant_tools()) as (model, requests):
        with opened(engine, model, dataset) as (runtime, owner, graph, store, memory_engine, sources):
            document = owner.create_document(uuid4(), "合成Memory未知發布結果")
            current = owner.storage.read_current(document)
            first_run = str(uuid4())
            assert runtime.start(document, first_run, "我只做檢查。",
                expected_revision_id=current.revision_id).wait(20).status == "completed"
            source = sources.capture(document, first_run).source_ref
            artifacts = MemoryArtifacts(store, document, source=MemorySourceReader(sources, document))
            publication = PublicationStore(memory_engine, artifacts)
            version = artifacts.save_memory(knowledge="只做檢查。", guide="只做檢查")
            publication.publish(publication.prepare(version, expected_revision=0,
                kind="consolidation", processed_source=source))

            original_publish = PublicationStore.publish
            attempted = []
            def lose_before_result(instance, request):
                if request.kind == "repair":
                    attempted.append((instance, request))
                    raise PublicationUncertain("synthetic unknown repair result")
                return original_publish(instance, request)
            monkeypatch.setattr(PublicationStore, "publish", lose_before_result)
            run = str(uuid4())
            handle = runtime.start(document, run, "更正：我只通報異常，維修由外包負責。",
                expected_revision_id=current.revision_id)
            with pytest.raises(AiRuntimeError, match="^run_recovery_required$"):
                handle.wait(30)
            assert len(attempted) == 1 and len(requests) == 2
            assert publication.current().revision == 1
            assert owner.status(document).write_blocked
            with pytest.raises(AiRuntimeError, match="^run_recovery_required$"):
                handle.recover()
            assert len(attempted) == 1 and len(requests) == 2

            # This simulates the original database attempt becoming observable;
            # App recovery must reconcile that exact request, never invoke C again.
            original_publish(*attempted[0])
            result = handle.recover()
            assert result.status == "failed" and result.input_saved
            assert publication.current().revision == 2
            assert len(attempted) == 1 and len(requests) == 2
            observed = runtime.checkpoints.observe(document, run, dataset)
            repair_message = next(m for m in observed.messages
                if isinstance(m, ToolMessage) and m.name == "repair_memory")
            assert observed.closed and repair_message.status == "success"
            assert not owner.status(document).write_blocked
            assert owner.storage.read_current(document).revision_id == current.revision_id


@pytest.mark.parametrize("failure", ["source", "store"])
def test_repair_source_or_store_failure_closes_as_not_published(monkeypatch, engine, failure):
    dataset = str(uuid4())
    private = "SYNTHETIC_PRIVATE_REPAIR_DEPENDENCY"

    def repair(_payload):
        return "repair_memory", {"edits": [{"path": "/memory/knowledge.md",
            "diff": "@@\n-只做檢查。\n+只通報異常，維修由外包負責。"}]}

    with _offline_model(monkeypatch, [_final, repair], expected_tools=build_consultant_tools()) as (model, requests):
        with opened(engine, model, dataset) as (runtime, owner, graph, store, memory_engine, sources):
            document = owner.create_document(uuid4(), f"合成Memory {failure}失敗")
            current = owner.storage.read_current(document)
            first_run = str(uuid4())
            assert runtime.start(document, first_run, "我只做檢查。",
                expected_revision_id=current.revision_id).wait(20).status == "completed"
            source = sources.capture(document, first_run).source_ref
            artifacts = MemoryArtifacts(store, document, source=MemorySourceReader(sources, document))
            publication = PublicationStore(memory_engine, artifacts)
            version = artifacts.save_memory(knowledge="只做檢查。", guide="只做檢查")
            publication.publish(publication.prepare(version, expected_revision=0,
                kind="consolidation", processed_source=source))

            if failure == "source":
                monkeypatch.setattr(MemorySourceReader, "read",
                    lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError(private)))
            else:
                monkeypatch.setattr(MemoryArtifacts, "save_memory",
                    lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError(private)))
            run = str(uuid4())
            result = runtime.start(document, run, "更正：我只通報異常，維修由外包負責。",
                expected_revision_id=current.revision_id).wait(30)
            assert result.status == "failed" and result.input_saved
            assert len(requests) == 2 and publication.current().revision == 1
            observed = runtime.checkpoints.observe(document, run, dataset)
            repair_message = next(m for m in observed.messages
                if isinstance(m, ToolMessage) and m.name == "repair_memory")
            payload = json.loads(repair_message.content)
            assert observed.closed and repair_message.status == "error"
            assert payload["status"] == "not_published" and payload["retryable"] is False
            assert private not in repair_message.content
            assert not owner.status(document).write_blocked
            assert owner.storage.read_current(document).revision_id == current.revision_id


def test_repair_root_close_ack_loss_uses_exact_readback_without_replay(monkeypatch, engine):
    dataset = str(uuid4())

    def repair(_payload):
        return "repair_memory", {"edits": [{"path": "/memory/knowledge.md",
            "diff": "@@\n-只做檢查。\n+只通報異常，維修由外包負責。"}]}

    with _offline_model(monkeypatch, [_final, repair, _final], expected_tools=build_consultant_tools()) as (model, requests):
        with opened(engine, model, dataset) as (runtime, owner, graph, store, memory_engine, sources):
            document = owner.create_document(uuid4(), "合成Memory閉合回覆遺失")
            current = owner.storage.read_current(document)
            first_run = str(uuid4())
            assert runtime.start(document, first_run, "我只做檢查。",
                expected_revision_id=current.revision_id).wait(20).status == "completed"
            source = sources.capture(document, first_run).source_ref
            artifacts = MemoryArtifacts(store, document, source=MemorySourceReader(sources, document))
            publication = PublicationStore(memory_engine, artifacts)
            version = artifacts.save_memory(knowledge="只做檢查。", guide="只做檢查")
            publication.publish(publication.prepare(version, expected_revision=0,
                kind="consolidation", processed_source=source))

            original_update = graph.update_state
            updates = []
            def commit_then_lose_close_reply(*args, **kwargs):
                result = original_update(*args, **kwargs)
                updates.append(True)
                raise OSError("synthetic root close acknowledgement lost")
            monkeypatch.setattr(graph, "update_state", commit_then_lose_close_reply)
            run = str(uuid4())
            result = runtime.start(document, run, "更正：我只通報異常，維修由外包負責。",
                expected_revision_id=current.revision_id).wait(30)
            assert result.status == "completed" and result.input_saved
            assert len(updates) == 1 and len(requests) == 3 and publication.current().revision == 2
            assert runtime.lookup(document, run).wait() == result
            assert owner.storage.read_current(document).revision_id == current.revision_id

    with opened(engine, None, dataset) as (runtime, owner, graph, store, memory_engine, sources):
        reopened = runtime.lookup(document, run)
        assert reopened is not None and reopened.wait().status == "completed"
        assert PublicationStore(memory_engine,
            MemoryArtifacts(store, document, source=MemorySourceReader(sources, document))).current().revision == 2
        assert len(updates) == 1 and len(requests) == 3


def test_cancel_during_repair_drains_publication_and_blocks_the_next_model(monkeypatch, engine):
    dataset = str(uuid4())
    entered, release = Event(), Event()

    def repair(payload):
        return "repair_memory", {"edits": [{"path": "/memory/knowledge.md",
            "diff": "@@\n-處理通報。\n+只通報異常，維修由外包負責。"}]}

    def forbidden(_):
        pytest.fail("Cancellation during C must not start another model request")

    with _offline_model(monkeypatch, [_final, repair, forbidden], expected_tools=build_consultant_tools()) as (model, requests):
        with opened(engine, model, dataset) as (runtime, owner, graph, store, memory_engine, sources):
            document = owner.create_document(uuid4(), "合成Memory取消排空")
            current = owner.storage.read_current(document)
            first_run = str(uuid4())
            assert runtime.start(document, first_run, "我負責處理通報。",
                expected_revision_id=current.revision_id).wait(20).status == "completed"
            source = sources.capture(document, first_run).source_ref
            artifacts = MemoryArtifacts(store, document, source=MemorySourceReader(sources, document))
            publication = PublicationStore(memory_engine, artifacts)
            version = artifacts.save_memory(knowledge="處理通報。", guide="處理通報")
            publication.publish(publication.prepare(version, expected_revision=0,
                kind="consolidation", processed_source=source))

            original_prepare = RepairWorkflow._prepare
            def held_prepare(self, state):
                entered.set()
                assert release.wait(10)
                return original_prepare(self, state)
            monkeypatch.setattr(RepairWorkflow, "_prepare", held_prepare)
            run = str(uuid4())
            handle = runtime.start(document, run, "更正：我只通報，維修由外包負責。",
                expected_revision_id=current.revision_id)
            assert entered.wait(10)
            handle.request_stop()
            release.set()
            result = handle.wait(30)
            assert result.status == "cancelled" and result.input_saved
            assert len(requests) == 2 and publication.current().revision == 2
            observed = runtime.checkpoints.observe(document, run, dataset)
            repair_message = next(m for m in observed.messages
                if isinstance(m, ToolMessage) and m.name == "repair_memory")
            assert observed.closed and repair_message.status == "success"
            assert owner.storage.read_current(document).revision_id == current.revision_id


@pytest.mark.parametrize("stop",
    ["source_before_binding", "tool_handoff", "repair_child_start"])
def test_repair_stopped_before_c_closes_the_original_call_as_not_executed(monkeypatch, engine, stop):
    """A stop proven to precede C must close that same call, not hold the gate.

    `source_before_binding` stops inside the binding handler, before any
    binding exists; `tool_handoff` stops on the consultant's own tool node and
    `repair_child_start` on the fixed child's own START, both after the binding
    was saved. All three leave Memory, JD and the original speech untouched, so
    the original turn owes this call a not-executed terminal.
    """
    dataset = str(uuid4())
    private = "SYNTHETIC_PRIVATE_STOP_DEPENDENCY"

    def repair(_payload):
        return "repair_memory", {"edits": [{"path": "/memory/knowledge.md",
            "diff": "@@\n-只做檢查。\n+只通報異常，維修由外包負責。"}]}

    with _offline_model(monkeypatch, [_final, repair, _final], expected_tools=build_consultant_tools()) as (model, requests):
        with opened(engine, model, dataset) as (runtime, owner, graph, store, memory_engine, sources):
            document = owner.create_document(uuid4(), f"合成Memory停止位置 {stop}")
            current = owner.storage.read_current(document)
            first_run = str(uuid4())
            assert runtime.start(document, first_run, "我只做檢查。",
                expected_revision_id=current.revision_id).wait(20).status == "completed"
            source = sources.capture(document, first_run).source_ref
            artifacts = MemoryArtifacts(store, document, source=MemorySourceReader(sources, document))
            publication = PublicationStore(memory_engine, artifacts)
            version = artifacts.save_memory(knowledge="只做檢查。", guide="只做檢查")
            publication.publish(publication.prepare(version, expected_revision=0,
                kind="consolidation", processed_source=source))
            before = publication.current()

            lifted = []  # Releases only this synthetic fault; the offline wire stays.
            monkeypatch.setattr(RepairWorkflow, "_seed",
                lambda *_args: pytest.fail("A stop proven before C must never start the core"))
            original_for_turn = ConversationSourceService.for_turn
            def unavailable_after_the_model_request(self, document_id, run_id):
                notice, served = original_for_turn(self, document_id, run_id), []
                def guarded(messages):
                    if served and not lifted:
                        raise OSError(private)
                    served.append(True)
                    return notice(messages)
                return guarded
            original_put = PostgresSaver.put
            def fail_first_child_loop(self, config, checkpoint, metadata, new_versions):
                if (not lifted and metadata["source"] == "loop"
                        and config["configurable"].get("checkpoint_ns", "").startswith("memory_repair:")):
                    raise OSError(private)
                return original_put(self, config, checkpoint, metadata, new_versions)
            original_handoff = MemoryRepairSession.handoff
            def refuse_handoff(self, runtime):
                if lifted:
                    return original_handoff(self, runtime)
                raise OSError(private)
            if stop == "source_before_binding":
                monkeypatch.setattr(ConversationSourceService, "for_turn",
                                    unavailable_after_the_model_request)
            elif stop == "tool_handoff":
                monkeypatch.setattr(MemoryRepairSession, "handoff", refuse_handoff)
            else:
                monkeypatch.setattr(PostgresSaver, "put", fail_first_child_loop)

            run = str(uuid4())
            result = runtime.start(document, run, "更正：我只通報異常，維修由外包負責。",
                expected_revision_id=current.revision_id).wait(30)
            assert result.status == "failed" and result.input_saved
            assert len(requests) == 2, "A stopped repair must not start another model request."
            assert publication.current() == before
            assert artifacts.read_text("/memory/knowledge.md", before.memory) == "只做檢查。"

            observed = runtime.checkpoints.observe(document, run, dataset)
            repair_message = next(m for m in observed.messages
                if isinstance(m, ToolMessage) and m.name == "repair_memory")
            payload = json.loads(repair_message.content)
            assert observed.closed and repair_message.status == "error"
            assert payload["status"] == "not_executed" and payload["retryable"] is False
            assert private not in repair_message.content
            assert repair_message.artifact["request"] is None
            if stop == "source_before_binding":
                assert observed.repair_bindings == []
                assert repair_message.artifact["operation_id"] is None
            else:
                assert len(observed.repair_bindings) == 1
                operation = observed.repair_bindings[0]["operation_id"]
                assert repair_message.artifact["operation_id"] == operation
                assert publication.receipt(operation) is None

            snapshot = runtime.inspect_run(document, run)
            assert snapshot.run_status == "failed" and snapshot.effects_settled
            assert runtime.lookup(document, run).wait() == result
            assert not owner.status(document).write_blocked
            assert owner.storage.read_current(document).revision_id == current.revision_id

            lifted.append(True)
            next_run = str(uuid4())
            assert runtime.start(document, next_run, "再確認一次工作範圍。",
                expected_revision_id=current.revision_id).wait(20).status == "completed"
            assert publication.current() == before


def test_a_later_memory_head_does_not_invalidate_the_original_applied_repair(monkeypatch, engine):
    """Background consolidation may move the head after a turn already closed.

    The saved tool feedback keeps that turn's own read head and guide. Only the
    original applied receipt decides whether the correction stands, so a newer
    head must neither invalidate the closed run nor roll its result backwards.
    """
    dataset = str(uuid4())
    fixture = {}

    def repair(_payload):
        return "repair_memory", {"edits": [{"path": "/memory/knowledge.md",
            "diff": "@@\n-只做檢查。\n+只通報異常，維修由外包負責。"}]}

    with _offline_model(monkeypatch, [_final, repair, _final, _final], expected_tools=build_consultant_tools()) as (model, requests):
        with opened(engine, model, dataset) as (runtime, owner, graph, store, memory_engine, sources):
            document = owner.create_document(uuid4(), "合成Memory晚到背景版本")
            current = owner.storage.read_current(document)
            first_run = str(uuid4())
            assert runtime.start(document, first_run, "我只做檢查。",
                expected_revision_id=current.revision_id).wait(20).status == "completed"
            source = sources.capture(document, first_run).source_ref
            artifacts = MemoryArtifacts(store, document, source=MemorySourceReader(sources, document))
            publication = PublicationStore(memory_engine, artifacts)
            version = artifacts.save_memory(knowledge="只做檢查。", guide="只做檢查")
            publication.publish(publication.prepare(version, expected_revision=0,
                kind="consolidation", processed_source=source))

            fixture["run"] = str(uuid4())
            fixture["result"] = runtime.start(document, fixture["run"],
                "更正：我只通報異常，維修由外包負責。",
                expected_revision_id=current.revision_id).wait(30)
            assert fixture["result"].status == "completed" and publication.current().revision == 2
            observed = runtime.checkpoints.observe(document, fixture["run"], dataset)
            saved = next(m for m in observed.messages
                if isinstance(m, ToolMessage) and m.name == "repair_memory")
            fixture["artifact"] = saved.artifact
            assert saved.status == "success" and saved.artifact["outcome"]["applied_head"]["revision"] == 2

            later = artifacts.save_memory(knowledge="只通報異常，維修由外包負責。整併後補充工作節奏。",
                guide="只通報異常")
            publication.publish(publication.prepare(later, expected_revision=2,
                kind="consolidation", processed_source=source))
            assert publication.current().revision == 3

            # A further turn pushes the corrected run into history, so lookup
            # must walk back to its own original position and still verify it.
            assert runtime.start(document, str(uuid4()), "再確認一次工作範圍。",
                expected_revision_id=current.revision_id).wait(20).status == "completed"

    with opened(engine, None, dataset) as (runtime, owner, graph, store, memory_engine, sources):
        reopened = runtime.lookup(document, fixture["run"])
        assert reopened is not None and reopened.wait() == fixture["result"]
        snapshot = runtime.inspect_run(document, fixture["run"])
        assert snapshot.run_status == "completed" and snapshot.effects_settled
        # The corrected run is now history: read it at its own position.
        again = runtime.run_history.find(document, fixture["run"], dataset)
        assert again.closed and again.record.run_id == fixture["run"]
        message = next(m for m in again.messages
            if isinstance(m, ToolMessage) and m.name == "repair_memory")
        assert message.artifact == fixture["artifact"]
        assert json.loads(message.content)["status"] == "applied"
        assert PublicationStore(memory_engine, MemoryArtifacts(store, document,
            source=MemorySourceReader(sources, document))).current().revision == 3
