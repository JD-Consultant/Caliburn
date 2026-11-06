"""正式 Host 從已完成訪談整理並發布；重啟能補回遺失通知。"""

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any, cast
from uuid import UUID, uuid4

import httpx2
import pytest
from sqlalchemy import Engine

from caliburn.host.app import build_app
from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.interview.application.withdrawal import withdraw_turn
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.model_references import ReferenceTarget
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.http_support import api_client
from tests.integration.agent.memory_reference_support import interview_ref
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    message,
    request_body,
    response_events,
    response_payload,
    sse_response,
)

type ModelReply = (
    list[dict[str, object]] | Callable[[dict[str, Any]], list[dict[str, object]]]
)


@pytest.mark.parametrize(
    ("lost_notification", "compaction", "candidate"),
    [
        (False, False, False),
        (True, False, False),
        (False, True, True),
        (False, False, True),
    ],
)
def test_host_publishes_completed_interview_and_recovers_notification(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    lost_notification: bool,
    compaction: bool,
    candidate: bool,
) -> None:
    from caliburn.host.memory import MemoryHost

    caplog.set_level(logging.INFO, logger="caliburn.host.memory")
    requests: list[dict[str, Any]] = []
    counts: list[dict[str, Any]] = []
    compacted_inputs: list[list[object]] = []
    outputs: list[ModelReply] = [
        [call("request_memory_consolidation", "request", "{}")],
        [message(text="已了解盤點工作。")],
        lambda request: [
            call(
                "create_work_situation",
                "situation",
                json.dumps(
                    {
                        "title": "庫存盤點",
                        "description": "逐筆核對",
                        "body": "逐筆核對庫存差異後送主管複核。",
                        "interview_references": [
                            interview_ref(request, "逐筆核對庫存差異後送主管複核。")
                        ],
                    }
                ),
            )
        ],
        [message(text='{"status":"complete"}')],
        [
            call(
                "create_work_understanding",
                "understanding",
                json.dumps(
                    {
                        "title": "盤點分工",
                        "description": "本人核對主管複核",
                        "body": "本人核對差異，主管負責複核。",
                        "work_situation_references": ["庫存盤點"],
                    }
                ),
            )
        ],
        [message(text='{"status":"complete"}')],
    ]
    if candidate and not compaction:
        outputs.extend(
            [
                [
                    call(
                        "read_work_situation",
                        "published-read",
                        '{"target_title":"庫存盤點"}',
                    )
                ],
                [message(text="已查閱發布的盤點內容。")],
            ]
        )

    def respond(request: httpx2.Request) -> httpx2.Response:
        body = request_body(request)
        if request.url.path == "/v1/responses/input_tokens":
            counts.append(body)
            return httpx2.Response(
                200,
                json={
                    "object": "response.input_tokens",
                    "input_tokens": 100
                    if len(requests) % 2
                    and not any(
                        item.get("type") == "compaction" for item in body["input"]
                    )
                    else 50,
                },
            )
        if request.url.path == "/v1/responses/compact":
            output = [
                {
                    "id": f"retained_{len(compacted_inputs)}",
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": body["input"][0]["content"]}
                    ],
                },
                {
                    "id": f"cmp_{len(compacted_inputs)}",
                    "type": "compaction",
                    "encrypted_content": f"opaque-{len(compacted_inputs)}",
                },
            ]
            compacted_inputs.append(output)
            return httpx2.Response(
                200,
                json={
                    "id": f"compaction_{len(compacted_inputs)}",
                    "object": "response.compaction",
                    "created_at": 1793491200,
                    "output": output,
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 40,
                        "total_tokens": 140,
                        "input_tokens_details": {"cached_tokens": 0},
                        "output_tokens_details": {"reasoning_tokens": 0},
                    },
                },
            )
        requests.append(body)
        reply = outputs[len(requests) - 1]
        payload = response_payload(reply(body) if callable(reply) else reply)
        return sse_response(EventStream(response_events(payload)))

    bundles: tuple[BundleConfig, ...] = (
        BundleConfig(
            "caliburn.bundles.interview",
            plugins=(
                "interview",
                "interview_source_prompt",
                *(("interview_context",) if not candidate else ()),
            ),
        ),
        BundleConfig(
            "tests.integration.agent.memory_candidate_bundle"
            if candidate
            else "caliburn.bundles.memory",
            {
                "threshold_tokens": 100,
                "context_plugins": ["native_compaction"] if compaction else [],
            }
            if candidate
            else {},
        ),
    )
    if candidate:
        bundles += (
            BundleConfig(
                "caliburn.bundles.context",
                {"threshold_tokens": 100},
                plugins=("window", *(("native_compaction",) if compaction else ())),
            ),
        )

    async def wait_publication(client: httpx2.AsyncClient, path: str) -> dict[str, Any]:
        async with asyncio.timeout(15):
            while True:
                response = await client.get(path)
                assert response.status_code == 200, response.text
                if response.json()["published_version"] is not None:
                    return cast(dict[str, Any], response.json())
                await asyncio.sleep(0.01)

    async def run() -> None:
        original_notify = MemoryHost.notify
        if lost_notification:
            monkeypatch.setattr(MemoryHost, "notify", lambda *_: None)
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=bundles,
        ) as client:
            workspace = (
                await client.post(
                    "/workspaces",
                    json={
                        "interviewee_name": "記憶接線",
                    },
                )
            ).json()["workspace_id"]
            path = f"/workspaces/{workspace}/memory"
            assert (await client.get(path)).json()["published_version"] is None
            turn_id = uuid4()
            submitted = await client.post(
                f"/workspaces/{workspace}/agent/turns",
                json={
                    "turn_id": str(turn_id),
                    "input": "逐筆核對庫存差異後送主管複核。",
                },
            )
            assert submitted.status_code == 202, submitted.text
            async with asyncio.timeout(10):
                while (await client.get(submitted.headers["Location"])).json()[
                    "status"
                ] == "running":
                    await asyncio.sleep(0.01)
            assert (await client.get(submitted.headers["Location"])).json()[
                "status"
            ] == "completed"
            if lost_notification:
                assert len(requests) == 2
                assert (await client.get(path)).json()["published_version"] is None
            else:
                await wait_publication(client, path)
        monkeypatch.setattr(MemoryHost, "notify", original_notify)
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=bundles,
        ) as client:
            saved = await wait_publication(client, path)
            assert {item["title"] for item in saved["items"]} == {
                "庫存盤點",
                "盤點分工",
            }
            version = saved["published_version"]
            entries = {item["kind"]: item for item in saved["items"]}
            situation = (
                await client.get(
                    f"{path}/versions/{version}/items/{entries['situation']['item_id']}"
                )
            ).json()
            understanding = (
                await client.get(
                    f"{path}/versions/{version}/items/{entries['understanding']['item_id']}"
                )
            ).json()
            transcript = (
                await client.get(
                    f"/workspaces/{workspace}/interview/messages",
                    params={"turn_id": str(turn_id)},
                )
            ).json()
            assert [entry["text"] for entry in transcript] == [
                "逐筆核對庫存差異後送主管複核。",
                "已了解盤點工作。",
            ]
            assert situation["source_ids"] == [transcript[0]["message_id"]]
            assert saved["covered_through_message_id"] == transcript[-1]["message_id"]
            reference = interview_ref(requests[2], "逐筆核對庫存差異後送主管複核。")
            assert reference.startswith("message_")
            references = SqlAlchemyModelReferences(create_session_factory(pg_engine))
            assert references.resolve_refs(UUID(workspace), [reference]) == {
                reference: ReferenceTarget("message", UUID(situation["source_ids"][0]))
            }
            assert understanding["source_ids"] == [situation["item_id"]]
            assert str(situation["source_ids"][0]) in json.dumps(transcript)
            assert (await client.get(f"{path}/versions/{version}")).json() == saved
            if candidate and not compaction:
                submitted = await client.post(
                    f"/workspaces/{workspace}/agent/turns",
                    json={"turn_id": str(uuid4()), "input": "查閱已發布的庫存盤點。"},
                )
                assert submitted.status_code == 202
                async with asyncio.timeout(10):
                    while (await client.get(submitted.headers["Location"])).json()[
                        "status"
                    ] == "running":
                        await asyncio.sleep(0.01)
                assert (await client.get(submitted.headers["Location"])).json()[
                    "status"
                ] == "completed"
                navigation = json.loads(requests[6]["input"][0]["content"])
                assert navigation["published_version"] == version
                result = next(
                    json.loads(item["output"])
                    for item in requests[7]["input"]
                    if item.get("type") == "function_call_output"
                    and item.get("call_id") == "published-read"
                )
                assert result["body"] == situation["body"]
                assert result["interview_references"] == [reference]
        assert len(requests) == (8 if candidate and not compaction else 6)
        if candidate:
            from tests.integration.agent.memory_candidate_bundle import DEFAULT_NOTE

            assert requests[2]["instructions"].endswith(DEFAULT_NOTE)
            assert DEFAULT_NOTE not in requests[0]["instructions"]
            assert DEFAULT_NOTE not in requests[4]["instructions"]
        if compaction:
            assert len(compacted_inputs) == 3
            for index, compacted in zip((1, 3, 5), compacted_inputs, strict=True):
                assert requests[index]["input"] == compacted
        elif candidate:
            assert not counts
        else:
            assert len(counts) == 4
            for counted, sent in zip(counts, requests[2:], strict=True):
                for request_field in ("input", "instructions", "tools"):
                    assert counted[request_field] == sent[request_field]
        app = build_app(
            reference_configuration=HOST_REFERENCE_CONFIGURATION,
            database_url=pg_engine.url.render_as_string(hide_password=False),
        )
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app), base_url="http://testserver"
            ) as reader,
        ):
            assert (await reader.get(path)).json() == saved
            assert (await reader.post(path, json={})).status_code == 405

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    finished = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "memory.consolidation.finished"
    ]
    assert finished
    assert all(
        getattr(record, "turn_id", None) and getattr(record, "workspace_id", None)
        for record in finished
    )
    assert "逐筆核對庫存差異後送主管複核。" not in caplog.text


