"""正式 Host 與離線匯出共用可生成的 SSE 契約。"""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from caliburn.export_openapi import export_openapi
from caliburn.host.app import build_app
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION


@pytest.fixture(scope="module")
def agent_openapi() -> dict[str, Any]:
    return build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url="postgresql+psycopg://localhost:1/unreachable",
    ).openapi()


def test_agent_sse_documents_each_event_payload_without_a_json_response(
    agent_openapi: dict[str, Any],
) -> None:
    document = agent_openapi
    components = document["components"]["schemas"]
    assert "TurnEvent" in components
    content = document["paths"][
        "/workspaces/{workspace_id}/agent/turns/{turn_id}/events"
    ]["get"]["responses"]["200"]["content"]
    assert set(content) == {"text/event-stream"}
    assert "schema" not in content["text/event-stream"]
    variants = content["text/event-stream"]["itemSchema"]["oneOf"]
    by_event = {item["properties"]["event"]["const"]: item for item in variants}
    assert set(by_event) == {
        "status",
        "text_delta",
        "reasoning_summary_delta",
        "tool_call",
        "resync_required",
        "cancellation",
    }
    for variant in by_event.values():
        assert set(variant["required"]) == {"event", "data"}
        data = variant["properties"]["data"]
        assert data["type"] == "string"
        assert data["contentMediaType"] == "application/json"
        assert (
            data["contentSchema"]["$ref"].removeprefix("#/components/schemas/")
            in components
        )
    assert by_event["status"]["properties"]["data"]["contentSchema"] == {
        "$ref": "#/components/schemas/TurnView"
    }


def test_event_schema_reuses_rest_usage_and_cancellation_contracts(
    agent_openapi: dict[str, Any],
) -> None:
    components = agent_openapi["components"]["schemas"]
    assert components["TurnView"]["properties"]["usage"]["anyOf"][0] == {
        "$ref": "#/components/schemas/UsageView"
    }
    assert components["CancellationData"]["properties"]["status"] == {
        "$ref": "#/components/schemas/CancelStatus"
    }
    assert components["CancelStatus"]["enum"] == ["pending", "completed"]


def test_all_transitive_event_references_resolve(
    agent_openapi: dict[str, Any],
) -> None:
    components = agent_openapi["components"]["schemas"]
    pending = [components["TurnEvent"]]
    visited = {"TurnEvent"}
    while pending:
        node = pending.pop()
        if isinstance(node, list):
            pending.extend(node)
        elif isinstance(node, dict):
            if "$ref" in node:
                reference = node["$ref"]
                assert reference.startswith("#/components/schemas/")
                name = reference.removeprefix("#/components/schemas/")
                assert name in components, f"missing event component: {name}"
                if name not in visited:
                    visited.add(name)
                    pending.append(components[name])
            pending.extend(node.values())


def test_offline_export_keeps_the_live_agent_event_contract(
    tmp_path: Path, agent_openapi: dict[str, Any]
) -> None:
    destination = tmp_path / "openapi.json"
    asyncio.run(export_openapi(destination))
    exported = json.loads(destination.read_text(encoding="utf-8"))
    event_path = "/workspaces/{workspace_id}/agent/turns/{turn_id}/events"
    assert exported["paths"][event_path] == agent_openapi["paths"][event_path]
    assert exported["components"]["schemas"] == agent_openapi["components"]["schemas"]


@pytest.mark.parametrize(
    "event,data",
    [
        ("text_delta", {"model_step": 1, "delta": "文字\n增量"}),
        ("reasoning_summary_delta", {"model_step": 1, "delta": "摘要"}),
        (
            "tool_call",
            {"model_step": 2, "call_id": "call-1", "name": "read", "arguments": "{}"},
        ),
        ("resync_required", {"reason": "slow_subscriber"}),
        (
            "cancellation",
            {"turn_id": "12345678-1234-1234-1234-123456789012", "status": "pending"},
        ),
        (
            "status",
            {
                "workspace_id": "12345678-1234-1234-1234-123456789012",
                "turn_id": "12345678-1234-1234-1234-123456789013",
                "status": "running",
                "input": "原文",
                "output": None,
                "interrupts": [],
                "usage": None,
                "compactions": [],
                "created_at": "2026-11-06T01:00:00Z",
                "updated_at": "2026-11-06T01:00:00Z",
            },
        ),
    ],
)
def test_generated_envelope_validates_payload_and_rejects_wrong_event(
    agent_openapi: dict[str, Any], event: str, data: dict[str, Any]
) -> None:
    validator = Draft202012Validator(
        {
            "$ref": "#/components/schemas/TurnEvent",
            "components": agent_openapi["components"],
        },
        format_checker=FormatChecker(),
    )
    validator.validate({"event": event, "data": data})
    assert not validator.is_valid({"event": event, "data": {}})
    assert not validator.is_valid({"event": "unknown", "data": data})
    assert not validator.is_valid({"data": data})
