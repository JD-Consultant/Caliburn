"""Offline native graph observation probe; no application/provider entry point.

Run with the isolated App's frozen environment. SQLite is in-memory and this
script initializes only that disposable fixture. Output contains synthetic IDs,
node names, booleans and receipt digests, never source or patch text.
"""
from dataclasses import asdict
from importlib.metadata import version
import json
from time import perf_counter
from typing import Any
from uuid import uuid4

from langchain.agents import create_agent
from langchain.tools import ToolRuntime, tool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command, StateSnapshot, interrupt
from langsmith import tracing_context
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from caliburn_memory.memory import MemoryArtifacts, MemoryVersion
from caliburn_memory.publication import PublicationStore, PublicationUncertain, PublishRequest
from caliburn_memory.repair import RepairState, RepairWorkflow
from caliburn_memory.sources import InvalidSourceReference


class FixedModel(BaseChatModel):
    replies: list[Any]
    calls: int = 0

    @property
    def _llm_type(self):
        return "offline-fixed-observation-probe"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, **kwargs):
        self.calls += 1
        if not self.replies:
            raise AssertionError("inspection_or_unexpected_model_execution")
        return ChatResult(generations=[ChatGeneration(message=self.replies.pop(0))])


class Source:
    def __init__(self, document_id):
        self.document_id = document_id
        self.reference = f"conversation:{document_id}:original"
        self.reads = 0

    def validate_reference(self, reference):
        if reference != self.reference:
            raise InvalidSourceReference("invalid_source_reference")

    def read(self, reference):
        self.validate_reference(reference)
        self.reads += 1
        return "合成原話：例外由主管核准。"


class Fixture:
    def __init__(self, mode):
        self.document_id = str(uuid4())
        self.source = Source(self.document_id)
        self.artifacts = MemoryArtifacts(InMemoryStore(), self.document_id, source=self.source)
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool)
        self.pub = PublicationStore(self.engine, self.artifacts)
        self.pub.setup()
        memory = self.artifacts.save_memory(knowledge="例外由主管核准。", guide="主管核准：/memory/knowledge.md")
        self.head = self.pub.publish(self.pub.prepare(memory, expected_revision=0,
            kind="consolidation", processed_source=self.source.reference))
        self.operation_id = str(uuid4())
        self.payload = {"operation_id": self.operation_id, "base": asdict(self.head),
            "source_reference": self.source.reference,
            "edits": [{"path": "/memory/knowledge.md", "diff": "@@\n-例外由主管核准。\n+例外由處長核准。"}]}
        self.mode = mode
        self.created = 0
        self.tool_calls = 0
        self.steps = {name: 0 for name in ("seed", "edit", "validate", "save", "prepare", "publish")}
        self.publish_calls = 0
        original_publish = self.pub.publish
        def publish(request):
            self.publish_calls += 1
            result = original_publish(request)
            if mode == "ack_lost":
                raise PublicationUncertain("synthetic_commit_ack_lost")
            return result
        self.pub.publish = publish

    def workflow(self):
        self.created += 1
        mode = self.mode
        steps = self.steps
        class PreparedRepair(RepairWorkflow):
            def _seed(self, state):
                steps["seed"] += 1
                return super()._seed(state)

            def _edit(self, state):
                steps["edit"] += 1
                return super()._edit(state)

            def _validate(self, state):
                steps["validate"] += 1
                return super()._validate(state)

            def _save(self, state):
                steps["save"] += 1
                return super()._save(state)

            def _prepare(self, state):
                steps["prepare"] += 1
                return super()._prepare(state)

            def _publish(self, state):
                steps["publish"] += 1
                if mode == "interrupt":
                    interrupt("synthetic_after_prepare")
                return super()._publish(state)
        return PreparedRepair(self.artifacts, self.pub, self.source)


def call_message():
    return AIMessage(id="synthetic-ai-call", content="", tool_calls=[{
        "name": "repair_memory", "args": {}, "id": "synthetic-call", "type": "tool_call"}])


def root_graph(child, saver):
    builder = StateGraph(MessagesState)
    builder.add_node("consultant", child)
    builder.add_edge(START, "consultant")
    builder.add_edge("consultant", END)
    return builder.compile(checkpointer=saver)


