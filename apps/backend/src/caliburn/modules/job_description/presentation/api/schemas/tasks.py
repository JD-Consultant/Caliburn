"""任務 HTTP 輸入；tagged union 在邊界轉為 Application 的具名輸入。"""

from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from caliburn.modules.job_description.application.tasks import inputs as task_inputs
from caliburn.modules.job_description.application.tasks.inputs import (
    AddTaskInput,
    ExistingDefinitionInput,
    NewDefinitionInput,
    UpdateTaskInput,
)
from caliburn.modules.job_description.presentation.api.schemas.citations import (
    CitationRequests,
)
from caliburn.modules.job_description.presentation.api.schemas.common import (
    CompetencyLevelInput,
    NameInput,
    NonBlankText,
    PatchRequest,
    RequestModel,
    StorableText,
    WriteRequest,
)
from caliburn.shared.presentation.api.values import HttpId


class ExistingDefinitionRequest(RequestModel):
    kind: Literal["existing"]
    id: HttpId

    def to_application(self) -> ExistingDefinitionInput:
        return ExistingDefinitionInput(id=self.id)


class NewDefinitionRequest(RequestModel):
    kind: Literal["new"]
    name: NameInput
    description: StorableText | None = None

    def to_application(self) -> NewDefinitionInput:
        return NewDefinitionInput(name=self.name, description=self.description)


DefinitionRequest = Annotated[
    ExistingDefinitionRequest | NewDefinitionRequest, Field(discriminator="kind")
]


class AddTaskRequest(WriteRequest):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "expected_version": 2,
                    "name": "維護設備",
                    "outcomes": ["設備可正常運作"],
                    "requirements": ["依維護程序檢查"],
                    "knowledge": [
                        {
                            "kind": "existing",
                            "id": "00112233-4455-6677-8899-aabbccddeeff",
                        }
                    ],
                    "skills": [{"kind": "new", "name": "故障排除"}],
                }
            ]
        }
    )

    name: NameInput
    description: StorableText | None = None
    duty_id: HttpId | None = None
    competency_level: CompetencyLevelInput | None = None
    outcomes: list[NonBlankText] = Field(default_factory=list)
    requirements: list[NonBlankText] = Field(default_factory=list)
    knowledge: list[DefinitionRequest] = Field(default_factory=list)
    skills: list[DefinitionRequest] = Field(default_factory=list)
    citations: CitationRequests = ()

    def to_application(self, job_description_id: UUID) -> AddTaskInput:
        return AddTaskInput(
            citations=tuple(change.to_application() for change in self.citations),
            job_description_id=job_description_id,
            expected_version=self.expected_version,
            correlation_id=self.correlation_id,
            name=self.name,
            description=self.description,
            duty_id=self.duty_id,
            competency_level=self.competency_level,
            outcomes=tuple(self.outcomes),
            requirements=tuple(self.requirements),
            knowledge=tuple(item.to_application() for item in self.knowledge),
            skills=tuple(item.to_application() for item in self.skills),
        )


class TaskPlacementRequest(RequestModel):
    destination_duty_id: HttpId | None
    before_id: HttpId | None = None


class AddOutcomeChange(RequestModel):
    action: Literal["add_outcome"]
    text: NonBlankText

    def to_application(self) -> task_inputs.AddOutcomeInput:
        return task_inputs.AddOutcomeInput(text=self.text)


class AddRequirementChange(RequestModel):
    action: Literal["add_requirement"]
    text: NonBlankText

    def to_application(self) -> task_inputs.AddRequirementInput:
        return task_inputs.AddRequirementInput(text=self.text)


class LinkKnowledgeChange(RequestModel):
    action: Literal["link_knowledge"]
    id: HttpId

    def to_application(self) -> task_inputs.LinkKnowledgeInput:
        return task_inputs.LinkKnowledgeInput(id=self.id)


class LinkSkillChange(RequestModel):
    action: Literal["link_skill"]
    id: HttpId

    def to_application(self) -> task_inputs.LinkSkillInput:
        return task_inputs.LinkSkillInput(id=self.id)


class CreateAndLinkKnowledgeChange(RequestModel):
    action: Literal["create_and_link_knowledge"]
    name: NameInput
    description: StorableText | None = None

    def to_application(self) -> task_inputs.CreateAndLinkKnowledgeInput:
        return task_inputs.CreateAndLinkKnowledgeInput(
            name=self.name, description=self.description
        )


class CreateAndLinkSkillChange(RequestModel):
    action: Literal["create_and_link_skill"]
    name: NameInput
    description: StorableText | None = None

    def to_application(self) -> task_inputs.CreateAndLinkSkillInput:
        return task_inputs.CreateAndLinkSkillInput(
            name=self.name, description=self.description
        )


class UpdateOutcomeChange(RequestModel):
    action: Literal["update_outcome"]
    id: HttpId
    text: NonBlankText

    def to_application(self) -> task_inputs.UpdateOutcomeInput:
        return task_inputs.UpdateOutcomeInput(id=self.id, text=self.text)


