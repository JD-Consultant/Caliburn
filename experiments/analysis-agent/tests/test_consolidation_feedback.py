"""ER-B01: actual Agent/StateBackend/SDK loop; only external HTTP is synthetic."""
import json

import httpx
import pytest
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from openai import APIConnectionError

from analysis_agent.consolidation import ConsolidationWorkflow
from test_consolidation import harness, call, done, knowledge


MISSING = "/interviews/00000000-0000-0000-0000-000000000000/summary.md"
KNOWLEDGE = "/memory/knowledge.md"


def invalid_then_done(h):
    h.replies.extend([call("write_file", file_path=KNOWLEDGE,
                           content="保留案例條件。\n詳記：" + MISSING), done()])


def correction(h):
    return call("edit_file", file_path=KNOWLEDGE, old_string=MISSING,
                new_string=h.extracted["files"][0]["summary_path"])


def agent_state(h, workflow):
    # The attempt is dynamically invoked, so root get_state cannot discover it.
    # Public Saver.list exposes its serialized child state without private APIs.
    checkpoints = [entry for entry in h.saver.list(workflow.config)
                   if "thread_model_call_count" in entry.checkpoint["channel_values"]]
    assert checkpoints
    entry = max(checkpoints, key=lambda entry: entry.checkpoint["id"])
    values = entry.checkpoint["channel_values"]
    state = {key: values[key] for key in ("messages", "thread_model_call_count",
                                         "thread_tool_call_count")}
    state["file_history"] = h.saver.get_delta_channel_history(config=entry.config, channels=["files"])["files"]
    return state


def staged_knowledge(state):
    writes = [value[KNOWLEDGE] for _, _, value in state["file_history"]["writes"] if KNOWLEDGE in value]
    return writes[-1]["content"]


def assert_paired(wire):
    calls = [item["call_id"] for item in wire["input"] if item.get("type") == "function_call"]
    results = [item["call_id"] for item in wire["input"] if item.get("type") == "function_call_output"]
    assert results == calls
    assert len(calls) == len(set(calls))


def runtime_feedback(wire):
    return [item for item in wire["input"] if item.get("role") == "user"
            and "Runtime validation feedback" in json.dumps(item)]


def assert_unpublished(h):
    assert h.pub.current() is None
    assert h.store.search(("q019-memory", h.reader.document_id, "versions")) == []


def test_missing_reference_and_done_repairs_inside_same_agent_before_publication(harness):
    h = harness
    original_source = h.reader.read(h.ref)
    original_b1 = h.b1.graph.get_state(h.b1.config).values
    invalid_then_done(h)
    h.replies[-1]["output"].insert(0, {"type": "reasoning", "id": "rs_invalid",
        "summary": [], "encrypted_content": "opaque-b2-validation"})

    def repair_without_early_publication():
        assert_unpublished(h)
        return correction(h)

    h.replies.extend([repair_without_early_publication, done()])
    workflow = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver)
    result = workflow.start()
    assert result["used_model_steps"] == 4 and result["used_tool_calls"] == 2
    assert len(h.sent) == 5  # B1 once, B2 write/done/edit/done.
    assert result["attempt"] == 1 and h.pub.current().revision == 1
    assert knowledge(h) == "保留案例條件。\n詳記：" + h.extracted["files"][0]["summary_path"]
    feedback = runtime_feedback(h.sent[3])
    assert len(feedback) == 1
    assert KNOWLEDGE in json.dumps(feedback) and MISSING in json.dumps(feedback)
    assert "unavailable" in json.dumps(feedback)
    assert "opaque-b2-validation" in json.dumps(h.sent[3])
    for wire in h.sent[1:]:
        assert_paired(wire)
        assert wire["store"] is False and "previous_response_id" not in wire
    assert len(runtime_feedback(h.sent[-1])) == 1
    assert h.reader.read(h.ref) == original_source  # No employee source injection.
    assert h.b1.graph.get_state(h.b1.config).values == original_b1
    assert workflow.resume()["result"] == result["result"] and len(h.sent) == 5


