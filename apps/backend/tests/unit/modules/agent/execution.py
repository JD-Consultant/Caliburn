"""完整消費公開串流，再從公開查讀入口核對保存結果。"""

from typing import Any
from uuid import UUID, uuid4

from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.agent import Agent


async def complete_turn(
    agent: Agent,
    *,
    workspace_id: UUID,
    input: str | ResponseInputParam,
    turn_id: UUID | None = None,
) -> dict[str, Any]:
    async for _ in agent.astream(
        workspace_id=workspace_id, turn_id=turn_id or uuid4(), input=input
    ):
        pass
    snapshot = await agent.aget_state(workspace_id=workspace_id)
    return dict(snapshot.values)
