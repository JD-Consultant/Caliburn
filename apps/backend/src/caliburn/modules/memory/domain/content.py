"""Memory 項目的原值文字。"""

from pydantic import ConfigDict, field_validator

from caliburn.modules.memory.domain.errors import InvalidMemoryContentError
from caliburn.shared.domain.base_value_object import BaseValueObject


class MemoryContent(BaseValueObject):
    model_config = ConfigDict(hide_input_in_errors=True)

    title: str
    description: str
    body: str

    @field_validator("title", "description", "body")
    @classmethod
    def _require_storable_text(cls, text: str) -> str:
        if not text.strip():
            raise InvalidMemoryContentError("Memory content must not be blank")
        if "\x00" in text or any("\ud800" <= char <= "\udfff" for char in text):
            raise InvalidMemoryContentError(
                "Memory content contains invalid characters"
            )
        return text
