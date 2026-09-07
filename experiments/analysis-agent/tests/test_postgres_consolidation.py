"""Reopen all clients after B2 failure; never use paid provider access."""
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
from analysis_agent.publication import PublicationStore, HeadRow, ReceiptRow
from analysis_agent.runtime import build_agent
from analysis_agent.sources import ConversationReader
from test_consolidation import call, done, with_guide
from test_extraction import source, body


@pytest.mark.parametrize("failure", ["during-agent", "before-save", "after-commit"])
def test_pg_b2_recovers_same_stage_with_new_clients(failure):
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
    document, threads = "q019-test-"+str(uuid4()), set()
    sent = []
    replies = [body(), with_guide(call("write_file", file_path="/memory/knowledge.md", content="已暫存的案例细節"))]
    def respond(request):
        sent.append(json.loads(request.content))
        assert replies, "No model call authorized at this resume point"
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        reply["id"] = f"resp_{len(sent)}"
        for i, item in enumerate(reply["output"]):
            item["id"] = f"item_{len(sent)}_{i}"
            if item["type"] == "function_call":
                item["call_id"] = f"call_{len(sent)}_{i}"
        return httpx.Response(200, json=reply)
    class FailedSave(MemoryArtifacts):
        def save_memory(self, **kwargs):
            raise RuntimeError("injected Store unavailable")
    class FailedRead(MemoryArtifacts):
        def interview_backend(self):
            backend = super().interview_backend()
            def fail(*args, **kwargs):
                raise RuntimeError("injected detail read failure")
            # Only fault injection; downloads/Store writes remain real. This
            # triggers after a staged write has already completed its tool step.
            backend.read = fail
            return backend
    class LostReply(PublicationStore):
        def publish(self, request):
            super().publish(request)
            raise RuntimeError("injected lost commit reply")
    first_engine = engine()
    try:
        with PostgresStore.from_conn_string(dsn) as store, PostgresSaver.from_conn_string(dsn) as saver:
            store.setup()
            saver.setup()
            with httpx.Client(transport=httpx.MockTransport(respond)) as client:
                model = build_model(model="gpt-5.6-luna", api_key="offline", http_client=client).model_copy(update={"max_retries": 0})
                reader, ref = source(model, saver, document)
                artifact_class = {"before-save": FailedSave, "during-agent": FailedRead}.get(failure, MemoryArtifacts)
                artifacts = artifact_class(store, document)
                b1 = ExtractionWorkflow(reader, artifacts, model, saver)
                extracted = b1.start(ref)
                replies.append(call("read_file", file_path=extracted["files"][0]["summary_path"]) if failure == "during-agent" else done())
                pub = (LostReply if failure == "after-commit" else PublicationStore)(first_engine, artifacts)
                pub.setup()
                workflow = ConsolidationWorkflow(b1, pub, model, saver)
                threads.update((document, workflow.thread_id, b1.config["configurable"]["thread_id"]))
                with pytest.raises(RuntimeError, match="injected"):
                    workflow.start()
                snapshot = workflow.graph.get_state(workflow.config)
                expected_node = {"during-agent": "consolidate", "before-save": "save", "after-commit": "publish"}[failure]
                assert snapshot.next == (expected_node,)
                request = snapshot.values.get("request")
                before = len(sent)
        first_engine.dispose()
        second_engine = engine()
        try:
            if failure == "during-agent":
                replies.extend([call("read_file", file_path="/memory/knowledge.md"), done()])
            with PostgresStore.from_conn_string(dsn) as store, PostgresSaver.from_conn_string(dsn) as saver:
                with httpx.Client(transport=httpx.MockTransport(respond)) as client:
                    model = build_model(model="gpt-5.6-luna", api_key="offline", http_client=client).model_copy(update={"max_retries": 0})
                    reader = ConversationReader(build_agent(model=model, checkpointer=saver, instructions="not invoked"), document)
                    artifacts = MemoryArtifacts(store, document)
                    b1 = ExtractionWorkflow(reader, artifacts, model, saver)
                    pub = PublicationStore(second_engine, artifacts)
                    workflow = ConsolidationWorkflow(b1, pub, model, saver)
                    result = workflow.resume()
                    assert pub.current().revision == 1 and pub.current().processed_source == ref
                    assert artifacts.read_text("/memory/knowledge.md", pub.current().memory) == "已暫存的案例细節"
                    assert artifacts.read_text("/memory/guide.md", pub.current().memory) == "網站案例：見 /memory/knowledge.md"
                    if failure == "during-agent":
                        assert len(sent) == before + 2
                        assert "已暫存的案例细節" in json.dumps(sent[-1], ensure_ascii=False)
                        assert any(i.get("type") == "function_call_output" for i in sent[before]["input"])
                    else:
                        assert len(sent) == before
                    if request:
                        assert result["request"]["operation_id"] == request["operation_id"]
                    assert workflow.start()["result"] == result["result"]
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
