"""B1 integration: real graph/model adapter/Store, synthetic external HTTP only."""

import importlib.util
import json

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from analysis_agent.memory import MemoryArtifacts
from analysis_agent.provider import build_model
from analysis_agent.runtime import build_agent
from analysis_agent.sources import ConversationReader
from test_native_continuity import assistant_text, response_body


def workflow_class():
    assert importlib.util.find_spec("analysis_agent.extraction"), "Missing B1 extraction workflow"
    from analysis_agent.extraction import ExtractionWorkflow
    return ExtractionWorkflow


def source(model, saver, document="extract-doc", turns=None):
    turns = turns or [("A網站限單次付款，需無障礙。", "B網站有何不同？"), ("B是月租，要權限分級。", "兩個案例由誰驗收？")]
    graph = build_agent(model=model, checkpointer=saver, instructions="PRIVATE-SYSTEM")
    messages = []
    for i, (employee, advisor) in enumerate(turns):
        messages.extend([HumanMessage(employee, id=f"u{i}"), AIMessage([
            {"type": "reasoning", "encrypted_content": "PRIVATE-REASONING", "summary": []},
            {"type": "text", "text": advisor}], id=f"a{i}", response_metadata={"status": "completed"})])
    graph.update_state({"configurable": {"thread_id": document}}, {"messages": messages}, as_node="model")
    reader = ConversationReader(graph, document)
    return reader, reader.capture("u0", f"a{len(turns)-1}")


def body(raw_memory="共同做客製前端，兩案例計費與權限條件不同。"):
    return response_body([assistant_text(json.dumps({"rollout_summary": "A網站：單次付款、無障礙。\nB網站：月租、權限分級。\n驗收人尚未回答。", "raw_memory": raw_memory, "rollout_slug": "網站/案例"}, ensure_ascii=False))])


@pytest.fixture
def harness():
    sent, responses = [], []
    def respond(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=responses.pop(0) if responses else body())
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = build_model(model="gpt-5.6-luna", api_key="offline", http_client=client).model_copy(update={"max_retries": 0})
        saver, store = InMemorySaver(), InMemoryStore()
        reader, ref = source(model, saver)
        yield model, saver, store, reader, ref, sent, responses


def test_native_three_fields_to_artifacts_with_real_source_and_no_publication(harness):
    cls = workflow_class()
    model, saver, store, reader, ref, sent, _ = harness
    artifacts = MemoryArtifacts(store, reader.document_id)
    workflow = cls(reader, artifacts, model, saver)
    result = workflow.start(ref)
    assert len(result["files"]) == 1
    item = result["files"][0]
    saved = store.search(("q019-memory", reader.document_id, "interviews"))
    text = json.dumps([s.value for s in saved], ensure_ascii=False)
    assert "驗收人尚未回答" in text and "月租" in text
    assert item["source_reference"] in text
    assert len(saved) == 2
    assert store.search(("q019-memory", reader.document_id, "versions")) == []
    schema = sent[0]["text"]["format"]
    assert schema["strict"] is True
    assert sent[0]["max_output_tokens"] == 4096
    assert set(schema["schema"]["properties"]) == {"rollout_summary", "raw_memory", "rollout_slug"}
    assert not sent[0].get("tools")
    payload = json.dumps(sent[0], ensure_ascii=False)
    assert "A網站限單次付款" in payload and "B是月租" in payload
    assert "PRIVATE-REASONING" not in payload and "PRIVATE-SYSTEM" not in payload
    assert workflow.start(ref)["files"] == result["files"]
    assert len(sent) == 1
    assert reader.read(ref)["segments"][0]["text"] == "A網站限單次付款，需無障礙。"


def test_windows_cover_every_new_turn_once_with_separate_previous_context(harness):
    model, saver, _, _, _, _, _ = harness
    reader, ref = source(model, saver, turns=[("工作A"*5, "問A"), ("工作B"*5, "問B"), ("工作C"*5, "問C"), ("工作D"*5, "問D")])
    windows = reader.extraction_windows(ref, max_chars=38, context_chars=20)
    seen = []
    assert len(windows) == 3
    for window in windows:
        seen += [s["message_id"] for s in reader.read(window["source_reference"])["segments"]]
    assert seen == ["u0", "a0", "u1", "a1", "u2", "a2", "u3", "a3"]
    assert windows[0]["context_reference"] is None
    assert [s["message_id"] for s in reader.read(windows[1]["context_reference"])["segments"]] == ["u1", "a1"]


