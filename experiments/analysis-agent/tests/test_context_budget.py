"""CT-01: actual LangChain/SDK serialization; both networks are synthetic."""
from contextlib import contextmanager
from copy import deepcopy
import importlib.util
import json

import httpx
import pytest
from langchain_core.exceptions import ContextOverflowError, ModelError, ModelInvalidRequestError
from langchain_core.messages import ToolMessage
from langgraph.store.memory import InMemoryStore
from openai import OpenAI, OpenAIError

from analysis_agent.provider import build_model
from test_consolidation import call, done
from test_extraction import body
from test_service import service_harness


# Independent documented SDK3.8 whitelist; do not derive expectations from guard.
COUNT_FIELDS = {'conversation', 'input', 'instructions', 'model', 'parallel_tool_calls',
                'personality', 'previous_response_id', 'reasoning', 'text', 'tool_choice',
                'tools', 'truncation'}


def budget_module():
    assert importlib.util.find_spec('analysis_agent.budget'), 'Missing serialized Responses budget guard'
    from analysis_agent import budget
    return budget


@contextmanager
def counter_for(model, *, capacity=10000, count=100, respond=None, exact_count=True):
    """Attach real request hook to an existing synthetic generation transport."""
    budget = budget_module()
    counted = []
    def transport(request):
        assert str(request.url) == str(model.root_client.base_url.join('responses/input_tokens'))
        counted.append(json.loads(request.content))
        return respond(request) if respond else httpx.Response(200, json={'input_tokens': count})
    with httpx.Client(transport=httpx.MockTransport(transport), timeout=7) as http:
        with OpenAI(api_key='offline', base_url=str(model.root_client.base_url),
                    http_client=http, timeout=7) as counter:
            guard = budget.ResponsesBudget(counter=counter, model=model.model_name,
                                           context_window_tokens=capacity, exact_count=exact_count)
            model.http_client.event_hooks['request'].append(guard)
            try:
                yield counted
            finally:
                model.http_client.event_hooks['request'].remove(guard)


def assert_counted(counted, requests):
    assert len(counted) == len(requests) > 0
    for count, request in zip(counted, requests, strict=True):
        actual = json.loads(request.content)
        assert count == {k: v for k, v in actual.items() if k in COUNT_FIELDS}
        assert count['truncation'] == 'disabled'
        assert 'max_output_tokens' not in count
        assert 'context_management' not in count


def test_provider_explicitly_disables_server_truncation():
    sent = []
    def respond(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=done())
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        build_model(model='gpt-5.6-luna', api_key='offline', http_client=client).invoke('case')
    assert sent[0].get('truncation') == 'disabled'


@pytest.mark.parametrize('count,allowed', [(99, True), (100, True), (101, False)])
def test_final_output_reserved_exactly_once_and_local_reject_never_retries(count, allowed):
    sent = []
    def respond(request):
        sent.append(request)
        return httpx.Response(200, json=done())
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=client)
        model = model.model_copy(update={'max_tokens': 90})
        # Installed LC normalizes model.max_tokens=90 over the call's 30.
        # Budget must use serialized 90, not guess from invocation kwargs.
        with counter_for(model, capacity=190, count=count) as counted:
            if allowed:
                model.invoke('case', max_output_tokens=30)
                assert_counted(counted, sent)
                assert json.loads(sent[0].content)['max_output_tokens'] == 90
            else:
                with pytest.raises(ContextOverflowError) as caught:
                    model.invoke('case', max_output_tokens=30)
                assert type(caught.value) is budget_module().RequestBudgetExceeded
                assert isinstance(caught.value, OpenAIError) and not caught.value.is_retryable
                assert len(counted) == 1 and not sent


