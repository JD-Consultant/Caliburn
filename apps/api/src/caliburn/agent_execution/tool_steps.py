"""只讀完整原生 history 與 pause；執行路由由標準 agent 負責。"""

from copy import deepcopy

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from openai.types.responses.response_input_item_param import FunctionCallOutput

from caliburn.adapters.response_serialization import (
    NativeItems,
    NativeSnapshot,
    response_input_items,
    restore_response,
)
from caliburn.agent_execution.context_windows import SavedContextWindow, read_context_checkpoint
from caliburn.agent_execution.native_agent import native_agent_pause, read_native_agent_state
from caliburn.agent_execution.response_runtime import PausedResponseLoop


async def read_completed_response_history(
    checkpointer: BaseCheckpointSaver[str], *, thread_id: str, checkpoint_id: str | None = None
) -> SavedContextWindow:
    """只讀已完成的原生視窗；final R、工具與控制邊界皆完成才有資格。

    這不是產品完成；只有 owner 交易可採用此位置。
    """

    saved = await read_context_checkpoint(
        checkpointer, thread_id=thread_id, checkpoint_id=checkpoint_id
    )

    values = saved.checkpoint["channel_values"]

    if values.get("next_action") != "deliver_answer":
        raise ValueError("The response history has not completed")

    if not values.get("agent_completed"):
        raise ValueError("The response history has not completed")
    snapshot = await read_native_agent_state(checkpointer, saved.config, values)
    if snapshot.next or snapshot.tasks:
        raise ValueError("The response history has not completed its control boundary")

    return SavedContextWindow(
        saved.checkpoint["id"],
        _completed_step_items(
            values["request_snapshot"], values["response_snapshot"], values["tool_results"]
        ),
    )


def _completed_step_items(
    request: NativeSnapshot,
    response: NativeSnapshot,
    tool_results: list[FunctionCallOutput],
) -> NativeItems:
    """Project a qualified finished Step before its originals are cleared."""

    return deepcopy(
        [
            *request["input"],
            *response_input_items(restore_response(response)),
            *(dict(item) for item in tool_results),
        ]
    )


async def read_response_pause(
    checkpointer: BaseCheckpointSaver[str], *, thread_id: str
) -> PausedResponseLoop | None:
    """沿同一 graph 解讀原生 pending pause；不執行節點或授予恢復資格。

    恢復准入與單一 writer 仍由 App owner 核對。
    """

    if not thread_id:
        raise ValueError("A pause read requires the original thread identity")

    config: RunnableConfig = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}

    saved = await checkpointer.aget_tuple(config)

    if saved is None:
        return None

    values = saved.checkpoint["channel_values"]

    if not values.get("pause_enabled", False):
        return None

    return native_agent_pause(await read_native_agent_state(checkpointer, config, values))
