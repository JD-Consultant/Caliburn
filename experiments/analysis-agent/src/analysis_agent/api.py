"""Loopback-only analysis API; factory owns clients for the entire worker life.

https://fastapi.tiangolo.com/advanced/events/
https://fastapi.tiangolo.com/async/
Routes are sync (Starlette threadpool), not async functions calling a blocking
graph. The graph itself runs in the service executor, never a response task.
"""
from contextlib import ExitStack, asynccontextmanager, contextmanager
from datetime import datetime
import os

import httpx
from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.cors import CORSMiddleware
from jd_editor_contract import models as jd_models

from analysis_agent.service import AnalysisService, ServiceConflict
from analysis_agent.jd_contract import SelectionCaptureInput
from analysis_agent.publication import PublicationUncertain


class DocumentInput(jd_models.JdDocumentCreateInput):

    @field_validator('title')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Title cannot be blank')
        return value


class MessageInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_key: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1)
    abandon_pending: bool = False
    jd_selection: SelectionCaptureInput | None = None

    @field_validator('text')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Message cannot be blank')
        return value


class DocumentOutput(jd_models.JdDocumentMetadata):
    pass


def document_output(row):
    return DocumentOutput.model_validate({key: row[key] for key in DocumentOutput.model_fields})


class DocumentMetadataInput(jd_models.JdDocumentMetadataCommand):
    @field_validator('root')
    @classmethod
    def nonblank_title(cls, value):
        if hasattr(value, 'title') and not value.title.strip():
            raise ValueError('Title cannot be blank')
        return value


class MessageOutput(BaseModel):
    id: str
    role: str
    text: str


class RunOutput(BaseModel):
    id: str
    document_id: str
    status: str
    error_code: str | None
    resume_count: int
    usage_complete: bool
    usage: dict[str, int] | None
    outcome: dict | None
    can_resume: bool


class RunLookupReceived(jd_models.JdRunLookupReceived):
    run: RunOutput


RunLookupOutput = jd_models.JdRunLookupMissing | RunLookupReceived


class MemoryStatusOutput(BaseModel):
    status: str
    error_code: str | None
    recovery_count: int


