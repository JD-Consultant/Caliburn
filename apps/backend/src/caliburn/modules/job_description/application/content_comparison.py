"""JD 內容比較視圖：身分欄位及各業務群組的順序，共供 no-op 與 Diff。"""

from dataclasses import dataclass
from uuid import UUID

from caliburn.modules.job_description.application.content import (
    CollectionKind,
    ContentValue,
    ItemKind,
    JobDescriptionContent,
)
from caliburn.modules.job_description.domain.models.citation import InterviewReference
from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind

type ItemKey = tuple[ItemKind, UUID]
type CollectionKey = tuple[CollectionKind, UUID, UUID | str | None]


@dataclass(frozen=True)
class ContentIndex:
    items: dict[ItemKey, dict[str, ContentValue]]
    collections: dict[CollectionKey, tuple[UUID, ...]]


def index_content(content: JobDescriptionContent) -> ContentIndex:
    """固定 JD 結構的投影，不反射任意物件或產生可執行 patch。"""
    jd_id = content.job_description_id
    items: dict[ItemKey, dict[str, ContentValue]] = {
        ("job_description", jd_id): {
            "workspace_id": content.workspace_id,
            "job_title": content.job_title,
            "organization_unit": content.organization_unit,
            "reports_to": content.reports_to,
            "purpose": content.purpose,
            "baseline_competency_level": content.baseline_competency_level,
        }
    }
    collections: dict[CollectionKey, tuple[UUID, ...]] = {
        ("duties", jd_id, None): tuple(duty.id for duty in content.duties),
        ("knowledge", jd_id, None): tuple(
            knowledge.id for knowledge in content.knowledge
        ),
        ("skills", jd_id, None): tuple(skill.id for skill in content.skills),
        ("collaborations", jd_id, None): tuple(
            collaboration.id for collaboration in content.collaborations
        ),
    }
    for duty in content.duties:
        items[("duty", duty.id)] = {"name": duty.name, "scope": duty.scope}
    for knowledge in content.knowledge:
        items[("knowledge", knowledge.id)] = {
            "name": knowledge.name,
            "description": knowledge.description,
        }
    for skill in content.skills:
        items[("skill", skill.id)] = {
            "name": skill.name,
            "description": skill.description,
        }
    for collaboration in content.collaborations:
        items[("collaboration", collaboration.id)] = {
            "collaborator_name": collaboration.collaborator_name,
            "scope": collaboration.scope,
        }
    for condition in content.conditions:
        items[("condition", condition.id)] = {
            "kind": condition.kind,
            "text": condition.text,
        }
    for kind in ConditionKind:
        collections[("conditions", jd_id, kind)] = tuple(
            condition.id for condition in content.conditions if condition.kind == kind
        )
    task_groups: dict[UUID | None, list[UUID]] = {}
    for task in content.tasks:
        task_groups.setdefault(task.duty_id, []).append(task.id)
        items[("task", task.id)] = {
            "duty_id": task.duty_id,
            "name": task.name,
            "description": task.description,
            "competency_level": task.competency_level,
        }
        for outcome in task.outcomes:
            items[("outcome", outcome.id)] = {"text": outcome.text}
        for requirement in task.requirements:
            items[("requirement", requirement.id)] = {"text": requirement.text}
        collections[("outcomes", task.id, None)] = tuple(
            outcome.id for outcome in task.outcomes
        )
        collections[("requirements", task.id, None)] = tuple(
            requirement.id for requirement in task.requirements
        )
        collections[("knowledge_ids", task.id, None)] = task.knowledge_ids
        collections[("skill_ids", task.id, None)] = task.skill_ids
    for duty_id, task_ids in task_groups.items():
        collections[("tasks", jd_id, duty_id)] = tuple(task_ids)
    for citation in content.citations:
        source = citation.source
        items[("citation", citation.id)] = {
            "target_kind": citation.target_kind,
            "target_id": citation.target_id,
            "source_kind": source.kind,
            "workspace_id": source.workspace_id,
            "message_id": source.message_id
            if isinstance(source, InterviewReference)
            else None,
            "published_version": None
            if isinstance(source, InterviewReference)
            else source.published_version,
            "item_id": None
            if isinstance(source, InterviewReference)
            else source.item_id,
            "jd_changed": int(citation.jd_changed),
        }
    collections[("citations", jd_id, None)] = tuple(x.id for x in content.citations)
    # 空集合的存在不是正文變動；新增／刪除空父項仍由 items 表達。
    return ContentIndex(items, {key: ids for key, ids in collections.items() if ids})


def same_content(before: JobDescriptionContent, after: JobDescriptionContent) -> bool:
    return index_content(before) == index_content(after)
