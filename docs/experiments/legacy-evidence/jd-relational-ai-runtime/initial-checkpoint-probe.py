"""Native initial-input failure shapes; zero provider/SQL and no graph replay.

LangGraph 1.2.11 / checkpoint 4.2.0, checked 2026-09-13.
https://docs.langchain.com/oss/python/langgraph/checkpointers
https://docs.langchain.com/oss/python/langgraph/use-time-travel
Only this InMemorySaver instance's put method is wrapped to inject faults.
"""
from copy import deepcopy
from importlib.metadata import version
import json
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "experiments/jd-relational-app/src"))
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from jd_relational.ai_checkpoints import AiCheckpointError, AiRunCheckpoints, new_run_record
from jd_relational.runtime_checkpoints import DocumentState


def shape(snapshot, run):
    return {"value_keys": sorted(snapshot.values), "next": list(snapshot.next),
        "tasks": [{"name": t.name, "has_subgraph": t.state is not None,
                   "has_result": t.result is not None} for t in snapshot.tasks],
        "source": (snapshot.metadata or {}).get("source"),
        "step": (snapshot.metadata or {}).get("step"),
        "new_human_in_values": any(isinstance(m, HumanMessage) and m.id == run
                                    for m in snapshot.values.get("messages", [])),
        "new_run_in_values": (snapshot.values.get("jd_ai_run") or {}).get("run_id") == run}


def probe(failure, prior, closure="ordinary"):
    dataset, document, run = (str(uuid4()) for _ in range(3))
    saver, calls, puts = InMemorySaver(), [], []
    child = StateGraph(DocumentState)
    def forbidden(state):
        calls.append("model")
        raise AssertionError("Initial-put fault must stop before model")
    child.add_node("model", forbidden)
    child.add_edge(START, "model"); child.add_edge("model", END)
    builder = StateGraph(DocumentState)
    builder.add_node("consultant", child.compile())
    builder.add_edge(START, "consultant"); builder.add_edge("consultant", END)
    root = builder.compile(checkpointer=saver)
    config = {"configurable": {"thread_id": document}}
    prior_messages = []
    if prior:
        previous, old_human = new_run_record(dataset, document, str(uuid4()), "synthetic previous human")
        prior_messages = [old_human, AIMessage(id="synthetic-old-ai", content="synthetic old reply")]
        root.update_state(config, {"jd_ai_run": previous.model_copy(update={"status": "completed"}).model_dump(),
            "messages": prior_messages, "jd_ai_bindings": [], "jd_ai_read": None,
            "jd_model_view": None}, as_node="consultant")
    before = root.get_state(config, subgraphs=True)
    record, human = new_run_record(dataset, document, run, "synthetic exact new human\r\nsecond line")
    original = {"jd_ai_run": record.model_dump(), "messages": [human], "jd_ai_bindings": [], "jd_ai_read": None}
    original_put = saver.put
    injected = []
    def put(conf, checkpoint, metadata, versions):
        nth = len(puts) + 1
        puts.append({"source": metadata["source"], "step": metadata["step"],
                     "namespace": conf["configurable"].get("checkpoint_ns", ""),
                     "channel_keys": sorted(checkpoint["channel_values"])})
        inject = (failure == "all_before" or (not injected and ((failure.startswith("first_") and nth == 1)
                  or (failure == "loop_before" and nth == 2)))
        )
        if inject:
            injected.append(1)
            if failure != "first_after":
                raise OSError("synthetic_before_put")
        result = original_put(conf, checkpoint, metadata, versions)
        if inject:
            raise OSError("synthetic_after_put_ack_lost")
        return result
    saver.put = put
    try:
        root.invoke(original, config, durability="sync")
    except OSError:
        pass
    else:
        raise AssertionError("Expected initial persistence fault")
    saver.put = original_put
    assert injected and not calls
    latest = root.get_state(config, subgraphs=True)
    pinned = root.get_state(latest.config, subgraphs=True)
    raw = saver.get_tuple(latest.config)
    try:
        AiRunCheckpoints(root).observe(document, run, dataset)
        observation = "observed"
    except AiCheckpointError as error:
        observation = error.code
    result = {"failure": failure, "prior": prior, "closure": closure, "puts": puts,
        "latest": shape(latest, run), "fixed": shape(pinned, run),
        "fixed_input_matches_original": raw is not None and raw.checkpoint["channel_values"].get(START) == original,
        "task_result_matches_original": len(pinned.tasks) == 1 and pinned.tasks[0].result == original,
        "pending_channels": [w[1] for w in (raw.pending_writes or [])] if raw else [],
        "position_unchanged": latest.config == before.config,
        "observer": observation, "model_calls": len(calls)}
    if failure == "all_before":
        assert latest.config == before.config and not calls
        result["known_no_new_checkpoint"] = True
        return result  # Do not fabricate an already-saved run.
    desired = {**deepcopy(original), "jd_ai_run": record.model_copy(update={"status": "failed"}).model_dump()}
    if closure == "ordinary":
        root.update_state(pinned.config, desired, as_node="consultant")
    elif closure == "clear_then_close":
        cleared = root.update_state(pinned.config, None, as_node=END)
        result["clear_shape"] = shape(root.get_state(cleared, subgraphs=True), run)
        root.update_state(cleared, desired, as_node="consultant")
    elif closure == "previous_fork":
        root.update_state(before.config, desired, as_node="consultant")
    after = root.get_state(config, subgraphs=True)
    fixed_after = root.get_state(after.config, subgraphs=True)
    result["after"] = shape(fixed_after, run)
    result["closed"] = not (fixed_after.next or fixed_after.tasks or fixed_after.interrupts)
    result["prior_messages_unchanged"] = fixed_after.values["messages"][:len(prior_messages)] == prior_messages
    result["new_human_exact"] = fixed_after.values["messages"][-1] == human
    result["saved_status"] = fixed_after.values["jd_ai_run"]["status"]
    assert not calls and result["prior_messages_unchanged"] and result["new_human_exact"]
    return result


if __name__ == "__main__":
    print(json.dumps({"versions": {p: version(p) for p in ("langgraph", "langgraph-checkpoint", "langchain-core")},
        "providers": 0, "database": 0, "graph_replay": 0}, sort_keys=True))
    for mode in ("first_before", "first_after", "loop_before", "all_before"):
        for prior in (False, True):
            print(json.dumps(probe(mode, prior), sort_keys=True))
    print(json.dumps(probe("loop_before", False, "clear_then_close"), sort_keys=True))
    print("PASS: 8 initial-input cases + 1 native clear-task counterexample; no replay/provider/DB")
