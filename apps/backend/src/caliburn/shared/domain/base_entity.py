"""Entity 的固定身分與比較契約，ID 型別由具體 Entity 指定。"""

from collections.abc import Hashable

from pydantic import BaseModel, ConfigDict, Field


class BaseEntity[IdT: Hashable](BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        validate_assignment=True,
    )

    id: IdT = Field(frozen=True)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseEntity) or type(self) is not type(other):
            return NotImplemented

        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
