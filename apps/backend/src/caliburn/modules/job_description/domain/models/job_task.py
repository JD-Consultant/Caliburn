"""JD 內部任務；局部變更只供 JobDescription 根委派。"""

from typing import Self
from uuid import UUID

from pydantic import (
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
    validate_call,
)

from caliburn.modules.job_description.domain.errors import (
    DuplicateIdentityError,
    InvalidTaskOrderError,
    InvalidTaskReferenceError,
    TaskOutcomeNotFoundError,
    TaskRequirementNotFoundError,
)
from caliburn.modules.job_description.domain.models.competency_level import (
    CompetencyLevel,
)
from caliburn.modules.job_description.domain.models.entry_name import EntryName
from caliburn.modules.job_description.domain.models.task_outcome import TaskOutcome
from caliburn.modules.job_description.domain.models.task_requirement import (
    TaskRequirement,
)
from caliburn.modules.job_description.domain.rules.collection_ordering import (
    move_before,
)
from caliburn.shared.domain.base_entity import BaseEntity

_UUID_ADAPTER = TypeAdapter(UUID)


class JobTask(BaseEntity[UUID]):
    """分類及 K/S 引用只保存 ID；完整關係與唯一性由 JD 根維護。"""

    job_description_id: UUID = Field(frozen=True)
    name: EntryName = Field(frozen=True)
    description: str | None = Field(default=None, frozen=True)
    duty_id: UUID | None = Field(default=None, frozen=True)
    competency_level: CompetencyLevel | None = Field(default=None, frozen=True)
    outcomes: tuple[TaskOutcome, ...] = Field(default=(), frozen=True)
    requirements: tuple[TaskRequirement, ...] = Field(default=(), frozen=True)
    knowledge_ids: tuple[UUID, ...] = Field(default=(), frozen=True)
    skill_ids: tuple[UUID, ...] = Field(default=(), frozen=True)

    @classmethod
    def create(
        cls,
        *,
        id: UUID,
        job_description_id: UUID,
        name: str,
        description: str | None = None,
        duty_id: UUID | None = None,
        competency_level: int | None = None,
        outcomes: tuple[TaskOutcome, ...] = (),
        requirements: tuple[TaskRequirement, ...] = (),
        knowledge_ids: tuple[UUID, ...] = (),
        skill_ids: tuple[UUID, ...] = (),
    ) -> Self:
        return cls(
            id=id,
            job_description_id=job_description_id,
            name=EntryName(value=name),
            description=description,
            duty_id=duty_id,
            competency_level=CompetencyLevel(value=competency_level)
            if competency_level is not None
            else None,
            outcomes=outcomes,
            requirements=requirements,
            knowledge_ids=knowledge_ids,
            skill_ids=skill_ids,
        )

    @model_validator(mode="after")
    def _validate_content_identities(self) -> JobTask:
        for kind, entries in (("成果", self.outcomes), ("工作要求", self.requirements)):
            identities = [entry.id for entry in entries]
            if len(identities) != len(set(identities)):
                raise DuplicateIdentityError(f"同一任務的{kind} ID 不可重複")
        return self

    @field_validator("knowledge_ids", "skill_ids")
    @classmethod
    def _deduplicate_references(cls, identities: tuple[UUID, ...]) -> tuple[UUID, ...]:
        return tuple(dict.fromkeys(identities))

    @validate_call(config=ConfigDict(strict=True))
    def _update_details(
        self,
        *,
        name: EntryName,
        description: str | None,
        competency_level: CompetencyLevel | None,
    ) -> bool:
        """原子更新本任務三個基本欄位，回報是否有實際變更。"""
        if (self.name, self.description, self.competency_level) == (
            name,
            description,
            competency_level,
        ):
            return False
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "competency_level", competency_level)
        return True

    def _add_outcome(self, *, outcome: TaskOutcome) -> None:
        """接收根建立並核對的成果。"""
        object.__setattr__(self, "outcomes", (*self.outcomes, outcome))

    def _reclassify(self, *, duty_id: UUID | None) -> bool:
        """變更已由 JD 根核對同 JD 的分類；None 明示為未分類。"""
        if duty_id == self.duty_id:
            return False
        object.__setattr__(self, "duty_id", duty_id)
        return True

    def _add_requirement(self, *, requirement: TaskRequirement) -> None:
        """接收根建立並核對的要求。"""
        object.__setattr__(self, "requirements", (*self.requirements, requirement))

    def get_outcome(self, *, outcome_id: UUID) -> TaskOutcome:
        """回本任務指定成果供當次操作使用；文字寫入仍經聚合方法。"""
        identity = _UUID_ADAPTER.validate_python(outcome_id, strict=True)
        for outcome in self.outcomes:
            if outcome.id == identity:
                return outcome
        raise TaskOutcomeNotFoundError("指定成果不存在於此任務")

    def get_requirement(self, *, requirement_id: UUID) -> TaskRequirement:
        """回本任務指定工作要求供當次操作使用；文字寫入仍經聚合方法。"""
        identity = _UUID_ADAPTER.validate_python(requirement_id, strict=True)
        for requirement in self.requirements:
            if requirement.id == identity:
                return requirement
        raise TaskRequirementNotFoundError("指定工作要求不存在於此任務")

    def _update_outcome(self, *, outcome_id: UUID, text: str) -> bool:
        return self.get_outcome(outcome_id=outcome_id)._update_text(text)

    def _update_requirement(self, *, requirement_id: UUID, text: str) -> bool:
        return self.get_requirement(requirement_id=requirement_id)._update_text(text)

    def _remove_outcome(self, *, outcome_id: UUID) -> None:
        """移除本任務指定成果；缺項拒絕，其餘 Entity 與相對次序不變。"""
        outcome = self.get_outcome(outcome_id=outcome_id)
        object.__setattr__(
            self,
            "outcomes",
            tuple(item for item in self.outcomes if item.id != outcome.id),
        )

    def _remove_requirement(self, *, requirement_id: UUID) -> None:
        """移除本任務指定要求；缺項拒絕，其餘 Entity 與相對次序不變。"""
        requirement = self.get_requirement(requirement_id=requirement_id)
        object.__setattr__(
            self,
            "requirements",
            tuple(item for item in self.requirements if item.id != requirement.id),
        )

    def _link_knowledge(self, *, knowledge_id: UUID) -> bool:
        """追加已由 JD 根核對的知識 ID；既有引用保持原位置。"""
        if knowledge_id in self.knowledge_ids:
            return False
        object.__setattr__(self, "knowledge_ids", (*self.knowledge_ids, knowledge_id))
        return True

    def _link_skill(self, *, skill_id: UUID) -> bool:
        """追加已由 JD 根核對的技能 ID；既有引用保持原位置。"""
        if skill_id in self.skill_ids:
            return False
        object.__setattr__(self, "skill_ids", (*self.skill_ids, skill_id))
        return True

    def _unlink_knowledge(self, *, knowledge_id: UUID) -> bool:
        """解除已由 JD 根核對的知識引用；其餘引用保持相對次序。"""
        if knowledge_id not in self.knowledge_ids:
            return False
        object.__setattr__(
            self,
            "knowledge_ids",
            tuple(item for item in self.knowledge_ids if item != knowledge_id),
        )
        return True

    def _unlink_skill(self, *, skill_id: UUID) -> bool:
        """解除已由 JD 根核對的技能引用；其餘引用保持相對次序。"""
        if skill_id not in self.skill_ids:
            return False
        object.__setattr__(
            self,
            "skill_ids",
            tuple(item for item in self.skill_ids if item != skill_id),
        )
        return True

    def _move_outcome(self, *, outcome_id: UUID, before_id: UUID | None) -> bool:
        outcome = self.get_outcome(outcome_id=outcome_id)
        identities = tuple(item.id for item in self.outcomes)
        ordered = _move_before(identities, outcome.id, before_id)
        if ordered == identities:
            return False
        entries = {item.id: item for item in self.outcomes}
        object.__setattr__(self, "outcomes", tuple(entries[key] for key in ordered))
        return True

    def _move_requirement(
        self, *, requirement_id: UUID, before_id: UUID | None
    ) -> bool:
        requirement = self.get_requirement(requirement_id=requirement_id)
        identities = tuple(item.id for item in self.requirements)
        ordered = _move_before(identities, requirement.id, before_id)
        if ordered == identities:
            return False
        entries = {item.id: item for item in self.requirements}
        object.__setattr__(self, "requirements", tuple(entries[key] for key in ordered))
        return True

    def _move_knowledge_reference(
        self, *, knowledge_id: UUID, before_id: UUID | None
    ) -> bool:
        if knowledge_id not in self.knowledge_ids:
            raise InvalidTaskReferenceError("指定知識不是此任務的有效引用")
        ordered = _move_before(self.knowledge_ids, knowledge_id, before_id)
        if ordered == self.knowledge_ids:
            return False
        object.__setattr__(self, "knowledge_ids", ordered)
        return True

    def _move_skill_reference(self, *, skill_id: UUID, before_id: UUID | None) -> bool:
        if skill_id not in self.skill_ids:
            raise InvalidTaskReferenceError("指定技能不是此任務的有效引用")
        ordered = _move_before(self.skill_ids, skill_id, before_id)
        if ordered == self.skill_ids:
            return False
        object.__setattr__(self, "skill_ids", ordered)
        return True


def _move_before(
    identities: tuple[UUID, ...], identity: UUID, before_id: UUID | None
) -> tuple[UUID, ...]:
    """目標已查得；驗證原始錨點並轉成 Task 的排序錯誤。"""
    if before_id is not None:
        _UUID_ADAPTER.validate_python(before_id, strict=True)
    try:
        return move_before(
            identity=identity, ordered_ids=identities, before_id=before_id
        )
    except ValueError as error:
        raise InvalidTaskOrderError("排序錨點須為同集合的其他項目") from error