class DeleteOutcomeChange(RequestModel):
    action: Literal["delete_outcome"]
    id: HttpId

    def to_application(self) -> task_inputs.DeleteOutcomeInput:
        return task_inputs.DeleteOutcomeInput(id=self.id)


class MoveOutcomeChange(RequestModel):
    action: Literal["move_outcome"]
    id: HttpId
    before_id: HttpId | None = None

    def to_application(self) -> task_inputs.MoveOutcomeInput:
        return task_inputs.MoveOutcomeInput(id=self.id, before_id=self.before_id)


class UpdateRequirementChange(RequestModel):
    action: Literal["update_requirement"]
    id: HttpId
    text: NonBlankText

    def to_application(self) -> task_inputs.UpdateRequirementInput:
        return task_inputs.UpdateRequirementInput(id=self.id, text=self.text)


class DeleteRequirementChange(RequestModel):
    action: Literal["delete_requirement"]
    id: HttpId

    def to_application(self) -> task_inputs.DeleteRequirementInput:
        return task_inputs.DeleteRequirementInput(id=self.id)


class MoveRequirementChange(RequestModel):
    action: Literal["move_requirement"]
    id: HttpId
    before_id: HttpId | None = None

    def to_application(self) -> task_inputs.MoveRequirementInput:
        return task_inputs.MoveRequirementInput(id=self.id, before_id=self.before_id)


class UnlinkKnowledgeChange(RequestModel):
    action: Literal["unlink_knowledge"]
    id: HttpId

    def to_application(self) -> task_inputs.UnlinkKnowledgeInput:
        return task_inputs.UnlinkKnowledgeInput(id=self.id)


class UnlinkSkillChange(RequestModel):
    action: Literal["unlink_skill"]
    id: HttpId

    def to_application(self) -> task_inputs.UnlinkSkillInput:
        return task_inputs.UnlinkSkillInput(id=self.id)


class MoveKnowledgeReferenceChange(RequestModel):
    action: Literal["move_knowledge_reference"]
    id: HttpId
    before_id: HttpId | None = None

    def to_application(self) -> task_inputs.MoveKnowledgeReferenceInput:
        return task_inputs.MoveKnowledgeReferenceInput(
            id=self.id, before_id=self.before_id
        )


class MoveSkillReferenceChange(RequestModel):
    action: Literal["move_skill_reference"]
    id: HttpId
    before_id: HttpId | None = None

    def to_application(self) -> task_inputs.MoveSkillReferenceInput:
        return task_inputs.MoveSkillReferenceInput(id=self.id, before_id=self.before_id)


TaskChangeRequest = Annotated[
    AddOutcomeChange
    | AddRequirementChange
    | LinkKnowledgeChange
    | LinkSkillChange
    | CreateAndLinkKnowledgeChange
    | CreateAndLinkSkillChange
    | UpdateOutcomeChange
    | DeleteOutcomeChange
    | MoveOutcomeChange
    | UpdateRequirementChange
    | DeleteRequirementChange
    | MoveRequirementChange
    | UnlinkKnowledgeChange
    | UnlinkSkillChange
    | MoveKnowledgeReferenceChange
    | MoveSkillReferenceChange,
    Field(discriminator="action"),
]


def _task_patch_json_schema(schema: dict[str, Any]) -> None:
    schema["anyOf"] = [
        {"required": [field]}
        for field in ("name", "description", "competency_level", "placement")
    ] + [
        {
            "required": ["changes"],
            "properties": {"changes": {"type": "array", "minItems": 1}},
        },
        {
            "required": ["citations"],
            "properties": {"citations": {"type": "array", "minItems": 1}},
        },
    ]
    for field in ("name", "placement"):
        schema["properties"][field].pop("default", None)


class UpdateTaskRequest(PatchRequest):
    model_config = ConfigDict(json_schema_extra=_task_patch_json_schema)
    patch_fields = (
        "name",
        "description",
        "competency_level",
        "placement",
        "changes",
        "citations",
    )
    nonnullable_patch_fields = ("name", "placement")

    name: NameInput | SkipJsonSchema[None] = None
    description: StorableText | None = None
    competency_level: CompetencyLevelInput | None = None
    placement: TaskPlacementRequest | SkipJsonSchema[None] = None
    citations: CitationRequests = ()
    changes: list[TaskChangeRequest] = Field(
        default_factory=list,
        description="依序套用的非遞迴內容修改。空陣列須與其他修改欄位並用。",
    )

    @model_validator(mode="after")
    def _require_task_patch(self) -> Self:
        if (
            not self.model_fields_set.intersection(
                {"name", "description", "competency_level", "placement"}
            )
            and not self.changes
            and not self.citations
        ):
            raise ValueError("至少須提供一個修改意圖")
        return self

    def to_application(
        self, job_description_id: UUID, task_id: UUID
    ) -> UpdateTaskInput:
        return UpdateTaskInput.model_validate(
            {
                "job_description_id": job_description_id,
                "task_id": task_id,
                **self.model_dump(exclude_unset=True, exclude={"changes"}),
                "changes": tuple(item.to_application() for item in self.changes),
            }
        )
