"""Task6 fixed engineering fixture over the complete real service/router.

Only HTTP model responses are synthetic. No external provider or key fallback.
The test factory explicitly initializes the dedicated test DB, not a production
startup procedure. Actual Windows bootstrap precedes every resource owner.
"""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import re
from threading import Event
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
SCENARIO_PATH = ROOT/'experiments/jd-editor/fixtures/core-scenario.json'


def scenario():
    return json.loads(SCENARIO_PATH.read_text(encoding='utf-8'))


def text_of(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ''.join(text_of(item) for item in value)
    if isinstance(value, dict):
        return value.get('text', '') + text_of(value.get('children', value.get('content', [])))
    return ''


def current_turn(body):
    items = body['input']
    last = max(i for i, item in enumerate(items)
               if item.get('role') == 'user' and 'app_jd_context' not in json.dumps(item))
    return text_of(items[last]), items[last:]


def current_source(body):
    supplied = '\n'.join(text_of(item) for item in body['input'] if item.get('role') in ('system','developer'))
    return re.search(r'Current input reference \(copy only if useful\): (conversation:[A-Za-z0-9_=-]+)', supplied).group(1)


class FixedInterview:
    """Finite fixture intentions, chosen only from explicit synthetic utterances.

    All runtime locators and sources come from the actual supplied tool/context
    values. This deliberately does NOT test natural tool selection or writing.
    """
    def __init__(self, record_path=None):
        self.fixture = scenario()
        self.requests = []
        self.record_path = record_path
        self.cancel_entered, self.cancel_release = Event(), Event()
        self.cancel_release.set()

    def __call__(self, request):
        import httpx
        from test_native_continuity import response_body, assistant_text
        assert request.method == 'POST' and request.url.path == '/v1/responses'
        body = json.loads(request.content)
        self.requests.append(body)
        if self.record_path:
            with Path(self.record_path).open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(body, ensure_ascii=False)+'\n')
        utterance, turn = current_turn(body)
        key = next((k for k,v in self.fixture['utterances'].items() if v == utterance), None)
        outputs = [i for i in turn if i.get('type') == 'function_call_output']
        calls = {i['call_id']:i for i in turn if i.get('type') == 'function_call'}
        results = [(calls[i['call_id']]['name'], i['output']) for i in outputs]
        reads = [json.loads(value) for name,value in results if name == 'jd_read']
        action = None
        if key == 'draft':
            step = len(outputs)
            paths = ['SKILL.md', 'references/complete-work-guide.md', 'references/writing-and-correction.md']
            if step < 3:
                action = ('read_file', {'file_path':'/skills/write-customized-jd/'+paths[step], 'limit':1000})
            elif step in (3,6):
                action = ('jd_read', {})
            elif step == 4:
                action = ('read_conversation', {'reference':current_source(body)})
            elif step == 5:
                source = json.loads(results[-1][1])['reference']
                content = deepcopy(self.fixture['expected_initial_content'])
                for section in content:
                    section['source_refs'] = [source]
                target = reads[-1]['targets'][0]['target_ref']
                action = ('jd_edit', {'commands':[
                    {'type':'insert_content','target_ref':target,'placement':'before','content':content},
                    {'type':'remove_content','target_ref':target}]})
            elif step == 7:
                targets = reads[-1]['targets']
                tasks = [t for t in targets if t['element']['type']=='jd_task']
                knowledge = [t['target_ref'] for t in targets if t['element']['type']=='jd_knowledge']
                skills = [t['target_ref'] for t in targets if t['element']['type']=='jd_skill']
                action = ('jd_edit', {'commands':[{'type':'set_properties','target_ref':t['target_ref'],
                    'set':{'knowledge_refs':knowledge,'skill_refs':skills if i else skills[:1]}}
                    for i,t in enumerate(tasks)]})
            elif step == 8:
                action = ('jd_change_read', {'change_ref':json.loads(results[-1][1])['change_ref']})
        elif key in ('correct','continue','lost'):
            if not outputs:
                action = ('jd_read', {})
            elif key == 'correct' and len(outputs)==1:
                action = ('read_conversation', {'reference':current_source(body)})
            elif len(outputs)==(2 if key=='correct' else 1):
                read = reads[-1]
                if key == 'correct':
                    target = next(t for t in read['targets'] if text_of(t['element'])==self.fixture['monthly_original'])
                    content = self.fixture['monthly_corrected']
                else:
                    section = next(t['element'] for t in read['targets'] if t['element'].get('section_kind')=='purpose')
                    target = next(t for t in read['targets'] if t['element']['id']==section['children'][1]['id'])
                    content = self.fixture['continued_purpose' if key=='continue' else 'lost_purpose']
                commands = [{'type':'replace_block_content','target_ref':target['target_ref'],'content':[{'text':content}]}]
                if key == 'correct':
                    commands.append({'type':'set_properties','target_ref':target['target_ref'],
                                     'set':{'source_refs':[json.loads(results[-1][1])['reference']]}})
                action = ('jd_edit', {'commands':commands})
        elif key == 'cancel':
            self.cancel_entered.set()
            assert self.cancel_release.wait(20), 'Test must explicitly release the synthetic response'
        if action:
            name, arguments = action
            output = [{'type':'function_call','id':'fc_'+str(uuid4()),'call_id':'call_'+str(uuid4()),
                       'name':name,'arguments':json.dumps(arguments,ensure_ascii=False),'status':'completed'}]
        else:
            writes = [json.loads(value) for name,value in results if name=='jd_edit']
            if writes:
                statuses = [r['status'] for r in writes]
                answer = '已依實際工具結果保存本輪修改。' if all(s in ('committed','no_change') for s in statuses) else '這輪尚未確認保存成功，請查看實際結果。'
            elif key=='intro':
                answer = '你平常負責哪些設備工作？可以先說一件你親自處理的例子。'
            else:
                answer = '已收到；這輪沒有修改職務說明書，可稍後继续補充。'
            output = [assistant_text(answer,item_id='msg_'+str(uuid4()))]
        return httpx.Response(200,json=response_body(output,response_id='resp_'+str(uuid4())))


