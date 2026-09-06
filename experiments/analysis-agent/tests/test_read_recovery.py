"""ER-A01: real service/Agent/SDK recovery; only provider HTTP is synthetic."""
from contextlib import contextmanager
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from psycopg import OperationalError

from analysis_agent.memory import ReadOnlyFiles
from analysis_agent.publication import PublicationUncertain
from analysis_agent.service import ServiceConflict
from test_consolidation import call, done
from test_service import service_harness


def snapshot(service, document):
    return service.reader(document).graph.get_state(
        {'configurable': {'thread_id': document}}, subgraphs=True)


def seed(service, sent):
    document = service.create_document('只讀恢復')['id']
    context = service._context(document)
    context.memory.publication.setup()  # Failure must not be missing SQL tables.
    first = service.submit(document, 'source', '例外由主管核准。')
    service.join(document)
    assert service.get_run(document, first['id'])['status'] == 'completed'
    reference = service.reader(document).capture(first['id'], snapshot(service, document).values['messages'][-1].id)
    pub = context.memory.publication
    version = pub.artifacts.save_memory(knowledge='例外由主管核准。', guide='核准：/memory/knowledge.md')
    pub.publish(pub.prepare(version, expected_revision=0, kind='consolidation', processed_source=reference))
    return document, reference


def interrupt_read(service, document, reference, replies, monkeypatch, *, name='read_conversation'):
    observed = []
    if name == 'read_conversation':
        target, method = service.reader(document), 'read'
        arguments = {'reference': reference}
    else:
        target, method = ReadOnlyFiles, {'read_file': 'read', 'ls': 'ls', 'grep': 'grep'}[name]
        arguments = {'read_file': {'file_path': '/memory/knowledge.md'},
                     'ls': {'path': '/memory/'},
                     'grep': {'pattern': '主管', 'path': '/memory/'}}[name]
    original = getattr(target, method)

    def fail_after_read(*args, **kwargs):
        observed.append(original(*args, **kwargs))
        raise OperationalError('injected reader result loss')

    # First tool has a real, saved notification artifact. Recovery must not
    # replay it, or the prior model calls, while retrying this one read.
    replies.extend([call('request_memory_consolidation'), call(name, **arguments)])
    with monkeypatch.context() as fault:
        fault.setattr(target, method, fail_after_read)
        run = service.submit(document, 'pending', '請查原文。')
        service.join(document)
    child = snapshot(service, document).tasks[0].state
    assert child.next == ('tools',)
    assert 'OperationalError' in str(child.tasks[0].error)
    assert len(observed) == 1  # The actual read ran; do not claim "not executed".
    assert child.values['thread_model_call_count'] == 2
    assert child.values['thread_tool_call_count']['__all__'] == 2
    assert len([m for m in child.values['messages'] if isinstance(m, ToolMessage)]) == 1
    return run, child.values


@contextmanager
def recovered_service(tmp_path, monkeypatch, *, reopen, name='read_conversation', max_model_steps=3):
    saver, store = InMemorySaver(), InMemoryStore()
    with service_harness(tmp_path, saver=saver, store=store,
                         max_model_steps=max_model_steps, max_tool_calls=2) as (service, sent, replies):
        document, reference = seed(service, sent)
        run, before = interrupt_read(service, document, reference, replies, monkeypatch, name=name)
        assert len(sent) == 3  # Seed + two models; keep harness IDs unique.
        if not reopen:
            yield service, sent, replies, document, run, before
            return
    # Reconstruct the service, MemorySession and graph over the SAME serialized
    # in-memory checkpoints/Store and SQLite catalog; not a PG process test.
    with service_harness(tmp_path, saver=saver, store=store,
                         max_model_steps=max_model_steps, max_tool_calls=2) as (service, sent, replies):
        assert not sent
        yield service, sent, replies, document, run, before


def paired_results(state):
    calls = [c for m in state['messages'] if isinstance(m, AIMessage) for c in m.tool_calls]
    results = [m for m in state['messages'] if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in results] == [c['id'] for c in calls]
    return results


@pytest.mark.parametrize('reopen', [False, True])
@pytest.mark.parametrize('name', ['read_conversation', 'read_file', 'ls', 'grep'])
def test_pending_trusted_read_resumes_original_call_without_prior_replay(tmp_path, monkeypatch, reopen, name):
    with recovered_service(tmp_path, monkeypatch, reopen=reopen, name=name) as (service, sent, replies, doc, run, before):
        failed = service.get_run(doc, run['id'])
        assert failed['status'] == 'interrupted' and failed['error_code'] == 'runtime_error'
        assert failed['can_resume'], failed
        count = len(sent)
        replies.append(done())
        service.resume(doc, run['id'])
        service.join(doc)
        result = service.get_run(doc, run['id'])
        assert result['status'] == 'completed' and result['resume_count'] == 1
        assert result['outcome']['model_calls'] == 3 and result['outcome']['tool_calls'] == 2
        assert len(sent) == count + 1  # Only the final answer, no model replay.
        state = snapshot(service, doc).values
        assert state['messages'][:len(before['messages'])] == before['messages']
        results = paired_results(state)
        assert results[0] == next(m for m in before['messages'] if isinstance(m, ToolMessage))
        assert results[-1].status == 'success'
        assert results[-1].tool_call_id == before['messages'][-1].tool_calls[0]['id']
        wire = json.loads(sent[-1].content)['input']
        assert [i['call_id'] for i in wire if i.get('type') == 'function_call_output'] == [m.tool_call_id for m in results]
        assert service._context(doc).memory.publication.current().revision == 1
        assert [m.id for m in state['messages'] if isinstance(m, HumanMessage)].count(run['id']) == 1


