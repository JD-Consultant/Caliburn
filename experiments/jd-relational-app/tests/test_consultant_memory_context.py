"""Real native read tools/context, synthetic source, SQLite/InMemoryStore only."""
from dataclasses import replace
import json
from uuid import uuid4

from caliburn_memory import MemoryArtifacts, PublicationStore
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
import pytest
import sqlalchemy as sa
from sqlalchemy.pool import StaticPool

from jd_relational.consultant_context import ConsultantContext, ConsultantState, JdNoticeMiddleware
from jd_relational.memory_context import MemoryReadError, MemoryReadSession, build_memory_read_tools, checked_memory_view
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
    def pin():
        return MemoryReadSession.open(store=store, engine=engine, sources=sources,
            dataset_id=dataset, document_id=document, run_id=str(uuid4()))
    yield store, publication, publish, pin
    engine.dispose()


def run_context(session, *, store=None, state=None, model=None):
    original, reply = setup()
    material = replace(original.turn_notice, document_id=session.document_id)
    context = replace(original, dataset_id=session.dataset_id, document_id=session.document_id,
        run_id=session.run_id, codec=type(original.codec)(b"s"*32, session.dataset_id),
        history=MaterialReader(material), turn_notice=material, memory_session=session)
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
    call = AIMessage(id="memory-read-call", content="", response_metadata={"stop_reason": "tool_use"},
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
