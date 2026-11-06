"""人工修改的固定兩端淨差異；不是引用來源差異。"""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from caliburn.bundles.job_description.projection import project_jd
from caliburn.modules.job_description.application.citations import CitationResult
from caliburn.modules.job_description.application.content import (
    CollectionKind,
    ItemKind,
)
from caliburn.modules.job_description.application.history.differences import (
    compare_contents,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.model_references.contracts import ReferenceTarget, ResourceKind

_COLLECTION_KINDS: dict[CollectionKind, ResourceKind] = {
    "duties": "duty",
    "tasks": "task",
    "outcomes": "outcome",
    "requirements": "requirement",
    "knowledge": "knowledge",
    "skills": "skill",
    "collaborations": "collaboration",
    "conditions": "condition",
    "knowledge_ids": "knowledge",
    "skill_ids": "skill",
    "citations": "citation",
}


def project_manual_changes(
    before: JobDescriptionResult,
    after: JobDescriptionResult,
    references: Mapping[ReferenceTarget, str],
    *,
    before_citations: Mapping[UUID, CitationResult] | None = None,
    after_citations: Mapping[UUID, CitationResult] | None = None,
) -> dict[str, Any] | None:
    difference = compare_contents(
        before, after, before_version=before.version, after_version=after.version
    )
    if not difference.items and not difference.collections:
        return None

    def endpoint(
        snapshot: JobDescriptionResult,
        kind: ItemKind,
        item_id: UUID,
        citation_results: Mapping[UUID, CitationResult] | None,
    ) -> dict[str, Any]:
        if kind == "job_description":
            return {
                "job_title": snapshot.job_title,
                "organization_unit": snapshot.organization_unit,
                "reports_to": snapshot.reports_to,
                "purpose": snapshot.purpose,
                "baseline_competency_level": snapshot.baseline_competency_level,
            }
        projected = project_jd(
            snapshot,
            references,
            view="item",
            target=ReferenceTarget(kind, item_id),
            citation_results=citation_results,
        )["item"]
        assert isinstance(projected, dict)
        return projected

    items = []
    for item in difference.items:
        read_ref = (
            "profile"
            if item.kind == "job_description"
            else references[ReferenceTarget(item.kind, item.id)]
        )
        items.append(
            {
                "read_ref": read_ref,
                "kind": item.kind,
                "change": item.change,
                "before": endpoint(before, item.kind, item.id, before_citations)
                if item.change != "added"
                else None,
                "after": endpoint(after, item.kind, item.id, after_citations)
                if item.change != "removed"
                else None,
            }
        )
    collections = []
    for collection in difference.collections:
        kind = _COLLECTION_KINDS[collection.collection]
        owner_ref = (
            "profile"
            if collection.owner_id == before.job_description_id
            else references[ReferenceTarget("task", collection.owner_id)]
        )
        group = collection.group
        group_ref = (
            references[ReferenceTarget("duty", group)]
            if isinstance(group, UUID)
            else group
        )
        collections.append(
            {
                "collection": collection.collection,
                "owner_ref": owner_ref,
                "group": group_ref,
                "before_refs": [
                    references[ReferenceTarget(kind, x)] for x in collection.before_ids
                ],
                "after_refs": [
                    references[ReferenceTarget(kind, x)] for x in collection.after_ids
                ],
            }
        )
    return {
        "data_kind": "jd_manual_changes",
        "before_version": before.version,
        "after_version": after.version,
        "items": items,
        "collections": collections,
    }
