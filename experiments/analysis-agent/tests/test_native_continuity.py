"""Wire-level checks: real adapter/SDK/serializer, synthetic HTTP responses.

No provider access or model-quality claim. A regression that drops native items
or re-enables server storage must fail at the outgoing request boundary.
"""

import json
from copy import deepcopy

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from openai.types.responses import Response

from analysis_agent.provider import build_model
from analysis_agent.context import server_compaction_view


def response_body(output: list[dict], response_id: str = "resp_test") -> dict:
    """Validate synthetic items with the pinned official SDK response schema."""
    return Response.model_validate(
        {
            "id": response_id,
            "object": "response",
            "created_at": 1788624000,
            "model": "gpt-5.6-luna",
            "status": "completed",
            "output": output,
            "parallel_tool_calls": False,
            "tool_choice": "auto",
            "tools": [],
            "store": False,
            "reasoning": {"effort": "medium", "context": "all_turns"},
            "usage": {
                "input_tokens": 100,
                "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                "output_tokens": 20,
                "output_tokens_details": {"reasoning_tokens": 10},
                "total_tokens": 120,
            },
        }
    ).model_dump(mode="json", exclude_none=True)


def assistant_text(text: str, item_id: str = "msg_test", phase: str = "final_answer") -> dict:
    return {
        "type": "message",
        "id": item_id,
        "role": "assistant",
        "status": "completed",
        "phase": phase,
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }


def test_binding_sends_stateless_all_turns_to_responses():
    requests: list[httpx.Request] = []
    body = response_body([assistant_text("請說明工作內容。")])

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=body)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = build_model(model="gpt-5.6-luna", api_key="offline-not-a-key", http_client=client)
        answer = model.invoke([HumanMessage("我接案製作網站。")])

    payload = json.loads(requests[0].content)
    assert requests[0].url.path == "/v1/responses"
    assert payload.get("store") is False
    assert payload.get("reasoning") == {"effort": "medium", "context": "all_turns"}
    assert payload.get("parallel_tool_calls") is False
    assert "previous_response_id" not in payload
    assert answer.text == "請說明工作內容。"


def test_tool_reasoning_and_phase_survive_serialization_and_next_user_turn():
    payloads: list[dict] = []
    bodies = [
        response_body([
            {"type": "reasoning", "id": "rs_before_tool", "summary": [], "encrypted_content": "opaque-test-1"},
            assistant_text("先查看 A 網站案例。", "msg_comment", "commentary"),
            {"type": "function_call", "id": "fc_case", "call_id": "call_case", "name": "read_case", "arguments": '{"name":"A"}', "status": "completed"},
        ], "resp_first"),
        response_body([
            {"type": "reasoning", "id": "rs_after_tool", "summary": [], "encrypted_content": "opaque-test-2"},
            assistant_text("A 網站使用單次付款。", "msg_answer"),
        ], "resp_second"),
        response_body([assistant_text("B 網站的月租如何處理？", "msg_followup")], "resp_third"),
    ]

    def respond(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json=bodies[len(payloads) - 1])

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = build_model(model="gpt-5.6-luna", api_key="offline-not-a-key", http_client=client)
        model = model.bind_tools([{
            "type": "function",
            "name": "read_case",
            "description": "Read a previously saved case.",
            "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"], "additionalProperties": False},
            "strict": True,
        }])
        messages = [HumanMessage("我接案製作網站，請查看 A 案例。")]
        messages.append(model.invoke(messages))
        messages.append(ToolMessage("A 網站使用單次付款", tool_call_id="call_case"))
        serializer = JsonPlusSerializer()
        messages = serializer.loads_typed(serializer.dumps_typed(messages))
        messages.append(model.invoke(messages))
        messages = serializer.loads_typed(serializer.dumps_typed(messages))
        messages.append(HumanMessage("B 網站改採月租。"))
        model.invoke(messages)

    wire = payloads[1]["input"]
    assert [item["type"] for item in wire] == ["message", "reasoning", "message", "function_call", "function_call_output"]
    assert wire[1]["encrypted_content"] == "opaque-test-1"
    assert wire[2]["phase"] == "commentary"
    assert wire[2]["content"][0]["text"] == "先查看 A 網站案例。"
    assert wire[3]["call_id"] == wire[4]["call_id"] == "call_case"
    assert wire[3]["arguments"] == '{"name":"A"}'
    assert wire[4]["output"] == "A 網站使用單次付款"

    next_turn = payloads[2]["input"]
    assert [item.get("encrypted_content") for item in next_turn if item["type"] == "reasoning"] == ["opaque-test-1", "opaque-test-2"]
    assert next_turn[-2]["phase"] == "final_answer"
    assert next_turn[-1]["content"] == "B 網站改採月租。"
    assert sum(item.get("content") == "B 網站改採月租。" for item in next_turn) == 1
    assert next_turn[0]["content"] == "我接案製作網站，請查看 A 案例。"


