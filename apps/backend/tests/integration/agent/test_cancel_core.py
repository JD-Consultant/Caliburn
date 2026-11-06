"""公開 Agent 取消與冷恢復的真 PostgreSQL 驗收。"""

import asyncio
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import httpx2
import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import ChannelVersions, Checkpoint, CheckpointMetadata
from langgraph.errors import GraphDrained
from langgraph.runtime import RunControl
from langgraph.types import Command

from caliburn.modules.agent.agent import AgentExecutionError
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from tests.integration.agent.cancel_core_fixture import EFFECTS, CancellationEffects
from tests.integration.agent.stream_support import consume
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def test_cancelled_turn_rejects_resume_and_new_turn_rebuilds_request(
    checkpoint_conninfo: str,
) -> None:
    workspace, old_turn, new_turn = UUID(int=101), UUID(int=102), UUID(int=103)
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        if len(sent) == 1:
            raise RuntimeError("synthetic model outage")
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with (
            open_postgres_checkpointer(checkpoint_conninfo, initialize=True) as saver,
            offline_client(httpx2.MockTransport(respond)) as client,
        ):
            async with open_agent(
                agent_id="cancel",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(),
                checkpointer=saver,
            ) as agent:
                with pytest.raises(RuntimeError, match="synthetic model outage"):
                    await consume(
                        agent.astream(
                            workspace_id=workspace,
                            turn_id=old_turn,
                            input="old",
                            input_fingerprint="original",
                        )
                    )
                await agent.acancel_turn(workspace_id=workspace, turn_id=old_turn)
                saved = await agent.aget_state(workspace_id=workspace)
                assert saved.values["cancel_status"] == "completed"
                assert saved.metadata is not None
                assert saved.metadata.get("turn_id") == str(old_turn)
                assert saved.metadata.get("input_fingerprint") == "original"
                assert saved.metadata.get("resume_version") == "v1"
            async with open_agent(
                agent_id="cancel",
                resume_version="v2",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(),
                checkpointer=saver,
            ) as agent:
                await agent.acancel_turn(workspace_id=workspace, turn_id=old_turn)
                with pytest.raises(AgentExecutionError):
                    await consume(
                        agent.aresume(workspace_id=workspace, turn_id=old_turn)
                    )
                with pytest.raises(AgentExecutionError):
                    await consume(
                        agent.astream(
                            workspace_id=workspace, turn_id=old_turn, input="old"
                        )
                    )
                await consume(
                    agent.astream(workspace_id=workspace, turn_id=new_turn, input="new")
                )
                saved = await agent.aget_state(workspace_id=workspace)
                assert saved.values["cancel_status"] is None
                assert saved.values["turn_id"] == new_turn
                assert saved.values["model_step"] == 1
                with pytest.raises(AgentExecutionError):
                    await agent.acancel_turn(workspace_id=workspace, turn_id=new_turn)
                # 舊輪取消重送不干擾已開始的新輪。
                await agent.acancel_turn(workspace_id=workspace, turn_id=old_turn)
                with pytest.raises(AgentExecutionError):
                    await consume(
                        agent.astream(
                            workspace_id=workspace, turn_id=old_turn, input="old"
                        )
                    )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(sent) == 2
    assert sent[1]["input"] == [{"role": "user", "content": "new"}]