@contextmanager
def open_service():
    """Fresh isolated resources; no automatic A resume. B checks saved work.

Timeout, output and compaction thresholds are explicit deployment values, not
an undocumented resurrected initial policy or a promised hard dollar cap.
"""
    from analysis_agent.windows_lifecycle import require_bootstrap
    lifecycle = require_bootstrap()
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.store.postgres import PostgresStore
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    from openai import OpenAI
    from analysis_agent.budget import ResponsesBudget, validate_context_budget
    from analysis_agent.catalog import Catalog
    from analysis_agent.jd_store import JdStore
    from analysis_agent.jd_engine import JdEngine
    from analysis_agent.jd_service import JdService
    from analysis_agent.provider import build_model
    from analysis_agent.publication import Base as PublicationBase

    required = ('Q019_DATABASE_URL', 'OPENAI_API_KEY', 'Q019_REQUEST_TIMEOUT_SECONDS',
                'Q019_MAX_OUTPUT_TOKENS', 'Q019_COMPACT_THRESHOLD', 'Q019_CONTEXT_WINDOW_TOKENS',
                'Q019_BACKGROUND_POLL_SECONDS', 'Q019_BACKGROUND_MAX_RECOVERIES')
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError('Required settings missing: ' + ', '.join(missing))
    budget_mode = os.environ.get('Q019_CONTEXT_BUDGET_MODE', 'native')
    if budget_mode not in {'native', 'exact'}:
        raise ValueError('Q019_CONTEXT_BUDGET_MODE must be native or exact')
    # CT50: use CT49's tested high profile; explicit per-role overrides remain.
    # No alternate loop or implicit output/context budget defaults.
    effort = os.environ.get('Q019_REASONING_EFFORT', 'high')
    consolidation_effort = os.environ.get('Q019_CONSOLIDATION_REASONING_EFFORT', 'high')
    for setting, value in [('Q019_REASONING_EFFORT', effort),
                           ('Q019_CONSOLIDATION_REASONING_EFFORT', consolidation_effort)]:
        if value not in {'low', 'medium', 'high', 'xhigh', 'max'}:
            raise ValueError('Invalid ' + setting)
    params = conninfo_to_dict(os.environ['Q019_DATABASE_URL'])
    if params.get('host') not in {'localhost', '127.0.0.1'} or not params.get('dbname', '').startswith('q019_'):
        raise ValueError('This isolated entry requires a local q019_ database')
    timeout = float(os.environ['Q019_REQUEST_TIMEOUT_SECONDS'])
    output = int(os.environ['Q019_MAX_OUTPUT_TOKENS'])
    compaction = int(os.environ['Q019_COMPACT_THRESHOLD'])
    capacity = int(os.environ['Q019_CONTEXT_WINDOW_TOKENS'])
    validate_context_budget(capacity, output, compaction)
    poll_seconds = float(os.environ['Q019_BACKGROUND_POLL_SECONDS'])
    recoveries = int(os.environ['Q019_BACKGROUND_MAX_RECOVERIES'])
    text_threshold = int(os.environ['Q019_MEMORY_TEXT_THRESHOLD']) if os.environ.get('Q019_MEMORY_TEXT_THRESHOLD') else None
    if not 0 < timeout < float('inf') or output <= 0 or compaction <= 0:
        raise ValueError('Timeout/output/compaction settings must be positive and finite')
    if not 0 < poll_seconds < float('inf') or recoveries < 0 or (text_threshold is not None and text_threshold <= 0):
        raise ValueError('Invalid explicit background settings')
    dsn = make_conninfo(os.environ['Q019_DATABASE_URL'], connect_timeout=5,
                       options='-c statement_timeout=10000 -c lock_timeout=5000')
    with ExitStack() as stack:
        engine = create_engine(URL.create('postgresql+psycopg'), connect_args=conninfo_to_dict(dsn),
                               hide_parameters=True, pool_pre_ping=True)
        stack.callback(engine.dispose)
        saver = stack.enter_context(PostgresSaver.from_conn_string(dsn))
        store = stack.enter_context(PostgresStore.from_conn_string(dsn))
        saver.setup()
        store.setup()
        catalog = Catalog(engine)
        catalog.setup()
        jd_store = JdStore(engine)
        jd_store.setup()
        jd = JdService(jd_store, JdEngine(), catalog)
        PublicationBase.metadata.create_all(engine)
        http_timeout = httpx.Timeout(timeout, connect=min(timeout, 10))
        count_http = stack.enter_context(httpx.Client(timeout=http_timeout))
        counter = stack.enter_context(OpenAI(api_key=os.environ['OPENAI_API_KEY'],
                                            http_client=count_http, timeout=http_timeout))
        model_name = os.environ.get('Q019_MODEL', 'gpt-5.6-luna')
        budget = ResponsesBudget(counter=counter, model=model_name, context_window_tokens=capacity,
                                 exact_count=budget_mode == 'exact')
        client = stack.enter_context(httpx.Client(timeout=http_timeout, event_hooks={'request': [budget]}))
        # Resolve OPENAI_BASE_URL once through the SDK public property. Both
        # clients MUST target the same endpoint, including custom path prefixes.
        model = build_model(model=model_name, base_url=str(counter.base_url),
                            api_key=os.environ['OPENAI_API_KEY'], http_client=client,
                            request_timeout=timeout, reasoning_effort=effort,
                            compact_threshold=compaction).model_copy(update={'max_tokens': output})
        stack.callback(model.root_client.close)
        # B1 keeps its independently calibrated high effort. Keep the same
        # endpoint, transport/budget hook and output cap as the other roles.
        extraction_model = build_model(model=model_name, base_url=str(counter.base_url),
            api_key=os.environ['OPENAI_API_KEY'], http_client=client,
            request_timeout=timeout, compact_threshold=compaction,
            reasoning_effort='high').model_copy(update={'max_tokens': output})
        stack.callback(extraction_model.root_client.close)
        # LangChain model copies share the same managed client/budget hook.
        consolidation_model = model.model_copy(update={
            'reasoning': {**model.reasoning, 'effort': consolidation_effort}})
        service = AnalysisService(catalog=catalog, saver=saver, store=store, model=model, jd=jd,lifecycle=lifecycle,
            instructions='你是職務訪談顧問。理解員工實際工作，按需追問不清楚的內容；遇到矛盾先確認。'
                         '根據已知內容簡短回述，優先問一個員工目前可回答、會影響工作理解的問題，不逐欄填問卷。'
                         '已說清楚的不重問；員工已說不知道、需查證或暫時答不出來，也算已回應：保留未知，轉問其他有用方向。'
                         '有新資訊或員工重新提出時才回看該未知；部分已說明就保留已知部分，未知不說成沒有這項工作或固定要求。'
                         '回述與歸納保留原資訊的對象、本人做法、適用條件、頻率與權限；不把某案例的工具或限制套到其他工作，不把同時提及說成因果。'
                         '你的改寫不等於員工確認；工作用語有歧義時保留員工用詞，有實際影響才追問。'
                         '準備收尾時，對照已談的重要工作範圍、本人做法、責任交接、重要條件、成果與實際專業判斷，不只核對工作名稱。'
                         '用目前對話與按需讀取的Memory核對；需要方法時用現有分析Skills，不每輪全面盤點，也不逐案例重問相同問題。'
                         '仍有影響理解的重要未知就自然追問；已說不知道的外部資訊保留限制，不為收尾編造要求。'
                         '收尾說明目前涵蓋與尚未確認之處，不用反覆最後一題或一句完整代替核對；員工可隨時休息或續談。'
                         '目前只做訪談分析，不製作或編輯JD。不顯示隱藏推理。')
        stack.callback(service.close)
        service.start()
        service.enable_background(max_recoveries=recoveries, text_threshold=text_threshold,
                                  extraction_model=extraction_model,
                                  consolidation_model=consolidation_model)
        service.start_background(poll_seconds=poll_seconds)
        yield service


