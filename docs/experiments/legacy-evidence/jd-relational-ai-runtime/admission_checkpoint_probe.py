"""Native after_model -> sync checkpoint -> tools ordering, zero SQL/providers.

2026-09-13: LangChain 1.4.0, LangGraph 1.2.11, checkpoint 4.2.0.
Official: https://docs.langchain.com/oss/python/langchain/middleware/custom
https://docs.langchain.com/oss/python/langgraph/checkpointers

Run with jd-relational-app's frozen Python. The test-only put wrapper injects
faults into one native InMemorySaver instance, not a replacement saver. The
synthetic tool counts attempted SQL boundaries but never opens a database.
No graph resume, new workflow implementation, model SDK or provider is used.
"""

from dataclasses import asdict
from importlib.metadata import version
import json
from pathlib import Path
import sys
from threading import Event
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "experiments/jd-relational-app/src"))

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_config
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from jd_relational.domain import CommandContext, Ref
from jd_relational.intents import bind_edit


class ProbeState(AgentState):
    jd_binding: dict | None


class FixedModel(BaseChatModel):
    calls: int = 0

    @property
    def _llm_type(self):
        return "synthetic-no-provider"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        reply = AIMessage(id=f"synthetic-response-{self.calls}", content="synthetic",
            tool_calls=([{"id": "synthetic-call", "name": "synthetic_write", "args": {}, "type": "tool_call"}]
                        if self.calls == 1 else []))
        return ChatResult(generations=[ChatGeneration(message=reply)])


def probe(mode):
    document, run, base = (str(uuid4()) for _ in range(3))
    saver = InMemorySaver()
    model = FixedModel()
    log = []
    admitted = []
    child_namespace = []
    attempted_sql = []
    durable_at_tool = []
    tool_started = Event()
    original_put = saver.put
    injected = []
    target_field = "synthetic-field-ref"

    def bound_record(call):
        context = CommandContext(document, base,
            {target_field: Ref(document, base, "profile", field="purpose")}, {},
            lambda: (_ for _ in ()).throw(AssertionError("Binding must not allocate content IDs")))
        intent = bind_edit(uuid4(), "ai", run, {"tool": "jd_set_text", "arguments": {
            "target_field_ref": target_field, "text": "synthetic", "basis_refs": []}}, context)
        identity = json.loads(json.dumps(asdict(intent.identity), default=str))
        assert len(identity) == 7
        result = {"identity": identity, "tool_call_id": call["id"],
                  "response_message_id": "synthetic-response-1"}
        admitted.append(result)
        return result

    def native_put(config, checkpoint, metadata, new_versions):
        candidate = checkpoint["channel_values"].get("jd_binding")
        at_binding = candidate is not None and not injected
        if at_binding:
            injected.append(True)
            child_namespace.append(config["configurable"]["checkpoint_ns"])
            log.append("binding_checkpoint_enter")
            if mode == "before_put_failure":
                raise OSError("synthetic_before_binding_put")
            if mode == "async_mode_counterexample":
                # Bounded proof: async lets tools run before this put completes.
                assert tool_started.wait(3), "Expected async next step before checkpoint"
        result = original_put(config, checkpoint, metadata, new_versions)
        if at_binding:
            log.append("binding_checkpoint_saved")
            if mode == "after_put_ack_loss":
                raise OSError("synthetic_after_binding_put")
        return result

    saver.put = native_put

    @tool
    def synthetic_write() -> str:
        """Count a hypothetical SQL boundary; perform no I/O."""
        attempted_sql.append(True)
        log.append("synthetic_sql_boundary")
        tool_started.set()
        if mode == "write_result_unknown":
            raise RuntimeError("synthetic_write_outcome_unknown")
        return "synthetic confirmed result"

    class BindingMiddleware(AgentMiddleware):
        state_schema = ProbeState

        def after_model(self, state, runtime):
            calls = state["messages"][-1].tool_calls
            if not calls:
                return None
            assert len(calls) == 1
            config = get_config()["configurable"]
            assert config["thread_id"] == document
            log.append("after_model_bind")
            return {"jd_binding": bound_record(calls[0])}

        def wrap_tool_call(self, request, handler):
            binding = request.state["jd_binding"]
            assert binding == admitted[0]
            assert binding["tool_call_id"] == request.tool_call["id"]
            # Read the native persisted checkpoint, not pending-writes overlay.
            saved = saver.get_tuple({"configurable": {
                "thread_id": document, "checkpoint_ns": child_namespace[0]}})
            durable = saved.checkpoint["channel_values"].get("jd_binding") == binding
            durable_at_tool.append(durable)
            if mode != "async_mode_counterexample":
                assert durable, "Tool must not run before admission persistence"
            result = handler(request)  # Exactly once; unknown is not retried.
            assert isinstance(result, ToolMessage)
            return Command(update={"messages": [result], "jd_binding": None})

    child = create_agent(model, tools=[synthetic_write], middleware=[BindingMiddleware()],
                         state_schema=ProbeState)
    builder = StateGraph(ProbeState)
    builder.add_node("consultant", child)
    builder.add_edge(START, "consultant")
    builder.add_edge("consultant", END)
    root = builder.compile(checkpointer=saver)
    raised = None
    try:
        root.invoke({"messages": [HumanMessage(id="synthetic-human", content="synthetic")]},
            {"configurable": {"thread_id": document}},
            durability="async" if mode == "async_mode_counterexample" else "sync")
    except (OSError, RuntimeError) as error:
        raised = type(error).__name__
    child_latest = saver.get_tuple({"configurable": {
        "thread_id": document, "checkpoint_ns": child_namespace[0]}})
    pinned_child = root.get_state(child_latest.config, subgraphs=True)
    child_binding = pinned_child.values.get("jd_binding")
    root_latest = root.get_state({"configurable": {"thread_id": document}}, subgraphs=True)
    pinned_root = root.get_state(root_latest.config, subgraphs=True)
    if mode == "before_put_failure":
        assert raised == "OSError" and not attempted_sql and child_binding is None
        assert model.calls == 1
    elif mode == "after_put_ack_loss":
        assert raised == "OSError" and not attempted_sql and child_binding == admitted[0]
        assert pinned_root.values.get("jd_binding") is None and pinned_root.tasks
        assert model.calls == 1
    elif mode == "write_result_unknown":
        assert raised == "RuntimeError" and len(attempted_sql) == 1
        assert child_binding == admitted[0] and model.calls == 1
    elif mode == "async_mode_counterexample":
        assert raised is None and durable_at_tool == [False] and model.calls == 2
    else:
        assert raised is None and durable_at_tool == [True] and model.calls == 2
        assert child_binding is None and not pinned_root.tasks
        assert [m.type for m in pinned_root.values["messages"]] == ["human", "ai", "tool", "ai"]
    return {"case": mode, "log": log, "raised": raised, "fixed_model_calls": model.calls,
        "synthetic_sql_boundaries": len(attempted_sql), "binding_durable_at_tool": durable_at_tool,
        "pinned_child_retains_original_binding": child_binding == admitted[0],
        "pinned_root_pending_tasks": len(pinned_root.tasks), "resume_calls": 0,
        "provider_calls": 0, "database_calls": 0}


if __name__ == "__main__":
    print(json.dumps({"versions": {name: version(name) for name in (
        "langchain", "langgraph", "langgraph-checkpoint")}}, sort_keys=True))
    for case in ("normal_sync", "before_put_failure", "after_put_ack_loss",
                 "write_result_unknown", "async_mode_counterexample"):
        print(json.dumps(probe(case), sort_keys=True))
    print("PASS: 5 native ordering cases; zero DB/provider/resume")
