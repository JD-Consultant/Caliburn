"""從官方新到舊歷史定位輪前各輪的最新保存點。"""

from collections.abc import AsyncIterator
from uuid import UUID

from langgraph.types import StateSnapshot


async def previous_turn_snapshots(
    history: AsyncIterator[StateSnapshot], *, before_turn_id: UUID
) -> AsyncIterator[StateSnapshot]:
    """以原生 input 保存點作輪前錨點；每輪僅交付最新保存點。"""
    seen: set[str] = set()
    before = str(before_turn_id)
    reached_input = False
    async for snapshot in history:
        metadata = snapshot.metadata or {}
        turn_id = metadata.get("turn_id")
        if not isinstance(turn_id, str):
            continue
        if not reached_input:
            seen.add(turn_id)
            reached_input = turn_id == before and metadata.get("source") == "input"
            continue
        if turn_id not in seen:
            seen.add(turn_id)
            yield snapshot
