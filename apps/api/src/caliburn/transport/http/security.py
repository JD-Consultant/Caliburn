"""Loopback HTTP boundary, not authentication or a remote deployment policy.

Install once with ``app.add_middleware(LocalHttpSecurityMiddleware)``. Keep the
server bound to loopback; GET/HEAD/OPTIONS routes must remain side-effect free.
Vite forwards /api to port 8100 while the browser's Origin stays at port 5173.
No CORS middleware is needed for that same-origin proxy arrangement.
"""

from starlette.datastructures import Headers, MutableHeaders
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_LOCAL_HOSTS = ("127.0.0.1", "localhost", "[::1]")
_LOCAL_ORIGINS = frozenset(
    {
        "http://127.0.0.1:8100",
        "http://localhost:8100",
        "http://[::1]:8100",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://[::1]:5173",
    }
)
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_FETCH_SITES = frozenset({"same-origin", "same-site", "cross-site", "none"})


class LocalHttpSecurityMiddleware:
    """Reuse Starlette Host parsing, then enforce local browser provenance.

    Unsafe requests require an exact local Origin or same-origin Fetch Metadata.
    A CLI without browser provenance may send application/json; a bodyless CLI
    control can instead supply an allowed Origin. Never infer trust from client
    IP, User-Agent or forwarded headers. This is not protection against a local
    process that can forge headers, or script running in the trusted UI origin.
    """

    def __init__(self, app: ASGIApp, *, dev_origin: str | None = None) -> None:
        self._app = app
        # Settings validates the optional origin at startup. Keep trust per app,
        # never mutate global defaults when an isolated test server is created.
        # Browser Origin serialization omits the default HTTP port.
        if dev_origin is not None:
            dev_origin = dev_origin.removesuffix(":80")
        self._allowed_origins = (
            _LOCAL_ORIGINS | {dev_origin} if dev_origin is not None else _LOCAL_ORIGINS
        )
        self._host_guard = TrustedHostMiddleware(
            self._check_request, allowed_hosts=_LOCAL_HOSTS, www_redirect=False
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and len(Headers(scope=scope).getlist("host")) != 1:
            await PlainTextResponse("Invalid host header", status_code=400)(scope, receive, send)
            return

        async def send_protected(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                media_type = headers.get("content-type", "").partition(";")[0].strip().lower()
                if media_type == "text/html":
                    # A separate policy composes with any existing CSP rather than weakening it.
                    headers.append("Content-Security-Policy", "frame-ancestors 'none'")
            await send(message)

        await self._host_guard(scope, receive, send_protected)

    async def _check_request(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and not _request_allowed(
            Headers(scope=scope), scope["method"], self._allowed_origins
        ):
            await PlainTextResponse(
                "Local request provenance required",
                status_code=403,
                headers={"Cache-Control": "no-store", "Vary": "Origin, Sec-Fetch-Site"},
            )(scope, receive, send)
            return
        await self._app(scope, receive, send)


def _request_allowed(headers: Headers, method: str, allowed_origins: frozenset[str]) -> bool:
    origins = headers.getlist("origin")
    if len(origins) > 1 or (origins and origins[0] not in allowed_origins):
        return False
    if method in _SAFE_METHODS:
        return True

    sites = headers.getlist("sec-fetch-site")
    if len(sites) > 1 or (sites and sites[0] not in _FETCH_SITES):
        return False
    if sites == ["cross-site"]:
        return False
    if len(headers.getlist("content-type")) > 1:
        return False
    if origins or sites == ["same-origin"]:
        return True

    # No browser signals is a CLI compatibility path, not a blanket exemption.
    # Simple cross-site forms cannot set application/json, and cross-site fetch
    # needs a preflight that this application does not grant. Partial browser
    # signals (including Referer) fail closed instead of taking this fallback.
    if "referer" in headers or any(name.startswith("sec-fetch-") for name in headers):
        return False
    media_type = headers.get("content-type", "").partition(";")[0].strip().lower()
    return media_type == "application/json"
