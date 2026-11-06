"""JD 明確 ORM 欄位差異保存；分段 flush 維持 FK。"""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.shared.infrastructure.persistence.orm_base import OrmBase

from .citation_rows import TARGET_COLUMNS, citation_to_row
from .content_mapping import ContentRows
from .orm_models import (
    CollaborationEntryRow,
    DutyRow,
    JobConditionRow,
    JobTaskRow,
    KnowledgeRow,
    SkillRow,
    TaskKnowledgeRow,
    TaskOutcomeRow,
    TaskRequirementRow,
    TaskSkillRow,
)

_SWAPPABLE = ", ".join(
    (
        "uq_duties_name",
        "uq_job_tasks_name",
        "uq_knowledge_name",
        "uq_skills_name",
        "uq_duties_position",
        "uq_job_tasks_position",
        "uq_knowledge_position",
        "uq_skills_position",
        "uq_task_outcomes_position",
        "uq_task_requirements_position",
        "uq_task_knowledge_position",
        "uq_task_skills_position",
        "uq_collaboration_entries_position",
        "uq_job_conditions_position",
    )
)


def save_content(
    session: Session, saved: ContentRows, job_description: JobDescription
) -> None:
    """只複製已變欄位；交換名稱／位置時延後對應唯一約束。"""
    wanted = _desired_content(saved, job_description)
    with session.no_autoflush:
        session.execute(text(f"SET CONSTRAINTS {_SWAPPABLE} DEFERRED"))
        for name in ("job_title", "organization_unit", "reports_to", "purpose"):
            value = getattr(job_description, name)
            if getattr(saved.job_description_row, name) != value:
                setattr(saved.job_description_row, name, value)
        level = job_description.baseline_competency_level
        saved.job_description_row.baseline_competency_level = (
            level.value if level else None
        )

        # 先刪必要的子列，維持定義與引用的外鍵次序。
        _remove(session, saved.citations, wanted.citations, ("id",))
        _remove(session, saved.outcomes, wanted.outcomes, ("id",))
        _remove(session, saved.requirements, wanted.requirements, ("id",))
        _remove(
            session,
            saved.knowledge_links,
            wanted.knowledge_links,
            ("task_id", "knowledge_id"),
        )
        _remove(session, saved.skill_links, wanted.skill_links, ("task_id", "skill_id"))
        session.flush()

        # 先建立定義及 Duty，Task 接著才能引用新身分；舊定義延後刪除。
        _sync(
            session,
            saved.duties,
            wanted.duties,
            ("id",),
            ("name", "scope", "position"),
        )
        _sync(
            session,
            saved.knowledge,
            wanted.knowledge,
            ("id",),
            ("name", "description", "position"),
        )
        _sync(
            session,
            saved.skills,
            wanted.skills,
            ("id",),
            ("name", "description", "position"),
        )
        session.flush()
        _sync(
            session,
            saved.tasks,
            wanted.tasks,
            ("id",),
            (
                "duty_id",
                "name",
                "description",
                "competency_level",
                "position",
            ),
        )
        session.flush()

        _sync(
            session,
            saved.outcomes,
            wanted.outcomes,
            ("id",),
            ("task_id", "text", "position"),
        )
        _sync(
            session,
            saved.requirements,
            wanted.requirements,
            ("id",),
            ("task_id", "text", "position"),
        )
        _sync(
            session,
            saved.knowledge_links,
            wanted.knowledge_links,
            ("task_id", "knowledge_id"),
            ("position",),
        )
        _sync(
            session,
            saved.skill_links,
            wanted.skill_links,
            ("task_id", "skill_id"),
            ("position",),
        )
        _remove(session, saved.collaborations, wanted.collaborations, ("id",))
        _remove(session, saved.conditions, wanted.conditions, ("id",))
        _sync(
            session,
            saved.collaborations,
            wanted.collaborations,
            ("id",),
            ("collaborator_name", "scope", "position"),
        )
        _sync(
            session,
            saved.conditions,
            wanted.conditions,
            ("id",),
            ("kind", "text", "position"),
        )
        session.flush()

        # Task 移動／子內容更新完成後，才移除已不在目標圖的 Task 與定義。
        _sync(
            session,
            saved.citations,
            wanted.citations,
            ("id",),
            (
                *(column for _, column, _ in TARGET_COLUMNS),
                "message_id",
                "published_version",
                "item_id",
                "jd_changed",
                "position",
            ),
        )
        session.flush()
        _remove(session, saved.tasks, wanted.tasks, ("id",))
        session.flush()
        _remove(session, saved.duties, wanted.duties, ("id",))
        _remove(session, saved.knowledge, wanted.knowledge, ("id",))
        _remove(session, saved.skills, wanted.skills, ("id",))
        session.flush()
        session.execute(text(f"SET CONSTRAINTS {_SWAPPABLE} IMMEDIATE"))


