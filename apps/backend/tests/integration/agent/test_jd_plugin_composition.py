"""正式 Host 冷開切換 JD Prompt／Plugin；短碼、已完成輪及正式資料保持。"""

import asyncio
import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest
from sqlalchemy import Engine

from caliburn.bundles.job_description.instructions import JD_INSTRUCTIONS
from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin
from tests.integration.agent.http_support import api_client
from tests.integration.agent.jd_bundle_support import tool_outputs, wait_for_idle
from tests.integration.agent.jd_turn_history_support import create_workspace_jd
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    return AgentBundle(
        plugins=(
            AgentPlugin(
                name="alternate_jd_prompt",
                required_plugins=("job_description_tools",),
                prompt_sections=("局部核對後編修 JD，保留既有內容。",),
            ),
        )
    )


def test_prompt_swap_and_plugin_disable_preserve_refs_and_completed_history(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    requests: list[dict[str, Any]] = []
    task_ref = ""

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal task_ref
        body = request_body(request)
        requests.append(body)
        output = None
        match len(requests):
            case 1:
                output = [call("read_jd", "map", '{"view":"map","read_ref":null}')]
            case 2:
                output = [call("create_jd_task", "create", '{"name":"核對退款清單"}')]
            case 3:
                task_ref = tool_outputs(body)["create"]["read_ref"]
            case 4:
                output = [
                    call(
                        "read_jd",
                        "before",
                        json.dumps({"view": "item", "read_ref": task_ref}),
                    )
                ]
            case 5:
                output = [
                    call(
                        "revise_jd_item",
                        "rename",
                        json.dumps(
                            {
                                "read_ref": task_ref,
                                "changes": [
                                    {
                                        "action": "set_field",
                                        "field": "name",
                                        "value": "每日核對退款清單",
                                    }
                                ],
                            }
                        ),
                    )
                ]
            case 6 | 9:
                output = [
                    call(
                        "read_jd",
                        "after",
                        json.dumps({"view": "item", "read_ref": task_ref}),
                    )
                ]
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        transport = httpx2.MockTransport(respond)
        base = ("job_description", "job_description_tools")
        first_turn = uuid4()
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            transport,
            bundles=(
                BundleConfig(
                    "caliburn.bundles.job_description",
                    plugins=(*base, "job_description_prompt"),
                ),
            ),
        ) as client:
            created = await client.post(
                "/workspaces", json={"interviewee_name": "配置比較"}
            )
            assert created.status_code == 201, created.text
            workspace_id = UUID(created.json()["workspace_id"])
            initial = (
                await client.get(f"/workspaces/{workspace_id}/job-description")
            ).json()
            prefix = (
                f"/workspaces/{workspace_id}/job-descriptions/"
                f"{initial['job_description_id']}"
            )
            turns = f"/workspaces/{workspace_id}/agent/turns"
            accepted = await client.post(
                turns, json={"turn_id": str(first_turn), "input": "建立退款核對任務"}
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"
            saved = (await client.get(prefix)).json()
            task_id = saved["tasks"][0]["id"]
            comparison = await client.get(prefix + f"/turns/{first_turn}/changes")
            assert comparison.status_code == 200, comparison.text
            original_changes = comparison.json()

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            transport,
            bundles=(
                BundleConfig("caliburn.bundles.job_description", plugins=base),
                BundleConfig(__name__),
            ),
        ) as client:
            accepted = await client.post(
                turns,
                json={
                    "turn_id": str(uuid4()),
                    "input": "沿原定位把名稱改為每日核對退款清單",
                },
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"
            changed = (await client.get(prefix)).json()
            assert changed["version"] == saved["version"] + 1
            assert changed["tasks"][0]["id"] == task_id
            assert changed["tasks"][0]["name"] == "每日核對退款清單"
            assert (
                await client.get(prefix + f"/turns/{first_turn}/changes")
            ).json() == original_changes

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            transport,
            bundles=(BundleConfig("caliburn.bundles.job_description", plugins=()),),
        ) as client:
            disabled_turn = uuid4()
            accepted = await client.post(
                turns, json={"turn_id": str(disabled_turn), "input": "只回覆文字"}
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"
            assert (await client.get(prefix)).json() == changed
            assert (
                await client.get(prefix + f"/turns/{disabled_turn}/changes")
            ).status_code == 404
            assert (
                await client.get(prefix + f"/turns/{first_turn}/changes")
            ).json() == original_changes

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            transport,
            bundles=(BundleConfig("caliburn.bundles.job_description", plugins=base),),
        ) as client:
            accepted = await client.post(
                turns, json={"turn_id": str(uuid4()), "input": "重新啟用後回讀原項目"}
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"
            assert (await client.get(prefix)).json() == changed

        assert len(requests) == 10
        assert requests[0]["tools"] == requests[3]["tools"] == requests[8]["tools"]
        assert JD_INSTRUCTIONS in requests[0]["instructions"]
        assert requests[3]["instructions"] == "局部核對後編修 JD，保留既有內容。"
        assert requests[7]["tools"] == []
        assert not requests[7].get("instructions")
        assert len(requests[7]["input"]) == 1
        for request_index, call_id in ((4, "before"), (6, "after"), (9, "after")):
            item = tool_outputs(requests[request_index])[call_id]["item"]
            assert item["read_ref"] == task_ref
        assert tool_outputs(requests[9])["after"]["item"]["name"] == "每日核對退款清單"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_reenabling_changes_does_not_replay_edits_crossed_while_disabled(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
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
                    "caliburn.bundles.job_description", plugins=("job_description",)
                ),
            ),
        ) as client:
            workspace_id, initial = await create_workspace_jd(client)
            prefix = (
                f"/workspaces/{workspace_id}/job-descriptions/"
                f"{initial.job_description_id}"
            )
            turns = f"/workspaces/{workspace_id}/agent/turns"
            accepted = await client.post(
                turns, json={"turn_id": str(uuid4()), "input": "只回答問題"}
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"
            edited = await client.patch(
                prefix, json={"expected_version": 1, "purpose": "人工保存的目的"}
            )
            assert edited.status_code == 200, edited.text
            passed_turn = uuid4()
            accepted = await client.post(
                turns, json={"turn_id": str(passed_turn), "input": "仍不讀JD"}
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"
            comparison = await client.get(prefix + f"/turns/{passed_turn}/changes")
            assert comparison.status_code == 200, comparison.text
            assert comparison.json()["before_version"] == 2
            assert comparison.json()["after_version"] == 2

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            transport,
            bundles=(
                BundleConfig(
                    "caliburn.bundles.job_description",
                    plugins=("job_description", "job_description_changes"),
                ),
            ),
        ) as client:
            accepted = await client.post(
                turns, json={"turn_id": str(uuid4()), "input": "重新啟用差異"}
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"
            assert (await client.get(prefix)).json() == edited.json()
            historical = await client.get(prefix + "/history/2")
            assert historical.status_code == 200, historical.text
            assert "人工保存的目的" in historical.text

        assert len(requests) == 3
        assert requests[2]["input"] == [{"role": "user", "content": "重新啟用差異"}]

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("include_context", [False, True])
def test_window_uses_only_selected_jd_contribution_regardless_of_bundle_order(
    pg_engine: Engine, checkpoint_conninfo: str, include_context: bool
) -> None:
    requests: list[dict[str, Any]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        selected = ("job_description",) + (
            ("job_description_context",) if include_context else ()
        )
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(
                BundleConfig(
                    "caliburn.bundles.context",
                    plugins=("window",),
                ),
                BundleConfig("caliburn.bundles.job_description", plugins=selected),
            ),
        ) as client:
            created = await client.post(
                "/workspaces", json={"interviewee_name": "窗口選取"}
            )
            assert created.status_code == 201, created.text
            workspace_id = created.json()["workspace_id"]
            accepted = await client.post(
                f"/workspaces/{workspace_id}/agent/turns",
                json={"turn_id": str(uuid4()), "input": "核對窗口材料"},
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"

        assert len(requests) == 1
        assert requests[0]["tools"] == []
        assert not requests[0].get("instructions")
        items = requests[0]["input"]
        assert len(items) == (2 if include_context else 1)
        if include_context:
            navigation = json.loads(items[0]["content"])
            assert navigation["data_kind"] == "job_description_map"
            assert navigation["jd"]["version"] == 1
        assert items[-1] == {"role": "user", "content": "核對窗口材料"}

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
