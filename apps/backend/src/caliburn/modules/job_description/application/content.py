"""JD 的不可變內容投影與共用值型別，不含保存結果或歷史座標。"""

from typing import Literal, Self
from uuid import UUID

from caliburn.modules.job_description.domain.models.citation import Citation
from caliburn.modules.job_description.domain.models.collaboration_entry import (
    CollaborationEntry,
)
from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind
from caliburn.modules.job_description.domain.models.duty import Duty
from caliburn.modules.job_description.domain.models.job_condition import JobCondition
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.modules.job_description.domain.models.job_task import JobTask
from caliburn.modules.job_description.domain.models.knowledge import Knowledge
from caliburn.modules.job_description.domain.models.skill import Skill
from caliburn.shared.application.base_dto import BaseDTO

type ItemKind = Literal[
    "job_description",
    "duty",
    "task",
    "outcome",
    "requirement",
    "knowledge",
    "skill",
    "collaboration",
    "condition",
    "citation",
]
type ContentValue = str | int | UUID | None
type CollectionKind = Literal[
    "duties",
    "tasks",
    "knowledge",
    "skills",
    "collaborations",
    "conditions",
    "outcomes",
    "requirements",
    "knowledge_ids",
    "skill_ids",
    "citations",
]


class DutyResult(BaseDTO):
    id: UUID
    name: str
    scope: str | None

    @classmethod
    def from_duty(cls, duty: Duty) -> Self:
        return cls(id=duty.id, name=duty.name.value, scope=duty.scope)


class KnowledgeResult(BaseDTO):
    id: UUID
    name: str
    description: str | None

    @classmethod
    def from_knowledge(cls, knowledge: Knowledge) -> Self:
        return cls(
            id=knowledge.id,
            name=knowledge.name.value,
            description=knowledge.description,
        )


class SkillResult(BaseDTO):
    id: UUID
    name: str
    description: str | None

    @classmethod
    def from_skill(cls, skill: Skill) -> Self:
        return cls(id=skill.id, name=skill.name.value, description=skill.description)


class TaskTextResult(BaseDTO):
    id: UUID
    text: str


class TaskResult(BaseDTO):
    id: UUID
    duty_id: UUID | None
    name: str
    description: str | None
    competency_level: int | None
    outcomes: tuple[TaskTextResult, ...]
    requirements: tuple[TaskTextResult, ...]
    knowledge_ids: tuple[UUID, ...]
    skill_ids: tuple[UUID, ...]

    @classmethod
    def from_task(cls, task: JobTask) -> Self:
        level = task.competency_level
        return cls(
            id=task.id,
            duty_id=task.duty_id,
            name=task.name.value,
            description=task.description,
            competency_level=level.value if level is not None else None,
            outcomes=tuple(
                TaskTextResult(id=outcome.id, text=outcome.text)
                for outcome in task.outcomes
            ),
            requirements=tuple(
                TaskTextResult(id=requirement.id, text=requirement.text)
                for requirement in task.requirements
            ),
            knowledge_ids=task.knowledge_ids,
            skill_ids=task.skill_ids,
        )


class CollaborationResult(BaseDTO):
    id: UUID
    collaborator_name: str
    scope: str | None

    @classmethod
    def from_collaboration(cls, collaboration: CollaborationEntry) -> Self:
        return cls(
            id=collaboration.id,
            collaborator_name=collaboration.collaborator_name,
            scope=collaboration.scope,
        )


class JobConditionResult(BaseDTO):
    id: UUID
    kind: ConditionKind
    text: str

    @classmethod
    def from_condition(cls, condition: JobCondition) -> Self:
        return cls(id=condition.id, kind=condition.kind, text=condition.text)


class JobDescriptionContent(BaseDTO):
    job_description_id: UUID
    workspace_id: UUID
    job_title: str | None
    organization_unit: str | None
    reports_to: str | None
    purpose: str | None
    baseline_competency_level: int | None
    duties: tuple[DutyResult, ...]
    tasks: tuple[TaskResult, ...]
    knowledge: tuple[KnowledgeResult, ...]
    skills: tuple[SkillResult, ...]
    collaborations: tuple[CollaborationResult, ...]
    conditions: tuple[JobConditionResult, ...]
    citations: tuple[Citation, ...] = ()

    @staticmethod
    def from_domain(job_description: JobDescription) -> JobDescriptionContent:
        level = job_description.baseline_competency_level
        return JobDescriptionContent(
            job_description_id=job_description.id,
            workspace_id=job_description.workspace_id,
            job_title=job_description.job_title,
            organization_unit=job_description.organization_unit,
            reports_to=job_description.reports_to,
            purpose=job_description.purpose,
            baseline_competency_level=level.value if level is not None else None,
            duties=tuple(DutyResult.from_duty(duty) for duty in job_description.duties),
            tasks=tuple(TaskResult.from_task(task) for task in job_description.tasks),
            knowledge=tuple(
                KnowledgeResult.from_knowledge(knowledge)
                for knowledge in job_description.knowledge
            ),
            skills=tuple(
                SkillResult.from_skill(skill) for skill in job_description.skills
            ),
            collaborations=tuple(
                CollaborationResult.from_collaboration(collaboration)
                for collaboration in job_description.collaborations
            ),
            conditions=tuple(
                JobConditionResult.from_condition(condition)
                for condition in job_description.conditions
            ),
            citations=job_description.citations,
        )