def test_recovery_skips_withdrawn_latest_intent_and_processes_earlier_valid_request(
    pg_engine: Engine, checkpoint_conninfo: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from caliburn.host.memory import MemoryHost

    outputs: list[ModelReply] = [
        [call("request_memory_consolidation", "first", "{}")],
        [message(text="已記錄有效工作。")],
        [call("request_memory_consolidation", "withdrawn", "{}")],
        [message(text="第二輪回覆。")],
        lambda request: [
            call(
                "create_work_situation",
                "situation",
                json.dumps(
                    {
                        "title": "有效工作",
                        "description": "保留首輪",
                        "body": "每日盤點庫存。",
                        "interview_references": [
                            interview_ref(request, "每日盤點庫存。")
                        ],
                    }
                ),
            )
        ],
        [message(text='{"status":"complete"}')],
        [message(text='{"status":"complete"}')],
    ]
    replies = iter(outputs)
    requests: list[dict[str, Any]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/v1/responses/input_tokens":
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 1}
            )
        body = request_body(request)
        requests.append(body)
        reply = next(replies)
        return sse_response(
            EventStream(
                response_events(
                    response_payload(reply(body) if callable(reply) else reply)
                )
            )
        )

    bundles = (
        BundleConfig(
            "caliburn.bundles.interview",
            plugins=("interview", "interview_context", "interview_source_prompt"),
        ),
        BundleConfig("caliburn.bundles.memory"),
    )

    async def run() -> None:
        original = MemoryHost.notify
        monkeypatch.setattr(MemoryHost, "notify", lambda *_: None)
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=bundles,
        ) as client:
            workspace = (
                await client.post(
                    "/workspaces",
                    json={
                        "interviewee_name": "撤回意圖",
                    },
                )
            ).json()["workspace_id"]
            last_turn = None
            for body in ["每日盤點庫存。", "這輪將被撤回。"]:
                last_turn = uuid4()
                created = await client.post(
                    f"/workspaces/{workspace}/agent/turns",
                    json={
                        "turn_id": str(last_turn),
                        "input": body,
                    },
                )
                assert created.status_code == 202
                async with asyncio.timeout(10):
                    while (await client.get(created.headers["Location"])).json()[
                        "status"
                    ] == "running":
                        await asyncio.sleep(0.01)
                assert (await client.get(created.headers["Location"])).json()[
                    "status"
                ] == "completed"
        assert last_turn is not None
        sessions = create_session_factory(pg_engine)
        await asyncio.to_thread(
            withdraw_turn,
            workspace_id=UUID(workspace),
            turn_id=last_turn,
            uow_factory=lambda: SqlAlchemyInterviewUnitOfWork(sessions),
        )
        monkeypatch.setattr(MemoryHost, "notify", original)
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=bundles,
        ) as client:
            async with asyncio.timeout(8):
                while True:
                    saved = (await client.get(f"/workspaces/{workspace}/memory")).json()
                    if saved["published_version"] is not None:
                        break
                    await asyncio.sleep(0.02)
            assert [item["title"] for item in saved["items"]] == ["有效工作"]
            assert interview_ref(requests[4], "每日盤點庫存。").startswith("message_")
            assert "這輪將被撤回。" not in json.dumps(
                requests[4]["input"], ensure_ascii=False
            )
        assert next(replies, None) is None

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