@contextmanager
def resources(transport=None):
    from analysis_agent.windows_lifecycle import require_bootstrap
    lifecycle = require_bootstrap()
    import httpx
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.store.postgres import PostgresStore
    from psycopg.conninfo import conninfo_to_dict
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    from analysis_agent.api import ADVISOR_INSTRUCTIONS
    from analysis_agent.catalog import Catalog
    from analysis_agent.jd_store import JdStore
    from analysis_agent.jd_engine import JdEngine
    from analysis_agent.jd_service import JdService
    from analysis_agent.provider import build_model
    from analysis_agent.publication import Base
    from analysis_agent.service import AnalysisService
    dsn = os.environ['Q019_TEST_DATABASE_URL']
    params = conninfo_to_dict(dsn)
    assert params['dbname']=='q019_jd_app_20260910' and params['host']=='127.0.0.1'
    assert 1 <= int(params.get('connect_timeout',0)) <= 5
    with ExitStack() as stack:
        engine = create_engine(URL.create('postgresql+psycopg'),connect_args=params,hide_parameters=True)
        stack.callback(engine.dispose)
        saver = stack.enter_context(PostgresSaver.from_conn_string(dsn)); saver.setup()
        store = stack.enter_context(PostgresStore.from_conn_string(dsn)); store.setup()
        catalog = Catalog(engine); catalog.setup(); catalog.upgrade_document_metadata()
        jd_store = JdStore(engine); jd_store.setup(); Base.metadata.create_all(engine)
        jd = JdService(jd_store,JdEngine(),catalog)
        transport = transport or FixedInterview(os.environ.get('Q019_TEST_RECORD_PATH'))
        client = stack.enter_context(httpx.Client(transport=httpx.MockTransport(transport)))
        model = build_model(model='gpt-5.6-luna',api_key='offline-not-a-key',http_client=client)
        stack.callback(model.root_client.close)
        service = AnalysisService(catalog=catalog,saver=saver,store=store,model=model,jd=jd,
                                  lifecycle=lifecycle,instructions=ADVISOR_INSTRUCTIONS)
        stack.callback(service.close)
        service.start()
        yield service


def create_app():
    from analysis_agent.windows_lifecycle import bootstrap
    bootstrap()
    from analysis_agent.api import create_app as real_app
    return real_app(resources)
