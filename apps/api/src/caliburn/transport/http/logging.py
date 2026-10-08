"""以 ASGI 邊界關聯 HTTP 事件，不讀取或複製請求／回應正文。"""

import asyncio
import logging
from time import perf_counter
from uuid import UUID, uuid4

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from caliburn.adapters.logging import bind_log_context

_LOG = logging.getLogger(__name__)


async def unhandled_error_response(request: Request, _error: Exception) -> PlainTextResponse:
    """ServerErrorMiddleware 在外層產生 500 時，沿用同次請求的安全關聯 ID。"""
    request_id = getattr(request.state, "http_request_id", None) or str(uuid4())
    return PlainTextResponse(
        "Internal Server Error", status_code=500, headers={"X-Request-ID": request_id}
    )


class HttpLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = str(uuid4())
        scope.setdefault("state", {})["http_request_id"] = request_id
        started = perf_counter()
        status: int | None = None
        outcome = "responded"
        failure_kind: str | None = None

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        with bind_log_context(http_request_id=request_id):
            try:
                await self.app(scope, receive, send_with_id)
            except asyncio.CancelledError:
                outcome = "cancelled"
                raise
            except Exception as error:
                outcome = "failed"
                failure_kind = type(error).__name__
                if status is None:
                    status = 500
                raise
            finally:
                fields: dict[str, object] = {
                    "http_request_id": request_id,
                    "method": scope["method"],
                    "http_status": status,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                    "outcome": outcome,
                }
                # 只接受路由樣板及已解析 UUID；404 原始路徑可能含私人資料。
                route = getattr(scope.get("route"), "path", None)
                if isinstance(route, str):
                    fields["route"] = route
                for name in ("job_file_id", "execution_id"):
                    value = scope.get("path_params", {}).get(name)
                    if isinstance(value, UUID):
                        fields[name] = value
                    elif isinstance(value, str):
                        try:
                            fields[name] = UUID(value)
                        except ValueError:
                            pass
                if failure_kind is not None:
                    fields["failure_kind"] = failure_kind
                _LOG.log(
                    logging.ERROR if outcome == "failed" else logging.INFO,
                    "http.request_finished",
                    extra=fields,
                )