@pytest.mark.parametrize("cap", [2, 4])
def test_persistently_invalid_final_hits_existing_limit_and_reopen_makes_no_http(harness, cap):
    h = harness
    invalid_then_done(h)
    h.replies.extend(done() for _ in range(cap - 2))
    workflow = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver, max_model_steps=cap)
    with pytest.raises(ModelCallLimitExceededError, match="limit"):
        workflow.start()
    before = agent_state(h, workflow)
    assert before["thread_model_call_count"] == cap
    assert before["thread_tool_call_count"]["__all__"] == 1
    feedback = [m for m in before["messages"] if isinstance(m, HumanMessage)][1:]
    assert len(feedback) == cap - 1
    assert all("Runtime validation feedback" in m.content for m in feedback)
    assert len(h.sent) == cap + 1
    reopened = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver, max_model_steps=cap)
    with pytest.raises(ModelCallLimitExceededError, match="limit"):
        reopened.resume()
    assert agent_state(h, reopened) == before
    assert len(h.sent) == cap + 1
    assert_unpublished(h)


def test_interrupted_correction_reopens_exact_saved_messages_files_and_counters(harness):
    h = harness
    # Changing ChatOpenAI.max_retries after construction does not rebuild its
    # SDK client. Disable HTTP retries on the actual public SDK client here.
    h.model = h.model.model_copy(update={"root_client": h.model.root_client.with_options(max_retries=0)})
    invalid_then_done(h)
    h.replies.append(httpx.ConnectError("interrupted corrective request"))
    workflow = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver)
    with pytest.raises(APIConnectionError):
        workflow.start()
    before = agent_state(h, workflow)
    assert workflow.graph.get_state(workflow.config).next == ("consolidate",)
    assert before["thread_model_call_count"] == 2
    assert before["thread_tool_call_count"]["__all__"] == 1
    assert MISSING in staged_knowledge(before)
    results = [m for m in before["messages"] if isinstance(m, ToolMessage)]
    calls = [c for m in before["messages"] if isinstance(m, AIMessage) for c in m.tool_calls]
    assert [m.tool_call_id for m in results] == [c["id"] for c in calls]
    assert len(runtime_feedback(h.sent[-1])) == 1
    assert_unpublished(h)
    reopened = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver)
    assert agent_state(h, reopened) == before
    h.replies.extend([correction(h), done()])
    result = reopened.resume()
    assert h.sent[4] == h.sent[3]  # Retry the same pending request, not write/done.
    assert len(h.sent) == 6 and result["used_model_steps"] == 4
    assert result["used_tool_calls"] == 2 and h.pub.current().revision == 1
    assert "保留案例條件" in knowledge(h) and MISSING not in knowledge(h)
    assert_paired(h.sent[-1])


def test_correction_cannot_execute_past_existing_tool_limit(harness):
    h = harness
    invalid_then_done(h)
    h.replies.append(correction(h))
    workflow = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver, max_tool_calls=1)
    with pytest.raises(Exception, match="limit"):
        workflow.start()
    before = agent_state(h, workflow)
    # Tool limit's after_model raises before the model counter's after hook;
    # resume stays on that rejection, without another model or tool execution.
    assert before["thread_model_call_count"] == 2
    assert MISSING in staged_knowledge(before)
    with pytest.raises(Exception, match="limit"):
        ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver, max_tool_calls=1).resume()
    assert len(h.sent) == 4
    assert_unpublished(h)


@pytest.mark.parametrize("file_path,invalid,reason", [
    (KNOWLEDGE, "細" * 2001, "2000"),
    ("/memory/guide.md", ("路由\n" * 1400), "4000"),
    (KNOWLEDGE, "/interviews/missing/summary.md", "address"),
    (KNOWLEDGE, "conversation:broken", "reference"),
])
def test_known_final_format_and_reference_errors_identify_file_for_correction(harness, file_path, invalid, reason):
    h = harness
    h.replies.extend([call("write_file", file_path=file_path, content=invalid), done(),
                      call("write_file", file_path=file_path, content="已修正"), done()])
    result = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver).start()
    feedback = runtime_feedback(h.sent[3])
    assert len(feedback) == 1
    assert file_path in json.dumps(feedback) and reason in json.dumps(feedback)
    assert len(json.dumps(feedback, ensure_ascii=False)) < 1000
    assert result["used_model_steps"] == 4 and result["used_tool_calls"] == 2
    assert h.artifacts.read_text(file_path, h.pub.current().memory) == "已修正"


