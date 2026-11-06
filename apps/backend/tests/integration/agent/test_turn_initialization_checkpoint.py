"""新輪 input／START 保存後失敗的原生恢復界線。"""

import asyncio
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import httpx2
import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import ChannelVersions, Checkpoint, CheckpointMetadata

from caliburn.modules.agent.agent import AgentExecutionError
from caliburn.modules.agent.bootstrap import open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from tests.integration.agent.stream_support import consume
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    message,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


@pytest.mark.parametrize("boundary", ["input", "input_without_start_writes", "start"])
def test_resume_after_new_input_checkpoint_never_emits_previous_turn_response(
    checkpoint_conninfo: str,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    """原生 input 快照可保留舊 State；串流只投影所恢復輪次。"""
    workspace = UUID(int=8)
    old_turn, new_turn = UUID(int=81), UUID(int=82)
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        payload = response_payload(
            [message(text="old reply" if len(sent) == 1 else "new reply")]
        )
        return sse_response(EventStream(response_events(payload)))

    async def run() -> None:
        async with (
            open_postgres_checkpointer(checkpoint_conninfo, initialize=True) as saver,
            offline_client(httpx2.MockTransport(respond)) as client,
            open_agent(
                agent_id="initialize-turn",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(),
                checkpointer=saver,
            ) as agent,
        ):
            await consume(
                agent.astream(workspace_id=workspace, turn_id=old_turn, input="old")
            )
            original_put = saver.aput
            original_writes = saver.aput_writes

            async def reject_start_writes(
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

            async def fail_after_new_input(
                config: RunnableConfig,
                checkpoint: Checkpoint,
                metadata: CheckpointMetadata,
                new_versions: ChannelVersions,
            ) -> RunnableConfig:
                saved = await original_put(config, checkpoint, metadata, new_versions)
                at_input = metadata.get("source") == "input"
                at_start = (
                    metadata.get("source") == "loop"
                    and checkpoint["channel_values"].get("turn_input") == "new"
                )
                if (boundary.startswith("input") and at_input) or (
                    boundary == "start" and at_start
                ):
                    raise RuntimeError("synthetic failure after input save")
                return saved

            with monkeypatch.context() as injection:
                injection.setattr(saver, "aput", fail_after_new_input)
                if boundary == "input_without_start_writes":
                    injection.setattr(saver, "aput_writes", reject_start_writes)
                with pytest.raises(RuntimeError, match="synthetic failure"):
                    await consume(
                        agent.astream(
                            workspace_id=workspace, turn_id=new_turn, input="new"
                        )
                    )
            assert len(sent) == 1

        async with (
            open_postgres_checkpointer(checkpoint_conninfo) as saver,
            offline_client(httpx2.MockTransport(respond)) as client,
            open_agent(
                agent_id="initialize-turn",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(),
                checkpointer=saver,
            ) as agent,
        ):
            pending = await agent.aget_state(workspace_id=workspace)
            assert pending.metadata is not None
            assert pending.metadata.get("turn_id") == str(new_turn)
            assert pending.values["workspace_id"] == workspace
            if boundary == "input_without_start_writes":
                assert pending.next == ("__start__",)
                assert pending.values["turn_id"] == old_turn
                assert pending.values["model_response"].output_text == "old reply"
            history_before = [
                item.config
                async for item in agent.aget_state_history(workspace_id=workspace)
            ]
            with pytest.raises(AgentExecutionError):
                await consume(agent.aresume(workspace_id=workspace, turn_id=old_turn))
            assert [
                item.config
                async for item in agent.aget_state_history(workspace_id=workspace)
            ] == history_before
            parts = [
                part
                async for part in agent.aresume(
                    workspace_id=workspace, turn_id=new_turn
                )
            ]
            responses = [
                part["data"]["model_response"]
                for part in parts
                if part["type"] == "values"
                and part["data"].get("model_response") is not None
            ]
            assert responses
            assert all(response.output_text == "new reply" for response in responses)
            assert all(
                part["data"]["turn_id"] == new_turn
                for part in parts
                if part["type"] == "values" and part["data"]
            )
            completed = await agent.aget_state(workspace_id=workspace)
            assert not completed.next
            assert completed.values["turn_input"] == "new"
            assert completed.values["turn_id"] == new_turn
            assert completed.values["model_step"] == 1

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(sent) == 2
    assert sent[1]["input"] == [{"role": "user", "content": "new"}]
