"""Task 擁有的工作要求，文字編修由聚合根控制。"""

from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, validate_call

from caliburn.modules.job_description.domain.errors import InvalidTextError
from caliburn.shared.domain.base_entity import BaseEntity


class TaskRequirement(BaseEntity[UUID]):
    text: str = Field(frozen=True)

    @field_validator("text")
    @classmethod
    def _require_text(cls, value: str) -> str:
        if not value.strip():
            raise InvalidTextError("正文不可為空白")
        return value

    @validate_call(config=ConfigDict(strict=True))
    def _update_text(self, text: str) -> bool:
        value = self._require_text(text)
        if value == self.text:
            return False
        object.__setattr__(self, "text", value)
        return True
