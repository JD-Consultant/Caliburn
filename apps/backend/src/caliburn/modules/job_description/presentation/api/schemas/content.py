"""JD 內容的獨立 HTTP 契約；完整回覆由已提交 DTO 投影。"""

from typing import Annotated
from uuid import UUID

from pydantic import ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema

from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind
from caliburn.modules.job_description.presentation.api.schemas.citations import (
    CitationRequests,
    CitationResponse,
)
from caliburn.modules.job_description.presentation.api.schemas.common import (
    CompetencyLevelInput,
    CorrelationIdInput,
    ExpectedVersion,
    NameInput,
    NonBlankText,
    PatchRequest,
    PlacementRequest,
    RequestModel,
    ResponseModel,
    StorableText,
    WriteRequest,
)

ConditionKindInput = Annotated[ConditionKind, Field(strict=False)]


class CreateJobDescriptionRequest(RequestModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{}]})

    correlation_id: CorrelationIdInput | None = None


class UpdateJobDescriptionRequest(PatchRequest):
    """只送要修改的欄位；省略表示保留，null 表示清空選填欄位。"""

    patch_fields = (
        "job_title",
        "organization_unit",
        "reports_to",
        "purpose",
        "baseline_competency_level",
        "citations",
    )

    job_title: StorableText | None = None
    organization_unit: StorableText | None = None
    reports_to: StorableText | None = None
    purpose: StorableText | None = None
    baseline_competency_level: CompetencyLevelInput | None = None
    citations: CitationRequests = ()


class AddDutyRequest(WriteRequest):
    citations: CitationRequests = ()
    name: NameInput
    scope: StorableText | None = None


class UpdateDutyRequest(PatchRequest):
    """內容與排序共同提交；省略 placement 保留原順序。"""

    patch_fields = ("name", "scope", "placement", "citations")
    citations: CitationRequests = ()
    nonnullable_patch_fields = ("name", "placement")

    name: NameInput | SkipJsonSchema[None] = None
    scope: StorableText | None = None
    placement: PlacementRequest | SkipJsonSchema[None] = None


class AddKnowledgeRequest(WriteRequest):
    citations: CitationRequests = ()
    name: NameInput
    description: StorableText | None = None


class UpdateKnowledgeRequest(PatchRequest):
    """定義與目錄排序共同提交；不改變 Task 的引用順序。"""

    patch_fields = ("name", "description", "placement", "citations")
    citations: CitationRequests = ()
    nonnullable_patch_fields = ("name", "placement")

    name: NameInput | SkipJsonSchema[None] = None
    description: StorableText | None = None
    placement: PlacementRequest | SkipJsonSchema[None] = None


class AddSkillRequest(WriteRequest):
    citations: CitationRequests = ()
    name: NameInput
    description: StorableText | None = None


class UpdateSkillRequest(PatchRequest):
    """定義與目錄排序共同提交；不改變 Task 的引用順序。"""

    patch_fields = ("name", "description", "placement", "citations")
    citations: CitationRequests = ()
    nonnullable_patch_fields = ("name", "placement")

    name: NameInput | SkipJsonSchema[None] = None
    description: StorableText | None = None
    placement: PlacementRequest | SkipJsonSchema[None] = None


class AddCollaborationRequest(WriteRequest):
    citations: CitationRequests = ()
    collaborator_name: NonBlankText
    scope: StorableText | None = None


class UpdateCollaborationRequest(PatchRequest):
    """內容與排序共同提交；省略 placement 保留原順序。"""

    patch_fields = ("collaborator_name", "scope", "placement", "citations")
    citations: CitationRequests = ()
    nonnullable_patch_fields = ("collaborator_name", "placement")

    collaborator_name: NonBlankText | SkipJsonSchema[None] = None
    scope: StorableText | None = None
    placement: PlacementRequest | SkipJsonSchema[None] = None


class AddConditionRequest(WriteRequest):
    citations: CitationRequests = ()
    kind: ConditionKindInput
    text: NonBlankText


class UpdateConditionRequest(PatchRequest):
    """文字、分類及排序共同提交；跨分類未指定位置時追加至新分類末尾。"""

    patch_fields = ("text", "kind", "placement", "citations")
    citations: CitationRequests = ()
    nonnullable_patch_fields = ("text", "kind", "placement")

    text: NonBlankText | SkipJsonSchema[None] = None
    kind: ConditionKindInput | SkipJsonSchema[None] = None
    placement: PlacementRequest | SkipJsonSchema[None] = None


class DutyResponse(ResponseModel):
    id: UUID
    name: str
    scope: str | None


class KnowledgeResponse(ResponseModel):
    id: UUID
    name: str
    description: str | None


class SkillResponse(ResponseModel):
    id: UUID
    name: str
    description: str | None


class TaskTextResponse(ResponseModel):
    id: UUID
    text: str


class TaskResponse(ResponseModel):
    id: UUID
    duty_id: UUID | None
    name: str
    description: str | None
    competency_level: CompetencyLevelInput | None
    outcomes: tuple[TaskTextResponse, ...]
    requirements: tuple[TaskTextResponse, ...]
    knowledge_ids: tuple[UUID, ...]
    skill_ids: tuple[UUID, ...]


class CollaborationResponse(ResponseModel):
    id: UUID
    collaborator_name: str
    scope: str | None


class ConditionResponse(ResponseModel):
    id: UUID
    kind: ConditionKind
    text: str


class JobDescriptionContentResponse(ResponseModel):
    job_description_id: UUID
    workspace_id: UUID
    job_title: str | None
    organization_unit: str | None
    reports_to: str | None
    purpose: str | None
    baseline_competency_level: CompetencyLevelInput | None
    duties: tuple[DutyResponse, ...]
    tasks: tuple[TaskResponse, ...]
    knowledge: tuple[KnowledgeResponse, ...]
    skills: tuple[SkillResponse, ...]
    collaborations: tuple[CollaborationResponse, ...]
    conditions: tuple[ConditionResponse, ...]
    citations: tuple[CitationResponse, ...] = ()


class JobDescriptionResponse(JobDescriptionContentResponse):
    version: ExpectedVersion
