"""Real native read tools/context, synthetic source, SQLite/InMemoryStore only."""
from dataclasses import replace
import json
from uuid import uuid4

from caliburn_memory import (
    CaseArtifact, MemoryArtifacts, PublicationStore, WorkUnderstandingArtifact,
)
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
import pytest
import sqlalchemy as sa
from sqlalchemy.pool import StaticPool

from jd_relational.consultant_context import ConsultantContext, ConsultantState, JdNoticeMiddleware
from jd_relational.memory_context import (
    MemoryReadError, MemoryReadSession, build_memory_read_tools,
    checked_memory_view, layered_read_proof,
)
from jd_relational.memory_repair_session import MemoryRepairSession
from jd_relational.memory_sources import MemorySourceReader
from jd_relational.runtime_checkpoints import build_document_graph
from test_chat_history import native
from test_conversation_sources import seed, service
from test_consultant_context import FixedModel, MaterialReader, setup


@pytest.fixture
def memory(native):
    observed, _ = seed(native)
    _, dataset, document, *_ = native
    sources = service(native)
    source_ref = sources.capture(document, observed.record.run_id).source_ref
    safe_run_id = sources.safe_turns(document)[0]["input_id"]
    bundle_source_ref = sources.capture(document, safe_run_id).source_ref
    source_window = sources.capture_window(
        document, first_run_id=safe_run_id, last_run_id=safe_run_id)
    store = InMemoryStore()
    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    artifacts = MemoryArtifacts(store, document, source=MemorySourceReader(sources, document))
    publication = PublicationStore(engine, artifacts)
    publication.setup()  # Explicit unit fixture only.
    def publish(revision, text):
        version = artifacts.save_memory(knowledge=text, guide="導覽：" + text)
        request = publication.prepare(version, expected_revision=revision,
            kind="consolidation", processed_source=source_ref)
        return publication.publish(request)
    def publish_bundle(revision, *, base_version=None, case_id=None, understanding_id=None,
                       case_text="本人先做設備故障初判。"):
        bundle_artifacts = MemoryArtifacts(store, document, source=MemorySourceReader(
            sources, document, window_references=True))
        bundle_publication = PublicationStore(engine, bundle_artifacts)
        case_id = case_id or str(uuid4())
        understanding_id = understanding_id or str(uuid4())
        case_path = f"/memory/cases/items/{case_id}.md"
        understanding_path = f"/memory/understanding/items/{understanding_id}.md"
        version = bundle_artifacts.save_bundle(
            base_publication_revision=revision,
            base_version=base_version,
            evidence_through_reference=source_window,
            case_guide=f"故障處理案例：[{case_id}]({case_path})",
            cases=(CaseArtifact(case_id, case_text, (bundle_source_ref,)),),
            understanding_guide=f"穩定故障初判責任：[{understanding_id}]({understanding_path})",
            understandings=(WorkUnderstandingArtifact(
                understanding_id,
                f"本人穩定負責初判；支持案例 [{case_id}]({case_path})。",
                (case_id,),
            ),),
        )
        request = bundle_publication.prepare(version, expected_revision=revision,
            kind="consolidation", processed_source=source_window)
        return bundle_publication.publish(request), case_path, understanding_path, bundle_source_ref
    def pin():
        return MemoryReadSession.open(store=store, engine=engine, sources=sources,
            dataset_id=dataset, document_id=document, run_id=str(uuid4()))
    publish.bundle = publish_bundle
    yield store, publication, publish, pin
    engine.dispose()


def run_context(session, *, store=None, state=None, model=None, repair=None):
    original, reply = setup()
    material = replace(original.turn_notice, document_id=session.document_id)
    context = replace(original, dataset_id=session.dataset_id, document_id=session.document_id,
        run_id=session.run_id, codec=type(original.codec)(b"s"*32, session.dataset_id),
        history=MaterialReader(material), turn_notice=material, memory_session=session,
        memory_repair_session=repair)
    model = model or FixedModel(replies=[reply])
    child = create_agent(model, tools=build_memory_read_tools(session.backend), system_prompt="合成顧問",
        middleware=[JdNoticeMiddleware()], state_schema=ConsultantState, context_schema=ConsultantContext)
    root = build_document_graph(child, InMemorySaver(), store=store or session.artifacts.store)
    human = HumanMessage(id=session.run_id, content="原話\r\n  不要改成導覽。")
    result = root.invoke({"messages": [human], "jd_memory_view": session.view if state is None else state},
        {"configurable": {"thread_id": session.document_id}}, context=context, durability="sync")
    return result, model.requests, human