def test_later_extraction_failure_resumes_without_repeating_first_window(harness):
    cls = workflow_class()
    model, saver, store, _, _, sent, responses = harness
    reader, ref = source(model, saver, turns=[("案例A"*5, "問A"), ("案例B"*5, "問B"), ("案例C"*5, "問C")])
    malformed = response_body([assistant_text('{"rollout_summary":"missing"}')])
    responses.extend([body(), malformed, body()])
    workflow = cls(reader, MemoryArtifacts(store, reader.document_id), model, saver, max_chars=38, context_chars=20)
    with pytest.raises(ValueError):
        workflow.start(ref)
    first = workflow.graph.get_state(workflow.config).values["files"][0]
    result = workflow.resume()
    assert result["files"][0] == first and len(result["files"]) == 2
    assert len(sent) == 3
    payload = json.loads(sent[-1]["input"][-1]["content"])
    assert "案例B" in json.dumps(payload["CONTEXT_ONLY"], ensure_ascii=False)
    assert "案例C" in json.dumps(payload["NEW_SOURCE"], ensure_ascii=False)
    assert "案例A" not in json.dumps(payload["NEW_SOURCE"], ensure_ascii=False)
    assert len(store.search(("q019-memory", reader.document_id, "interviews"))) == 4


@pytest.mark.parametrize("case", ["oversize", "partial", "foreign", "unfinished"])
def test_invalid_source_stops_before_model(harness, case):
    cls = workflow_class()
    model, saver, store, reader, ref, sent, _ = harness
    kwargs = {}
    if case == "oversize":
        kwargs = {"max_chars": 5, "context_chars": 0}
    elif case == "partial":
        ref = reader.capture("a0", "a1")
    elif case == "foreign":
        other, ref = source(model, saver, document="other-doc")
    else:
        config = {"configurable": {"thread_id": reader.document_id}}
        reader.graph.update_state(config, {"messages": [HumanMessage("未回答", id="u2")]}, as_node="model")
        ref = reader.capture("u2", "u2")
    with pytest.raises(ValueError):
        cls(reader, MemoryArtifacts(store, reader.document_id), model, saver, **kwargs).start(ref)
    assert sent == [] and store.search(("q019-memory", reader.document_id)) == []


def test_oversize_batch_is_bounded_before_any_model_call(harness):
    cls = workflow_class()
    model, saver, store, _, _, sent, _ = harness
    reader, ref = source(model, saver, turns=[("工作"*8, "問")]*4)
    with pytest.raises(ValueError, match="windows"):
        cls(reader, MemoryArtifacts(store, reader.document_id), model, saver,
            max_chars=20, context_chars=1, max_windows=2).start(ref)
    assert sent == []


def test_rejected_source_plan_does_not_lock_out_a_smaller_valid_range(harness):
    cls = workflow_class()
    model, saver, store, reader, ref, sent, _ = harness
    workflow = cls(reader, MemoryArtifacts(store, reader.document_id), model, saver, max_chars=35, context_chars=0, max_windows=1)
    with pytest.raises(ValueError):
        workflow.start(ref)
    result = workflow.start(reader.capture("u0", "a0"))
    assert len(result["files"]) == 1 and len(sent) == 1


def test_empty_candidates_is_saved_success_not_a_failure(harness):
    cls = workflow_class()
    model, saver, store, reader, ref, sent, responses = harness
    responses.append(body(""))
    result = cls(reader, MemoryArtifacts(store, reader.document_id), model, saver).start(ref)
    assert len(result["files"]) == 1 and len(sent) == 1


