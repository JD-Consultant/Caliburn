"""從同一份 Plan 查詢結果投影模型正文與已見版本。"""

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any, TypedDict

from langgraph.runtime import Runtime

from caliburn.bundles.context.contracts import WindowContribution
from caliburn.bundles.context.services import WINDOW_CONTRIBUTIONS
from caliburn.bundles.plan.services import PLAN_QUERIES
from caliburn.modules.agent.plugins.contracts import AgentContext, AgentPlugin
from caliburn.modules.agent.plugins.services import PluginServices, ServiceBinding
from caliburn.modules.agent.state import AgentState, OpenAIItems, request_items
from caliburn.modules.plan.application.errors import PlanNotInitializedError
from caliburn.modules.plan.application.results import PlanView


class PlanContext(TypedDict):
    items: OpenAIItems
    plan_version: int


@asynccontextmanager
async def _open_plan_window(
    services: PluginServices,
) -> AsyncIterator[tuple[ServiceBinding[tuple[WindowContribution, ...]], ...]]:
    yield (WINDOW_CONTRIBUTIONS.bind((WindowContribution(prepare_plan_window),)),)


def create_context_plugin() -> AgentPlugin:
    """向選用的窗口提供固定回呼，不另開捕捉正文的節點。"""
    return AgentPlugin(
        name="plan_context",
        required_plugins=("plan_lifecycle",),
        required_services=(PLAN_QUERIES,),
        provided_services=(WINDOW_CONTRIBUTIONS,),
        open_services=_open_plan_window,
    )


def project_plan_context(plan: PlanView) -> PlanContext:
    """保留正文的 null／空字串；尚未初始化時拒絕，不猜測版本。"""
    if plan.version is None:
        raise PlanNotInitializedError
    return {
        "items": [
            {
                "role": "user",
                "content": json.dumps(
                    {"data_kind": "consultant_interview_plan", "plan": plan.body},
                    ensure_ascii=False,
                ),
            }
        ],
        "plan_version": plan.version,
    }


async def prepare_plan_window(
    state: AgentState,
    *,
    previous: Mapping[str, Any] | None,
    rebuilding: bool,
    runtime: Runtime[AgentContext],
) -> Mapping[str, object]:
    """重建時附加同次查讀的 Plan；延續時沿用前窗口已見版，不改取消基準。"""
    if not rebuilding:
        return {
            "plan_version": previous.get("plan_version")
            if previous is not None
            else None
        }
    queries = runtime.context.services.require(PLAN_QUERIES)
    plan = await asyncio.to_thread(
        queries.get_current, workspace_id=state["workspace_id"]
    )
    projected = project_plan_context(plan)
    request = state["model_request"]
    return {
        "model_request": {
            **request,
            "input": [*request_items(request), *projected["items"]],
        },
        "plan_version": projected["plan_version"],
    }
