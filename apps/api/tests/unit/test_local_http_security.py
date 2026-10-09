"""Real ASGI rejection must happen before any endpoint side effect."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from caliburn.transport.http.security import LocalHttpSecurityMiddleware


def test_html_responses_prevent_framing_without_restricting_scripts() -> None:
    app = FastAPI()
    app.add_middleware(LocalHttpSecurityMiddleware)

    @app.get("/")
    def index() -> Response:
        return Response("<html>Local workspace</html>", media_type="text/html")

    with TestClient(app, base_url="http://127.0.0.1:8100") as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-security-policy"] == "frame-ancestors 'none'"


@pytest.fixture
def guarded_client() -> Iterator[tuple[TestClient, list[bytes]]]:
    app = FastAPI()
    app.add_middleware(LocalHttpSecurityMiddleware)
    calls: list[bytes] = []

    @app.api_route("/effect", methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"])
    async def effect(request: Request) -> Response:
        body = await request.body()
        calls.append(body)
        return Response(body, media_type="application/json")

    with TestClient(app, base_url="http://127.0.0.1:8100") as client:
        yield client, calls


@pytest.mark.parametrize(
    "host",
    ["evil.example", "127.0.0.1.evil.example", "testserver", "localhost@evil.example", ""],
)
def test_untrusted_host_rejected_before_route(
    guarded_client: tuple[TestClient, list[bytes]], host: str
) -> None:
    client, calls = guarded_client
    response = client.post("/effect", headers={"Host": host}, json={"change": True})
    assert (response.status_code, calls) == (400, [])


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        "http://localhost:9999",
        "http://127.0.0.1:5173.evil.example",
        "http://localhost:5173/path",
        "http://user@localhost:5173",
        "null",
        "",
    ],
)
def test_untrusted_origin_rejected_before_route(
    guarded_client: tuple[TestClient, list[bytes]], origin: str
) -> None:
    client, calls = guarded_client
    response = client.post("/effect", headers={"Origin": origin}, json={"change": True})
    assert (response.status_code, calls) == (403, [])


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_cross_site_metadata_cannot_be_overridden_by_allowed_origin(
    guarded_client: tuple[TestClient, list[bytes]], method: str
) -> None:
    client, calls = guarded_client
    response = client.request(
        method,
        "/effect",
        headers={"Origin": "http://localhost:5173", "Sec-Fetch-Site": "cross-site"},
        json={"change": True},
    )
    assert (response.status_code, calls) == (403, [])


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Content-Type": "text/plain"},
        {"Content-Type": "application/x-www-form-urlencoded"},
        {"Content-Type": "multipart/form-data; boundary=example"},
        {"Content-Type": "application/json", "Sec-Fetch-Site": "same-site"},
        {"Content-Type": "application/json", "Sec-Fetch-Site": "none"},
        {"Content-Type": "application/json", "Sec-Fetch-Site": "invalid"},
        {"Content-Type": "application/json", "Sec-Fetch-Mode": "cors"},
        {"Content-Type": "application/json", "Referer": "https://evil.example/"},
    ],
)
def test_missing_browser_provenance_cannot_use_simple_request_fallback(
    guarded_client: tuple[TestClient, list[bytes]], headers: dict[str, str]
) -> None:
    client, calls = guarded_client
    response = client.post("/effect", headers=headers, content=b"")
    assert (response.status_code, calls) == (403, [])


@pytest.mark.parametrize(
    ("host", "origin", "site"),
    [
        ("127.0.0.1:8100", "http://127.0.0.1:8100", "same-origin"),
        ("localhost:5173", "http://localhost:5173", "same-origin"),
        ("127.0.0.1:8100", "http://localhost:5173", "same-origin"),
        ("127.0.0.1:8100", "http://127.0.0.1:5173", "same-site"),
        ("[::1]:8100", "http://[::1]:5173", "same-site"),
    ],
)
def test_local_origin_and_vite_proxy_shape_keep_body_unchanged(
    guarded_client: tuple[TestClient, list[bytes]], host: str, origin: str, site: str
) -> None:
    client, calls = guarded_client
    body = b'{"text":"user data"}'
    response = client.post(
        "/effect",
        headers={"Host": host, "Origin": origin, "Sec-Fetch-Site": site},
        content=body,
    )
    assert (response.status_code, response.content, calls) == (200, body, [body])


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "http://localhost:5173"},
        {"Sec-Fetch-Site": "same-origin"},
        {"Content-Type": "application/json"},
        {"Content-Type": "application/json; charset=utf-8"},
    ],
)
def test_bodyless_controls_and_cli_have_explicit_safe_paths(
    guarded_client: tuple[TestClient, list[bytes]], headers: dict[str, str]
) -> None:
    client, calls = guarded_client
    response = client.post("/effect", headers=headers)
    assert (response.status_code, calls) == (200, [b""])


@pytest.mark.parametrize(
    ("headers", "status"),
    [
        ([("Host", "127.0.0.1:8100"), ("Host", "evil.example")], 400),
        ([("Origin", "http://localhost:5173"), ("Origin", "https://evil.example")], 403),
        ([("Sec-Fetch-Site", "same-origin"), ("Sec-Fetch-Site", "cross-site")], 403),
        ([("Content-Type", "application/json"), ("Content-Type", "text/plain")], 403),
    ],
)
def test_ambiguous_security_headers_are_rejected(
    guarded_client: tuple[TestClient, list[bytes]], headers: list[tuple[str, str]], status: int
) -> None:
    client, calls = guarded_client
    response = client.post("/effect", headers=headers, content=b"{}")
    assert (response.status_code, calls) == (status, [])


def test_forwarded_headers_cannot_make_host_or_origin_trusted(
    guarded_client: tuple[TestClient, list[bytes]],
) -> None:
    client, calls = guarded_client
    response = client.post(
        "/effect",
        headers={
            "Host": "evil.example",
            "Origin": "https://evil.example",
            "X-Forwarded-Host": "localhost:8100",
            "Forwarded": "host=localhost:8100;proto=http",
        },
        json={},
    )
    assert (response.status_code, calls) == (400, [])


def test_preflight_does_not_grant_cross_origin_permission(
    guarded_client: tuple[TestClient, list[bytes]],
) -> None:
    client, calls = guarded_client
    response = client.options(
        "/effect",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert "access-control-allow-origin" not in response.headers
    assert calls == []


def test_readonly_cli_needs_only_local_host(
    guarded_client: tuple[TestClient, list[bytes]],
) -> None:
    client, calls = guarded_client
    assert client.get("/effect").status_code == 200
    assert calls == [b""]


def test_untrusted_explicit_origin_is_not_ignored_on_reads(
    guarded_client: tuple[TestClient, list[bytes]],
) -> None:
    client, calls = guarded_client
    response = client.get("/effect", headers={"Origin": "null"})
    assert (response.status_code, calls) == (403, [])


@pytest.mark.parametrize(
    ("headers", "status"),
    [
        ([], 400),
        ([(b"host", b"localhost:8100"), (b"origin", b"null")], 403),
        ([(b"host", b"localhost:8100"), (b"sec-fetch-site", b"cross-site")], 403),
    ],
)
async def test_rejection_does_not_consume_body_or_call_downstream(
    headers: list[tuple[bytes, bytes]], status: int
) -> None:
    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        pytest.fail("Rejected request reached downstream app")

    async def receive() -> Message:
        pytest.fail("Rejected request body was consumed")

    messages: list[Message] = []

    async def send(message: Message) -> None:
        messages.append(message)

    await LocalHttpSecurityMiddleware(downstream)(
        {"type": "http", "method": "POST", "headers": headers}, receive, send
    )
    assert messages[0]["status"] == status


async def test_asgi_body_and_stream_chunks_pass_through_without_buffering() -> None:
    requests: list[Message] = [
        {"type": "http.request", "body": b"first", "more_body": True},
        {"type": "http.request", "body": b"last", "more_body": False},
    ]
    responses: list[Message] = []
    received = 0

    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        while True:
            message = await receive()
            await send(
                {
                    "type": "http.response.body",
                    "body": message["body"],
                    "more_body": message["more_body"],
                }
            )
            if not message["more_body"]:
                break

    async def receive() -> Message:
        nonlocal received
        # Response start, then each previous chunk must already be delivered.
        assert len(responses) == received + 1
        message = requests[received]
        received += 1
        return message

    async def send(message: Message) -> None:
        responses.append(message)

    await LocalHttpSecurityMiddleware(downstream)(
        {
            "type": "http",
            "method": "POST",
            "headers": [(b"host", b"localhost:8100"), (b"content-type", b"application/json")],
        },
        receive,
        send,
    )
    assert [message["body"] for message in responses[1:]] == [b"first", b"last"]
    assert responses[-1]["more_body"] is False


def test_real_bootstrap_keeps_offline_health_and_blocks_bad_host() -> None:
    from caliburn.bootstrap import create_app
    from caliburn.settings import Settings

    app = create_app(Settings())
    with TestClient(app, base_url="http://127.0.0.1:8100") as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        assert client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
        assert client.post("/api/job-files", headers={"Origin": "null"}, json={}).status_code == 403
