"""JD 模型視圖：只轉換正式身分欄位，正文逐字保留。"""

from collections.abc import Mapping
from typing import Any, Literal
from uuid import UUID

from caliburn.modules.job_description.application.citations import CitationResult
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.domain.models.citation import InterviewReference
from caliburn.modules.model_references.contracts import ReferenceTarget, ResourceKind

type ReadView = Literal["map", "item", "full"]


def reference_targets(snapshot: JobDescriptionResult) -> tuple[ReferenceTarget, ...]:
    targets = [ReferenceTarget("duty", item.id) for item in snapshot.duties]
    for item in snapshot.tasks:
        targets.append(ReferenceTarget("task", item.id))
        targets.extend(ReferenceTarget("outcome", text.id) for text in item.outcomes)
        targets.extend(
            ReferenceTarget("requirement", text.id) for text in item.requirements
        )
    targets.extend(ReferenceTarget("knowledge", item.id) for item in snapshot.knowledge)
    targets.extend(ReferenceTarget("skill", item.id) for item in snapshot.skills)
    targets.extend(
        ReferenceTarget("collaboration", item.id) for item in snapshot.collaborations
    )
    targets.extend(
        ReferenceTarget("condition", item.id) for item in snapshot.conditions
    )
    for citation in snapshot.citations:
        targets.append(ReferenceTarget("citation", citation.id))
        if isinstance(citation.source, InterviewReference):
            targets.append(ReferenceTarget("message", citation.source.message_id))
    return tuple(targets)


def project_jd(
    snapshot: JobDescriptionResult,
    references: Mapping[ReferenceTarget, str],
    *,
    view: ReadView,
    target: ReferenceTarget | None = None,
    citation_results: Mapping[UUID, CitationResult] | None = None,
) -> dict[str, Any]:
    def ref(kind: ResourceKind, item_id: UUID) -> str:
        return references[ReferenceTarget(kind, item_id)]

    profile: dict[str, Any] = {
        "version": snapshot.version,
        "job_title": snapshot.job_title,
        "organization_unit": snapshot.organization_unit,
        "reports_to": snapshot.reports_to,
        "purpose": snapshot.purpose,
        "baseline_competency_level": snapshot.baseline_competency_level,
    }
    entries: dict[ReferenceTarget, dict[str, Any]] = {}

    def entry(
        resource_kind: ResourceKind, item_id: UUID, **fields: object
    ) -> dict[str, Any]:
        value = {"read_ref": ref(resource_kind, item_id), **fields}
        entries[ReferenceTarget(resource_kind, item_id)] = value
        return value

    duties = [entry("duty", x.id, name=x.name, scope=x.scope) for x in snapshot.duties]
    tasks = []
    for task in snapshot.tasks:
        outcomes = [entry("outcome", x.id, text=x.text) for x in task.outcomes]
        requirements = [
            entry("requirement", x.id, text=x.text) for x in task.requirements
        ]
        task_view = entry(
            "task",
            task.id,
            name=task.name,
            description=task.description,
            competency_level=task.competency_level,
            duty_ref=ref("duty", task.duty_id) if task.duty_id is not None else None,
            outcomes=outcomes,
            requirements=requirements,
            knowledge_refs=[ref("knowledge", x) for x in task.knowledge_ids],
            skill_refs=[ref("skill", x) for x in task.skill_ids],
        )
        tasks.append(task_view)
        text_targets = [ReferenceTarget("outcome", text.id) for text in task.outcomes]
        text_targets.extend(
            ReferenceTarget("requirement", text.id) for text in task.requirements
        )
        for text_target in text_targets:
            # 局部 O/P 查讀須附上 Task，完整 Task 內不重複父座標。
            entries[text_target] = {
                **entries[text_target],
                "task_ref": ref("task", task.id),
            }
    knowledge = [
        entry("knowledge", x.id, name=x.name, description=x.description)
        for x in snapshot.knowledge
    ]
    skills = [
        entry("skill", x.id, name=x.name, description=x.description)
        for x in snapshot.skills
    ]
    collaborations = [
        entry(
            "collaboration", x.id, collaborator_name=x.collaborator_name, scope=x.scope
        )
        for x in snapshot.collaborations
    ]
    conditions = [
        entry("condition", x.id, kind=x.kind.value, text=x.text)
        for x in snapshot.conditions
    ]
    for citation in snapshot.citations:
        source = citation.source
        result = (
            citation_results.get(citation.id) if citation_results is not None else None
        )
        source_view = result.source if result is not None else None
        summary: dict[str, Any] = {
            "citation_ref": ref("citation", citation.id),
            "kind": source.kind,
            "jd_changed": citation.jd_changed,
            "source_changed": result.source_changed if result is not None else None,
            "needs_recheck": result.needs_recheck if result is not None else None,
        }
        if isinstance(source, InterviewReference):
            summary["message_ref"] = ref("message", source.message_id)
        else:
            summary["published_version"] = source.published_version
        if source_view is not None:
            summary["availability"] = source_view.availability
            if source_view.title is not None:
                summary["target_title"] = source_view.title
            if source_view.item_kind is not None:
                summary["memory_kind"] = f"work_{source_view.item_kind}"
        owner = (
            profile
            if citation.target_kind == "job_description"
            else entries[ReferenceTarget(citation.target_kind, citation.target_id)]
        )
        owner.setdefault("supporting_sources", []).append(summary)
        entries[ReferenceTarget("citation", citation.id)] = {
            **summary,
            "read_ref": ref("citation", citation.id),
            "target_ref": (
                "profile"
                if citation.target_kind == "job_description"
                else ref(citation.target_kind, citation.target_id)
            ),
            "source_text": source_view.text if source_view is not None else None,
        }
    if view == "item":
        if target not in entries:
            raise ValueError("指定項目不存在於目前 JD")
        return {"version": snapshot.version, "item": entries[target]}
    if view == "map":
        tasks = [
            {
                "read_ref": task["read_ref"],
                "name": task["name"],
                "duty_ref": task["duty_ref"],
                "competency_level": task["competency_level"],
                "outcome_count": len(task["outcomes"]),
                "requirement_count": len(task["requirements"]),
                "knowledge_refs": task["knowledge_refs"],
                "skill_refs": task["skill_refs"],
                "supporting_sources": task.get("supporting_sources", []),
            }
            for task in tasks
        ]
        knowledge = [
            {
                "read_ref": x["read_ref"],
                "name": x["name"],
                "supporting_sources": x.get("supporting_sources", []),
            }
            for x in knowledge
        ]
        skills = [
            {
                "read_ref": x["read_ref"],
                "name": x["name"],
                "supporting_sources": x.get("supporting_sources", []),
            }
            for x in skills
        ]
    return {
        **profile,
        "duties": duties,
        "tasks": tasks,
        "knowledge": knowledge,
        "skills": skills,
        "collaborations": collaborations,
        "conditions": conditions,
    }
