"""Reopen real Saver/Store/ORM connections after interrupted re-extraction B2."""
import json
import os
from uuid import uuid4

import httpx
import pytest
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy import create_engine, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from analysis_agent.consolidation import ConsolidationWorkflow
from analysis_agent.extraction import ExtractionWorkflow
from analysis_agent.memory import MemoryArtifacts
from analysis_agent.provider import build_model
from analysis_agent.publication import HeadRow, ReceiptRow, PublicationStore
from analysis_agent.runtime import build_agent
from analysis_agent.sources import ConversationReader
from test_consolidation import call, done
from test_extraction import source, body
from test_summary_reextraction import corrected


@pytest.mark.parametrize("failure", ["before-save", "after-commit"])
def test_pg_reextraction_recovery_preserves_cursor_and_references(failure):
    dsn = os.environ.get("Q019_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Dedicated q019_agent_test required; not a durability pass")
    params = conninfo_to_dict(dsn)
    assert params.get("dbname") == "q019_agent_test"
    assert params.get("host") in ("127.0.0.1", "localhost")
    assert 1 <= int(params.get("connect_timeout", "0")) <= 10
    dsn = make_conninfo(dsn, options="-c statement_timeout=10000 -c lock_timeout=5000")
    def engine():
        return create_engine(URL.create("postgresql+psycopg"), connect_args=conninfo_to_dict(dsn), hide_parameters=True)
    document, threads = "q019-test-" + str(uuid4()), set()
    sent, replies = [], [body(), corrected()]
    def respond(request):
        sent.append(json.loads(request.content))
        assert replies, "Resume must not re-call an already completed model step"
        reply = replies.pop(0)
        reply["id"] = f"resp_{len(sent)}"
        for i, item in enumerate(reply["output"]):
            item["id"] = f"item_{len(sent)}_{i}"
            if item["type"] == "function_call":
                item["call_id"] = f"call_{len(sent)}_{i}"
        return httpx.Response(200, json=reply)
    class FailedSave(MemoryArtifacts):
        def save_memory(self, **kwargs):
            raise RuntimeError("injected save failure")
    class LostReply(PublicationStore):
        def publish(self, request):
            super().publish(request)
            raise RuntimeError("injected lost reply")
    first_engine = engine()
    try:
        with PostgresStore.from_conn_string(dsn) as store, PostgresSaver.from_conn_string(dsn) as saver:
            store.setup()
            saver.setup()
            with httpx.Client(transport=httpx.MockTransport(respond)) as client:
                model = build_model(model="gpt-5.6-luna", api_key="offline", http_client=client).model_copy(update={"max_retries": 0})
                reader, ref = source(model, saver, document)
                artifacts = MemoryArtifacts(store, document)
                b1 = ExtractionWorkflow(reader, artifacts, model, saver)
                old = b1.start(ref)["files"][0]["summary_path"]
                pub = PublicationStore(first_engine, artifacts)
                pub.setup()
                version = artifacts.save_memory(knowledge="案例：" + old, guide="網站案例")
                pub.publish(pub.prepare(version, expected_revision=0, kind="consolidation", processed_source=ref))
                new = b1.reextract(old)["files"][0]["summary_path"]
                replies.extend([call("apply_memory_patch", file_path="/memory/knowledge.md", diff=f"@@\n-案例：{old}\n+案例：{new}"), done()])
                if failure == "before-save":
                    b1 = ExtractionWorkflow(reader, FailedSave(store, document), model, saver)
                else:
                    pub = LostReply(first_engine, artifacts)
                b2 = ConsolidationWorkflow(b1, pub, model, saver)
                threads.update((document, b1.config["configurable"]["thread_id"],
                    b1.reextraction_config(old)["configurable"]["thread_id"], b2.thread_id))
                with pytest.raises(RuntimeError, match="injected"):
                    b2.start_reextraction(old)
                assert b2.graph.get_state(b2.config).next == (("save",) if failure == "before-save" else ("publish",))
                count = len(sent)
        first_engine.dispose()
        second_engine = engine()
        try:
            with PostgresStore.from_conn_string(dsn) as store, PostgresSaver.from_conn_string(dsn) as saver:
                with httpx.Client(transport=httpx.MockTransport(respond)) as client:
                    model = build_model(model="gpt-5.6-luna", api_key="offline", http_client=client).model_copy(update={"max_retries": 0})
                    reader = ConversationReader(build_agent(model=model, checkpointer=saver, instructions="not invoked"), document)
                    artifacts = MemoryArtifacts(store, document)
                    b1 = ExtractionWorkflow(reader, artifacts, model, saver)
                    pub = PublicationStore(second_engine, artifacts)
                    b2 = ConsolidationWorkflow(b1, pub, model, saver)
                    result = b2.resume()
                    assert len(sent) == count
                    assert pub.current().revision == 2 and pub.current().processed_source == ref
                    assert artifacts.read_text("/memory/knowledge.md", pub.current().memory) == "案例：" + new
                    assert artifacts.read_text(old) and artifacts.read_text(new)
                    assert reader.read(ref)["segments"][0]["text"] == "A網站限單次付款，需無障礙。"
                    assert b1.resume_reextraction(old)["files"][0]["summary_path"] == new
                    assert b2.start_reextraction(old)["result"] == result["result"]
                    assert len(sent) == count
        finally:
            second_engine.dispose()
    finally:
        first_engine.dispose()
        cleanup_engine = engine()
        try:
            with Session(cleanup_engine) as session, session.begin():
                for row in session.scalars(select(ReceiptRow).where(ReceiptRow.document_id == document)):
                    session.delete(row)
                head = session.get(HeadRow, document)
                if head:
                    session.delete(head)
            with PostgresStore.from_conn_string(dsn) as store, PostgresSaver.from_conn_string(dsn) as saver:
                items, offset = [], 0
                while page := store.search(("q019-memory", document), limit=100, offset=offset):
                    items.extend(page)
                    offset += len(page)
                for item in items:
                    store.delete(item.namespace, item.key)
                for thread in threads:
                    saver.delete_thread(thread)
        finally:
            cleanup_engine.dispose()
