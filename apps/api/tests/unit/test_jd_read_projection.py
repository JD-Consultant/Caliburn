"""Only selected JD content and correctly owned direct evidence appear in local reads."""

from uuid import UUID

import pytest

from caliburn.features.job_description.areas import ResponsibilityArea
from caliburn.features.job_description.capabilities import (
    Capability,
    CapabilityKind,
    TaskCapabilityLink,
)
from caliburn.features.job_description.collaborators import Collaborator
from caliburn.features.job_description.conditions import ConditionKind, JobCondition
from caliburn.features.job_description.models import JdProfile, ProfileField
from caliburn.features.job_description.navigation import (
    JdReadTarget,
    jd_read_ref,
)
from caliburn.features.job_description.sources import (
    InterviewSource,
    JdSourceReference,
    JdSourceTarget,
    MemorySource,
    MemorySourceLayer,
    SourceTargetKind,
)
from caliburn.features.job_description.tasks import DetailKind, TaskDetail, WorkTask
from caliburn.features.job_description.work_models import JdWorkRevision
from caliburn.transport.model_tools.jd_detail_projection import (
    jd_read_source_targets,
    project_jd_item,
    project_jd_profile,
    select_jd_items,
)
from caliburn.workflows.job_description.reads import JdSourceReading


@pytest.fixture
def work() -> JdWorkRevision:
    return JdWorkRevision(
        UUID(int=1),
        (ResponsibilityArea(UUID(int=2), UUID(int=3), None, "職責完整範圍"),),
        (
            WorkTask(
                UUID(int=4),
                UUID(int=5),
                UUID(int=2),
                "同名任務",
                "完整任務\n原文",
                (
                    TaskDetail(UUID(int=6), DetailKind.OUTCOME, "同文"),
                    TaskDetail(UUID(int=7), DetailKind.OUTCOME, "同文"),
                    TaskDetail(UUID(int=8), DetailKind.REQUIREMENT, "要求原文"),
                ),
            ),
            WorkTask(UUID(int=9), UUID(int=10), None, "同名任務", None, ()),
        ),
        (
            Capability(UUID(int=11), UUID(int=12), CapabilityKind.KNOWLEDGE, None, "知識正文"),
            Capability(UUID(int=13), UUID(int=14), CapabilityKind.SKILL, "技能", "技能正文"),
        ),
        (
            TaskCapabilityLink(UUID(int=4), UUID(int=13)),
            TaskCapabilityLink(UUID(int=4), UUID(int=11)),
            TaskCapabilityLink(UUID(int=9), UUID(int=11)),
        ),
        (Collaborator(UUID(int=15), UUID(int=16), None, "協作範圍"),),
        (JobCondition(UUID(int=17), UUID(int=18), ConditionKind.SHARED_AUTHORITY, "權限範圍"),),
    )


def interview_reading(number: int, target: JdSourceTarget) -> JdSourceReading:
    return JdSourceReading(
        JdSourceReference(UUID(int=number), target, InterviewSource(UUID(int=1000 + number))),
        interview_sequence=number,
    )


def test_interview_source_without_a_number_is_not_projected_as_current_input(work):
    task = work.tasks[0]
    source = JdSourceReading(
        JdSourceReference(
            UUID(int=20),
            JdSourceTarget(SourceTargetKind.TASK, task.task_id),
            InterviewSource(UUID(int=1020)),
        )
    )
    with pytest.raises(AssertionError):
        project_jd_item(task, work, (source,))


def test_task_children_use_task_evidence_and_capability_definition_stays_independent(work):
    task = work.tasks[0]
    own = interview_reading(20, JdSourceTarget(SourceTargetKind.TASK, task.task_id))
    definition = interview_reading(23, JdSourceTarget(SourceTargetKind.CAPABILITY, UUID(int=11)))
    result = project_jd_item(task, work, (own, definition))
    assert result["title"] == "同名任務"
    assert result["required_knowledge"][0]["description"] == "知識正文"
    assert result["supporting_sources"] == [
        {
            "citation_ref": "citation_00000000000000000000000000000014",
            "kind": "interview",
            "interview_sequence": 20,
            "needs_recheck": False,
            "jd_changed": False,
            "source_changed": False,
        }
    ]
    assert result["outcomes"] == [
        {"read_ref": "outcome_00000000000000000000000000000006", "text": "同文"},
        {"read_ref": "outcome_00000000000000000000000000000007", "text": "同文"},
    ]
    assert result["required_knowledge"] == [
        {
            "read_ref": "knowledge_0000000000000000000000000000000b",
            "name": None,
            "description": "知識正文",
        }
    ]
    assert jd_read_source_targets(work, (task,)) == (own.reference.target,)
    detail = project_jd_item(task.details[0], work, (own, definition))
    assert detail["task_read_ref"] == jd_read_ref(task)
    assert detail["supporting_sources"] == result["supporting_sources"]
    assert jd_read_source_targets(work, (task.details[0],)) == (own.reference.target,)
    capability = project_jd_item(work.capabilities[0], work, (own, definition))
    assert capability["supporting_sources"] == [
        {
            "citation_ref": "citation_00000000000000000000000000000017",
            "kind": "interview",
            "interview_sequence": 23,
            "needs_recheck": False,
            "jd_changed": False,
            "source_changed": False,
        }
    ]
    assert capability["used_by_tasks"][0]["supporting_sources"] == result["supporting_sources"]


