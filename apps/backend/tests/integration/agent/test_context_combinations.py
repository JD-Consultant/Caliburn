"""Host 的可移除 Bundle 組合，各自保留資料與跨輪窗口責任。"""

import asyncio
import json
from functools import partial
from itertools import product
from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest
from sqlalchemy import Engine

from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.plan.application.plans import initialize_plan, patch_plan
from caliburn.modules.plan.infrastructure.persistence.unit_of_work import (
    SqlAlchemyPlanUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.http_support import api_client
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    message,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


@pytest.mark.parametrize(
    ("memory", "interview", "plan"), tuple(product((False, True), repeat=3))
)
@pytest.mark.parametrize(
    ("window", "native"),
    [(False, False), (True, False), (False, True), (True, True)],
    ids=("without-context", "window", "native", "window-and-native"),
)
def test_optional_bundles_complete_two_turns_in_every_context_mode(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
    memory: bool,
    interview: bool,
    plan: bool,
    window: bool,
    native: bool,
) -> None:
    sessions = create_session_factory(pg_engine)
    plan_factory = partial(SqlAlchemyPlanUnitOfWork, sessions)
    initialize_plan(workspace_id=jd_workspace_id, uow_factory=plan_factory)
    patch_plan(
        workspace_id=jd_workspace_id,
        expected_version=1,
        diff="@@\n+既有計畫只供啟用的 Plan 能力讀取\n*** End of File",
        uow_factory=plan_factory,
    )
    bundles = []
    if interview:
        bundles.append(
            BundleConfig(
                "caliburn.bundles.interview",
                plugins=(
                    "interview",
                    "interview_source_prompt",
                    *(("interview_context",) if not window else ()),
                    *(("interview_read",) if not memory else ()),
                    *(("interview_navigation",) if not memory and not window else ()),
                ),
            )
        )
        if window and not memory:
            bundles.append(BundleConfig("caliburn.bundles.interview.window"))
    if memory:
        bundles.append(
            BundleConfig(
                "caliburn.bundles.memory",
                plugins=(
                    "memory_context",
                    "memory_prompt",
                    "memory_read",
                    *(("memory_window",) if window else ()),
                ),
            )
        )
    if plan:
        bundles.append(BundleConfig("caliburn.bundles.plan"))
    if window or native:
        bundles.append(
            BundleConfig(
                "caliburn.bundles.context",
                plugins=(
                    *(("window",) if window else ()),
                    *(("native_compaction",) if native else ()),
                ),
            )
        )

    requests: list[dict[str, Any]] = []
    counts: list[dict[str, Any]] = []
    inputs = ("第一輪獨有原話", "第二輪獨有原話")

    def respond(request: httpx2.Request) -> httpx2.Response:
        body = request_body(request)
        if request.url.path.endswith("input_tokens"):
            counts.append(body)
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 1}
            )
        assert request.url.path == "/v1/responses"
        requests.append(body)
        return sse_response(
            EventStream(
                response_events(
                    response_payload([message(text=f"第{len(requests)}輪完整回覆")])
                )
            )
        )

    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=tuple(bundles),
        ) as client:
            for text in inputs:
                submitted = await client.post(
                    f"/workspaces/{jd_workspace_id}/agent/turns",
                    json={"turn_id": str(uuid4()), "input": text},
                )
                assert submitted.status_code == 202, submitted.text
                async with asyncio.timeout(10):
                    while True:
                        turn = (await client.get(submitted.headers["Location"])).json()
                        if turn["status"] != "running":
                            break
                        await asyncio.sleep(0.01)
                assert turn["status"] == "completed", turn

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(requests) == 2
    assert len(counts) == ((3 if window else 2) if native else 0)
    for index, request in enumerate(requests):
        encoded = json.dumps(request["input"], ensure_ascii=False)
        assert encoded.count(inputs[index]) == 1
        assert ("memory_navigation" in encoded) == (window and memory)
        assert ("consultant_interview_plan" in encoded) == (window and plan)
        assert ("既有計畫只供啟用的 Plan 能力讀取" in encoded) == (window and plan)
        tools = {tool["name"] for tool in request["tools"]}
        assert ("read_work_situation_map" in tools) == memory
        assert ("read_interview_plan" in tools) == plan
    if window:
        first_input = requests[0]["input"]
        assert requests[1]["input"][: len(first_input)] == first_input
        assert (
            json.dumps(requests[1]["input"], ensure_ascii=False).count(inputs[0]) == 1
        )
        assert any(
            item.get("type") == "message"
            and item.get("role") == "assistant"
            and item.get("phase") == "final_answer"
            and any(part.get("text") == "第1輪完整回覆" for part in item["content"])
            for item in requests[1]["input"]
        )
