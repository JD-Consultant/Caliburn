"""將 Agent 的取消裁決接到 JD 自有完整快照恢復。"""

import asyncio
from uuid import UUID

from caliburn.bundles.job_description.services import JD_UOW_FACTORY
from caliburn.bundles.job_description.state import JobDescriptionState
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.job_description.application.history.turn_changes import (
    RestoreTurnChangesInput,
    restore_turn_changes,
)


async def cancel_turn_jd(
    state: JobDescriptionState | None,
    *,
    workspace_id: UUID,
    turn_id: UUID,
    context: AgentContext,
) -> None:
    if state is None or state.get("jd_turn_id") != turn_id:
        return
    jd_id, base_version = state["jd_id"], state["jd_turn_start_version"]
    if jd_id is None or base_version is None:
        return
    await asyncio.to_thread(
        restore_turn_changes,
        workspace_id=workspace_id,
        input=RestoreTurnChangesInput(
            job_description_id=jd_id,
            base_version=base_version,
            correlation_id=str(turn_id),
        ),
        uow_factory=context.services.require(JD_UOW_FACTORY),
    )