def build_tool_root(fixture, saver, *, dynamic, inspection=False):
    # Both versions intentionally use the real create_agent ToolNode. Having a
    # compiled graph in the StructuredTool closure is not assumed discoverable.
    fixed = None if dynamic else fixture.workflow().graph
    @tool
    def repair_memory() -> str:
        """Perform the fixed synthetic repair."""
        graph = fixture.workflow().graph if dynamic else fixed
        result = graph.invoke(fixture.payload, durability="sync")
        return json.dumps({"status": result["outcome"]["status"]})
    model = FixedModel(replies=[] if inspection else [call_message(), AIMessage(content="synthetic_done")])
    child = create_agent(model, tools=[repair_memory])
    return root_graph(child, saver), model


def request_from(values):
    data = dict(values["request"])
    data["memory"] = MemoryVersion(**data["memory"])
    data["repair_sources"] = tuple(data["repair_sources"])
    return PublishRequest(**data)


def inspect_snapshot(graph, config):
    snapshot = graph.get_state(config, subgraphs=True)
    def walk(value):
        return {"next": list(value.next), "request_present": "request" in value.values,
            "tasks": [{"name": task.name, "state_type": type(task.state).__name__,
                "child": walk(task.state) if isinstance(task.state, StateSnapshot) else None}
                for task in value.tasks]}
    return snapshot, walk(snapshot)


def probe_tool(mode, dynamic):
    fixture = Fixture(mode)
    saver = InMemorySaver()
    graph, model = build_tool_root(fixture, saver, dynamic=dynamic)
    config = {"configurable": {"thread_id": fixture.document_id}}
    try:
        graph.invoke({"messages": [HumanMessage(id="synthetic-human", content="synthetic_input")]},
            config, durability="sync")
        raised = None
    except PublicationUncertain:
        raised = "PublicationUncertain"
    before = (fixture.created, fixture.source.reads, fixture.publish_calls)
    inspection, inspection_model = build_tool_root(fixture, saver, dynamic=dynamic, inspection=True)
    after_build = (fixture.created, fixture.source.reads, fixture.publish_calls)
    snapshot, visible = inspect_snapshot(inspection, config)
    fixed = inspection.get_state(snapshot.config, subgraphs=True)
    assert fixed.config == snapshot.config
    assert inspection_model.calls == 0
    assert (fixture.created, fixture.source.reads, fixture.publish_calls) == after_build
    # Inspection may build a static graph but must not execute any graph work.
    assert before[1:] == after_build[1:]
    subgraphs = [name for name, _ in inspection.get_subgraphs(recurse=True)]
    assert subgraphs == ["consultant"]
    if mode != "normal":
        child = snapshot.tasks[0].state
        assert isinstance(child, StateSnapshot)
        assert len(child.tasks) == 1 and child.tasks[0].name == "tools"
        assert child.tasks[0].state is None
    receipt = fixture.pub.receipt(fixture.operation_id)
    assert (receipt is not None) == (mode != "interrupt")
    result = {"shape": "dynamic_tool" if dynamic else "closure_tool", "mode": mode,
        "raised": raised, "subgraphs": subgraphs, "snapshot": visible,
        "model_calls": model.calls, "inspection_calls": inspection_model.calls,
        "publish_calls": fixture.publish_calls, "receipt_present": receipt is not None}
    fixture.engine.dispose()
    return result


class HandoffState(RepairState, MessagesState):
    pass


class WrapperState(MessagesState):
    jd_memory_repair_bindings: list[dict]