def test_store_failure_resumes_saved_model_result_without_calling_model_again(harness):
    cls = workflow_class()
    model, saver, store, reader, ref, sent, _ = harness
    class FailedSave(MemoryArtifacts):
        def save_extraction(self, **kwargs):
            raise RuntimeError("storage unavailable")
    workflow = cls(reader, FailedSave(store, reader.document_id), model, saver)
    with pytest.raises(RuntimeError, match="storage unavailable"):
        workflow.start(ref)
    with pytest.raises(ValueError, match="pending"):
        workflow.start(ref)
    restored = cls(reader, MemoryArtifacts(store, reader.document_id), model, saver)
    result = restored.resume()
    assert len(result["files"]) == 1 and len(sent) == 1
    assert restored.resume()["files"] == result["files"]


@pytest.mark.parametrize("bad", ["refusal", "incomplete", "schema"])
def test_bad_model_outcomes_never_become_empty_success(harness, bad):
    cls = workflow_class()
    model, saver, store, reader, ref, sent, responses = harness
    response = body()
    if bad == "refusal":
        response["output"][0]["content"] = [{"type": "refusal", "refusal": "Cannot process"}]
    elif bad == "incomplete":
        response["status"] = "incomplete"
        response["incomplete_details"] = {"reason": "max_output_tokens"}
    else:
        response["output"][0]["content"][0]["text"] = '{"rollout_summary":"missing two fields"}'
    responses.append(response)
    with pytest.raises(ValueError):
        cls(reader, MemoryArtifacts(store, reader.document_id), model, saver).start(ref)
    assert store.search(("q019-memory", reader.document_id)) == []
    assert len(sent) == 1


def test_invalid_artifact_format_is_rejected_before_persisting_model_success(harness):
    cls = workflow_class()
    model, saver, store, reader, ref, sent, responses = harness
    response = body()
    response["output"][0]["content"][0]["text"] = json.dumps({"rollout_summary": "甲" * 2100, "raw_memory": "候選", "rollout_slug": "案例"}, ensure_ascii=False)
    responses.append(response)
    workflow = cls(reader, MemoryArtifacts(store, reader.document_id), model, saver)
    with pytest.raises(ValueError):
        workflow.start(ref)
    assert store.search(("q019-memory", reader.document_id)) == []
    # Caller explicitly resumes; a fresh valid extraction must be requested,
    # not an endless replay of an already-known invalid Store payload.
    result = workflow.resume()
    assert len(result["files"]) == 1 and len(sent) == 2


def test_incomplete_native_source_is_not_a_completed_extraction_window(harness):
    cls = workflow_class()
    model, saver, store, _, _, sent, responses = harness
    truncated = response_body([assistant_text("請說明驗收的")])
    truncated["status"] = "incomplete"
    truncated["incomplete_details"] = {"reason": "max_output_tokens"}
    responses.append(truncated)
    graph = build_agent(model=model, checkpointer=saver, instructions="顧問")
    config = {"configurable": {"thread_id": "incomplete-source"}}
    result = graph.invoke({"messages": [HumanMessage("A案由客戶驗收。", id="u0")]}, config, durability="sync")
    assert graph.get_state(config).next == ()
    assert result["messages"][-1].response_metadata["status"] == "incomplete"
    reader = ConversationReader(graph, "incomplete-source")
    ref = reader.capture("u0", result["messages"][-1].id)
    with pytest.raises(ValueError, match="completed"):
        cls(reader, MemoryArtifacts(store, reader.document_id), model, saver).start(ref)
    assert len(sent) == 1  # Only the main Agent, never the B1 model.
    assert store.search(("q019-memory", reader.document_id)) == []


def test_source_without_completion_metadata_is_not_assumed_completed(harness):
    cls = workflow_class()
    model, saver, store, reader, ref, sent, _ = harness
    config = {"configurable": {"thread_id": reader.document_id}}
    reader.graph.update_state(config, {"messages": [AIMessage("未知是否完整", id="a1")]}, as_node="model")
    ref = reader.capture("u0", "a1")
    with pytest.raises(ValueError, match="completed"):
        cls(reader, MemoryArtifacts(store, reader.document_id), model, saver).start(ref)
    assert sent == []


