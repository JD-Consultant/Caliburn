"""Reopen actual PostgreSQL after B1 model-result checkpoint / Store failure."""

import os
from uuid import uuid4

import httpx
import pytest
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from analysis_agent.extraction import ExtractionWorkflow
from analysis_agent.memory import MemoryArtifacts
from analysis_agent.provider import build_model
from analysis_agent.runtime import build_agent
from analysis_agent.sources import ConversationReader
from test_extraction import body, source


@pytest.mark.parametrize("failure", ["before-write", "after-summary"])
def test_postgres_reopen_resumes_artifact_save_not_model(failure):
    dsn = os.environ.get("Q019_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Requires dedicated q019_agent_test; not a durability pass")
    params = conninfo_to_dict(dsn)
    assert params.get("dbname") == "q019_agent_test"
    assert params.get("host") in ("localhost", "127.0.0.1")
    assert 1 <= int(params.get("connect_timeout", "0")) <= 10
    dsn = make_conninfo(dsn, options="-c statement_timeout=10000 -c lock_timeout=5000")
    document, workflow_thread = "q019-test-" + str(uuid4()), None
    called = []
    def respond(request):
        called.append(request)
        return httpx.Response(200, json=body())
    class FailedSave(MemoryArtifacts):
        def _save(self, backend, path, content):
            if failure == "before-write":
                raise RuntimeError("injected Store outage")
            super()._save(backend, path, content)
            if path.endswith("summary.md"):
                raise RuntimeError("injected partial artifact write")
    try:
        with PostgresStore.from_conn_string(dsn) as store, PostgresSaver.from_conn_string(dsn) as saver:
            store.setup()
            saver.setup()
            with httpx.Client(transport=httpx.MockTransport(respond)) as client:
                model = build_model(model="gpt-5.6-luna", api_key="offline", http_client=client)
                reader, ref = source(model, saver, document)
                workflow = ExtractionWorkflow(reader, FailedSave(store, document), model, saver)
                workflow_thread = workflow.config["configurable"]["thread_id"]
                with pytest.raises(RuntimeError, match="injected"):
                    workflow.start(ref)
                assert len(called) == 1
                saved = workflow.graph.get_state(workflow.config)
                assert saved.next == ("save",)
                assert saved.values["extracted"]["raw_memory"].startswith("共同做客製前端")
        # New connections, graphs, reader, backend and HTTP client. A repeat
        # request is an immediate failure, not a permissive fake model answer.
        with PostgresStore.from_conn_string(dsn) as store, PostgresSaver.from_conn_string(dsn) as saver:
            with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("B1 model must not repeat"))) as client:
                model = build_model(model="gpt-5.6-luna", api_key="offline", http_client=client)
                graph = build_agent(model=model, checkpointer=saver, instructions="unused")
                reader = ConversationReader(graph, document)
                artifacts = MemoryArtifacts(store, document)
                workflow = ExtractionWorkflow(reader, artifacts, model, saver)
                result = workflow.resume()
                assert result["position"] == 1 and len(result["files"]) == 1
                item = result["files"][0]
                assert "A網站限單次付款" in reader.read(item["source_reference"])["segments"][0]["text"]
                entries = store.search(("q019-memory", document, "interviews"))
                assert len(entries) == (2 if failure == "before-write" else 3)
                assert store.search(("q019-memory", document, "versions")) == []
                assert workflow.start(ref)["files"] == result["files"]
                assert workflow.graph.get_state(workflow.config).next == ()
    finally:
        with PostgresStore.from_conn_string(dsn) as store, PostgresSaver.from_conn_string(dsn) as saver:
            items, offset = [], 0
            while page := store.search(("q019-memory", document), limit=100, offset=offset):
                items.extend(page)
                offset += len(page)
            for item in items:
                store.delete(item.namespace, item.key)
            saver.delete_thread(document)
            if workflow_thread is not None:
                saver.delete_thread(workflow_thread)