@pytest.mark.parametrize("failure", ["incomplete", "failed", "refusal", "malformed"])
def test_invalid_staging_does_not_turn_provider_failure_into_corrective_call(harness, failure):
    h = harness
    invalid_then_done(h)
    last = h.replies[-1]
    if failure in {"incomplete", "failed"}:
        last["status"] = failure
    elif failure == "refusal":
        last["output"][0]["content"] = [{"type": "refusal", "refusal": "Cannot consolidate"}]
    else:
        h.replies[-1] = call("write_file", file_path=KNOWLEDGE, content="bad")
        h.replies[-1]["output"][0]["arguments"] = '{"file_path":'
    workflow = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver)
    with pytest.raises(ValueError, match="complete|refus|invalid tool"):
        workflow.start()
    with pytest.raises(ValueError, match="complete|refus|invalid tool"):
        ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver).resume()
    assert len(h.sent) == 3 and not any(runtime_feedback(wire) for wire in h.sent)
    assert_unpublished(h)


@pytest.mark.parametrize("failure", [RuntimeError, ValueError])
def test_unknown_reference_reader_failure_is_not_model_correction(harness, monkeypatch, failure):
    h = harness
    h.replies.extend([call("write_file", file_path=KNOWLEDGE, content=h.ref), done()])

    def fail(*args, **kwargs):
        raise failure("injected unknown reader failure")

    monkeypatch.setattr(h.reader, "read", fail)
    workflow = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver)
    with pytest.raises(failure, match="injected unknown"):
        workflow.start()
    with pytest.raises(failure, match="injected unknown"):
        ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver).resume()
    assert len(h.sent) == 3 and not any(runtime_feedback(wire) for wire in h.sent)
    assert_unpublished(h)


def test_corrected_attempt_rebases_on_c_head_with_remaining_budget_and_no_b1_rerun(harness):
    h = harness
    original_b1 = h.b1.graph.get_state(h.b1.config).values
    invalid_then_done(h)

    def concurrent_c():
        version = h.artifacts.save_memory(knowledge="C 已更正：保留年租條件。", guide="目前條件")
        h.pub.publish(h.pub.prepare(version, expected_revision=0, kind="repair", repair_sources=(h.ref,)))
        return done()

    h.replies.extend([correction(h), concurrent_c, done()])
    result = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver, max_model_steps=5).start()
    assert result["attempt"] == 2 and result["used_model_steps"] == 5
    assert result["used_tool_calls"] == 2 and len(h.sent) == 6
    assert knowledge(h) == "C 已更正：保留年租條件。"
    assert h.pub.current().revision == 2 and h.pub.current().processed_source == h.ref
    assert "RECENT_REPAIRS" in json.dumps(h.sent[-1]) and h.ref in json.dumps(h.sent[-1])
    assert not runtime_feedback(h.sent[-1])  # Fresh stale attempt, not old feedback.
    assert h.b1.graph.get_state(h.b1.config).values == original_b1


def test_repaired_publication_lost_reply_reconciles_receipt_without_more_model(harness, monkeypatch):
    h = harness
    invalid_then_done(h)
    h.replies.extend([correction(h), done()])
    original = h.pub.publish

    def lost_reply(request):
        original(request)
        raise RuntimeError("lost repaired commit reply")

    workflow = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver)
    with monkeypatch.context() as fault:
        fault.setattr(h.pub, "publish", lost_reply)
        with pytest.raises(RuntimeError, match="lost repaired"):
            workflow.start()
    request = workflow.graph.get_state(workflow.config).values["request"]
    assert h.pub.receipt(request["operation_id"]) is not None
    result = ConsolidationWorkflow(h.b1, h.pub, h.model, h.saver).resume()
    assert result["request"] == request and h.pub.current().revision == 1
    assert len(h.sent) == 5 and MISSING not in knowledge(h)