def create_app(resources=open_service):
    if resources is open_service:
        from analysis_agent.windows_lifecycle import bootstrap
        bootstrap()
    @asynccontextmanager
    async def lifespan(app):
        manager = resources()
        service = await run_in_threadpool(manager.__enter__)
        app.state.service = service
        try:
            yield
        finally:
            # Join workers before their HTTP/DB clients exit. Disconnecting one
            # browser request never reaches this application-level cleanup.
            await run_in_threadpool(manager.__exit__, None, None, None)

    app = FastAPI(title='Caliburn analysis-only API', lifespan=lifespan)
    from analysis_agent.jd_routes import router as jd_router
    app.include_router(jd_router)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1'])
    web_origins = ['http://127.0.0.1:3001', 'http://localhost:3001']
    app.add_middleware(CORSMiddleware, allow_origins=web_origins, allow_credentials=False,
        allow_methods=['GET', 'POST', 'PATCH'], allow_headers=['Content-Type'])

    @app.middleware('http')
    async def same_origin(request: Request, call_next):
        origin = request.headers.get('origin')
        if origin and origin not in web_origins:
            return JSONResponse({'detail': 'Cross-origin access is not enabled'}, status_code=403)
        return await call_next(request)

    @app.exception_handler(ServiceConflict)
    async def conflict(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=409)

    @app.exception_handler(PublicationUncertain)
    async def uncertain(request, exc):
        return JSONResponse({'detail': 'Memory publication result requires reconciliation'}, status_code=409)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({'detail': 'Resource not found'}, status_code=404)

    @app.get('/health')
    def health():
        return {'status': 'ready'}

    @app.post('/documents', response_model=DocumentOutput, status_code=201)
    def create_document(data: DocumentInput):
        return document_output(app.state.service.create_document(data.title, request_key=str(data.request_key)))

    @app.get('/documents', response_model=list[DocumentOutput])
    def documents(archived: bool = False):
        rows = [r for r in app.state.service.list_documents() if r['archived'] == archived]
        return [document_output(row) for row in sorted(rows, key=lambda r: (r['created_at'], r['id']), reverse=True)]

    @app.get('/documents/{document}', response_model=DocumentOutput)
    def document_metadata(document: str):
        return document_output(app.state.service.catalog.document(document))

    @app.patch('/documents/{document}', response_model=DocumentOutput)
    def update_document(document: str, data: DocumentMetadataInput):
        return document_output(app.state.service.update_document(document, data.model_dump(mode='json')))

    @app.post('/documents/{document}/runs', response_model=RunOutput, status_code=202)
    def submit(document: str, data: MessageInput):
        return app.state.service.submit(document, data.request_key, data.text, abandon_pending=data.abandon_pending,
            **({"jd_selection": data.jd_selection.model_dump(mode="json")} if data.jd_selection is not None else {}))

    @app.get('/documents/{document}/messages', response_model=list[MessageOutput])
    def messages(document: str):
        return app.state.service.messages(document)

    @app.get('/documents/{document}/sources', response_model=jd_models.JdSourceReadResult)
    def source(document: str, request: Request, reference: str = Query(min_length=1, max_length=4096), offset: int = Query(default=0, ge=0)):
        service = request.app.state.service
        service.catalog.document(document)
        try:
            return service.reader(document).read(reference, offset)
        except ValueError as exc:
            from fastapi import HTTPException
            raise HTTPException(422, 'Source is unavailable in this document') from exc

    @app.get('/documents/{document}/memory-status', response_model=MemoryStatusOutput)
    def memory_status(document: str):
        service = app.state.service
        service.catalog.document(document)
        return (service.background.status(document) if service.background else
                {'status': 'disabled', 'error_code': None, 'recovery_count': 0})

    @app.get('/documents/{document}/runs', response_model=list[RunOutput])
    def runs(document: str):
        return app.state.service.runs(document)

    @app.get('/documents/{document}/runs/by-request', response_model=RunLookupOutput)
    def run_by_request(document: str, request_key: str = Query(min_length=1, max_length=128)):
        return app.state.service.run_by_request(document, request_key)

    @app.get('/documents/{document}/runs/{run_id}', response_model=RunOutput)
    def get_run(document: str, run_id: str):
        return app.state.service.get_run(document, run_id)

    @app.post('/documents/{document}/runs/{run_id}/stop', response_model=RunOutput)
    def stop(document: str, run_id: str):
        return app.state.service.stop(document, run_id)

    @app.post('/documents/{document}/runs/{run_id}/resume', response_model=RunOutput, status_code=202)
    def resume(document: str, run_id: str):
        return app.state.service.resume(document, run_id)

    return app


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(create_app(), host='127.0.0.1', port=8091, workers=1, reload=False, proxy_headers=False)
