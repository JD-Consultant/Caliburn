"""Diagnostic copies preserve original pairing without becoming execution authority."""

from copy import deepcopy

import pytest

from caliburn.diagnostics import projection
from caliburn.diagnostics.projection import collect_steps, redact, role_for_thread


def record(response=None, results=None, request=None, thread="a"):
    return {
        "thread_id": thread,
        "role": "job_consultant",
        "checkpoint_id": "cp1",
        "checkpoint_time": "2026-10-03T00:00:00Z",
        "source": "checkpoint",
        "values": {
            "request_snapshot": request or {"model": "luna", "input": ["original"]},
            "response_snapshot": response
            or {
                "id": "r1",
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "c1",
                        "name": "read_jd",
                        "arguments": "{}",
                    },
                    {
                        "type": "function_call",
                        "call_id": "c2",
                        "name": "read_jd",
                        "arguments": "{}",
                    },
                ],
            },
            "tool_results": results or [],
        },
    }


def test_retains_first_original_request_and_pairs_results_by_call_id():
    rows = [
        record(),
        record(
            results=[
                {"type": "function_call_output", "call_id": "c2", "output": ""},
                {"type": "function_call_output", "call_id": "c1", "output": "JD"},
            ],
            request={"input": ["later"]},
        ),
    ]
    steps = collect_steps(rows)
    assert len(steps) == 1
    assert steps[0]["request"]["input"] == ["original"]
    assert steps[0]["tool_results"] == {"c2": "", "c1": "JD"}


def test_missing_result_is_not_success_or_empty_output():
    assert collect_steps([record()])[0]["tool_results"] == {}


def test_same_response_id_in_different_threads_does_not_merge_stages():
    assert len(collect_steps([record(thread="stage1"), record(thread="stage2")])) == 2


def test_conflicting_result_rejects_export_instead_of_hiding_evidence():
    rows = [record(results=[{"call_id": "c1", "output": value}]) for value in ("one", "two")]
    with pytest.raises(ValueError, match="Conflicting"):
        collect_steps(rows)


def test_redaction_preserves_public_content_and_does_not_mutate_original():
    original = {
        "output": [{"encrypted_content": "opaque", "summary": [{"text": "公開摘要"}]}],
        "arguments": '{"api_key":"secret","target_title":"盤點"}',
        "authorization": "Bearer secret",
    }
    before = deepcopy(original)
    value = redact(original)
    assert value["output"][0]["encrypted_content"] == "[redacted]"
    assert value["output"][0]["summary"] == [{"text": "公開摘要"}]
    assert "secret" not in str(value)
    assert "盤點" in value["arguments"]
    assert original == before


def test_role_selection_excludes_capture_preparation_and_other_files():
    prefix = "00000000-0000-4000-8000-000000000001:00000000-0000-4000-8000-000000000002:"
    stage = ":stage:00000000-0000-4000-8000-000000000003:00000000-0000-4000-8000-000000000004"
    for role in ("job_consultant", "work_situation_analyst", "work_understanding_analyst"):
        thread = prefix + role + ":completed_work"
        assert role_for_thread(thread, prefix) == role
        assert role_for_thread(thread + stage, prefix) == role
        assert role_for_thread(thread + stage + ":context", prefix) is None
        assert role_for_thread(thread.replace("completed_work", "prepared_history"), prefix) is None
        assert role_for_thread("other:" + thread, prefix) is None


def test_request_without_response_remains_inspectable_after_failure_or_cancellation():
    saved = record(request={"model": "luna", "input": ["失敗前已保存的請求"]})
    saved["values"].update(request_id="request-1", response_snapshot={})

    steps = collect_steps([saved])

    assert len(steps) == 1
    assert steps[0]["request_id"] == "request-1"
    assert steps[0]["request"]["input"] == ["失敗前已保存的請求"]
    assert steps[0]["response"] is None
    assert steps[0]["response_state"] == "request_only"
    assert steps[0]["tool_results"] == {}


def test_request_only_is_merged_with_its_later_response_without_losing_original_input():
    request = record()
    request["values"].update(request_id="request-1", response_snapshot={})
    response = record(request={"input": ["later"]})
    response["values"]["request_id"] = "request-1"
    response["checkpoint_id"] = "cp2"
    next_request = record()
    next_request["values"].update(request_id="request-2", response_snapshot={})

    steps = collect_steps([request, response, next_request])

    assert len(steps) == 2
    assert steps[0]["request"]["input"] == ["original"]
    assert steps[0]["response"]["id"] == "r1"
    assert steps[0]["response_state"] == "recorded"
    assert steps[0]["checkpoint_id"] == "cp1"
    assert steps[0]["response_checkpoint_id"] == "cp2"
    assert steps[1]["response_state"] == "request_only"


def test_initial_context_is_separate_from_model_requests_and_preserves_original_binding():
    captured = record(thread="a:job_consultant:initial_context")
    captured["values"] = {
        "request_snapshot": {"input": ["當時導覽"], "api_key": "secret"},
        "binding": {"snapshot_id": "old-memory", "plan_base_revision_id": "old-plan"},
    }
    subsequent_step = record()
    records = [captured, subsequent_step]

    assert len(collect_steps(records)) == 1
    original = projection.collect_initial_context(records)

    assert original["binding"] == captured["values"]["binding"]
    assert original["request"]["input"] == ["當時導覽"]
    assert original["request"]["api_key"] == "[redacted]"
    assert "tool_results" not in original
    assert original["thread_id"].endswith(":initial_context")


def test_initial_context_keeps_actual_tool_configuration_and_rejects_conflicting_copies():
    captured = record(thread="a:job_consultant:initial_context")
    captured["values"].update(binding={"snapshot_id": "old"}, jd_read_max_result_characters=50)
    original = projection.collect_initial_context([captured])
    assert original["tool_configuration"] == {"jd_read_max_result_characters": 50}
    conflicting = deepcopy(captured)
    conflicting["values"]["jd_read_max_result_characters"] = 60
    with pytest.raises(ValueError, match="Conflicting"):
        projection.collect_initial_context([captured, conflicting])
