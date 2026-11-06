"""目前整理的固定來源窗口、階段及最新失敗。"""

from typing import Literal, Self
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from caliburn.modules.memory.domain.errors import InvalidMemorySourceError
from caliburn.modules.memory.domain.snapshot import MAX_MEMORY_VERSION
from caliburn.shared.domain.base_value_object import BaseValueObject

type MemoryPhase = Literal["situation", "understanding"]
type MemoryFailureReason = Literal[
    "invalid_completion", "invalid_source_window", "analysis_limit"
]


class MemorySourceWindow(BaseValueObject):
    model_config = ConfigDict(hide_input_in_errors=True)

    workspace_id: UUID
    through_message_id: UUID
    message_ids: tuple[UUID, ...]
    required_message_ids: tuple[UUID, ...]

    @model_validator(mode="after")
    def _validate_source_window(self) -> Self:
        messages = set(self.message_ids)
        required = set(self.required_message_ids)
        if len(messages) != len(self.message_ids) or len(required) != len(
            self.required_message_ids
        ):
            raise InvalidMemorySourceError("Memory source window repeats a message")
        if self.through_message_id not in messages or not required.issubset(messages):
            raise InvalidMemorySourceError("Memory source window is incomplete")
        return self


class MemoryAnalysis(BaseValueObject):
    model_config = ConfigDict(hide_input_in_errors=True)

    analysis_id: UUID
    phase: MemoryPhase
    base_published_version: int | None = Field(gt=0, le=MAX_MEMORY_VERSION)
    source_window: MemorySourceWindow


class MemoryFailure(BaseValueObject):
    analysis_id: UUID
    reason: MemoryFailureReason
    formal_message_ids: tuple[UUID, ...]
