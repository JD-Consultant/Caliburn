"""CT-02: real serialized requests, optional count, no real provider calls."""
from contextlib import contextmanager
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.exceptions import ModelInvalidRequestError
from openai import OpenAI

from analysis_agent.api import create_app, open_service
from analysis_agent.budget import ResponsesBudget
from analysis_agent.provider import build_model
from test_consolidation import done
from test_context_budget import counter_for
from test_service import service_harness


def test_provider_overflow_closes_turn_without_erasing_source_or_locking_next_input(tmp_path):
    with service_harness(tmp_path) as (service, sent, _):
        def overflow(request):
            sent.append(request)
            return httpx.Response(400, json={'error': {
                'message': 'Synthetic context overflow', 'type': 'invalid_request_error',
                'code': 'context_length_exceeded', 'param': 'input'}})
        # Replace only provider transport; keep the real SDK, hook and framework.
        with httpx.Client(transport=httpx.MockTransport(overflow)) as http:
            service.model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=http).model_copy(
                update={'max_tokens': 128})
            with counter_for(service.model, exact_count=False) as counted:
                doc = service.create_document('原生超限處理')['id']
                for key in ['one', 'two']:
                    run = service.submit(doc, key, '保留員工這段原話：' + key)
                    service.join(doc)
                    result = service.get_run(doc, run['id'])
                    assert result['status'] == 'configuration_error' and not result['can_resume']
                    assert not service._context(doc).graph.get_state(service._context(doc).config).next
                assert len(sent) == 2 and counted == []
                assert [m['text'] for m in service.messages(doc) if m['role'] == 'user'] == [
                    '保留員工這段原話：one', '保留員工這段原話：two']


def test_default_native_mode_generates_without_counting_or_mutating_payload():
    sent = []
    def respond(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=done())
    with httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail('count was called'))) as count_http:
        with OpenAI(api_key='offline', http_client=count_http) as counter:
            guard = ResponsesBudget(counter=counter, model='gpt-5.6-luna', context_window_tokens=10000)
            with httpx.Client(transport=httpx.MockTransport(respond), event_hooks={'request': [guard]}) as client:
                model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=client,
                                    compact_threshold=8000)
                result = model.invoke('我負責依客戶需求開發網站。', max_output_tokens=128,
                                      extra_body={'prompt_cache_options': {'mode': 'implicit'}})
    assert result.response_metadata['status'] == 'completed'
    assert len(sent) == 1
    assert sent[0]['input'] == [{'type': 'message', 'role': 'user', 'content': '我負責依客戶需求開發網站。'}]
    assert sent[0]['reasoning'] == {'effort': 'medium', 'context': 'all_turns'}
    assert sent[0]['context_management'] == [{'type': 'compaction', 'compact_threshold': 8000}]
    assert sent[0]['prompt_cache_options'] == {'mode': 'implicit'}
    assert sent[0]['max_output_tokens'] == 128
    assert sent[0]['store'] is False and sent[0]['truncation'] == 'disabled'


@pytest.mark.parametrize('override', [
    {'max_output_tokens': 0}, {'max_output_tokens': 10001}, {'max_output_tokens': True},
    {'truncation': 'auto'}, {'model': 'different'},
])
def test_native_mode_keeps_local_request_contract_errors_nonretryable(override):
    with httpx.Client(transport=httpx.MockTransport(lambda r: pytest.fail('generation was sent'))) as client:
        model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=client)
        with counter_for(model, exact_count=False) as counted:
            with pytest.raises(ModelInvalidRequestError) as error:
                model.invoke('原文不應被修改。', **({'max_output_tokens': 128} | override))
            assert not error.value.is_retryable and not counted


@pytest.mark.parametrize('value', [None, 0, 1, 'false'])
def test_count_mode_must_be_an_actual_boolean(value):
    with OpenAI(api_key='offline') as counter:
        with pytest.raises(ModelInvalidRequestError):
            ResponsesBudget(counter=counter, model='gpt-5.6-luna', context_window_tokens=10000,
                            exact_count=value)


@pytest.mark.parametrize('mode', ['', 'approximate', 'Native'])
def test_invalid_factory_mode_fails_before_opening_resources(monkeypatch, mode):
    import sqlalchemy
    settings = {'Q019_DATABASE_URL': 'host=127.0.0.1 dbname=q019_fake', 'OPENAI_API_KEY': 'offline',
        'Q019_REQUEST_TIMEOUT_SECONDS': '7', 'Q019_MAX_OUTPUT_TOKENS': '128',
        'Q019_CONTEXT_WINDOW_TOKENS': '10000', 'Q019_COMPACT_THRESHOLD': '8000',
        'Q019_BACKGROUND_POLL_SECONDS': '60', 'Q019_BACKGROUND_MAX_RECOVERIES': '1',
        'Q019_CONTEXT_BUDGET_MODE': mode}
    for key, value in settings.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(sqlalchemy, 'create_engine', lambda *a, **k: pytest.fail('opened DB'))
    with pytest.raises(ValueError, match='Q019_CONTEXT_BUDGET_MODE'):
        with open_service():
            pytest.fail('invalid configuration launched')


def test_native_api_two_turns_replay_reasoning_and_report_actual_usage(tmp_path):
    observed = {}
    @contextmanager
    def resources():
        with service_harness(tmp_path) as (service, sent, replies):
            service.model = service.model.model_copy(update={'max_tokens': 128})
            first = done()
            first['output'].insert(0, {'type': 'reasoning', 'id': 'synthetic_reasoning',
                                      'encrypted_content': 'SYNTHETIC-OPAQUE', 'summary': []})
            replies.extend([first, done()])
            with counter_for(service.model, exact_count=False) as counted:
                observed.update(service=service, sent=sent, counted=counted)
                yield service
    with TestClient(create_app(resources), base_url='http://localhost') as web:
        doc = web.post('/documents', json={'title': '網站接案訪談'}).json()['id']
        for key, text in [('one', '我接案做網站。'), ('two', '剛才補充，是企業形象網站。')]:
            run = web.post(f'/documents/{doc}/runs', json={'request_key': key, 'text': text}).json()
            observed['service'].join(doc)
            result = web.get(f'/documents/{doc}/runs/{run["id"]}').json()
            assert result['status'] == 'completed' and result['error_code'] is None
            assert result['usage_complete'] is True
            assert result['usage'] == {'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120}
        messages = web.get(f'/documents/{doc}/messages').json()
        assert [m['text'] for m in messages if m['role'] == 'user'] == [
            '我接案做網站。', '剛才補充，是企業形象網站。']
        assert 'SYNTHETIC-OPAQUE' not in json.dumps(messages)
    assert len(observed['sent']) == 2 and observed['counted'] == []
    payload = json.loads(observed['sent'][1].content)
    assert sum(i.get('encrypted_content') == 'SYNTHETIC-OPAQUE' for i in payload['input']) == 1
    assert sum(i.get('content') == '剛才補充，是企業形象網站。' for i in payload['input']) == 1
