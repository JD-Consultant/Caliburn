"""HTTP A completion triggers real background roles and exposes only their publication."""

import asyncio
import json
import time
from uuid import UUID, uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient

from caliburn.adapters.openai_responses import create_responses_client
from caliburn.bootstrap import create_app
from caliburn.settings import ModelSettings, Settings
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from tests.fixtures.response_transport import response_http_reply
from tests.unit.test_response_loop import response_at

pytestmark = pytest.mark.postgres


def test_completed_notification_publishes_two_layers_and_next_turn_sees_maps(
    database_settings, monkeypatch
):
    requests = []

    def respond(request):
        if request.url.path.endswith("/input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 500}
            )
        payload = json.loads(request.content)
        requests.append(payload)
        number = len(requests)
        call = None
        if number == 1:
            call = ("request_memory_consolidation", {})
        elif number == 3:
            call = (
                "create_work_situation",
                {
                    "title": "月末盘點",
                    "description": "帳物核對",
                    "body": "每月核對庫存。",
                    "interview_references": [2],
                },
            )
        elif number == 5:
            call = (
                "create_work_understanding",
                {
                    "title": "庫存資料維護",
                    "description": "盤點與回報",
                    "body": "核對庫存差異。",
                    "work_situation_references": ["月末盘點"],
                },
            )
        raw = response_at(number, final=call is None, tools=0).model_dump(mode="json")
        raw["service_tier"] = "default"
        if call is not None:
            raw["output"] = [
                {
                    "type": "function_call",
                    "id": f"fc_{number}",
                    "call_id": f"call_{number}",
                    "name": call[0],
                    "arguments": json.dumps(call[1], ensure_ascii=False),
                }
            ]
        else:
            raw["output"][1]["content"][0]["text"] = (
                '{"status":"complete"}' if number in (4, 6) else "遇到庫存差異時怎麼處理？"
            )
        return response_http_reply(request, raw)

    def synthetic_client(**kwargs):
        return create_responses_client(
            **kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond))
        )

    monkeypatch.setattr("caliburn.bootstrap.create_responses_client", synthetic_client)
    app = create_app(Settings(database=database_settings, model=ModelSettings(api_key="synthetic")))
    with TestClient(
        app,
        base_url="http://127.0.0.1:8100",
        headers={"Origin": "http://127.0.0.1:8100"},
        backend_options={"loop_factory": asyncio.SelectorEventLoop},
    ) as client:
        file_id = client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "背景完整旅程",
                "employee_name": "合成",
            },
        ).json()["job_file_id"]
        submitted = client.post(
            f"/api/job-files/{file_id}/inputs",
            json={
                "command_id": str(uuid4()),
                "text": "每月盤點庫存並回報差異。",
            },
        )
        assert submitted.status_code == 202

        async def published():
            return await MemoryCandidateWorkflow(app.state.database.sessions).read_latest_snapshot(
                UUID(file_id)
            )

        assert client.portal is not None
        deadline = time.monotonic() + 12
        snapshot = None
        while time.monotonic() < deadline:
            snapshot = client.portal.call(published)
            if snapshot is not None:
                break
            time.sleep(0.05)
        assert snapshot is not None, "Completed A notification never published background Memory"
        assert snapshot.covered_through_sequence == 2
        assert len(requests) == 6
        history = client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]
        assert [item["interview_sequence"] for item in history] == [1, 2, 3]
        assert "工作理解" not in requests[2]["input"][-1]["content"]

        next_turn = client.post(
            f"/api/job-files/{file_id}/inputs",
            json={
                "command_id": str(uuid4()),
                "text": "差異會再查入出庫單。",
            },
        ).json()
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            result = client.get(
                f"/api/job-files/{file_id}/consultant-turns/{next_turn['execution_id']}"
            ).json()
            if result["status"] != "active":
                break
            time.sleep(0.05)
        assert result["status"] == "completed"
        assert len(requests) == 7
        app_data = json.loads(requests[-1]["input"][-2]["content"])
        assert app_data["work_situation_map"]["items"][0]["target_title"] == "月末盘點"
        assert app_data["work_understanding_map"]["items"][0]["target_title"] == "庫存資料維護"
        assert app_data["interview_read_boundary"]["covered_through_sequence"] == 2
