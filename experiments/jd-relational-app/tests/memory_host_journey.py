"""Synthetic Memory probe inside the actual configured host; not an App API."""
from dataclasses import asdict
import json
from threading import Event, Thread
from uuid import uuid4

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from caliburn_memory.memory import MemoryArtifacts, MemoryVersion
from caliburn_memory.publication import PublicationStore, PublishRequest
from jd_relational.memory_sources import MemorySourceReader
from jd_relational.runtime_checkpoints import DocumentState
from test_chat_history import append


def child():
    replies, calls, stores = [], [], []
    def synthetic(state, runtime: Runtime):
        calls.append(state["jd_ai_run"]["run_id"])
        stores.append(runtime.store)
        return {"messages": list(replies)}
    graph = StateGraph(DocumentState)
    graph.add_node("synthetic", synthetic)
    graph.add_edge(START, "synthetic"); graph.add_edge("synthetic", END)
    return graph.compile(), replies, calls, stores


def request(value):
    return PublishRequest(**{**value, "memory": MemoryVersion(**value["memory"]),
        "repair_sources": tuple(value["repair_sources"])})


def run(managed, mode, manifest, replies, calls, stores):
    host, settings = managed.opened.host, managed.opened.settings
    host.runtime.finish_startup(timeout=20)
    source = managed.ai_runtime.conversation_sources
    assert source is not None
    assert host.graph.store is host.store and host.store_connection is not host.saver_connection
    assert host.memory_engine.pool is host.engine.pool
    assert host.memory_engine.get_execution_options()["schema_translate_map"] == {None: settings.checkpoint_schema}
    if mode == "memory-write":
        document = host.runtime.create_document(uuid4(), "合成宿主工作理解")
    else:
        fixture = json.loads(manifest.read_text(encoding="utf-8"))
        assert fixture["dataset_id"] == settings.dataset_id
        document = fixture["document"]
    artifacts = MemoryArtifacts(host.store, document, source=MemorySourceReader(source, document))
    pub = PublicationStore(host.memory_engine, artifacts)
    if mode == "memory-write":
        native = host.graph, settings.dataset_id, document, replies, set(), calls
        original = "我會處理設備異常。\r\n  只限服務合約內的設備。"
        first_run = append(native, [AIMessage(id="synthetic-question", content="維修也由你負責嗎？")], text=original)
        first_source = source.capture(document, first_run.record.run_id).source_ref
        files = artifacts.save_extraction(summary="異常處理，實際維修責任尚待確認。", candidates="待釐清維修邊界。",
            slug="設備異常", source_reference=first_source)
        memory = artifacts.save_memory(knowledge=f"合約內設備異常處理。\n[詳記]({files.summary_path})",
            guide=f"異常处理→[詳記]({files.summary_path})")
        initial_request = pub.prepare(memory, expected_revision=0, kind="consolidation", processed_source=first_source)
        initial = pub.publish(initial_request)
        second_run = append(native, [AIMessage(id="synthetic-confirmation", content="已更正維修邊界。")],
            text="我只初步確認與記錄，維修由外包負責。")
        correction_source = source.capture(document, second_run.record.run_id).source_ref
        corrected = artifacts.save_memory(knowledge=f"合約內設備的初步確認與記錄；維修由外包負責。\n[更正原話]({correction_source})",
            guide=f"異常初步確認→[更正]({correction_source})")
        repair_request = pub.prepare(corrected, expected_revision=1, kind="repair", repair_sources=(correction_source,))
        repaired = pub.publish(repair_request)
        assert repaired.revision == 2 and repaired.processed_source == first_source
        assert stores == [host.store, host.store]
        fixture = {"dataset_id": settings.dataset_id, "document": document, "original": original,
            "first_source": first_source, "correction_source": correction_source,
            "summary_path": files.summary_path, "first_request": asdict(initial_request),
            "repair_request": asdict(repair_request)}
        manifest.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
    initial_request, repair_request = request(fixture["first_request"]), request(fixture["repair_request"])
    current = pub.current()
    assert current.revision == 2 and current.processed_source == fixture["first_source"]
    assert pub.publish(initial_request).revision == 1 and pub.current() == current
    assert pub.publish(repair_request) == current
    assert "維修由外包" in artifacts.reader(current.memory).read("/memory/knowledge.md").file_data["content"]
    assert source.read(fixture["first_source"], document).messages[-1].text == fixture["original"]
    assert artifacts.extraction_window(fixture["summary_path"])["source_reference"] == fixture["first_source"]
    assert len(calls) == (2 if mode == "memory-write" else 0)
    assert host.runtime.storage.read_current(document).revision_number == 1
    with host.engine.connect() as conn:
        assert conn.exec_driver_sql("SHOW search_path").scalar_one() == "public"
    # Actual admitted read must keep all resources open through a close timeout.
    entered, release = Event(), Event()
    results, errors = [], []
    def read():
        def materialized():
            entered.set()
            assert release.wait(10), "The test must release its own held read."
            return artifacts.guide(pub.current().memory)
        try:
            results.append(host.runtime.inspect_document(document, materialized))
        except BaseException as error:
            errors.append(type(error).__name__)
    reader = Thread(target=read)
    reader.start()
    try:
        assert entered.wait(5)
        assert host.close(timeout=0.01) is False
        assert not host.store_connection.closed and not host.saver_connection.closed
    finally:
        release.set()
        reader.join(timeout=10)
    assert not reader.is_alive() and not errors and len(results) == 1
    assert managed.close() is True
    assert host.store_connection.closed and host.saver_connection.closed
    return {"status": mode, "document": document, "dataset_id": settings.dataset_id,
        "memory_revision": current.revision, "jd_revision": 1, "closed": True,
        "drain_kept_resources": True, "synthetic_calls": len(calls), "provider_calls": 0}