def build_handoff_root(fixture, saver, *, inspection=False, wrapped=False):
    # Public Command.PARENT makes the native tool yield to a statically mounted
    # graph. The existing create_agent still owns model/tool orchestration.
    @tool
    def repair_memory(runtime: ToolRuntime) -> Command:
        """Perform the fixed synthetic repair."""
        fixture.tool_calls += 1
        if wrapped:
            return Command(graph=Command.PARENT, goto="memory_repair", update={
                "jd_memory_repair_bindings": [{**fixture.payload,
                    "tool_call_id": runtime.tool_call_id}], "messages": runtime.state["messages"]})
        return Command(graph=Command.PARENT, goto="memory_repair", update={
            **fixture.payload, "messages": runtime.state["messages"]})
    model = FixedModel(replies=[] if inspection else [call_message(), AIMessage(content="synthetic_done")])
    child = create_agent(model, tools=[repair_memory])
    workflow = fixture.workflow()
    repair_graph = workflow.graph
    def wrapped_repair(state):
        # The actual compiled subgraph is captured directly by a fixed node.
        # Private C files/material/request channels do not enter the root.
        binding = state["jd_memory_repair_bindings"][-1]
        result = repair_graph.invoke({key: binding[key] for key in (
            "operation_id", "base", "source_reference", "edits")}, durability="sync")
        return {"messages": [ToolMessage(id="synthetic-tool-result", tool_call_id=binding["tool_call_id"],
            name="repair_memory", content=json.dumps({"status": result["outcome"]["status"]}),
            artifact={"request": result["request"]})]}
    def repair_result(state):
        return {"messages": [ToolMessage(id="synthetic-tool-result", tool_call_id="synthetic-call",
            name="repair_memory", content=json.dumps({"status": state["outcome"]["status"]}),
            artifact={"request": state["request"]})]}
    builder = StateGraph(WrapperState if wrapped else HandoffState)
    builder.add_node("consultant", child)
    builder.add_node("memory_repair", wrapped_repair if wrapped else repair_graph)
    builder.add_edge(START, "consultant")
    builder.add_edge("consultant", END)
    if wrapped:
        builder.add_edge("memory_repair", "consultant")
    else:
        builder.add_node("repair_result", repair_result)
        builder.add_edge("memory_repair", "repair_result")
        builder.add_edge("repair_result", "consultant")
    return builder.compile(checkpointer=saver), model, workflow


