"""同程序 App 候選走正式 HTTP／保存流程，各自持有模型及提示設定。"""

import asyncio
import json
import time
from contextlib import asynccontextmanager
from dataclasses import replace
from uuid import uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient

from caliburn.adapters.openai_responses import create_responses_client
from caliburn.agents.job_consultant.configuration import (
    ConsultantConfiguration,
    ConsultantPrompts,
    ToolDescriptionOverride,
)
from caliburn.bootstrap import create_app
from caliburn.settings import ModelSettings, Settings
from tests.fixtures.scripted_backend import create_scripted_app
from tests.fixtures.scripted_model import ScriptedModel

pytestmark = pytest.mark.postgres


def complete_turn(app, name):
    with TestClient(
        app,
        base_url="http://127.0.0.1:8100",
        headers={"Origin": "http://127.0.0.1:8100"},
        backend_options={"loop_factory": asyncio.SelectorEventLoop},
    ) as client:
        created = client.post(
            "/api/job-files",
            json={"command_id": str(uuid4()), "display_name": name, "employee_name": "合成"},
        )
        assert created.status_code == 201
        file_id = created.json()["job_file_id"]
        submitted = client.post(
            f"/api/job-files/{file_id}/inputs",
            json={"command_id": str(uuid4()), "text": "我每月核對庫存。"},
        )
        assert submitted.status_code == 202
        turn_id = submitted.json()["execution_id"]
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            status = client.get(f"/api/job-files/{file_id}/consultant-turns/{turn_id}").json()
            if status["status"] != "active":
                break
            time.sleep(0.02)
        else:
            pytest.fail("The synthetic consultant did not finish")
        assert status["status"] == "completed", status
        history = client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]
        assert len(history) == 3
        return file_id, history[-1]["interview_text"]


def test_two_app_compositions_keep_actual_requests_and_resources_independent(database_settings):
    from caliburn.app_composition import AppComposition

    settings = Settings(database=database_settings, model=ModelSettings(api_key="synthetic"))
    defaults = AppComposition()
    requests = {"甲": [], "乙": []}
    clients = []
    events = []

    def variant(name, plans):
        model = ScriptedModel(chunk_delay_seconds=0)

        async def respond(request):
            if request.url.path.endswith("/responses"):
                requests[name].append(json.loads(request.content))
            return await model.handle(request)

        def create_client(model_settings):
            sdk = create_responses_client(
                api_key=model_settings.api_key,
                timeout_seconds=model_settings.request_timeout_seconds,
                http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
            )
            clients.append(sdk)
            return sdk

        @asynccontextmanager
        async def open_checkpointer(configured):
            async with defaults.open_checkpointer(configured) as native:
                events.append((name, "opened"))
                try:
                    yield native
                finally:
                    events.append((name, "closed"))

        return create_app(
            settings,
            composition=AppComposition(
                consultant_configuration=ConsultantConfiguration(
                    prompts=replace(ConsultantPrompts(), focus=f"候選{name}的焦點指引"),
                    tool_descriptions=(ToolDescriptionOverride("read_jd", f"候選{name}說明"),),
                ),
                interview_plans_enabled=plans,
                create_responses_client=create_client,
                open_checkpointer=open_checkpointer,
            ),
        )

    # 先建立兩個 App，再各自啟動；後建立的候選不能覆蓋前者的模型或提示。
    left = variant("甲", True)
    right = variant("乙", False)
    left_file, _ = complete_turn(left, "候選甲")
    right_file, _ = complete_turn(right, "候選乙")
    assert left_file != right_file
    for name, plans in (("甲", True), ("乙", False)):
        assert len(requests[name]) == 1
        request = requests[name][0]
        assert f"候選{name}的焦點指引" in request["instructions"]
        tools = {tool["name"]: tool for tool in request["tools"]}
        assert tools["read_jd"]["description"] == f"候選{name}說明"
        assert ("edit_interview_plan" in tools) == plans
    assert len(clients) == 2
    assert all(client.is_closed() for client in clients)
    assert events == [("甲", "opened"), ("甲", "closed"), ("乙", "opened"), ("乙", "closed")]


def test_scripted_apps_use_their_own_provider_without_global_replacement(database_settings):
    models = [ScriptedModel(chunk_delay_seconds=0), ScriptedModel(chunk_delay_seconds=0)]
    apps = [create_scripted_app(Settings(database=database_settings), model) for model in models]
    complete_turn(apps[0], "腳本甲")
    assert [model.responses_sent for model in models] == [1, 0]
    complete_turn(apps[1], "腳本乙")
    assert [model.responses_sent for model in models] == [1, 1]
