"""取消保存方案的 LangGraph 原生探針；不冒充 Agent 產品驗收。"""

import asyncio
import operator
from typing import Annotated, TypedDict

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import ChannelVersions, Checkpoint, CheckpointMetadata
from langgraph.graph import END, START, StateGraph
from langgraph.types import StateUpdate

from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)


class ProbeState(TypedDict, total=False):
    turn_id: str
    baseline: Annotated[list[str], operator.add]
    cancel_status: str | None


@pytest.mark.parametrize("boundary", ["input", "baseline", "waiting"])
def test_public_bulk_update_retains_pending_result_and_replaces_old_schedule(
    checkpoint_conninfo: str, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    async def run() -> None:
        calls: list[str] = []

        def initialize(state: ProbeState) -> ProbeState:
            return {"baseline": [state["turn_id"]]}

        def tool(state: ProbeState) -> ProbeState:
            calls.append(state["turn_id"])
            return {}

        builder = StateGraph(ProbeState)
        builder.add_node("initialize", initialize)
        builder.add_node("tool", tool)
        builder.add_node("cancel", lambda state: {})
        builder.add_edge(START, "initialize")
        builder.add_edge("initialize", "tool")
        builder.add_edge("tool", END)
        async with open_postgres_checkpointer(
            checkpoint_conninfo, initialize=True
        ) as saver:
            graph = builder.compile(checkpointer=saver, interrupt_before=["tool"])
            config: RunnableConfig = {
                "configurable": {"thread_id": boundary},
                "metadata": {
                    "turn_id": "old",
                    "resume_version": "v1",
                    "input_fingerprint": "old-fingerprint",
                },
            }
            original_put = saver.aput

            async def fail_after_checkpoint(
                config: RunnableConfig,
                checkpoint: Checkpoint,
                metadata: CheckpointMetadata,
                new_versions: ChannelVersions,
            ) -> RunnableConfig:
                at_input = metadata.get("source") == "input"
                at_baseline = checkpoint["channel_values"].get("baseline") == ["old"]
                if boundary == "baseline" and at_baseline:
                    raise RuntimeError("stop before baseline checkpoint")
                saved = await original_put(config, checkpoint, metadata, new_versions)
                if boundary == "input" and at_input:
                    raise RuntimeError("stop after input checkpoint")
                return saved

            with monkeypatch.context() as patch:
                patch.setattr(saver, "aput", fail_after_checkpoint)
                if boundary == "waiting":
                    await graph.ainvoke(
                        {"turn_id": "old", "cancel_status": None},
                        config,
                        durability="sync",
                    )
                else:
                    with pytest.raises(RuntimeError, match="stop"):
                        await graph.ainvoke(
                            {"turn_id": "old", "cancel_status": None},
                            config,
                            durability="sync",
                        )
            saved = await graph.aget_state(config)
            expected = saved.values.get("baseline", [])
            updates = [
                StateUpdate(
                    {
                        key: value
                        for key, value in task.result.items()
                        if key != "cancel_status"
                    },
                    task.name,
                    task.id,
                )
                for task in saved.tasks
                if task.result is not None
            ]
            updates.append(StateUpdate({"cancel_status": "pending"}, "cancel"))
            await graph.abulk_update_state(config, [updates])
            pending = await graph.aget_state(config)
            assert pending.values.get("baseline", []) == expected
            assert pending.values["cancel_status"] == "pending"
            assert pending.metadata is not None
            assert pending.metadata.get("turn_id") == "old"
            assert pending.metadata.get("resume_version") == "v1"
            assert pending.metadata.get("input_fingerprint") == "old-fingerprint"
            await graph.aupdate_state(
                config, {"cancel_status": "completed"}, as_node="cancel"
            )
            await graph.ainvoke(
                {"turn_id": "new", "cancel_status": None},
                {**config, "metadata": {"turn_id": "new"}},
                durability="sync",
            )
            await graph.ainvoke(None, config, durability="sync")
            assert calls == ["new"]
            assert (await graph.aget_state(config)).values["cancel_status"] is None

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
