"""Real source Saver -> StoreBackend -> publication -> correction -> reopen.

Synthetic native node, no provider/model, no host/worker integration claim.
Explicitly initialize scripts/init_test_memory.py first. Tests never setup or
remove evidence. Reopen uses new connections/graph/owners in this process.
"""
from contextlib import contextmanager
from copy import deepcopy
import os
from uuid import uuid4

from langchain_core.messages import AIMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.store.postgres import PostgresStore
from psycopg import Connection
from psycopg.rows import dict_row
import pytest
import sqlalchemy as sa

from caliburn_memory.memory import MemoryArtifacts
from caliburn_memory.publication import PublicationStore, StalePublication
from jd_relational.ai_checkpoints import AiRunCheckpoints
from jd_relational.conversation_sources import ConversationSourceCodec, ConversationSourceService
from jd_relational.memory_sources import MemorySourceReader
from jd_relational.runtime_checkpoints import DocumentState, build_document_graph
from test_chat_history import append
from test_manual_runtime_postgres import connect, NATIVE_TABLES, RUNTIME_SCHEMA


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")
KEY = b"synthetic-memory-source-key-32-bytes"
SCHEMA = "jd_memory_core_test"
TABLES = {"store", "store_migrations", "q019_document_memory_head", "q019_memory_publication_receipt"}


