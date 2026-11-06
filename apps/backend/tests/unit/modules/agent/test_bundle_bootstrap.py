"""由有序 Bundle 設定進入真 Graph 與 SDK 的離線驗收。"""

import asyncio
from collections.abc import Mapping
from copy import deepcopy
from typing import cast
from uuid import UUID

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from openai.types.responses.response_create_params import ResponseCreateParamsBase
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin
from caliburn.modules.agent.state import request_items
from tests.unit.modules.agent.bundle_fixtures.host_services import LABEL
from tests.unit.modules.agent.execution import complete_turn
from tests.unit.modules.agent.offline_openai import (
    INITIAL,
    MODEL_REQUEST,
    TEST_WORKSPACE_ID,
    EventStream,
    call,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)

PROMPTS = "tests.unit.modules.agent.bundle_fixtures.prompts"
CAPABILITY = "tests.unit.modules.agent.bundle_fixtures.capability"
TOOLS = "tests.unit.modules.agent.bundle_fixtures.tools"
EMPTY = "tests.unit.modules.agent.bundle_fixtures.empty"


@pytest.mark.parametrize("labels", [("North", "South"), ("South", "North")])
def test_bootstrap_loads_configured_bundles_and_preserves_all_declared_order(
    labels: tuple[str, str],
) -> None:
    """設定順序、Bundle 內插件及各插件的段落順序皆保留。"""
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=tuple(
                    BundleConfig(PROMPTS, {"label": label}) for label in labels
                ),
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
            ) as agent:
                result = await complete_turn(
                    agent,
                    workspace_id=TEST_WORKSPACE_ID,
                    input=cast(ResponseInputParam, INITIAL),
                )
            assert result["model_response"].output_text == "Synthetic reply"

    asyncio.run(run())
    first, second = labels
    assert (
        sent[0]["instructions"]
        == f"{first}: opening\n\n{first}: first detail\n\n{first}: second detail\n\n"
        f"{second}: opening\n\n{second}: first detail\n\n{second}: second detail"
    )
    assert sent[0]["input"] == INITIAL
    assert sent[0]["tools"] == []


@pytest.mark.parametrize(
    "selection, instructions",
    [
        (None, "North: opening\n\nNorth: first detail\n\nNorth: second detail"),
        ((), None),
        (("North-opening",), "North: opening"),
        (("North-details",), "North: first detail\n\nNorth: second detail"),
        (
            ("North-details", "North-opening"),
            "North: opening\n\nNorth: first detail\n\nNorth: second detail",
        ),
    ],
)
def test_bundle_plugin_selection_preserves_factory_order_in_model_request(
    selection: tuple[str, ...] | None, instructions: str | None
) -> None:
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="selected-prompts",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(BundleConfig(PROMPTS, {"label": "North"}, plugins=selection),),
                checkpointer=InMemorySaver(),
            ) as agent:
                await complete_turn(agent, workspace_id=UUID(int=1), input="question")

    asyncio.run(run())
    assert sent[0].get("instructions") == instructions
    assert sent[0]["tools"] == []


def test_unselected_capability_has_no_services_state_hooks_or_tools() -> None:
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="disabled-capability",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(
                    BundleConfig(
                        CAPABILITY,
                        {"label": "Alpha", "tool_name": "read_alpha"},
                        plugins=(),
                    ),
                ),
                checkpointer=InMemorySaver(),
            ) as agent:
                result = await complete_turn(
                    agent, workspace_id=UUID(int=1), input="question"
                )
                assert "capability_stamps" not in result

    asyncio.run(run())
    assert "instructions" not in sent[0]
    assert sent[0]["tools"] == []


@pytest.mark.parametrize(
    "selection, match",
    [
        (("missing",), "Unknown.*missing"),
        (("North-opening", "North-opening"), "Duplicate.*North-opening"),
    ],
)
def test_invalid_bundle_plugin_selection_fails_before_model_call(
    selection: tuple[str, ...], match: str
) -> None:
    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail("model called"))
        ) as client:
            with pytest.raises(ValueError, match=match):
                async with open_agent(
                    agent_id="invalid-selection",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=(
                        BundleConfig(PROMPTS, {"label": "North"}, plugins=selection),
                    ),
                    checkpointer=InMemorySaver(),
                ):
                    pytest.fail("invalid Agent opened")

    asyncio.run(run())


