"""Agent 測試的合成 SSE、原生 SDK client 及普通材料 callable。"""

import json
from collections.abc import AsyncIterator, Mapping
from contextlib import aclosing, asynccontextmanager
from typing import Any, cast
from uuid import UUID, uuid4

import httpx2
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from openai import AsyncOpenAI
from openai.types.responses.response_create_params import ResponseCreateParamsBase
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.agent import Agent
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    openai_checkpoint_serializer,
)
from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin
from caliburn.modules.agent.state import AgentState, OpenAIItems

MODEL_REQUEST: ResponseCreateParamsBase = {
    "model": "offline-model",
    "max_output_tokens": 100,
    "reasoning": {"effort": "low"},
}
TEST_WORKSPACE_ID = UUID(int=2)
INITIAL: OpenAIItems = [{"role": "user", "content": "Synthetic input"}]


def message(
    phase: str | None = "final_answer", text: str = "Synthetic reply"
) -> dict[str, object]:
    return {
        "id": "msg_" + (phase or "legacy"),
        "type": "message",
        "role": "assistant",
        "status": "completed",
        "phase": phase,
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }


def call(
    name: str = "read_alpha",
    call_id: str = "call_alpha",
    arguments: str = '{"item":"alpha"}',
) -> dict[str, object]:
    return {
        "id": "fc_" + call_id,
        "type": "function_call",
        "call_id": call_id,
        "name": name,
        "arguments": arguments,
        "status": "completed",
        "future_call_field": {"retained": True},
    }


def reasoning() -> dict[str, object]:
    return {
        "id": "rs_offline",
        "type": "reasoning",
        "summary": [],
        "encrypted_content": "synthetic-opaque-content",
        "status": "completed",
    }


def response_payload(
    output: list[dict[str, object]] | None = None, *, status: str = "completed"
) -> dict[str, object]:
    return {
        "id": "resp_offline",
        "object": "response",
        "created_at": 1793491200.0,
        "model": "offline-model",
        "status": status,
        "error": {"code": "server_error", "message": "Synthetic failure"}
        if status == "failed"
        else None,
        "incomplete_details": {"reason": "max_output_tokens"}
        if status == "incomplete"
        else None,
        "instructions": "Synthetic instructions",
        "output": [message()] if output is None else output,
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "usage": {
            "input_tokens": 13,
            "input_tokens_details": {"cached_tokens": 3},
            "output_tokens": 8,
            "output_tokens_details": {"reasoning_tokens": 5},
            "total_tokens": 21,
        },
        "future_response_field": {"retained": True},
    }


def response_events(payload: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "type": "response.created",
            "sequence_number": 0,
            "response": {**payload, "status": "in_progress", "output": []},
        },
        {
            "type": "response." + str(payload["status"]),
            "sequence_number": 1,
            "response": payload,
        },
    ]


class EventStream(httpx2.AsyncByteStream):
    def __init__(self, events: list[dict[str, object]]):
        self.events = events
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for event in self.events:
            yield ("data: " + json.dumps(event) + "\n\n").encode()

    async def aclose(self) -> None:
        self.closed = True


def sse_response(stream: httpx2.AsyncByteStream) -> httpx2.Response:
    return httpx2.Response(
        200, headers={"content-type": "text/event-stream"}, stream=stream
    )


def offline_client(transport: httpx2.MockTransport) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key="offline-api-key",
        admin_api_key="offline-admin-key",
        organization="offline-organization",
        project="offline-project",
        webhook_secret="offline-webhook-secret",
        base_url="https://offline.invalid/v1",
        timeout=5,
        http_client=httpx2.AsyncClient(transport=transport, trust_env=False),
    )


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    return AgentBundle(cast(tuple[AgentPlugin, ...], config["plugins"]))


@asynccontextmanager
async def open_test_agent(
    *,
    client: AsyncOpenAI,
    tools: tuple[StructuredTool, ...] = (),
    plugins: tuple[AgentPlugin, ...] = (),
    max_model_steps: int = 64,
    max_tool_calls_per_step: int = 32,
    recursion_limit: int | None = None,
) -> AsyncIterator[Agent]:
    async with open_agent(
        agent_id="offline",
        resume_version="v1",
        client=client,
        model_settings=MODEL_REQUEST,
        bundles=[
            BundleConfig(
                __name__,
                {"plugins": (*plugins, AgentPlugin("test_tools", tools=tools))},
            )
        ],
        checkpointer=InMemorySaver(serde=openai_checkpoint_serializer()),
        max_model_steps=max_model_steps,
        max_tool_calls_per_step=max_tool_calls_per_step,
        recursion_limit=recursion_limit,
    ) as agent:
        yield agent


async def run_turn(
    agent: Agent,
    *,
    input: str | ResponseInputParam = "Synthetic input",
    workspace_id: UUID = TEST_WORKSPACE_ID,
) -> AgentState:
    async for _ in agent.astream(
        turn_id=uuid4(), workspace_id=workspace_id, input=input
    ):
        pass
    return cast(AgentState, (await agent.aget_state(workspace_id=workspace_id)).values)


async def run_test_agent(
    *,
    client: AsyncOpenAI,
    tools: tuple[StructuredTool, ...] = (),
    plugins: tuple[AgentPlugin, ...] = (),
    input: str | ResponseInputParam = "Synthetic input",
    max_model_steps: int = 64,
    max_tool_calls_per_step: int = 32,
    recursion_limit: int | None = None,
) -> AgentState:
    async with open_test_agent(
        client=client,
        tools=tools,
        plugins=plugins,
        max_model_steps=max_model_steps,
        max_tool_calls_per_step=max_tool_calls_per_step,
        recursion_limit=recursion_limit,
    ) as agent:
        return await run_turn(agent, input=input)


async def stream_test_agent(
    *,
    client: AsyncOpenAI,
    tools: tuple[StructuredTool, ...] = (),
    input: str | ResponseInputParam = "Synthetic input",
) -> AsyncIterator[dict[str, Any]]:
    async with open_test_agent(client=client, tools=tools) as agent:
        async with aclosing(
            agent.astream(turn_id=uuid4(), workspace_id=TEST_WORKSPACE_ID, input=input)
        ) as stream:
            async for event in stream:
                yield event


def request_body(request: httpx2.Request) -> dict[str, Any]:
    """HTTP JSON 是外部邊界；僅此測試解析點容許動態欄位。"""
    body = json.loads(request.content)
    assert isinstance(body, dict)
    return body
