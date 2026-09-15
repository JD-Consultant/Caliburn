"""Same native Agent layout, no provider, no SQL; execution guards are real."""

import asyncio
from hashlib import sha256
import json
from uuid import uuid4

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from jd_relational.ai_checkpoints import AiRunCheckpoints, new_run_record
from jd_relational.consultant_context import (
    ConsultantContextError, ConsultantState, build_consultant_node,
)
from jd_relational.consultant_model import create_consultant_model
from jd_relational.consultant_tools import AiToolMiddleware as RealToolMiddleware, build_jd_tools
from jd_relational.inspection_model import (
    InspectionExecutionDisabled, InspectionGuard, InspectionOnly, build_inspection_consultant_node,
)
from jd_relational.runtime_checkpoints import build_document_graph
from support.openrouter_replies import reply
from test_consultant_context import FixedModel
from test_consultant_model import answering


@pytest.fixture(autouse=True)
def no_tracing(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class AiToolMiddleware(AgentMiddleware):
    """Synthetic hook body; original native node name, no App binding claims."""
    state_schema = ConsultantState

    @hook_config(can_jump_to=["end"])
    def before_model(self, state, runtime):
        return None

    def after_model(self, state, runtime):
        record, reply = state["jd_ai_run"], state["messages"][-1]
        notice = '{"current_revision_number":1,"type":"jd_change_notice"}'
        return {"jd_ai_bindings": [{"synthetic_binding": "unchanged"}],
            "jd_ai_read": {"synthetic_read": "unchanged"}, "jd_model_view": {
                "format_version": 1, "dataset_id": record["dataset_id"],
                "document_id": record["document_id"], "run_id": record["run_id"],
                "revision_id": str(uuid4()), "revision_number": 1,
                "response_message_id": reply.id,
                "response_digest": sha256(canonical(reply.model_dump(mode="json")).encode()).hexdigest(),
                "notice_json": notice, "notice_digest": sha256(notice.encode()).hexdigest()}}


def pending_fixture(pending):
    model = FixedModel(replies=[AIMessage(id="synthetic-ai", content="完整合成回覆",
        tool_calls=[{"name": "jd_read", "args": {}, "id": "original-call", "type": "tool_call"}])])
    child = create_agent(model, tools=build_jd_tools(), middleware=[AiToolMiddleware()],
        state_schema=ConsultantState, interrupt_before=[pending])
    saver = InMemorySaver()
    graph = build_document_graph(child, saver)
    record, human = new_run_record(*(str(uuid4()) for _ in range(3)), "完整原話\r\n保留", start_revision_id=str(uuid4()))
    graph.invoke({"messages": [human], "jd_ai_run": record.model_dump(),
        "jd_ai_bindings": [], "jd_ai_read": None},
        {"configurable": {"thread_id": record.document_id}}, durability="sync")
    return graph, child, saver, model, record


@pytest.mark.parametrize("pending", ["tools", "AiToolMiddleware.after_model"])
def test_same_native_factory_keeps_complete_fixed_child_channels_tasks_and_evidence(pending):
    original, child, saver, model, record = pending_fixture(pending)
    inspected_child = build_inspection_consultant_node()
    inspected = build_document_graph(inspected_child, saver)
    before = AiRunCheckpoints(original).observe(record.document_id, record.run_id, record.dataset_id)
    after = AiRunCheckpoints(inspected).discover(record.document_id, record.dataset_id)
    assert after == before and not after.closed
    left = original.get_state(before.source_config, subgraphs=True)
    right = inspected.get_state(after.source_config, subgraphs=True)
    assert left.values == right.values
    assert left.next == right.next == (pending,)
    assert [(t.id, t.name, t.path, t.error, t.interrupts) for t in left.tasks] == [
        (t.id, t.name, t.path, t.error, t.interrupts) for t in right.tasks]
    assert set(inspected_child.channels) == set(child.channels)
    assert set(inspected_child.nodes) == set(child.nodes)
    assert len(model.requests) == 1


def test_confirmed_provider_factory_assembles_the_same_recovery_state_without_invoking_provider():
    # Explicit synthetic key only constructs native configuration; no SDK call.
    with answering(reply("inspection")) as (model, _):
        actual = build_consultant_node(model, tools=build_jd_tools(), guidance="synthetic",
            extra_middleware=[RealToolMiddleware()])
    inspected = build_inspection_consultant_node()
    assert {"model", "tools"}.issubset(actual.nodes) and {"model", "tools"}.issubset(inspected.nodes)
    for channel in ("messages", "jd_ai_run", "jd_ai_bindings", "jd_model_view"):
        assert channel in actual.channels and channel in inspected.channels


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("entry", ["model", "tools", "AiToolMiddleware.after_model"])
def test_native_invocation_is_disabled_before_business_hooks(entry, asynchronous, monkeypatch):
    if entry == "model":
        graph = build_document_graph(build_inspection_consultant_node(), InMemorySaver())
        record, human = new_run_record(*(str(uuid4()) for _ in range(3)), "合成不可執行", start_revision_id=str(uuid4()))
        value = {"messages": [human], "jd_ai_run": record.model_dump(), "jd_ai_bindings": [], "jd_ai_read": None}
        config = {"configurable": {"thread_id": record.document_id}}
    else:
        _, _, saver, _, record = pending_fixture(entry)
        graph = build_document_graph(build_inspection_consultant_node(), saver)
        config = {"configurable": {"thread_id": record.document_id}}
        value = None
    calls = []
    def unexpected(*args, **kwargs):
        calls.append("business")
        raise AssertionError("No context/notice/session port may execute")
    monkeypatch.setattr("jd_relational.consultant_context._project", unexpected)
    monkeypatch.setattr("jd_relational.consultant_tools._session", unexpected)
    # LangGraph adds task notes to the exception; they are not its public code.
    with pytest.raises(InspectionExecutionDisabled) as failure:
        if asynchronous:
            asyncio.run(graph.ainvoke(value, config, durability="sync"))
        else:
            graph.invoke(value, config, durability="sync")
    assert failure.value.code == str(failure.value) == "execution_disabled"
    assert not calls


@pytest.mark.parametrize("hook", ["wrap_model_call", "wrap_tool_call", "awrap_model_call", "awrap_tool_call"])
def test_all_four_wraps_never_call_the_next_handler(hook):
    called = []
    def next_handler(request): called.append(request)
    guard = InspectionGuard()
    with pytest.raises(InspectionExecutionDisabled, match="^execution_disabled$"):
        if hook.startswith("a"):
            asyncio.run(getattr(guard, hook)(None, next_handler))
        else:
            getattr(guard, hook)(None, next_handler)
    assert not called


@pytest.mark.parametrize("asynchronous", [False, True])
def test_base_model_backstop_never_returns_a_response(asynchronous):
    model = InspectionOnly(cache=False)
    with pytest.raises(InspectionExecutionDisabled, match="^execution_disabled$"):
        if asynchronous: asyncio.run(model.ainvoke("synthetic"))
        else: model.invoke("synthetic")


@pytest.mark.parametrize("extras", [[], [AgentMiddleware()], [RealToolMiddleware(), AgentMiddleware()]])
def test_inspection_rejects_unknown_extra_hooks(extras):
    with pytest.raises(ConsultantContextError, match="^invalid_consultant_configuration$"):
        build_consultant_node(InspectionOnly(cache=False), tools=build_jd_tools(),
            guidance="synthetic", extra_middleware=extras)


def test_inspection_rejects_subclass_instead_of_admitting_arbitrary_models():
    class Different(InspectionOnly):
        pass
    with pytest.raises(ConsultantContextError, match="^invalid_consultant_configuration$"):
        build_consultant_node(Different(cache=False), tools=build_jd_tools(),
            guidance="synthetic", extra_middleware=[RealToolMiddleware()])
