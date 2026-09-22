"""Real native read tools/context, synthetic source, SQLite/InMemoryStore only."""
from dataclasses import replace
from copy import deepcopy
import json
from types import SimpleNamespace
from uuid import uuid4

from caliburn_memory import (
    CaseArtifact, MemoryArtifacts, PublicationStore, WorkUnderstandingArtifact,
)
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.store.memory import InMemoryStore
import pytest
import sqlalchemy as sa
from sqlalchemy.pool import StaticPool

from jd_relational.consultant_context import ConsultantContext, ConsultantState, JdNoticeMiddleware
from jd_relational.memory_context import (
    MemoryReadError, MemoryReadSession, build_memory_read_tools,
    bind_memory_read_request, case_read_projection, checked_memory_view, evidence_read_projection,
    issue_evidence_key, layered_read_proof,
)
from jd_relational.memory_repair_session import MemoryRepairSession
from jd_relational.memory_read_tools import _jd_evidence_projection
from jd_relational.consultant_tools import RuntimeEvidence
from jd_relational.memory_sources import MemorySourceReader
from jd_relational.runtime_checkpoints import build_document_graph
from test_chat_history import native
from test_conversation_sources import seed, service
from test_consultant_context import FixedModel, MaterialReader, setup


def model_notice(request, kind):
    return next(json.loads(block["text"]) for block in request[0].content
                if block["text"].startswith("{")
                and json.loads(block["text"]).get("type") == kind)


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
        notice = model_notice(request, "memory_guide")
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
    notice = model_notice(requests[0], "memory_guide")
    assert notice["published"] is False and notice["guide"] == "" and notice["revision"] == 0
    assert result["messages"][0] == human
    assert empty.backend.read("/memory/knowledge.md").error


@pytest.mark.parametrize("layered", [False, True])
def test_model_file_tool_reads_mounted_analysis_skill_with_or_without_memory(memory, monkeypatch, layered):
    _, _, publish, pin = memory
    case_path = None
    if layered:
        _, case_path, _, _ = publish.bundle(0)
    session = pin()
    monkeypatch.setattr("jd_relational.memory_context.memory_session", lambda runtime: session)
    request = SimpleNamespace(
        tool_call={"name": "read_file"},
        runtime=object(),
        override=lambda **kwargs: SimpleNamespace(**kwargs),
    )
    tool = bind_memory_read_request(request).tool
    graph = StateGraph(MessagesState)
    graph.add_node("tools", ToolNode([tool]))
    graph.add_edge(START, "tools")
    graph.add_edge("tools", END)
    result = graph.compile().invoke({"messages": [AIMessage(content="", tool_calls=[{
        "id": "read-analysis-method", "name": "read_file",
        "args": {"file_path": "/skills/work-scope-interview/SKILL.md", "offset": 0, "limit": 1000},
    }])]}, {"configurable": {"thread_id": session.document_id}})
    reply = result["messages"][-1]
    assert reply.status == "success", reply.content
    assert "name: work-scope-interview" in reply.content
    if layered:
        denied = graph.compile().invoke({"messages": [AIMessage(content="", tool_calls=[{
            "id": "generic-memory-bypass", "name": "read_file",
            "args": {"file_path": case_path, "offset": 0, "limit": 10},
        }])]}, {"configurable": {"thread_id": session.document_id}})["messages"][-1]
        assert denied.status == "error"
        assert "layered_memory_requires_typed_read" in denied.content


