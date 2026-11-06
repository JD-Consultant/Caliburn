"""新輪最早 input 保存點不能冒充上一成功輪的完成 State。"""

import asyncio
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import httpx2
import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import ChannelVersions, Checkpoint, CheckpointMetadata
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.modules.agent.bootstrap import open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    openai_checkpoint_serializer,
)
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    offline_client,
    response_events,
    response_payload,
    sse_response,
)


@pytest.mark.parametrize("reject_start_writes", [False, True])
def test_input_capture_returns_previous_completed_checkpoint_without_resuming(
    monkeypatch: pytest.MonkeyPatch, reject_start_writes: bool
) -> None:
    workspace, previous_turn, new_turn = UUID(int=41), UUID(int=419), UUID(int=412)
    requests: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        saver = InMemorySaver(serde=openai_checkpoint_serializer())
        async with (
            offline_client(httpx2.MockTransport(respond)) as client,
            open_agent(
                agent_id="input-capture-read",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(),
                checkpointer=saver,
            ) as agent,
        ):
            async for _ in agent.astream(
                workspace_id=workspace, turn_id=previous_turn, input="first"
            ):
                pass
            completed = await agent.aget_state(workspace_id=workspace)
            original_put = saver.aput
            original_writes = saver.aput_writes

            async def fail_after_input(
                config: RunnableConfig,
                checkpoint: Checkpoint,
                metadata: CheckpointMetadata,
                new_versions: ChannelVersions,
            ) -> RunnableConfig:
                saved = await original_put(config, checkpoint, metadata, new_versions)
                if metadata.get("source") == "input":
                    raise RuntimeError("synthetic failure after input capture")
                return saved

            async def fail_before_start_writes(
                config: RunnableConfig,
                writes: Sequence[tuple[str, Any]],
                task_id: str,
                task_path: str = "",
            ) -> None:
                if any(
                    channel == "turn_id" and value == new_turn
                    for channel, value in writes
                ):
                    raise RuntimeError("synthetic failure before start writes")
                await original_writes(config, writes, task_id, task_path)

            with monkeypatch.context() as injection:
                injection.setattr(saver, "aput", fail_after_input)
                if reject_start_writes:
                    injection.setattr(saver, "aput_writes", fail_before_start_writes)
                with pytest.raises(RuntimeError, match="synthetic failure"):
                    async for _ in agent.astream(
                        workspace_id=workspace, turn_id=new_turn, input="second"
                    ):
                        pass
            pending = await agent.aget_state(workspace_id=workspace)
            assert pending.metadata is not None
            assert pending.metadata.get("source") == "input"
            assert pending.metadata.get("turn_id") == str(new_turn)
            if reject_start_writes:
                assert pending.values["turn_id"] == previous_turn
                assert pending.values["model_response"] is not None
            result = await agent.aget_previous_completed_turn(
                workspace_id=workspace, before_turn_id=new_turn
            )
            assert result is not None
            assert result.config == completed.config
            assert result.values["turn_id"] == previous_turn
            assert result.values["model_response"].output_text == "Synthetic reply"
            assert (await agent.aget_state(workspace_id=workspace)) == pending
            assert len(requests) == 1

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
