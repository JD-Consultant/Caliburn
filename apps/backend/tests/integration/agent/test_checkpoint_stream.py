"""真 PostgreSQL：同步保存的非輸入 checkpoint 事件可直接公開查回。"""

import asyncio
from collections.abc import Mapping
from uuid import UUID

import httpx2
from langgraph.runtime import Runtime

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from caliburn.modules.agent.plugins.contracts import (
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.state import AgentState
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    offline_client,
    response_events,
    response_payload,
    sse_response,
)


def test_applied_checkpoint_is_readable_before_blocked_start_hook_finishes(
    checkpoint_conninfo: str,
) -> None:
    async def run() -> None:
        entered = asyncio.Event()
        release = asyncio.Event()
        turn_id = UUID(int=11)
        workspace_id = UUID(int=1)
        fingerprint = "synthetic-fingerprint"
        confirmed: list[str] = []

        async def wait_at_start(
            state: AgentState, *, runtime: Runtime[AgentContext]
        ) -> Mapping[str, object]:
            entered.set()
            await release.wait()
            return {}

        plugin = AgentPlugin(
            "blocked", on_turn_start=(PluginStep("wait", wait_at_start),)
        )
        async with (
            open_postgres_checkpointer(checkpoint_conninfo, initialize=True) as saver,
            offline_client(
                httpx2.MockTransport(
                    lambda _: sse_response(
                        EventStream(response_events(response_payload()))
                    )
                )
            ) as client,
            open_agent(
                agent_id="checkpoint-barrier",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(
                    BundleConfig(
                        "tests.unit.modules.agent.offline_openai",
                        {"plugins": (plugin,)},
                    ),
                ),
                checkpointer=saver,
            ) as agent,
        ):

            async def consume() -> None:
                async for part in agent.astream(
                    workspace_id=workspace_id,
                    turn_id=turn_id,
                    input="synthetic input",
                    input_fingerprint=fingerprint,
                    include_checkpoints=True,
                ):
                    if part["type"] != "checkpoints":
                        continue
                    checkpoint = part["data"]
                    if (
                        checkpoint["metadata"].get("source") == "input"
                        or checkpoint["values"].get("turn_id") != turn_id
                    ):
                        continue
                    checkpoint_id = checkpoint["config"]["configurable"][
                        "checkpoint_id"
                    ]
                    saved = await agent.aget_state(
                        workspace_id=workspace_id, checkpoint_id=checkpoint_id
                    )
                    assert saved.metadata
                    assert saved.metadata.get("turn_id") == str(turn_id)
                    assert saved.metadata.get("input_fingerprint") == fingerprint
                    assert saved.values["turn_input"] == "synthetic input"
                    confirmed.append(checkpoint_id)

            invocation = asyncio.create_task(consume())
            try:
                await asyncio.wait_for(entered.wait(), timeout=5)
                assert confirmed
                assert not invocation.done()
            finally:
                release.set()
                await invocation

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
