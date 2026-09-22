"""Offline SDK serialization only: no provider acceptance or persistence claim.

Checked 2026-09-13 against the installed OpenAI 3.13.0, Anthropic 1.5.0,
and httpx2 2.12.0 sources. Official interface references:
https://developers.openai.com/api/docs/guides/function-calling
https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools
https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls
https://pydantic.dev/docs/httpx2/advanced/transports/
"""

from __future__ import annotations

import json
import os
import socket
from copy import deepcopy
from typing import Any

import httpx2
import pytest
from anthropic import Anthropic
from jsonschema import Draft202012Validator
from openai import OpenAI
from result_fixtures import observed_result

from jd_relational.transport import model_command, tool_definition, tool_output


TOOLS = (
    "jd_create_task", "jd_revise_work", "jd_set_text", "jd_insert_item",
    "jd_delete_item", "jd_move_item", "jd_set_task_capability", "jd_replace_selection",
)
MODEL = "offline-fixture"
RESULT = observed_result()  # Synthetic confirmed no_change; no database is used.
PROMPT = "依已知工作內容建立或修訂任務；未知不補造。"
APP_FIELDS = {
    "document_id", "dataset_id", "base_view_token", "base_version",
    "base_revision", "base_revision_id", "operation_id", "operation_key",
    "ai_run_id", "run_id", "actor", "origin", "id", "position",
}


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # Replace the mapping without reading credential values or SDK defaults.
    monkeypatch.setattr(os, "environ", {})
    # Anthropic 1.5.0 also probes local profiles merely to warn about shadowing
    # when an explicit fake key is supplied. Disable only that discovery probe.
    monkeypatch.setattr("anthropic._client._has_auto_discoverable_credentials", lambda: False)

    def forbid_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Only the injected MockTransport may handle requests")

    monkeypatch.setattr(socket, "getaddrinfo", forbid_network)
    monkeypatch.setattr(socket, "create_connection", forbid_network)
    monkeypatch.setattr(socket.socket, "connect", forbid_network)
    monkeypatch.setattr(socket.socket, "connect_ex", forbid_network)


def _canonical_arguments_for(tool: str) -> dict[str, Any]:
    if tool == "jd_create_task":
        return {
            "container_ref": "issued-unassigned-tasks",
            "after_ref": None,
            "name": None,
            "description": "整理可辨識的前端交付版本與交接事項。\n已知限制需保留：結果不明 ≠ 失敗。🔎",
            "basis_refs": [],
            "outcomes": [
                {"text": "可辨識的前端交付版本", "basis_refs": []},
                {"text": "接收者可使用的交接說明", "basis_refs": []},
            ],
            "requirements": [
                {"text": "交付版本與檢查結果一致。", "basis_refs": []},
                {"text": "發布問題提供重現資訊；服務端部署與後端工程師協作。", "basis_refs": []},
                {"text": "客戶驗收仍由客戶確認。", "basis_refs": []},
            ],
            "capabilities": [
                {"capability_ref": "issued-shared-knowledge", "basis_refs": []},
                {"capability_ref": "issued-shared-skill", "basis_refs": []},
            ],
        }
    if tool == "jd_set_text":
        return {"target_field_ref": "issued-optional-name-field", "text": None, "basis_refs": []}
    if tool == "jd_insert_item":
        return {"item": {
            "kind": "knowledge", "container_ref": "issued-knowledge-container",
            "after_ref": None, "name": None,
            "description": "理解前後端資料格式與非同步狀態。\n適用範圍仍依各專案約定。🔎",
            "basis_refs": [],
        }}
    if tool in {"jd_delete_item", "jd_move_item"}:
        content_changes = [
            {"kind": "set_field", "target_field_ref": "issued-task-description",
             "text": "對有月檢約定的專案按月檢查；不套用到僅約定缺陷修正的專案。", "basis_refs": []},
            {"kind": "add_task_detail", "task_ref": "issued-task", "detail_kind": "requirement",
             "after_ref": None, "text": "超出服务約定的需求，先由負責窗口確認。", "basis_refs": []},
        ]
        if tool == "jd_delete_item":
            return {"target_ref": "issued-duty", "content_changes": content_changes}
        return {"target_ref": "issued-task", "destination_container_ref": "issued-unassigned-tasks",
                "after_ref": None, "content_changes": content_changes}
    if tool == "jd_set_task_capability":
        return {"task_ref": "issued-task", "capability_ref": "issued-shared-skill",
                "mode": "link", "basis_refs": []}
    if tool == "jd_replace_selection":
        return {"selection_ref": "issued-selection", "replacement_text": "每季🔎\n依服務約定",
                "basis_refs": []}
    assert tool == "jd_revise_work"
    return {
        "changes": [
            {
                "kind": "set_field",
                "target_field_ref": "issued-task-description",
                "text": "依服務約定釐清前端異常。\n不能確認根因時保留未知，不承諾客戶期限。",
                "basis_refs": [],
            },
            {
                "kind": "add_task_detail", "task_ref": "issued-task",
                "detail_kind": "requirement", "after_ref": None,
                "text": "區分觀察結果與待驗證假設，再轉交適當人員。",
                "basis_refs": [],
            },
            {"kind": "remove_task_detail", "detail_ref": "issued-wrong-requirement"},
            {
                "kind": "set_task_capability", "task_ref": "issued-task",
                "capability_ref": "issued-wrong-service-skill", "mode": "unlink",
                "basis_refs": [],
            },
            {
                "kind": "add_condition", "container_ref": "issued-shared-authority",
                "after_ref": None, "text": "對外承諾由專案經理協調。",
                "basis_refs": [],
            },
            {"kind": "remove_condition", "condition_ref": "issued-wrong-authority"},
        ]
    }


