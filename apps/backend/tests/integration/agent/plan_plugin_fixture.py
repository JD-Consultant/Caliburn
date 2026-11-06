"""只在公開插件與查詢邊界注入 Plan 恢復測試的故障。"""

from collections.abc import Awaitable, Callable, Mapping
from uuid import UUID

from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin
from caliburn.modules.plan.application.errors import PlanQueryError
from caliburn.modules.plan.application.results import PlanView


class UnavailablePlanQueries:
    def get_current(self, *, workspace_id: UUID) -> PlanView:
        raise PlanQueryError("synthetic Plan query outage")


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    async def fail_after_edit(
        request: ToolCallRequest,
        execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[str]]],
    ) -> ToolMessage | Command[str]:
        result = await execute(request)
        if config.get("fail") and request.tool_call["name"] == "edit_interview_plan":
            raise RuntimeError("synthetic post-edit outage")
        return result

    return AgentBundle(
        (AgentPlugin("plan-failure-boundary", wrap_tool_call=(fail_after_edit,)),)
    )
