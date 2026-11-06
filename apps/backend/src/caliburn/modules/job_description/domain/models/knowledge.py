"""JD 共用知識定義；由根維護跨條目規則。"""

from typing import Self
from uuid import UUID

from pydantic import ConfigDict, Field, validate_call

from caliburn.modules.job_description.domain.models.entry_name import EntryName
from caliburn.shared.domain.base_entity import BaseEntity


class Knowledge(BaseEntity[UUID]):
    job_description_id: UUID = Field(frozen=True)
    name: EntryName = Field(frozen=True)
    description: str | None = Field(default=None, frozen=True)

    @classmethod
    def create(
        cls,
        *,
        id: UUID,
        job_description_id: UUID,
        name: str,
        description: str | None = None,
    ) -> Self:
        return cls(
            id=id,
            job_description_id=job_description_id,
            name=EntryName(value=name),
            description=description,
        )

    @validate_call(config=ConfigDict(strict=True))
    def _update_details(self, *, name: EntryName, description: str | None) -> bool:
        if (self.name, self.description) == (name, description):
            return False
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)
        return True
