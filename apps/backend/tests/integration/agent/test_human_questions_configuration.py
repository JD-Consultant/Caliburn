"""正式 Host 啟動時核對提問所需的訪談輪次保存能力。"""

import asyncio
import json
from typing import Any
from uuid import uuid4

import httpx2
import pytest
from sqlalchemy import Engine

from caliburn.modules.agent.bootstrap import BundleConfig
from tests.integration.agent.http_support import api_client
from tests.integration.agent.jd_bundle_support import wait_for_idle
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


@pytest.mark.parametrize(
    "interview", [False, True], ids=["absent", "recording-unselected"]
)
def test_host_rejects_questions_without_interview_recording_before_model_send(
    pg_engine: Engine, checkpoint_conninfo: str, interview: bool
) -> None:
    bundles: tuple[BundleConfig, ...] = (
        BundleConfig("caliburn.bundles.human_questions"),
    )
    if interview:
        bundles += (
            BundleConfig(
                "caliburn.bundles.interview", plugins=("interview_source_prompt",)
            ),
        )
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        raise AssertionError("Invalid configuration must not reach the model")

    async def run() -> None:
        with pytest.raises(ValueError, match="human_questions.*interview"):
            async with api_client(
                pg_engine,
                checkpoint_conninfo,
                httpx2.MockTransport(respond),
                bundles=bundles,
            ):
                pass
        assert not sent

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize(
    "plugins", [None, ("interview",)], ids=["default", "recording-only"]
)
def test_selected_recording_allows_questions(
    pg_engine: Engine, checkpoint_conninfo: str, plugins: tuple[str, ...] | None
) -> None:
    requests: list[dict[str, Any]] = []
    question = "目前主要負責哪些工作？"

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request_body(request))
        output = [
            call(
                "ask_user_question",
                "ask",
                json.dumps({"questions": [{"question": question}]}),
            )
        ]
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(
                BundleConfig("caliburn.bundles.human_questions"),
                BundleConfig("caliburn.bundles.interview", plugins=plugins),
            ),
        ) as client:
            workspace = await client.post(
                "/workspaces", json={"interviewee_name": "合成提問配置"}
            )
            assert workspace.status_code == 201, workspace.text
            base = f"/workspaces/{workspace.json()['workspace_id']}"
            turn_id = str(uuid4())
            submitted = await client.post(
                base + "/agent/turns",
                json={"turn_id": turn_id, "input": "我在採購部工作"},
            )
            assert submitted.status_code == 202, submitted.text
            turn = await wait_for_idle(client, submitted.headers["Location"])
            assert turn["status"] == "waiting_for_input", turn
            pending = turn["interrupts"][0]["value"]["questions"]
            assert pending[0]["question"] == question
            transcript = await client.get(
                base + "/interview/messages", params={"turn_id": turn_id}
            )
            assert transcript.status_code == 200, transcript.text
            messages = transcript.json()
            assert [(item["speaker"], item["text"]) for item in messages] == [
                ("employee", "我在採購部工作"),
                ("consultant", question),
            ]
            assert messages[1]["message_id"] == pending[0]["message_id"]

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(requests) == 1
