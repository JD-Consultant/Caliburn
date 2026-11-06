"""同一版本的完整發布內容圖。"""

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from caliburn.modules.memory.domain.errors import InvalidMemorySnapshotError
from caliburn.modules.memory.domain.items import MemoryItem, validate_memory_items
from caliburn.shared.domain.base_value_object import BaseValueObject

MAX_MEMORY_VERSION = 9_007_199_254_740_991


class MemorySnapshot(BaseValueObject):
    model_config = ConfigDict(hide_input_in_errors=True)

    workspace_id: UUID
    version: int = Field(gt=0, le=MAX_MEMORY_VERSION)
    covered_through_message_id: UUID
    published_at: datetime
    items: tuple[MemoryItem, ...]

    @model_validator(mode="after")
    def _validate_snapshot(self) -> Self:
        if self.published_at.utcoffset() is None:
            raise InvalidMemorySnapshotError("Memory publication time must be aware")
        validate_memory_items(
            workspace_id=self.workspace_id, version=self.version, items=self.items
        )
        return self
