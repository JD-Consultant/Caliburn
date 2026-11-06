"""JD 模型的引用支持範圍；排序與歸屬不代表語意內容改變。"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from caliburn.modules.job_description.domain.models.citation import CitationTargetKind
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)

type Target = tuple[CitationTargetKind, UUID]


@dataclass(frozen=True)
class CitationSupport:
    content: dict[Target, tuple[object, ...]]
    citation_ids: frozenset[UUID]


def capture_citation_support(root: JobDescription) -> CitationSupport:
    content: dict[Target, tuple[object, ...]] = {
        ("job_description", root.id): (
            root.job_title,
            root.organization_unit,
            root.reports_to,
            root.purpose,
            root.baseline_competency_level,
        )
    }
    for duty in root.duties:
        content[("duty", duty.id)] = (duty.name, duty.scope)
    for knowledge in root.knowledge:
        content[("knowledge", knowledge.id)] = (knowledge.name, knowledge.description)
    for skill in root.skills:
        content[("skill", skill.id)] = (skill.name, skill.description)
    for collaboration in root.collaborations:
        content[("collaboration", collaboration.id)] = (
            collaboration.collaborator_name,
            collaboration.scope,
        )
    for condition in root.conditions:
        content[("condition", condition.id)] = (condition.kind, condition.text)
    for task in root.tasks:
        content[("task", task.id)] = (
            task.name,
            task.description,
            task.competency_level,
            tuple(sorted((item.id, item.text) for item in task.outcomes)),
            tuple(sorted((item.id, item.text) for item in task.requirements)),
            tuple(
                (identity, content[("knowledge", identity)])
                for identity in sorted(task.knowledge_ids)
            ),
            tuple(
                (identity, content[("skill", identity)])
                for identity in sorted(task.skill_ids)
            ),
        )
    return CitationSupport(content, frozenset(x.id for x in root.citations))


def apply_citation_review(
    root: JobDescription,
    *,
    before: CitationSupport,
    actor: Literal["human", "consultant"],
    confirmed_ids: frozenset[UUID] = frozenset(),
) -> None:
    after = capture_citation_support(root)
    for citation in root.citations:
        key = (citation.target_kind, citation.target_id)
        if citation.id not in before.citation_ids or citation.id in confirmed_ids:
            continue
        if before.content.get(key) != after.content.get(key):
            root.set_citation_review(
                citation_id=citation.id, jd_changed=actor == "human"
            )
