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
            "request_id": "00000000-0000-4000-8000-000000000001",
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
        ),
    ]
    steps = collect_steps(rows)
    assert len(steps) == 1
    assert steps[0]["request"]["input"] == ["original"]
    assert steps[0]["tool_results"] == {"c2": "", "c1": "JD"}


def test_missing_result_is_not_success_or_empty_output():
    assert collect_steps([record()])[0]["tool_results"] == {}


@pytest.mark.parametrize("namespace", ["", "NativePolicy.before_model:task"])
@pytest.mark.parametrize("response_saved", [False, True])
def test_saved_input_count_is_visible_before_parent_returns(namespace, response_saved):
    parent = record()
    parent["values"]["input_count"] = None
    if not response_saved:
        parent["values"]["response_snapshot"] = {}
    counted = deepcopy(parent)
    counted.update(checkpoint_ns=namespace, source="pending_write", task_id="count-task")
    counted["values"]["input_count"] = {"input_tokens": 321, "attempt_id": "count-attempt"}
    rows = [counted, parent]
    before = deepcopy(rows)

    steps = collect_steps(rows)

    assert len(steps) == 1
    assert steps[0]["input_count"] == {"input_tokens": 321, "attempt_id": "count-attempt"}
    assert rows == before


@pytest.mark.parametrize("missing", [True, False])
def test_unobserved_input_count_stays_null(missing):
    saved = record()
    if not missing:
        saved["values"]["input_count"] = None
    assert collect_steps([saved])[0]["input_count"] is None


@pytest.mark.parametrize("other", ["previous_request", "before_fit", "prepared_history"])
def test_input_count_from_another_request_or_history_cannot_fill_current_step(other):
    parent = record(thread="a:job_consultant:completed_work")
    child = deepcopy(parent)
    child["checkpoint_ns"] = "NativePolicy.before_model:task"
    child["values"]["input_count"] = {"input_tokens": 999, "attempt_id": "other-attempt"}
    if other == "prepared_history":
        child["thread_id"] = "a:job_consultant:prepared_history"
    else:
        child["values"]["request_id"] = other
    steps = collect_steps([child, parent])
    assert len(steps) == 1
    assert steps[0]["input_count"] is None


@pytest.mark.parametrize("field", ["input", "tools", "model"])
def test_count_with_matching_identity_but_different_snapshot_rejects_projection(field):
    parent = record()
    child = deepcopy(parent)
    child["checkpoint_ns"] = "NativePolicy.before_model:task"
    child["values"]["request_snapshot"][field] = "different"
    child["values"]["input_count"] = {"input_tokens": 321, "attempt_id": "count-attempt"}
    with pytest.raises(ValueError, match="original request"):
        collect_steps([parent, child])


@pytest.mark.parametrize("field,value", [("input_tokens", 322), ("attempt_id", "other-attempt")])
def test_conflicting_saved_count_rejects_projection(field, value):
    parent = record()
    parent["values"]["input_count"] = {"input_tokens": 321, "attempt_id": "count-attempt"}
    child = deepcopy(parent)
    child["checkpoint_ns"] = "NativePolicy.before_model:task"
    child["values"]["input_count"][field] = value
    with pytest.raises(ValueError, match="Conflicting saved input counts"):
        collect_steps([child, parent])


def test_subgraph_saved_result_remains_visible_without_parent_tool_completion():
    parent = record()
    child = {
        **parent,
        "checkpoint_ns": "tools:parent:execute:child",
        "source": "pending_write",
        "task_id": "execute",
        "values": {
            "request_id": parent["values"]["request_id"],
            "call": parent["values"]["response_snapshot"]["output"][0],
            "output": "",
        },
    }
    other_task = {
        **child,
        "task_id": "other",
        "values": {"request_id": "unrelated", "output": "wrong"},
    }
    steps = collect_steps([child, parent, other_task])
    assert len(steps) == 1
    assert steps[0]["tool_results"] == {"c1": ""}


def test_parent_tool_message_observation_pairs_only_the_current_native_call():
    saved = record()
    saved["values"]["messages"] = [
        {"type": "tool", "tool_call_id": "preceding", "content": "not this Step"},
        {"type": "tool", "tool_call_id": "c2", "content": "rejected"},
    ]
    assert collect_steps([saved])[0]["tool_results"] == {"c2": "rejected"}


