"""JD 歷史、比較及恢復的 HTTP 契約。"""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, ConfigDict

from caliburn.modules.job_description.application.content import (
    CollectionKind,
    ContentValue,
    ItemKind,
)
from caliburn.modules.job_description.application.history.operations import (
    RestoreJobDescriptionInput,
)
from caliburn.modules.job_description.presentation.api.schemas.common import (
    CorrelationIdInput,
    ExpectedVersion,
    ResponseModel,
    WriteRequest,
)
from caliburn.modules.job_description.presentation.api.schemas.content import (
    JobDescriptionContentResponse,
)


class RestoreJobDescriptionRequest(WriteRequest):
    """以目前版本為前置，將目標歷史內容保存成下一版。"""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"expected_version": 10, "target_version": 3}]}
    )

    target_version: ExpectedVersion
    reverts_correlation_id: CorrelationIdInput | None = None

    def to_application(self, *, job_description_id: UUID) -> RestoreJobDescriptionInput:
        return RestoreJobDescriptionInput(
            job_description_id=job_description_id,
            target_version=self.target_version,
            expected_version=self.expected_version,
            correlation_id=self.correlation_id,
            reverts_correlation_id=self.reverts_correlation_id,
        )


class HistoryEntryResponse(ResponseModel):
    job_description_id: UUID
    version: ExpectedVersion
    kind: Literal["created", "edited", "restored"]
    recorded_at: AwareDatetime
    correlation_id: str | None
    reverts_correlation_id: str | None
    restored_from_version: ExpectedVersion | None


class HistoryPageResponse(ResponseModel):
    items: tuple[HistoryEntryResponse, ...]
    next_page_token: str | None


class HistoryResponse(ResponseModel):
    content: JobDescriptionContentResponse
    entry: HistoryEntryResponse


class FieldDifferenceResponse(ResponseModel):
    field: str
    before: ContentValue
    after: ContentValue


class ItemDifferenceResponse(ResponseModel):
    kind: ItemKind
    id: UUID
    change: Literal["added", "removed", "modified"]
    fields: tuple[FieldDifferenceResponse, ...]


class CollectionDifferenceResponse(ResponseModel):
    collection: CollectionKind
    owner_id: UUID
    group: UUID | str | None
    before_ids: tuple[UUID, ...]
    after_ids: tuple[UUID, ...]


class JobDescriptionDifferenceResponse(ResponseModel):
    job_description_id: UUID
    before_version: ExpectedVersion
    after_version: ExpectedVersion
    items: tuple[ItemDifferenceResponse, ...]
    collections: tuple[CollectionDifferenceResponse, ...]
