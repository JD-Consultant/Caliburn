"""JD 擁有的協作記載；只由根控制修改。"""

from uuid import UUID

from pydantic import Field, field_validator

from caliburn.modules.job_description.domain.errors import (
    InvalidCollaborationNameError,
)
from caliburn.shared.domain.base_entity import BaseEntity


class CollaborationEntry(BaseEntity[UUID]):
    collaborator_name: str = Field(frozen=True)
    scope: str | None = Field(default=None, frozen=True)

    @field_validator("collaborator_name")
    @classmethod
    def _require_collaborator(cls, value: str) -> str:
        if not value.strip():
            raise InvalidCollaborationNameError("協作對象不可為空白")
        return value

    def _update(self, *, collaborator_name: str, scope: str | None) -> bool:
        candidate = CollaborationEntry(
            id=self.id, collaborator_name=collaborator_name, scope=scope
        )
        if (self.collaborator_name, self.scope) == (
            candidate.collaborator_name,
            candidate.scope,
        ):
            return False
        object.__setattr__(self, "collaborator_name", candidate.collaborator_name)
        object.__setattr__(self, "scope", candidate.scope)
        return True
