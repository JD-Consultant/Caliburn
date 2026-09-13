"""B1 over real PostgreSQL: Saver progress and Store artifacts, no provider.

The adopted extraction workflow runs on a real `PostgresSaver`, a real
`PostgresStore` and the real OpenAI SDK, answered in process by
`httpx.MockTransport`. Nothing here publishes, writes JD, adds a table or
re-implements the workflow: this is the same B1 the offline tests cover, on
durable resources that are then closed and rebuilt.

Run `scripts/init_test_runtime.py` and `scripts/init_test_memory.py`
explicitly first. These tests never setup, clear or drop anything.
"""
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from uuid import uuid4

import httpx
from langchain_core.messages import AIMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.store.postgres import PostgresStore
from langgraph.types import interrupt
from psycopg import Connection
from psycopg.rows import dict_row
import pytest

from caliburn_memory import MemoryArtifacts
from jd_relational.ai_checkpoints import AiRunCheckpoints
from jd_relational.conversation_sources import ConversationSourceCodec, ConversationSourceService
from jd_relational.extraction_app import build_extraction_model, build_extraction_workflow
from jd_relational.memory_sources import MemorySourceReader
from jd_relational.runtime_checkpoints import DocumentState, build_document_graph

from test_extraction_app import completed
from test_interview_window_source import settled
from test_manual_runtime_postgres import connect, NATIVE_TABLES, RUNTIME_SCHEMA
from test_memory_core_postgres import SCHEMA, TABLES


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")
KEY = b"synthetic-b1-postgres-key-32-byte"


class FaultyStore(PostgresStore):
    """A real Store with one armable write fault; nothing else is simulated."""

    def __init__(self, connection):
        super().__init__(connection)
        self.pass_writes = None

    def batch(self, operations):
        writes = [operation for operation in operations if type(operation).__name__ == "PutOp"]
        if self.pass_writes is not None and writes:
            if self.pass_writes < len(writes):
                self.pass_writes = None
                raise RuntimeError("synthetic store fault")
            self.pass_writes -= len(writes)
        return super().batch(operations)