def test_server_compaction_trims_only_request_view_and_preserves_following_tool():
    payloads: list[dict] = []
    bodies = [
        response_body([
            {"type": "reasoning", "id": "rs_old", "summary": [], "encrypted_content": "opaque-before-cut"},
            {"type": "compaction", "id": "cmp_new", "encrypted_content": "opaque-compacted"},
            {"type": "reasoning", "id": "rs_new", "summary": [], "encrypted_content": "opaque-after-cut"},
            {"type": "function_call", "id": "fc_new", "call_id": "call_new", "name": "read_case", "arguments": '{"name":"A"}', "status": "completed"},
        ]),
        response_body([assistant_text("已讀到案例。")], "resp_done"),
    ]

    def respond(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json=bodies[len(payloads) - 1])

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = build_model(model="gpt-5.6-luna", api_key="offline-not-a-key", http_client=client)
        canonical = [HumanMessage("很久以前的完整問答仍然需要保留。")]
        canonical.append(model.invoke(canonical))
        canonical.append(ToolMessage("案例完整細節", tool_call_id="call_new"))
        serializer = JsonPlusSerializer()
        canonical = serializer.loads_typed(serializer.dumps_typed(canonical))
        before = deepcopy(canonical)
        view = server_compaction_view(canonical)
        model.invoke(view)

    wire = payloads[1]["input"]
    assert [item["type"] for item in wire] == ["compaction", "reasoning", "function_call", "function_call_output"]
    assert wire[0]["encrypted_content"] == "opaque-compacted"
    assert wire[1]["encrypted_content"] == "opaque-after-cut"
    assert wire[2]["call_id"] == wire[3]["call_id"] == "call_new"
    assert canonical == before
    assert canonical[0].content == "很久以前的完整問答仍然需要保留。"


def test_latest_compaction_drops_pre_cut_tool_metadata_not_the_new_call():
    canonical = [
        HumanMessage("原始訪談"),
        AIMessage(content=[{"type": "compaction", "id": "cmp_earlier", "encrypted_content": "earlier"}]),
        HumanMessage("新的訪談"),
        AIMessage(
            content=[
                {"type": "function_call", "id": "fc_old", "call_id": "call_old", "name": "read_case", "arguments": "{}"},
                {"type": "compaction", "id": "cmp_latest", "encrypted_content": "latest"},
                {"type": "function_call", "id": "fc_after", "call_id": "call_after", "name": "read_case", "arguments": "{}"},
            ],
            tool_calls=[
                {"name": "read_case", "args": {}, "id": "call_old", "type": "tool_call"},
                {"name": "read_case", "args": {}, "id": "call_after", "type": "tool_call"},
            ],
        ),
        ToolMessage("後續讀取內容", tool_call_id="call_after"),
    ]
    before = deepcopy(canonical)
    view = server_compaction_view(canonical)
    assert len(view) == 2
    assert view[0].content[0]["id"] == "cmp_latest"
    assert [call["id"] for call in view[0].tool_calls] == ["call_after"]
    assert view[1].tool_call_id == "call_after"
    assert canonical == before


def test_uncompacted_conversation_is_retained_without_aliasing_canonical():
    canonical = [HumanMessage("細節不應被改寫"), AIMessage(content="請繼續說明。")]
    before = deepcopy(canonical)
    view = server_compaction_view(canonical)
    assert view == before
    view[0].content = "僅改 request view"
    assert canonical == before


def test_compaction_threshold_is_sent_to_provider_when_configured():
    payloads: list[dict] = []
    body = response_body([assistant_text("繼續訪談")])

    def respond(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json=body)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        model = build_model(
            model="gpt-5.6-luna", api_key="offline-not-a-key", http_client=client,
            compact_threshold=32_000,
        )
        model.invoke([HumanMessage("這是測試訪談")])
    assert payloads[0].get("context_management") == [{"type": "compaction", "compact_threshold": 32_000}]


@pytest.mark.parametrize("threshold", [0, -1])
def test_invalid_compaction_threshold_is_rejected_without_http(threshold):
    with httpx.Client(transport=httpx.MockTransport(lambda request: pytest.fail("No HTTP expected"))) as client:
        with pytest.raises(ValueError, match="compact_threshold"):
            build_model(
                model="gpt-5.6-luna", api_key="offline-not-a-key", http_client=client,
                compact_threshold=threshold,
            )
