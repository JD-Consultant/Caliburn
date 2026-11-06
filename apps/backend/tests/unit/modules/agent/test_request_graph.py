"""有序 hook/subgraph/hook、私有 State 與跨模型步 channel。"""

import asyncio
import operator
from collections.abc import Mapping
from typing import Annotated, TypedDict, cast
from uuid import uuid4

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginHook,
    PluginStep,
)
from caliburn.modules.agent.state import AgentState, request_items
from tests.unit.modules.agent.bundle_fixtures.memory_materials import static_tool
from tests.unit.modules.agent.bundle_fixtures.summary_graph import (
    GRAPH_TRACE,
    summary_plugin,
)
from tests.unit.modules.agent.execution import complete_turn
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    TEST_WORKSPACE_ID,
    EventStream,
    call,
    message,
    offline_client,
    reasoning,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


class MemoryFields(TypedDict, total=False):
    memory_label: str
    visits: int
    ledger: Annotated[list[str], operator.add]


class MemoryState(AgentState, MemoryFields):
    pass


def create_bundle(config: Mapping[str, object]) -> AgentBundle:

    async def before(
        state: MemoryState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        runtime.context.services.require(GRAPH_TRACE).append("before")
        request = state["model_request"]
        items = [
            item
            for item in request_items(request)
            if not (isinstance(item, dict) and item.get("role") == "developer")
        ]
        visit = state.get("visits", 0) + 1
        return {
            "visits": visit,
            "memory_label": f"map:{visit}",
            "ledger": [f"visit:{visit}"],
            "model_request": {
                **request,
                "input": cast(
                    ResponseInputParam,
                    [{"role": "developer", "content": f"memory:{visit}"}, *items],
                ),
            },
        }

    def around(next_hook: PluginHook[MemoryState]) -> PluginHook[MemoryState]:

        async def call(
            state: MemoryState, *, runtime: Runtime[AgentContext]
        ) -> Mapping[str, object]:
            runtime.context.services.require(GRAPH_TRACE).append("around:before")
            update = await next_hook(state, runtime=runtime)
            runtime.context.services.require(GRAPH_TRACE).append("around:after")
            return update

        return call

    async def after(
        state: MemoryState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        runtime.context.services.require(GRAPH_TRACE).append("after")
        request = state["model_request"]
        items = [
            item
            for item in request_items(request)
            if not (isinstance(item, dict) and item.get("role") == "developer")
        ]
        return {
            "model_request": {
                **request,
                "input": cast(
                    ResponseInputParam,
                    [
                        {"role": "developer", "content": f"memory:{state['visits']}"},
                        *items,
                    ],
                ),
            }
        }

    steps = [PluginStep("before", before, input_schema=MemoryState, wrappers=(around,))]
    if config.get("summary", True):
        steps.append(
            PluginStep(
                "summary",
                summary_plugin(from_model_step=2 if config.get("tools") else 1)
                .before_model_step[0]
                .node,
            )
        )
    steps.append(PluginStep("after", after, input_schema=MemoryState))
    return AgentBundle(
        (
            AgentPlugin(
                "workflow",
                prompt_sections=("Fixed A", "Fixed B"),
                tools=(static_tool(),) if config.get("tools") else (),
                required_services=(GRAPH_TRACE,),
                state_schema=MemoryFields,
                before_model_step=tuple(steps),
            ),
        )
    )


@pytest.mark.parametrize(
    "summary, text, branch",
    [
        (True, "old prefix", "adopt"),
        (True, "keep", "keep"),
        (False, "old prefix", None),
    ],
)
def test_ordered_hooks_native_conditional_subgraph_and_cross_step_state(
    summary: bool, text: str, branch: str | None
) -> None:
    sent = []
    trace: list[str] = []
    initial = [{"role": "user", "content": text}]

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(
            EventStream(
                response_events(
                    response_payload(
                        [message("commentary")] if len(sent) == 1 else None
                    )
                )
            )
        )

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"summary": summary})],
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
                external_services=(GRAPH_TRACE.bind(trace),),
            ) as agent:
                states = [
                    event["data"]
                    async for event in agent.astream(
                        turn_id=uuid4(),
                        workspace_id=TEST_WORKSPACE_ID,
                        input=cast(ResponseInputParam, initial),
                    )
                    if event["type"] == "values"
                ]
                assert all(
                    set(state) <= {"turn_id", "model_response"} for state in states
                )
                final = cast(
                    MemoryState,
                    (await agent.aget_state(workspace_id=TEST_WORKSPACE_ID)).values,
                )
        assert final["visits"] == 2
        assert final["ledger"] == ["visit:1", "visit:2"]
        assert "summary" not in final
        assert "model_history" not in final and "result" not in final

    asyncio.run(run())
    assert initial == [{"role": "user", "content": text}]
    assert [body["instructions"] for body in sent] == ["Fixed A\n\nFixed B"] * 2
    for visit, body in enumerate(sent, 1):
        assert body["input"][0] == {"role": "developer", "content": f"memory:{visit}"}
        assert (
            len([item for item in body["input"] if item.get("role") == "developer"])
            == 1
        )
        assert body["input"][1]["content"] == (
            f"Summary for workspace {TEST_WORKSPACE_ID.int}"
            if branch == "adopt"
            else text
        )
    expected = ["around:before", "before", "around:after"]
    assert trace[: len(expected)] == expected
    if summary:
        assert trace == [
            *expected,
            "inspect",
            branch,
            "after",
            *expected,
            "inspect",
            "keep",
            "after",
        ]
    else:
        assert trace == [*expected, "after"] * 2


def test_compaction_preserves_encrypted_reasoning_and_complete_tool_pair() -> None:
    sent = []
    trace: list[str] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = [reasoning(), call()] if len(sent) == 1 else None
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"tools": True})],
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
                external_services=(GRAPH_TRACE.bind(trace),),
            ) as agent:
                result = await complete_turn(
                    agent,
                    workspace_id=TEST_WORKSPACE_ID,
                    input=[{"role": "user", "content": "old prefix"}],
                )
                assert result["model_response"].output_text == "Synthetic reply"

    asyncio.run(run())
    assert len(sent) == 2
    assert [item.get("type", item.get("role")) for item in sent[1]["input"]] == [
        "developer",
        "user",
        "reasoning",
        "function_call",
        "function_call_output",
    ]
    assert sent[1]["input"][0]["content"] == "memory:2"
    assert (
        sent[1]["input"][1]["content"]
        == f"Summary for workspace {TEST_WORKSPACE_ID.int}"
    )
    assert sent[1]["input"][2]["encrypted_content"] == "synthetic-opaque-content"
    assert (
        sent[1]["input"][3]["call_id"] == sent[1]["input"][4]["call_id"] == "call_alpha"
    )
    assert sent[1]["input"][3]["future_call_field"] == {"retained": True}
    assert "parsed_arguments" not in sent[1]["input"][3]
    assert sent[1]["input"][4]["output"] == "map:1/alpha"
    assert sent[0]["input"][1]["content"] == "old prefix"
    assert trace == [
        "around:before",
        "before",
        "around:after",
        "inspect",
        "keep",
        "after",
        "around:before",
        "before",
        "around:after",
        "inspect",
        "adopt",
        "after",
    ]
