"""Read-only discovery/layout probes after synthetic native graph setup.

No provider, DB, host bootstrap, or storage format implementation. Discovery
only reads; separate negative guard cases deliberately attempt native resumes.
LangChain1.4.0/LangGraph1.2.11/checkpoint4.2.0, 2026-09-13.
"""
from hashlib import sha256
import asyncio
from importlib.metadata import version
import json
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "experiments/jd-relational-app/src"))
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from jd_relational.ai_checkpoints import AiCheckpointError, AiRunCheckpoints, AiRunRecord, new_run_record
from jd_relational.consultant_context import ConsultantState, ConsultantContext, JdNoticeMiddleware
from jd_relational.consultant_tools import AiToolMiddleware as AppToolMiddleware, build_jd_tools
from jd_relational.runtime_checkpoints import DocumentState, build_document_graph


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class SyntheticModel(BaseChatModel):
    calls: int = 0
    @property
    def _llm_type(self): return "synthetic-offline-layout-probe"
    def bind_tools(self, tools, **kwargs): return self
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=AIMessage(
            id=f"synthetic-ai-{self.calls}", content="synthetic complete reply",
            tool_calls=[{"id": f"synthetic-call-{self.calls}", "name": "synthetic_write", "args": {}, "type": "tool_call"}]))])


class InspectionOnly(BaseChatModel):
    @property
    def _llm_type(self): return "inspection-only-execution-disabled"
    def bind_tools(self, tools, **kwargs): return self
    def _generate(self, *args, **kwargs): raise ValueError("execution_disabled")


class ExecutionDisabled(AgentMiddleware):
    def wrap_model_call(self, request, handler): raise ValueError("execution_disabled")
    async def awrap_model_call(self, request, handler): raise ValueError("execution_disabled")
    def wrap_tool_call(self, request, handler): raise ValueError("execution_disabled")
    async def awrap_tool_call(self, request, handler): raise ValueError("execution_disabled")


def factory_inspection_child():
    # Configuration tested before adding the shared factory inspection branch.
    # Keep this original preflight fixture; actual factory is covered by tests.
    return create_agent(InspectionOnly(cache=False, output_version=None), tools=build_jd_tools(),
        system_prompt="synthetic inspection-only guidance",
        middleware=[ExecutionDisabled(), JdNoticeMiddleware(), AppToolMiddleware()],
        state_schema=ConsultantState, context_schema=ConsultantContext)


class AiToolMiddleware(AgentMiddleware):
    """Synthetic body; same named native after_model slot as the installed App."""
    state_schema = ConsultantState
    def after_model(self, state, runtime):
        record, reply = state["jd_ai_run"], state["messages"][-1]
        notice = '{"current_revision_number":1,"type":"jd_change_notice"}'
        view = {"format_version": 1, "dataset_id": record["dataset_id"],
            "document_id": record["document_id"], "run_id": record["run_id"],
            "revision_id": str(uuid4()), "revision_number": 1,
            "response_message_id": reply.id,
            "response_digest": sha256(canonical(reply.model_dump(mode="json")).encode()).hexdigest(),
            "notice_json": notice, "notice_digest": sha256(notice.encode()).hexdigest()}
        return {"jd_ai_bindings": [{"synthetic_original_binding": record["run_id"]}],
                "jd_ai_read": {"synthetic_original_read": record["run_id"]}, "jd_model_view": view}


@tool
def synthetic_write() -> str:
    """Never execute; the native tool node is interrupted for this probe."""
    raise AssertionError("Probe must never run a tool")


def unavailable(state):
    raise AssertionError("Read-only graph must never execute")


def baseline_messages_only_child():
    # The exact simple layout used at baseline 3980689a. Production now uses
    # build_inspection_consultant_node; preserve the original negative fixture.
    graph = StateGraph(MessagesState)
    graph.add_node("consultant", unavailable)
    graph.add_edge(START, "consultant"); graph.add_edge("consultant", END)
    return graph.compile()