def test_preloaded_plugins_do_not_call_bundle_factory_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from caliburn.modules.agent.bootstrap import load_plugins
    from tests.unit.modules.agent.bundle_fixtures import prompts

    original = prompts.create_bundle
    calls = 0

    def counted(config: Mapping[str, object]) -> AgentBundle:
        nonlocal calls
        calls += 1
        return original(config)

    monkeypatch.setattr(prompts, "create_bundle", counted)
    plugins = load_plugins(
        (BundleConfig(PROMPTS, {"label": "North"}, plugins=("North-details",)),)
    )
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="preloaded",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(AgentBundle(plugins=plugins),),
                checkpointer=InMemorySaver(),
            ) as agent:
                await complete_turn(agent, workspace_id=UUID(int=1), input="question")

    asyncio.run(run())
    assert calls == 1
    assert sent[0]["instructions"] == "North: first detail\n\nNorth: second detail"


@pytest.mark.parametrize(
    "selection, expected",
    [
        ((), []),
        (("source",), ["source:enter", "source:exit"]),
        (
            None,
            [
                "source:enter",
                "consumer:shared:enter",
                "consumer:shared:exit",
                "source:exit",
            ],
        ),
    ],
)
def test_plugin_selection_opens_only_selected_services(
    selection: tuple[str, ...] | None, expected: list[str]
) -> None:
    from tests.unit.modules.agent.test_plugin_services import TRACE

    events: list[str] = []

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail("model called"))
        ) as client:
            async with open_agent(
                agent_id="selected-services",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(
                    BundleConfig(
                        "tests.unit.modules.agent.test_plugin_services",
                        {"name": "normal"},
                        plugins=selection,
                    ),
                ),
                external_services=(TRACE.bind(events),),
                checkpointer=InMemorySaver(),
            ):
                pass

    asyncio.run(run())
    assert events == expected


def test_plugin_selection_does_not_automatically_enable_missing_provider() -> None:
    from tests.unit.modules.agent.test_plugin_services import TRACE

    events: list[str] = []

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail("model called"))
        ) as client:
            with pytest.raises(ValueError, match="consumer.*missing service first"):
                async with open_agent(
                    agent_id="selected-consumer",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=(
                        BundleConfig(
                            "tests.unit.modules.agent.test_plugin_services",
                            {"name": "normal"},
                            plugins=("consumer",),
                        ),
                    ),
                    external_services=(TRACE.bind(events),),
                    checkpointer=InMemorySaver(),
                ):
                    pytest.fail("invalid Agent opened")

    asyncio.run(run())
    assert events == []


def test_existing_instructions_remain_the_first_section() -> None:
    """固定 instructions 與插件段落一起出站，不遺失原始政策。"""
    sent = []
    model_request: ResponseCreateParamsBase = {
        **MODEL_REQUEST,
        "instructions": "Base policy",
    }

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings=model_request,
                bundles=[BundleConfig(PROMPTS, {"label": "North"})],
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
            ) as agent:
                await complete_turn(
                    agent,
                    workspace_id=TEST_WORKSPACE_ID,
                    input=cast(ResponseInputParam, INITIAL),
                )

    asyncio.run(run())
    assert (
        sent[0]["instructions"] == "Base policy\n\nNorth: opening\n\n"
        "North: first detail\n\nNorth: second detail"
    )
    assert model_request["instructions"] == "Base policy"


def test_bootstrap_accepts_mixed_bundles_in_declared_plugin_order() -> None:
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                agent_id="mixed-bundles",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(
                    AgentBundle(
                        (
                            AgentPlugin("first", prompt_sections=("First",)),
                            AgentPlugin("second", prompt_sections=("Second",)),
                        )
                    ),
                    BundleConfig(PROMPTS, {"label": "Configured"}),
                    AgentBundle((AgentPlugin("last", prompt_sections=("Last",)),)),
                ),
                checkpointer=InMemorySaver(),
            ) as agent:
                result = await complete_turn(
                    agent, workspace_id=TEST_WORKSPACE_ID, input="mixed bundle input"
                )
                assert result["model_response"].output_text == "Synthetic reply"

    asyncio.run(run())
    assert sent[0]["instructions"] == (
        "First\n\nSecond\n\nConfigured: opening\n\nConfigured: first detail\n\n"
        "Configured: second detail\n\nLast"
    )
    assert sent[0]["input"] == [{"role": "user", "content": "mixed bundle input"}]


@pytest.mark.parametrize(
    "fixed_input", ["Source text", [{"role": "user", "content": "Source text"}]]
)
def test_nonempty_template_input_is_rejected_before_outbound_request(
    fixed_input: str | ResponseInputParam,
) -> None:
    """固定 input 不得被當步歷史靜默蓋掉。"""
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            with pytest.raises(ValueError, match="input"):
                async with open_agent(
                    client=client,
                    model_settings={
                        **MODEL_REQUEST,
                        "input": cast(ResponseInputParam, fixed_input),
                    },
                    bundles=[],
                    agent_id="test-agent",
                    resume_version="v1",
                    checkpointer=InMemorySaver(),
                ):
                    pass

    asyncio.run(run())
    assert sent == []


