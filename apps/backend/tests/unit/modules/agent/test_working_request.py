"""唯一工作 request 的公開接縫驗收。"""

import asyncio
from collections.abc import Mapping
from typing import cast

import httpx2
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.state import AgentState, request_items
from tests.unit.modules.agent.execution import complete_turn
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    TEST_WORKSPACE_ID,
    EventStream,
    message,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def create_bundle(config: Mapping[str, object]) -> AgentBundle:

    async def inject(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> AgentState:
        items = request_items(state["model_request"])
        if len(items) != 1:
            return {}
        return {
            "model_request": {
                **state["model_request"],
                "input": cast(
                    ResponseInputParam,
                    [{"role": "developer", "content": "memory"}, *items],
                ),
            }
        }

    return AgentBundle(
        (AgentPlugin("memory", before_model_step=(PluginStep("inject", inject),)),)
    )


def test_plugin_context_survives_the_next_model_step_in_the_working_request() -> None:
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = [message("commentary")] if len(sent) == 1 else None
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__)],
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
            ) as agent:
                await complete_turn(
                    agent,
                    workspace_id=TEST_WORKSPACE_ID,
                    input=cast(
                        ResponseInputParam, [{"role": "user", "content": "question"}]
                    ),
                )

    asyncio.run(run())
    assert sent[0]["input"][0] == {"role": "developer", "content": "memory"}
    assert sent[1]["input"][0] == sent[0]["input"][0]
