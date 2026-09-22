"""Offline contract gate for the consultant's native compaction transport.

These checks replace only the HTTP boundary.  They prove what the installed
clients serialize, parse and preserve through LangGraph; they do not claim an
OpenRouter server or model actually implements OpenAI Responses compaction.
"""

import asyncio
import inspect
import json

import httpx
import pytest
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from openrouter.components.compactionitem import CompactionItem
from openrouter.responses import Responses
from pydantic import TypeAdapter, ValidationError

from jd_relational.consolidation_app import build_consolidation_model
from jd_relational.consultant_model import (
    CONSULTANT_MODEL,
    OPENROUTER_BASE_URL,
    OPENROUTER_HEADERS,
    OPENROUTER_PROVIDER,
    create_consultant_model,
)
from jd_relational.response_context import native_context_view
from support.openai_replies import body
from support.openrouter_replies import reply


def assistant_text(text: str, identity: str, phase: str = "final_answer") -> dict:
    return {
        "type": "message",
        "id": identity,
        "role": "assistant",
        "status": "completed",
        "phase": phase,
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }


@pytest.mark.parametrize("target", ["official-openai", "openrouter-responses-candidate"])
def test_responses_clients_round_trip_inline_compaction_and_tools(target):
    """The completed Responses contract is the positive reference exam.

    This mirrors the consultant's previously verified request-only view: real
    ChatOpenAI request/response conversion and the real LangGraph Saver run;
    only the remote provider is synthetic.
    """
    saver = InMemorySaver()
    config = {"configurable": {"thread_id": "compaction-positive-reference"}}
    payloads: list[dict] = []
    tool_reads: list[str] = []
    replies = [
        body(
            [
                {
                    "type": "reasoning",
                    "id": "rs_before_tool",
                    "summary": [],
                    "encrypted_content": "opaque-reasoning-before",
                },
                assistant_text("先讀案例。", "msg_commentary", "commentary"),
                {
                    "type": "function_call",
                    "id": "fc_case",
                    "call_id": "call_case",
                    "name": "read_case",
                    "arguments": '{"name":"A"}',
                    "status": "completed",
                },
            ],
            identity="tool",
        ),
        body(
            [
                {
                    "type": "compaction",
                    "id": "cmp_reference",
                    "encrypted_content": "opaque-compaction-reference",
                },
                {
                    "type": "reasoning",
                    "id": "rs_after_compaction",
                    "summary": [],
                    "encrypted_content": "opaque-reasoning-after",
                },
                assistant_text("A 是單次付款。", "msg_first_answer"),
            ],
            identity="compacted",
        ),
        body([assistant_text("接著談 B。", "msg_second_answer")], identity="next"),
    ]

    @tool
    def read_case(name: str) -> str:
        """Read one synthetic saved case for this offline contract test."""
        tool_reads.append(name)
        return "A 使用單次付款"

    def receive(request: httpx.Request) -> httpx.Response:
        expected_path = (
            "/api/v1/responses"
            if target == "openrouter-responses-candidate"
            else "/v1/responses"
        )
        assert request.url.path == expected_path
        if target == "openrouter-responses-candidate":
            assert request.headers["X-OpenRouter-Metadata"] == "enabled"
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json=replies[len(payloads) - 1], request=request)

    headers = OPENROUTER_HEADERS if target == "openrouter-responses-candidate" else None
    with httpx.Client(
        transport=httpx.MockTransport(receive),
        trust_env=False,
        headers=headers,
    ) as client:
        if target == "openrouter-responses-candidate":
            model = ChatOpenAI(
                model=CONSULTANT_MODEL,
                api_key="synthetic-not-a-key",
                base_url=OPENROUTER_BASE_URL,
                http_client=client,
                timeout=client.timeout,
                max_retries=0,
                use_responses_api=True,
                output_version="responses/v1",
                store=False,
                truncation="disabled",
                reasoning={"effort": "high", "context": "all_turns"},
                model_kwargs={"parallel_tool_calls": False},
                context_management=[{
                    "type": "compaction",
                    "compact_threshold": 12000,
                }],
                extra_body={
                    "provider": {
                        "only": [OPENROUTER_PROVIDER],
                        "order": [OPENROUTER_PROVIDER],
                        "allow_fallbacks": False,
                        "require_parameters": False,
                    },
                },
            )
            assert model.max_retries == 0
        else:
            model = build_consolidation_model(
                model="gpt-5.6-luna",
                api_key="synthetic-not-a-key",
                http_client=client,
            ).model_copy(update={"max_retries": 0})

        def graph():
            return create_agent(
                model=model,
                tools=[read_case],
                system_prompt="固定顧問規則",
                middleware=[native_context_view],
                checkpointer=saver,
            )

        agent = graph()
        agent.invoke(
            {"messages": [HumanMessage("A 是一次付費的網站。", id="employee-a")]},
            config,
            durability="sync",
        )
        # Rebuild the graph on the same Saver so the second turn exercises a
        # persisted checkpoint read, not a hand-built in-memory message list.
        agent = graph()
        agent.invoke(
            {"messages": [HumanMessage("B 是月租。", id="employee-b")]},
            config,
            durability="sync",
        )
        canonical = agent.get_state(config).values["messages"]

    assert tool_reads == ["A"]
    assert len(payloads) == 3
    assert all(payload["context_management"] == [
        {"type": "compaction", "compact_threshold": 12000}
    ] for payload in payloads)
    assert all(payload["store"] is False for payload in payloads)
    if target == "openrouter-responses-candidate":
        assert all(payload["model"] == CONSULTANT_MODEL for payload in payloads)
        assert all(payload["provider"] == {
            "only": [OPENROUTER_PROVIDER],
            "order": [OPENROUTER_PROVIDER],
            "allow_fallbacks": False,
            "require_parameters": False,
        } for payload in payloads)
    else:
        assert all("provider" not in payload for payload in payloads)

    tool_wire = payloads[1]["input"]
    paired = [(item["type"], item["call_id"])
              for item in tool_wire if "call_id" in item]
    assert paired == [
        ("function_call", "call_case"),
        ("function_call_output", "call_case"),
    ]
    assert next(item for item in tool_wire if item.get("id") == "rs_before_tool")[
        "encrypted_content"
    ] == "opaque-reasoning-before"

    next_wire = payloads[2]["input"]
    assert next_wire[0]["role"] == "system"
    assert [item["type"] for item in next_wire[1:]] == [
        "compaction",
        "reasoning",
        "message",
        "message",
    ]
    assert next_wire[1]["encrypted_content"] == "opaque-compaction-reference"
    assert next_wire[2]["encrypted_content"] == "opaque-reasoning-after"
    assert next_wire[-1]["content"] == "B 是月租。"

    assert [message.content for message in canonical if isinstance(message, HumanMessage)] == [
        "A 是一次付費的網站。",
        "B 是月租。",
    ]
    assert [message.content for message in canonical if isinstance(message, ToolMessage)] == [
        "A 使用單次付款"
    ]
    assert any(
        isinstance(message, AIMessage)
        and isinstance(message.content, list)
        and any(isinstance(item, dict) and item.get("type") == "compaction"
                for item in message.content)
        for message in canonical
    ), "the Saver's canonical history must retain the provider item"