def _key(row: OrmBase, names: tuple[str, ...]) -> tuple[object, ...]:
    return tuple(getattr(row, name) for name in names)


def _remove[T: OrmBase](
    session: Session, saved: tuple[T, ...], wanted: tuple[T, ...], keys: tuple[str, ...]
) -> None:
    retained = {_key(row, keys) for row in wanted}
    for row in saved:
        if _key(row, keys) not in retained:
            session.delete(row)


def _sync[T: OrmBase](
    session: Session,
    saved: tuple[T, ...],
    wanted: tuple[T, ...],
    keys: tuple[str, ...],
    fields: tuple[str, ...],
) -> None:
    existing = {_key(row, keys): row for row in saved}
    for candidate in wanted:
        row = existing.get(_key(candidate, keys))
        if row is None:
            session.add(candidate)
        else:
            for field in fields:
                value = getattr(candidate, field)
                if getattr(row, field) != value:
                    setattr(row, field, value)


def _positions(identities: tuple[UUID, ...], saved: dict[UUID, int]) -> dict[UUID, int]:
    """重用存續成員的稀疏槽；新增／跨組轉入接目的組末，不改未變列。"""
    retained = tuple(identity for identity in identities if identity in saved)
    slots = sorted(saved[identity] for identity in retained)
    next_position = max(saved.values(), default=-1) + 1
    for identity in identities:
        if identity not in saved:
            slots.append(next_position)
            next_position += 1
    return dict(zip(identities, slots, strict=True))