def test_head_is_pinned_across_real_model_and_native_file_tool_calls(memory):
    store, pub, publish, pin = memory
    first = publish(0, "只做初步確認。")
    session = pin()
    class UpdatingModel(FixedModel):
        def _generate(self, *args, **kwargs):
            if not self.requests:
                publish(1, "維修由外包負責。")
            return super()._generate(*args, **kwargs)
    call = AIMessage(id="memory-read-call", content="",
        response_metadata={"status": "completed", "finish_reason": "tool_calls"},
        tool_calls=[{"name": "read_file", "id": "tool-memory-read", "args": {
            "file_path": "/memory/knowledge.md", "offset": 0, "limit": 100}}])
    _, final = setup()
    result, requests, human = run_context(session, model=UpdatingModel(replies=[call, final]))
    assert pub.current().revision == 2 and session.head == first
    assert result["jd_memory_view"] == session.view
    for request in requests:
        notice = json.loads(request[0].content[-1]["text"])
        assert notice["type"] == "memory_guide" and notice["revision"] == 1
        assert notice["guide"] == "導覽：只做初步確認。"
        assert request[1].model_dump() == human.model_dump()
    tool = next(m for m in result["messages"] if isinstance(m, ToolMessage))
    assert "只做初步確認。" in tool.content and "維修由外包" not in tool.content
    assert pin().guide == "導覽：維修由外包負責。"


def test_no_publication_is_explicit_empty_and_does_not_refresh_mid_turn(memory):
    _, _, publish, pin = memory
    empty = pin()
    publish(0, "後來才整理的工作。")
    result, requests, human = run_context(empty)
    notice = json.loads(requests[0][0].content[-1]["text"])
    assert notice["published"] is False and notice["guide"] == "" and notice["revision"] == 0
    assert result["messages"][0] == human
    assert empty.backend.read("/memory/knowledge.md").error


def test_model_notice_uses_the_explicitly_refreshed_turn_baseline(memory, monkeypatch):
    _, pub, publish, pin = memory
    publish(0, "回合開始版本。")
    initial = pin()
    publish(1, "明確刷新後版本。")
    refreshed = replace(pin(), run_id=initial.run_id)
    repair = MemoryRepairSession(initial, pub)
    monkeypatch.setattr(repair, "current_read", lambda state: refreshed)

    _, requests, _ = run_context(initial, repair=repair)

    notice = json.loads(requests[0][0].content[-1]["text"])
    assert notice["revision"] == 2
    assert notice["guide"] == "導覽：明確刷新後版本。"


@pytest.mark.parametrize("mismatch", ["state", "store", "run", "document", "guide"])
def test_wrong_scope_stops_before_actual_model_or_backend(memory, monkeypatch, mismatch):
    _, _, publish, pin = memory
    publish(0, "不可讀到錯誤文件")
    session = pin()
    model = FixedModel(replies=[])
    # Run-external pin is done. Neither projection nor tools may read now.
    monkeypatch.setattr(session.backend, "read", lambda *a, **kw: pytest.fail("scope before read"))
    kwargs = {"model": model}
    if mismatch == "state": kwargs["state"] = session.view | {"revision": 99}
    if mismatch == "store": kwargs["store"] = InMemoryStore()
    if mismatch == "run": kwargs["state"] = session.view | {"run_id": str(uuid4())}
    if mismatch == "document": kwargs["state"] = session.view | {"document_id": str(uuid4())}
    if mismatch == "guide":
        # A session with a different immutable head cannot use a forged state.
        session = replace(session, guide="changed after pin")
        kwargs["state"] = pin().view
    with pytest.raises(MemoryReadError, match="invalid_memory_session"):
        run_context(session, **kwargs)
    assert not model.requests


def test_missing_published_guide_is_not_an_empty_memory_fallback(memory, monkeypatch):
    _, _, publish, pin = memory
    publish(0, "已保存")
    monkeypatch.setattr(MemoryArtifacts, "read_text", lambda *a, **kw: (_ for _ in ()).throw(
        RuntimeError("PRIVATE_CONNECTION_OR_BODY")))
    with pytest.raises(MemoryReadError, match="^memory_not_available$") as failure:
        pin()
    assert failure.value.__suppress_context__


@pytest.mark.parametrize("changes", [{"revision": True}, {"revision": -1}, {"version_id": None},
    {"guide_digest": "not-a-digest"}, {"unexpected": "private"}, {"run_id": str(uuid4())}])