@pytest.mark.parametrize('override', [
    {'model': 'other-model'}, {'max_output_tokens': None}, {'max_output_tokens': 0},
    {'max_output_tokens': -1}, {'max_output_tokens': True}, {'max_output_tokens': 1.5},
    {'truncation': 'auto'}, {'prompt': {'id': 'pmpt_remote'}},
    {'extra_body': {'unaccounted_content': 'cannot silently omit'}},
    {'extra_query': {'unaccounted': 'cannot bypass endpoint guard'}},
])
def test_unsupported_request_fails_closed_without_count_or_generation(override):
    sent = []
    with httpx.Client(transport=httpx.MockTransport(lambda r: sent.append(r))) as client:
        model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=client)
        with counter_for(model) as counted:
            with pytest.raises(ModelInvalidRequestError) as caught:
                model.invoke('case', **({'max_output_tokens': 30} | override))
            assert isinstance(caught.value, OpenAIError) and not caught.value.is_retryable
            assert not counted and not sent


@pytest.mark.parametrize('count', [-1, True, 1.5, '100', None])
def test_invalid_counter_schema_fails_closed(count):
    with httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail('generation sent'))) as client:
        model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=client)
        with counter_for(model, count=count) as counted:
            with pytest.raises(ModelInvalidRequestError):
                model.invoke('case', max_output_tokens=30)
            assert len(counted) == 1


@pytest.mark.parametrize('response', [
    httpx.Response(200, json={}), httpx.Response(200, json=[]),
    httpx.Response(200, content=b'not JSON', headers={'content-type': 'application/json'}),
    pytest.param(httpx.Response(200, content=b'{"input_tokens": "\xff"}',
                               headers={'content-type': 'application/json'}), id='invalid-utf8'),
    httpx.Response(200, json={'input_tokens': 0}),
])
def test_incomplete_counter_response_is_nonretryable_configuration_error(response):
    with httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail('generation sent'))) as client:
        model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=client)
        with counter_for(model, respond=lambda r: response) as counted:
            with pytest.raises(ModelError) as caught:
                model.invoke('nonempty input', max_output_tokens=30)
            assert (len(counted), caught.value.is_retryable,
                    isinstance(caught.value, ModelInvalidRequestError)) == (1, False, True)


def test_strict_endpoint_and_zero_for_empty_input_preserve_exact_serialized_bytes():
    budget = budget_module()
    counted, sent = [], []
    def count(request):
        counted.append(json.loads(request.content))
        return httpx.Response(200, json={'input_tokens': 0})
    def generate(request):
        sent.append(request.content)
        return httpx.Response(200, json={})
    with httpx.Client(transport=httpx.MockTransport(count)) as count_http:
        with OpenAI(api_key='offline', base_url='https://endpoint.invalid/custom/v1/',
                    http_client=count_http) as counter:
            guard = budget.ResponsesBudget(counter=counter, model='configured', context_window_tokens=130, exact_count=True)
            with httpx.Client(transport=httpx.MockTransport(generate), event_hooks={'request': [guard]}) as client:
                for method, url in [
                    ('GET', 'https://endpoint.invalid/custom/v1/responses'),
                    ('POST', 'http://endpoint.invalid/custom/v1/responses'),
                    ('POST', 'https://endpoint.invalid:444/custom/v1/responses'),
                    ('POST', 'https://other.invalid/custom/v1/responses'),
                    ('POST', 'https://endpoint.invalid/v1/responses'),
                    ('POST', 'https://endpoint.invalid/custom/v1/responses/'),
                    ('POST', 'https://endpoint.invalid/custom/v1/responses/input_tokens'),
                ]:
                    client.request(method, url, json={'not': 'a generation request'})
                assert not counted
                raw = b'{"model":"configured", "input": [], "max_output_tokens":130, "truncation":"disabled"}'
                client.post('https://endpoint.invalid/custom/v1/responses', content=raw)
                assert counted == [{'model': 'configured', 'input': [], 'truncation': 'disabled'}]
                assert sent[-1] == raw


@pytest.mark.parametrize('base_url', [
    'https://endpoint.invalid/v1/?deployment=other', 'https://endpoint.invalid/v1/#fragment',
])
def test_ambiguous_base_url_is_rejected_before_hook_can_be_bypassed(base_url):
    budget = budget_module()
    with httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail('network'))) as http:
        with OpenAI(api_key='offline', base_url=base_url, http_client=http) as counter:
            with pytest.raises(ModelInvalidRequestError):
                budget.ResponsesBudget(counter=counter, model='configured', context_window_tokens=130)


