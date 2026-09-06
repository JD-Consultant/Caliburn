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
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from analysis_agent.service import AnalysisService, ServiceConflict
from analysis_agent.publication import PublicationUncertain


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=200)

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

    @field_validator('text')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Message cannot be blank')
        return value


class DocumentOutput(BaseModel):
    id: str
    title: str
    created_at: datetime


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


@contextmanager
def open_service():
    """Fresh isolated local resources; startup does not call a model.

Timeout, output and compaction thresholds are explicit deployment values, not
an undocumented resurrected initial policy or a promised hard dollar cap.
"""
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.store.postgres import PostgresStore
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    from analysis_agent.catalog import Catalog
    from analysis_agent.provider import build_model
    from analysis_agent.publication import Base as PublicationBase

    required = ('Q019_DATABASE_URL', 'OPENAI_API_KEY', 'Q019_REQUEST_TIMEOUT_SECONDS',
                'Q019_MAX_OUTPUT_TOKENS', 'Q019_COMPACT_THRESHOLD')
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError('Required settings missing: ' + ', '.join(missing))
    params = conninfo_to_dict(os.environ['Q019_DATABASE_URL'])
    if params.get('host') not in {'localhost', '127.0.0.1'} or not params.get('dbname', '').startswith('q019_'):
        raise ValueError('This isolated entry requires a local q019_ database')
    timeout = float(os.environ['Q019_REQUEST_TIMEOUT_SECONDS'])
    output = int(os.environ['Q019_MAX_OUTPUT_TOKENS'])
    compaction = int(os.environ['Q019_COMPACT_THRESHOLD'])
    if not 0 < timeout < float('inf') or output <= 0 or compaction <= 0:
        raise ValueError('Timeout/output/compaction settings must be positive and finite')
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
        PublicationBase.metadata.create_all(engine)
        client = stack.enter_context(httpx.Client(timeout=httpx.Timeout(timeout, connect=min(timeout, 10))))
        model = build_model(model=os.environ.get('Q019_MODEL', 'gpt-5.6-luna'),
                            api_key=os.environ['OPENAI_API_KEY'], http_client=client,
                            request_timeout=timeout,
                            compact_threshold=compaction).model_copy(update={'max_tokens': output})
        service = AnalysisService(catalog=catalog, saver=saver, store=store, model=model,
            instructions='你是職務訪談顧問。理解員工實際工作，按需追問不清楚的內容；遇到矛盾先確認。'
                         '目前只做訪談分析，不製作或編輯JD。不顯示隱藏推理。'
                         '一段訪談已有值得整理的資訊時，可通知背景記憶整理；不必每回合通知。')
        stack.callback(service.close)
        service.start()
        yield service


def create_app(resources=open_service):
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
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1'])

    @app.middleware('http')
    async def same_origin(request: Request, call_next):
        origin = request.headers.get('origin')
        if origin and origin != str(request.base_url).rstrip('/'):
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
        return app.state.service.create_document(data.title)

    @app.get('/documents', response_model=list[DocumentOutput])
    def documents():
        return app.state.service.list_documents()

    @app.post('/documents/{document}/runs', response_model=RunOutput, status_code=202)
    def submit(document: str, data: MessageInput):
        return app.state.service.submit(document, data.request_key, data.text, abandon_pending=data.abandon_pending)

    @app.get('/documents/{document}/messages', response_model=list[MessageOutput])
    def messages(document: str):
        return app.state.service.messages(document)

    @app.get('/documents/{document}/runs', response_model=list[RunOutput])
    def runs(document: str):
        return app.state.service.runs(document)

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
