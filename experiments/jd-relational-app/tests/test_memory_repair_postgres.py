"""One real PG/Saver/Store C journey, no provider, DDL or full App C claim.

The repair-only parent has its own synthetic thread, so it cannot overwrite
the saved conversation root. Reopen uses new connections in this process.
"""
from dataclasses import asdict
import os
from uuid import uuid4

from langchain_core.messages import AIMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
import pytest

from caliburn_memory import MemoryVersion, PublishRequest, PublicationUncertain
import caliburn_memory.repair as repair_module
from caliburn_memory.repair import RepairState, RepairWorkflow
from jd_relational.ai_checkpoints import AiRunCheckpoints
from jd_relational.manual_runtime import ManualRuntime
from jd_relational.runtime_checkpoints import DocumentCheckpoints
from jd_relational.storage.service import JdReader, JdStorage
from test_chat_history import append
from test_manual_runtime_postgres import connect, native_graph
from test_memory_core_postgres import opened
from test_storage_postgres import engine


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")


class PreparedPause(RepairWorkflow):
    def _publish(self, state):
        interrupt("synthetic_pause_after_saved_publish_request")
        return super()._publish(state)


def parent(workflow, saver):
    graph = StateGraph(RepairState)
    graph.add_node("repair", workflow.graph)
    graph.add_edge(START, "repair")
    graph.add_edge("repair", END)
    return graph.compile(checkpointer=saver)


def prepared(graph, config):
    snapshot = graph.get_state(config, subgraphs=True)
    assert snapshot.next == ("repair",) and len(snapshot.tasks) == 1
    child = snapshot.tasks[0].state
    # Read the exact saved child; do not infer preparation from latest overlay.
    fixed = graph.get_state(child.config)
    assert fixed.config == child.config and fixed.next == ("publish",)
    data = dict(fixed.values["request"])
    data["memory"] = MemoryVersion(**data["memory"])
    data["repair_sources"] = tuple(data["repair_sources"])
    return fixed, PublishRequest(**data)


def seed_jd(engine):
    with connect() as connection:
        graph, _ = native_graph(PostgresSaver(connection,
            serde=JsonPlusSerializer(allowed_msgpack_modules=None)))
        owner = ManualRuntime(DocumentCheckpoints(graph), lambda authority: JdStorage(engine, authority))
        try:
            document = owner.create_document(uuid4(), "合成C修補，不改JD驗收")
            original = owner.storage.read_current(document)
        finally:
            assert owner.close(timeout=10)
    return document, original


