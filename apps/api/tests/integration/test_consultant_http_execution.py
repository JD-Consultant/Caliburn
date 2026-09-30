"""HTTP admission starts the durable consultant without a second, UI-owned model loop."""

import asyncio
import time
from uuid import uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient

from caliburn.bootstrap import create_app
from caliburn.settings import DatabaseSettings, ModelSettings, Settings
from tests.unit.test_response_loop import response_at

pytestmark = pytest.mark.postgres


def create_file(client: TestClient) -> str:
    return client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "端到端訪談", "employee_name": "合成"},
    ).json()["job_file_id"]


def test_unconfigured_model_does_not_accept_an_unrunnable_turn(database_settings) -> None:
    with TestClient(
        create_app(Settings(database=database_settings)),
        base_url="http://127.0.0.1:8100",
        headers={"Origin": "http://127.0.0.1:8100"},
        backend_options={"loop_factory": asyncio.SelectorEventLoop},
    ) as client:
        file_id = create_file(client)
        response = client.post(
            f"/api/job-files/{file_id}/inputs",
            json={"command_id": str(uuid4()), "text": "我管理庫存"},
        )
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "model_not_configured"


def test_http_input_reaches_saved_formal_answer(
    database_settings: DatabaseSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from caliburn.adapters.openai_responses import create_responses_client

    model_calls = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 500}
            )
        model_calls.append(request)
        response = response_at(1, final=True, tools=0).model_dump(mode="json")
        response["service_tier"] = "default"
        response["output"][1]["content"][0]["text"] = "最近一次盤點，您負責哪些部分？"
        return httpx2.Response(200, json=response)

    def synthetic_client(**kwargs):
        return create_responses_client(
            **kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond))
        )

    monkeypatch.setattr("caliburn.bootstrap.create_responses_client", synthetic_client)
    with TestClient(
        create_app(Settings(database=database_settings, model=ModelSettings(api_key="synthetic"))),
        base_url="http://127.0.0.1:8100",
        headers={"Origin": "http://127.0.0.1:8100"},
        backend_options={"loop_factory": asyncio.SelectorEventLoop},
    ) as client:
        file_id = create_file(client)
        submitted = client.post(
            f"/api/job-files/{file_id}/inputs",
            json={"command_id": str(uuid4()), "text": "我管理庫存"},
        )
        assert submitted.status_code == 202
        execution_id = submitted.json()["execution_id"]
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            status = client.get(f"/api/job-files/{file_id}/consultant-turns/{execution_id}")
            assert status.status_code == 200
            result = status.json()
            if result["status"] != "active":
                break
            time.sleep(0.05)
        else:
            pytest.fail("The accepted consultant did not finish")
        assert result["status"] == "completed", result
        assert len(model_calls) == 1
        history = client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]
        assert history[-1]["interview_text"] == "最近一次盤點，您負責哪些部分？"
        assert [message["interview_sequence"] for message in history] == [1, 2, 3]


def test_known_provider_rejection_finishes_failed_without_formalizing_input(
    database_settings: DatabaseSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from caliburn.adapters.openai_responses import create_responses_client

    calls = []

    def respond(request):
        calls.append(request)
        return httpx2.Response(
            401, json={"error": {"message": "synthetic private detail", "type": "invalid_api_key"}}
        )

    def synthetic_client(**kwargs):
        return create_responses_client(
            **kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond))
        )

    monkeypatch.setattr("caliburn.bootstrap.create_responses_client", synthetic_client)
    with TestClient(
        create_app(Settings(database=database_settings, model=ModelSettings(api_key="synthetic"))),
        base_url="http://127.0.0.1:8100",
        headers={"Origin": "http://127.0.0.1:8100"},
        backend_options={"loop_factory": asyncio.SelectorEventLoop},
    ) as client:
        file_id = create_file(client)
        submitted = client.post(
            f"/api/job-files/{file_id}/inputs",
            json={"command_id": str(uuid4()), "text": "尚未完成的合成輸入"},
        ).json()
        path = f"/api/job-files/{file_id}/consultant-turns/{submitted['execution_id']}"
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            status = client.get(path).json()
            if status["status"] != "active":
                break
            time.sleep(0.05)
        assert status["status"] == "failed"
        assert len(calls) == 1  # Rejected credentials are not transient retry work.
        assert "synthetic private detail" not in str(status)
        history = client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]
        assert len(history) == 1