def readonly_child(*, matching=False):
    graph = StateGraph(ConsultantState if matching else DocumentState)
    if matching:
        for name in ("model", "tools", "AiToolMiddleware.after_model"):
            graph.add_node(name, unavailable)
        graph.add_edge(START, "model")
        graph.add_edge("model", "AiToolMiddleware.after_model")
        graph.add_edge("AiToolMiddleware.after_model", END)
        graph.add_edge("tools", "model")
    else:
        graph.add_node("unavailable", unavailable)
        graph.add_edge(START, "unavailable"); graph.add_edge("unavailable", END)
    return graph.compile()


def make_pending(*, pending="tools"):
    saver, model = InMemorySaver(), SyntheticModel()
    child = create_agent(model, tools=[synthetic_write], middleware=[AiToolMiddleware()],
        state_schema=ConsultantState, interrupt_before=[pending])
    root = build_document_graph(child, saver)
    dataset, document, run = (str(uuid4()) for _ in range(3))
    record, human = new_run_record(dataset, document, run, "synthetic original human")
    config = {"configurable": {"thread_id": document}}
    root.invoke({"jd_ai_run": record.model_dump(), "messages": [human],
        "jd_ai_bindings": [], "jd_ai_read": None}, config, durability="sync")
    return root, child, saver, model, record


def fixed_root(graph, document):
    latest = graph.get_state({"configurable": {"thread_id": document}}, subgraphs=True)
    return graph.get_state(latest.config, subgraphs=True)


def discover(graph, document, dataset):
    """Prototype only: select run from fixed data, then reuse existing validator."""
    root = fixed_root(graph, document)
    if root.next == (START,):
        original = graph.checkpointer.get_tuple(root.config)
        value = original.checkpoint["channel_values"][START]["jd_ai_run"]
    else:
        value = root.values.get("jd_ai_run")
    if value is None:
        if root.next or root.tasks or root.interrupts:
            raise ValueError("unrecognized_pending_work")
        return None
    record = AiRunRecord.model_validate(value, strict=True)
    if record.document_id != document or record.dataset_id != dataset:
        raise ValueError("invalid_scope")
    result = AiRunCheckpoints(graph).observe(document, record.run_id, dataset)
    if result.root_config["configurable"]["checkpoint_id"] != root.config["configurable"]["checkpoint_id"]:
        raise ValueError("checkpoint_changed")
    return result


def layout_probe(pending):
    original, child, saver, model, record = make_pending(pending=pending)
    reference = fixed_root(original, record.document_id)
    child_ref = reference.tasks[0].state
    reference_child = original.get_state(child_ref.config, subgraphs=True)
    outputs = []
    for name, replacement in (("messages_only", baseline_messages_only_child()),
        ("same_fields_other_node", readonly_child()), ("same_fields_named_nodes", readonly_child(matching=True)),
        ("same_native_factory_configuration", factory_inspection_child())):
        graph = build_document_graph(replacement, saver)
        root = fixed_root(graph, record.document_id)
        projected = graph.get_state(root.tasks[0].state.config, subgraphs=True)
        try:
            found = discover(graph, record.document_id, record.dataset_id)
            outcome = "observed"
        except (AiCheckpointError, ValueError) as error:
            found, outcome = None, getattr(error, "code", type(error).__name__)
        outputs.append({"reader": name, "child_keys": sorted(projected.values),
            "same_channel_names": set(replacement.channels) == set(child.channels),
            "child_next": list(projected.next), "child_tasks": [t.name for t in projected.tasks],
            "reference_next": list(reference_child.next),
            "same_full_messages": projected.values.get("messages") == reference_child.values.get("messages"),
            "same_bindings": projected.values.get("jd_ai_bindings") == reference_child.values.get("jd_ai_bindings"),
            "same_view": projected.values.get("jd_model_view") == reference_child.values.get("jd_model_view"),
            "observation": outcome, "root_closed": found.closed if found else None})
    assert model.calls == 1
    assert outputs[0]["observation"] == "invalid_checkpoint"
    assert not outputs[0]["same_bindings"]
    assert outputs[1]["same_bindings"] and not outputs[1]["child_next"]
    assert outputs[2]["child_next"] == list(reference_child.next)
    assert outputs[2]["same_full_messages"] and outputs[2]["same_view"]
    assert outputs[3]["child_next"] == list(reference_child.next)
    assert outputs[3]["same_full_messages"] and outputs[3]["same_view"] and outputs[3]["same_bindings"]
    assert outputs[3]["same_channel_names"]
    return {"case": f"layout_before_{pending}", "original_agent_nodes": sorted(child.nodes),
        "synthetic_setup_model_calls": model.calls, "inspection_model_calls": 0, "readers": outputs}


