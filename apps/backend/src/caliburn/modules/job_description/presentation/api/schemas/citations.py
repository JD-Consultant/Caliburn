"""來源引用的 HTTP 值型別；正式 UUID 不依賴模型短碼。"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from caliburn.modules.job_description.application.citation_inputs import (
    AddCitationInput,
    ConfirmCitationInput,
    RemoveCitationInput,
)
from caliburn.modules.job_description.application.citations import CitationResult
from caliburn.modules.job_description.domain.models.citation import CitationTargetKind
from caliburn.modules.job_description.presentation.api.schemas.common import (
    ExpectedVersion,
    RequestModel,
    ResponseModel,
    WriteRequest,
)
from caliburn.shared.presentation.api.values import HttpId


class InterviewReferenceRequest(RequestModel):
    kind: Literal["interview"]
    workspace_id: HttpId
    message_id: HttpId


class MemoryReferenceRequest(RequestModel):
    kind: Literal["memory"]
    workspace_id: HttpId
    published_version: ExpectedVersion
    item_id: HttpId


type SourceReferenceRequest = Annotated[
    InterviewReferenceRequest | MemoryReferenceRequest, Field(discriminator="kind")
]


class AddCitationRequest(RequestModel):
    action: Literal["add"]
    source: SourceReferenceRequest

    def to_application(self) -> AddCitationInput:
        return AddCitationInput.model_validate(self.model_dump())


class RemoveCitationRequest(RequestModel):
    action: Literal["remove"]
    citation_id: HttpId

    def to_application(self) -> RemoveCitationInput:
        return RemoveCitationInput.model_validate(self.model_dump())


class ConfirmCitationRequest(RequestModel):
    action: Literal["confirm"]
    citation_id: HttpId
    published_version: ExpectedVersion | None = None

    def to_application(self) -> ConfirmCitationInput:
        return ConfirmCitationInput.model_validate(self.model_dump())


type CitationChangeRequest = Annotated[
    AddCitationRequest | RemoveCitationRequest | ConfirmCitationRequest,
    Field(discriminator="action"),
]
type CitationRequests = Annotated[
    tuple[CitationChangeRequest, ...], Field(strict=False)
]


class ChangeCitationsRequest(WriteRequest):
    target_kind: CitationTargetKind
    target_id: HttpId
    changes: Annotated[CitationRequests, Field(min_length=1)]


class InterviewReferenceResponse(ResponseModel):
    kind: Literal["interview"]
    workspace_id: UUID
    message_id: UUID


class MemoryReferenceResponse(ResponseModel):
    kind: Literal["memory"]
    workspace_id: UUID
    published_version: ExpectedVersion
    item_id: UUID


type SourceReferenceResponse = Annotated[
    InterviewReferenceResponse | MemoryReferenceResponse, Field(discriminator="kind")
]


class CitationResponse(ResponseModel):
    id: UUID
    target_kind: CitationTargetKind
    target_id: UUID
    source: SourceReferenceResponse
    jd_changed: bool


class CitationSourceResponse(ResponseModel):
    source: SourceReferenceResponse
    availability: Literal["available", "unavailable"]
    title: str | None
    text: str | None
    changed_version: int | None
    item_kind: Literal["situation", "understanding"] | None


class MemoryContentResponse(ResponseModel):
    title: str
    description: str
    body: str


class MemoryCitationItemResponse(ResponseModel):
    id: UUID
    workspace_id: UUID
    kind: Literal["situation", "understanding"]
    content: MemoryContentResponse
    changed_version: int
    interview_message_ids: tuple[UUID, ...] = ()
    situation_ids: tuple[UUID, ...] = ()


class MemoryCitationContentResponse(ResponseModel):
    item: MemoryCitationItemResponse
    situations: tuple[MemoryCitationItemResponse, ...]


class CitationComparisonResponse(ResponseModel):
    before: MemoryCitationContentResponse
    after: MemoryCitationContentResponse | None
    source_changed: bool


class CitationDetailsResponse(ResponseModel):
    citation: CitationResponse
    source: CitationSourceResponse
    comparison: CitationComparisonResponse | None
    source_changed: bool | None
    needs_recheck: bool | None

    @classmethod
    def from_result(cls, result: CitationResult) -> CitationDetailsResponse:
        return cls.model_validate(result)
