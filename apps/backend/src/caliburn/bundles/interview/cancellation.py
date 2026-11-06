"""沿 Agent 已核對的輪次身分撤回訪談，不依賴 Graph 保存時點。"""

import asyncio
from uuid import UUID

from caliburn.bundles.interview.services import INTERVIEW_UOW_FACTORY
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.state import AgentState
from caliburn.modules.interview.application.withdrawal import withdraw_turn


async def cancel_turn_interview(
    state: AgentState | None,
    *,
    workspace_id: UUID,
    turn_id: UUID,
    context: AgentContext,
) -> None:
    await asyncio.to_thread(
        withdraw_turn,
        workspace_id=workspace_id,
        turn_id=turn_id,
        uow_factory=context.services.require(INTERVIEW_UOW_FACTORY),
    )
