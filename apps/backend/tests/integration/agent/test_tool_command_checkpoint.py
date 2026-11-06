"""原生 ToolRuntime／Command 的同批 State 推進與逐工具保存。"""

import asyncio
from uuid import UUID

import httpx2
import pytest

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from tests.integration.agent.command_fixture import COMMAND_PROBE, CommandProbe
from tests.integration.agent.stream_support import consume
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    call,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def test_tool_only_plugin_commands_resume_saved_reducer_and_same_batch_aliases(
    checkpoint_conninfo: str,
) -> None:
    """會抓到額外 State 被裁掉、同批看舊值或 reducer 被套用兩次。"""
    workspace = UUID(int=7)
    first, resumed = CommandProbe(), CommandProbe()
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = (
            [
                call("advance", call_id="first", arguments='{"label":"alpha"}'),
                call("advance", call_id="second", arguments='{"label":"beta"}'),
            ]
            if len(sent) == 1
            else None
        )
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        for fail, probe in ((True, first), (False, resumed)):
            async with (
                open_postgres_checkpointer(
                    checkpoint_conninfo, initialize=fail
                ) as saver,
                offline_client(httpx2.MockTransport(respond)) as client,
                open_agent(
                    agent_id="command-progress",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=(
                        BundleConfig(
                            "tests.integration.agent.command_fixture", {"fail": fail}
                        ),
                    ),
                    checkpointer=saver,
                    external_services=(COMMAND_PROBE.bind(probe),),
                ) as agent,
            ):
                if fail:
                    with pytest.raises(RuntimeError, match="synthetic command outage"):
                        await consume(
                            agent.astream(
                                turn_id=UUID(int=101),
                                workspace_id=workspace,
                                input="run",
                            )
                        )
                    saved = await agent.aget_state(workspace_id=workspace)
                    assert saved.next
                    assert saved.values["journal"] == ["alpha"]
                    assert saved.values["aliases"] == {"k1": "alpha"}
                else:
                    before = await agent.aget_state(workspace_id=workspace)
                    assert before.values["journal"] == ["alpha"]
                    await consume(
                        agent.aresume(turn_id=UUID(int=101), workspace_id=workspace)
                    )
                    saved = await agent.aget_state(workspace_id=workspace)
                    assert not saved.next
                    assert saved.values["journal"] == ["alpha", "beta"]
                    assert saved.values["aliases"] == {"k1": "beta"}
                    assert (
                        saved.values["model_response"].output_text == "Synthetic reply"
                    )
                assert "messages" not in saved.values
                assert saved.values["workspace_id"] == workspace

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert first.observed == [
        (workspace, "alpha", [], None),
        (workspace, "beta", ["alpha"], "alpha"),
    ]
    assert resumed.observed == [(workspace, "beta", ["alpha"], "alpha")]
    assert len(sent) == 2
    assert sent[0]["tools"][0]["parameters"]["properties"] == {
        "label": {"type": "string"}
    }
    assert [
        item["output"]
        for item in sent[1]["input"]
        if item.get("type") == "function_call_output"
    ] == ["alpha after none", "beta after alpha"]