def test_model_notice_uses_the_explicitly_refreshed_turn_baseline(memory, monkeypatch):
    _, pub, publish, pin = memory
    publish(0, "回合開始版本。")
    initial = pin()
    publish(1, "明確刷新後版本。")
    refreshed = replace(pin(), run_id=initial.run_id)
    repair = MemoryRepairSession(initial, pub)
    monkeypatch.setattr(repair, "current_read", lambda state: refreshed)

    _, requests, _ = run_context(initial, repair=repair)

    notice = model_notice(requests[0], "memory_guide")
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
    case_id = case_path.removeprefix("/memory/cases/items/").removesuffix(".md")
    evidence_key = issue_evidence_key(
        dataset_id=session.dataset_id,
        document_id=session.document_id,
        run_id=session.run_id,
        case_id=case_id,
        source_reference=source_ref,
    )
    source_call = AIMessage(id="source-read-call", content="",
        response_metadata={"status": "completed", "finish_reason": "tool_calls"},
        tool_calls=[{"name": "read_evidence", "id": "tool-source-read", "args": {
            "evidence_key": evidence_key}}])
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
    notice = model_notice(requests[0], "memory_guide")
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
    assert all("source_references" not in content and "conversation:" not in content
               and "memory_version_id" not in content and "memory_revision" not in content
               and "case_digest" not in content for content in contents)
    assert any("本人穩定負責初判" in content and "case_bindings" in content
               for content in contents)
    assert any("前一輪原話" in content for content in contents)
    assert all("新版改由外包處理" not in content for content in contents)
    case_result = json.loads(next(message.content for message in feedback
                                  if message.name == "read_case"))
    understanding_result = json.loads(next(message.content for message in feedback
                                           if message.name == "read_work_understanding"))
    source_result = json.loads(next(message.content for message in feedback
                                    if message.name == "read_evidence"))
    assert case_result["evidence"] == [{"evidence_key": evidence_key}]
    assert source_result["evidence_key"] == evidence_key
    assert source_result["has_more"] is False
    case_message = next(message for message in feedback if message.name == "read_case")
    source_message = next(message for message in feedback if message.name == "read_evidence")
    assert case_message.artifact["memory_revision"] == 1
    assert case_message.artifact["memory_version_id"] == head.memory.version_id
    assert case_message.artifact["evidence"][0]["source_reference"] == source_ref
    assert source_message.artifact["source_reference"] == source_ref
    assert source_message.artifact["read_offset"] == 0
    assert source_message.artifact["next_offset"] is None
    # The native model boundary still carries ToolMessage objects; only their
    # content is provider-visible. The OpenRouter wire exclusion is asserted
    # separately at the adapter boundary.
    assert all(
        source_ref not in message.content
        for request in requests
        for message in request
        if isinstance(message, ToolMessage) and isinstance(message.content, str)
    )
    proof = layered_read_proof(
        result["messages"], dataset_id=session.dataset_id,
        document_id=session.document_id, run_id=session.run_id,
        revision=1, version_id=head.memory.version_id,
    )
    understanding_id = understanding_path.removeprefix(
        "/memory/understanding/items/",
    ).removesuffix(".md")
    assert proof.case_evidence == {case_id: {evidence_key: source_ref}}
    assert proof.understanding_ids == frozenset({understanding_id})
    assert proof.complete_case_evidence == frozenset({(case_id, evidence_key)})
    assert publication.current().revision == 2 and publication.current() != head


def test_same_source_has_case_scoped_keys_and_read_proof(memory):
    _, _, publish, pin = memory
    _, case_path, _, source_ref = publish.bundle(0)
    session = pin()
    first_id = case_path.removeprefix("/memory/cases/items/").removesuffix(".md")
    first = session.artifacts.case(session.head.memory, first_id)
    second = replace(first, case_id=str(uuid4()))
    first_content, first_artifact = case_read_projection(session, first)
    second_content, second_artifact = case_read_projection(session, second)
    first_key = first_artifact["evidence"][0]["evidence_key"]
    second_key = second_artifact["evidence"][0]["evidence_key"]
    resumed_content, resumed_artifact = case_read_projection(session, first)
    next_run_artifact = case_read_projection(
        replace(session, run_id=str(uuid4())), first,
    )[1]
    assert resumed_content == first_content
    assert resumed_artifact["evidence"][0]["evidence_key"] == first_key
    assert next_run_artifact["evidence"][0]["evidence_key"] != first_key
    assert first_key != second_key

    evidence_content, evidence_artifact = evidence_read_projection(
        session,
        case_id=first_id,
        evidence_key=first_key,
        source_reference=source_ref,
        page={
            "segments": [{"role": "user", "text": "合成原話", "text_offset": 0}],
            "read_offset": 0,
            "next_offset": None,
        },
    )
    messages = [
        HumanMessage(id=session.run_id, content="合成"),
        AIMessage(id="case-a", content="", tool_calls=[{
            "name": "read_case", "id": "case-a-call", "args": {"case_id": first_id},
        }]),
        ToolMessage(id="case-a-result", name="read_case", tool_call_id="case-a-call",
                    content=first_content, artifact=first_artifact),
        AIMessage(id="case-b", content="", tool_calls=[{
            "name": "read_case", "id": "case-b-call", "args": {"case_id": second.case_id},
        }]),
        ToolMessage(id="case-b-result", name="read_case", tool_call_id="case-b-call",
                    content=second_content, artifact=second_artifact),
        AIMessage(id="source-a", content="", tool_calls=[{
            "name": "read_evidence", "id": "source-a-call", "args": {"evidence_key": first_key},
        }]),
        ToolMessage(id="source-a-result", name="read_evidence", tool_call_id="source-a-call",
                    content=evidence_content, artifact=evidence_artifact),
    ]
    proof = layered_read_proof(
        messages,
        dataset_id=session.dataset_id,
        document_id=session.document_id,
        run_id=session.run_id,
        revision=session.head.revision,
        version_id=session.head.memory.version_id,
    )
    assert proof.case_evidence[first_id][first_key] == source_ref
    assert proof.case_evidence[second.case_id][second_key] == source_ref
    assert (first_id, first_key) in proof.complete_case_evidence
    assert (second.case_id, second_key) not in proof.complete_case_evidence

    tampered = deepcopy(messages)
    tampered[-1].artifact["document_id"] = str(uuid4())
    with pytest.raises(MemoryReadError, match="invalid_layered_read_proof"):
        layered_read_proof(
            tampered,
            dataset_id=session.dataset_id,
            document_id=session.document_id,
            run_id=session.run_id,
            revision=session.head.revision,
            version_id=session.head.memory.version_id,
        )


