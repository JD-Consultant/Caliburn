"""Navigation is a projection of one visible JD, not another mutable summary."""

from dataclasses import replace
from uuid import UUID

import pytest

from caliburn.features.job_description.areas import ResponsibilityArea
from caliburn.features.job_description.capabilities import Capability, CapabilityKind
from caliburn.features.job_description.collaborators import Collaborator
from caliburn.features.job_description.conditions import ConditionKind, JobCondition
from caliburn.features.job_description.models import JdProfile
from caliburn.features.job_description.navigation import (
    JdReadTargetNotFoundError,
    resolve_jd_read_ref,
)
from caliburn.features.job_description.tasks import DetailKind, TaskDetail, WorkTask
from caliburn.features.job_description.work_queries import JdWorkRevision
from caliburn.transport.model_tools.jd_navigation import project_jd_map


@pytest.fixture
def work() -> JdWorkRevision:
    return JdWorkRevision(
        UUID(int=1),
        (ResponsibilityArea(UUID(int=2), UUID(int=3), "網站交付", "只負責前端。"),),
        (
            WorkTask(UUID(int=4), UUID(int=5), None, "支援交接", None, ()),
            WorkTask(
                UUID(int=6),
                UUID(int=7),
                UUID(int=2),
                "實作頁面",
                "依確認稿實作頁面。",
                (
                    TaskDetail(UUID(int=8), DetailKind.OUTCOME, "可操作頁面"),
                    TaskDetail(UUID(int=9), DetailKind.OUTCOME, "交付說明"),
                    TaskDetail(UUID(int=10), DetailKind.REQUIREMENT, "檢查錯誤情境"),
                ),
            ),
        ),
        (
            Capability(
                UUID(int=11), UUID(int=12), CapabilityKind.KNOWLEDGE, "資料介面", "知識完整內容"
            ),
            Capability(
                UUID(int=13), UUID(int=14), CapabilityKind.KNOWLEDGE, "資料介面", "不同用途"
            ),
            Capability(
                UUID(int=15), UUID(int=16), CapabilityKind.SKILL, "介面實作", "技能完整內容"
            ),
        ),
        (),
        (Collaborator(UUID(int=17), UUID(int=18), "設計師", "協作完整內容"),),
        (JobCondition(UUID(int=19), UUID(int=20), ConditionKind.WORK_ENVIRONMENT, "測試用環境。"),),
    )


def test_map_preserves_hierarchy_counts_and_only_navigation_content(work: JdWorkRevision) -> None:
    result = project_jd_map(JdProfile("前端工程師", "產品團隊", "主管", "交付前端網站。"), work)
    payload = result.model_dump(mode="json", exclude_unset=True)
    assert payload == {
        "profile": {
            "job_title": "前端工程師",
            "organization_unit": "產品團隊",
            "reports_to": "主管",
            "job_purpose_preview": "交付前端網站。",
        },
        "responsibility_areas": [
            {
                "read_ref": "area_00000000000000000000000000000002",
                "title": "網站交付",
                "scope_preview": "只負責前端。",
                "work_tasks": [
                    {
                        "read_ref": "task_00000000000000000000000000000006",
                        "title": "實作頁面",
                        "work_preview": "依確認稿實作頁面。",
                        "outcome_count": 2,
                        "requirement_count": 1,
                    }
                ],
            }
        ],
        "unassigned_work_tasks": [
            {
                "read_ref": "task_00000000000000000000000000000004",
                "title": "支援交接",
                "outcome_count": 0,
                "requirement_count": 0,
            }
        ],
        "required_knowledge": [
            {"read_ref": "knowledge_0000000000000000000000000000000b", "name": "資料介面"},
            {"read_ref": "knowledge_0000000000000000000000000000000d", "name": "資料介面"},
        ],
        "required_skills": [
            {"read_ref": "skill_0000000000000000000000000000000f", "name": "介面實作"}
        ],
        "main_collaborators": [
            {"read_ref": "collaborator_00000000000000000000000000000011", "name": "設計師"}
        ],
        "job_wide_conditions": [
            {
                "read_ref": "condition_00000000000000000000000000000013",
                "description_preview": "測試用環境。",
            }
        ],
    }


def test_empty_jd_does_not_invent_work_or_preview() -> None:
    work = JdWorkRevision(UUID(int=1), (), (), (), (), (), ())
    payload = project_jd_map(JdProfile(), work).model_dump(mode="json", exclude_unset=True)
    assert payload.pop("profile") == {
        "job_title": None,
        "organization_unit": None,
        "reports_to": None,
    }
    assert all(value == [] for value in payload.values())


def test_preview_is_exact_excerpt_not_summary_and_never_changes_source(
    work: JdWorkRevision,
) -> None:
    profile = JdProfile(purpose="前端🙂\n固定工作：每月確認！")
    result = project_jd_map(profile, work, preview_characters=6)
    assert result.profile.job_purpose_preview == "前端🙂\n固定…"
    assert profile.purpose == "前端🙂\n固定工作：每月確認！"
    assert result.responsibility_areas[0].scope_preview == "只負責前端。"
    with pytest.raises(ValueError):
        project_jd_map(profile, work, preview_characters=0)


def test_nameless_valid_items_remain_visible_without_fabricated_names(work: JdWorkRevision) -> None:
    item = replace(work.capabilities[0], name=None)
    work = replace(work, capabilities=(item,))
    result = project_jd_map(JdProfile(), work)
    assert result.required_knowledge[0].name is None
    assert resolve_jd_read_ref(work, result.required_knowledge[0].read_ref) == item


def test_same_names_and_same_detail_text_do_not_merge_identity(work: JdWorkRevision) -> None:
    result = project_jd_map(JdProfile(), work)
    first, second = result.required_knowledge
    assert first.read_ref != second.read_ref
    assert resolve_jd_read_ref(work, first.read_ref) == work.capabilities[0]
    assert resolve_jd_read_ref(work, second.read_ref) == work.capabilities[1]
    assert (
        resolve_jd_read_ref(work, "outcome_00000000000000000000000000000008")
        == work.tasks[1].details[0]
    )


def test_ref_follows_same_identity_after_rename_but_not_deleted_replacement(
    work: JdWorkRevision,
) -> None:
    reference = project_jd_map(JdProfile(), work).responsibility_areas[0].read_ref
    renamed = replace(work.areas[0], title="正式交付", content_revision_id=UUID(int=21))
    newer = replace(work, revision_id=UUID(int=22), areas=(renamed,))
    assert resolve_jd_read_ref(newer, reference) == renamed
    replacement = replace(renamed, area_id=UUID(int=23), title="網站交付")
    newer = replace(newer, areas=(replacement,), tasks=())
    with pytest.raises(JdReadTargetNotFoundError):
        resolve_jd_read_ref(newer, reference)


@pytest.mark.parametrize(
    "reference",
    [
        "網站交付",
        "area_2",
        "task_00000000000000000000000000000002",
        "area_00000000000000000000000000000099",
    ],
)
def test_invalid_or_out_of_scope_reference_never_falls_back_to_name(
    work: JdWorkRevision, reference: str
) -> None:
    with pytest.raises(JdReadTargetNotFoundError):
        resolve_jd_read_ref(work, reference)