@pytest.mark.parametrize(
    "boundary", ["input", "input_without_start_writes", "baseline"]
)
def test_cancellation_preserves_only_target_turn_baseline_at_save_failures(
    checkpoint_conninfo: str,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    workspace, old_turn, turn_id = UUID(int=301), UUID(int=302), UUID(int=303)
    effects = CancellationEffects()

    async def run() -> None:
        async with (
            open_postgres_checkpointer(checkpoint_conninfo, initialize=True) as saver,
            offline_client(
                httpx2.MockTransport(lambda _: pytest.fail("model called"))
            ) as client,
            open_agent(
                agent_id="cancel-save",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(
                    BundleConfig(
                        "tests.integration.agent.cancel_core_fixture", {"wait": True}
                    ),
                ),
                external_services=(EFFECTS.bind(effects),),
                checkpointer=saver,
            ) as agent,
        ):
            await consume(
                agent.astream(workspace_id=workspace, turn_id=old_turn, input="old")
            )
            await agent.acancel_turn(workspace_id=workspace, turn_id=old_turn)
            original_put, original_writes = saver.aput, saver.aput_writes

            async def fail_checkpoint(
                config: RunnableConfig,
                checkpoint: Checkpoint,
                metadata: CheckpointMetadata,
                new_versions: ChannelVersions,
            ) -> RunnableConfig:
                if (
                    boundary == "baseline"
                    and checkpoint["channel_values"].get("baseline_turn_id") == turn_id
                ):
                    raise RuntimeError("synthetic checkpoint failure")
                result = await original_put(config, checkpoint, metadata, new_versions)
                if boundary.startswith("input") and metadata.get("source") == "input":
                    raise RuntimeError("synthetic checkpoint failure")
                return result

            async def fail_start_writes(
                config: RunnableConfig,
                writes: Sequence[tuple[str, Any]],
                task_id: str,
                task_path: str = "",
            ) -> None:
                if any(
                    channel == "turn_id" and value == turn_id
                    for channel, value in writes
                ):
                    raise RuntimeError("synthetic START write failure")
                await original_writes(config, writes, task_id, task_path)

            with monkeypatch.context() as injection:
                injection.setattr(saver, "aput", fail_checkpoint)
                if boundary == "input_without_start_writes":
                    injection.setattr(saver, "aput_writes", fail_start_writes)
                with pytest.raises(RuntimeError, match="synthetic"):
                    await consume(
                        agent.astream(
                            workspace_id=workspace, turn_id=turn_id, input="new"
                        )
                    )
            await agent.acancel_turn(workspace_id=workspace, turn_id=turn_id)
            expected = [str(old_turn), str(turn_id)] if boundary == "baseline" else None
            assert effects.withdrawals[turn_id] == expected
            assert (turn_id in effects.missing_states) == (
                boundary == "input_without_start_writes"
            )
            saved = await agent.aget_state(workspace_id=workspace)
            assert saved.values["cancel_status"] == "completed"
            if boundary == "baseline":
                assert saved.values["baseline"] == [str(old_turn), str(turn_id)]

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_run_control_drains_at_saved_plugin_boundary_then_allows_cancellation(
    checkpoint_conninfo: str,
) -> None:
    workspace, turn_id = UUID(int=401), UUID(int=402)
    effects, control = CancellationEffects(), RunControl()

    async def run() -> None:
        async with (
            open_postgres_checkpointer(checkpoint_conninfo, initialize=True) as saver,
            offline_client(
                httpx2.MockTransport(lambda _: pytest.fail("model called"))
            ) as client,
            open_agent(
                agent_id="cancel-drain",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(
                    BundleConfig(
                        "tests.integration.agent.cancel_core_fixture", {"drain": True}
                    ),
                ),
                external_services=(EFFECTS.bind(effects),),
                checkpointer=saver,
            ) as agent,
        ):
            with pytest.raises(GraphDrained):
                await consume(
                    agent.astream(
                        workspace_id=workspace,
                        turn_id=turn_id,
                        input="old",
                        control=control,
                    )
                )
            assert control.drain_requested
            assert (await agent.aget_state(workspace_id=workspace)).values[
                "baseline_turn_id"
            ] == turn_id
            resume_control = RunControl()
            resume_control.request_drain("stop before resume")
            with pytest.raises(GraphDrained):
                await consume(
                    agent.aresume(
                        workspace_id=workspace, turn_id=turn_id, control=resume_control
                    )
                )
            await agent.acancel_turn(workspace_id=workspace, turn_id=turn_id)
            assert effects.withdrawals == {turn_id: [str(turn_id)]}

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_failed_plugin_keeps_pending_and_cold_retry_uses_saved_baseline(
    checkpoint_conninfo: str,
) -> None:
    workspace, turn_id = UUID(int=201), UUID(int=202)
    effects = CancellationEffects(fail=True)

    async def run() -> None:
        async with (
            open_postgres_checkpointer(checkpoint_conninfo, initialize=True) as saver,
            offline_client(
                httpx2.MockTransport(lambda _: pytest.fail("model called"))
            ) as client,
        ):
            async with open_agent(
                agent_id="cancel-hook",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(
                    BundleConfig(
                        "tests.integration.agent.cancel_core_fixture", {"wait": True}
                    ),
                ),
                external_services=(EFFECTS.bind(effects),),
                checkpointer=saver,
            ) as agent:
                await consume(
                    agent.astream(workspace_id=workspace, turn_id=turn_id, input="old")
                )
                with pytest.raises(RuntimeError, match="withdrawal failure"):
                    await agent.acancel_turn(workspace_id=workspace, turn_id=turn_id)
                pending = await agent.aget_state(workspace_id=workspace)
                assert pending.values["cancel_status"] == "pending"
            effects.fail = False
            async with open_agent(
                agent_id="cancel-hook",
                resume_version="v2",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(BundleConfig("tests.integration.agent.cancel_core_fixture"),),
                external_services=(EFFECTS.bind(effects),),
                checkpointer=saver,
            ) as agent:
                commands: tuple[Command[Any] | None, ...] = (
                    None,
                    Command(resume={"ignored": "answer"}),
                )
                for command in commands:
                    with pytest.raises(AgentExecutionError):
                        await consume(
                            agent.aresume(
                                workspace_id=workspace,
                                turn_id=turn_id,
                                resume_command=command,
                            )
                        )
                with pytest.raises(AgentExecutionError):
                    await consume(
                        agent.astream(
                            workspace_id=workspace, turn_id=UUID(int=203), input="new"
                        )
                    )
                await agent.acancel_turn(workspace_id=workspace, turn_id=turn_id)
                assert effects.withdrawals == {turn_id: [str(turn_id)]}
                saved = await agent.aget_state(workspace_id=workspace)
                assert saved.values["cancel_status"] == "completed"
                assert saved.metadata is not None
                assert saved.metadata.get("resume_version") == "v1"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