def test_current_chat_openrouter_drops_only_the_responses_compaction_block():
    """Characterize the exact current adapter gap with a valid chat reply."""
    payloads: list[dict] = []

    def receive(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json=reply("chat-gap"), request=request)

    transport = httpx.MockTransport(receive)
    sync_client = httpx.Client(
        transport=transport,
        trust_env=False,
        headers=OPENROUTER_HEADERS,
    )
    async_client = httpx.AsyncClient(
        transport=transport,
        trust_env=False,
        headers=OPENROUTER_HEADERS,
    )
    try:
        model = create_consultant_model(
            api_key="synthetic-not-a-key",
            http_client=sync_client,
            async_http_client=async_client,
        )
        assert model.streaming is False, "the formal A path is currently non-streaming"
        previous = AIMessage(
            content=[
                {"type": "text", "text": "可由 Chat Completions 表示的文字"},
                {
                    "type": "compaction",
                    "id": "cmp_not_chat",
                    "encrypted_content": "opaque-compaction-lost",
                },
            ],
            tool_calls=[{
                "name": "jd_read",
                "args": {"view": "current"},
                "id": "call_still_supported",
                "type": "tool_call",
            }],
            additional_kwargs={
                "reasoning_content": "可由目前 adapter 另外保留的 reasoning",
                "reasoning_details": [{
                    "type": "reasoning.encrypted",
                    "data": "opaque-reasoning-supported",
                }],
            },
        )
        model.invoke([
            HumanMessage("較早的使用者內容"),
            previous,
            ToolMessage("工具結果", tool_call_id="call_still_supported"),
            HumanMessage("下一輪內容"),
        ])
    finally:
        sync_client.close()
        asyncio.run(async_client.aclose())

    assert len(payloads) == 1
    assert payloads[0]["model"] == CONSULTANT_MODEL
    assistant = payloads[0]["messages"][1]
    assert assistant["content"] == [
        {"type": "text", "text": "可由 Chat Completions 表示的文字"}
    ]
    assert assistant["tool_calls"][0]["id"] == "call_still_supported"
    assert assistant["reasoning"] == "可由目前 adapter 另外保留的 reasoning"
    assert assistant["reasoning_details"][0]["data"] == "opaque-reasoning-supported"
    assert payloads[0]["messages"][2] == {
        "role": "tool",
        "content": "工具結果",
        "tool_call_id": "call_still_supported",
    }
    assert "opaque-compaction-lost" not in json.dumps(payloads[0], ensure_ascii=False)


def test_locked_openrouter_responses_schema_is_not_a_complete_compaction_candidate():
    """Record the installed SDK seam without inferring service capability."""
    parameters = inspect.signature(Responses.send).parameters
    assert "context_management" not in parameters
    assert not hasattr(Responses, "compact")

    # The locked SDK can describe a compaction item as Responses input.
    item = CompactionItem.model_validate({
        "type": "compaction",
        "id": "cmp_input_only",
        "encrypted_content": "opaque-input",
    })
    assert item.encrypted_content == "opaque-input"

    # Its Responses output union has no compaction discriminator, so the same
    # item cannot complete the receive -> save -> resend contract.
    from openrouter.components.outputitems import OutputItems

    with pytest.raises(ValidationError):
        TypeAdapter(OutputItems).validate_python(item.model_dump(mode="json"))
