"""正式 Host 保存顧問開場，並按設定將提示與工具送入模型請求。"""

import asyncio
from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest
from sqlalchemy import Engine

from caliburn.bundles.consultant import OPENING_TEXT
from caliburn.bundles.interview.source_prompt import INTERVIEW_SOURCE_PROMPT
from caliburn.modules.agent.bootstrap import BundleConfig
from tests.integration.agent.http_support import api_client
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    message,
    request_body,
    response_events,
    response_payload,
    sse_response,
)

CONSULTANT_BUNDLE = "caliburn.bundles.consultant"


@pytest.mark.parametrize(
    ("consultant_bundle", "consultant_enabled", "optional_tools"),
    [
        (BundleConfig(CONSULTANT_BUNDLE), True, False),
        (BundleConfig(CONSULTANT_BUNDLE), True, True),
        (None, False, True),
        (BundleConfig(CONSULTANT_BUNDLE, plugins=()), False, True),
    ],
    ids=["minimal", "with-optional-tools", "without-consultant", "empty-selection"],
)
def test_consultant_policy_and_interview_survive_optional_tool_selection(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    consultant_bundle: BundleConfig | None,
    consultant_enabled: bool,
    optional_tools: bool,
) -> None:
    bundles: tuple[BundleConfig, ...] = (
        (consultant_bundle,) if consultant_bundle is not None else ()
    )
    interview_plugins = (
        None
        if optional_tools
        else ("interview", "interview_context", "interview_source_prompt")
    )
    bundles += (BundleConfig("caliburn.bundles.interview", plugins=interview_plugins),)
    if optional_tools:
        bundles += (
            BundleConfig("caliburn.bundles.plan"),
            BundleConfig("caliburn.bundles.human_questions"),
        )

    requests: list[dict[str, Any]] = []
    employee = " 我在採購部負責報價整理。\n"
    final = "收到。除了報價整理，你還負責哪些工作？"

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request_body(request))
        output = [message("commentary", "正在整理輪廓。"), message(text=final)]
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=bundles,
        ) as client:
            created_workspace = await client.post(
                "/workspaces", json={"interviewee_name": "顧問接線"}
            )
            assert created_workspace.status_code == 201, created_workspace.text
            workspace = UUID(created_workspace.json()["workspace_id"])
            transcript_path = f"/workspaces/{workspace}/interview/messages"
            initial_transcript = await client.get(transcript_path)
            assert initial_transcript.status_code == 200, initial_transcript.text
            (opening,) = initial_transcript.json()
            assert opening["speaker"] == "app"
            assert opening["kind"] == "text"
            assert opening["text"] == OPENING_TEXT
            assert "職位" in opening["text"]
            assert "主要負責哪些工作" in opening["text"]
            assert not requests

            created_turn = await client.post(
                f"/workspaces/{workspace}/agent/turns",
                json={"turn_id": str(uuid4()), "input": employee},
            )
            assert created_turn.status_code == 202, created_turn.text
            async with asyncio.timeout(10):
                while True:
                    turn = await client.get(created_turn.headers["Location"])
                    assert turn.status_code == 200, turn.text
                    if turn.json()["status"] != "running":
                        break
                    await asyncio.sleep(0.01)
            assert turn.json()["status"] == "completed", turn.text
            transcript = await client.get(transcript_path)
            assert transcript.status_code == 200, transcript.text
            saved = transcript.json()
            assert [(item["speaker"], item["text"]) for item in saved] == [
                ("app", OPENING_TEXT),
                ("employee", employee),
                ("consultant", final),
            ]
            assert saved[0]["message_id"] == opening["message_id"]

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    (request,) = requests
    instructions = request["instructions"]
    assert ("你是 Caliburn 的職務顧問。" in instructions) is consultant_enabled
    assert ("初期先建立工作廣度" in instructions) is consultant_enabled
    names = {tool["name"] for tool in request.get("tools", [])}
    expected_optional = {
        "read_interview",
        "read_interview_plan",
        "edit_interview_plan",
        "ask_user_question",
    }
    if optional_tools:
        assert expected_optional <= names
        assert "預設用「目前焦點」與「工作方向」組織" in instructions
    else:
        assert not names
        assert INTERVIEW_SOURCE_PROMPT in instructions
        assert "本輪有 read_interview 時" in INTERVIEW_SOURCE_PROMPT
        role_instructions = instructions.replace(INTERVIEW_SOURCE_PROMPT, "", 1)
        assert not any(name in role_instructions for name in expected_optional)
        assert "預設用「目前焦點」與「工作方向」組織" not in instructions
