"""Complete product content, not model navigation or internal evidence, goes to print."""

from uuid import uuid4

from caliburn.features.job_description.areas import ResponsibilityArea
from caliburn.features.job_description.capabilities import (
    Capability,
    CapabilityKind,
    TaskCapabilityLink,
)
from caliburn.features.job_description.collaborators import Collaborator
from caliburn.features.job_description.conditions import ConditionKind, JobCondition
from caliburn.features.job_description.export_projection import project_jd_export_html
from caliburn.features.job_description.models import JdProfile
from caliburn.features.job_description.tasks import DetailKind, TaskDetail, WorkTask
from caliburn.features.job_description.work_queries import JdWorkRevision


def example_work() -> JdWorkRevision:
    area, task, knowledge, skill = (uuid4() for _ in range(4))
    return JdWorkRevision(
        uuid4(),
        (ResponsibilityArea(area, uuid4(), "網站交付", "前端範圍"),),
        (
            WorkTask(
                task,
                uuid4(),
                area,
                "驗證表單",
                "輸入測試\n異常回報",
                (
                    TaskDetail(uuid4(), DetailKind.OUTCOME, "可重現的測試報告"),
                    TaskDetail(uuid4(), DetailKind.REQUIREMENT, "遵守無障礙規範"),
                ),
            ),
            WorkTask(uuid4(), uuid4(), None, None, "支援跨團隊需求", ()),
        ),
        (
            Capability(knowledge, uuid4(), CapabilityKind.KNOWLEDGE, "HTTP", "回應狀態語意"),
            Capability(skill, uuid4(), CapabilityKind.SKILL, "除錯", "定位失敗路徑"),
        ),
        (TaskCapabilityLink(task, knowledge), TaskCapabilityLink(task, skill)),
        (Collaborator(uuid4(), uuid4(), "設計師", "核對互動細節"),),
        tuple(JobCondition(uuid4(), uuid4(), kind, f"條件-{kind.value}") for kind in ConditionKind),
    )


def test_complete_export_preserves_all_sections_and_escapes_untrusted_text() -> None:
    work = example_work()
    html = project_jd_export_html(
        JdProfile("<script>alert(1)</script>", "研發", "主管", "交付網站"), work
    )
    for expected in (
        "網站交付",
        "前端範圍",
        "驗證表單",
        "輸入測試\n異常回報",
        "可重現的測試報告",
        "遵守無障礙規範",
        "支援跨團隊需求",
        "HTTP",
        "回應狀態語意",
        "除錯",
        "定位失敗路徑",
        "設計師",
        "核對互動細節",
    ):
        assert expected in html
    for kind in ConditionKind:
        assert f"條件-{kind.value}" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>" not in html
    assert str(work.revision_id) not in html
    assert "read_ref" not in html


def test_empty_formal_jd_is_exportable_without_invented_work() -> None:
    html = project_jd_export_html(JdProfile(), JdWorkRevision(uuid4(), (), (), (), (), (), ()))
    assert "職務說明書" in html
    assert "尚無已保存的職務內容" in html
