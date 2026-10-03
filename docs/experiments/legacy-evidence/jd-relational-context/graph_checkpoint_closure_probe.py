"""Native graph closure probe: synthetic model, InMemorySaver, zero providers/DB.

Run with experiments/jd-relational-app's frozen Python environment.
Checked 2026-09-13 against LangGraph 1.2.11/checkpoint 4.2.0.
Official contracts: https://docs.langchain.com/oss/python/langgraph/checkpointers
and https://docs.langchain.com/oss/python/langgraph/use-subgraphs .

The single-instance put wrapper injects a test fault; it is not a replacement
saver. No graph resume/replay, application writes, SDK or model calls occur.
"""

from importlib.metadata import version
import json

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph


class SharedState(MessagesState):
    last_model_view: dict | None


def probe(root_state, failure=None):
    saver = InMemorySaver()
    calls, injections = [], []
    child = StateGraph(SharedState)

    def synthetic_model(state):
        calls.append(1)
        return {"messages": [AIMessage(content="synthetic response", id="ai-one")],
            "last_model_view": {"message_id": "ai-one", "head": "synthetic-H"}}

    child.add_node("model", synthetic_model)
    child.add_edge(START, "model")
    child.add_edge("model", END)
    root = StateGraph(root_state)
    root.add_node("consultant", child.compile())
    root.add_edge(START, "consultant")
    root.add_edge("consultant", END)
    graph = root.compile(checkpointer=saver)
    original_put = saver.put

    def put(config, checkpoint, metadata, new_versions):
        inject = (failure is not None and not injections
            and config["configurable"].get("checkpoint_ns", "") == ""
            and checkpoint["channel_values"].get("last_model_view"))
        if inject:
            injections.append(1)
            if failure == "before_root_put":
                raise RuntimeError("synthetic_checkpoint_failure")
        result = original_put(config, checkpoint, metadata, new_versions)
        if inject:
            raise RuntimeError("synthetic_ack_lost")
        return result

    saver.put = put
    config = {"configurable": {"thread_id": f"synthetic-{root_state.__name__}-{failure}"}}
    raised = False
    try:
        graph.invoke({"messages": [HumanMessage(content="original", id="human-one")]},
            config, durability="sync")
    except RuntimeError:
        raised = True
    assert len(calls) == 1
    latest = graph.get_state(config, subgraphs=True)
    # Latest reads apply pending task writes. The returned exact checkpoint ID
    # disables that overlay and is essential to checking full-root completion.
    pinned = graph.get_state(latest.config, subgraphs=True)
    children = [{"next": list(task.state.next),
        "has_notice": bool(task.state.values.get("last_model_view")),
        "message_ids": [message.id for message in task.state.values.get("messages", [])]}
        for task in latest.tasks if hasattr(task.state, "values")]
    result = {"root_schema": root_state.__name__, "failure": failure, "raised": raised,
        "synthetic_model_node_calls": len(calls),
        "latest_notice": bool(latest.values.get("last_model_view")),
        "pinned_notice": bool(pinned.values.get("last_model_view")),
        "latest_next": list(latest.next), "latest_task_count": len(latest.tasks),
        "pinned_task_count": len(pinned.tasks), "children": children}
    if root_state is MessagesState:
        assert not raised and not result["latest_notice"] and not result["pinned_notice"]
    elif failure == "before_root_put":
        assert raised and result["latest_notice"] and not result["pinned_notice"]
        assert result["latest_next"] == [] and result["latest_task_count"] == 1
        assert len(children) == 1 and children[0]["has_notice"] and children[0]["next"] == []
    else:
        assert result["latest_notice"] and result["pinned_notice"]
        assert result["latest_task_count"] == result["pinned_task_count"] == 0
        assert raised == (failure == "after_root_put")
        assert [message.id for message in pinned.values["messages"]] == ["human-one", "ai-one"]
    return result


if __name__ == "__main__":
    versions = {name: version(name) for name in ("langgraph", "langgraph-checkpoint", "langchain-core")}
    print(json.dumps({"versions": versions, "provider_calls": 0, "database_calls": 0,
        "graph_resume_calls": 0, "cases": 4}, sort_keys=True))
    for state, failure in ((MessagesState, None), (SharedState, None),
        (SharedState, "before_root_put"), (SharedState, "after_root_put")):
        print(json.dumps(probe(state, failure), sort_keys=True))
    print("PASS: 4 native InMemorySaver closure cases; no provider or database calls")
