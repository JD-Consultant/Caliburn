"""Actual native tool handoff and C staging; synthetic SQLite, no provider."""
from dataclasses import replace
import json
from types import SimpleNamespace
from threading import Event
from uuid import uuid4

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
import pytest

from caliburn_memory import PublicationStore

from jd_relational.ai_checkpoints import AiRunCheckpoints, new_run_record
from jd_relational.ai_runtime import AiRuntime, AiRuntimeError, _pending_calls
from jd_relational.consultant_context import ConsultantState
from jd_relational.consultant_tools import BINDING_NODE, AiToolError, AiToolMiddleware, AiToolSession
from jd_relational.memory_context import build_consultant_tools
from jd_relational.memory_repair_session import MemoryRepairSession, repair_progress
from jd_relational.references import ReferenceCodec
from jd_relational.runtime_checkpoints import build_document_graph
from test_chat_history import native
from test_consultant_memory_context import memory
from test_consultant_context import FixedModel


def call(number, old="只做初步確認。", new="維修由外包負責。", *, args=None):
    return AIMessage(id=f"repair-{number}", content="", tool_calls=[{
        "name": "repair_memory", "id": f"repair-call-{number}", "args": args if args is not None else {
        "edits": [{"path": "/memory/knowledge.md", "diff": f"@@\n-{old}\n+{new}"}]}}])


def read_call(number):
    return AIMessage(id=f"read-{number}", content="", tool_calls=[{
        "name": "read_file", "id": f"read-call-{number}",
        "args": {"file_path": "/memory/knowledge.md", "offset": 0, "limit": 100}}])


def setup_repair(memory, replies):
    store, pub, publish, pin = memory
    publish(0, "只做初步確認。")
    selected = pin()
    repair = MemoryRepairSession(selected, pub)
    source = pub.current().processed_source
    stop = Event()
    permit = SimpleNamespace(identity=SimpleNamespace(document_id=selected.document_id,
        run_id=selected.run_id, request_digest="a" * 64), stop_event=stop)
    tool_session = AiToolSession(
        SimpleNamespace(execute_foreground=lambda *_: pytest.fail("unexpected JD write")),
        permit,
        SimpleNamespace(read_revision=lambda *_: pytest.fail("unexpected JD history read")),
        SimpleNamespace(read=lambda *_: pytest.fail("unexpected JD read")),
        SimpleNamespace(read=lambda *_: pytest.fail("unexpected JD change read")),
        ReferenceCodec(b"s" * 32, selected.dataset_id),
    )
    context = SimpleNamespace(dataset_id=selected.dataset_id, document_id=selected.document_id,
        run_id=selected.run_id, memory_session=selected, memory_repair_session=repair,
        tool_session=tool_session, stop_event=stop,
        source_notice=lambda messages: {"source_ref": source})
    model = FixedModel(replies=replies)
    child = create_agent(model, tools=build_consultant_tools(), middleware=[AiToolMiddleware()],
        state_schema=ConsultantState)
    root = build_document_graph(child, InMemorySaver(), store=store)
    payload = {"messages": [HumanMessage(id=selected.run_id, content="更正：維修由外包負責。")],
        "jd_memory_view": selected.view, "jd_ai_bindings": [], "jd_ai_read": None,
        "jd_memory_repair_bindings": []}
    config = {"configurable": {"thread_id": selected.document_id}, "max_concurrency": 1}
    return root, model, selected, repair, pub, context, payload, config