def discovery_and_history_probe():
    dataset, document = str(uuid4()), str(uuid4())
    graph = build_document_graph(factory_inspection_child(), InMemorySaver())
    config = {"configurable": {"thread_id": document, "checkpoint_ns": ""}}
    assert discover(graph, document, dataset) is None
    old, first = new_run_record(dataset, document, str(uuid4()), "synthetic first human")
    graph.update_state(config, {"jd_ai_run": old.model_copy(update={"status": "completed"}).model_dump(),
        "messages": [first, AIMessage(id=str(uuid4()), content="synthetic first reply")],
        "jd_ai_bindings": [], "jd_ai_read": None}, as_node="consultant")
    terminal = discover(graph, document, dataset)
    assert terminal.record.status == "completed" and terminal.closed
    new, human = new_run_record(dataset, document, str(uuid4()), "synthetic new human")
    original = {"jd_ai_run": new.model_dump(), "messages": [human], "jd_ai_bindings": [], "jd_ai_read": None}
    original_put = graph.checkpointer.put
    def fail_loop(config, checkpoint, metadata, versions):
        if metadata["source"] == "loop": raise OSError("synthetic_loop_failure")
        return original_put(config, checkpoint, metadata, versions)
    graph.checkpointer.put = fail_loop
    try:
        graph.invoke(original, config, durability="sync")
    except OSError:
        pass
    finally:
        graph.checkpointer.put = original_put
    start_root = fixed_root(graph, document)
    assert start_root.values["jd_ai_run"]["run_id"] == old.run_id
    initial = discover(graph, document, dataset)
    assert initial.record.run_id == new.run_id and not initial.closed
    assert initial.messages[-1] == human
    graph.update_state(initial.root_config, {**original, "messages": initial.messages}, as_node="consultant")
    idle = discover(graph, document, dataset)
    assert idle.record.status == "running" and idle.closed
    graph.update_state(idle.root_config,
        {"jd_ai_run": new.model_copy(update={"status": "failed"}).model_dump()}, as_node="consultant")
    current = discover(graph, document, dataset)
    root_id = current.root_config
    history_wrong = list(graph.get_state_history(root_id, limit=32))
    assert len(history_wrong) == 1  # checkpoint_id filters to that exact record.
    history = list(graph.get_state_history(config, before=root_id, limit=32))
    matches = [s for s in history if not (s.next or s.tasks or s.interrupts)
        and (s.values.get("jd_ai_run") or {}).get("run_id") == old.run_id
        and s.values["jd_ai_run"]["status"] == "completed"]
    assert len(matches) == 1
    original_record = AiRunRecord.model_validate(matches[0].values["jd_ai_run"])
    assert original_record == terminal.record
    original_human = next(m for m in matches[0].values["messages"] if m.id == old.run_id)
    assert original_human == first
    changed, _ = new_run_record(dataset, document, old.run_id, "synthetic changed original input")
    assert changed.request_digest != original_record.request_digest
    try:
        discover(graph, document, str(uuid4()))
    except ValueError:
        pass
    else:
        raise AssertionError("Corrupt/wrong scope must fail closed")
    return {"case": "discover_and_old_request_history", "empty": True, "terminal": True,
        "start_chooses_original_new_input_not_old_values": True,
        "graph_idle_is_not_run_terminal": True,
        "checkpoint_id_history_filter_count": len(history_wrong), "bounded_history_rows": len(history),
        "original_terminal_and_human_found": True, "changed_input_conflicts": True,
        "wrong_dataset_rejected": True, "provider_calls": 0, "inspection_model_calls": 0}


