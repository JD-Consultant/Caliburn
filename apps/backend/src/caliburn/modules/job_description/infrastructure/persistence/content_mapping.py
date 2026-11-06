"""JD 的具體關聯式內容圖及 Domain 映射，只映射目前內容。"""

from collections import defaultdict
from collections.abc import Hashable, Iterable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from caliburn.modules.job_description.domain.models.collaboration_entry import (
    CollaborationEntry,
)
from caliburn.modules.job_description.domain.models.competency_level import (
    CompetencyLevel,
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
from caliburn.modules.job_description.domain.models.task_outcome import TaskOutcome
from caliburn.modules.job_description.domain.models.task_requirement import (
    TaskRequirement,
)

from .citation_rows import CitationRow, citation_from_row
from .orm_models import (
    CollaborationEntryRow,
    DutyRow,
    JobConditionRow,
    JobDescriptionRow,
    JobTaskRow,
    KnowledgeRow,
    SkillRow,
    TaskKnowledgeRow,
    TaskOutcomeRow,
    TaskRequirementRow,
    TaskSkillRow,
)


@dataclass
class ContentRows:
    job_description_row: JobDescriptionRow
    duties: tuple[DutyRow, ...] = ()
    tasks: tuple[JobTaskRow, ...] = ()
    knowledge: tuple[KnowledgeRow, ...] = ()
    skills: tuple[SkillRow, ...] = ()
    outcomes: tuple[TaskOutcomeRow, ...] = ()
    requirements: tuple[TaskRequirementRow, ...] = ()
    knowledge_links: tuple[TaskKnowledgeRow, ...] = ()
    skill_links: tuple[TaskSkillRow, ...] = ()
    collaborations: tuple[CollaborationEntryRow, ...] = ()
    conditions: tuple[JobConditionRow, ...] = ()
    citations: tuple[CitationRow, ...] = ()

    def to_domain(self) -> JobDescription:
        _validate_structure(self)
        job_description_row = self.job_description_row
        return JobDescription(
            id=job_description_row.id,
            workspace_id=job_description_row.workspace_id,
            job_title=job_description_row.job_title,
            organization_unit=job_description_row.organization_unit,
            reports_to=job_description_row.reports_to,
            purpose=job_description_row.purpose,
            baseline_competency_level=_level(
                job_description_row.baseline_competency_level
            ),
            duties=tuple(
                Duty.create(
                    id=row.id,
                    job_description_id=row.job_description_id,
                    name=row.name,
                    scope=row.scope,
                )
                for row in sorted(self.duties, key=lambda row: row.position)
            ),
            tasks=_map_tasks(self),
            knowledge=tuple(
                Knowledge.create(
                    id=row.id,
                    job_description_id=row.job_description_id,
                    name=row.name,
                    description=row.description,
                )
                for row in sorted(self.knowledge, key=lambda row: row.position)
            ),
            skills=tuple(
                Skill.create(
                    id=row.id,
                    job_description_id=row.job_description_id,
                    name=row.name,
                    description=row.description,
                )
                for row in sorted(self.skills, key=lambda row: row.position)
            ),
            collaborations=tuple(
                CollaborationEntry(
                    id=row.id, collaborator_name=row.collaborator_name, scope=row.scope
                )
                for row in sorted(self.collaborations, key=lambda row: row.position)
            ),
            conditions=tuple(
                JobCondition(id=row.id, kind=ConditionKind(row.kind), text=row.text)
                for row in sorted(self.conditions, key=lambda row: row.position)
            ),
            citations=tuple(
                citation_from_row(row)
                for row in sorted(self.citations, key=lambda row: row.position)
            ),
        )


def _map_tasks(rows: ContentRows) -> tuple[JobTask, ...]:
    outcomes: defaultdict[UUID, list[TaskOutcome]] = defaultdict(list)
    requirements: defaultdict[UUID, list[TaskRequirement]] = defaultdict(list)
    knowledge: defaultdict[UUID, list[UUID]] = defaultdict(list)
    skills: defaultdict[UUID, list[UUID]] = defaultdict(list)
    for outcome in sorted(rows.outcomes, key=lambda row: row.position):
        outcomes[outcome.task_id].append(TaskOutcome(id=outcome.id, text=outcome.text))
    for requirement in sorted(rows.requirements, key=lambda row: row.position):
        requirements[requirement.task_id].append(
            TaskRequirement(id=requirement.id, text=requirement.text)
        )
    for knowledge_link in sorted(rows.knowledge_links, key=lambda row: row.position):
        knowledge[knowledge_link.task_id].append(knowledge_link.knowledge_id)
    for skill_link in sorted(rows.skill_links, key=lambda row: row.position):
        skills[skill_link.task_id].append(skill_link.skill_id)
    return tuple(
        JobTask.create(
            id=task.id,
            job_description_id=task.job_description_id,
            duty_id=task.duty_id,
            name=task.name,
            description=task.description,
            competency_level=task.competency_level,
            outcomes=tuple(outcomes[task.id]),
            requirements=tuple(requirements[task.id]),
            knowledge_ids=tuple(knowledge[task.id]),
            skill_ids=tuple(skills[task.id]),
        )
        for task in sorted(rows.tasks, key=lambda row: row.position)
    )


def _validate_structure(rows: ContentRows) -> None:
    """讀取時拒絕不完整結構，不丟掉孤兒或猜測重複位置的邏輯順序。"""
    owners = (
        *(row.job_description_id for row in rows.duties),
        *(row.job_description_id for row in rows.tasks),
        *(row.job_description_id for row in rows.knowledge),
        *(row.job_description_id for row in rows.skills),
        *(row.job_description_id for row in rows.knowledge_links),
        *(row.job_description_id for row in rows.skill_links),
        *(row.job_description_id for row in rows.collaborations),
        *(row.job_description_id for row in rows.conditions),
        *(row.job_description_id for row in rows.citations),
    )
    if any(owner != rows.job_description_row.id for owner in owners):
        raise ValueError("內容列不屬於此 JD")
    task_ids = {row.id for row in rows.tasks}
    parents = (
        *(row.task_id for row in rows.outcomes),
        *(row.task_id for row in rows.requirements),
        *(row.task_id for row in rows.knowledge_links),
        *(row.task_id for row in rows.skill_links),
    )
    if any(parent not in task_ids for parent in parents):
        raise ValueError("內容列缺少所屬 Task")
    _require_positions((None, row.position) for row in rows.duties)
    _require_positions((None, row.position) for row in rows.knowledge)
    _require_positions((None, row.position) for row in rows.skills)
    _require_positions((None, row.position) for row in rows.collaborations)
    _require_positions((row.duty_id, row.position) for row in rows.tasks)
    _require_positions((row.kind, row.position) for row in rows.conditions)
    _require_positions((row.task_id, row.position) for row in rows.outcomes)
    _require_positions((row.task_id, row.position) for row in rows.requirements)
    _require_positions((row.task_id, row.position) for row in rows.knowledge_links)
    _require_positions((row.task_id, row.position) for row in rows.skill_links)
    _require_positions((None, row.position) for row in rows.citations)


def _require_positions(entries: Iterable[tuple[Hashable, int]]) -> None:
    positions: set[tuple[Hashable, int]] = set()
    for group, position in entries:
        if type(position) is not int or position < 0 or (group, position) in positions:
            raise ValueError("集合位置無法確定唯一合法順序")
        positions.add((group, position))


def _level(value: int | None) -> CompetencyLevel | None:
    return CompetencyLevel(value=value) if value is not None else None


def load_current_content(
    session: Session, job_description_row: JobDescriptionRow
) -> ContentRows:
    """根寫鎖由呼叫者先取得；此函式本身也可在唯讀快照內使用。"""
    jd_id = job_description_row.id
    tasks = tuple(
        session.scalars(
            select(JobTaskRow).where(JobTaskRow.job_description_id == jd_id)
        )
    )
    task_ids = tuple(row.id for row in tasks)
    return ContentRows(
        job_description_row=job_description_row,
        duties=tuple(
            session.scalars(select(DutyRow).where(DutyRow.job_description_id == jd_id))
        ),
        tasks=tasks,
        knowledge=tuple(
            session.scalars(
                select(KnowledgeRow).where(KnowledgeRow.job_description_id == jd_id)
            )
        ),
        skills=tuple(
            session.scalars(
                select(SkillRow).where(SkillRow.job_description_id == jd_id)
            )
        ),
        outcomes=tuple(
            session.scalars(
                select(TaskOutcomeRow).where(TaskOutcomeRow.task_id.in_(task_ids))
            )
        ),
        requirements=tuple(
            session.scalars(
                select(TaskRequirementRow).where(
                    TaskRequirementRow.task_id.in_(task_ids)
                )
            )
        ),
        knowledge_links=tuple(
            session.scalars(
                select(TaskKnowledgeRow).where(
                    TaskKnowledgeRow.job_description_id == jd_id,
                    TaskKnowledgeRow.task_id.in_(task_ids),
                )
            )
        ),
        skill_links=tuple(
            session.scalars(
                select(TaskSkillRow).where(
                    TaskSkillRow.job_description_id == jd_id,
                    TaskSkillRow.task_id.in_(task_ids),
                )
            )
        ),
        collaborations=tuple(
            session.scalars(
                select(CollaborationEntryRow).where(
                    CollaborationEntryRow.job_description_id == jd_id
                )
            )
        ),
        conditions=tuple(
            session.scalars(
                select(JobConditionRow).where(
                    JobConditionRow.job_description_id == jd_id
                )
            )
        ),
        citations=tuple(
            session.scalars(
                select(CitationRow).where(CitationRow.job_description_id == jd_id)
            )
        ),
    )
