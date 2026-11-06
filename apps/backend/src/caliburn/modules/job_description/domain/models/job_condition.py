"""JD 擁有的條件記載；分類與正文只由根控制修改。"""

from uuid import UUID

from pydantic import ConfigDict, Field, TypeAdapter, field_validator, validate_call

from caliburn.modules.job_description.domain.errors import InvalidTextError
from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind
from caliburn.shared.domain.base_entity import BaseEntity

_KIND_ADAPTER = TypeAdapter(ConditionKind)


class JobCondition(BaseEntity[UUID]):
    kind: ConditionKind = Field(frozen=True)
    text: str = Field(frozen=True)

    @field_validator("text")
    @classmethod
    def _require_text(cls, value: str) -> str:
        if not value.strip():
            raise InvalidTextError("正文不可為空白")
        return value

    @validate_call(config=ConfigDict(strict=True))
    def _update_text(self, *, text: str) -> bool:
        candidate = self._require_text(text)
        if candidate == self.text:
            return False
        object.__setattr__(self, "text", candidate)
        return True

    def _reclassify(self, *, kind: ConditionKind) -> bool:
        candidate = _KIND_ADAPTER.validate_python(kind, strict=True)
        if candidate == self.kind:
            return False
        object.__setattr__(self, "kind", candidate)
        return True
