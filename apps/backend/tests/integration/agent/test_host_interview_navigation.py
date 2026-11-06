"""正式 Host 的無 Memory 訪談窗口保留當輪定位與有效來源導覽。"""

import asyncio
import json
from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest
from sqlalchemy import Engine

from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.http_support import api_client
from tests.integration.agent.test_agent_http_cancellation import wait_for_idle
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def current_input_material(
    request: dict[str, Any], text: str
) -> dict[str, dict[str, Any]]:
    """只看當輪原文後的材料，不能讓歷史輪的 ref／導覽代替本輪。"""
    items = request["input"]
    positions = [
        index
        for index, item in enumerate(items)
        if item.get("role") == "user" and item.get("content") == text
    ]
    assert len(positions) == 1, "本輪原文應只提供一次"
    material: dict[str, dict[str, Any]] = {}
    for item in items[positions[0] + 1 :]:
        content = item.get("content")
        if item.get("role") != "user" or not isinstance(content, str):
            continue
        try:
            value = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("data_kind"), str):
            kind = value["data_kind"]
            assert kind not in material, f"本輪材料不應重複：{kind}"
            material[kind] = value
    return material


def test_interview_window_keeps_current_refs_through_resume_and_cancel(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    first_text = "Synthetic first employee input"
    second_text = "Synthetic continued employee input"
    cancelled_text = "Synthetic employee input to withdraw"
    fresh_text = "Synthetic employee input after cancellation"
    requests: list[dict[str, Any]] = []
    bundles = (
        BundleConfig(
            "caliburn.bundles.interview",
            plugins=("interview", "interview_source_prompt", "interview_read"),
        ),
        BundleConfig("caliburn.bundles.interview.window"),
        BundleConfig(
            "caliburn.bundles.context",
            plugins=("window",),
        ),
    )

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request_body(request))
        if len(requests) in (3, 4):
            raise RuntimeError("Synthetic model outage after request capture")
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        transport = httpx2.MockTransport(respond)
        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=bundles
        ) as client:
            created = await client.post(
                "/workspaces", json={"interviewee_name": "Synthetic interview window"}
            )
            assert created.status_code == 201, created.text
            workspace = created.json()["workspace_id"]
            turns = f"/workspaces/{workspace}/agent/turns"
            transcript_url = f"/workspaces/{workspace}/interview/messages"
            for text in (first_text, second_text):
                accepted = await client.post(
                    turns, json={"turn_id": str(uuid4()), "input": text}
                )
                assert accepted.status_code == 202, accepted.text
                assert (await wait_for_idle(client, accepted.headers["Location"]))[
                    "status"
                ] == "completed"
            cancelled_turn = str(uuid4())
            accepted = await client.post(
                turns, json={"turn_id": cancelled_turn, "input": cancelled_text}
            )
            assert accepted.status_code == 202, accepted.text
            location = accepted.headers["Location"]
            assert (await wait_for_idle(client, location))["status"] == "interrupted"
            original = await client.get(
                transcript_url, params={"turn_id": cancelled_turn}
            )
            assert original.status_code == 200, original.text
            input_ids = {
                item["message_id"]
                for item in original.json()
                if item["speaker"] == "employee" and item["text"] == cancelled_text
            }
            assert len(input_ids) == 1

        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=bundles
        ) as client:
            assert (await client.get(location)).json()["status"] == "interrupted"
            resumed = await client.post(location + "/resume")
            assert resumed.status_code == 202, resumed.text
            assert (await wait_for_idle(client, location))["status"] == "interrupted"
            resumed_messages = await client.get(
                transcript_url, params={"turn_id": cancelled_turn}
            )
            assert resumed_messages.status_code == 200, resumed_messages.text
            assert {
                item["message_id"]
                for item in resumed_messages.json()
                if item["speaker"] == "employee" and item["text"] == cancelled_text
            } == input_ids
            cancelled = await client.post(location + "/cancel")
            assert cancelled.status_code == 204, cancelled.text
            accepted = await client.post(
                turns, json={"turn_id": str(uuid4()), "input": fresh_text}
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"
            transcript = await client.get(transcript_url)
            assert transcript.status_code == 200, transcript.text
            employee_texts = {
                item["text"]
                for item in transcript.json()
                if item["speaker"] == "employee"
            }
            assert {first_text, second_text, fresh_text} <= employee_texts
            assert cancelled_text not in employee_texts

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(requests) == 5
    assert requests[3] == requests[2], "冷恢復必須沿原捕捉請求，不重新選取訪談"
    assert cancelled_text not in json.dumps(requests[4]["input"])
    references = []
    for request, text in zip(
        requests,
        (first_text, second_text, cancelled_text, cancelled_text, fresh_text),
        strict=True,
    ):
        material = current_input_material(request, text)
        assert "employee_input_reference" in material, (
            f"{text}: Context 丟失本輪員工原話定位"
        )
        assert "interview_navigation" in material, (
            f"{text}: Context 丟失本輪有效訪談導覽"
        )
        reference = material["employee_input_reference"]["ref"]
        navigation = material["interview_navigation"]
        assert reference.startswith("message_")
        assert navigation["last_ref"] == reference
        assert navigation["first_ref"].startswith("message_")
        references.append(reference)
    assert len(set(references)) == 4
    assert references[2] == references[3]


@pytest.mark.parametrize("recording,read", [(True, False), (False, True), (True, True)])
def test_interview_window_preserves_independent_input_capabilities_without_preload(
    pg_engine: Engine, checkpoint_conninfo: str, recording: bool, read: bool
) -> None:
    seed_text = "Synthetic earlier interview"
    current_text = "Synthetic current input without preload"
    requests: list[dict[str, Any]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        transport = httpx2.MockTransport(respond)
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            transport,
            bundles=(
                BundleConfig(
                    "caliburn.bundles.interview",
                    plugins=("interview",),
                ),
            ),
        ) as client:
            created = await client.post(
                "/workspaces", json={"interviewee_name": "Synthetic capability toggles"}
            )
            assert created.status_code == 201, created.text
            workspace = created.json()["workspace_id"]
            turns = f"/workspaces/{workspace}/agent/turns"
            transcript_url = f"/workspaces/{workspace}/interview/messages"
            seeded = await client.post(
                turns, json={"turn_id": str(uuid4()), "input": seed_text}
            )
            assert seeded.status_code == 202, seeded.text
            assert (await wait_for_idle(client, seeded.headers["Location"]))[
                "status"
            ] == "completed"
            previous_response = await client.get(transcript_url)
            assert previous_response.status_code == 200, previous_response.text
            previous = previous_response.json()

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            transport,
            resume_version="v2",
            bundles=(
                BundleConfig(
                    "caliburn.bundles.interview",
                    plugins=tuple(
                        name
                        for name, enabled in (
                            ("interview", recording),
                            ("interview_read", read),
                        )
                        if enabled
                    ),
                ),
                BundleConfig(
                    "caliburn.bundles.interview.window",
                    {
                        "preload": False,
                        "include_input_reference": recording,
                        "include_navigation": read,
                    },
                ),
                BundleConfig(
                    "caliburn.bundles.context",
                    plugins=("window",),
                ),
            ),
        ) as client:
            turn = str(uuid4())
            accepted = await client.post(
                turns, json={"turn_id": turn, "input": current_text}
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"
            current_response = await client.get(
                transcript_url, params={"turn_id": turn}
            )
            assert current_response.status_code == 200, current_response.text
            current = current_response.json()

        request = requests[-1]
        material = current_input_material(request, current_text)
        assert ("employee_input_reference" in material) is recording
        assert ("interview_navigation" in material) is read
        assert ("read_interview" in {tool["name"] for tool in request["tools"]}) is read
        assert not any(
            isinstance(item.get("content"), str)
            and '"source": "interview"' in item["content"]
            for item in request["input"]
        ), "preload=False 不應預載訪談正文"

        references = SqlAlchemyModelReferences(create_session_factory(pg_engine))
        if recording:
            original = next(
                item
                for item in current
                if item["speaker"] == "employee" and item["text"] == current_text
            )
            reference = material["employee_input_reference"]["ref"]
            target = references.resolve_refs(UUID(workspace), (reference,))[reference]
            assert target.resource_kind == "message"
            assert target.resource_id == UUID(original["message_id"])
        else:
            assert current == []
        if read:
            navigation = material["interview_navigation"]
            endpoints = (navigation["first_ref"], navigation["last_ref"])
            targets = references.resolve_refs(UUID(workspace), endpoints)
            assert targets[endpoints[0]].resource_id == UUID(previous[0]["message_id"])
            expected_last = original if recording else previous[-1]
            assert targets[endpoints[1]].resource_id == UUID(
                expected_last["message_id"]
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