@pytest.mark.parametrize('capacity', [None, 0, -1, True, 1.5, '130'])
def test_hook_invalid_capacity_cannot_escape_as_retryable_transport_error(capacity):
    budget = budget_module()
    with httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail('network'))) as http:
        with OpenAI(api_key='offline', http_client=http) as counter:
            with pytest.raises(ModelInvalidRequestError) as caught:
                budget.ResponsesBudget(counter=counter, model='configured', context_window_tokens=capacity)
            assert isinstance(caught.value, OpenAIError) and not caught.value.is_retryable


@pytest.mark.parametrize('status', [400, 404, 500, 'timeout'])
def test_counter_failure_uses_only_sdk_retries_never_generates(status):
    def failed(request):
        if status == 'timeout':
            raise httpx.ReadTimeout('synthetic', request=request)
        return httpx.Response(status, json={'error': {'message': 'unsupported or unavailable',
                                                     'type': 'invalid_request_error'}})
    with httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail('generation sent'))) as client:
        model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=client)
        with counter_for(model, respond=failed) as counted:
            with pytest.raises(ModelError) as caught:
                model.invoke('case', max_output_tokens=30)
            assert caught.value.is_retryable == (status in (500, 'timeout'))
            assert len(counted) == (3 if status in (500, 'timeout') else 1)


@pytest.mark.parametrize('exact', [False, True])
def test_a_each_call_includes_skills_memory_guide_results_and_preserves_canonical(tmp_path, exact):
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        service.model = service.model.model_copy(update={'max_tokens': 30})
        with counter_for(service.model, exact_count=exact) as counted:
            doc = service.create_document('budget A')['id']
            context = service._context(doc)
            context.memory.publication.setup()
            replies.append(done())
            old = service.submit(doc, 'old', '舊案例完整原文。')
            service.join(doc)
            before = deepcopy(context.graph.get_state(context.config).values['messages'])
            ref = service.reader(doc).capture(old['id'], before[-1].id)
            pub = context.memory.publication
            memory = context.memory.artifacts.save_memory(knowledge='主管核准', guide='導覽：/memory/knowledge.md')
            pub.publish(pub.prepare(memory, expected_revision=0, kind='consolidation', processed_source=ref))
            response = call('read_file', file_path='/skills/work-scope-interview/SKILL.md')
            response['output'][0:0] = [
                {'type': 'reasoning', 'id': 'rs_old', 'summary': [], 'encrypted_content': 'opaque-old'},
                {'type': 'compaction', 'id': 'cmp', 'encrypted_content': 'opaque-compaction'},
                {'type': 'reasoning', 'id': 'rs_new', 'summary': [], 'encrypted_content': 'opaque-new'},
            ]
            replies.extend([response, call('read_file', file_path='/memory/knowledge.md'), done()])
            run = service.submit(doc, 'new', '現在案例不同。')
            service.join(doc)
            assert service.get_run(doc, run['id'])['status'] == 'completed'
            if exact:
                assert_counted(counted, sent)
            else:
                assert counted == []
            payloads = [json.loads(request.content) for request in sent]
            assert len(payloads) == 4
            full = json.dumps(payloads[1], ensure_ascii=False)
            assert '舊案例完整原文。' in full and '現在案例不同。' in full and '導覽：' in full
            assert '/skills/work-scope-interview/SKILL.md' in full
            assert '# 工作範圍與案例訪談' in json.dumps(payloads[2], ensure_ascii=False)
            assert '主管核准' in json.dumps(payloads[3], ensure_ascii=False)
            opaque = [i for i in payloads[2]['input'] if i.get('type') in ('reasoning', 'compaction')]
            assert [i['encrypted_content'] for i in opaque] == ['opaque-compaction', 'opaque-new']
            saved = context.graph.get_state(context.config).values['messages']
            assert saved[:len(before)] == before
            assert 'opaque-old' in repr(saved) and 'opaque-compaction' in repr(saved)
            assert sum(isinstance(m, ToolMessage) for m in saved) == 2


