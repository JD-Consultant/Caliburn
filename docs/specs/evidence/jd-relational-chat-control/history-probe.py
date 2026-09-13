"""Bounded native historical lookup counterexamples; no DB/provider or resume.

Fixture setup invokes synthetic in-process nodes and explicit native closures.
All lookup/pagination paths only use get_state/get_tuple/get_state_history.
LangGraph 1.2.11, checkpoint 4.2.0, Core 1.6.3; 2026-09-13.
"""
from copy import deepcopy
from importlib.metadata import version
import json
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "experiments/jd-relational-app/src"))
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from jd_relational.ai_checkpoints import AiRunCheckpoints, new_run_record
from jd_relational.intents import AdmittedIdentity
from jd_relational.runtime_checkpoints import DocumentCheckpoints, DocumentState, build_document_graph


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def config(document, *, run=None, checkpoint=None):
    result = {"configurable": {"thread_id": document, "checkpoint_ns": ""}}
    if checkpoint is not None: result["configurable"]["checkpoint_id"] = checkpoint
    if run is not None: result["metadata"] = {"jd_run_id": run, "jd_run_index_format": 2}
    return result


def native():
    paused, calls = set(), []
    def model(state):
        run = state["jd_ai_run"]["run_id"]
        calls.append(run)
        return {"messages": [AIMessage(id=run + ":ai", content=[
            {"type": "thinking", "thinking": "synthetic native block", "signature": "synthetic-signature"},
            {"type": "text", "text": "完整合成回覆\r\n保留原生欄位。"}],
            response_metadata={"stop_reason": "end_turn"})]}
    def hold(state):
        if state["jd_ai_run"]["run_id"] in paused: interrupt("synthetic paused")
        return {}
    child = StateGraph(DocumentState)
    child.add_node("model", model); child.add_node("hold", hold)
    child.add_edge(START, "model"); child.add_edge("model", "hold"); child.add_edge("hold", END)
    root = build_document_graph(child.compile(), InMemorySaver())
    return root, str(uuid4()), str(uuid4()), paused, calls


def read_at(graph, fixed, run, dataset):
    # Probe-only adapter demonstrates reuse of existing full material decoder.
    # A production observe_at should factor the fixed decoder, not redirect latest.
    class Fixed:
        checkpointer = graph.checkpointer
        def get_state(self, supplied, **kwargs):
            return graph.get_state(supplied if supplied["configurable"].get("checkpoint_id") else fixed, **kwargs)
    return AiRunCheckpoints(Fixed()).observe(fixed["configurable"]["thread_id"], run, dataset)


def append(graph, dataset, document, paused, *, pause=False, indexed=False, name="run", close=True):
    record, human = new_run_record(dataset, document, str(uuid4()), f"{name} 原話\r\n  保留😀")
    if pause: paused.add(record.run_id)
    graph.invoke({"jd_ai_run": record.model_dump(), "messages": [human],
        "jd_ai_bindings": [], "jd_ai_read": None}, config(document, run=record.run_id if indexed else None),
        durability="sync")
    observed = AiRunCheckpoints(graph).discover(document, dataset)
    assert observed.record == record
    if close and not pause:
        observed = AiRunCheckpoints(graph).close(observed, status="completed", messages=observed.messages,
            bindings=observed.bindings, model_view=observed.model_view, read_binding=observed.read_binding)
    return observed


def parent_page(graph, first, *, limit=8):
    """Direct public parent_config walk; no branch inference or fallback."""
    rows, location, seen = [], first, set()
    for _ in range(limit):
        if location is None: return rows, None, "end"
        token = canonical(location)
        if token in seen: raise AssertionError("cycle")
        seen.add(token)
        saved = graph.checkpointer.get_tuple(location)
        if saved is None: return rows, location, "gap"
        assert saved.config["configurable"] == location["configurable"]
        state = graph.get_state(saved.config, subgraphs=True)
        rows.append(state)
        location = saved.parent_config
    return rows, location, "more" if location else "end"


def terminal_matches(rows, run):
    return [row for row in rows if not(row.next or row.tasks or row.interrupts)
        and (row.values.get("jd_ai_run") or {}).get("run_id") == run
        and row.values["jd_ai_run"]["status"] != "running"]


def ordinary_and_manual():
    graph, dataset, document, paused, calls = native()
    a = append(graph, dataset, document, paused, name="A")
    manual = AdmittedIdentity(document, uuid4(), uuid4(), "manual", None, "a" * 64, "jd_set_text")
    owner = DocumentCheckpoints(graph)
    owner.admit(manual); owner.close(manual)  # No SQL; native descriptor fixture only.
    b = append(graph, dataset, document, paused, name="B")
    rows, _, state = parent_page(graph, b.root_config, limit=32)
    matching = terminal_matches(rows, a.record.run_id)
    assert state == "end" and len(matching) == 3  # A terminal + manual admit/close.
    assert all(read_at(graph, row.config, a.record.run_id, dataset).messages == a.messages for row in matching)
    assert any(row.values.get("jd_manual_pending") for row in matching)
    c = append(graph, dataset, document, paused, pause=True, name="C")
    rows, _, state = parent_page(graph, c.root_config, limit=32)
    assert terminal_matches(rows, a.record.run_id) and not c.closed
    assert c.source_config != c.root_config
    assert len(calls) == 3
    return {"case": "A_then_B_manual_then_active_C", "A_terminal_material_preserved": True,
        "manual_duplicate_terminal_snapshots": len(matching), "active_child_pinned": True, "lookup_node_calls": 0}