def test_own_content_reverse_uses_and_all_collection_boundaries(work: JdWorkRevision) -> None:
    collections: dict[str, tuple[JdReadTarget, ...]] = {
        "responsibility_areas": work.areas,
        "work_tasks": (work.tasks[0],),
        "unassigned_work_tasks": (work.tasks[1],),
        "required_knowledge": (work.capabilities[0],),
        "required_skills": (work.capabilities[1],),
        "main_collaborators": work.collaborators,
        "job_wide_conditions": work.conditions,
    }
    for view, items in collections.items():
        reference = jd_read_ref(work.areas[0]) if view == "work_tasks" else None
        assert select_jd_items(work, view, reference) == items
        for item in items:
            assert select_jd_items(work, "item", jd_read_ref(item)) == (item,)
    assert project_jd_item(work.areas[0], work, ()) == {
        "kind": "responsibility_area",
        "read_ref": jd_read_ref(work.areas[0]),
        "title": None,
        "scope_text": "職責完整範圍",
        "supporting_sources": [],
    }
    relation = interview_reading(30, JdSourceTarget(SourceTargetKind.TASK, UUID(int=4)))
    result = project_jd_item(work.capabilities[0], work, (relation,))
    assert result == {
        "kind": "knowledge",
        "read_ref": jd_read_ref(work.capabilities[0]),
        "name": None,
        "description": "知識正文",
        "supporting_sources": [],
        "used_by_tasks": [
            {
                "read_ref": jd_read_ref(work.tasks[0]),
                "title": "同名任務",
                "supporting_sources": [
                    {
                        "citation_ref": "citation_0000000000000000000000000000001e",
                        "kind": "interview",
                        "interview_sequence": 30,
                        "needs_recheck": False,
                        "jd_changed": False,
                        "source_changed": False,
                    }
                ],
            },
            {"read_ref": jd_read_ref(work.tasks[1]), "title": "同名任務", "supporting_sources": []},
        ],
    }
    assert relation.reference.target in jd_read_source_targets(work, (work.capabilities[0],))
    assert project_jd_item(work.collaborators[0], work, ())["scope_text"] == "協作範圍"
    assert project_jd_item(work.conditions[0], work, ()) == {
        "kind": "job_wide_condition",
        "read_ref": jd_read_ref(work.conditions[0]),
        "condition_kind": "shared_authority",
        "text": "權限範圍",
        "supporting_sources": [],
    }


def test_profile_sources_are_per_field_and_only_pending_status_is_visible() -> None:
    target = JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE)
    memory = MemorySource(
        MemorySourceLayer.WORK_UNDERSTANDING, UUID(int=50), UUID(int=51), UUID(int=52)
    )
    source = JdSourceReading(
        JdSourceReference(UUID(int=53), target, memory),
        target_title="新版名稱",
        historical_title="引用時名稱",
        source_changed=True,
    )
    assert project_jd_profile(JdProfile(purpose="完整目的"), (source,)) == {
        "job_title": None,
        "organization_unit": None,
        "reports_to": None,
        "purpose": "完整目的",
        "supporting_sources": {
            "job_title": [],
            "organization_unit": [],
            "reports_to": [],
            "purpose": [
                {
                    "citation_ref": "citation_00000000000000000000000000000035",
                    "kind": "work_understanding",
                    "target_title": "新版名稱",
                    "historical_title": "引用時名稱",
                    "needs_recheck": True,
                    "jd_changed": False,
                    "source_changed": True,
                }
            ],
        },
    }
