"""正式 Host 的局部更正、第二次發布與冷開後顧問查讀；只有模型 I/O 為替身。"""

import asyncio
import json
from collections.abc import Callable
from typing import Any, cast
from uuid import UUID, uuid4

import httpx2
from sqlalchemy import Engine

from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.memory.infrastructure.persistence.queries import (
    SqlAlchemyMemoryQueries,
)
from tests.integration.agent.http_support import api_client
from tests.integration.agent.memory_reference_support import interview_ref
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    message,
    request_body,
    response_events,
    response_payload,
    sse_response,
)

FIRST_INPUT = (
    "我每週一整理20項物料，週二中午前交清單。"
    "每天核對送貨單，退貨由主管決定；特殊情況還說不清楚。"
)
CORRECTION = "更正一下，清單應在週一17點前交，20項不變；收貨分工和未知情況都不變。"
SITUATION = "每週一整理20項物料。\n週二中午前交清單。"
CORRECTED_SITUATION = "每週一整理20項物料。\n週一17點前交清單。"
RECEIVING = "每天核對送貨單，退貨由主管決定。\n特殊情況尚不清楚。"
UNDERSTANDING = (
    "本人每週整理20項物料並於週二中午前交清單。\n"
    "每天核對送貨單，退貨由主管決定。\n特殊情況尚不清楚。"
)
CORRECTED_UNDERSTANDING = (
    "本人每週整理20項物料並於週一17點前交清單。\n"
    "每天核對送貨單，退貨由主管決定。\n特殊情況尚不清楚。"
)

type Reply = (
    list[dict[str, object]] | Callable[[dict[str, Any]], list[dict[str, object]]]
)


def tool(name: str, call_id: str, **arguments: object) -> dict[str, object]:
    return call(name, call_id, json.dumps(arguments))


def result(request: dict[str, Any], call_id: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        next(
            json.loads(item["output"])
            for item in request["input"]
            if item.get("type") == "function_call_output" and item["call_id"] == call_id
        ),
    )


def material(request: dict[str, Any], kind: str) -> dict[str, Any]:
    for item in request["input"]:
        if item.get("role") != "user" or not isinstance(item.get("content"), str):
            continue
        try:
            value = json.loads(item["content"])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("data_kind") == kind:
            return value
    raise AssertionError(f"Missing model material: {kind}")


def revision_replies() -> list[Reply]:
    complete = [message(text='{"status":"complete"}')]
    return [
        [tool("request_memory_consolidation", "first-request")],
        [message(text="已記錄物料與收貨分工。")],
        lambda request: [
            tool(
                "create_work_situation",
                call_id,
                title=title,
                description=description,
                body=body,
                interview_references=[interview_ref(request, FIRST_INPUT)],
            )
            for call_id, title, description, body in (
                ("ordering", "物料清單", "每週清單期限", SITUATION),
                ("receiving", "收貨核對", "本人核對與主管決定", RECEIVING),
            )
        ],
        complete,
        [
            tool(
                "create_work_understanding",
                "responsibility",
                title="物料與收貨責任",
                description="交單期限與決定權",
                body=UNDERSTANDING,
                work_situation_references=["物料清單", "收貨核對"],
            )
        ],
        complete,
        [
            tool("read_work_situation", "before-correction", target_title="物料清單"),
            tool("request_memory_consolidation", "second-request"),
        ],
        [message(text="已記錄清單期限更正。")],
        [tool("read_work_situation", "b1-read", target_title="物料清單")],
        lambda request: [
            tool(
                "update_work_situation",
                "correct-situation",
                target_title="物料清單",
                changes=[
                    {
                        "field": "body",
                        "diff": "@@\n-週二中午前交清單。\n+週一17點前交清單。",
                    },
                    {
                        "field": "interview_references",
                        "add": [interview_ref(request, CORRECTION)],
                    },
                ],
            )
        ],
        complete,
        [
            tool("read_work_situation", "b2-situation", target_title="物料清單"),
            tool(
                "read_work_understanding",
                "b2-understanding",
                target_title="物料與收貨責任",
            ),
        ],
        [
            tool(
                "update_work_understanding",
                "correct-understanding",
                target_title="物料與收貨責任",
                changes=[
                    {
                        "field": "body",
                        "diff": (
                            "@@\n-本人每週整理20項物料並於週二中午前交清單。\n"
                            "+本人每週整理20項物料並於週一17點前交清單。"
                        ),
                    }
                ],
            )
        ],
        complete,
        [
            tool("read_work_situation", "a3-situation", target_title="物料清單"),
            tool(
                "read_work_understanding",
                "a3-understanding",
                target_title="物料與收貨責任",
            ),
        ],
        lambda request: [
            tool(
                "read_interview",
                "a3-sources",
                query={
                    "kind": "messages",
                    "refs": result(request, "a3-situation")["interview_references"],
                },
            )
        ],
        [
            message(
                text="已查回兩層記憶與原話；清單期限已更新，收貨分工及未知情況保留。"
            )
        ],
    ]


