"""JD 內部職責分類；由根維護跨條目規則。"""

from typing import Self
from uuid import UUID

from pydantic import ConfigDict, Field, validate_call

from caliburn.modules.job_description.domain.models.entry_name import EntryName
from caliburn.shared.domain.base_entity import BaseEntity


class Duty(BaseEntity[UUID]):
    job_description_id: UUID = Field(frozen=True)
    name: EntryName = Field(frozen=True)
    scope: str | None = Field(default=None, frozen=True)

    @classmethod
    def create(
        cls,
        *,
        id: UUID,
        job_description_id: UUID,
        name: str,
        scope: str | None = None,
    ) -> Self:
        return cls(
            id=id,
            job_description_id=job_description_id,
            name=EntryName(value=name),
            scope=scope,
        )

    @validate_call(config=ConfigDict(strict=True))
    def _update_details(self, *, name: EntryName, scope: str | None) -> bool:
        if (self.name, self.scope) == (name, scope):
            return False
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "scope", scope)
        return True
