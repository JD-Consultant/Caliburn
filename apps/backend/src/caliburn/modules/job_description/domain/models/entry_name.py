"""條目名稱清洗、值比較及同類名稱集合的判重。"""

from collections.abc import Iterable

from pydantic import field_validator

from caliburn.modules.job_description.domain.errors import (
    DuplicateNameError,
    InvalidNameError,
)
from caliburn.shared.domain.base_domain_primitive import BaseDomainPrimitive


class EntryName(BaseDomainPrimitive[str]):
    @field_validator("value")
    @classmethod
    def _clean(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise InvalidNameError("條目名稱不可為空白")
        if len(cleaned) > 255:
            raise InvalidNameError("條目名稱不可超過 255 字元")
        return cleaned


def require_distinct_names(names: Iterable[EntryName]) -> None:
    values = tuple(names)
    if len(set(values)) != len(values):
        raise DuplicateNameError("同一名稱範圍不可重名")
