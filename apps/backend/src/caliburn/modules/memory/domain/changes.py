"""依穩定身分比較目前稿與固定發布圖。"""

from uuid import UUID

from pydantic import ConfigDict

from caliburn.modules.memory.domain.errors import InvalidMemorySnapshotError
from caliburn.modules.memory.domain.items import (
    MemoryItem,
    MemoryKind,
    same_memory_item,
)
from caliburn.modules.memory.domain.snapshot import MemorySnapshot
from caliburn.modules.memory.domain.work_memory import WorkMemory
from caliburn.shared.domain.base_value_object import BaseValueObject


class MemoryChange(BaseValueObject):
    model_config = ConfigDict(hide_input_in_errors=True)

    item_id: UUID
    kind: MemoryKind
    before: MemoryItem | None
    after: MemoryItem | None


def describe_changes(
    baseline: MemorySnapshot | None, current: WorkMemory | MemorySnapshot
) -> tuple[MemoryChange, ...]:
    if baseline is not None and baseline.workspace_id != current.workspace_id:
        raise InvalidMemorySnapshotError(
            "Cannot compare Memory from different workspaces"
        )
    before_by_id = (
        {} if baseline is None else {item.id: item for item in baseline.items}
    )
    after_by_id = {item.id: item for item in current.items}
    changes = []
    for item_id in sorted(before_by_id.keys() | after_by_id.keys()):
        before = before_by_id.get(item_id)
        after = after_by_id.get(item_id)
        if before is not None and after is not None:
            if before.kind != after.kind:
                raise InvalidMemorySnapshotError("Memory item kind changed")
            if same_memory_item(before, after):
                continue
        item = after if after is not None else before_by_id[item_id]
        changes.append(
            MemoryChange(item_id=item_id, kind=item.kind, before=before, after=after)
        )
    return tuple(changes)