def test_capabilities_rebuild_after_complete_tool_roundtrip() -> None:
    """同份材料決定指引、宣告與執行；新步只接續一次工具歷史。"""
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = (
            [call(), call(name="read_beta", call_id="call_beta")]
            if len(sent) == 1
            else None
        )
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[
                    BundleConfig(
                        CAPABILITY, {"label": "Alpha", "tool_name": "read_alpha"}
                    ),
                    BundleConfig(
                        CAPABILITY, {"label": "Beta", "tool_name": "read_beta"}
                    ),
                ],
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
                external_services=(LABEL.bind("North"),),
            ) as agent:
                result = await complete_turn(
                    agent,
                    workspace_id=UUID(int=1),
                    input=cast(ResponseInputParam, INITIAL),
                )
            assert result["model_step"] == 2
            assert len(request_items(result["model_request"])) == 6

    asyncio.run(run())
    assert (
        sent[0]["instructions"]
        == "Use read_alpha for Alpha:North:1:1.\n\nUse read_beta for Beta:North:1:1."
    )
    assert [tool["name"] for tool in sent[0]["tools"]] == ["read_alpha", "read_beta"]
    assert [tool["description"] for tool in sent[0]["tools"]] == [
        "Read item.",
        "Read item.",
    ]
    assert (
        sent[1]["instructions"]
        == "Use read_alpha for Alpha:North:1:5.\n\nUse read_beta for Beta:North:1:5."
    )
    assert sent[1]["input"][0] == INITIAL[0]
    assert [item["type"] for item in sent[1]["input"][1:]] == [
        "function_call",
        "function_call",
        "function_call_output",
        "function_call_output",
    ]
    assert sent[1]["input"][-2:] == [
        {
            "type": "function_call_output",
            "call_id": "call_alpha",
            "output": "Alpha:North:1:1/alpha",
        },
        {
            "type": "function_call_output",
            "call_id": "call_beta",
            "output": "Beta:North:1:1/alpha",
        },
    ]


@pytest.mark.parametrize(
    "bundles, expected_tools",
    [([], []), ([BundleConfig(EMPTY)], []), ([BundleConfig(TOOLS)], ["echo"])],
)
def test_empty_bundles_and_tool_only_plugins_need_no_prompt(
    bundles: list[BundleConfig], expected_tools: list[str]
) -> None:
    """空清單、空 Bundle 及純工具插件都可直接完成裸模型請求。"""
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings={**MODEL_REQUEST, "input": cast(ResponseInputParam, [])},
                bundles=bundles,
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
            ) as agent:
                result = await complete_turn(
                    agent,
                    workspace_id=TEST_WORKSPACE_ID,
                    input=cast(ResponseInputParam, INITIAL),
                )
            assert result["model_step"] == 1

    asyncio.run(run())
    assert "instructions" not in sent[0]
    assert [tool["name"] for tool in sent[0]["tools"]] == expected_tools
    assert sent[0]["input"] == INITIAL


def test_removing_a_bundle_removes_its_prompt_and_tool_together() -> None:
    """清單移除能力時，該能力的指引與工具都不殘留。"""
    sent = []
    alpha = BundleConfig(CAPABILITY, {"label": "Alpha", "tool_name": "read_alpha"})
    beta = BundleConfig(CAPABILITY, {"label": "Beta", "tool_name": "read_beta"})

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            for bundles in ([alpha, beta], [beta], []):
                async with open_agent(
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=bundles,
                    agent_id="test-agent",
                    resume_version="v1",
                    checkpointer=InMemorySaver(),
                    external_services=(LABEL.bind("North"),),
                ) as agent:
                    await complete_turn(
                        agent,
                        workspace_id=UUID(int=1),
                        input=cast(ResponseInputParam, INITIAL),
                    )

    asyncio.run(run())
    assert [tool["name"] for tool in sent[0]["tools"]] == ["read_alpha", "read_beta"]
    assert sent[1]["instructions"] == "Use read_beta for Beta:North:1:1."
    assert [tool["name"] for tool in sent[1]["tools"]] == ["read_beta"]
    assert "instructions" not in sent[2] and sent[2]["tools"] == []


