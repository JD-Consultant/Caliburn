"""The provider credential lives only in the Authorization header of a live request.

A synthetic key is used everywhere; nothing here reads a real credential. The scan looks at
every text, JSON and bytea column of the application schema, which includes the LangGraph
checkpoint tables that keep the native history.
"""

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import httpx2
import psycopg
import pytest
from fastapi.testclient import TestClient
from openai import AsyncOpenAI
from psycopg import sql

from caliburn.app_composition import AppComposition
from caliburn.bootstrap import create_app
from caliburn.settings import DatabaseSettings, ModelSettings, Settings
from tests.fixtures.response_transport import response_http_reply
from tests.unit.test_response_loop import response_at

pytestmark = pytest.mark.postgres

SECRET = "sk-caliburn-synthetic-0123456789abcdefghijklmnop"
# A masked echo, as some providers return, still identifies the account.
FRAGMENTS = (SECRET, SECRET[-12:])
STORED_TYPES = {"text", "character varying", "json", "jsonb", "bytea", "name"}


def stored_secrets(connection: psycopg.Connection, schema: str) -> list[str]:
    """Return table.column names whose stored value contains any fragment of the key."""
    columns = connection.execute(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = %s",
        (schema,),
    ).fetchall()
    found = []
    for table, column, data_type in columns:
        if data_type not in STORED_TYPES:
            continue
        name = sql.Identifier(column)
        value = sql.SQL("encode({}, 'escape')" if data_type == "bytea" else "{}::text").format(name)
        for fragment in FRAGMENTS:
            query = sql.SQL("SELECT EXISTS (SELECT 1 FROM {}.{} WHERE position(%s IN {}) > 0)")
            hit = connection.execute(
                query.format(sql.Identifier(schema), sql.Identifier(table), value), (fragment,)
            ).fetchone()
            if hit and hit[0]:
                found.append(f"{table}.{column}")
                break
    return found


def test_the_scan_sees_a_secret_in_every_kind_of_stored_column(
    database_connection: psycopg.Connection, database_settings: DatabaseSettings
) -> None:
    database_connection.execute("CREATE TABLE plant (t text, j jsonb, b bytea, n integer)")
    database_connection.execute(
        "INSERT INTO plant VALUES (%s, %s, %s, 1)",
        ("prefix " + SECRET, json.dumps({"nested": [f"x{SECRET[-12:]}y"]}), SECRET.encode()),
    )
    assert sorted(stored_secrets(database_connection, database_settings.schema)) == [
        "plant.b",
        "plant.j",
        "plant.t",
    ]


def test_a_clean_schema_has_nothing_to_find(
    database_connection: psycopg.Connection, database_settings: DatabaseSettings
) -> None:
    assert stored_secrets(database_connection, database_settings.schema) == []


def run_turn(
    database_settings: DatabaseSettings,
    respond: Callable[[httpx2.Request], httpx2.Response],
) -> tuple[dict[str, Any], list[str]]:
    from caliburn.adapters.openai_responses import create_responses_client

    def synthetic_client(model: ModelSettings) -> AsyncOpenAI:
        return create_responses_client(
            api_key=model.api_key,
            timeout_seconds=model.request_timeout_seconds,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        )

    seen: list[str] = []
    with TestClient(
        create_app(
            Settings(database=database_settings, model=ModelSettings(api_key=SECRET)),
            composition=AppComposition(create_responses_client=synthetic_client),
        ),
        base_url="http://127.0.0.1:8100",
        headers={"Origin": "http://127.0.0.1:8100"},
        backend_options={"loop_factory": asyncio.SelectorEventLoop},
    ) as client:
        file_id = client.post(
            "/api/job-files",
            json={"command_id": str(uuid4()), "display_name": "憑證隔離", "employee_name": "合成"},
        ).json()["job_file_id"]
        submitted = client.post(
            f"/api/job-files/{file_id}/inputs",
            json={"command_id": str(uuid4()), "text": "我負責庫存盤點"},
        )
        assert submitted.status_code == 202
        path = f"/api/job-files/{file_id}/consultant-turns/{submitted.json()['execution_id']}"
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            status = client.get(path).json()
            if status["status"] != "active":
                break
            time.sleep(0.05)
        else:
            pytest.fail("The accepted consultant did not finish")
        for public in (
            path,
            f"/api/job-files/{file_id}/interviews",
            f"/api/job-files/{file_id}",
            f"/api/job-files/{file_id}/jd/work",
        ):
            response = client.get(public)
            assert response.status_code == 200
            seen.append(response.text)
    return status, seen


def test_a_completed_turn_keeps_the_key_out_of_the_body_the_database_and_public_reads(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    bearers: list[str] = []
    bodies: list[str] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        bearers.append(request.headers.get("authorization", ""))
        bodies.append(request.content.decode())
        if request.url.path.endswith("/input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 500}
            )
        response = response_at(1, final=True, tools=0).model_dump(mode="json")
        response["service_tier"] = "default"
        response["output"][1]["content"][0]["text"] = "盤點時您負責哪一段？"
        return response_http_reply(request, response)

    status, public = run_turn(database_settings, respond)

    assert status["status"] == "completed", status
    assert bearers and all(bearer == f"Bearer {SECRET}" for bearer in bearers)
    assert not [body for body in bodies if any(part in body for part in FRAGMENTS)]
    assert stored_secrets(database_connection, database_settings.schema) == []
    assert not [text for text in public if any(part in text for part in FRAGMENTS)]
    assert not any(part in caplog.text for part in FRAGMENTS)


def test_a_provider_error_that_echoes_the_key_is_not_stored_or_shown(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def respond(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            401,
            json={
                "error": {
                    "message": f"Incorrect API key provided: {SECRET}.",
                    "type": "invalid_request_error",
                    "code": "invalid_api_key",
                }
            },
        )

    status, public = run_turn(database_settings, respond)

    assert status["status"] == "failed", status
    assert not any(part in json.dumps(status, ensure_ascii=False) for part in FRAGMENTS)
    assert stored_secrets(database_connection, database_settings.schema) == []
    assert not [text for text in public if any(part in text for part in FRAGMENTS)]
    assert not any(part in caplog.text for part in FRAGMENTS)
