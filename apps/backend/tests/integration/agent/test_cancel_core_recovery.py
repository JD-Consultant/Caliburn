"""取消保存故障與取消後新輪 input-only 的冷恢復邊界。"""

import asyncio
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import httpx2
import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import ChannelVersions, Checkpoint, CheckpointMetadata

from caliburn.modules.agent.agent import turn_cancel_status
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


@pytest.mark.parametrize(
    "stage", ["pending_before", "pending_after", "completed_before", "completed_after"]
)
def test_cancel_save_failure_is_recovered_through_same_public_entry(
    checkpoint_conninfo: str,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
) -> None:
    workspace, turn_id = UUID(int=501), UUID(int=502)
    effects = CancellationEffects()
    target, boundary = stage.split("_")

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(lambda _: pytest.fail("model called"))
        ) as client:
            async with (
                open_postgres_checkpointer(
                    checkpoint_conninfo, initialize=True
                ) as saver,
                open_agent(
                    agent_id="cancel-recover",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=(
                        BundleConfig(
                            "tests.integration.agent.cancel_core_fixture",
                            {"wait": True},
                        ),
                    ),
                    external_services=(EFFECTS.bind(effects),),
                    checkpointer=saver,
                ) as agent,
            ):
                await consume(
                    agent.astream(workspace_id=workspace, turn_id=turn_id, input="old")
                )
                original_put = saver.aput

                async def fail_save(
                    config: RunnableConfig,
                    checkpoint: Checkpoint,
                    metadata: CheckpointMetadata,
                    new_versions: ChannelVersions,
                ) -> RunnableConfig:
                    matches = (
                        checkpoint["channel_values"].get("cancel_status") == target
                    )
                    if matches and boundary == "before":
                        raise RuntimeError("synthetic cancel save failure")
                    result = await original_put(
                        config, checkpoint, metadata, new_versions
                    )
                    if matches and boundary == "after":
                        raise RuntimeError("synthetic cancel save failure")
                    return result

                with monkeypatch.context() as injection:
                    injection.setattr(saver, "aput", fail_save)
                    with pytest.raises(RuntimeError, match="cancel save failure"):
                        await agent.acancel_turn(
                            workspace_id=workspace, turn_id=turn_id
                        )
                if target == "pending":
                    assert effects.withdrawals == {}
                else:
                    assert effects.withdrawals == {turn_id: [str(turn_id)]}
                saved = await agent.aget_state(workspace_id=workspace)
                expected = (
                    None
                    if stage == "pending_before"
                    else "completed"
                    if stage == "completed_after"
                    else "pending"
                )
                assert turn_cancel_status(saved) == expected
            async with (
                open_postgres_checkpointer(checkpoint_conninfo) as saver,
                open_agent(
                    agent_id="cancel-recover",
                    resume_version="v2",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=(
                        BundleConfig("tests.integration.agent.cancel_core_fixture"),
                    ),
                    external_services=(EFFECTS.bind(effects),),
                    checkpointer=saver,
                ) as agent,
            ):
                await agent.acancel_turn(workspace_id=workspace, turn_id=turn_id)
                assert effects.withdrawals == {turn_id: [str(turn_id)]}
                assert (
                    turn_cancel_status(await agent.aget_state(workspace_id=workspace))
                    == "completed"
                )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_new_input_after_cancel_does_not_inherit_previous_completed_on_cold_resume(
    checkpoint_conninfo: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, old_turn, new_turn = UUID(int=601), UUID(int=602), UUID(int=603)
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        if len(sent) == 1:
            raise RuntimeError("synthetic old model failure")
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(respond)) as client:
            async with (
                open_postgres_checkpointer(
                    checkpoint_conninfo, initialize=True
                ) as saver,
                open_agent(
                    agent_id="cancel-new-input",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=(),
                    checkpointer=saver,
                ) as agent,
            ):
                with pytest.raises(RuntimeError, match="old model failure"):
                    await consume(
                        agent.astream(
                            workspace_id=workspace, turn_id=old_turn, input="old"
                        )
                    )
                await agent.acancel_turn(workspace_id=workspace, turn_id=old_turn)
                original_put, original_writes = saver.aput, saver.aput_writes

                async def fail_input(
                    config: RunnableConfig,
                    checkpoint: Checkpoint,
                    metadata: CheckpointMetadata,
                    new_versions: ChannelVersions,
                ) -> RunnableConfig:
                    result = await original_put(
                        config, checkpoint, metadata, new_versions
                    )
                    if metadata.get("source") == "input":
                        raise RuntimeError("synthetic new input failure")
                    return result

                async def fail_start(
                    config: RunnableConfig,
                    writes: Sequence[tuple[str, Any]],
                    task_id: str,
                    task_path: str = "",
                ) -> None:
                    if any(
                        channel == "turn_id" and value == new_turn
                        for channel, value in writes
                    ):
                        raise RuntimeError("synthetic new START failure")
                    await original_writes(config, writes, task_id, task_path)

                with monkeypatch.context() as injection:
                    injection.setattr(saver, "aput", fail_input)
                    injection.setattr(saver, "aput_writes", fail_start)
                    with pytest.raises(RuntimeError, match="synthetic new"):
                        await consume(
                            agent.astream(
                                workspace_id=workspace, turn_id=new_turn, input="new"
                            )
                        )
            async with (
                open_postgres_checkpointer(checkpoint_conninfo) as saver,
                open_agent(
                    agent_id="cancel-new-input",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=(),
                    checkpointer=saver,
                ) as agent,
            ):
                before = await agent.aget_state(workspace_id=workspace)
                assert before.values["cancel_status"] == "completed"
                assert before.values["turn_id"] == old_turn
                assert turn_cancel_status(before) is None
                await consume(agent.aresume(workspace_id=workspace, turn_id=new_turn))
                saved = await agent.aget_state(workspace_id=workspace)
                assert saved.values["turn_id"] == new_turn
                assert saved.values["cancel_status"] is None
                assert saved.values["model_step"] == 1

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(sent) == 2
    assert sent[1]["input"] == [{"role": "user", "content": "new"}]