def test_saved_memory_view_is_strict_and_bound_to_its_run(memory, changes):
    _, _, publish, pin = memory
    publish(0, "已保存")
    session = pin()
    with pytest.raises(MemoryReadError, match="invalid_memory_view"):
        checked_memory_view(session.view | changes, dataset_id=session.dataset_id,
            document_id=session.document_id, run_id=session.run_id)


def test_layered_bundle_starts_from_both_guides_and_reads_both_layers_on_the_pinned_version(memory):
    _, publication, publish, pin = memory
    head, case_path, understanding_path, source_ref = publish.bundle(0)
    session = pin()
    case_call = AIMessage(id="case-read-call", content="",
        response_metadata={"status": "completed", "finish_reason": "tool_calls"},
        tool_calls=[{"name": "read_case", "id": "tool-case-read", "args": {
            "case_id": case_path.removeprefix("/memory/cases/items/").removesuffix(".md")}}])
    understanding_call = AIMessage(id="understanding-read-call", content="",
        response_metadata={"status": "completed", "finish_reason": "tool_calls"},
        tool_calls=[{"name": "read_work_understanding", "id": "tool-understanding-read", "args": {
            "understanding_id": understanding_path.removeprefix(
                "/memory/understanding/items/").removesuffix(".md")}}])
    source_call = AIMessage(id="source-read-call", content="",
        response_metadata={"status": "completed", "finish_reason": "tool_calls"},
        tool_calls=[{"name": "read_conversation", "id": "tool-source-read", "args": {
            "reference": source_ref}}])
    _, final = setup()

    class UpdatingModel(FixedModel):
        def _generate(self, *args, **kwargs):
            if not self.requests:
                publish.bundle(
                    1, base_version=head.memory,
                    case_id=case_path.removeprefix("/memory/cases/items/").removesuffix(".md"),
                    understanding_id=understanding_path.removeprefix(
                        "/memory/understanding/items/").removesuffix(".md"),
                    case_text="新版改由外包處理。",
                )
            return super()._generate(*args, **kwargs)

    result, requests, _ = run_context(
        session, model=UpdatingModel(replies=[
            case_call, understanding_call, source_call, final,
        ]))

    assert session.head == head and session.view["version_id"] == head.memory.version_id
    notice = json.loads(requests[0][0].content[-1]["text"])
    assert notice["type"] == "memory_guide" and notice["revision"] == 1
    assert "案例導覽" in notice["guide"] and "/memory/cases/guide.md" in notice["guide"]
    assert "工作理解導覽" in notice["guide"] and "/memory/understanding/guide.md" in notice["guide"]
    assert case_path in notice["guide"] and understanding_path in notice["guide"]
    assert "本人先做設備故障初判" not in notice["guide"]
    assert "本人穩定負責初判" not in notice["guide"]
    feedback = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    contents = [message.content for message in feedback]
    assert all("schema_version" not in content for content in contents)
    assert any("本人先做設備故障初判" in content for content in contents)
    assert any("source_references" in content and "conversation:" in content for content in contents)
    assert any("本人穩定負責初判" in content and "case_bindings" in content
               and "case_digest" in content for content in contents)
    assert any("前一輪原話" in content for content in contents)
    assert all("新版改由外包處理" not in content for content in contents)
    case_result = json.loads(next(message.content for message in feedback
                                  if message.name == "read_case"))
    understanding_result = json.loads(next(message.content for message in feedback
                                           if message.name == "read_work_understanding"))
    source_result = json.loads(next(message.content for message in feedback
                                    if message.name == "read_conversation"))
    assert case_result["memory_revision"] == understanding_result["memory_revision"] == 1
    assert case_result["memory_version_id"] == understanding_result["memory_version_id"] \
        == head.memory.version_id
    assert case_result["evidence"] == [{
        "evidence_key": "E1", "source_reference": source_ref,
    }]
    assert source_result["read_offset"] == 0 and source_result["next_offset"] is None
    proof = layered_read_proof(
        result["messages"], run_id=session.run_id,
        revision=1, version_id=head.memory.version_id,
    )
    case_id = case_path.removeprefix("/memory/cases/items/").removesuffix(".md")
    understanding_id = understanding_path.removeprefix(
        "/memory/understanding/items/",
    ).removesuffix(".md")
    assert proof.case_evidence == {case_id: {"E1": source_ref}}
    assert proof.understanding_ids == frozenset({understanding_id})
    assert proof.complete_sources == frozenset({source_ref})
    assert publication.current().revision == 2 and publication.current() != head