def test_two_native_repairs_refresh_only_this_turn_and_keep_staging_off_root(memory):
    root, model, initial, repair, pub, context, payload, config = setup_repair(memory,
        [call(1), call(2, "維修由外包負責。", "只通報異常，維修由外包負責。"), AIMessage(content="已更正。")])
    result = root.invoke(payload, config, context=context, durability="sync")
    assert pub.current().revision == 3 and len(model.requests) == 3
    assert result["jd_memory_view"] == initial.view
    assert not {"files", "request", "material", "version", "outcome"} & result.keys()
    progress = repair_progress(result, dataset_id=initial.dataset_id,
        document_id=initial.document_id, run_id=initial.run_id)
    assert progress.failures == 0 and progress.outcome["head"]["revision"] == 3
    results = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(results) == 2 and all(m.status == "success" for m in results)
    assert results[0].artifact["request"]["expected_revision"] == 1
    assert results[1].artifact["request"]["expected_revision"] == 2
    assert "operation_id" not in json.loads(results[0].content)
    loaded = repair.current_read(result).backend.read("/memory/knowledge.md")
    assert not loaded.error and "只通報異常" in loaded.file_data["content"]
    new_run = dict(payload, messages=result["messages"], jd_memory_repair_bindings=[])
    assert repair.current_read(new_run) is initial


def test_two_bad_calls_stop_repair_without_entering_core_or_sending_internal_ids(memory, monkeypatch):
    root, model, initial, repair, pub, context, payload, config = setup_repair(memory,
        [call(1, args={"edits": []}), call(2, args={"edits": []}), call(3), AIMessage(content="先釐清。")])
    monkeypatch.setattr(repair.workflow, "_seed", lambda state: pytest.fail("no C on invalid/limit"))
    result = root.invoke(payload, config, context=context, durability="sync")
    feedback = [json.loads(m.content) for m in result["messages"] if isinstance(m, ToolMessage)]
    assert [m["status"] for m in feedback] == ["invalid_edit", "invalid_edit", "repair_limit"]
    assert [m["retryable"] for m in feedback] == [True, False, False]
    assert pub.current().revision == 1


def test_native_memory_read_keeps_applied_repair_when_rebased_background_publishes_later(
        memory, monkeypatch):
    root, model, initial, repair, pub, context, payload, config = setup_repair(memory,
        [call(1), read_call(1), AIMessage(content="已核對新版。")])
    actual_publish = pub.publish
    later = []

    def publish_then_rebased_background(request):
        applied = actual_publish(request)
        if request.kind == "repair" and not later:
            version = initial.artifacts.save_memory(
                knowledge="維修由外包負責。背景重整後補充工作節奏。",
                guide="背景重整後導覽")
            later.append(actual_publish(pub.prepare(version,
                expected_revision=applied.revision, kind="consolidation",
                processed_source=applied.processed_source)))
        return applied

    monkeypatch.setattr(pub, "publish", publish_then_rebased_background)
    result = root.invoke(payload, config, context=context, durability="sync")
    feedback = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert [m.name for m in feedback] == ["repair_memory", "read_file"]
    assert feedback[0].status == "success" and "維修由外包負責" in feedback[1].content
    assert "背景重整後補充" not in feedback[1].content
    assert result["jd_memory_view"] == initial.view
    assert later and pub.current() == later[0] and pub.current().revision == 3
    assert repair.current_read(result).head.revision == 2


def test_wrong_scope_and_stop_are_checked_before_starting_c(memory):
    root, model, initial, repair, pub, context, payload, config = setup_repair(memory, [call(1)])
    context.stop_event.set()
    result = root.invoke(payload, config, context=context, durability="sync")
    assert pub.current().revision == 1 and len(model.requests) == 0
    assert not result.get("jd_memory_repair_bindings")


def test_cancel_during_c_drains_started_save_and_stops_next_model_work(memory, monkeypatch):
    root, model, initial, repair, pub, context, payload, config = setup_repair(memory,
        [call(1), AIMessage(content="result")])
    original = repair.workflow._prepare
    def prepare(state):
        context.stop_event.set()
        return original(state)
    monkeypatch.setattr(repair.workflow, "_prepare", prepare)
    result = root.invoke(payload, config, context=context, durability="sync")
    assert pub.current().revision == 2
    assert next(m for m in result["messages"] if isinstance(m, ToolMessage)).status == "success"
    assert len(model.requests) == 1, "A stop raised during C must block the next model request."


