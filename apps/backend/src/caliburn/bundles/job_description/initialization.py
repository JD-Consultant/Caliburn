"""每輪捕捉 JD 取消基準，原輪恢復重用官方 Task 結果。"""

import asyncio

from langgraph.func import task
from langgraph.runtime import Runtime

from caliburn.bundles.job_description.services import JD_PREVIOUS_COMPLETED, JD_QUERIES
from caliburn.bundles.job_description.state import (
    JobDescriptionState,
    JobDescriptionTurnState,
)
from caliburn.modules.agent.plugins.contracts import AgentContext


async def initialize_turn_jd(
    state: JobDescriptionTurnState, *, runtime: Runtime[AgentContext]
) -> JobDescriptionState:
    queries = runtime.context.services.require(JD_QUERIES)

    @task
    async def capture() -> JobDescriptionState:
        previous = await runtime.context.services.require(JD_PREVIOUS_COMPLETED)(
            state["workspace_id"], state["turn_id"]
        )
        snapshot = await asyncio.to_thread(
            queries.find_job_description_by_workspace,
            workspace_id=state["workspace_id"],
        )
        before_version = None
        if snapshot is not None:
            before_version = 1
            if (
                previous is not None
                and previous.values.get("jd_id") == snapshot.job_description_id
            ):
                completed_version = previous.values.get("jd_completed_version")
                if isinstance(completed_version, int):
                    before_version = completed_version
        return {
            "jd_turn_id": state["turn_id"],
            "jd_id": snapshot.job_description_id if snapshot else None,
            "jd_turn_start_version": snapshot.version if snapshot else None,
            "jd_version": None,
            "jd_manual_before_version": before_version,
            "jd_completed_version": None,
        }

    return await capture()