def test_built_graph_owns_model_and_bundle_configuration_snapshots() -> None:
    """呼叫者後續改動設定，不改已建 Graph 的模型參數與插件材料。"""
    sent = []
    model_request = deepcopy(MODEL_REQUEST)
    model_request["instructions"] = "Base policy"
    config: dict[str, object] = {"label": "Alpha", "tool_name": "read_alpha"}
    bundles = [BundleConfig(CAPABILITY, config)]

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with open_agent(
                client=client,
                model_settings=model_request,
                bundles=bundles,
                agent_id="test-agent",
                resume_version="v1",
                checkpointer=InMemorySaver(),
                external_services=(LABEL.bind("North"),),
            ) as agent:
                config["label"] = "Changed"
                bundles.clear()
                model_request["instructions"] = "Changed"
                reasoning = model_request["reasoning"]
                assert reasoning is not None
                reasoning["effort"] = "high"
                await complete_turn(
                    agent,
                    workspace_id=UUID(int=1),
                    input=cast(ResponseInputParam, INITIAL),
                )

    asyncio.run(run())
    assert (
        sent[0]["instructions"] == "Base policy\n\nUse read_alpha for Alpha:North:1:1."
    )
    assert sent[0]["tools"][0]["description"] == "Read item."
    assert sent[0]["reasoning"]["effort"] == "low"


@pytest.mark.parametrize(
    "module, error",
    [
        ("tests.unit.modules.agent.bundle_fixtures.missing", ModuleNotFoundError),
        ("tests.unit.modules.agent.bundle_fixtures", AttributeError),
    ],
)
def test_bundle_loading_errors_remain_native(
    module: str, error: type[Exception]
) -> None:
    """缺模組或缺約定入口須直接報錯，不假裝空 Bundle。"""

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail())
        ) as client:
            with pytest.raises(error):
                async with open_agent(
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=[BundleConfig(module)],
                    agent_id="test-agent",
                    resume_version="v1",
                    checkpointer=InMemorySaver(),
                ):
                    pass

    asyncio.run(run())


def test_duplicate_bundle_tools_are_rejected_before_outbound_request() -> None:
    """不同 Bundle 的同名工具仍由共同定稿在出站前拒絕。"""
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            with pytest.raises(ValueError, match="Duplicate tool name: echo"):
                async with open_agent(
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=[
                        BundleConfig(TOOLS),
                        BundleConfig(TOOLS, {"name": "second-tools"}),
                    ],
                    agent_id="test-agent",
                    resume_version="v1",
                    checkpointer=InMemorySaver(),
                ) as agent:
                    await complete_turn(
                        agent,
                        workspace_id=TEST_WORKSPACE_ID,
                        input=cast(ResponseInputParam, INITIAL),
                    )

    asyncio.run(run())
    assert sent == []


def test_interleaved_runs_keep_prompt_and_tool_closures_private() -> None:
    """兩輪先同時出站，再執行工具；閉包保留各自當步的資料。"""

    async def run() -> None:
        both_prepared = asyncio.Event()
        sent = []

        async def respond(request: httpx2.Request) -> httpx2.Response:
            body = request_body(request)
            sent.append(body)
            if len(body["input"]) == 1:
                if len(sent) == 2:
                    both_prepared.set()
                await asyncio.wait_for(both_prepared.wait(), timeout=5)
                output = [call()]
            else:
                output = None
            return sse_response(EventStream(response_events(response_payload(output))))

        async with offline_client(httpx2.MockTransport(respond)) as client:

            async def invoke(*, workspace_id: UUID, label: str) -> None:
                async with open_agent(
                    agent_id=label,
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=[
                        BundleConfig(
                            CAPABILITY, {"label": "Lookup", "tool_name": "read_alpha"}
                        )
                    ],
                    external_services=(LABEL.bind(label),),
                    checkpointer=InMemorySaver(),
                ) as agent:
                    result = await complete_turn(
                        agent,
                        workspace_id=workspace_id,
                        input=cast(ResponseInputParam, INITIAL),
                    )
                    assert result["model_step"] == 2

            await asyncio.gather(
                invoke(workspace_id=UUID(int=10), label="Left"),
                invoke(workspace_id=UUID(int=11), label="Right"),
            )
        subsequent = [body for body in sent if len(body["input"]) == 3]
        assert len(subsequent) == 2
        assert {
            (body["instructions"], body["input"][-1]["output"]) for body in subsequent
        } == {
            ("Use read_alpha for Lookup:Left:10:3.", "Lookup:Left:10:1/alpha"),
            ("Use read_alpha for Lookup:Right:11:3.", "Lookup:Right:11:1/alpha"),
        }
        assert INITIAL == [{"role": "user", "content": "Synthetic input"}]

    asyncio.run(run())