@pytest.mark.parametrize("appended", [False, True])
def test_old_source_after_another_completed_job_is_rejected_without_reextracting(harness, appended):
    cls = workflow_class()
    model, saver, store, reader, _, sent, _ = harness
    if appended:
        reader, _ = source(model, saver, document="growing-source", turns=[("A案", "B案呢？")])
    x = reader.capture("u0", "a0")
    workflow = cls(reader, MemoryArtifacts(store, reader.document_id), model, saver)
    workflow.start(x)
    if appended:
        reader.graph.update_state({"configurable": {"thread_id": reader.document_id}}, {"messages": [
            HumanMessage("B案要月租", id="u1"),
            AIMessage("月租如何收？", id="a1", response_metadata={"status": "completed"})]}, as_node="model")
    y = reader.capture("u1", "a1")
    second = workflow.start(y)
    with pytest.raises(ValueError, match="source|range"):
        workflow.start(x)
    assert len(sent) == 2
    assert workflow.start(y)["files"] == second["files"]
    assert len(store.search(("q019-memory", reader.document_id, "interviews"))) == 4


def test_overlap_with_previously_extracted_source_is_rejected(harness):
    cls = workflow_class()
    model, saver, store, reader, whole, sent, _ = harness
    workflow = cls(reader, MemoryArtifacts(store, reader.document_id), model, saver)
    workflow.start(reader.capture("u0", "a0"))
    with pytest.raises(ValueError, match="source|range"):
        workflow.start(whole)
    assert len(sent) == 1
    # A rejected overlap does not block the legitimate next range.
    workflow.start(reader.capture("u1", "a1"))
    assert len(sent) == 2


def test_b1_receives_failed_turn_metadata_and_all_employee_text_not_error(harness):
    from analysis_agent.conversation import build_conversation
    import analysis_agent.conversation as conversation
    from langchain.agents.middleware import wrap_model_call
    model, saver, store, _, _, sent, responses = harness
    @wrap_model_call
    def fail(request, handler):
        raise RuntimeError('SECRET_TECHNICAL_ERROR')
    graph = build_conversation(model=model, checkpointer=saver, instructions='test', middleware=[fail])
    config = {'configurable': {'thread_id': 'failed-b1'}}
    graph.update_state(config, {'messages': [HumanMessage('案件細節', id='u0'),
        AIMessage('誰核准？', id='a0', response_metadata={'status': 'completed'})]}, as_node='analysis')
    employee = '甲' * 2000 + '中段特殊條件不能漏' + '乙' * 2000
    with pytest.raises(RuntimeError):
        graph.invoke({'messages': [HumanMessage(employee, id='u1')]}, config, durability='sync')
    assert hasattr(conversation, 'close_turn'), 'Missing failed source closure'
    closed = conversation.close_turn(graph, config, reason='configuration_error', quiescent=True)
    reader = ConversationReader(graph, 'failed-b1')
    ref = reader.capture('u1', closed['messages'][-1].id)
    responses.append(body())
    result = workflow_class()(reader, MemoryArtifacts(store, 'failed-b1'), model, saver).start(ref)
    assert len(result['files']) == 1 and len(sent) == 1
    payload = json.loads(sent[0]['input'][-1]['content'])
    assert payload['NEW_SOURCE']['turns'] == [
        {'input_id': 'u1', 'status': 'configuration_error', 'answer_succeeded': False}]
    assert ''.join(s['text'] for s in payload['NEW_SOURCE']['segments']) == employee
    assert payload['CONTEXT_ONLY']['segments'][-1]['text'] == '誰核准？'
    assert 'SECRET_TECHNICAL_ERROR' not in json.dumps(payload)


def test_b1_cannot_jump_over_unresolved_middle_turn(harness):
    model, saver, store, _, _, sent, _ = harness
    reader, _ = source(model, saver, turns=[('A案', '問A'), ('B案', '問B'), ('C案', '問C')])
    config = {'configurable': {'thread_id': reader.document_id}}
    reader.graph.update_state(config, {'messages': [AIMessage('未完成', id='a1')]}, as_node='model')
    workflow = workflow_class()(reader, MemoryArtifacts(store, reader.document_id), model, saver)
    workflow.start(reader.capture('u0', 'a0'))
    with pytest.raises(ValueError, match='completed|contiguous|source'):
        workflow.start(reader.capture('u2', 'a2'))
    assert len(sent) == 1