def _model_arguments(value: Any) -> Any:
    if isinstance(value, list):
        return [_model_arguments(item) for item in value]
    if not isinstance(value, dict):
        return value
    return {
        ("basis_evidence_keys" if key == "basis_refs" else key): _model_arguments(item)
        for key, item in value.items()
    }


def arguments_for(tool: str) -> dict[str, Any]:
    """Provider fixtures use the model-facing key; domain fixtures stay canonical."""
    return _model_arguments(_canonical_arguments_for(tool))


def schema_nodes(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from schema_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from schema_nodes(child)


def resolve_local_ref(schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        ref = node["$ref"]
        assert ref.startswith("#/$defs/"), "The wire schema must be self-contained"
        node = schema["$defs"][ref.removeprefix("#/$defs/").replace("~1", "/").replace("~0", "~")]
    return node


def variant_kinds(schema: dict[str, Any], node: dict[str, Any]) -> set[str]:
    variants = resolve_local_ref(schema, node)["anyOf"]
    kinds = set()
    for variant in variants:
        kind = resolve_local_ref(schema, variant)["properties"]["kind"]
        if "enum" in kind:
            assert len(kind["enum"]) == 1
            kinds.add(kind["enum"][0])
        else:
            kinds.add(kind["const"])
    assert len(kinds) == len(variants)
    return kinds


def assert_wire_schema(definition: dict[str, Any], provider: str, tool: str) -> None:
    assert definition["name"] == tool
    assert isinstance(definition["description"], str) and definition["description"]
    assert definition["strict"] is True
    if provider == "openai":
        assert definition["type"] == "function"
    schema = definition["parameters" if provider == "openai" else "input_schema"]
    assert schema["type"] == "object"
    assert "anyOf" not in schema and "oneOf" not in schema
    for node in schema_nodes(schema):
        properties = node.get("properties", {})
        assert APP_FIELDS.isdisjoint(properties), "App-owned context leaked into model parameters"
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(properties)

    args = arguments_for(tool)
    assert set(schema["properties"]) == set(args)
    validator = Draft202012Validator(schema)
    validator.validate(args)
    assert not validator.is_valid({**args, "operation_id": "model-must-not-supply-this"})

    if tool == "jd_create_task":
        assert set(schema["properties"]) == set(args)
        # Explicit null is legal; omitting a required nullable key is not.
        assert args["name"] is None and args["after_ref"] is None
        missing_name = deepcopy(args)
        del missing_name["name"]
        assert not validator.is_valid(missing_name)
    elif tool == "jd_revise_work":
        changes = resolve_local_ref(schema, schema["properties"]["changes"])
        assert variant_kinds(schema, changes["items"]) == {
            "set_field", "add_task_detail", "remove_task_detail",
            "set_task_capability", "add_condition", "remove_condition",
        }
        nullable_text = deepcopy(args)
        nullable_text["changes"][0]["text"] = None
        validator.validate(nullable_text)
        missing_text = deepcopy(nullable_text)
        del missing_text["changes"][0]["text"]
        assert not validator.is_valid(missing_text)
    elif tool == "jd_insert_item":
        assert variant_kinds(schema, schema["properties"]["item"]) == {
            "duty", "collaborator", "knowledge", "skill", "outcome", "requirement", "condition",
        }
    elif tool in {"jd_delete_item", "jd_move_item"}:
        changes = resolve_local_ref(schema, schema["properties"]["content_changes"])
        assert variant_kinds(schema, changes["items"]) == {"set_field", "add_task_detail"}
    elif tool == "jd_set_text":
        assert args["text"] is None
        assert not validator.is_valid({key: value for key, value in args.items() if key != "text"})
    elif tool == "jd_replace_selection":
        assert set(schema["properties"]) == {"selection_ref", "replacement_text", "basis_evidence_keys"}
        assert not validator.is_valid({**args, "start": 0})
        assert not validator.is_valid({**args, "replacement_text": None})


def mock_transport(provider: str, tool: str, args: dict[str, Any]):
    captured: list[dict[str, Any]] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "POST"
        assert request.url.scheme == "https" and request.url.host == "offline.invalid"
        assert request.url.path == ("/responses" if provider == "openai" else "/v1/messages")
        assert len(captured) < 2, "Unexpected extra request or retry"
        body = json.loads(request.content)
        assert body["model"] == MODEL
        captured.append(body)
        first = len(captured) == 1
        if provider == "openai":
            payload = {
                "id": "resp_offline_first" if first else "resp_offline_final",
                "object": "response", "created_at": 0, "model": MODEL,
                "status": "completed", "error": None, "incomplete_details": None,
                "parallel_tool_calls": False, "tool_choice": "auto", "tools": body["tools"],
                "output": [{
                    "id": "fc_offline_item", "type": "function_call",
                    "call_id": "call_offline_result", "name": tool,
                    "arguments": json.dumps(args, ensure_ascii=False), "status": "completed",
                }] if first else [],
            }
        else:
            payload = {
                "id": "msg_offline_first" if first else "msg_offline_final",
                "type": "message", "role": "assistant", "model": MODEL,
                "content": [{
                    "type": "tool_use", "id": "toolu_offline_result",
                    "name": tool, "input": args,
                }] if first else [{"type": "text", "text": "離線回傳形狀已接收；未保存。"}],
                "stop_reason": "tool_use" if first else "end_turn",
                "stop_sequence": None, "usage": {"input_tokens": 0, "output_tokens": 0},
            }
        return httpx2.Response(200, json=payload)

    return httpx2.MockTransport(handle), captured


@pytest.mark.parametrize("tool", TOOLS)
def test_openai_responses_wire_round_trip(tool: str) -> None:
    args = arguments_for(tool)
    definition = tool_definition("openai", tool)
    transport, captured = mock_transport("openai", tool, args)
    with httpx2.Client(transport=transport, trust_env=False) as http_client:
        with OpenAI(
            api_key="fake-offline-key", base_url="https://offline.invalid",
            max_retries=0, http_client=http_client,
        ) as client:
            response = client.responses.create(
                model=MODEL, input=[{"role": "user", "content": PROMPT}],
                tools=[definition], store=False,
            )
            call = response.output[0]
            assert call.type == "function_call"
            assert call.id == "fc_offline_item" and call.call_id == "call_offline_result"
            assert model_command(call.name, call.arguments) == model_command(tool, args)
            result_block = tool_output("openai", call.call_id, deepcopy(RESULT))
            client.responses.create(
                model=MODEL, store=False, tools=[definition],
                input=[
                    {"role": "user", "content": PROMPT},
                    call.model_dump(mode="json", exclude_none=True),
                    result_block,
                ],
            )

    assert len(captured) == 2
    for body in captured:
        assert body["store"] is False
        assert body["tools"] == [definition]
        assert_wire_schema(body["tools"][0], "openai", tool)
    echoed_call, result = captured[1]["input"][-2:]
    assert json.loads(echoed_call["arguments"]) == args
    assert result["type"] == "function_call_output"
    assert result["call_id"] == echoed_call["call_id"] == "call_offline_result"
    assert result["call_id"] != echoed_call["id"]
    assert json.loads(result["output"]) == RESULT


@pytest.mark.parametrize("tool", TOOLS)
def test_anthropic_messages_wire_round_trip(tool: str) -> None:
    args = arguments_for(tool)
    definition = tool_definition("anthropic", tool)
    transport, captured = mock_transport("anthropic", tool, args)
    with httpx2.Client(transport=transport, trust_env=False) as http_client:
        with Anthropic(
            api_key="fake-offline-key", base_url="https://offline.invalid",
            max_retries=0, http_client=http_client,
        ) as client:
            response = client.messages.create(
                model=MODEL, max_tokens=1024, tools=[definition],
                messages=[{"role": "user", "content": PROMPT}],
            )
            call = response.content[0]
            assert call.type == "tool_use" and call.id == "toolu_offline_result"
            assert model_command(call.name, call.input) == model_command(tool, args)
            result_block = tool_output("anthropic", call.id, deepcopy(RESULT))
            client.messages.create(
                model=MODEL, max_tokens=1024, tools=[definition],
                messages=[
                    {"role": "user", "content": PROMPT},
                    {"role": "assistant", "content": [call.model_dump(mode="json", exclude_none=True)]},
                    {"role": "user", "content": [result_block]},
                ],
            )

    assert len(captured) == 2
    for body in captured:
        assert body["tools"] == [definition]
        assert_wire_schema(body["tools"][0], "anthropic", tool)
    assistant, user = captured[1]["messages"][-2:]
    assert assistant["role"] == "assistant" and user["role"] == "user"
    echoed_call = assistant["content"][0]
    assert echoed_call["input"] == args
    assert len(user["content"]) == 1
    result = user["content"][0]
    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == echoed_call["id"] == "toolu_offline_result"
    assert json.loads(result["content"]) == RESULT
    assert result.get("is_error", False) is False
