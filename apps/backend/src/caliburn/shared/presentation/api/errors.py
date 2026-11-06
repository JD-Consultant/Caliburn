"""只輸出安全的 HTTP 錯誤代碼與欄位位置。"""

from fastapi import Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.responses import Response

from caliburn.shared.presentation.api.schemas import (
    ErrorDetail,
    ErrorResponse,
    ValidationIssue,
)

_REQUEST_LOCATIONS = frozenset({"body", "path", "query"})
_SAFE_CODES = {
    "missing",
    "extra_forbidden",
    "string_type",
    "int_parsing",
    "int_type",
    "greater_than_equal",
    "less_than_equal",
    "json_invalid",
    "value_error",
    "model_attributes_type",
    "uuid_parsing",
}


async def http_exception_error(request: Request, exception: Exception) -> Response:
    """框架 400 不回原始解碼訊息，其餘 HTTP 錯誤沿框架處理。"""
    assert isinstance(exception, HTTPException)
    if exception.status_code != 400:
        return await http_exception_handler(request, exception)
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(detail=ErrorDetail(code="invalid_request")).model_dump(
            mode="json", exclude_none=True
        ),
        headers=exception.headers,
    )


def validation_issues(
    exception: RequestValidationError,
    *,
    public_validation_fields: frozenset[str],
) -> list[ValidationIssue]:
    """不序列化 input／ctx／原始訊息或未知欄位名稱。"""
    safe_locations = _REQUEST_LOCATIONS | public_validation_fields
    return [
        ValidationIssue(
            loc=[
                part if isinstance(part, int) or part in safe_locations else "unknown"
                for part in error["loc"]
            ],
            code=error["type"] if error["type"] in _SAFE_CODES else "invalid_value",
        )
        for error in exception.errors()
    ]


async def request_validation_error(
    request: Request,
    exception: Exception,
    *,
    public_validation_fields: frozenset[str],
) -> JSONResponse:
    assert isinstance(exception, RequestValidationError)
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            detail=ErrorDetail(
                code="invalid_request",
                errors=validation_issues(
                    exception, public_validation_fields=public_validation_fields
                ),
            )
        ).model_dump(mode="json", exclude_none=True),
    )