def test_two_file_repair_saved_request_commit_ack_loss_and_new_connection_reconcile(engine, monkeypatch):
    document, original_jd = seed_jd(engine)
    dataset, operation, repair_thread = str(uuid4()), str(uuid4()), str(uuid4())
    config = {"configurable": {"thread_id": repair_thread}}
    original = "例外由主管核准。\r\n  員工只彙整資料；其他責任不變。"
    correction = "更正：例外是處長核准，員工仍只彙整資料。"
    with opened(dataset, document) as (native, source, artifacts, pub, store_conn, saver_conn):
        first = append(native, [AIMessage(id="repair-first-reply", content="先保留核准邊界。")], text=original)
        first_ref = source.capture(document, first.record.run_id).source_ref
        detail = artifacts.save_extraction(summary="員工只彙整；核准由主管負責。", candidates="確認核准者。",
            slug="修補原始詳記", source_reference=first_ref)
        knowledge = f"例外由主管核准。\n其他責任不變。\n[詳記]({detail.summary_path})"
        guide = "主管核准：/memory/knowledge.md"
        version = artifacts.save_memory(knowledge=knowledge, guide=guide)
        base = pub.publish(pub.prepare(version, expected_revision=0, kind="consolidation",
            processed_source=first_ref))
        second = append(native, [AIMessage(id="repair-second-reply", content="核准者更正為處長。")], text=correction)
        correction_ref = source.capture(document, second.record.run_id).source_ref
        original_messages = second.messages
        original_source_root = second.root_config
        workflow = PreparedPause(artifacts, pub, artifacts.source)
        graph = parent(workflow, native[0].checkpointer)
        edits = [{"path": "/memory/knowledge.md", "diff": "@@\n-例外由主管核准。\n+例外由處長核准。\n 其他責任不變。"},
            {"path": "/memory/guide.md", "diff": "@@\n-主管核准：/memory/knowledge.md\n+處長核准：/memory/knowledge.md"}]
        calls = {"patch": [], "save": 0, "publish": []}
        actual_patch, actual_save, actual_publish = repair_module.apply_staged_patch, artifacts.save_memory, pub.publish

        def counted_patch(path, diff):
            calls["patch"].append(path)
            return actual_patch(path, diff)

        def counted_save(**material):
            calls["save"] += 1
            return actual_save(**material)

        def commit_then_lose(request):
            calls["publish"].append(request)
            actual_publish(request)  # The real short SQL transaction commits.
            raise PublicationUncertain("synthetic_commit_ack_lost")

        def forbidden(*args, **kwargs):
            pytest.fail("Reconciliation must not patch, save, publish or replay source reads")

        with monkeypatch.context() as spy:
            spy.setattr(repair_module, "apply_staged_patch", counted_patch)
            spy.setattr(artifacts, "save_memory", counted_save)
            spy.setattr(pub, "publish", commit_then_lose)
            graph.invoke({"operation_id": operation, "base": asdict(base), "source_reference": correction_ref,
                "edits": edits, "index": 0, "outcome": None}, config, durability="sync")
            fixed, request = prepared(graph, config)
            assert fixed.values["base"] == asdict(base) and fixed.values["index"] == 2
            assert request.operation_id == operation and request.expected_revision == 1
            assert request.kind == "repair" and request.processed_source is None
            assert request.repair_sources == (correction_ref,)
            assert pub.current() == base and pub.receipt(operation) is None
            assert calls == {"patch": [edit["path"] for edit in edits], "save": 1, "publish": []}
            assert artifacts.read_text("/memory/knowledge.md", request.memory) == knowledge.replace("主管", "處長")
            assert artifacts.guide(request.memory) == guide.replace("主管", "處長")
            with pytest.raises(PublicationUncertain):
                workflow.reconcile(request)  # No receipt is unknown, not permission to publish.
            assert not calls["publish"]
            with pytest.raises(PublicationUncertain, match="synthetic_commit_ack_lost"):
                graph.invoke(Command(resume=True), config, durability="sync")
            after_failure, same_request = prepared(graph, config)
            assert same_request == request and after_failure.values["request"] == fixed.values["request"]
            applied = pub.current()
            assert applied.revision == 2 and applied.processed_source == base.processed_source == first_ref
            receipt = pub.receipt(operation)
            assert receipt.base_revision == 1 and receipt.result == applied
            assert receipt.request_digest == request.digest() and receipt.repair_sources == (correction_ref,)
            assert calls == {"patch": [edit["path"] for edit in edits], "save": 1, "publish": [request]}
            with monkeypatch.context() as stopped:
                stopped.setattr(repair_module, "apply_staged_patch", forbidden)
                stopped.setattr(artifacts, "save_memory", forbidden)
                stopped.setattr(artifacts.store, "put", forbidden)
                stopped.setattr(pub, "publish", forbidden)
                stopped.setattr(source, "read", forbidden)
                recovered = workflow.reconcile(same_request)
            assert recovered["status"] == "applied" and recovered["applied_head"] == asdict(applied)
            assert recovered["head"] == asdict(applied) and recovered["source_reference"] == correction_ref
            assert "changes" not in recovered
        later_version = artifacts.save_memory(knowledge=knowledge.replace("主管", "處長") + "\n後續有效工作保留。",
            guide="後續導覽：/memory/knowledge.md")
        later = pub.publish(pub.prepare(later_version, expected_revision=2, kind="consolidation",
            processed_source=correction_ref))
        assert later.revision == 3 and later.processed_source == correction_ref
        assert native[0].get_state(original_source_root).values["messages"] == list(original_messages)
        assert AiRunCheckpoints(native[0]).observe(document, second.record.run_id, dataset) == second
        assert JdReader(engine).read_current(document) == original_jd
        assert store_conn.execute("SELECT count(*) AS n FROM q019_memory_publication_receipt WHERE document_id=%s",
            (document,)).fetchone()["n"] == 3

    with opened(dataset, document) as (native, source, artifacts, pub, store_conn, saver_conn):
        reopened = parent(PreparedPause(artifacts, pub, artifacts.source), native[0].checkpointer)
        saved, reopened_request = prepared(reopened, config)
        assert reopened_request == request and saved.values["base"] == asdict(base)
        with monkeypatch.context() as stopped:
            stopped.setattr(repair_module, "apply_staged_patch", forbidden)
            stopped.setattr(artifacts, "save_memory", forbidden)
            stopped.setattr(artifacts.store, "put", forbidden)
            stopped.setattr(pub, "publish", forbidden)
            stopped.setattr(source, "read", forbidden)
            recovered = RepairWorkflow(artifacts, pub, artifacts.source).reconcile(reopened_request)
        assert recovered["applied_head"] == asdict(applied)
        assert recovered["head"] == asdict(later) and recovered["guide"] == "後續導覽：/memory/knowledge.md"
        assert recovered["source_reference"] == correction_ref and "changes" not in recovered
        assert pub.current() == later and pub.receipt(operation) == receipt
        assert source.read(first_ref, document).messages[-1].text == original
        assert source.read(correction_ref, document).messages[-1].text == correction
        assert native[0].get_state(original_source_root).values["messages"] == list(original_messages)
        assert AiRunCheckpoints(native[0]).observe(document, second.record.run_id, dataset) == second
        assert not native[-1], "new connection read/reconcile must not invoke the synthetic conversation node"
        assert JdReader(engine).read_current(document) == original_jd
        assert store_conn.execute("SELECT count(*) AS n FROM q019_memory_publication_receipt WHERE document_id=%s",
            (document,)).fetchone()["n"] == 3
        print(f"synthetic C document={document}, repair_thread={repair_thread}, memory_head=3, "
            f"applied_head=2, receipts=3, patches=2, JD_head={original_jd.revision_number}, provider_calls=0")