@contextmanager
def opened(dataset, document, *, store_class=PostgresStore):
    """One document on real durable resources, closed again on exit."""
    with connect() as saver_conn, Connection.connect(host="127.0.0.1", port=55436,
        dbname="caliburn_jd_relational_test", user="jd_test", password="jd-local-test-only",
        options=f"-csearch_path={SCHEMA},public", connect_timeout=5,
        autocommit=True, row_factory=dict_row, prepare_threshold=0) as store_conn:
        assert store_conn.execute("SELECT current_database() AS db, current_user AS usr, "
            "current_setting('server_version_num')::integer AS version").fetchone() == {
                "db": "caliburn_jd_relational_test", "usr": "jd_test", "version": 180006}
        assert {row["tablename"] for row in store_conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname=%s", (SCHEMA,))} == TABLES
        assert {row["tablename"] for row in saver_conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname=%s", (RUNTIME_SCHEMA,))} == NATIVE_TABLES
        replies, paused, calls = [], set(), []
        def model(state):
            calls.append(state["jd_ai_run"]["run_id"])
            return {"messages": deepcopy(replies)}
        def hold(state):
            if state["jd_ai_run"]["run_id"] in paused:
                interrupt("synthetic pause")
            return {}
        child = StateGraph(DocumentState)
        child.add_node("model", model); child.add_node("hold", hold)
        child.add_edge(START, "model"); child.add_edge("model", "hold"); child.add_edge("hold", END)
        saver = PostgresSaver(saver_conn, serde=JsonPlusSerializer(allowed_msgpack_modules=None))
        graph = build_document_graph(child.compile(), saver)
        windows = ConversationSourceService(AiRunCheckpoints(graph), ConversationSourceCodec(KEY, dataset))
        yield (graph, dataset, document, replies, paused, calls), windows, store_class(store_conn), \
            saver, store_conn


@contextmanager
def provider():
    """The real SDK against an in-process transport; every call is counted."""
    sent, queue = [], []

    def respond(request):
        sent.append(json.loads(request.content))
        item = queue.pop(0) if queue else completed()
        if isinstance(item, int):
            return httpx.Response(item, json={"error": {"message": "synthetic", "type": "server_error"}})
        return httpx.Response(200, json=item)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        yield build_extraction_model(model="gpt-5.6-luna", api_key="offline",
                                     http_client=client).model_copy(update={"max_retries": 0}), sent, queue


def interviewed(native, count):
    """Turns sized so the verified 6000/1500 profile really cuts several windows."""
    return [settled(native, [AIMessage(id=f"pg-a{index}", content="回" * 1250)],
                    text="問" * 1250) for index in range(count)]


def artifacts_for(windows, store, document):
    return MemoryArtifacts(store, document, source=MemorySourceReader(
        windows, document, window_references=True, context_references=True))


def saved_rows(store_conn, document):
    return store_conn.execute("SELECT count(*) AS n FROM store WHERE prefix LIKE %s",
                              ("q019-memory." + document + ".%",)).fetchone()["n"]


def published_rows(store_conn, document):
    return store_conn.execute("SELECT count(*) AS n FROM q019_document_memory_head "
                              "WHERE document_id=%s", (document,)).fetchone()["n"]


def test_one_bounded_batch_saves_durably_and_the_cursor_alone_takes_the_tail():
    """The whole R1 path on durable resources: target, batch, B1, then the tail.

    Nothing is published, so the saved detail must not become current Memory,
    and the second batch must be admitted only because the first one's own
    reference moved the cursor.
    """
    dataset, document = str(uuid4()), str(uuid4())
    with opened(dataset, document) as (native, windows, store, saver, store_conn):
        interviewed(native, 5)
        target = windows.capture_window(document, **windows.unprocessed_source(document))
        planned = windows.plan_saved_windows(target, document)
        batch = windows.plan_saved_batch(target, document, max_windows=2)
        assert batch["covers_whole_range"] is False
        with provider() as (model, sent, _):
            workflow = build_extraction_workflow(service=windows, document_id=document,
                store=store, model=model, checkpointer=saver)
            result = workflow.start(batch["source_reference"])
            assert len(result["files"]) == 2 and len(sent) == 2
            artifacts = artifacts_for(windows, store, document)
            assert [artifacts.source_window(file["summary_path"]) for file in result["files"]] == [
                {"source_reference": pair["source_reference"],
                 "context_reference": pair["context_reference"]} for pair in planned[:2]]
            assert artifacts.read_text(result["files"][0]["summary_path"]).endswith(
                "甲案：單次付款、無障礙。\n乙案：月租、權限分級。")
            assert saved_rows(store_conn, document) == 4
            assert published_rows(store_conn, document) == 0

            rest = windows.plan_saved_batch(target, document,
                                            after_reference=batch["source_reference"])
            assert rest["covers_whole_range"] is True
            tail = workflow.start(rest["source_reference"])
            assert len(tail["files"]) == 2 and len(sent) == 4
            assert saved_rows(store_conn, document) == 8 and published_rows(store_conn, document) == 0
            # Every number here is measured; none is written in by hand.
            print(f"B1 real PG document={document} windows={len(planned)} "
                  f"files={len(result['files']) + len(tail['files'])} http={len(sent)} "
                  f"rows={saved_rows(store_conn, document)} "
                  f"published={published_rows(store_conn, document)}")


def test_a_store_fault_resumes_on_rebuilt_resources_without_calling_the_model_again():
    """The saved model result is progress, not something to buy twice.

    The fault lands after the candidate is checkpointed, so every resource is
    closed and reopened and the original job resumed from its own config: the
    window completes with no further request reaching the transport.
    """
    dataset, document = str(uuid4()), str(uuid4())
    with opened(dataset, document, store_class=FaultyStore) as (native, windows, store, saver, _):
        interviewed(native, 3)
        target = windows.capture_window(document, **windows.unprocessed_source(document))
        batch = windows.plan_saved_batch(target, document, max_windows=1)["source_reference"]
        store.pass_writes = 0
        with provider() as (model, sent, _):
            workflow = build_extraction_workflow(service=windows, document_id=document,
                store=store, model=model, checkpointer=saver)
            with pytest.raises(RuntimeError, match="synthetic store fault"):
                workflow.start(batch)
            assert len(sent) == 1
    with opened(dataset, document) as (_, windows, store, saver, store_conn):
        assert saved_rows(store_conn, document) == 0
        with provider() as (model, sent, _):
            workflow = build_extraction_workflow(service=windows, document_id=document,
                store=store, model=model, checkpointer=saver)
            result = workflow.resume()
            assert sent == [], "the checkpointed model result must not be requested again"
            assert len(result["files"]) == 1
            assert result["source_reference"] == batch
            artifacts = artifacts_for(windows, store, document)
            assert artifacts.read_text(result["files"][0]["summary_path"]).endswith(
                "甲案：單次付款、無障礙。\n乙案：月租、權限分級。")
            assert saved_rows(store_conn, document) == 2
            assert published_rows(store_conn, document) == 0


def test_a_half_written_pair_leaves_an_unreferenced_artifact_and_still_completes():
    """One Store write landed, the next did not. That leftover is allowed.

    The verified boundary is that `files` names the pair actually saved and no
    unreferenced artifact is ever read as Memory. Requiring zero leftovers
    would mean a cross-Saver/Store transaction or a collector, and neither is
    part of this design.
    """
    dataset, document = str(uuid4()), str(uuid4())
    with opened(dataset, document, store_class=FaultyStore) as (native, windows, store, saver, store_conn):
        interviewed(native, 3)
        target = windows.capture_window(document, **windows.unprocessed_source(document))
        batch = windows.plan_saved_batch(target, document, max_windows=1)["source_reference"]
        store.pass_writes = 1
        with provider() as (model, sent, _):
            workflow = build_extraction_workflow(service=windows, document_id=document,
                store=store, model=model, checkpointer=saver)
            with pytest.raises(RuntimeError, match="synthetic store fault"):
                workflow.start(batch)
            assert len(sent) == 1 and saved_rows(store_conn, document) == 1
            result = workflow.resume()
            assert len(sent) == 1, "resuming the save must not buy the window again"
            assert len(result["files"]) == 1
            # Three rows: the orphaned summary plus the pair that `files` names.
            assert saved_rows(store_conn, document) == 3
            artifacts = artifacts_for(windows, store, document)
            assert artifacts.read_text(result["files"][0]["summary_path"]).endswith(
                "甲案：單次付款、無障礙。\n乙案：月租、權限分級。")
            assert published_rows(store_conn, document) == 0


def test_a_repeat_request_reads_back_and_a_pending_job_refuses_a_new_input():
    """Same intent, same answer; a different intent never replaces pending work."""
    dataset, document = str(uuid4()), str(uuid4())
    with opened(dataset, document, store_class=FaultyStore) as (native, windows, store, saver, store_conn):
        interviewed(native, 5)
        target = windows.capture_window(document, **windows.unprocessed_source(document))
        first = windows.plan_saved_batch(target, document, max_windows=1)["source_reference"]
        with provider() as (model, sent, _):
            workflow = build_extraction_workflow(service=windows, document_id=document,
                store=store, model=model, checkpointer=saver)
            result = workflow.start(first)
            assert len(sent) == 1
            assert workflow.start(first) == result and len(sent) == 1
            assert saved_rows(store_conn, document) == 2

            store.pass_writes = 0
            later = windows.plan_saved_batch(target, document, after_reference=first,
                                             max_windows=1)["source_reference"]
            with pytest.raises(RuntimeError, match="synthetic store fault"):
                workflow.start(later)
            with pytest.raises(ValueError, match="pending job"):
                workflow.start(first)
            assert len(sent) == 2


def test_re_extraction_reads_the_original_pair_and_leaves_the_normal_position():
    """A re-extraction is its own job: the admitted position never moves."""
    dataset, document = str(uuid4()), str(uuid4())
    with opened(dataset, document) as (native, windows, store, saver, store_conn):
        interviewed(native, 3)
        target = windows.capture_window(document, **windows.unprocessed_source(document))
        batch = windows.plan_saved_batch(target, document, max_windows=1)["source_reference"]
        with provider() as (model, sent, queue):
            workflow = build_extraction_workflow(service=windows, document_id=document,
                store=store, model=model, checkpointer=saver)
            result = workflow.start(batch)
            summary_path = result["files"][0]["summary_path"]
            queue.append(completed(summary="重抽後的詳記。", slug="重抽"))
            again = workflow.reextract(summary_path)
            assert again["replaces_summary"] == summary_path
            assert again["windows"] == [{
                "source_reference": result["files"][0]["source_reference"],
                "context_reference": result["files"][0]["context_reference"]}]
            assert len(sent) == 2
            assert workflow.graph.get_state(workflow.config).values["files"] == result["files"]
            assert workflow.graph.get_state(workflow.config).values["source_reference"] == batch


def test_an_unconfirmed_save_checkpoint_resumes_without_buying_the_window_again(monkeypatch):
    """Both artifacts landed; the checkpoint recording them did not.

    At this position the save task's own output was already written as a
    pending write, so resuming applies that recorded result instead of running
    the node again: the model is not called again and this window leaves no
    second pair behind. That is an observation about this boundary, not a
    general exactly-once guarantee for external effects, and it claims no
    cross Saver/Store transaction. What must hold either way is that `files`
    names artifacts the Store really has and nothing is published.
    """
    dataset, document = str(uuid4()), str(uuid4())
    with opened(dataset, document) as (native, windows, store, saver, store_conn):
        interviewed(native, 3)
        target = windows.capture_window(document, **windows.unprocessed_source(document))
        batch = windows.plan_saved_batch(target, document, max_windows=1)["source_reference"]
        original = PostgresSaver.put

        def refuse_the_save_record(self, config, checkpoint, metadata, versions):
            # The checkpoint that first carries `files` is the one recording
            # artifacts the Store already holds: exactly the boundary to break.
            if checkpoint["channel_values"].get("files"):
                monkeypatch.undo()
                raise RuntimeError("synthetic saver fault")
            return original(self, config, checkpoint, metadata, versions)

        monkeypatch.setattr(PostgresSaver, "put", refuse_the_save_record)
        with provider() as (model, sent, _):
            workflow = build_extraction_workflow(service=windows, document_id=document,
                store=store, model=model, checkpointer=saver)
            with pytest.raises(RuntimeError, match="synthetic saver fault"):
                workflow.start(batch)
            assert len(sent) == 1 and saved_rows(store_conn, document) == 2
            result = workflow.resume()
            assert len(sent) == 1, "the recorded model result must not be requested again"
            assert len(result["files"]) == 1
            # Two rows: the recorded task output was applied, not re-executed,
            # so this window wrote its pair once rather than twice.
            assert saved_rows(store_conn, document) == 2
            assert published_rows(store_conn, document) == 0
            artifacts = artifacts_for(windows, store, document)
            assert artifacts.source_window(result["files"][0]["summary_path"])[
                "source_reference"] == result["files"][0]["source_reference"]