def _desired_content(
    saved: ContentRows, job_description: JobDescription
) -> ContentRows:
    duties = _positions(
        tuple(x.id for x in job_description.duties),
        {x.id: x.position for x in saved.duties},
    )
    knowledge = _positions(
        tuple(x.id for x in job_description.knowledge),
        {x.id: x.position for x in saved.knowledge},
    )
    skills = _positions(
        tuple(x.id for x in job_description.skills),
        {x.id: x.position for x in saved.skills},
    )
    collaborations = _positions(
        tuple(x.id for x in job_description.collaborations),
        {x.id: x.position for x in saved.collaborations},
    )
    saved_task_groups: defaultdict[UUID | None, dict[UUID, int]] = defaultdict(dict)
    task_groups: defaultdict[UUID | None, list[UUID]] = defaultdict(list)
    for task_row in saved.tasks:
        saved_task_groups[task_row.duty_id][task_row.id] = task_row.position
    for task in job_description.tasks:
        task_groups[task.duty_id].append(task.id)
    tasks: dict[UUID, int] = {}
    for duty_id, ordered_ids in task_groups.items():
        tasks.update(_positions(tuple(ordered_ids), saved_task_groups[duty_id]))
    saved_condition_groups: defaultdict[str, dict[UUID, int]] = defaultdict(dict)
    condition_groups: defaultdict[str, list[UUID]] = defaultdict(list)
    for condition_row in saved.conditions:
        saved_condition_groups[condition_row.kind][condition_row.id] = (
            condition_row.position
        )
    for condition in job_description.conditions:
        condition_groups[condition.kind.value].append(condition.id)
    conditions: dict[UUID, int] = {}
    for kind, ordered_ids in condition_groups.items():
        conditions.update(_positions(tuple(ordered_ids), saved_condition_groups[kind]))
    saved_outcomes: defaultdict[UUID, dict[UUID, int]] = defaultdict(dict)
    saved_requirements: defaultdict[UUID, dict[UUID, int]] = defaultdict(dict)
    saved_knowledge_links: defaultdict[UUID, dict[UUID, int]] = defaultdict(dict)
    saved_skill_links: defaultdict[UUID, dict[UUID, int]] = defaultdict(dict)
    for outcome_row in saved.outcomes:
        saved_outcomes[outcome_row.task_id][outcome_row.id] = outcome_row.position
    for requirement_row in saved.requirements:
        saved_requirements[requirement_row.task_id][requirement_row.id] = (
            requirement_row.position
        )
    for knowledge_link in saved.knowledge_links:
        saved_knowledge_links[knowledge_link.task_id][knowledge_link.knowledge_id] = (
            knowledge_link.position
        )
    for skill_link in saved.skill_links:
        saved_skill_links[skill_link.task_id][skill_link.skill_id] = skill_link.position
    outcomes: list[TaskOutcomeRow] = []
    requirements: list[TaskRequirementRow] = []
    knowledge_links: list[TaskKnowledgeRow] = []
    skill_links: list[TaskSkillRow] = []
    for task in job_description.tasks:
        outcome_positions = _positions(
            tuple(x.id for x in task.outcomes),
            saved_outcomes[task.id],
        )
        requirement_positions = _positions(
            tuple(x.id for x in task.requirements),
            saved_requirements[task.id],
        )
        knowledge_positions = _positions(
            task.knowledge_ids,
            saved_knowledge_links[task.id],
        )
        skill_positions = _positions(
            task.skill_ids,
            saved_skill_links[task.id],
        )
        outcomes.extend(
            TaskOutcomeRow(
                id=x.id, task_id=task.id, text=x.text, position=outcome_positions[x.id]
            )
            for x in task.outcomes
        )
        requirements.extend(
            TaskRequirementRow(
                id=x.id,
                task_id=task.id,
                text=x.text,
                position=requirement_positions[x.id],
            )
            for x in task.requirements
        )
        knowledge_links.extend(
            TaskKnowledgeRow(
                task_id=task.id,
                knowledge_id=x,
                job_description_id=job_description.id,
                position=knowledge_positions[x],
            )
            for x in task.knowledge_ids
        )
        skill_links.extend(
            TaskSkillRow(
                task_id=task.id,
                skill_id=x,
                job_description_id=job_description.id,
                position=skill_positions[x],
            )
            for x in task.skill_ids
        )
    return ContentRows(
        job_description_row=saved.job_description_row,
        duties=tuple(
            DutyRow(
                id=x.id,
                job_description_id=job_description.id,
                name=x.name.value,
                scope=x.scope,
                position=duties[x.id],
            )
            for x in job_description.duties
        ),
        tasks=tuple(
            JobTaskRow(
                id=x.id,
                job_description_id=job_description.id,
                duty_id=x.duty_id,
                name=x.name.value,
                description=x.description,
                competency_level=x.competency_level.value
                if x.competency_level
                else None,
                position=tasks[x.id],
            )
            for x in job_description.tasks
        ),
        knowledge=tuple(
            KnowledgeRow(
                id=x.id,
                job_description_id=job_description.id,
                name=x.name.value,
                description=x.description,
                position=knowledge[x.id],
            )
            for x in job_description.knowledge
        ),
        skills=tuple(
            SkillRow(
                id=x.id,
                job_description_id=job_description.id,
                name=x.name.value,
                description=x.description,
                position=skills[x.id],
            )
            for x in job_description.skills
        ),
        collaborations=tuple(
            CollaborationEntryRow(
                id=x.id,
                job_description_id=job_description.id,
                collaborator_name=x.collaborator_name,
                scope=x.scope,
                position=collaborations[x.id],
            )
            for x in job_description.collaborations
        ),
        conditions=tuple(
            JobConditionRow(
                id=x.id,
                job_description_id=job_description.id,
                kind=x.kind.value,
                text=x.text,
                position=conditions[x.id],
            )
            for x in job_description.conditions
        ),
        outcomes=tuple(outcomes),
        requirements=tuple(requirements),
        knowledge_links=tuple(knowledge_links),
        skill_links=tuple(skill_links),
        citations=tuple(
            citation_to_row(
                citation, job_description_id=job_description.id, position=position
            )
            for position, citation in enumerate(job_description.citations)
        ),
    )
