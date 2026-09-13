"""Chat admission uses real native persistence and managed Futures, no provider."""

from threading import Event
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from jd_relational.ai_runtime import AiRuntime, AiRuntimeError, _verify_saved_results, _not_executed
from jd_relational.reads import read_json
from jd_relational.manual_runtime import RuntimeFailure
from test_ai_runtime import make_runtime, _receipt_fixture


def test_stale_new_request_does_not_save_input_or_invoke_model(make_runtime):
    make, _ = make_runtime
    runtime, graph, calls = make()
    document = str(uuid4())
    with pytest.raises(RuntimeFailure, match="^stale_view$"):
        runtime.start(document, str(uuid4()), "員工尚未送出的原話", expected_revision_id=uuid4())
    assert calls == []
    assert graph.get_state({"configurable": {"thread_id": document}}).values == {}


def test_original_request_returns_before_new_head_check_and_conflicting_base_rejects(make_runtime):
    make, _ = make_runtime
    runtime, _, calls = make()
    document, run = str(uuid4()), str(uuid4())
    base = runtime.owner.storage.read_current(document).revision_id
    handle = runtime.start(document, run, "原話", expected_revision_id=base)
    assert handle.wait(5).status == "completed"
    runtime.owner.storage.revision_id = uuid4()
    assert runtime.start(document, run, "原話", expected_revision_id=base) is handle
    with pytest.raises(AiRuntimeError, match="^operation_conflict$"):
        runtime.start(document, run, "原話", expected_revision_id=runtime.owner.storage.revision_id)
    assert calls == [run]


def test_older_run_lookup_and_retry_do_not_replay_after_a_newer_turn(make_runtime):
    make, _ = make_runtime
    runtime, graph, calls = make()
    document, first, second = str(uuid4()), str(uuid4()), str(uuid4())
    base = runtime.owner.storage.read_current(document).revision_id
    result = runtime.start(document, first, "第一輪\r\n  保留😀", expected_revision_id=base).wait(5)
    runtime.start(document, second, "第二輪", expected_revision_id=base).wait(5)
    before = graph.get_state({"configurable": {"thread_id": document}})
    assert runtime.lookup(document, first).wait(0) == result
    assert runtime.start(document, first, "第一輪\r\n  保留😀", expected_revision_id=base).wait(0) == result
    assert graph.get_state(before.config) == before
    assert calls == [first, second]


def test_lookup_during_live_ai_is_read_only_and_unknown_lookup_does_not_start(make_runtime):
    make, releases = make_runtime
    entered, release = Event(), Event()
    releases.append(release)
    def work(state):
        entered.set()
        assert release.wait(5)
        return {}
    runtime, _, calls = make(work)
    document, run = str(uuid4()), str(uuid4())
    handle = runtime.start(document, run, "尚在執行", expected_revision_id=runtime.owner.storage.read_current(document).revision_id)
    assert entered.wait(2)
    assert runtime.lookup(document, run) is handle
    assert runtime.lookup(document, str(uuid4())) is None
    assert calls == [run] and runtime.owner.status(document).write_blocked
    release.set()
    handle.wait(5)


def test_actual_run_rechecks_admitted_head_before_saving_input(make_runtime):
    make, _ = make_runtime
    runtime, graph, calls = make()
    document = str(uuid4())
    base = runtime.owner.storage.read_current(document).revision_id
    def real_run(attempt, permit):
        # Simulate an external storage change outside the local owner.
        runtime.owner.storage.revision_id = uuid4()
        return AiRuntime._run(runtime, attempt, permit)
    runtime._run = real_run
    result = runtime.start(document, str(uuid4()), "未保存原話", expected_revision_id=base).wait(5)
    assert result.status == "failed" and result.input_saved is False
    assert calls == []
    assert not any(isinstance(m, HumanMessage) for m in graph.get_state(
        {"configurable": {"thread_id": document}}).values.get("messages", []))


@pytest.mark.parametrize("value", [None, 1, True, "", "not-a-uuid"])
def test_lookup_invalid_identity_is_a_fixed_input_error(make_runtime, value):
    make, _ = make_runtime
    runtime, _, _ = make()
    with pytest.raises(AiRuntimeError, match="^invalid_input$"):
        runtime.lookup(str(uuid4()), value)


def test_closed_owner_cannot_return_a_cached_start_or_lookup(make_runtime):
    make, _ = make_runtime
    runtime, _, _ = make()
    document, run = str(uuid4()), str(uuid4())
    base = runtime.owner.storage.read_current(document).revision_id
    runtime.start(document, run, "原話", expected_revision_id=base).wait(5)
    assert runtime.owner.close(timeout=2)
    with pytest.raises(RuntimeFailure, match="^runtime_closed$"):
        runtime.lookup(document, run)
    with pytest.raises(RuntimeFailure, match="^runtime_closed$"):
        runtime.start(document, run, "原話", expected_revision_id=base)


def test_current_turn_claimed_write_success_requires_original_binding_and_receipt():
    messages, _, _, codec = _receipt_fixture()
    run = str(uuid4())
    with pytest.raises(AiRuntimeError, match="^invalid_saved_tool_result$"):
        _verify_saved_results([HumanMessage(id=run, content="本輪"), *messages], (), {}, codec, run_id=run)


def test_prior_turn_success_does_not_need_a_binding_in_this_turn():
    previous, _, _, codec = _receipt_fixture()
    run = str(uuid4())
    current_call = AIMessage(id="unbound-call-message", content="", tool_calls=[
        {"id": "not-saved-call", "name": "jd_set_text", "args": {}}])
    error = ToolMessage(id="not-saved-result", tool_call_id="not-saved-call", name="jd_set_text",
                        content=read_json(_not_executed()), status="error")
    _verify_saved_results([HumanMessage(id=str(uuid4()), content="前輪"), *previous,
        HumanMessage(id=run, content="本輪"), current_call, error], (), {}, codec, run_id=run)