def failed_short_correction(harness, *, prior_notice=False, correction='不是，是處長'):
    """Real long prior turn + visible question, then a safely closed failure."""
    from langchain.agents.middleware import AgentMiddleware
    from analysis_agent.conversation import build_conversation, close_turn
    model, saver, _, _, _, _, responses = harness
    class ConfigurationFailure(AgentMiddleware):
        def wrap_model_call(self, request, handler):
            if request.messages[-1].id in {'short-correction', 'second-correction'}:
                raise RuntimeError('injected configuration failure')
            return handler(request)

        def after_model(self, state, runtime):
            if prior_notice:
                raise RuntimeError('injected failure after the visible question')
    graph = build_conversation(model=model, checkpointer=saver, instructions='test',
                               middleware=[ConfigurationFailure()])
    config = {'configurable': {'thread_id': 'r01-source'}}
    responses.append(response_body([assistant_text('是由主管核准嗎？')]))
    if prior_notice:
        with pytest.raises(RuntimeError, match='visible question'):
            graph.invoke({'messages': [HumanMessage('甲' * 1600, id='long-prior')]}, config, durability='sync')
        close_turn(graph, config, reason='configuration_error', quiescent=True)
    else:
        graph.invoke({'messages': [HumanMessage('甲' * 1600, id='long-prior')]}, config, durability='sync')
    with pytest.raises(RuntimeError, match='configuration failure'):
        graph.invoke({'messages': [HumanMessage(correction, id='short-correction')]}, config, durability='sync')
    result = close_turn(graph, config, reason='configuration_error', quiescent=True)
    reader = ConversationReader(graph, 'r01-source')
    return reader, reader.capture('short-correction', result['messages'][-1].id)


@pytest.mark.parametrize('prior_notice', [False, True])
def test_r01_b1_long_prior_keeps_short_question_for_failed_correction(harness, prior_notice):
    model, saver, store, _, _, sent, _ = harness
    reader, ref = failed_short_correction(harness, prior_notice=prior_notice)
    canonical = [m.model_dump() for m in reader.graph.get_state(
        {'configurable': {'thread_id': reader.document_id}}).values['messages']]
    result = workflow_class()(reader, MemoryArtifacts(store, reader.document_id), model, saver).start(ref)
    payload = json.loads(sent[-1]['input'][-1]['content'])
    assert payload['CONTEXT_ONLY'] is not None, 'Lost the necessary question after a long prior turn'
    assert payload['CONTEXT_ONLY']['segments'] == [{'role': 'assistant', 'text': '是由主管核准嗎？'}]
    assert payload['NEW_SOURCE']['segments'] == [{'role': 'user', 'text': '不是，是處長'}]
    assert payload['NEW_SOURCE']['turns'] == [
        {'input_id': 'short-correction', 'status': 'configuration_error', 'answer_succeeded': False}]
    context_ref = result['files'][0]['context_reference']
    assert reader.read(context_ref)['segments'][0]['role'] == 'assistant'
    assert reader.read(context_ref)['segments'][0]['text'] == '是由主管核准嗎？'
    assert [m.model_dump() for m in reader.graph.get_state(
        {'configurable': {'thread_id': reader.document_id}}).values['messages']] == canonical
    assert len(sent) == 2  # prior consultant + B1; the failed turn made no HTTP call