def branch_prefix_counterexample():
    graph, dataset, document, paused, calls = native()
    a = append(graph, dataset, document, paused, name="A")
    b = append(graph, dataset, document, paused, name="B")
    branch = graph.update_state(a.root_config,
        {"jd_ai_run": a.record.model_copy(update={"status": "failed"}).model_dump()}, as_node="consultant")
    active = graph.update_state(b.root_config, {"jd_manual_pending": None}, as_node="consultant")
    active_state = graph.get_state(active, subgraphs=True)
    history = list(graph.get_state_history(config(document), before=active, limit=32))
    first = terminal_matches(history, a.record.run_id)[0]
    assert first.config["configurable"] == branch["configurable"]
    assert first.values["jd_ai_run"]["status"] == "failed"
    assert first.values["messages"] == active_state.values["messages"][:len(first.values["messages"])]
    chain, _, end = parent_page(graph, active, limit=32)
    original = terminal_matches(chain, a.record.run_id)[0]
    assert original.values["jd_ai_run"]["status"] == "completed" and end == "end"
    assert branch["configurable"] not in [row.config["configurable"] for row in chain]
    return {"case": "branch_prefix_is_not_original_result_proof", "history_first_A": "failed",
        "first_candidate_full_message_prefix_matches": True, "ancestor_A": "completed",
        "side_branch_rejected_by_parent_chain": True, "lookup_node_calls": 0}


def bounded_chain_and_conversation():
    graph, dataset, document, paused, calls = native()
    original = append(graph, dataset, document, paused, name="original")
    for number in range(18): append(graph, dataset, document, paused, name=f"later{number}")
    current = append(graph, dataset, document, paused, pause=True, name="active")
    first = current.root_config
    configs, pages = [], 0
    while first is not None:
        rows, first, ending = parent_page(graph, first, limit=7)
        assert ending != "gap" and len(rows) <= 7
        configs.extend(canonical(row.config["configurable"]) for row in rows)
        pages += 1
    assert len(configs) == len(set(configs)) and pages > 2
    # Chat pagination reads one original source; it must not concatenate the
    # full message replicas found in checkpoint history.
    anchor = current.source_config
    messages = current.messages
    first_messages = deepcopy(messages[:3])
    closed = AiRunCheckpoints(graph).close(current, status="cancelled", messages=current.messages,
        bindings=current.bindings, model_view=current.model_view, read_binding=current.read_binding)
    append(graph, dataset, document, paused, name="new-after-page")
    rest = graph.get_state(anchor, subgraphs=True).values["messages"][3:]
    assert first_messages + rest == messages
    assert len(calls) == 21  # Fixture writes only; no lookup or page invokes.
    return {"case": "bounded_chain_and_fixed_conversation_page", "chain_pages": pages,
        "per_page_max": 7, "unique_root_checkpoints": len(configs),
        "fixed_messages": len(messages), "later_run_excluded_from_continuation": True,
        "full_native_blocks_preserved": True, "lookup_node_calls": 0}


def start_and_missing_parent():
    output = []
    for fault in ("input_before", "loop_before"):
        graph, dataset, document, paused, calls = native()
        a = append(graph, dataset, document, paused, name="A")
        record, human = new_run_record(dataset, document, str(uuid4()), "B 原始START\r\n保留😀")
        original, failures = graph.checkpointer.put, []
        def put(conf, checkpoint, metadata, versions):
            source = metadata["source"]
            if not failures and not conf["configurable"].get("checkpoint_ns") and (
                    fault == "input_before" and source == "input" or fault == "loop_before" and source == "loop"):
                failures.append(1); raise OSError("synthetic_original_put_failure")
            return original(conf, checkpoint, metadata, versions)
        graph.checkpointer.put = put
        try:
            graph.invoke({"jd_ai_run": record.model_dump(), "messages": [human],
                "jd_ai_bindings": [], "jd_ai_read": None}, config(document), durability="sync")
        except OSError: pass
        else: raise AssertionError("Expected native save failure")
        finally: graph.checkpointer.put = original
        observed = AiRunCheckpoints(graph).discover(document, dataset)
        assert observed.record.run_id == record.run_id and observed.messages == [*a.messages, human]
        fixed = graph.get_state(observed.root_config, subgraphs=True)
        before_chain, _, before_end = parent_page(graph, observed.root_config, limit=32)
        closed = AiRunCheckpoints(graph).close(observed, status="failed", messages=observed.messages,
            bindings=observed.bindings, model_view=observed.model_view, read_binding=observed.read_binding)
        chain, gap, ending = parent_page(graph, closed.root_config, limit=32)
        if fault == "input_before":
            assert ending == "gap" and graph.checkpointer.get_tuple(gap) is None
            assert not terminal_matches(chain, a.record.run_id)
            raw_history = list(graph.get_state_history(config(document), before=closed.root_config, limit=32))
            assert terminal_matches(raw_history, a.record.run_id)
        else:
            assert fixed.next == (START,) and ending == "end"
            payload = graph.checkpointer.get_tuple(observed.root_config).checkpoint["channel_values"][START]
            assert payload["messages"] == [human] and terminal_matches(chain, a.record.run_id)
        assert calls == [a.record.run_id]
        output.append({"fault": fault, "chain_end": ending, "fixed_root_next": list(fixed.next),
            "original_human_preserved": True, "lookup_node_calls": 0})
    return {"case": "START_and_native_missing_parent", "variants": output}