@pytest.mark.parametrize('after_read', [False, True])
def test_a_budget_error_closes_unlocks_and_is_not_resumable(tmp_path, after_read):
    from analysis_agent.service import ServiceConflict
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        service.model = service.model.model_copy(update={'max_tokens': 30})
        def respond(request):
            return httpx.Response(200, json={'input_tokens': 100 if after_read and not sent else 101})
        with counter_for(service.model, capacity=130, respond=respond) as counted:
            doc = service.create_document('budget close')['id']
            context = service._context(doc)
            context.memory.publication.setup()
            replies.append(call('read_file', file_path='/skills/work-scope-interview/SKILL.md'))
            run = service.submit(doc, 'one', '原文只接受一次')
            service.join(doc)
            result = service.get_run(doc, run['id'])
            assert result['status'] == 'configuration_error'
            assert result['error_code'] == 'context_budget_exceeded'
            assert not result['can_resume'] and not result['usage_complete']
            assert not context.graph.get_state(context.config).next
            with pytest.raises(ServiceConflict):
                service.resume(doc, run['id'])
            assert service.submit(doc, 'one', '原文只接受一次')['id'] == run['id']
            assert len(counted) == (2 if after_read else 1)
            assert len(sent) == int(after_read)
            assert len([m for m in service.messages(doc) if m['role'] == 'user']) == 1
            # Unlock allows explicit NEW input, not silent canonical deletion/retry.
            service.submit(doc, 'two', '新輸入仍可能超限')
            service.join(doc)
            assert len([m for m in service.messages(doc) if m['role'] == 'user']) == 2


@pytest.mark.parametrize('exact', [False, True])
def test_b1_schema_and_b2_read_loop_actual_payload(tmp_path, exact):
    from analysis_agent.consolidation import ConsolidationWorkflow
    from analysis_agent.extraction import ExtractionWorkflow
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        service.model = service.model.model_copy(update={'max_tokens': 30})
        with counter_for(service.model, exact_count=exact) as counted:
            doc = service.create_document('background payload')['id']
            context = service._context(doc)
            context.memory.publication.setup()
            replies.append(done())
            run = service.submit(doc, 'a', '網站案例要無障礙。')
            service.join(doc)
            saved = context.graph.get_state(context.config).values['messages']
            ref = service.reader(doc).capture(run['id'], saved[-1].id)
            b1 = ExtractionWorkflow(service.reader(doc), context.memory.artifacts, service.model, service.saver)
            replies.append(body())
            extracted = b1.start(ref)
            path = extracted['files'][0]['summary_path']
            replies.extend([call('read_file', file_path='/interviews/missing/summary.md'),
                call('read_file', file_path=path),
                call('write_file', file_path='/memory/knowledge.md', content='網站工作：'+path),
                call('write_file', file_path='/memory/guide.md', content='網站：/memory/knowledge.md'),
                call('validate_memory'), done()])
            b2 = ConsolidationWorkflow(b1, context.memory.publication, service.model, service.saver)
            b2.start()
            assert context.memory.publication.current().revision == 1
            if exact:
                assert_counted(counted, sent)
            else:
                assert counted == []
            payloads = [json.loads(request.content) for request in sent]
            assert payloads[1]['text']['format']['type'] == 'json_schema'
            assert payloads[1]['text']['format']['strict'] is True
            assert not payloads[1].get('tools')
            assert {t['name'] for t in payloads[2]['tools']} == {
                'ls', 'grep', 'read_file', 'write_file', 'edit_file', 'validate_memory'}
            assert any(i.get('type') == 'function_call_output' and 'Error' in i['output']
                       for i in payloads[3]['input'])
            assert 'A網站：單次付款' in json.dumps(payloads[4], ensure_ascii=False)
            assert context.graph.get_state(context.config).values['messages'] == saved


