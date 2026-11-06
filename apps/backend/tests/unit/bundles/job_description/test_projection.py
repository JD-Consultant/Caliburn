"""JD 的模型投影保留順序／正文，所有關聯只用共用短碼。"""

import json
from uuid import UUID

import pytest

from caliburn.bundles.job_description.projection import project_jd, reference_targets
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.domain.models.citation import (
    Citation,
    InterviewReference,
)
from caliburn.modules.model_references.contracts import ReferenceTarget, ResourceKind


def snapshot() -> JobDescriptionResult:
    return JobDescriptionResult.model_validate(
        {
            "job_description_id": UUID(int=1),
            "workspace_id": UUID(int=2),
            "version": 7,
            "job_title": "倉管",
            "organization_unit": None,
            "reports_to": None,
            "purpose": "保留 task_999 原文",
            "baseline_competency_level": 3,
            "duties": [{"id": UUID(int=3), "name": "收貨", "scope": "範圍"}],
            "tasks": [
                {
                    "id": UUID(int=4),
                    "duty_id": UUID(int=3),
                    "name": "驗收",
                    "description": " 原文\n",
                    "competency_level": 2,
                    "outcomes": [{"id": UUID(int=5), "text": "完成清單"}],
                    "requirements": [{"id": UUID(int=6), "text": "逐項核對"}],
                    "knowledge_ids": [UUID(int=7)],
                    "skill_ids": [UUID(int=8)],
                }
            ],
            "knowledge": [
                {"id": UUID(int=7), "name": "商品規格", "description": "知識正文"}
            ],
            "skills": [{"id": UUID(int=8), "name": "查驗", "description": "技能正文"}],
            "collaborations": [
                {"id": UUID(int=9), "collaborator_name": "採購", "scope": "異常"}
            ],
            "conditions": [
                {"id": UUID(int=10), "kind": "work_environment", "text": "倉庫"}
            ],
        },
        strict=False,
    )


def refs() -> dict[ReferenceTarget, str]:
    items: tuple[tuple[ResourceKind, int], ...] = (
        ("duty", 3),
        ("task", 4),
        ("outcome", 5),
        ("requirement", 6),
        ("knowledge", 7),
        ("skill", 8),
        ("collaboration", 9),
        ("condition", 10),
    )
    return {
        ReferenceTarget(kind, UUID(int=number)): f"{kind}_{number + 100}"
        for kind, number in items
    }


def test_full_projection_preserves_text_and_projects_all_relationships() -> None:
    result = project_jd(snapshot(), refs(), view="full")
    encoded = json.dumps(result)
    assert all(str(UUID(int=n)) not in encoded for n in range(1, 11))
    assert result["purpose"] == "保留 task_999 原文"
    assert result["version"] == 7
    task = result["tasks"][0]
    assert task["read_ref"] == "task_104"
    assert task["duty_ref"] == "duty_103"
    assert task["description"] == " 原文\n"
    assert task["outcomes"] == [{"read_ref": "outcome_105", "text": "完成清單"}]
    assert task["knowledge_refs"] == ["knowledge_107"]
    assert task["skill_refs"] == ["skill_108"]
    assert set(reference_targets(snapshot())) == set(refs())


def test_navigation_retains_all_kinds_and_counts_without_full_task_text() -> None:
    result = project_jd(snapshot(), refs(), view="map")
    task = result["tasks"][0]
    assert task["outcome_count"] == 1
    assert task["requirement_count"] == 1
    assert "description" not in task and "outcomes" not in task
    assert task["knowledge_refs"] == ["knowledge_107"]
    assert all(
        len(result[key]) == 1
        for key in (
            "duties",
            "tasks",
            "knowledge",
            "skills",
            "collaborations",
            "conditions",
        )
    )


@pytest.mark.parametrize(
    "kind,number", [("task", 4), ("outcome", 5), ("requirement", 6)]
)
def test_item_returns_exact_target_with_parent_for_task_text(
    kind: str, number: int
) -> None:
    target = next(target for target in refs() if target.resource_id == UUID(int=number))
    result = project_jd(snapshot(), refs(), view="item", target=target)
    assert result["item"]["read_ref"] == f"{kind}_{number + 100}"
    assert result["version"] == 7
    if kind != "task":
        assert result["item"]["task_ref"] == "task_104"


def test_deleted_or_other_kind_target_is_rejected_even_if_mapping_still_exists() -> (
    None
):
    with pytest.raises(ValueError):
        project_jd(
            snapshot(),
            refs(),
            view="item",
            target=ReferenceTarget("message", UUID(int=4)),
        )


def test_citations_project_stable_ids_without_exposing_formal_source_uuid() -> None:
    before = snapshot()
    citation = Citation(
        id=UUID(int=11),
        target_kind="task",
        target_id=UUID(int=4),
        source=InterviewReference(
            workspace_id=before.workspace_id, message_id=UUID(int=12)
        ),
        jd_changed=True,
    )
    current = before.model_copy(update={"citations": (citation,)})
    assigned = {
        **refs(),
        ReferenceTarget("citation", citation.id): "citation_111",
        ReferenceTarget("message", UUID(int=12)): "message_112",
    }
    result = project_jd(
        current, assigned, view="item", target=ReferenceTarget("task", UUID(int=4))
    )
    support = result["item"]["supporting_sources"][0]
    assert (
        support["citation_ref"] == "citation_111"
        and support["message_ref"] == "message_112"
    )
    assert support["jd_changed"] is True
    assert support["needs_recheck"] is None  # 純歷史投影沒有另查目前來源狀態。
    assert str(UUID(int=12)) not in json.dumps(result)
    assert ReferenceTarget("citation", citation.id) in reference_targets(current)