def disabled_entry_probe():
    # A real native tool node can execute before the next model. This negative
    # demonstrates why _generate alone cannot make a graph inspection-only.
    attempts = []
    @tool
    def synthetic_write() -> str:
        """Synthetic boundary only; never opens SQL or an external service."""
        attempts.append("tool_boundary")
        raise ValueError("synthetic_tool_boundary_reached")
    original, _, saver, model, record = make_pending()
    config = {"configurable": {"thread_id": record.document_id}}
    model_only = create_agent(InspectionOnly(cache=False, output_version=None), tools=[synthetic_write],
        middleware=[AiToolMiddleware()], state_schema=ConsultantState)
    negative = build_document_graph(model_only, saver)
    try:
        negative.invoke(None, config, durability="sync")
    except ValueError:
        pass
    assert attempts == ["tool_boundary"]
    # Separate Saver fixture avoids reusing the deliberately attempted negative.
    _, _, saver, _, record = make_pending()
    guarded = build_document_graph(factory_inspection_child(), saver)
    current = fixed_root(guarded, record.document_id)
    try:
        guarded.invoke(None, current.config, durability="sync")
    except ValueError as error:
        assert str(error) == "execution_disabled"
    else:
        raise AssertionError("Pending tool entry must be disabled")
    fresh_record, human = new_run_record(record.dataset_id, str(uuid4()), str(uuid4()), "synthetic guard check")
    try:
        guarded.invoke({"messages": [human], "jd_ai_run": fresh_record.model_dump(),
            "jd_ai_bindings": [], "jd_ai_read": None},
            {"configurable": {"thread_id": fresh_record.document_id}}, durability="sync")
    except ValueError as error:
        assert str(error) == "execution_disabled"
    else:
        raise AssertionError("New model entry must be disabled")
    return {"case": "inspection_execution_guard", "model_guard_only_enters_synthetic_tool": True,
        "guarded_pending_tool_rejected": True, "guarded_fresh_model_rejected": True,
        "provider_calls": 0, "database_calls": 0,
        "limit": "A rejected invoke may still write native input/error checkpoints; use only read methods in recovery discovery."}


async def async_disabled_entry_probe():
    guard = ExecutionDisabled()
    handlers = []
    async def handler(request):
        handlers.append(request)
        raise AssertionError("No handler may execute")
    for method in (guard.awrap_model_call, guard.awrap_tool_call):
        try:
            await method(None, handler)
        except ValueError as error:
            assert str(error) == "execution_disabled"
        else:
            raise AssertionError("Missing async guard")
    assert not handlers
    _, _, saver, _, record = make_pending()
    guarded = build_document_graph(factory_inspection_child(), saver)
    try:
        await guarded.ainvoke(None, fixed_root(guarded, record.document_id).config, durability="sync")
    except ValueError as error:
        assert str(error) == "execution_disabled"
    else:
        raise AssertionError("Async pending tool must be blocked")
    fresh, human = new_run_record(record.dataset_id, str(uuid4()), str(uuid4()), "synthetic async guard")
    try:
        await guarded.ainvoke({"messages": [human], "jd_ai_run": fresh.model_dump(),
            "jd_ai_bindings": [], "jd_ai_read": None},
            {"configurable": {"thread_id": fresh.document_id}}, durability="sync")
    except ValueError as error:
        assert str(error) == "execution_disabled"
    else:
        raise AssertionError("Async fresh model must be blocked")
    return {"case": "async_execution_guard", "handler_calls": 0,
        "async_pending_tool_rejected": True, "async_fresh_model_rejected": True}


if __name__ == "__main__":
    print(canonical({"versions": {p: version(p) for p in ("langchain", "langgraph", "langgraph-checkpoint")},
        "provider_calls": 0, "database_calls": 0, "discovery_resumes": 0,
        "guard_negative_tests_attempt_native_invocation": True}))
    for pending in ("tools", "AiToolMiddleware.after_model"):
        print(canonical(layout_probe(pending)))
    print(canonical(discovery_and_history_probe()))
    print(canonical(disabled_entry_probe()))
    print(canonical(asyncio.run(async_disabled_entry_probe())))
    print("5 probe groups passed; native InMemory fixtures only.")