def parallel_calls(number=1):
    """One invalid response that puts a repair call beside another call."""
    message = call(number)
    message.tool_calls.append({"name": "read_file", "id": f"read-call-{number}",
        "args": {"file_path": "/memory/knowledge.md", "offset": 0, "limit": 100},
        "type": "tool_call"})
    return message


def stopped(memory, monkeypatch, fault, replies=None):
    """Reproduce one real native stop that precedes C, then observe it.

    `binding` stops inside the App's own binding handler and `parallel_calls`
    stops there through an invalid multi-call response, both before any binding
    exists. `tool_handoff` stops on the consultant's own tool node and
    `child_start` on the fixed child's own START, both after the binding was
    saved. None of them may start the core.
    """
    root, model, initial, repair, pub, context, payload, config = setup_repair(
        memory, replies if replies is not None else [call(1)])
    record, human = new_run_record(initial.dataset_id, initial.document_id, initial.run_id,
        "合成停止收尾", start_revision_id=str(uuid4()))
    payload.update(jd_ai_run=record.model_dump(mode="json"), messages=[human])
    monkeypatch.setattr(repair.workflow, "_seed",
        lambda state: pytest.fail("A stop proven before C must never start the core"))
    expected = OSError
    if fault == "parallel_calls":
        # The invalid response itself is the fault: the binding handler refuses
        # it before any C material exists, and never reaches the repair session.
        expected = AiToolError
    elif fault == "binding":
        def unavailable(_messages):
            raise OSError("synthetic source notice failure")
        context.source_notice = unavailable
    elif fault == "tool_handoff":
        # The native tool wrapper converts an unknown dependency failure into
        # the App's fixed public code, so the stop lands on the tool node.
        expected = AiToolError
        def refuse(self, runtime):
            raise OSError("synthetic tool handoff failure")
        monkeypatch.setattr(MemoryRepairSession, "handoff", refuse)
    else:
        original_put = root.checkpointer.put
        def fail_first_child_loop(cfg, checkpoint, metadata, versions):
            if (metadata["source"] == "loop"
                    and cfg["configurable"].get("checkpoint_ns", "").startswith("memory_repair:")):
                raise OSError("synthetic first child loop save failure")
            return original_put(cfg, checkpoint, metadata, versions)
        monkeypatch.setattr(root.checkpointer, "put", fail_first_child_loop)
    with pytest.raises(expected):
        root.invoke(payload, config, context=context, durability="sync")
    runtime = AiRuntime.__new__(AiRuntime)
    runtime.graph, runtime.memory_engine = root, pub.engine
    runtime.conversation_sources = initial.source.service
    observed = AiRunCheckpoints(root).observe(initial.document_id, initial.run_id, initial.dataset_id)
    assert len(model.requests) == 1 and pub.current().revision == 1
    return runtime, observed


def recovered(runtime, observed):
    return runtime._recover_pending_repair(observed, observed.messages,
                                           _pending_calls(observed.messages))


@pytest.mark.parametrize("fault", ["binding", "child_start"])
def test_a_stop_proven_before_c_closes_the_same_original_call_as_not_executed(memory, monkeypatch, fault):
    runtime, observed = stopped(memory, monkeypatch, fault)
    message = recovered(runtime, observed)
    content = json.loads(message.content)
    assert message.name == "repair_memory" and message.tool_call_id == "repair-call-1"
    assert message.status == "error" and message.artifact["request"] is None
    assert content["status"] == "not_executed" and content["retryable"] is False
    if fault == "binding":
        assert observed.consultant_next == [BINDING_NODE] and observed.repair_checkpoint is None
        assert observed.repair_bindings == [] and message.artifact["operation_id"] is None
    else:
        assert observed.consultant_next is None and observed.repair_checkpoint["next"] == ["__start__"]
        assert message.artifact["operation_id"] == observed.repair_bindings[0]["operation_id"]


