"""JD 同集合條目的純排列；不處理歸屬、型別或持久位置。"""

from uuid import UUID


def move_before(
    *, identity: UUID, ordered_ids: tuple[UUID, ...], before_id: UUID | None
) -> tuple[UUID, ...]:
    """重排已核對唯一的 ID；缺目標／錨點或自身錨點以 ValueError 拒絕。"""
    remaining = list(ordered_ids)
    remaining.remove(identity)
    index = len(remaining) if before_id is None else remaining.index(before_id)
    remaining.insert(index, identity)
    return tuple(remaining)
