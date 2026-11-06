"""HTTP 組裝與不洩漏輸入資料的錯誤回應。"""

from functools import partial

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.middleware.base import RequestResponseEndpoint
from starlette.types import Lifespan

from caliburn.shared.presentation.api.diagnostics import log_http_failure
from caliburn.shared.presentation.api.errors import (
    http_exception_error,
    request_validation_error,
)
from caliburn.shared.presentation.api.schemas import ErrorDetail, ErrorResponse


def build_http_app(
    router: APIRouter,
    *,
    title: str = "Caliburn",
    public_validation_fields: frozenset[str] = frozenset(),
    lifespan: Lifespan[FastAPI] | None = None,
) -> FastAPI:
    app = FastAPI(
        title=title,
        lifespan=lifespan,
        responses={
            400: {
                "model": ErrorResponse,
                "description": "Request body decoding failed",
            },
            422: {"model": ErrorResponse, "description": "Invalid request"},
            500: {
                "model": ErrorResponse,
                "description": "Internal error; outcome may be unknown",
                "headers": {
                    "X-Request-ID": {
                        "description": "故障日誌識別，非重試或恢復憑證",
                        "schema": {"type": "string"},
                    }
                },
            },
        },
    )
    app.add_exception_handler(HTTPException, http_exception_error)
    app.add_exception_handler(
        RequestValidationError,
        partial(
            request_validation_error, public_validation_fields=public_validation_fields
        ),
    )

    @app.middleware("http")
    async def protect_internal_errors(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as error:
            request_id = log_http_failure(request, error)
            return JSONResponse(
                status_code=500,
                content=ErrorResponse(
                    detail=ErrorDetail(code="internal_error")
                ).model_dump(mode="json", exclude_none=True),
                headers={"X-Request-ID": request_id},
            )

    app.include_router(router)
    return app