@pytest.mark.parametrize("step", ["tools", "model", "__start__"])
def test_an_unbound_call_stopped_outside_the_binding_node_keeps_the_gate(memory, monkeypatch, step):
    runtime, observed = stopped(memory, monkeypatch, "binding")
    elsewhere = replace(observed, _consultant_next_json=json.dumps([step]))
    with pytest.raises(AiRuntimeError, match="^run_recovery_required$"):
        recovered(runtime, elsewhere)


@pytest.mark.parametrize("mutation",
    ["operation_id", "base", "source_reference", "edits", "missing_key", "absent"])
def test_a_child_start_input_that_disagrees_with_the_original_call_keeps_the_gate(
        memory, monkeypatch, mutation):
    runtime, observed = stopped(memory, monkeypatch, "child_start")
    checkpoint = observed.repair_checkpoint
    payload = checkpoint["input"]
    if mutation == "operation_id":
        payload["operation_id"] = str(uuid4())
    elif mutation == "base":
        payload["base"] = dict(payload["base"], revision=payload["base"]["revision"] + 1)
    elif mutation == "source_reference":
        payload["source_reference"] = "conversation:synthetic-other-document"
    elif mutation == "edits":
        payload["edits"] = [{"path": "/memory/guide.md", "diff": "@@\n-其他\n+其他更正"}]
    elif mutation == "missing_key":
        payload.pop("edits")
    else:
        checkpoint["input"] = None
    changed = replace(observed, _repair_checkpoint_json=json.dumps(checkpoint))
    with pytest.raises(AiRuntimeError, match="^run_recovery_required$"):
        recovered(runtime, changed)


def test_a_receipt_at_the_child_start_position_is_never_called_not_executed(memory, monkeypatch):
    runtime, observed = stopped(memory, monkeypatch, "child_start")
    operation = observed.repair_bindings[0]["operation_id"]
    # A START position proves no node ran, but an actual receipt outranks it.
    monkeypatch.setattr(PublicationStore, "receipt",
        lambda self, value: {"operation_id": value} if value == operation else None)
    with pytest.raises(AiRuntimeError, match="^run_recovery_required$"):
        recovered(runtime, observed)


def test_a_stop_on_the_consultants_own_tool_node_is_not_executed_not_merely_unpublished(
        memory, monkeypatch):
    """A bound call whose tool never returned to root never started C.

    The root's pending task is still the consultant subgraph, so the fixed
    `memory_repair` node has not run. Without that position this would rest on
    a missing child checkpoint plus a missing receipt, which proves nothing.
    """
    runtime, observed = stopped(memory, monkeypatch, "tool_handoff")
    assert observed.consultant_next == ["tools"] and observed.repair_checkpoint is None
    assert len(observed.repair_bindings) == 1
    message = recovered(runtime, observed)
    content = json.loads(message.content)
    assert content["status"] == "not_executed" and content["retryable"] is False
    assert message.artifact["operation_id"] == observed.repair_bindings[0]["operation_id"]
    assert message.artifact["request"] is None


def test_an_unknown_stop_without_any_position_evidence_keeps_the_gate(memory, monkeypatch):
    runtime, observed = stopped(memory, monkeypatch, "tool_handoff")
    blind = replace(observed, _consultant_next_json="null")
    with pytest.raises(AiRuntimeError, match="^run_recovery_required$"):
        recovered(runtime, blind)


def test_an_invalid_parallel_response_still_closes_its_repair_call(memory, monkeypatch):
    """A repair call beside another call must not lock the document forever.

    The binding handler refuses the whole response, so nothing was bound and C
    never started; the original repair call still owes this turn a terminal.
    """
    runtime, observed = stopped(memory, monkeypatch, "parallel_calls",
                                replies=[parallel_calls(1)])
    pending = _pending_calls(observed.messages)
    assert len(pending) == 2 and observed.repair_bindings == []
    assert observed.consultant_next == [BINDING_NODE]
    message = recovered(runtime, observed)
    assert message.tool_call_id == "repair-call-1"
    assert json.loads(message.content)["status"] == "not_executed"
    assert message.artifact["operation_id"] is None
