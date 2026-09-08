"""Role-specific effort uses real SDK/graphs; only external HTTP is synthetic.

These assert wiring, not the semantic quality of canned model responses.
Live uncertainty-fidelity evidence is archived in CT37/CT38.
"""
import hashlib
import json

import httpx
import pytest
from langchain_core.messages import HumanMessage
from langgraph.store.memory import InMemoryStore

from analysis_agent.provider import build_model
from analysis_agent.publication import Base
from test_consolidation import done
from test_extraction import body
from test_scheduling import notify
from test_service import service_harness


@pytest.mark.parametrize('effort', ['medium', 'high'])
def test_provider_effort_survives_structured_output_binding(effort):
    from analysis_agent.extraction import ExtractionOutput
    sent = []

    def respond(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=body())

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = build_model(model='gpt-5.6-luna', api_key='offline', http_client=client,
                            reasoning_effort=effort, compact_threshold=10000)
        model.with_structured_output(ExtractionOutput.model_json_schema(),
            method='json_schema', strict=True, include_raw=True,
            max_output_tokens=4096).invoke([HumanMessage('離線抽取')])
    assert sent[0]['reasoning'] == {'effort': effort, 'context': 'all_turns'}
    assert sent[0]['text']['format']['strict'] is True
    assert sent[0]['max_output_tokens'] == 4096
    assert sent[0]['context_management'] == [{'type': 'compaction', 'compact_threshold': 10000}]
    assert sent[0]['store'] is False and sent[0]['truncation'] == 'disabled'


@pytest.mark.parametrize('separate', [False, True])
@pytest.mark.parametrize('output_limit', [1000, 6000])
def test_service_background_selects_high_only_for_extraction(tmp_path, separate, output_limit):
    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, replies):
        Base.metadata.create_all(service.catalog.engine)
        service.model = service.model.model_copy(update={'max_tokens': output_limit})
        high = build_model(model='gpt-5.6-luna', api_key='offline',
            http_client=service.model.http_client, reasoning_effort='high').model_copy(
                update={'max_tokens': output_limit})
        worker = service.enable_background(max_recoveries=1,
            **({'extraction_model': high} if separate else {}))
        doc = service.create_document('角色接線')['id']
        notify(service, doc, replies)
        replies.extend([body(), done()])
        worker.tick()
        service.submit(doc, 'two', '繼續訪談')
        service.join(doc)
        assert worker.status(doc)['status'] == 'idle'
        assert service._context(doc).memory.publication.current().revision == 1
        payloads = [json.loads(request.content) for request in sent]
        assert [p['reasoning']['effort'] for p in payloads] == [
            'medium', 'medium', 'high' if separate else 'medium', 'medium', 'medium']
        assert all(p['reasoning']['context'] == 'all_turns' for p in payloads)
        assert all(p['max_output_tokens'] == output_limit for p in payloads)
        assert all(p['store'] is False and p['truncation'] == 'disabled' for p in payloads)
        # Exact adoption guard, not proof that the model follows the prompt.
        extraction_prompt = payloads[2]['input'][0]['content']
        assert hashlib.sha256(extraction_prompt.encode()).hexdigest() == (
            '0f621a77a1a8f04edb1edac59ef1c2eee349c2467f7d0325049e36b19f7355c5')


