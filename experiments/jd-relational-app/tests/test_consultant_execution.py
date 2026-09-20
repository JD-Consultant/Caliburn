"""A consultant execution policy derived only from canonical saved messages."""

import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.runtime import Runtime
import pytest

from jd_relational.consultant_execution import (
    ConsultantExecutionError,
    ConsultantExecutionMiddleware,
    decide_consultant_execution,
)
from jd_relational.consultant_model import MAX_MODEL_STEPS, MAX_TOOL_CALLS
from jd_relational.generated.reads import ReadPage
from jd_relational.result_transport import validate_result


def _human(run_id):
    return HumanMessage(id=run_id, content="合成員工原話")


def _result(status, next_action, *, operation_ref=None):
    success = status in {"committed", "no_change"}
    effect = "changed" if status == "committed" else "unknown" if status == "outcome_unknown" else "unchanged"
    value = {
        "status": status,
        "effect": effect,
        "receipt_durability": "unconfirmed" if status == "outcome_unknown" else "confirmed" if operation_ref else "unconfirmed",
        "operation_ref": operation_ref,
        "result_revision_ref": "revision-ref" if success else None,
        "change_ref": "change-ref" if status == "committed" else None,
        "error": None if success else {
            "code": status,
            "message": "合成且不含私密資料的工具結果。",
            "related_refs": [],
        },
        "next_action": next_action,
    }
    return validate_result(value)


def _read_page():
    return ReadPage(
        format_version=2,
        view="current",
        access="current",
        revision_ref="revision-ref",
        records=[],
        start_index=0,
        total_records=0,
        has_more=False,
        next_cursor=None,
        oversized_unit=False,
    ).model_dump(mode="json")


def _exchange(name, args, result, *, status="error", call_id=None):
    call_id = call_id or f"call-{uuid4()}"
    request = AIMessage(
        id=f"message-{uuid4()}",
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )
    reply = ToolMessage(
        id=f"result-{uuid4()}",
        name=name,
        tool_call_id=call_id,
        content=json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        status=status,
    )
    return [request, reply]


def _decision(messages, run_id, *, used=1):
    return decide_consultant_execution(
        messages,
        run_id=run_id,
        model_requests_used=used,
    )


def test_original_invalid_input_allows_two_replacements_then_finalizes():
    run_id = str(uuid4())
    failed = _result("invalid_input", "correct_arguments")
    messages = [_human(run_id)]
    messages += _exchange("jd_set_text", {"text": "a"}, failed)
    assert _decision(messages, run_id).finalize is False

    messages += _exchange("jd_set_text", {"text": "b"}, failed)
    assert _decision(messages, run_id).finalize is False

    messages += _exchange("jd_set_text", {"text": "c"}, failed)
    decision = _decision(messages, run_id)
    assert decision.finalize is True
    assert decision.reason == "correction_exhausted"


def test_successful_replacement_closes_the_episode():
    run_id = str(uuid4())
    messages = [_human(run_id)]
    messages += _exchange(
        "jd_set_text", {"text": "bad"},
        _result("invalid_input", "correct_arguments"),
    )
    messages += _exchange(
        "jd_set_text", {"text": "fixed"},
        _result("committed", "continue", operation_ref="operation-ref"),
        status="success",
    )
    assert _decision(messages, run_id).finalize is False


def test_stale_reread_does_not_reset_or_consume_mutation_submissions():
    run_id = str(uuid4())
    stale = _result("stale_view", "reread_current", operation_ref="operation-ref")
    messages = [_human(run_id)]
    messages += _exchange("jd_set_text", {"text": "old"}, stale)
    messages += _exchange(
        "jd_read",
        {"view": "current", "target_ref": None, "cursor": None},
        _read_page(),
        status="success",
    )
    messages += _exchange("jd_set_text", {"text": "new"}, stale)
    assert _decision(messages, run_id).finalize is False

    messages += _exchange("jd_set_text", {"text": "newer"}, stale)
    assert _decision(messages, run_id).reason == "correction_exhausted"


def test_exact_request_and_result_repeat_stops_without_a_third_try():
    run_id = str(uuid4())
    failed = _result("invalid_input", "correct_arguments")
    messages = [_human(run_id)]
    messages += _exchange("jd_set_text", {"text": "same"}, failed)
    messages += _exchange("jd_set_text", {"text": "same"}, failed)
    decision = _decision(messages, run_id)
    assert decision.finalize is True
    assert decision.reason == "no_progress"


@pytest.mark.parametrize("result", [
    _result("invalid_input", "stop"),
    _result("outcome_unknown", "reconcile_operation", operation_ref="operation-ref"),
])
def test_stop_and_reconcile_results_never_authorize_another_tool(result):
    run_id = str(uuid4())
    messages = [_human(run_id), *_exchange("jd_set_text", {"text": "x"}, result)]
    decision = _decision(messages, run_id)
    assert decision.finalize is True
    assert decision.reason == "nonrecoverable_result"


def test_dependent_items_never_implies_cascade_or_set_null():
    run_id = str(uuid4())
    dependent = _result("dependent_items", "resolve_dependencies", operation_ref="operation-ref")
    messages = [_human(run_id), *_exchange("jd_delete_item", {"target_ref": "item-ref"}, dependent)]
    decision = _decision(messages, run_id)
    assert decision.finalize is False
    assert decision.reason is None


def test_previous_employee_runs_do_not_consume_the_new_child_budget():
    previous_run = str(uuid4())
    current_run = str(uuid4())
    failed = _result("invalid_input", "correct_arguments")
    messages = [_human(previous_run)]
    messages += _exchange("jd_set_text", {"text": "a"}, failed)
    messages += _exchange("jd_set_text", {"text": "b"}, failed)
    messages += _exchange("jd_set_text", {"text": "c"}, failed)
    messages += [_human(current_run)]

    decision = _decision(messages, current_run, used=0)
    assert decision.finalize is False
    assert decision.reason is None


