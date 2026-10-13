"""舊測例的 I/O double 改接正式 agent，不保留舊執行圖。"""

from caliburn.agent_execution.native_agent import (
    NativeToolBinding,
    native_tool,
    read_native_agent_state,
    run_native_agent,
)
from caliburn.agent_execution.response_runtime import ModelStepLimitError
from tests.fixtures.response_capacity import synthetic_capacity_limits


def synthetic_tool_definitions():
    return [
        {
            "type": "function",
            "name": name,
            "description": "合成執行工具",
            "parameters": {"type": "object", "properties": {}},
        }
        for name in ("read_jd", "read_test_record")
    ]


async def read_response_state(checkpointer, config):
    saved = await checkpointer.aget_tuple(config)
    values = {
        "capacity_limits": synthetic_capacity_limits(),
        "pause_enabled": False,
        "request_snapshot": {"tools": []},
        **(saved.checkpoint["channel_values"] if saved else {}),
    }
    request = values["request_snapshot"]
    values["request_snapshot"] = {
        **request,
        "tools": request.get("tools") or synthetic_tool_definitions(),
    }
    return await read_native_agent_state(checkpointer, config, values)


async def run_response_loop(checkpointer, *, runtime, **kwargs):
    request = kwargs["request"]
    if request is None:
        saved = await checkpointer.aget_tuple({"configurable": {"thread_id": kwargs["thread_id"]}})
        definitions = (
            saved.checkpoint["channel_values"].get("request_snapshot", {}).get("tools", [])
            if saved
            else []
        )
    else:
        definitions = request.create_payload()["tools"]
    tools = []
    if runtime.prepare_tool is not None and runtime.execute_tool is not None:
        tools = [
            native_tool(
                definition,
                NativeToolBinding(runtime.prepare_tool, runtime.execute_tool),
                runtime.ensure_active,
            )
            for definition in definitions or synthetic_tool_definitions()
        ]
    return await run_native_agent(
        checkpointer,
        runtime=runtime,
        tools=tools,
        unknown_tool_output="synthetic unknown tool",
        **kwargs,
    )


async def run_response_step(checkpointer, *, thread_id, **kwargs):
    """測一個有界 Step 的原件，不重新提供產品單 Step 執行入口。"""
    try:
        return await run_response_loop(
            checkpointer, thread_id=thread_id, max_model_steps=1, **kwargs
        )
    except ModelStepLimitError:
        saved = await checkpointer.aget_tuple({"configurable": {"thread_id": thread_id}})
        return saved.checkpoint["channel_values"]
