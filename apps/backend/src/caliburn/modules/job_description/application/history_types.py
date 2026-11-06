"""JD 單一版本與持久追查資料；不表示上層編修資格。"""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, Field, PositiveInt, model_validator

from caliburn.modules.job_description.application.errors import (
    InvalidHistoryPaginationError,
)
from caliburn.modules.job_description.application.input_text import (
    require_storable_text,
)
from caliburn.shared.application.base_dto import BaseDTO

DEFAULT_HISTORY_PAGE_SIZE = 20


def normalize_history_page_size(value: int) -> int:
    if type(value) is not int or value < 0:
        raise InvalidHistoryPaginationError("歷史頁面大小須為非負整數")
    return min(value or DEFAULT_HISTORY_PAGE_SIZE, 100)


def require_correlation_id(value: str) -> str:
    require_storable_text(value)
    if not value.strip():
        raise ValueError("來源識別不可全為空白")
    return value


CorrelationId = Annotated[
    str, Field(min_length=1, max_length=200), AfterValidator(require_correlation_id)
]


class RestoreMetadata(BaseDTO):
    target_version: PositiveInt
    reverts_correlation_id: CorrelationId | None = None


class HistoryEntry(BaseDTO):
    job_description_id: UUID
    version: PositiveInt
    kind: Literal["created", "edited", "restored"]
    recorded_at: AwareDatetime
    restored_from_version: PositiveInt | None = None
    correlation_id: CorrelationId | None = None
    reverts_correlation_id: CorrelationId | None = None

    @model_validator(mode="after")
    def _validate_restore(self) -> Self:
        if (self.kind == "restored") != (self.restored_from_version is not None):
            raise ValueError("只有恢復紀錄必須提供來源版本")
        if self.kind != "restored" and self.reverts_correlation_id is not None:
            raise ValueError("只有恢復紀錄可提供撤銷關聯")
        return self


class HistoryPage(BaseDTO):
    items: tuple[HistoryEntry, ...]
    next_page_token: str | None = None
