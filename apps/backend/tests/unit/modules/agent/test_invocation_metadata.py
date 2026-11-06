"""公開入口保留受理識別，按輪查讀原生保存證據。"""

import asyncio
from collections.abc import Mapping
from uuid import UUID

import httpx2
import pytest
from langgraph.runtime import Runtime

from caliburn.modules.agent.plugins.contracts import (
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.state import AgentState
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    offline_client,
    open_test_agent,
    response_events,
    response_payload,
    sse_response,
)

WORKSPACE = UUID(int=1)
TURN = UUID(int=11)
FINGERPRINT = "14e0ffdc8215c81da0cde40f581237ee35177ddac4f1fc7613cad3004798d25f"


def test_new_turn_preserves_fingerprint_in_every_saved_checkpoint() -> None:
    async def run() -> None:
        async with (
            offline_client(
                httpx2.MockTransport(
                    lambda _: sse_response(
                        EventStream(response_events(response_payload()))
                    )
                )
            ) as client,
            open_test_agent(client=client) as agent,
        ):
            async for _ in agent.astream(
                workspace_id=WORKSPACE,
                turn_id=TURN,
                input="original",
                input_fingerprint=FINGERPRINT,
            ):
                pass
            history = [
                item async for item in agent.aget_state_history(workspace_id=WORKSPACE)
            ]
            assert history
            assert all(
                item.metadata
                and item.metadata.get("turn_id") == str(TURN)
                and item.metadata.get("input_fingerprint") == FINGERPRINT
                for item in history
            )

    asyncio.run(run())


def test_failure_resume_retains_original_fingerprint_without_resending_input() -> None:
    attempts = 0

    async def prepare(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("synthetic preparation failure")
        return {}

    plugin = AgentPlugin(
        "prepare", before_model_step=(PluginStep("fail_once", prepare),)
    )

    async def run() -> None:
        async with (
            offline_client(
                httpx2.MockTransport(
                    lambda _: sse_response(
                        EventStream(response_events(response_payload()))
                    )
                )
            ) as client,
            open_test_agent(client=client, plugins=(plugin,)) as agent,
        ):
            with pytest.raises(RuntimeError, match="preparation failure"):
                async for _ in agent.astream(
                    workspace_id=WORKSPACE,
                    turn_id=TURN,
                    input="original",
                    input_fingerprint=FINGERPRINT,
                ):
                    pass
            resumed = [
                part
                async for part in agent.aresume(
                    workspace_id=WORKSPACE, turn_id=TURN, include_checkpoints=True
                )
            ]
            assert any(part["type"] == "checkpoints" for part in resumed)
            saved = await agent.aget_state(workspace_id=WORKSPACE)
            assert saved.values["turn_input"] == "original"
            assert saved.metadata
            assert saved.metadata.get("input_fingerprint") == FINGERPRINT

    asyncio.run(run())


def test_turn_history_filter_includes_only_requested_turn_checkpoints() -> None:
    async def run() -> None:
        async with (
            offline_client(
                httpx2.MockTransport(
                    lambda _: sse_response(
                        EventStream(response_events(response_payload()))
                    )
                )
            ) as client,
            open_test_agent(client=client) as agent,
        ):
            for turn_id, text in ((TURN, "first"), (UUID(int=12), "second")):
                async for _ in agent.astream(
                    workspace_id=WORKSPACE, turn_id=turn_id, input=text
                ):
                    pass
            history = [
                item
                async for item in agent.aget_state_history(
                    workspace_id=WORKSPACE, turn_id=TURN
                )
            ]
            assert history
            assert {
                item.metadata.get("turn_id") for item in history if item.metadata
            } == {str(TURN)}
            assert history[-1].metadata
            assert history[-1].metadata.get("source") == "input"
            assert [
                item
                async for item in agent.aget_state_history(
                    workspace_id=WORKSPACE, turn_id=UUID(int=99)
                )
            ] == []

    asyncio.run(run())


def test_checkpoint_stream_is_opt_in_and_preserves_native_identity() -> None:
    async def run() -> None:
        async with (
            offline_client(
                httpx2.MockTransport(
                    lambda _: sse_response(
                        EventStream(response_events(response_payload()))
                    )
                )
            ) as client,
            open_test_agent(client=client) as agent,
        ):
            default_parts = [
                part
                async for part in agent.astream(
                    workspace_id=WORKSPACE, turn_id=TURN, input="first"
                )
            ]
            assert {part["type"] for part in default_parts} == {"values", "custom"}
            second_turn = UUID(int=12)
            checkpoints = [
                part["data"]
                async for part in agent.astream(
                    workspace_id=WORKSPACE,
                    turn_id=second_turn,
                    input="second",
                    input_fingerprint=FINGERPRINT,
                    include_checkpoints=True,
                )
                if part["type"] == "checkpoints"
            ]
            assert checkpoints
            applied = next(
                item
                for item in checkpoints
                if item["values"].get("turn_id") == second_turn
            )
            saved = await agent.aget_state(
                workspace_id=WORKSPACE,
                checkpoint_id=applied["config"]["configurable"]["checkpoint_id"],
            )
            assert saved.metadata
            assert saved.metadata.get("turn_id") == str(second_turn)
            assert saved.metadata.get("input_fingerprint") == FINGERPRINT

    asyncio.run(run())
