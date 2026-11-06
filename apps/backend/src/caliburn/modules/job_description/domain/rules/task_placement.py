"""依目的組身分決定 Task 相對位置，不處理持久位置或版本。"""

from dataclasses import dataclass
from uuid import UUID

from pydantic import TypeAdapter

from caliburn.modules.job_description.domain.errors import InvalidTaskOrderError

_UUID_ADAPTER = TypeAdapter(UUID)


@dataclass(frozen=True, slots=True)
class TaskPlacement:
    task_ids: tuple[UUID, ...]
    changed: bool


def plan_task_placement(
    *, task_id: UUID, destination_task_ids: tuple[UUID, ...], before_id: UUID | None
) -> TaskPlacement:
    """依目的組的完整順序驗錨點；目標不在組內即代表跨組插入。"""
    _UUID_ADAPTER.validate_python(task_id, strict=True)
    if before_id is not None:
        _UUID_ADAPTER.validate_python(before_id, strict=True)
    if before_id == task_id or (
        before_id is not None and before_id not in destination_task_ids
    ):
        raise InvalidTaskOrderError("排序錨點須為目的組的其他 Task")
    remaining = tuple(item for item in destination_task_ids if item != task_id)
    index = len(remaining) if before_id is None else remaining.index(before_id)
    ordered = (*remaining[:index], task_id, *remaining[index:])
    return TaskPlacement(task_ids=ordered, changed=ordered != destination_task_ids)
