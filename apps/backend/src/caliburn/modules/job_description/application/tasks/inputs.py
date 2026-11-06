"""Task 新增及局部修改的不可變輸入，原文交給 Domain 驗證。"""

from typing import Self
from uuid import UUID

from pydantic import PositiveInt, model_validator

from caliburn.modules.job_description.application.citation_inputs import CitationChange
from caliburn.modules.job_description.application.errors import (
    InvalidJobDescriptionInputError,
)
from caliburn.modules.job_description.application.history_types import CorrelationId
from caliburn.modules.job_description.application.input_text import StorableText
from caliburn.shared.application.base_dto import BaseDTO


class ExistingDefinitionInput(BaseDTO):
    id: UUID


class NewDefinitionInput(BaseDTO):
    name: StorableText
    description: StorableText | None = None


class AddTaskInput(BaseDTO):
    job_description_id: UUID
    expected_version: PositiveInt
    citations: tuple[CitationChange, ...] = ()
    correlation_id: CorrelationId | None = None
    name: StorableText
    description: StorableText | None = None
    duty_id: UUID | None = None
    competency_level: int | None = None
    outcomes: tuple[StorableText, ...] = ()
    requirements: tuple[StorableText, ...] = ()
    knowledge: tuple[ExistingDefinitionInput | NewDefinitionInput, ...] = ()
    skills: tuple[ExistingDefinitionInput | NewDefinitionInput, ...] = ()


class AddOutcomeInput(BaseDTO):
    text: StorableText


class AddRequirementInput(BaseDTO):
    text: StorableText


class LinkKnowledgeInput(BaseDTO):
    id: UUID


class LinkSkillInput(BaseDTO):
    id: UUID


class CreateAndLinkKnowledgeInput(BaseDTO):
    name: StorableText
    description: StorableText | None = None


class CreateAndLinkSkillInput(BaseDTO):
    name: StorableText
    description: StorableText | None = None


class UpdateOutcomeInput(BaseDTO):
    id: UUID
    text: StorableText


class DeleteOutcomeInput(BaseDTO):
    id: UUID


class MoveOutcomeInput(BaseDTO):
    id: UUID
    before_id: UUID | None = None


class UpdateRequirementInput(BaseDTO):
    id: UUID
    text: StorableText


class DeleteRequirementInput(BaseDTO):
    id: UUID


class MoveRequirementInput(BaseDTO):
    id: UUID
    before_id: UUID | None = None


class UnlinkKnowledgeInput(BaseDTO):
    id: UUID


class UnlinkSkillInput(BaseDTO):
    id: UUID


class MoveKnowledgeReferenceInput(BaseDTO):
    id: UUID
    before_id: UUID | None = None


class MoveSkillReferenceInput(BaseDTO):
    id: UUID
    before_id: UUID | None = None


type TaskChange = (
    AddOutcomeInput
    | AddRequirementInput
    | LinkKnowledgeInput
    | LinkSkillInput
    | CreateAndLinkKnowledgeInput
    | CreateAndLinkSkillInput
    | UpdateOutcomeInput
    | DeleteOutcomeInput
    | MoveOutcomeInput
    | UpdateRequirementInput
    | DeleteRequirementInput
    | MoveRequirementInput
    | UnlinkKnowledgeInput
    | UnlinkSkillInput
    | MoveKnowledgeReferenceInput
    | MoveSkillReferenceInput
)


class TaskPlacementInput(BaseDTO):
    destination_duty_id: UUID | None
    before_id: UUID | None = None


class DutyScopeChange(BaseDTO):
    duty_id: UUID
    scope: StorableText | None


class UpdateTaskInput(BaseDTO):
    """以 model_fields_set 保留省略；None 只可清空描述與級別。"""

    job_description_id: UUID
    task_id: UUID
    expected_version: PositiveInt
    citations: tuple[CitationChange, ...] = ()
    correlation_id: CorrelationId | None = None
    name: StorableText | None = None
    description: StorableText | None = None
    competency_level: int | None = None
    placement: TaskPlacementInput | None = None
    changes: tuple[TaskChange, ...] = ()
    duty_scopes: tuple[DutyScopeChange, ...] = ()

    @model_validator(mode="after")
    def _require_patch(self) -> Self:
        if (
            not self.model_fields_set.intersection(
                {"name", "description", "competency_level", "placement"}
            )
            and not self.changes
            and not self.citations
        ):
            raise ValueError("至少須提供一個可修改欄位")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("任務名稱不可清空")
        if "placement" in self.model_fields_set and self.placement is None:
            raise ValueError("位置不可為空值")
        return self

    def validate_changes(self) -> None:
        """同一目標只接受不衝突的修改意圖；集合歸屬仍交由 Domain。"""
        if len({change.duty_id for change in self.duty_scopes}) != len(
            self.duty_scopes
        ):
            raise InvalidJobDescriptionInputError("同一職責範圍不可重複修改")
        seen: dict[tuple[str, UUID], set[str]] = {}
        for change in self.changes:
            if isinstance(
                change, (UpdateOutcomeInput, DeleteOutcomeInput, MoveOutcomeInput)
            ):
                target = ("outcome", change.id)
            elif isinstance(
                change,
                (UpdateRequirementInput, DeleteRequirementInput, MoveRequirementInput),
            ):
                target = ("requirement", change.id)
            elif isinstance(
                change,
                (LinkKnowledgeInput, UnlinkKnowledgeInput, MoveKnowledgeReferenceInput),
            ):
                target = ("knowledge", change.id)
            elif isinstance(
                change, (LinkSkillInput, UnlinkSkillInput, MoveSkillReferenceInput)
            ):
                target = ("skill", change.id)
            else:
                continue

            if isinstance(change, (UpdateOutcomeInput, UpdateRequirementInput)):
                operation = "update"
            elif isinstance(change, (DeleteOutcomeInput, DeleteRequirementInput)):
                operation = "delete"
            elif isinstance(change, (LinkKnowledgeInput, LinkSkillInput)):
                operation = "link"
            elif isinstance(change, (UnlinkKnowledgeInput, UnlinkSkillInput)):
                operation = "unlink"
            else:
                operation = "move"

            previous = seen.setdefault(target, set())
            if (
                operation in previous
                or "delete" in previous
                or (operation == "delete" and previous)
                or (operation == "unlink" and previous.intersection({"link", "move"}))
                or (operation in {"link", "move"} and "unlink" in previous)
            ):
                raise InvalidJobDescriptionInputError(
                    "同一目標的修改不可重複或互相矛盾"
                )
            previous.add(operation)