@pytest.mark.parametrize(
    "suffix", ["prepared_history", "completed_work:compact:00000000-0000-4000-8000-000000000003"]
)
def test_compaction_threads_are_readable_but_are_not_model_steps(suffix):
    prefix = "00000000-0000-4000-8000-000000000001:00000000-0000-4000-8000-000000000002:"
    thread = prefix + "job_consultant:" + suffix
    assert role_for_thread(thread, prefix) == "job_consultant"
    assert collect_steps([record(thread=thread)]) == []


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
    stage = ":stage:00000000-0000-4000-8000-000000000004"
    for role in ("job_consultant", "work_situation_analyst", "work_understanding_analyst"):
        thread = prefix + role + ":completed_work"
        assert role_for_thread(thread, prefix) == role
        assert role_for_thread(thread + stage, prefix) == role
        assert role_for_thread(thread + stage + ":context", prefix) == (
            None if role == "job_consultant" else role
        )
        assert role_for_thread(thread.replace("completed_work", "prepared_history"), prefix) == role
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
    response = record()
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


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("capture_source", ["checkpoint", "pending_write"])
@pytest.mark.parametrize("bootstrap", [[], ["本輪 App 導覽", "Plan"]])
def test_initial_context_preserves_capture_before_native_history_preparation(
    reverse, capture_source, bootstrap
):
    current_input = {"role": "user", "content": '{"interview_sequence":4,"text":"本輪"}'}
    captured = record(
        thread="a:job_consultant:initial_context",
        request={"model": "luna", "tools": [], "input": [*bootstrap, current_input]},
    )
    captured["source"] = capture_source
    captured["values"].update(binding={"snapshot_id": "fixed-memory"})
    committed = deepcopy(captured)
    committed.update(checkpoint_id="cp2", source="checkpoint")
    prepared = deepcopy(committed)
    prepared["source"] = "pending_write"
    prepared["values"]["request_snapshot"]["input"] = [
        {"role": "user", "content": "先前 App 導覽與原生歷史"},
        *bootstrap,
        current_input,
    ]
    records = [captured, committed, prepared]
    if reverse:
        records.reverse()

    original = projection.collect_initial_context(records)

    assert original["request"] == captured["values"]["request_snapshot"]
    assert original["checkpoint_id"] == "cp1"
    assert original["source"] == capture_source
    assert collect_steps(records) == []  # Capture observations do not prove delivery.


@pytest.mark.parametrize("change", ["binding", "model", "tools", "input", "bootstrap"])
def test_initial_context_rejects_changes_beyond_native_history_prefix(change):
    captured = record(
        thread="a:job_consultant:initial_context",
        request={"model": "luna", "tools": [], "input": ["App 導覽", "本輪 input"]},
    )
    captured["values"]["binding"] = {"snapshot_id": "fixed-memory"}
    prepared = deepcopy(captured)
    prepared["checkpoint_id"] = "cp2"
    request = prepared["values"]["request_snapshot"]
    request["input"].insert(0, "原生歷史")
    if change == "binding":
        prepared["values"]["binding"]["snapshot_id"] = "different-memory"
    elif change == "model":
        request["model"] = "different-model"
    elif change == "tools":
        request["tools"] = [{"name": "different-tool"}]
    elif change == "input":
        request["input"][-1] = "另一輪 input"
    else:
        request["input"].remove("App 導覽")

    with pytest.raises(ValueError, match="Conflicting"):
        projection.collect_initial_context([prepared, captured])


def test_response_operation_seed_distinguishes_calls_without_saved_outputs():
    from uuid import uuid4, uuid5

    seed = uuid4()
    saved = record()
    saved["values"]["operation_seed"] = str(seed)
    step = collect_steps([saved])[0]
    assert step["metadata"]["operation_seed"] == str(seed)
    assert step["metadata"]["tool_operation_ids"] == {
        "c1": str(uuid5(seed, "c1")),
        "c2": str(uuid5(seed, "c2")),
    }
    assert step["tool_results"] == {}


def test_request_only_seed_cannot_be_used_for_a_different_response():
    from uuid import uuid4, uuid5

    before, response = record(), record()
    before["values"].update(request_id="same", response_snapshot={}, operation_seed=str(uuid4()))
    seed = uuid4()
    response["values"].update(request_id="same", operation_seed=str(seed))
    step = collect_steps([before, response])[0]
    assert step["metadata"]["tool_operation_ids"]["c1"] == str(uuid5(seed, "c1"))


def test_missing_operation_seed_is_explicitly_unknown():
    assert collect_steps([record()])[0]["metadata"] == {
        "operation_seed": None,
        "tool_operation_ids": {"c1": None, "c2": None},
    }


def test_conflicting_seed_for_same_response_rejects_projection():
    from uuid import uuid4

    first, second = record(), record()
    first["values"]["operation_seed"] = str(uuid4())
    second["values"]["operation_seed"] = str(uuid4())
    with pytest.raises(ValueError, match="Conflicting"):
        collect_steps([first, second])


def test_native_json_projection_allows_only_known_uuid_identity_channels():
    from uuid import UUID

    from caliburn.adapters.native_checkpoint_reads import _normalize

    value = UUID("00000000-0000-4000-8000-000000000001")
    assert _normalize(value, "operation_seed") == str(value)
    assert _normalize(value, "request_id") == str(value)
    with pytest.raises(ValueError, match="decode"):
        _normalize(value, "tool_results")
    with pytest.raises(ValueError, match="decode"):
        _normalize(b"not JSON", "request_snapshot")
    assert _normalize(None, "operation_seed") is None