def test_layered_proof_ignores_known_jd_evidence_but_rejects_unknown_kind(memory):
    _, _, publish, pin = memory
    _, case_path, _, source_ref = publish.bundle(0)
    session = pin()
    case_id = case_path.removeprefix("/memory/cases/items/").removesuffix(".md")
    case = session.artifacts.case(session.head.memory, case_id)
    case_content, case_artifact = case_read_projection(session, case)
    case_key = case_artifact["evidence"][0]["evidence_key"]
    jd_entry = RuntimeEvidence("E-jd-source", source_ref, "jd_source", "jd-item", "available", 0)
    jd_content, jd_artifact = _jd_evidence_projection(
        jd_entry,
        {"segments": [{"role": "user", "text": "合成 JD 原話", "text_offset": 0}],
         "read_offset": 0, "next_offset": None},
        session,
    )
    messages = [
        HumanMessage(id=session.run_id, content="核對案例及 JD 來源"),
        AIMessage(id="case-call", content="", tool_calls=[{
            "name": "read_case", "id": "case-call-id", "args": {"case_id": case_id},
        }]),
        ToolMessage(id="case-result", name="read_case", tool_call_id="case-call-id",
                    content=case_content, artifact=case_artifact),
        AIMessage(id="jd-source-call", content="", tool_calls=[{
            "name": "read_evidence", "id": "jd-source-call-id",
            "args": {"evidence_key": jd_entry.evidence_key},
        }]),
        ToolMessage(id="jd-source-result", name="read_evidence",
                    tool_call_id="jd-source-call-id", content=jd_content, artifact=jd_artifact),
    ]
    proof = layered_read_proof(
        messages, dataset_id=session.dataset_id, document_id=session.document_id,
        run_id=session.run_id, revision=session.head.revision,
        version_id=session.head.memory.version_id,
    )
    assert proof.case_evidence == {case_id: {case_key: source_ref}}
    assert proof.complete_case_evidence == frozenset()

    unknown = deepcopy(messages)
    unknown[-1].artifact["kind"] = "unknown_evidence_kind"
    with pytest.raises(MemoryReadError, match="invalid_layered_read_proof"):
        layered_read_proof(
            unknown, dataset_id=session.dataset_id, document_id=session.document_id,
            run_id=session.run_id, revision=session.head.revision,
            version_id=session.head.memory.version_id,
        )


def test_unknown_or_other_run_evidence_key_never_reads_source(memory, monkeypatch):
    _, _, publish, pin = memory
    _, case_path, _, source_ref = publish.bundle(0)
    session = pin()
    other_run_key = issue_evidence_key(
        dataset_id=session.dataset_id,
        document_id=session.document_id,
        run_id=str(uuid4()),
        case_id=case_path.removeprefix("/memory/cases/items/").removesuffix(".md"),
        source_reference=source_ref,
    )
    monkeypatch.setattr(type(session.source), "read",
                        lambda *_: pytest.fail("unknown key read source"))
    call = AIMessage(
        id="unknown-evidence",
        content="",
        response_metadata={"status": "completed", "finish_reason": "tool_calls"},
        tool_calls=[{
            "name": "read_evidence", "id": "unknown-evidence-call",
            "args": {"evidence_key": other_run_key},
        }],
    )
    _, final = setup()
    result, _, _ = run_context(session, model=FixedModel(replies=[call, final]))
    feedback = next(message for message in result["messages"]
                    if isinstance(message, ToolMessage))
    assert feedback.status == "error" and "unknown_evidence_key" in feedback.content
