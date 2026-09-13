"""Catalog HTTP adapter on the existing owned manual App lifespan."""
from dataclasses import dataclass
from http import HTTPStatus
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Body, Depends, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from .catalog_service import CatalogError, CatalogService, parse_catalog
from .generated.catalog_http import (CatalogDocument, CatalogPage, CatalogCreateInput,
    CatalogCreationResult, CatalogCreationLookup, CatalogMetadataInput, CatalogProblem)
from .manual_api import ManualBoundary, ManualServices, create_manual_app

CATALOG_ROUTE = "/api/documents"
LOOKUP_ROUTE = "/api/document-creations/lookup"
METADATA_ROUTE = "/api/documents/{document_id}/metadata"
CATALOG_ROUTES = frozenset({CATALOG_ROUTE, LOOKUP_ROUTE, METADATA_ROUTE})
MERGE_PATCH = "application/merge-patch+json"


@dataclass(frozen=True)
class CatalogServices(ManualServices):
    catalog: CatalogService


_ERRORS = {
    "invalid_input": (422, "correct_input", "請檢查輸入內容。"),
    "unsupported_patch": (415, "correct_input", "請使用 App 支援的修改格式。"),
    "document_missing": (404, "reread", "找不到這份文件，請重新查看列表。"),
    "creation_conflict": (409, "retry_same_creation", "請使用原建立請求的編號與名稱查回文件。"),
    "dataset_changed": (409, "reread", "目前開啟的資料已更換，請重新查看文件列表。"),
    "precondition_required": (428, "reread", "請先讀取目前文件資訊後再操作。"),
    "metadata_changed": (412, "reread", "文件資訊已變更，請重新查看後再決定。"),
    "busy": (409, "wait", "這份文件仍有修改尚未結束，請稍後再試。"),
    "service_unavailable": (503, "wait", "服務目前未就緒，請稍後查看狀態。"),
    "write_unconfirmed": (503, "reread", "目前無法確認保存結果，請先查看目前文件資訊。"),
    "origin_not_allowed": (403, "stop", "請從本機 App 的工作畫面操作。"),
}


def catalog_problem(scope, code="service_unavailable", *, internal=False):
    code = code if type(code) is str and code in _ERRORS else "service_unavailable"
    status, action, detail = _ERRORS[code]
    if code == "write_unconfirmed" and getattr(scope.get("route"), "path", None) == CATALOG_ROUTE:
        action, detail = "retry_same_creation", "目前無法確認建立結果，請用原請求查回；不要另建新請求。"
    if internal:
        status = 500
    value = CatalogProblem(type="about:blank", title=HTTPStatus(status).phrase,
        status=status, detail=detail, instance=f"urn:uuid:{scope['jd.request_id']}",
        code=code, next_action=action).model_dump(mode="json")
    return JSONResponse(value, status_code=status, media_type="application/problem+json",
                        headers={"Accept-Patch": MERGE_PATCH} if code == "unsupported_patch" else None)


class CatalogBoundary(ManualBoundary):
    routes = ManualBoundary.routes | CATALOG_ROUTES
    origin_problem = staticmethod(catalog_problem)

    def failure_response(self, scope, error):
        if getattr(scope.get("route"), "path", None) not in CATALOG_ROUTES:
            return super().failure_response(scope, error)
        return catalog_problem(scope, error.code) if isinstance(error, CatalogError) else catalog_problem(scope, internal=True)


def create_catalog_app(resources, *, allowed_origins,
                       _boundary_factory=CatalogBoundary,
                       _allowed_headers=("Content-Type", "If-Match")):
    app = create_manual_app(resources, allowed_origins=allowed_origins,
        _boundary_factory=_boundary_factory, _allowed_methods=("GET", "POST", "PATCH"),
        _allowed_headers=_allowed_headers, _expose_headers=("X-Request-ID", "ETag", "Location"))
    previous_invalid = app.exception_handlers[RequestValidationError]

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, error):
        if getattr(request.scope.get("route"), "path", None) in CATALOG_ROUTES:
            return catalog_problem(request.scope, "invalid_input")
        return await previous_invalid(request, error)

    async def creation_arguments(request: Request, body: CatalogCreateInput):
        try:
            return parse_catalog((await request.body()).decode("utf-8"), CatalogCreateInput)
        except UnicodeError:
            raise CatalogError("invalid_input") from None

    async def metadata_arguments(request: Request,
            body: Annotated[CatalogMetadataInput, Body(media_type=MERGE_PATCH)]):
        content_types = request.headers.getlist("content-type")
        if len(content_types) != 1 or content_types[0].split(";", 1)[0].strip().lower() != MERGE_PATCH:
            raise CatalogError("unsupported_patch")
        if len(request.headers.getlist("if-match")) > 1:
            raise CatalogError("invalid_input")
        try:
            return parse_catalog((await request.body()).decode("utf-8"), CatalogMetadataInput)
        except UnicodeError:
            raise CatalogError("invalid_input") from None

    errors = {status: {"model": CatalogProblem, "content": {"application/problem+json": {}}}
              for status in (403, 404, 409, 412, 415, 422, 428, 500, 503)}

    @app.get(CATALOG_ROUTE, response_model=CatalogPage, responses=errors)
    def documents(request: Request, archived: Literal["false", "true", "all"] = "false",
                  after: UUID | None = None, limit: Annotated[int, Query(ge=1, le=100)] = 50):
        return request.app.state.jd_queries.catalog.list(
            archived={"false": False, "true": True, "all": None}[archived],
            after=str(after) if after else None, limit=limit)

    @app.post(CATALOG_ROUTE, response_model=CatalogCreationResult, responses=errors)
    def create(request: Request, envelope: Annotated[dict, Depends(creation_arguments)]):
        # 200 also describes original creation retries; do not imply a new row.
        return request.app.state.jd_queries.catalog.create(envelope)

    @app.post(LOOKUP_ROUTE, response_model=CatalogCreationLookup, responses=errors)
    def lookup(request: Request, envelope: Annotated[dict, Depends(creation_arguments)]):
        return request.app.state.jd_queries.catalog.lookup(envelope)

    def representation(service, document_id, value):
        return JSONResponse(value, headers={"ETag": service.etag(value),
            "Content-Location": METADATA_ROUTE.format(document_id=document_id), "Accept-Patch": MERGE_PATCH})

    @app.get(METADATA_ROUTE, response_model=CatalogDocument, responses=errors)
    def metadata(document_id: UUID, request: Request):
        service = request.app.state.jd_queries.catalog
        return representation(service, str(document_id), service.get(str(document_id)))

    @app.patch(METADATA_ROUTE, response_model=CatalogDocument, responses=errors)
    def update(document_id: UUID, request: Request,
               envelope: Annotated[dict, Depends(metadata_arguments)],
               if_match: Annotated[str | None, Header()] = None):
        service = request.app.state.jd_queries.catalog
        value = service.update(str(document_id), if_match, envelope,
            kind="title" if "title" in envelope else "archive")
        return representation(service, str(document_id), value)

    previous_openapi = app.openapi
    def catalog_openapi():
        schema = previous_openapi()
        for path, method in ((CATALOG_ROUTE, "get"), (CATALOG_ROUTE, "post"),
                             (LOOKUP_ROUTE, "post"), (METADATA_ROUTE, "get"), (METADATA_ROUTE, "patch")):
            for status in errors:
                content = schema["paths"][path][method]["responses"][str(status)]["content"]
                if "application/json" in content:
                    content["application/problem+json"] = content.pop("application/json")
        return schema
    app.openapi = catalog_openapi
    return app
