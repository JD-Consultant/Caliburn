"""正式 HTTP 從 PostgreSQL 冷查讀已採用 C，恢復前後不重算或串輪。"""

import asyncio
from typing import Any
from uuid import uuid4

import httpx2
import pytest
from sqlalchemy import Engine

from caliburn.modules.agent.bootstrap import BundleConfig
from tests.integration.agent.http_support import api_client
from tests.unit.bundles.context.support import compacted_payload
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    message,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


async def settled_turn(client: httpx2.AsyncClient, location: str) -> dict[str, Any]:
    async with asyncio.timeout(10):
        while True:
            response = await client.get(location)
            assert response.status_code == 200
            value: dict[str, Any] = response.json()
            if value["status"] != "running":
                return value
            await asyncio.sleep(0.01)


@pytest.mark.parametrize("missing_usage", [False, True], ids=["null", "omitted"])
def test_cold_http_resume_keeps_boundary_and_step_compactions_separate(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    missing_usage: bool,
) -> None:
    models = 0
    compacts = 0
    failed_recount = False
    compacted_window = compacted_payload()["output"]
    bundles = (
        BundleConfig(
            "caliburn.bundles.context",
            {
                "history_threshold_tokens": 100,
                "threshold_tokens": 100,
            },
            plugins=("window", "native_compaction"),
        ),
    )

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal models, compacts, failed_recount
        body = request_body(request)
        if request.url.path.endswith("input_tokens"):
            if compacts == 3 and not failed_recount:
                failed_recount = True
                return httpx2.Response(
                    400,
                    json={
                        "error": {
                            "message": "synthetic recount failure",
                            "type": "invalid_request_error",
                        }
                    },
                )
            tokens = (
                20
                if models == 0 or models >= 3 or body["input"] == compacted_window
                else 100
            )
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": tokens}
            )
        if request.url.path.endswith("compact"):
            compacts += 1
            payload = {**compacted_payload(), "id": f"cmp_{compacts}"}
            if compacts == 3:
                if missing_usage:
                    payload.pop("usage")
                else:
                    payload["usage"] = None
            return httpx2.Response(200, json=payload)
        models += 1
        output = [message("commentary")] if models == 2 else [message()]
        payload = {**response_payload(output), "id": f"response_{models}"}
        return sse_response(EventStream(response_events(payload)))

    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=bundles,
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "Synthetic"})
            ).json()["workspace_id"]
            base = f"/workspaces/{workspace}/agent/turns"
            first = await client.post(
                base, json={"turn_id": str(uuid4()), "input": "第一輪"}
            )
            first_location = first.headers["Location"]
            assert (await settled_turn(client, first_location))["compactions"] == []
            second = await client.post(
                base, json={"turn_id": str(uuid4()), "input": "第二輪"}
            )
            location = second.headers["Location"]
            interrupted = await settled_turn(client, location)
            assert interrupted["status"] == "interrupted"
            assert interrupted["usage"]["total_tokens"] == 21
            assert [
                (item["response_id"], item["model_step"])
                for item in interrupted["compactions"]
            ] == [
                ("cmp_1", 0),
                ("cmp_2", 1),
                ("cmp_3", 2),
            ]
            assert [item["usage"] for item in interrupted["compactions"]] == [
                {"input_tokens": 128000, "output_tokens": 20, "total_tokens": 128020},
                {"input_tokens": 128000, "output_tokens": 20, "total_tokens": 128020},
                None,
            ]
            steps = (await client.get(location + "/steps")).json()
            assert [step["model_step"] for step in steps] == [1]
            assert [item["response_id"] for item in steps[0]["compactions"]] == [
                "cmp_2"
            ]
            assert (await settled_turn(client, first_location))["compactions"] == []

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=bundles,
        ) as client:
            cold = await settled_turn(client, location)
            assert cold["compactions"] == interrupted["compactions"]
            assert cold["usage"] == interrupted["usage"]
            assert (await client.post(location + "/resume")).status_code == 202
            completed = await settled_turn(client, location)
            assert completed["status"] == "completed"
            assert completed["usage"] == {
                "input_tokens": 26,
                "output_tokens": 16,
                "total_tokens": 42,
            }
            assert completed["compactions"] == interrupted["compactions"]
            steps = (await client.get(location + "/steps")).json()
            assert [step["model_step"] for step in steps] == [1, 2]
            assert [
                [item["response_id"] for item in step["compactions"]] for step in steps
            ] == [["cmp_2"], ["cmp_3"]]
            assert steps[1]["compactions"][0]["usage"] is None
            assert all(
                set(item) == {"response_id", "model_step", "usage"}
                for item in completed["compactions"]
            )
            third = await client.post(
                base, json={"turn_id": str(uuid4()), "input": "第三輪"}
            )
            third_location = third.headers["Location"]
            next_turn = await settled_turn(client, third_location)
            assert next_turn["status"] == "completed"
            assert next_turn["compactions"] == []
            assert next_turn["usage"]["total_tokens"] == 21
            assert (await client.get(third_location + "/steps")).json()[0][
                "compactions"
            ] == []

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(),
        ) as client:
            assert (await settled_turn(client, location))["compactions"] == interrupted[
                "compactions"
            ]
            turns = (await client.get(base)).json()
            assert [len(turn["compactions"]) for turn in turns] == [0, 3, 0]

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert models == 4
    assert compacts == 3


@pytest.mark.parametrize("cancel", [False, True], ids=["resume", "cancel"])
def test_task_saved_compaction_is_not_reported_as_adopted_before_parent_update(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    cancel: bool,
) -> None:
    compacts = 0
    payload = compacted_payload()
    bundle_module = "tests.integration.agent.test_compaction"

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal compacts
        if request.url.path.endswith("input_tokens"):
            tokens = 20 if request_body(request)["input"] == payload["output"] else 100
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": tokens}
            )
        if request.url.path.endswith("compact"):
            compacts += 1
            return httpx2.Response(200, json=payload)
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(BundleConfig(bundle_module, {"fail_after": True}),),
        ) as client:
            workspace = (
                await client.post("/workspaces", json={"interviewee_name": "Synthetic"})
            ).json()["workspace_id"]
            base = f"/workspaces/{workspace}/agent/turns"
            accepted = await client.post(
                base, json={"turn_id": str(uuid4()), "input": "合成輸入"}
            )
            location = accepted.headers["Location"]
            interrupted = await settled_turn(client, location)
            assert interrupted["status"] == "interrupted"
            assert interrupted["compactions"] == []
            assert interrupted["usage"] is None
            assert (await client.get(location + "/steps")).json() == []

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(BundleConfig(bundle_module, {"fail_after": False}),),
        ) as client:
            assert (await settled_turn(client, location))["compactions"] == []
            if cancel:
                assert (await client.post(location + "/cancel")).status_code == 204
                assert (await client.get(location)).status_code == 404
                assert (await client.get(base)).json() == []
            else:
                assert (await client.post(location + "/resume")).status_code == 202
                completed = await settled_turn(client, location)
                assert completed["status"] == "completed"
                assert completed["compactions"] == [
                    {
                        "response_id": "cmp_offline",
                        "model_step": 1,
                        "usage": {
                            "input_tokens": 128000,
                            "output_tokens": 20,
                            "total_tokens": 128020,
                        },
                    }
                ]
                assert completed["usage"]["total_tokens"] == 21

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert compacts == 1