@pytest.mark.parametrize('max_chars,context_chars,accepted', [
    (6000, 7, False), (13, 8, False), (14, 8, True), (6000, 0, False),
])
def test_r01_required_question_respects_context_and_combined_budgets(harness, max_chars, context_chars, accepted):
    model, saver, store, _, _, sent, _ = harness
    reader, ref = failed_short_correction(harness)
    workflow = workflow_class()(reader, MemoryArtifacts(store, reader.document_id), model, saver,
                                max_chars=max_chars, context_chars=context_chars)
    if not accepted:
        with pytest.raises(ValueError, match='question.*budget'):
            workflow.start(ref)
        assert len(sent) == 1
        assert not workflow.graph.get_state(workflow.config).values
        assert store.search(('q019-memory', reader.document_id)) == []
    else:
        workflow.start(ref)
        payload = json.loads(sent[-1]['input'][-1]['content'])
        assert payload['CONTEXT_ONLY'] is not None
        assert sum(len(s['text']) for section in payload.values() for s in section['segments']) == 14
        assert len(sent) == 2


def close_second_correction(reader):
    from analysis_agent.conversation import close_turn
    config = {'configurable': {'thread_id': reader.document_id}}
    with pytest.raises(RuntimeError, match='configuration failure'):
        reader.graph.invoke({'messages': [HumanMessage('只限特殊案件', id='second-correction')]}, config, durability='sync')
    result = close_turn(reader.graph, config, reason='configuration_error', quiescent=True)
    return reader.capture('second-correction', result['messages'][-1].id)


@pytest.mark.parametrize('prior_notice', [False, True])
def test_r01_consecutive_failed_b1_payload_keeps_question_and_intervening_answer(harness, prior_notice):
    from analysis_agent.sources import parse_reference
    model, saver, store, _, _, sent, _ = harness
    reader, first_ref = failed_short_correction(harness, prior_notice=prior_notice)
    workflow = workflow_class()(reader, MemoryArtifacts(store, reader.document_id), model, saver,
                                max_chars=20, context_chars=14)
    workflow.start(first_ref)
    second_ref = close_second_correction(reader)
    config = {'configurable': {'thread_id': reader.document_id}}
    canonical = [m.model_dump() for m in reader.graph.get_state(config).values['messages']]
    result = workflow.start(second_ref)
    payload = json.loads(sent[-1]['input'][-1]['content'])
    assert payload['CONTEXT_ONLY']['segments'] == [
        {'role': 'assistant', 'text': '是由主管核准嗎？'},
        {'role': 'user', 'text': '不是，是處長'}]
    assert payload['NEW_SOURCE']['segments'] == [{'role': 'user', 'text': '只限特殊案件'}]
    assert payload['CONTEXT_ONLY']['turns'] == [
        {'input_id': 'short-correction', 'status': 'configuration_error', 'answer_succeeded': False}]
    assert payload['NEW_SOURCE']['turns'] == [
        {'input_id': 'second-correction', 'status': 'configuration_error', 'answer_succeeded': False}]
    context_ref = result['files'][0]['context_reference']
    assert parse_reference(context_ref, reader.document_id)['last'] == parse_reference(first_ref, reader.document_id)['last']
    assert reader.read(context_ref)['segments'][0]['role'] == 'assistant'
    assert 'runtime_notice' in reader.read(context_ref)['omitted_content_types']
    assert sum(len(s['text']) for section in payload.values() for s in section['segments']) == 20
    assert [m.model_dump() for m in reader.graph.get_state(config).values['messages']] == canonical
    assert len(sent) == 3  # one prior advisor + two requested B1 batches


@pytest.mark.parametrize('max_chars,context_chars,correction', [
    (6000, 13, '不是，是處長'),
    (19, 14, '不是，是處長'),
    (6000, 1500, '不是，是處長。' + '甲' * 1500),
], ids=['context-budget', 'total-budget', 'long-middle'])
def test_r01_consecutive_required_range_over_budget_rejects_before_b1(harness, max_chars, context_chars, correction):
    model, saver, store, _, _, sent, _ = harness
    reader, _ = failed_short_correction(harness, correction=correction)
    second_ref = close_second_correction(reader)
    workflow = workflow_class()(reader, MemoryArtifacts(store, reader.document_id), model, saver,
                                max_chars=max_chars, context_chars=context_chars)
    with pytest.raises(ValueError, match='question.*budget'):
        workflow.start(second_ref)
    assert len(sent) == 1
    assert not workflow.graph.get_state(workflow.config).values
    assert store.search(('q019-memory', reader.document_id)) == []