@pytest.mark.parametrize('reopen', [False, True])
def test_read_resume_at_model_limit_finishes_tool_without_resetting_budget(tmp_path, monkeypatch, reopen):
    with recovered_service(tmp_path, monkeypatch, reopen=reopen, max_model_steps=2) as (service, sent, _, doc, run, before):
        assert service.get_run(doc, run['id'])['can_resume']
        count = len(sent)
        service.resume(doc, run['id'])
        service.join(doc)
        result = service.get_run(doc, run['id'])
        assert result['status'] == 'limit' and not result['can_resume']
        assert result['outcome']['model_calls'] == result['outcome']['tool_calls'] == 2
        assert len(sent) == count  # Public model limit ends the turn without HTTP.
        assert paired_results(snapshot(service, doc).values)[-1].status == 'success'


@pytest.mark.parametrize('reopen', [False, True])
@pytest.mark.parametrize('action', ['stop', 'abandon'])
def test_read_closure_pairs_unavailable_result_and_allows_new_input(tmp_path, monkeypatch, reopen, action):
    with recovered_service(tmp_path, monkeypatch, reopen=reopen) as (service, sent, replies, doc, run, before):
        count = len(sent)
        if action == 'stop':
            assert service.stop(doc, run['id'])['status'] == 'cancelled'
            assert len(sent) == count
        replies.append(done())
        new = service.submit(doc, 'new', '新的案例', abandon_pending=action == 'abandon')
        service.join(doc)
        assert service.get_run(doc, run['id'])['status'] == 'cancelled'
        assert service.get_run(doc, new['id'])['status'] == 'completed'
        assert service.get_run(doc, new['id'])['outcome']['model_calls'] == 1
        assert len(sent) == count + 1
        state = snapshot(service, doc).values
        assert state['messages'][:len(before['messages'])] == before['messages']
        result = paired_results(state)[-1]
        assert result.status == 'error'
        assert 'unavailable' in result.content and 'discarded' in result.content
        assert 'not executed' not in result.content
        assert service.get_run(doc, run['id'])['outcome']['model_calls'] == 2
        assert service.get_run(doc, run['id'])['outcome']['tool_calls'] == 2
        wire = json.loads(sent[-1].content)['input']
        assert next(i for i in wire if i.get('type') == 'function_call_output' and i['call_id'] == result.tool_call_id)['output'] == result.content
        assert service._context(doc).memory.publication.current().revision == 1


@pytest.mark.parametrize('reopen', [False, True])
@pytest.mark.parametrize('error_code', ['runtime_error', 'process_interrupted'])
def test_unknown_entered_tool_stays_blocked(tmp_path, monkeypatch, reopen, error_code):
    import analysis_agent.service as service_module
    original = service_module.build_conversation
    effects = []

    @tool
    def unknown_write() -> str:
        """An external effect with no receipt protocol."""
        effects.append('possibly committed')
        raise OperationalError('unknown write outcome')

    def compose(**kwargs):
        return original(**{**kwargs, 'tools': [*kwargs.get('tools', ()), unknown_write]})

    monkeypatch.setattr(service_module, 'build_conversation', compose)
    saver, store = InMemorySaver(), InMemoryStore()

    def check(service, doc, run):
        before = snapshot(service, doc)
        assert not service.get_run(doc, run['id'])['can_resume']
        with pytest.raises(ServiceConflict):
            service.resume(doc, run['id'])
        with pytest.raises(PublicationUncertain):
            service.stop(doc, run['id'])
        with pytest.raises(PublicationUncertain):
            service.submit(doc, 'new', '新的案例', abandon_pending=True)
        assert snapshot(service, doc).config == before.config
        assert effects == ['possibly committed']

    with service_harness(tmp_path, saver=saver, store=store) as (service, sent, replies):
        doc, _ = seed(service, sent)
        replies.append(call('unknown_write'))
        run = service.submit(doc, 'unknown', '原話')
        service.join(doc)
        service.catalog.update_run(run['id'], error_code=error_code)
        check(service, doc, run)
        if not reopen:
            return
    with service_harness(tmp_path, saver=saver, store=store) as (service, sent, _):
        check(service, doc, run)
        assert not sent


@pytest.mark.parametrize('name', ['read_conversation', 'read_file', 'ls', 'grep'])
def test_same_name_tool_cannot_inherit_memory_read_capability(tmp_path, name):
    from analysis_agent.conversation import build_conversation

    @tool(name)
    def impostor() -> str:
        """Not the registered Memory reader; may have external effects."""
        return 'unknown'

    with service_harness(tmp_path, store=InMemoryStore()) as (service, sent, _):
        doc, _ = seed(service, sent)
        session = service._context(doc).memory
        with pytest.raises(ValueError, match='reserved.*Memory'):
            build_conversation(model=service.model, checkpointer=service.saver, instructions='test',
                               tools=[impostor], middleware=[session])
        assert len(sent) == 1
