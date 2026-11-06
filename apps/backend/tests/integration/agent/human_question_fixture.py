"""只在指定呼叫故障一次，驗證提問工具前後的原生恢復。"""

import json
from collections.abc import Awaitable, Callable, Mapping

from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    failed = False

    async def fail_once(
        request: ToolCallRequest,
        execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[object]]],
    ) -> ToolMessage | Command[object]:
        nonlocal failed
        if config["when"] == "rewrite":
            request = request.override(
                tool_call={
                    **request.tool_call,
                    "args": {
                        "questions": [
                            {
                                "question": "實際展示的問題？",
                                "options": [{"label": "實際選項"}],
                            }
                        ]
                    },
                }
            )
            return await execute(request)
        if not failed and config["when"] == "before":
            failed = True
            raise RuntimeError("提問前的合成故障")
        result = await execute(request)
        if config["when"] == "reorder_answers":
            assert isinstance(result, ToolMessage) and isinstance(result.content, str)
            answers = json.loads(result.content)["answers"]
            return result.model_copy(
                update={"content": json.dumps({"answers": list(reversed(answers))})}
            )
        if not failed and config["when"] == "after":
            failed = True
            raise RuntimeError("取得答案後的合成故障")
        return result

    return AgentBundle(plugins=(AgentPlugin("fault", wrap_tool_call=(fail_once,)),))
