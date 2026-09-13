"""The pure consolidation notification: registered, recognised, never an effect.

The tool only records that the consultant asked for background consolidation.
It runs no B job, writes no Memory and publishes nothing, so its saved result
must never be read as a JD operation receipt or as a C publication. What it
does have to survive is every turn ending the other tools survive: a stop
before it ran, a reply that was never saved, and being read back afterwards.
"""
import json
from uuid import uuid4

from caliburn_memory.requests import REQUEST_KIND, REQUEST_TOOL_NAME, has_saved_request
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
import pytest

from jd_relational.ai_runtime import (
    AiRuntimeError, _not_executed, _pending_calls, _verify_saved_results,
)
from jd_relational.memory_context import build_consultant_tools
from jd_relational.reads import read_json

from test_ai_runtime import HEAD, _receipt_fixture, make_runtime


def notification_call(state):
    return {"messages": [AIMessage(id="notice-message", content="", tool_calls=[
        {"id": "notice-call", "name": REQUEST_TOOL_NAME, "args": {}}])]}


def test_the_consultant_is_given_the_notification_tool_by_name():
    """Identity, not a count: the consultant can actually ask for consolidation."""
    names = [tool.name for tool in build_consultant_tools()]
    assert REQUEST_TOOL_NAME in names
    assert len(names) == len(set(names)), "one tool per name"


def test_an_unanswered_notification_closes_as_its_own_result_not_a_jd_effect(make_runtime):
    """A stopped notification is not an unchanged JD operation.

    Borrowing that shape would tell the consultant a JD write was attempted
    and left unchanged, which is a different fact about a different subject.
    """
    make, _ = make_runtime
    runtime, graph, calls = make(notification_call)
    document, run = str(uuid4()), str(uuid4())
    result = runtime.start(document, run, "請整理一下", expected_revision_id=HEAD).wait(5)
    assert result.status == "failed" and len(calls) == 1
    saved = graph.get_state({"configurable": {"thread_id": document}}).values["messages"]
    assert not _pending_calls(saved)
    tool = next(message for message in saved if isinstance(message, ToolMessage))
    assert tool.name == REQUEST_TOOL_NAME and tool.status == "error"
    value = json.loads(tool.content)
    assert value == {"error": "memory_consolidation_not_requested", "next_action": "stop"}
    assert not {"operation_ref", "receipt_durability", "effect"} & set(value)


def test_an_unanswered_notification_never_counts_as_a_saved_request(make_runtime):
    """Nothing asked for scheduling, so nothing may be admitted for it."""
    make, _ = make_runtime
    runtime, graph, _ = make(notification_call)
    document = str(uuid4())
    runtime.start(document, str(uuid4()), "請整理一下", expected_revision_id=HEAD).wait(5)
    saved = graph.get_state({"configurable": {"thread_id": document}}).values["messages"]
    assert has_saved_request(saved) is False


def test_a_saved_notification_receipt_needs_no_binding_and_is_still_a_request(make_runtime):
    """The artifact is the receipt; there is no SQL operation behind it."""
    make, _ = make_runtime
    def answered(state):
        return {"messages": [
            AIMessage(id="notice-message", content="", tool_calls=[
                {"id": "notice-call", "name": REQUEST_TOOL_NAME, "args": {}}]),
            ToolMessage(id="notice-result", tool_call_id="notice-call", name=REQUEST_TOOL_NAME,
                        content="收到整理請求", status="success", artifact={"kind": REQUEST_KIND}),
            AIMessage(id="notice-final", content="我繼續問下一題。")]}
    runtime, graph, _ = make(answered)
    document = str(uuid4())
    result = runtime.start(document, str(uuid4()), "請整理一下", expected_revision_id=HEAD).wait(5)
    assert result.status == "completed"
    saved = graph.get_state({"configurable": {"thread_id": document}}).values["messages"]
    assert has_saved_request(saved) is True


@pytest.mark.parametrize("forged", ["no_artifact", "wrong_kind", "borrowed_jd_failure"])
def test_a_notification_without_its_own_receipt_or_result_is_refused(forged):
    """Only this tool's own artifact, or its own fixed stop result, counts.

    A success claim needs the artifact the tool itself emits -- a model cannot
    write one. A failure may only be the notification's own stop result: a JD
    operation result borrowed into this call would assert an effect on a
    subject this tool never touches.
    """
    _, _, _, codec = _receipt_fixture()
    run = str(uuid4())
    call = AIMessage(id="notice-message", content="", tool_calls=[
        {"id": "notice-call", "name": REQUEST_TOOL_NAME, "args": {}}])
    result = (ToolMessage(id="notice-result", tool_call_id="notice-call", name=REQUEST_TOOL_NAME,
                          content=read_json(_not_executed()), status="error")
              if forged == "borrowed_jd_failure" else
              ToolMessage(id="notice-result", tool_call_id="notice-call", name=REQUEST_TOOL_NAME,
                          content="收到整理請求", status="success",
                          artifact=None if forged == "no_artifact" else {"kind": "jd_operation"}))
    with pytest.raises(AiRuntimeError, match="^invalid_saved_tool_result$"):
        _verify_saved_results([HumanMessage(id=run, content="本輪"), call, result],
                              (), {}, codec, run_id=run)