@pytest.mark.parametrize('main_effort,b2_effort', [(None, None), ('high', None), ('medium', 'high')])
def test_real_factory_routes_models_through_same_budget_and_lifetime(tmp_path, monkeypatch, main_effort, b2_effort):
    """Actual composition root; replace only DB resources and HTTP transport."""
    from contextlib import nullcontext
    import sqlalchemy
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.store.postgres import PostgresStore
    from analysis_agent.api import open_service
    from analysis_agent.budget import ResponsesBudget
    from test_consolidation import call

    settings = {'Q019_DATABASE_URL': 'host=127.0.0.1 dbname=q019_offline',
        'OPENAI_API_KEY': 'offline', 'OPENAI_BASE_URL': 'https://offline.invalid/v1/',
        'OPENAI_API_BASE': 'https://offline.invalid/v1/', 'Q019_MODEL': 'gpt-5.6-luna',
        'Q019_REQUEST_TIMEOUT_SECONDS': '7', 'Q019_MAX_OUTPUT_TOKENS': '6000',
        'Q019_CONTEXT_WINDOW_TOKENS': '20000', 'Q019_COMPACT_THRESHOLD': '10000',
        'Q019_BACKGROUND_POLL_SECONDS': '600', 'Q019_BACKGROUND_MAX_RECOVERIES': '1',
        'Q019_MEMORY_TEXT_THRESHOLD': '', 'Q019_CONTEXT_BUDGET_MODE': 'native'}
    for name, value in settings.items():
        monkeypatch.setenv(name, value)
    for name, value in [('Q019_REASONING_EFFORT', main_effort),
                        ('Q019_CONSOLIDATION_REASONING_EFFORT', b2_effort)]:
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    engine = sqlalchemy.create_engine(f'sqlite:///{tmp_path / "factory.db"}')
    saver, store = InMemorySaver(), InMemoryStore()
    monkeypatch.setattr(sqlalchemy, 'create_engine', lambda *a, **kw: engine)
    monkeypatch.setattr(PostgresSaver, 'from_conn_string', lambda *a, **kw: nullcontext(saver))
    monkeypatch.setattr(PostgresStore, 'from_conn_string', lambda *a, **kw: nullcontext(store))
    monkeypatch.setattr(InMemorySaver, 'setup', lambda self: None, raising=False)
    monkeypatch.setattr(InMemoryStore, 'setup', lambda self: None, raising=False)
    sent, budget_calls = [], []
    replies = [call('request_memory_consolidation'), done(), body(), done()]

    def transport(self, request):
        assert str(request.url) == 'https://offline.invalid/v1/responses'
        sent.append(json.loads(request.content))
        answer = replies.pop(0)
        answer['id'] = f'resp_factory_{len(sent)}'
        for n, item in enumerate(answer['output']):
            item['id'] = f'item_factory_{len(sent)}_{n}'
        return httpx.Response(200, json=answer)

    original_guard = ResponsesBudget.__call__

    def guard(self, request):
        budget_calls.append(json.loads(request.content)['reasoning']['effort'])
        return original_guard(self, request)

    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', transport)
    monkeypatch.setattr(ResponsesBudget, '__call__', guard)
    with open_service() as service:
        service.scheduler.pause()
        high = service.background.extraction_model
        main = service.model
        consolidation = service.background.consolidation_model
        assert main.http_client is high.http_client is consolidation.http_client
        assert not main.http_client.is_closed
        assert main.root_client.timeout == high.root_client.timeout == 7
        assert main.http_client.timeout == httpx.Timeout(7, connect=7)
        doc = service.create_document('真入口離線接線')['id']
        service.submit(doc, 'one', '我製作網站。')
        service.join(doc)
        service.background.tick()
        assert service.background.status(doc)['status'] == 'idle'
        assert service._context(doc).memory.publication.current().revision == 1
    assert not replies
    assert budget_calls == [main_effort or 'medium', main_effort or 'medium', 'high', b2_effort or 'medium']
    assert [p['reasoning']['effort'] for p in sent] == budget_calls
    assert all(p['reasoning']['context'] == 'all_turns' for p in sent)
    assert all(p['max_output_tokens'] == 6000 for p in sent)
    assert all(p['context_management'] == [{'type': 'compaction', 'compact_threshold': 10000}] for p in sent)
    assert main.http_client.is_closed
    assert main.root_client.is_closed() and high.root_client.is_closed()


@pytest.mark.parametrize('setting', ['Q019_REASONING_EFFORT', 'Q019_CONSOLIDATION_REASONING_EFFORT'])
def test_invalid_role_effort_fails_before_database_or_network(monkeypatch, setting):
    from analysis_agent.api import open_service
    import sqlalchemy
    required = ('Q019_DATABASE_URL', 'OPENAI_API_KEY', 'Q019_REQUEST_TIMEOUT_SECONDS',
                'Q019_MAX_OUTPUT_TOKENS', 'Q019_COMPACT_THRESHOLD', 'Q019_CONTEXT_WINDOW_TOKENS',
                'Q019_BACKGROUND_POLL_SECONDS', 'Q019_BACKGROUND_MAX_RECOVERIES')
    for name in required:
        monkeypatch.setenv(name, 'offline')
    monkeypatch.setenv('Q019_CONTEXT_BUDGET_MODE', 'native')
    monkeypatch.setenv('Q019_REASONING_EFFORT', 'medium')
    monkeypatch.setenv('Q019_CONSOLIDATION_REASONING_EFFORT', 'medium')
    monkeypatch.setenv(setting, 'invented')
    def forbidden(*args, **kwargs):
        raise AssertionError('Must reject configuration before opening resources')
    monkeypatch.setattr(sqlalchemy, 'create_engine', forbidden)
    with pytest.raises(ValueError, match=setting):
        with open_service():
            pytest.fail('Invalid effort accepted')
