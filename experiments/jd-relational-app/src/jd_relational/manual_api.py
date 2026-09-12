"""Manual HTTP entry points over the same queries and owned JD writer.

The supplied lifespan owns resources. A request observes an operation; it never
owns, cancels, or establishes the death of its writer. Browser source validation
happens before reading the body and before any operation can be admitted.
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from functools import partial
from http import HTTPStatus
from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import Body, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from .generated.http_results import HttpProblem
from .generated.manual_http import (
    ManualDocumentState, ManualOperationState, ManualProblem, ManualSaveInput,
)
from .generated.results import MutationResult
from .http_results import project_result
from .manual_service import ManualError, ManualService, parse_manual_save
from .query_api import QueryBoundary, QueryServices, create_query_app, _problem
from .transport import REQUEST_LIMIT


EDIT_ROUTE = "/api/documents/{document_id}/jd/edits"
STATE_ROUTE = "/api/documents/{document_id}/jd/state"
OPERATION_ROUTE = "/api/documents/{document_id}/jd/operations/{operation_id}"
RECOVER_ROUTE = OPERATION_ROUTE + "/recover"
MANUAL_ROUTES = frozenset({EDIT_ROUTE, STATE_ROUTE, OPERATION_ROUTE, RECOVER_ROUTE})


@dataclass(frozen=True)
class ManualServices(QueryServices):
    manual: ManualService


_ERRORS = {
    "invalid_input": (422, "correct_input", "請檢查輸入內容。"),
    "invalid_ref": (422, "reread", "請重新讀取目前內容後再編輯。"),
    "target_missing": (404, "reread", "找不到指定的文件或內容。"),
    "stale_view": (409, "reread", "內容已變更，請重新讀取後再編輯。"),
    "operation_conflict": (409, "lookup_operation", "這個操作編號已對應其他修改，請先查回原操作。"),
    "busy": (409, "wait", "目前仍有操作尚未結束，請稍後查看狀態。"),
    "service_unavailable": (503, "lookup_operation", "目前無法確認操作狀態，請先查回原操作。"),
    "selection_not_available": (422, "stop", "此版本尚未提供選取文字修改。"),
    "origin_not_allowed": (403, "stop", "請從本機 App 的工作畫面操作。"),
}


def manual_problem(scope, code="service_unavailable", *, internal=False):
    if type(code) is not str or code not in _ERRORS:
        code = "service_unavailable"
    status, next_action, detail = _ERRORS[code]
    if internal:
        status = 500
    value = ManualProblem(
        type="about:blank", title=HTTPStatus(status).phrase, status=status,
        detail=detail, instance=f"urn:uuid:{scope['jd.request_id']}",
        code=code, next_action=next_action,
    ).model_dump(mode="json")
    return JSONResponse(value, status_code=status, media_type="application/problem+json")


class ManualOriginGate:
    def __init__(self, app, *, allowed_origins):
        self.app, self.allowed_origins = app, frozenset(allowed_origins)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] in {"POST", "PUT", "PATCH", "DELETE"}:
            origins = [value for name, value in scope.get("headers", []) if name.lower() == b"origin"]
            if len(origins) != 1 or origins[0].decode("latin-1") not in self.allowed_origins:
                return await manual_problem(scope, "origin_not_allowed")(scope, receive, send)
        return await self.app(scope, receive, send)


class ManualBoundary(QueryBoundary):
    routes = QueryBoundary.routes | MANUAL_ROUTES
    interrupted_message = "jd_manual_response_interrupted"
    event_name = "jd.http.workspace"
    log_message = "JD workspace request completed"

    def __init__(self, app, *, allowed_origins):
        super().__init__(ManualOriginGate(app, allowed_origins=allowed_origins))

    def failure_response(self, scope, error):
        if getattr(scope.get("route"), "path", None) in QueryBoundary.routes:
            return super().failure_response(scope, error)
        if isinstance(error, ManualError):
            return manual_problem(scope, error.code)
        return manual_problem(scope, internal=True)


def create_manual_app(
    resources: Callable[[], AbstractAsyncContextManager[ManualServices]],
    *, allowed_origins: tuple[str, ...],
) -> FastAPI:
    # This local browser API deliberately requires a single, configured Origin
    # on unsafe methods, including requests from an eventual same-origin UI.
    try:
        if type(allowed_origins) is not tuple or not allowed_origins:
            raise ValueError()
        for origin in allowed_origins:
            if type(origin) is not str:
                raise ValueError()
            url = urlsplit(origin)
            port = url.port
            canonical = f"{url.scheme}://{url.hostname}" + (f":{port}" if port is not None else "")
            if origin != canonical or port is not None and not 1 <= port <= 65535:
                raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("explicit_local_origins_required") from None

    app = create_query_app(
        resources, allowed_origins=allowed_origins, _body_limit=REQUEST_LIMIT,
        _boundary_factory=partial(ManualBoundary, allowed_origins=allowed_origins),
        _allowed_methods=("GET", "POST"),
    )
    app.title = "Caliburn JD workspace"

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, error):
        if getattr(request.scope.get("route"), "path", None) in QueryBoundary.routes:
            return _problem(request.scope, "invalid_input")
        return manual_problem(request.scope, "invalid_input")

    async def save_arguments(request: Request, body: ManualSaveInput):
        try:
            return parse_manual_save((await request.body()).decode("utf-8"))
        except UnicodeError:
            raise ManualError("invalid_input") from None

    async def empty_body(body: Annotated[dict, Body()]):
        if body:
            raise ManualError("invalid_input")

    errors = {
        status: {"model": ManualProblem, "content": {"application/problem+json": {}}}
        for status in (403, 404, 409, 422, 500, 503)
    }
    save_errors = {
        status: {**response, "model": ManualProblem | HttpProblem}
        if status in {404, 409, 422, 500} else response
        for status, response in errors.items()
    }

    @app.post(EDIT_ROUTE, response_model=MutationResult,
              responses={**save_errors, 202: {"model": MutationResult}})
    def save(document_id: UUID, request: Request,
             envelope: Annotated[dict, Depends(save_arguments)]):
        result = request.app.state.jd_queries.manual.save(str(document_id), envelope)
        response = project_result(result, request_id=request.scope["jd.request_id"])
        return JSONResponse(response.body, status_code=response.status_code,
                            media_type=response.media_type, headers=response.headers)

    @app.get(STATE_ROUTE, response_model=ManualDocumentState, responses=errors)
    def state(document_id: UUID, request: Request):
        return request.app.state.jd_queries.manual.status(str(document_id))

    @app.get(OPERATION_ROUTE, response_model=ManualOperationState, responses=errors)
    def operation(document_id: UUID, operation_id: UUID, request: Request):
        return request.app.state.jd_queries.manual.lookup(str(document_id), str(operation_id))

    @app.post(RECOVER_ROUTE, response_model=ManualOperationState, responses=errors)
    def recover(document_id: UUID, operation_id: UUID, request: Request,
                _empty: Annotated[None, Depends(empty_body)]):
        return request.app.state.jd_queries.manual.recover(str(document_id), str(operation_id))

    previous_openapi = app.openapi

    def manual_openapi():
        schema = previous_openapi()
        for path, method in ((EDIT_ROUTE, "post"), (STATE_ROUTE, "get"),
                             (OPERATION_ROUTE, "get"), (RECOVER_ROUTE, "post")):
            for status in errors:
                content = schema["paths"][path][method]["responses"][str(status)]["content"]
                if "application/json" in content:
                    content["application/problem+json"] = content.pop("application/json")
        return schema

    app.openapi = manual_openapi
    return app
