"""Host 在所有合法 Context 順序下計數真正外送的人工 JD 差異。"""

import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx2
import pytest
from sqlalchemy import Engine

from caliburn.host.agent_settings import load_agent_configuration
from tests.integration.agent.http_support import api_client
from tests.integration.agent.jd_bundle_support import wait_for_idle
from tests.unit.bundles.context.support import compacted_payload
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


@pytest.mark.parametrize("window", [None, False, True], ids=["default", "off", "on"])
@pytest.mark.parametrize("context_first", [True, False], ids=["before-jd", "after-jd"])
@pytest.mark.parametrize("capacity", ["fits", "compact", "still-full"])
def test_capacity_gate_sees_http_manual_changes_before_model_send(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    tmp_path: Path,
    window: bool | None,
    context_first: bool,
    capacity: str,
) -> None:
    context: dict[str, object] = {"threshold_tokens": 100}
    context_bundle: dict[str, object] = {
        "module": "caliburn.bundles.context",
        "config": context,
    }
    if window is not None:
        context_bundle["plugins"] = (
            ["window", "native_compaction"] if window else ["native_compaction"]
        )
    configured = [
        context_bundle,
        {"module": "caliburn.bundles.job_description"},
    ]
    if not context_first:
        configured.reverse()
    path = tmp_path / "agent.json"
    path.write_text(
        json.dumps(
            {
                "agent_id": "http-test",
                "resume_version": "v1",
                "model": "offline-model",
                "bundles": configured,
            }
        ),
        encoding="utf-8",
    )
    configuration = load_agent_configuration(
        path, checkpoint_conninfo=checkpoint_conninfo
    )
    calls: list[tuple[str, dict[str, Any]]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        body = request_body(request)
        calls.append((request.url.path, body))
        if request.url.path.endswith("input_tokens"):
            has_changes = "jd_manual_changes" in json.dumps(body["input"])
            is_compacted = any(
                item.get("type") == "compaction" for item in body["input"]
            )
            full = (has_changes and capacity != "fits") or (
                is_compacted and capacity == "still-full"
            )
            return httpx2.Response(
                200,
                json={
                    "object": "response.input_tokens",
                    "input_tokens": 100 if full else 1,
                },
            )
        if request.url.path.endswith("compact"):
            return httpx2.Response(200, json=compacted_payload())
        assert request.url.path == "/v1/responses"
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=configuration.bundles,
        ) as client:
            workspace = await client.post(
                "/workspaces", json={"interviewee_name": "合成人工 JD 修改"}
            )
            assert workspace.status_code == 201, workspace.text
            base = f"/workspaces/{workspace.json()['workspace_id']}"
            original = await client.get(base + "/job-description")
            assert original.status_code == 200, original.text
            jd = original.json()
            changed = await client.patch(
                base + f"/job-descriptions/{jd['job_description_id']}",
                json={"expected_version": 1, "purpose": "人工新增：核對交付資料"},
            )
            assert changed.status_code == 200, changed.text
            assert changed.json()["version"] == 2
            submitted = await client.post(
                base + "/agent/turns",
                json={"turn_id": str(uuid4()), "input": "檢查人工修改後的 JD"},
            )
            assert submitted.status_code == 202, submitted.text
            turn = await wait_for_idle(client, submitted.headers["Location"])
            assert turn["status"] == (
                "interrupted" if capacity == "still-full" else "completed"
            ), turn

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    counts = [body for route, body in calls if route.endswith("input_tokens")]
    compacts = [body for route, body in calls if route.endswith("compact")]
    models = [body for route, body in calls if route == "/v1/responses"]
    changes = [
        json.loads(item["content"])
        for item in counts[0]["input"]
        if item.get("role") == "user"
        and isinstance(item.get("content"), str)
        and "jd_manual_changes" in item["content"]
    ]
    assert len(changes) == 1
    assert changes[0]["before_version"] == 1
    assert changes[0]["after_version"] == 2
    assert changes[0]["items"][0]["after"]["purpose"] == "人工新增：核對交付資料"
    assert counts[0]["instructions"]
    assert counts[0]["tools"]
    if capacity != "fits":
        assert len(compacts) == 1
        assert compacts[0]["input"] == counts[0]["input"]
        assert compacts[0]["instructions"] == counts[0]["instructions"]
        assert len(counts) == 2
        assert counts[1]["input"] == compacted_payload()["output"]
        assert counts[1]["tools"] == counts[0]["tools"]
    else:
        assert not compacts
        assert len(counts) == 1
    if capacity == "still-full":
        assert not models
    else:
        (model,) = models
        assert counts[-1] == {
            key: value
            for key, value in model.items()
            if key
            not in {
                "max_output_tokens",
                "store",
                "background",
                "stream",
                "include",
                "service_tier",
            }
        }
