"""Real PG/Saver/Store and SDK wire; fixed responses, zero provider calls.

Memory publishing here is a test fixture, not model B1/B2/C execution. Resource
reopen uses new connections in this process, not a foreign-host death proof.
"""
from contextlib import contextmanager
import json
import os
from uuid import uuid4

from caliburn_memory import MemoryArtifacts, PublicationStore
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.store.postgres import PostgresStore
from psycopg import Connection
from psycopg.rows import dict_row
import pytest

from jd_relational.ai_checkpoints import AiRunCheckpoints
from jd_relational.ai_runtime import AiRuntime
from jd_relational.consultant_context import build_consultant_node
from jd_relational.consultant_tools import AiToolMiddleware
from jd_relational.conversation_sources import ConversationSourceCodec, ConversationSourceService
from jd_relational.inspection_model import build_inspection_consultant_node
from jd_relational.manual_runtime import ManualRuntime
from jd_relational.memory_context import build_consultant_tools
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
    with _offline_model(monkeypatch, plan, expected_tool_count=14) as (model, requests):
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