@pytest.mark.parametrize('stage', ['b1', 'b2'])
def test_background_budget_blocks_without_repeat_per_tick(tmp_path, stage):
    from test_scheduling import notify
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        service.model = service.model.model_copy(update={'max_tokens': 30})
        doc = service.create_document('blocked B')['id']
        service._context(doc).memory.publication.setup()
        service.enable_background(max_recoveries=1)
        notify(service, doc, replies)
        sent.clear()
        def respond(request):
            return httpx.Response(200, json={'input_tokens': 100 if stage == 'b2' and not sent else 9999})
        with counter_for(service.model, capacity=5000, respond=respond) as counted:
            replies.append(body())
            assert service.background.tick()
            assert service.background.status(doc)['status'] == 'blocked'
            assert service.background.status(doc)['error_code'] == 'context_budget_exceeded'
            attempts = len(counted)
            assert attempts == (2 if stage == 'b2' else 1)
            for _ in range(3):
                assert not service.background.tick()
            assert len(counted) == attempts and len(sent) == int(stage == 'b2')


@pytest.mark.parametrize('fault,code,status,resumable', [
    ('overflow', 'context_budget_exceeded', 'configuration_error', False),
    ('schema', 'configuration_error', 'configuration_error', False),
    ('utf8', 'configuration_error', 'configuration_error', False),
    ('timeout', 'transport_error', 'interrupted', True),
])
def test_api_surfaces_safe_counter_failure_without_generation(tmp_path, fault, code, status, resumable):
    from fastapi.testclient import TestClient
    from analysis_agent.api import create_app
    observed = {}
    def failed(request):
        if fault == 'timeout':
            raise httpx.ReadTimeout('PRIVATE transport diagnostic', request=request)
        if fault == 'utf8':
            return httpx.Response(200, content=b'{"input_tokens": "\xff"}',
                                  headers={'content-type': 'application/json'})
        return httpx.Response(200, json={'input_tokens': 101} if fault == 'overflow' else {})
    @contextmanager
    def resources():
        with service_harness(tmp_path) as (service, sent, _):
            service.model = service.model.model_copy(update={'max_tokens': 30})
            with counter_for(service.model, capacity=130, respond=failed) as counted:
                observed.update(service=service, sent=sent, counted=counted)
                yield service
    with TestClient(create_app(resources), base_url='http://localhost') as web:
        doc = web.post('/documents', json={'title': 'safe budget error'}).json()['id']
        run = web.post(f'/documents/{doc}/runs', json={'request_key': 'one', 'text': 'original case'}).json()
        observed['service'].join(doc)
        response = web.get(f'/documents/{doc}/runs/{run["id"]}')
        assert response.json()['status'] == status
        assert response.json()['error_code'] == code
        assert response.json()['can_resume'] is resumable
        assert 'PRIVATE' not in response.text and 'original case' not in response.text
        assert not observed['sent']
        assert len(observed['counted']) == (3 if fault == 'timeout' else 1)
        if not resumable:
            context = observed['service']._context(doc)
            assert not context.graph.get_state(context.config).next
            assert web.post(f'/documents/{doc}/runs/{run["id"]}/resume').status_code == 409
            assert web.get(f'/documents/{doc}/messages').json() == [
                {'id': run['id'], 'role': 'user', 'text': 'original case'}]


@pytest.mark.parametrize('capacity', [None, '', '0', '-1', 'abc', '30', '129'])
def test_real_api_requires_consistent_explicit_capacity_before_resources(monkeypatch, capacity):
    from analysis_agent.api import open_service
    import sqlalchemy
    settings = {'Q019_DATABASE_URL': 'host=127.0.0.1 dbname=q019_fake', 'OPENAI_API_KEY': 'offline',
        'Q019_REQUEST_TIMEOUT_SECONDS': '7', 'Q019_MAX_OUTPUT_TOKENS': '30',
        'Q019_COMPACT_THRESHOLD': '100', 'Q019_BACKGROUND_POLL_SECONDS': '60',
        'Q019_BACKGROUND_MAX_RECOVERIES': '1'}
    for key, value in settings.items():
        monkeypatch.setenv(key, value)
    if capacity is None:
        monkeypatch.delenv('Q019_CONTEXT_WINDOW_TOKENS', raising=False)
    else:
        monkeypatch.setenv('Q019_CONTEXT_WINDOW_TOKENS', capacity)
    monkeypatch.setattr(sqlalchemy, 'create_engine', lambda *a, **k: pytest.fail('opened resources before budget validation'))
    with pytest.raises((RuntimeError, ValueError)):
        with open_service():
            pytest.fail('invalid configuration launched')
