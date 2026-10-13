"""HTTP A completion triggers real background roles and exposes only their publication."""

import asyncio
import json
import time
from uuid import UUID, uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient

from caliburn.adapters.openai_responses import create_responses_client
from caliburn.app_composition import AppComposition
from caliburn.bootstrap import create_app
from caliburn.settings import ModelSettings, Settings
from caliburn.workflows.work_memory.candidates import MemoryCandidateWorkflow
from tests.fixtures.jd_memory_journey import JourneyModel
from tests.fixtures.response_loop import response_at
from tests.fixtures.response_transport import response_http_reply

pytestmark = pytest.mark.postgres


def test_completed_notification_publishes_two_layers_and_next_turn_sees_maps(database_settings):
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

    def synthetic_client(model):
        return create_responses_client(
            api_key=model.api_key,
            timeout_seconds=model.request_timeout_seconds,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        )

    app = create_app(
        Settings(database=database_settings, model=ModelSettings(api_key="synthetic")),
        composition=AppComposition(create_responses_client=synthetic_client),
    )
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
        from tests.integration.test_jd_manual_changes import manual_profile

        manual_profile(client, file_id, "purpose", "新版換窗的人工使命")
        manual_profile(client, file_id, "reports_to", "新版換窗的人工主管")

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
        assert len(requests[-1]["input"]) == 4
        net = requests[-1]["input"][-2]["content"]
        assert "人工最終差異" in net
        assert "新版換窗的人工使命" in net and "新版換窗的人工主管" in net
        changes = next(tool for tool in requests[-1]["tools"] if tool["name"] == "read_jd_changes")
        assert (
            changes["parameters"]["$defs"]["SourceQuery"]["properties"]["kind"]["const"] == "source"
        )
        assert "ManualQuery" not in changes["parameters"]["$defs"]
        app_data = json.loads(requests[-1]["input"][0]["content"])
        assert app_data["work_situation_map"]["items"][0]["target_title"] == "月末盘點"
        assert app_data["work_understanding_map"]["items"][0]["target_title"] == "庫存資料維護"
        assert app_data["interview_read_boundary"]["covered_through_sequence"] == 2
        assert [m["interview_sequence"] for m in app_data["historical_interview"]["messages"]] == [
            3
        ]
        assert json.loads(requests[-1]["input"][-1]["content"])["interview_sequence"] == 4
        manual_profile(client, file_id, "purpose", "同版新一輪的人工使命")
        following = client.post(
            f"/api/job-files/{file_id}/inputs",
            json={"command_id": str(uuid4()), "text": "同版談別的工作"},
        ).json()
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            result = client.get(
                f"/api/job-files/{file_id}/consultant-turns/{following['execution_id']}"
            ).json()
            if result["status"] != "active":
                break
            time.sleep(0.05)
        assert result["status"] == "completed"
        assert len(requests) == 8
        assert "同版新一輪的人工使命" in requests[-1]["input"][-2]["content"]
        assert "人工最終差異" in requests[-1]["input"][-2]["content"]
        assert json.loads(requests[-1]["input"][-1]["content"])["interview_sequence"] == 6


def test_http_jd_plan_memory_manual_net_uses_real_titles_and_native_compaction(database_settings):
    model = JourneyModel("manual_cross_section_changes")

    def open_sdk(settings):
        return create_responses_client(
            api_key=settings.api_key,
            timeout_seconds=settings.request_timeout_seconds,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(model.handle)),
        )

    app = create_app(
        Settings(database=database_settings, model=ModelSettings(api_key="synthetic")),
        composition=AppComposition(create_responses_client=open_sdk),
    )
    with TestClient(
        app,
        base_url="http://127.0.0.1:8100",
        headers={"Origin": "http://127.0.0.1:8100"},
        backend_options={"loop_factory": asyncio.SelectorEventLoop},
    ) as client:
        created = client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "完整正式鏈",
                "employee_name": "合成",
            },
        )
        assert created.status_code == 201
        path = f"/api/job-files/{created.json()['job_file_id']}"

        def submit(text):
            response = client.post(
                path + "/inputs", json={"command_id": str(uuid4()), "text": text}
            )
            assert response.status_code == 202
            accepted = response.json()
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                status = client.get(path + "/consultant-turns/" + accepted["execution_id"]).json()
                if status["status"] != "active":
                    assert status["status"] == "completed", status
                    return accepted
                time.sleep(0.05)
            pytest.fail("The formal consultant did not finish")

        first = submit("設備異常時記錄、停用並交技師，請整理工作記憶。")
        assert client.get(path + "/interview-plan").json()["plan"] is not None
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            memory = client.get(path + "/memory").json()
            if memory["snapshot_id"] is not None:
                break
            time.sleep(0.05)
        assert memory["covered_through_sequence"] == 2
        assert memory["work_situations"] and memory["work_understandings"]
        assert not model.compactions, "A new publication wins over the old compact intent"
        submit("另有核對借用紀錄的工作。")
        work = client.get(path + "/jd/work").json()
        second_task = next(item for item in work["tasks"] if item["title"] == "合成工作 4")
        changed = client.post(
            path + "/jd/tasks",
            json={
                "command_id": str(uuid4()),
                "expected_revision_id": work["revision_id"],
                "change": {
                    "action": "revise_task",
                    "task_id": second_task["task_id"],
                    "changes": [
                        {
                            "action": "set_field",
                            "field": "description",
                            "value": "人工改為自行核准借用。",
                        }
                    ],
                },
            },
        )
        assert changed.status_code == 200
        submit("本輪轉談季末清點。")
        assert len(model.compactions) == 1
        latest = [p for p in model.sent if "create_jd_task" in {t["name"] for t in p["tools"]}][-1]
        net = next(
            item["content"]
            for item in latest["input"]
            if "人工最終差異" in str(item.get("content", ""))
        )
        assert "人工改為自行核准借用。" in net
        assert "Memory work_understanding：合成理解 2；涵蓋訪談至 2" in net
        assert "Memory work_understanding：None" not in net
        compact_output = [
            {"type": "compaction", "encrypted_content": "synthetic-window"},
            *model.compactions[0]["input"],
        ]
        assert latest["input"][: len(compact_output)] == compact_output
        sources = client.get(path + "/jd/sources").json()
        citation = next(
            item
            for item in sources["references"]
            if item["target"]["item_id"] == second_task["task_id"]
            and item["source_kind"] == "work_understanding"
        )
        fixed = client.get(
            path + "/jd/sources/" + citation["citation_id"],
            params={"revision_id": sources["revision_id"]},
        )
        assert fixed.status_code == 200
        assert fixed.json()["content"]["references"]
        delta = client.get(
            path + "/jd/sources/" + citation["citation_id"] + "/changes",
            params={"revision_id": sources["revision_id"]},
        )
        assert delta.status_code == 200
        assert client.get(path + "/jd/sources").json() == sources
        assert first["source_id"] in {
            m["source_id"] for m in client.get(path + "/interviews").json()["messages"]
        }
