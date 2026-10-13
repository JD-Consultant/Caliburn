"""HTTP 驗證失敗只回固定錯誤碼，不外送輸入、例外或不可信欄位路徑。"""

from fastapi import Request
from pydantic import StrictStr
from starlette.responses import JSONResponse

from caliburn.transport.http.models.common import HttpModel


class HttpErrorDetail(HttpModel):
    code: StrictStr


class HttpErrorResponse(HttpModel):
    detail: HttpErrorDetail


async def invalid_request_response(_request: Request, _error: Exception) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": {"code": "invalid_http_request"}})
