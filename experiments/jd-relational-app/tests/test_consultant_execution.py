"""A consultant execution policy derived only from canonical saved messages."""

import json
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
import pytest

from jd_relational.consultant_execution import (
    ConsultantExecutionError,
    decide_consultant_execution,
)
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