def test_malformed_known_tool_result_fails_closed():
    run_id = str(uuid4())
    messages = [_human(run_id)]
    messages += _exchange(
        "jd_set_text",
        {"text": "x"},
        {"status": "invalid_input", "next_action": "correct_arguments"},
    )
    with pytest.raises(ConsultantExecutionError, match="^invalid_tool_result$"):
        _decision(messages, run_id)


def _model_request(run_id, *, model_requests_used, messages=None, system_blocks=None):
    messages = messages or [_human(run_id)]
    system_blocks = system_blocks or [{"type": "text", "text": "assembled context"}]
    return ModelRequest(
        model=FakeMessagesListChatModel(responses=[AIMessage(content="synthetic answer")]),
        messages=messages,
        system_message=SystemMessage(content=system_blocks),
        tools=[{"type": "function", "function": {"name": "jd_set_text"}}],
        tool_choice="auto",
        state={
            "messages": messages,
            "thread_model_call_count": model_requests_used,
            "continuation_compaction": {"summary": "保留的上下文延續"},
        },
        runtime=Runtime(context=SimpleNamespace(run_id=run_id)),
    )


def test_request_64_has_no_tools_and_explicit_none_tool_choice():
    run_id = str(uuid4())
    request = _model_request(run_id, model_requests_used=63)
    seen = []

    def handler(projected):
        seen.append(projected)
        return ModelResponse(result=[AIMessage(content="只整理已確認結果")])

    response = ConsultantExecutionMiddleware().wrap_model_call(request, handler)

    assert isinstance(response, ModelResponse)
    assert len(seen) == 1
    assert seen[0].tools == []
    assert seen[0].tool_choice == "none"
    assert seen[0].model_settings["tool_choice"] == "none"
    assert "strict" not in seen[0].model_settings
    assert "不能再呼叫工具" in seen[0].system_message.content[-1]["text"]


def test_finalization_rejects_a_provider_tool_call_without_synthetic_messages():
    run_id = str(uuid4())
    request = _model_request(run_id, model_requests_used=63)
    called = []

    def handler(projected):
        called.append(projected)
        return ModelResponse(result=[AIMessage(
            content="不應再呼叫工具",
            tool_calls=[{"name": "jd_read", "args": {}, "id": "unexpected", "type": "tool_call"}],
        )])

    with pytest.raises(ConsultantExecutionError, match="^invalid_final_response$"):
        ConsultantExecutionMiddleware().wrap_model_call(request, handler)
    assert len(called) == 1


def test_early_public_answer_does_not_create_an_extra_request():
    run_id = str(uuid4())
    request = _model_request(run_id, model_requests_used=0)
    seen = []

    def handler(projected):
        seen.append(projected)
        return ModelResponse(result=[AIMessage(content="已完成回答")])

    ConsultantExecutionMiddleware().wrap_model_call(request, handler)

    assert len(seen) == 1
    assert seen[0].tools == request.tools
    assert seen[0].tool_choice == request.tool_choice
    assert "不能再呼叫工具" not in seen[0].system_message.content[-1]["text"]


def test_finalization_preserves_all_already_assembled_context_blocks():
    run_id = str(uuid4())
    blocks = [
        {"type": "text", "text": "JD notice"},
        {"type": "text", "text": "source notice"},
        {"type": "text", "text": "Memory notice"},
        {"type": "text", "text": "Skills and background"},
        {"type": "text", "text": "compacted continuation"},
    ]
    request = _model_request(run_id, model_requests_used=63, system_blocks=blocks)
    seen = []

    def handler(projected):
        seen.append(projected)
        return ModelResponse(result=[AIMessage(content="整理目前成果與未完成事項")])

    ConsultantExecutionMiddleware().wrap_model_call(request, handler)

    final_text = "\n".join(block["text"] for block in seen[0].system_message.content)
    for expected in ("JD notice", "source notice", "Memory notice", "Skills and background",
                     "compacted continuation", "不能再呼叫工具"):
        assert expected in final_text


def test_finalization_does_not_mutate_canonical_messages_or_compaction_state():
    run_id = str(uuid4())
    request = _model_request(run_id, model_requests_used=63)
    before_messages = deepcopy(request.messages)
    before_state = deepcopy(request.state)
    before_system = deepcopy(request.system_message.content)

    ConsultantExecutionMiddleware().wrap_model_call(
        request, lambda projected: ModelResponse(result=[AIMessage(content="完成")]))

    assert request.messages == before_messages
    assert request.state == before_state
    assert request.system_message.content == before_system


def test_framework_limit_backstops_raise_without_artificial_messages():
    from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
    from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
    from langchain.agents.middleware.tool_call_limit import ToolCallLimitExceededError

    runtime = Runtime(context=None)
    with pytest.raises(ModelCallLimitExceededError):
        ModelCallLimitMiddleware(thread_limit=64, exit_behavior="error").before_model(
            {"thread_model_call_count": 64}, runtime)

    message = AIMessage(content="", tool_calls=[
        {"name": "jd_set_text", "args": {}, "id": "blocked", "type": "tool_call"}
    ])
    with pytest.raises(ToolCallLimitExceededError):
        ToolCallLimitMiddleware(thread_limit=63, exit_behavior="error").after_model(
            {"messages": [message], "thread_tool_call_count": {"__all__": 63}}, runtime)


def test_a_constants_are_64_and_63_without_changing_model_profile():
    assert MAX_MODEL_STEPS == 64
    assert MAX_TOOL_CALLS == 63