def probe_handoff(mode, *, wrapped=False):
    fixture = Fixture(mode)
    saver = InMemorySaver()
    graph, model, workflow = build_handoff_root(fixture, saver, wrapped=wrapped)
    config = {"configurable": {"thread_id": fixture.document_id}}
    try:
        graph.invoke({"messages": [HumanMessage(id="synthetic-human", content="synthetic_input")]},
            config, durability="sync")
        raised = None
    except PublicationUncertain:
        raised = "PublicationUncertain"
    inspection, inspection_model, _ = build_handoff_root(fixture, saver, inspection=True, wrapped=wrapped)
    before = (fixture.created, fixture.source.reads, fixture.publish_calls)
    snapshot, visible = inspect_snapshot(inspection, config)
    subgraphs = [name for name, _ in inspection.get_subgraphs(recurse=True)]
    assert subgraphs == ["consultant", "memory_repair"]
    if mode == "normal":
        messages = snapshot.values["messages"]
        tool_results = [message for message in messages if isinstance(message, ToolMessage)]
        assert len(tool_results) == 1 and tool_results[0].tool_call_id == "synthetic-call"
        request = request_from(tool_results[0].artifact)
        assert not snapshot.next and model.calls == 2
        request_path = "root.messages[ToolMessage].artifact.request"
    else:
        assert len(snapshot.tasks) == 1 and snapshot.tasks[0].name == "memory_repair"
        child = snapshot.tasks[0].state
        assert isinstance(child, StateSnapshot)
        fixed = inspection.get_state(child.config)
        for key in ("thread_id", "checkpoint_ns", "checkpoint_id"):
            assert fixed.config["configurable"][key] == child.config["configurable"][key]
        assert fixed.next == ("publish",)
        request = request_from(fixed.values)
        request_path = "root.tasks[memory_repair].state.config -> root.get_state(fixed).values.request"
        assert model.calls == 1
    assert request.operation_id == fixture.operation_id
    assert request.memory.document_id == fixture.document_id
    receipt = fixture.pub.receipt(fixture.operation_id)
    if receipt is not None:
        assert receipt.request_digest == request.digest()
        reconciled = workflow.reconcile(request)
        assert reconciled["status"] == "applied"
        assert reconciled["applied_head"]["revision"] == 2
    else:
        assert mode == "interrupt"
    assert inspection_model.calls == 0
    assert (fixture.created, fixture.source.reads, fixture.publish_calls) == before
    assert fixture.tool_calls == 1
    if wrapped:
        assert set(snapshot.values) <= {"messages", "jd_memory_repair_bindings"}
    assert all(fixture.steps[name] == 1 for name in ("seed", "edit", "validate", "save", "prepare"))
    observation_steps = dict(fixture.steps)
    if mode == "interrupt":
        graph.invoke(Command(resume=True), config, durability="sync")
        resumed = graph.get_state(config)
        assert resumed.next == () and model.calls == 2 and fixture.tool_calls == 1
        assert fixture.publish_calls == 1 and fixture.steps["publish"] == 2
        assert all(fixture.steps[name] == 1 for name in ("seed", "edit", "validate", "save", "prepare"))
        assert fixture.pub.receipt(fixture.operation_id).request_digest == request.digest()
        # An original fixed root remains inspectable after the latest root closes.
        historical = inspection.get_state(snapshot.config, subgraphs=True)
        prior_child = historical.tasks[0].state
        assert request_from(inspection.get_state(prior_child.config).values) == request
        settlement = "native_resume_publish_only"
    elif mode == "ack_lost":
        # Synthetic equivalent of a stopped owner applying the confirmed result
        # to the native root. This is NOT stopped-worker proof or an App adapter.
        prior = (model.calls, fixture.tool_calls, fixture.source.reads, dict(fixture.steps))
        graph.update_state(snapshot.config, {"messages": [ToolMessage(id="synthetic-tool-result",
            tool_call_id="synthetic-call", name="repair_memory", content="synthetic_applied",
            artifact={"request": asdict(request)})]}, as_node="consultant")
        closed = graph.get_state(config, subgraphs=True)
        assert closed.next == () and closed.tasks == ()
        assert (model.calls, fixture.tool_calls, fixture.source.reads, fixture.steps) == prior
        historical = inspection.get_state(snapshot.config, subgraphs=True)
        prior_child = historical.tasks[0].state
        assert request_from(inspection.get_state(prior_child.config).values) == request
        assert fixture.publish_calls == 1
        settlement = "native_root_close_no_invoke"
    else:
        settlement = "normal_completed"
    final = graph.get_state(config)
    if wrapped:
        assert set(final.values) == {"messages", "jd_memory_repair_bindings"}
        assert set(graph.nodes) == {"__start__", "consultant", "memory_repair"}
    humans = [m for m in final.values["messages"] if isinstance(m, HumanMessage)]
    assert len(humans) == 1 and humans[0].id == "synthetic-human" and humans[0].content == "synthetic_input"
    calls = [m for m in final.values["messages"] if isinstance(m, AIMessage) and m.tool_calls]
    answers = [m for m in final.values["messages"] if isinstance(m, ToolMessage)]
    assert len(calls) == len(answers) == 1
    assert calls[0].tool_calls[0]["id"] == answers[0].tool_call_id == "synthetic-call"
    result = {"shape": "static_wrapper" if wrapped else "static_handoff", "mode": mode, "raised": raised,
        "subgraphs": subgraphs, "snapshot": visible, "request_path": request_path,
        "request_scope_match": True, "request_digest": request.digest(),
        "model_calls": model.calls, "inspection_calls": inspection_model.calls,
        "publish_calls": fixture.publish_calls, "receipt_present_at_observation": receipt is not None,
        "tool_calls": fixture.tool_calls, "steps_at_observation": observation_steps,
        "steps_after_settlement": fixture.steps, "settlement": settlement,
        "root_value_keys": sorted(final.values)}
    fixture.engine.dispose()
    return result


def main():
    started = perf_counter()
    with tracing_context(enabled=False):
        results = [probe_tool(mode, dynamic) for dynamic in (True, False)
            for mode in ("normal", "interrupt", "ack_lost")]
        results.extend(probe_handoff(mode) for mode in ("normal", "interrupt", "ack_lost"))
        results.extend(probe_handoff(mode, wrapped=True) for mode in ("normal", "interrupt", "ack_lost"))
    print(json.dumps({"versions": {p: version(p) for p in ("langchain", "langgraph", "deepagents")},
        "passed_cases": len(results), "elapsed_seconds": round(perf_counter() - started, 3),
        "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
