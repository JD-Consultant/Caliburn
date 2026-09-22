"""Thin chat HTTP projection on the existing local App lifespan and boundaries."""
from dataclasses import dataclass
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import Body, Depends, Query, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from .catalog_api import CatalogBoundary, CatalogServices
from .chat_service import ChatError, ChatService, parse_chat_input
from .run_change_reads import run_change_openapi_conditions
from .generated.chat_http import ChatStartInput, ChatRunState, ChatHistoryPage, ChatProblem, ChatRunChangePage


START_ROUTE = '/api/documents/{document_id}/chat/runs'
RUN_ROUTE = START_ROUTE + '/{run_id}'
CANCEL_ROUTE = RUN_ROUTE + '/cancel'
RECOVER_ROUTE = RUN_ROUTE + '/recover'
HISTORY_ROUTE = '/api/documents/{document_id}/chat/messages'
CHANGES_ROUTE = RUN_ROUTE + '/changes'
CHAT_ROUTES = frozenset({START_ROUTE, RUN_ROUTE, CANCEL_ROUTE, RECOVER_ROUTE, HISTORY_ROUTE, CHANGES_ROUTE})


@dataclass(frozen=True)
class ChatServices(CatalogServices):
    chat: ChatService


_ERRORS = {
    'invalid_input': (422, 'correct_input', '請檢查送出的訪談內容。'),
    'invalid_ref': (422, 'reread', '請重新讀取文件或對話後再操作。'),
    'document_missing': (404, 'reread', '找不到這份文件，請重新查看列表。'),
    'dataset_changed': (409, 'reread', '目前開啟的資料已更換，請重新查看文件。'),
    'stale_view': (409, 'reread', 'JD 已有新修改，請先確認保存的內容後再送出。'),
    'run_conflict': (409, 'lookup_run', '這個訪談編號已對應其他內容，請先查回原回合。'),
    'busy': (409, 'wait', '這份文件仍有工作尚未結束，或已封存；請先查看文件狀態。'),
    'recovery_required': (409, 'recover', '原回合尚未確認收尾，請使用原回合的恢復操作。'),
    'ai_unavailable': (503, 'stop', 'AI 訪談尚未啟用；請保留輸入。目前仍可查看原有對話及編輯 JD。'),
    'service_unavailable': (503, 'lookup_run', '目前無法開始或確認 AI 回合；請保留原輸入並查看原回合狀態。'),
    'origin_not_allowed': (403, 'stop', '請從本機 App 的工作畫面操作。'),
}


def chat_problem(scope, code='service_unavailable', *, internal=False):
    code = code if type(code) is str and code in _ERRORS else 'service_unavailable'
    status, action, detail = _ERRORS[code]
    if internal:
        status = 500
    value = ChatProblem(type='about:blank', title=HTTPStatus(status).phrase,
        status=status, detail=detail, instance=f"urn:uuid:{scope['jd.request_id']}",
        code=code, next_action=action).model_dump(mode='json')
    return JSONResponse(value, status_code=status, media_type='application/problem+json')


class ChatBoundary(CatalogBoundary):
    routes = CatalogBoundary.routes | CHAT_ROUTES
    # Origin is checked before routing. Its fixed envelope is compatible with
    # the same local Origin rejection on the existing manual/catalog routes.
    origin_problem = staticmethod(chat_problem)

    def failure_response(self, scope, error):
        if getattr(scope.get('route'), 'path', None) not in CHAT_ROUTES:
            return super().failure_response(scope, error)
        return chat_problem(scope, error.code) if isinstance(error, ChatError) else chat_problem(scope, internal=True)


def attach_chat_routes(app):
    previous_invalid = app.exception_handlers[RequestValidationError]
    @app.exception_handler(RequestValidationError)
    async def invalid(request, error):
        if getattr(request.scope.get('route'), 'path', None) in CHAT_ROUTES:
            return chat_problem(request.scope, 'invalid_input')
        return await previous_invalid(request, error)

    async def arguments(request: Request, body: ChatStartInput):
        try:
            return parse_chat_input((await request.body()).decode('utf-8'))
        except UnicodeError:
            raise ChatError('invalid_input') from None

    async def empty_body(request: Request, body: Annotated[dict, Body()]):
        try:
            parse_chat_input((await request.body()).decode('utf-8'), empty=True)
        except UnicodeError:
            raise ChatError('invalid_input') from None

    errors = {status: {'model': ChatProblem, 'content': {'application/problem+json': {}}}
              for status in (403,404,409,422,500,503)}
    def response(value):
        pending = value['run_status'] in {'running','closing','recovery_required'}
        return JSONResponse(value, status_code=202 if pending else 200,
            headers={'Location': RUN_ROUTE.format(document_id=value['document_id'], run_id=value['run_id'])})

    @app.post(START_ROUTE, response_model=ChatRunState,
              responses={**errors, 202: {'model': ChatRunState}})
    def start(document_id: UUID, request: Request, value: Annotated[dict, Depends(arguments)]):
        return response(request.app.state.jd_queries.chat.start(str(document_id), value))

    @app.get(RUN_ROUTE, response_model=ChatRunState, responses=errors)
    def status(document_id: UUID, run_id: UUID, request: Request):
        return request.app.state.jd_queries.chat.status(str(document_id), str(run_id))

    @app.post(CANCEL_ROUTE, response_model=ChatRunState,
              responses={**errors, 202: {'model': ChatRunState}})
    def cancel(document_id: UUID, run_id: UUID, request: Request, _: Annotated[None, Depends(empty_body)]):
        return response(request.app.state.jd_queries.chat.cancel(str(document_id), str(run_id)))

    @app.post(RECOVER_ROUTE, response_model=ChatRunState,
              responses={**errors, 202: {'model': ChatRunState}})
    def recover(document_id: UUID, run_id: UUID, request: Request, _: Annotated[None, Depends(empty_body)]):
        return response(request.app.state.jd_queries.chat.recover(str(document_id), str(run_id)))

    @app.get(HISTORY_ROUTE, response_model=ChatHistoryPage, responses=errors)
    def messages(document_id: UUID, request: Request,
                 cursor: Annotated[str | None, Query(min_length=1, max_length=4096)] = None,
                 limit: Annotated[int, Query(ge=1, le=50)] = 50):
        return request.app.state.jd_queries.chat.messages(str(document_id), cursor=cursor, limit=limit)

    @app.get(CHANGES_ROUTE, response_model=ChatRunChangePage, responses=errors)
    def changes(document_id: UUID, run_id: UUID, request: Request,
                cursor: Annotated[str | None, Query(min_length=1, max_length=4096)] = None):
        return request.app.state.jd_queries.chat.changes(str(document_id), str(run_id), cursor=cursor)

    previous_openapi = app.openapi
    def chat_openapi():
        schema = previous_openapi()
        schema['components']['schemas']['ChatRunChangePage']['allOf'] = run_change_openapi_conditions()
        for path, method in ((START_ROUTE,'post'),(RUN_ROUTE,'get'),(CANCEL_ROUTE,'post'),
                             (RECOVER_ROUTE,'post'),(HISTORY_ROUTE,'get'),(CHANGES_ROUTE,'get')):
            for status in errors:
                content = schema['paths'][path][method]['responses'][str(status)]['content']
                if 'application/json' in content:
                    content['application/problem+json'] = content.pop('application/json')
        return schema
    app.openapi = chat_openapi
    return app