def metadata_index():
    graph, dataset, document, paused, calls = native()
    a = append(graph, dataset, document, paused, indexed=True, name="indexed-A", close=False)
    run = a.record.run_id
    rows = list(graph.get_state_history(config(document), filter={"jd_run_id": run}, limit=32))
    assert rows and all(row.metadata["jd_run_id"] == run for row in rows)
    children = list(graph.checkpointer.list({"configurable": {"thread_id": document}}, filter={"jd_run_id": run}, limit=64))
    assert any(row.config["configurable"]["checkpoint_ns"] for row in children)
    closed = AiRunCheckpoints(graph).close(a, status="completed", messages=a.messages,
        bindings=a.bindings, model_view=a.model_view, read_binding=a.read_binding)
    saved = graph.checkpointer.get_tuple(closed.root_config)
    assert "jd_run_id" not in saved.metadata
    without_label = list(graph.get_state_history(config(document), filter={"jd_run_id": run}, limit=32))
    assert not terminal_matches(without_label, run)
    # Explicit metadata on the trusted closure config supplies the index. An
    # ACK loss doesn't undo the metadata or state; read back, never retry put.
    explicit = {**closed.root_config, "metadata": {"jd_run_id": run, "jd_run_index_format": 2}}
    original = graph.checkpointer.put
    def lost_ack(*args, **kwargs):
        original(*args, **kwargs)
        raise OSError("synthetic_closure_ack_lost")
    graph.checkpointer.put = lost_ack
    try:
        graph.update_state(explicit, {"jd_ai_run": closed.record.model_dump()}, as_node="consultant")
    except OSError: pass
    finally: graph.checkpointer.put = original
    indexed_closed = AiRunCheckpoints(graph).discover(document, dataset)
    assert indexed_closed.closed and indexed_closed.record == closed.record
    assert graph.checkpointer.get_tuple(indexed_closed.root_config).metadata["jd_run_id"] == run
    b = append(graph, dataset, document, paused, indexed=True, name="indexed-B", close=False)
    b_rows = list(graph.get_state_history(config(document), filter={"jd_run_id": b.record.run_id}, limit=32))
    b_input = next(row for row in b_rows if row.metadata["source"] == "input")
    assert b_input.values["jd_ai_run"]["run_id"] == run
    # Deliberate labelled side branch still matches native metadata filtering.
    side = graph.update_state({**indexed_closed.root_config, "metadata": {"jd_run_id": run}},
        {"jd_ai_run": indexed_closed.record.model_copy(update={"status": "failed"}).model_dump()}, as_node="consultant")
    head = graph.update_state(b.root_config, {"jd_manual_pending": None}, as_node="consultant")
    hits = terminal_matches(list(graph.get_state_history(config(document), before=head,
        filter={"jd_run_id": run}, limit=32)), run)
    assert {row.values["jd_ai_run"]["status"] for row in hits} == {"completed", "failed"}
    unknown = str(uuid4())
    assert not list(graph.get_state_history(config(document), before=head, filter={"jd_run_id": unknown}, limit=2))
    assert all(message.id != unknown for message in AiRunCheckpoints(graph).discover(document, dataset).messages)
    return {"case": "metadata_index_contract", "invoke_root_and_child_labelled": True,
        "ordinary_close_drops_label": True, "explicit_close_ACK_loss_keeps_label": True,
        "next_input_metadata_B_contains_old_A_values": True,
        "metadata_filter_still_contains_conflicting_side_branch": True,
        "unknown_ID_absent_from_fixed_humans_and_index": True, "lookup_node_calls": 0}


if __name__ == "__main__":
    print(canonical({"versions": {name: version(name) for name in
        ("langgraph", "langgraph-checkpoint", "langchain-core", "langgraph-checkpoint-postgres")},
        "provider_calls": 0, "database_calls": 0, "lookup_resumes": 0}))
    for probe in (ordinary_and_manual, branch_prefix_counterexample, bounded_chain_and_conversation,
                  start_and_missing_parent, metadata_index):
        print(canonical(probe()))
    print("PASS: 5 bounded native history groups; fixture setup only, no provider/DB/replay.")