async def completed_turn(client: httpx2.AsyncClient, location: str) -> None:
    async with asyncio.timeout(15):
        while True:
            response = await client.get(location)
            assert response.status_code == 200, response.text
            status = response.json()["status"]
            if status != "running":
                assert status == "completed", response.text
                return
            await asyncio.sleep(0.01)


async def published(
    client: httpx2.AsyncClient, path: str, *, after: int = 0
) -> dict[str, Any]:
    async with asyncio.timeout(15):
        while True:
            response = await client.get(path)
            assert response.status_code == 200, response.text
            value = response.json()
            if (value["published_version"] or 0) > after:
                return cast(dict[str, Any], value)
            await asyncio.sleep(0.01)


async def contents(
    client: httpx2.AsyncClient, path: str, snapshot: dict[str, Any]
) -> dict[str, Any]:
    items = {}
    for entry in snapshot["items"]:
        response = await client.get(
            f"{path}/versions/{snapshot['published_version']}/items/{entry['item_id']}"
        )
        assert response.status_code == 200, response.text
        items[entry["title"]] = response.json()
    return items


def test_revision_publishes_both_layers_and_next_consultant_reads_new_window(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    replies = revision_replies()
    requests: list[dict[str, Any]] = []
    bundles = (
        BundleConfig(
            "caliburn.bundles.interview",
            plugins=("interview", "interview_source_prompt"),
        ),
        BundleConfig("caliburn.bundles.memory"),
        BundleConfig("caliburn.bundles.context", plugins=("window",)),
    )
    queries = SqlAlchemyMemoryQueries(pg_engine)

    async def run() -> None:
        a2_waiting, b2_waiting = asyncio.Event(), asyncio.Event()
        finish_a2, finish_b2 = asyncio.Event(), asyncio.Event()

        async def respond(request: httpx2.Request) -> httpx2.Response:
            if request.url.path == "/v1/responses/input_tokens":
                return httpx2.Response(
                    200, json={"object": "response.input_tokens", "input_tokens": 1}
                )
            assert request.url.path == "/v1/responses"
            body = request_body(request)
            index = len(requests)
            requests.append(body)
            if index == 7:
                a2_waiting.set()
                await finish_a2.wait()
            elif index == 13:
                b2_waiting.set()
                await finish_b2.wait()
            reply = replies[index]
            payload = response_payload(reply(body) if callable(reply) else reply)
            return sse_response(EventStream(response_events(payload)))

        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=bundles,
        ) as client:
            try:
                created = await client.post(
                    "/workspaces", json={"interviewee_name": "Memory 更正旅程"}
                )
                assert created.status_code == 201, created.text
                workspace = created.json()["workspace_id"]
                path = f"/workspaces/{workspace}/memory"
                turns = f"/workspaces/{workspace}/agent/turns"
                first_turn, second_turn = uuid4(), uuid4()
                first = await client.post(
                    turns, json={"turn_id": str(first_turn), "input": FIRST_INPUT}
                )
                assert first.status_code == 202, first.text
                await completed_turn(client, first.headers["Location"])
                baseline = await published(client, path)
                original = await contents(client, path, baseline)
                assert (
                    await client.post(first.headers["Location"] + "/cancel")
                ).status_code == 409

                second = await client.post(
                    turns, json={"turn_id": str(second_turn), "input": CORRECTION}
                )
                assert second.status_code == 202, second.text
                async with asyncio.timeout(15):
                    await a2_waiting.wait()
                assert (await client.get(second.headers["Location"])).json()[
                    "status"
                ] == "running"
                current = await asyncio.to_thread(
                    queries.get_current, workspace_id=UUID(workspace)
                )
                assert current.analysis is None
                assert (await client.get(path)).json() == baseline
                assert result(requests[7], "before-correction")["body"] == SITUATION
                assert (
                    material(requests[6], "memory_navigation")["published_version"]
                    == baseline["published_version"]
                )
                finish_a2.set()

                async with asyncio.timeout(15):
                    await b2_waiting.wait()
                await completed_turn(client, second.headers["Location"])
                assert (
                    await client.post(second.headers["Location"] + "/cancel")
                ).status_code == 409
                current = await asyncio.to_thread(
                    queries.get_current, workspace_id=UUID(workspace)
                )
                assert current.analysis is not None
                assert current.analysis.phase == "understanding"
                assert (await client.get(path)).json() == baseline
                assert await contents(client, path, baseline) == original
                assert result(requests[10], "correct-situation")["status"] == "updated"
                assert (
                    result(requests[12], "b2-situation")["body"] == CORRECTED_SITUATION
                )
                assert result(requests[12], "b2-understanding")["body"] == UNDERSTANDING
                assert (
                    result(requests[13], "correct-understanding")["status"] == "updated"
                )
                (change,) = material(requests[11], "memory_analysis_input")[
                    "work_situation_changes"
                ]
                assert change["change"] == "modified"
                assert change["target_title"] == "物料清單"
                assert change["affected_understanding_titles"] == ["物料與收貨責任"]
                assert "週二中午前交清單。" in change["diff"]
                assert "週一17點前交清單。" in change["diff"]
                finish_b2.set()

                revised = await published(
                    client, path, after=baseline["published_version"]
                )
                updated = await contents(client, path, revised)
                assert updated["物料清單"]["body"] == CORRECTED_SITUATION
                assert updated["物料與收貨責任"]["body"] == CORRECTED_UNDERSTANDING
                assert set(updated["物料與收貨責任"]["source_ids"]) == {
                    updated["物料清單"]["item_id"],
                    updated["收貨核對"]["item_id"],
                }
                for title in original:
                    assert updated[title]["item_id"] == original[title]["item_id"]
                    assert updated[title]["workspace_id"] == workspace
                for title in ("物料清單", "物料與收貨責任"):
                    assert (
                        updated[title]["changed_version"]
                        > original[title]["changed_version"]
                    )
                assert updated["收貨核對"]["body"] == RECEIVING
                assert (
                    updated["收貨核對"]["source_ids"]
                    == original["收貨核對"]["source_ids"]
                )
                assert (
                    updated["收貨核對"]["changed_version"]
                    == original["收貨核對"]["changed_version"]
                )
                assert (
                    updated["物料與收貨責任"]["source_ids"]
                    == original["物料與收貨責任"]["source_ids"]
                )
                transcript = (
                    await client.get(f"/workspaces/{workspace}/interview/messages")
                ).json()
                by_text = {entry["text"]: entry["message_id"] for entry in transcript}
                assert set(updated["物料清單"]["source_ids"]) == {
                    by_text[FIRST_INPUT],
                    by_text[CORRECTION],
                }
                assert (
                    revised["covered_through_message_id"]
                    == by_text["已記錄清單期限更正。"]
                )
                assert (
                    await client.get(f"{path}/versions/{baseline['published_version']}")
                ).json() == baseline
                assert await contents(client, path, baseline) == original
            finally:
                finish_a2.set()
                finish_b2.set()

        # 冷開沿正式 Host recover 與原生 Checkpoint，已涵蓋意圖不得重跑 B。
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=bundles,
        ) as client:
            assert (await client.get(path)).json() == revised
            third = await client.post(
                turns,
                json={
                    "turn_id": str(uuid4()),
                    "input": "請從記憶確認現在的工作內容與依據。",
                },
            )
            assert third.status_code == 202, third.text
            await completed_turn(client, third.headers["Location"])
            assert (
                material(requests[14], "memory_navigation")["published_version"]
                == revised["published_version"]
            )
            assert all(item.get("role") == "user" for item in requests[14]["input"])
            assert FIRST_INPUT not in json.dumps(
                requests[14]["input"], ensure_ascii=False
            )
            assert CORRECTION not in json.dumps(
                requests[14]["input"], ensure_ascii=False
            )
            assert result(requests[15], "a3-situation")["body"] == CORRECTED_SITUATION
            assert (
                result(requests[15], "a3-understanding")["body"]
                == CORRECTED_UNDERSTANDING
            )
            assert {
                entry["text"]
                for entry in result(requests[16], "a3-sources")["messages"]
            } == {FIRST_INPUT, CORRECTION}
            assert (await client.get(path)).json() == revised
        assert len(requests) == len(replies)

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
