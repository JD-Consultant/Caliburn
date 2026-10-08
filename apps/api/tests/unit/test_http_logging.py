"""HTTP 日誌只記伺服器產生的識別與路由樣板，不記使用者原始 URL。"""

import json
import logging
from uuid import UUID

from fastapi.testclient import TestClient
from starlette.responses import StreamingResponse

from caliburn.adapters.logging import SafeJsonFormatter
from caliburn.bootstrap import create_app
from caliburn.settings import Settings


def test_http_response_can_be_correlated_without_logging_request_secrets(caplog):
    caplog.set_level(logging.INFO)
    app = create_app(Settings())
    with TestClient(app, base_url="http://127.0.0.1:8100") as client:
        result = client.get(
            "/api/health?secret=private-data", headers={"X-Request-ID": "untrusted"}
        )
        missing = client.get("/private-data?key=secret")
    request_id = result.headers.get("x-request-id")
    assert request_id is not None
    UUID(request_id)
    assert request_id != missing.headers.get("x-request-id")
    records = [
        json.loads(SafeJsonFormatter().format(record))
        for record in caplog.records
        if record.name == "caliburn.transport.http.logging"
    ]
    assert len(records) == 2
    assert records[0]["http_request_id"] == request_id
    assert records[0]["route"] == "/api/health"
    assert records[0]["http_status"] == result.status_code
    assert records[0]["duration_ms"] >= 0
    assert "route" not in records[1]
    assert "private-data" not in json.dumps(records)
    assert "untrusted" not in json.dumps(records)


def test_unhandled_failure_keeps_request_id_and_http_status(caplog):
    caplog.set_level(logging.INFO)
    app = create_app(Settings())

    @app.get("/test-error")
    async def broken():
        raise ValueError("private-data")

    with TestClient(app, base_url="http://127.0.0.1:8100", raise_server_exceptions=False) as client:
        result = client.get("/test-error")
    assert result.status_code == 500
    assert result.text == "Internal Server Error"
    request_id = result.headers.get("x-request-id")
    assert request_id is not None
    records = [
        record for record in caplog.records if record.name == "caliburn.transport.http.logging"
    ]
    assert len(records) == 1
    payload = json.loads(SafeJsonFormatter().format(records[0]))
    assert payload["http_request_id"] == request_id
    assert payload["http_status"] == 500
    assert payload["outcome"] == "failed"
    assert payload["failure_kind"] == "ValueError"
    assert "private-data" not in json.dumps(payload)


def test_failure_after_stream_start_preserves_sent_status(caplog):
    caplog.set_level(logging.INFO)
    app = create_app(Settings())

    @app.get("/test-stream-error")
    async def broken_stream():
        async def chunks():
            yield "first chunk"
            raise ValueError("private-data")

        return StreamingResponse(chunks())

    with TestClient(app, base_url="http://127.0.0.1:8100", raise_server_exceptions=False) as client:
        result = client.get("/test-stream-error")
    assert result.status_code == 200
    assert result.headers.get("x-request-id") is not None
    records = [
        record for record in caplog.records if record.name == "caliburn.transport.http.logging"
    ]
    assert len(records) == 1
    assert json.loads(SafeJsonFormatter().format(records[0]))["http_status"] == 200
