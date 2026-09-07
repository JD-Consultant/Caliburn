"""Persistence of artifact addresses and original source, not generated quality."""

import os
from uuid import uuid4

import httpx
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from analysis_agent.memory import MemoryArtifacts
from analysis_agent.sources import ConversationReader
from analysis_agent.provider import build_model
from analysis_agent.runtime import build_agent
from test_memory_read_path import setup_source


def test_postgres_reopen_preserves_artifacts_and_original_conversation():
    dsn = os.environ.get("Q019_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Set Q019_TEST_DATABASE_URL to dedicated q019_agent_test DB; not a persistence pass")
    params = conninfo_to_dict(dsn)
    assert params.get("dbname") == "q019_agent_test"
    assert 1 <= int(params.get("connect_timeout", "0")) <= 10
    dsn = make_conninfo(dsn, options="-c statement_timeout=10000 -c lock_timeout=5000")
    document = "q019-test-" + str(uuid4())
    # No embeddings configured, no paid service, no product credentials.
    with PostgresStore.from_conn_string(dsn) as store, PostgresSaver.from_conn_string(dsn) as saver:
        store.setup()
        saver.setup()
    try:
        with PostgresStore.from_conn_string(dsn) as store, PostgresSaver.from_conn_string(dsn) as saver:
            graph, reader, source, _ = setup_source(saver, document)
            artifacts = MemoryArtifacts(store, document)
            extraction = artifacts.save_extraction(summary="A網站一次付費，主管核准例外。", candidates="核准責任屬主管。", slug="案例A", source_reference=source)
            version = artifacts.save_memory(knowledge=f"# 網站交付\n依需求開發網站。\n[詳記]({extraction.summary_path})", guide="案例A → /memory/knowledge.md")
        # Entire DB clients and reader are recreated. Version is a runtime
        # handle, not a claim that durable current-head publication is done.
        with PostgresStore.from_conn_string(dsn) as store, PostgresSaver.from_conn_string(dsn) as saver:
            with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("Source read must not call LLM"))) as client:
                graph = build_agent(model=build_model(model="gpt-5.6-luna", api_key="offline", http_client=client), checkpointer=saver, instructions="test")
                artifacts = MemoryArtifacts(store, document)
                assert artifacts.guide(version) == "案例A → /memory/knowledge.md"
                backend = artifacts.reader(version)
                assert extraction.summary_path in backend.read("/memory/knowledge.md").file_data["content"]
                assert source in backend.read(extraction.summary_path).file_data["content"]
                window = artifacts.source_window(extraction.summary_path)
                assert window == {'source_reference': source, 'context_reference': None}
                page = ConversationReader(graph, document).read(window['source_reference'])
                assert [s["text"] for s in page["segments"]] == ["例外也是你核准嗎？", "不是，例外由主管核准。"]
                result = backend.grep("網站交付", "/memory/knowledge.md")
                assert result.matches and result.matches[0]["path"] == "/memory/knowledge.md"
    finally:
        with PostgresStore.from_conn_string(dsn) as store, PostgresSaver.from_conn_string(dsn) as saver:
            # Collect before deleting, to avoid paging offsets over a shrinking set.
            items, offset = [], 0
            while page := store.search(("q019-memory", document), limit=100, offset=offset):
                items.extend(page)
                offset += len(page)
            for item in items:
                store.delete(item.namespace, item.key)
            saver.delete_thread(document)