@contextmanager
def opened(dataset, document):
    engine = sa.create_engine(sa.URL.create("postgresql+psycopg", username="jd_test",
        password="jd-local-test-only", host="127.0.0.1", port=55436,
        database="caliburn_jd_relational_test"), hide_parameters=True,
        connect_args={"options": "-csearch_path=jd_memory_core_test,public", "connect_timeout": 5})
    try:
        with connect() as saver_conn, Connection.connect(host="127.0.0.1", port=55436,
            dbname="caliburn_jd_relational_test", user="jd_test", password="jd-local-test-only",
            options="-csearch_path=jd_memory_core_test,public", connect_timeout=5,
            autocommit=True, row_factory=dict_row, prepare_threshold=0) as store_conn:
            assert store_conn.execute("SELECT current_database() AS db, current_user AS usr, "
                "current_setting('server_version_num')::integer AS version").fetchone() == {
                    "db": "caliburn_jd_relational_test", "usr": "jd_test", "version": 180006}
            assert store_conn.execute("SHOW search_path").fetchone()["search_path"] == SCHEMA + ",public"
            assert {row["tablename"] for row in store_conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname=%s", (SCHEMA,))} == TABLES
            assert {row["tablename"] for row in saver_conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname=%s", (RUNTIME_SCHEMA,))} == NATIVE_TABLES
            replies, calls = [], []
            def synthetic(state):
                calls.append(state["jd_ai_run"]["run_id"])
                return {"messages": deepcopy(replies)}
            child = StateGraph(DocumentState)
            child.add_node("synthetic", synthetic)
            child.add_edge(START, "synthetic"); child.add_edge("synthetic", END)
            saver = PostgresSaver(saver_conn, serde=JsonPlusSerializer(allowed_msgpack_modules=None))
            graph = build_document_graph(child.compile(), saver)
            source = ConversationSourceService(AiRunCheckpoints(graph), ConversationSourceCodec(KEY, dataset))
            store = PostgresStore(store_conn)
            assert [row["v"] for row in store_conn.execute("SELECT v FROM store_migrations ORDER BY v")] == list(range(len(store.MIGRATIONS)))
            artifacts = MemoryArtifacts(store, document, source=MemorySourceReader(source, document))
            publication = PublicationStore(engine, artifacts)
            native = graph, dataset, document, replies, set(), calls
            yield native, source, artifacts, publication, store_conn, saver_conn
    finally:
        engine.dispose()


def text(artifacts, memory):
    return artifacts.reader(memory).read("/memory/knowledge.md").file_data["content"]


def test_saved_sources_memory_correction_stale_publish_and_new_connection_reopen():
    dataset, document = str(uuid4()), str(uuid4())
    original = "我會處理合約內設備的異常。\r\n  先記錄，權限還要確認。"
    correction = "更正：只做初步確認及記錄；維修由外包負責。"
    with opened(dataset, document) as (native, source, artifacts, pub, store_conn, saver_conn):
        first_run = append(native, [AIMessage(id="synthetic-followup", content="你也負責維修嗎？")], text=original)
        first_ref = source.capture(document, first_run.record.run_id).source_ref
        assert first_ref.startswith("conversation:")
        files = artifacts.save_extraction(summary="合約內設備的異常處理，權限尚待確認。",
            candidates="實際維修責任待釐清。", slug="異常處理", source_reference=first_ref)
        first_memory = artifacts.save_memory(knowledge=f"工作與未知\n[詳記]({files.summary_path})\n[原話]({first_ref})",
            guide=f"異常處理→[詳記]({files.summary_path})")
        first_request = pub.prepare(first_memory, expected_revision=0, kind="consolidation", processed_source=first_ref)
        first = pub.publish(first_request)
        fixed = artifacts.reader(first.memory)
        second_run = append(native, [AIMessage(id="synthetic-ack", content="已確認維修責任屬外包。")], text=correction)
        second_ref = source.capture(document, second_run.record.run_id).source_ref
        stale = pub.prepare(first.memory, expected_revision=1, kind="consolidation", processed_source=second_ref)
        corrected_memory = artifacts.save_memory(knowledge=f"只做初步確認及記錄；維修由外包負責。\n[原話]({second_ref})\n[早期詳記]({files.summary_path})",
            guide=f"異常初步確認→[原話]({second_ref})")
        repair_request = pub.prepare(corrected_memory, expected_revision=1, kind="repair", repair_sources=(second_ref,))
        repaired = pub.publish(repair_request)
        assert repaired.revision == 2 and repaired.processed_source == first_ref
        assert fixed.read("/memory/knowledge.md").file_data["content"] == text(artifacts, first.memory)
        assert "維修由外包" in text(artifacts, repaired.memory)
        with pytest.raises(StalePublication) as failure:
            pub.publish(stale)
        assert failure.value.current == repaired and pub.receipt(stale.operation_id) is None
        assert pub.current() == repaired and source.read(first_ref, document).messages[-1].text == original
        assert artifacts.extraction_window(files.summary_path) == {"source_reference": first_ref, "context_reference": None}
        assert len(native[-1]) == 2
        # A known committed receipt remains readable if artifact/source storage
        # is down. Shape/scope validation must not open either resource.
        store_conn.close(); saver_conn.close()
        assert pub.publish(first_request) == first and pub.publish(repair_request) == repaired
        assert pub.current() == repaired
    with opened(dataset, document) as (native, source, artifacts, pub, store_conn, _):
        assert pub.current() == repaired and pub.receipt(first_request.operation_id).result == first
        assert pub.publish(first_request) == first and pub.current() == repaired
        assert source.read(first_ref, document).messages[-1].text == original
        assert source.read(second_ref, document).messages[-1].text == correction
        assert artifacts.extraction_window(files.summary_path) == {"source_reference": first_ref, "context_reference": None}
        assert text(artifacts, first.memory).startswith("工作與未知")
        assert "維修由外包" in text(artifacts, pub.current().memory)
        assert not native[-1], "reopen/read/receipt must not invoke the synthetic consultant"
        assert len(pub.repair_receipts(after_revision=0, through_revision=2)) == 1
        assert store_conn.execute("SELECT count(*) AS n FROM q019_memory_publication_receipt WHERE document_id=%s",
            (document,)).fetchone()["n"] == 2
        assert store_conn.execute("SELECT count(*) AS n FROM store WHERE prefix LIKE %s",
            ("q019-memory." + document + ".%",)).fetchone()["n"] == 6
        print(f"synthetic Memory document={document}, head=2, receipts=2, artifacts=6, provider_calls=0")
