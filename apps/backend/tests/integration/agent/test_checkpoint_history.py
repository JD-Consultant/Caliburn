"""公開入口分配 thread 後，原生查讀／刪除維持彼此隔離。"""

import asyncio
from uuid import UUID

import httpx2
import pytest
from langchain_core.runnables import RunnableConfig

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from tests.integration.agent.stream_support import consume
from tests.integration.agent.tool_fixture import PROBE, ToolProbe
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


def test_read_history_does_not_execute_and_delete_only_removes_selected_thread(
    checkpoint_conninfo: str,
) -> None:
    async def run() -> None:
        sent = []
        probe = ToolProbe(fail_before_effect=True)

        def respond(request: httpx2.Request) -> httpx2.Response:
            sent.append(request_body(request))
            payload = response_payload([call()] if len(sent) <= 2 else None)
            payload["id"] = f"resp_{len(sent)}"
            return sse_response(EventStream(response_events(payload)))

        async with (
            open_postgres_checkpointer(checkpoint_conninfo, initialize=True) as saver,
            offline_client(httpx2.MockTransport(respond)) as client,
            open_agent(
                agent_id="workspace-history",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(BundleConfig("tests.integration.agent.tool_fixture"),),
                external_services=(PROBE.bind(probe),),
                checkpointer=saver,
            ) as agent,
        ):
            for number in (1, 2):
                with pytest.raises(RuntimeError, match="synthetic tool outage"):
                    await consume(
                        agent.astream(
                            turn_id=UUID(int=101),
                            workspace_id=UUID(int=number),
                            input=f"workspace {number}",
                        )
                    )
        assert len(sent) == 2 and probe.effects == []
        probe.fail_before_effect = False
        async with (
            open_postgres_checkpointer(checkpoint_conninfo) as saver,
            offline_client(httpx2.MockTransport(respond)) as client,
            open_agent(
                agent_id="workspace-history",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(BundleConfig("tests.integration.agent.tool_fixture"),),
                external_services=(PROBE.bind(probe),),
                checkpointer=saver,
            ) as agent,
        ):
            for number in (1, 2):
                workspace = UUID(int=number)
                snapshot = await agent.aget_state(workspace_id=workspace)
                history = [
                    item
                    async for item in agent.aget_state_history(workspace_id=workspace)
                ]
                assert (
                    snapshot.values["model_request"]["input"][0]["content"]
                    == f"workspace {number}"
                )
                assert snapshot.values["workspace_id"] == workspace
                before_model = [
                    item for item in history if item.next == ("call_model",)
                ]
                assert before_model[0].values["model_request"]["input"] == [
                    {"role": "user", "content": f"workspace {number}"}
                ]
                assert {
                    item.values["model_response"].id
                    for item in history
                    if item.values.get("model_response") is not None
                } == {f"resp_{number}"}
                historical = await agent.aget_state(
                    workspace_id=workspace,
                    checkpoint_id=before_model[0].config["configurable"][
                        "checkpoint_id"
                    ],
                )
                assert historical.values == before_model[0].values
                assert (
                    await agent.aget_state(workspace_id=workspace)
                ).config == snapshot.config
                assert [
                    item.config
                    async for item in agent.aget_state_history(
                        workspace_id=workspace, limit=1
                    )
                ] == [history[0].config]
            assert len(sent) == 2 and probe.effects == []
            first = await agent.aget_state(workspace_id=UUID(int=1))
            first_thread = first.config["configurable"]["thread_id"]
            first_config: RunnableConfig = {"configurable": {"thread_id": first_thread}}
            await saver.adelete_thread(first_thread)
            await saver.adelete_thread(first_thread)
            assert [item async for item in saver.alist(first_config)] == []
            assert (await agent.aget_state(workspace_id=UUID(int=1))).values == {}
            assert [
                item
                async for item in agent.aget_state_history(workspace_id=UUID(int=1))
            ] == []
            assert (await agent.aget_state(workspace_id=UUID(int=2))).next
            await consume(
                agent.aresume(turn_id=UUID(int=101), workspace_id=UUID(int=2))
            )
            assert len(sent) == 3 and probe.effects == ["alpha"]

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
