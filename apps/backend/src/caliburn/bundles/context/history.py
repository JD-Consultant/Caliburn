"""從既有 Agent checkpoint 選取上一個成功完成的顧問窗口。"""

from uuid import UUID

from langgraph.types import StateSnapshot

from caliburn.modules.agent.agent import Agent, completed_turn_id


async def previous_completed_window(
    agent: Agent, *, workspace_id: UUID, turn_id: UUID
) -> StateSnapshot | None:
    seen = {str(turn_id)}
    async for snapshot in agent.aget_state_history(workspace_id=workspace_id):
        metadata = snapshot.metadata or {}
        identity = metadata.get("turn_id")
        if not isinstance(identity, str) or identity in seen:
            continue
        seen.add(identity)
        if completed_turn_id(snapshot) is not None:
            if metadata.get("resume_version") != agent.resume_version:
                return None
            return snapshot
    return None


async def completed_window_turns(
    agent: Agent, *, workspace_id: UUID
) -> frozenset[UUID]:
    seen: set[str] = set()
    completed: set[UUID] = set()
    async for snapshot in agent.aget_state_history(workspace_id=workspace_id):
        identity = snapshot.metadata.get("turn_id") if snapshot.metadata else None
        if not isinstance(identity, str) or identity in seen:
            continue
        seen.add(identity)
        if turn_id := completed_turn_id(snapshot):
            completed.add(turn_id)
    return frozenset(completed)
