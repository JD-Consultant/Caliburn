"""Full JD is finished-product text, not navigation or a second authored summary."""

from dataclasses import replace
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
from caliburn.features.job_description.models import JdProfile
from caliburn.features.job_description.tasks import DetailKind, TaskDetail, WorkTask
from caliburn.features.job_description.work_queries import JdWorkRevision
from caliburn.transport.jd_full_text import project_jd_full_text


@pytest.fixture
def work() -> JdWorkRevision:
    return JdWorkRevision(
        UUID(int=1),
        (
            ResponsibilityArea(UUID(int=2), UUID(int=3), "網站交付", "只負責前端。"),
            ResponsibilityArea(UUID(int=20), UUID(int=21), "維運", "僅限已約定的維護範圍。"),
        ),
        (
            WorkTask(UUID(int=4), UUID(int=5), None, "支援交接", "整理操作說明。", ()),
            WorkTask(
                UUID(int=6),
                UUID(int=7),
                UUID(int=2),
                "實作頁面",
                "依確認稿實作頁面。\n保留表格中的 | 字元與 🙂。",
                (
                    TaskDetail(UUID(int=8), DetailKind.REQUIREMENT, "檢查錯誤情境。"),
                    TaskDetail(UUID(int=9), DetailKind.OUTCOME, "可操作頁面。"),
                    TaskDetail(UUID(int=10), DetailKind.OUTCOME, "交付說明。"),
                    TaskDetail(UUID(int=22), DetailKind.REQUIREMENT, "逐項列明未解限制。"),
                ),
            ),
            WorkTask(UUID(int=23), UUID(int=24), UUID(int=2), "確認交付", None, ()),
        ),
        (
            Capability(
                UUID(int=11), UUID(int=12), CapabilityKind.KNOWLEDGE, "資料介面", "請求格式。"
            ),
            Capability(
                UUID(int=15), UUID(int=16), CapabilityKind.SKILL, "介面實作", "實作錯誤處理。"
            ),
            Capability(
                UUID(int=13), UUID(int=14), CapabilityKind.KNOWLEDGE, "資料介面", "回應語意。"
            ),
        ),
        (
            TaskCapabilityLink(UUID(int=6), UUID(int=13)),
            TaskCapabilityLink(UUID(int=6), UUID(int=15)),
            TaskCapabilityLink(UUID(int=6), UUID(int=11)),
            TaskCapabilityLink(UUID(int=4), UUID(int=15)),
        ),
        (
            Collaborator(UUID(int=17), UUID(int=18), "設計師", "確認互動，不代替主管核准。"),
            Collaborator(UUID(int=25), UUID(int=26), "後端工程師", "負責後端規則。"),
        ),
        (
            JobCondition(UUID(int=27), UUID(int=28), ConditionKind.SCHEDULE_TRAVEL, "依約出差。"),
            JobCondition(UUID(int=29), UUID(int=30), ConditionKind.WORK_ENVIRONMENT, "辦公室。"),
            JobCondition(
                UUID(int=31), UUID(int=32), ConditionKind.SHARED_AUTHORITY, "不具採購核准權。"
            ),
            JobCondition(
                UUID(int=33), UUID(int=34), ConditionKind.SHARED_COLLABORATION, "跨團隊確認變更。"
            ),
            JobCondition(UUID(int=35), UUID(int=36), ConditionKind.QUALIFICATION, "有效作業許可。"),
        ),
    )


def test_full_preserves_all_content_grouping_and_relationship_order(work: JdWorkRevision) -> None:
    purpose = "交付前端網站。\n" + "此段已寫文字不可改為預覽。" * 20
    profile = JdProfile("前端工程師", "產品團隊", "產品主管", purpose)

    result = project_jd_full_text(profile, work)

    assert result.startswith("# 職務說明書\n\n## 職務基本資料\n")
    assert "**職稱**\n\n前端工程師" in result
    assert "**組織單位**\n\n產品團隊" in result
    assert "**匯報對象**\n\n產品主管" in result
    assert f"## 職務目的\n\n{purpose}" in result
    assigned, unassigned = result.split("### 未歸屬任務\n\n")
    assert "### 職責 1：網站交付\n\n只負責前端。" in assigned
    assert "### 職責 2：維運\n\n僅限已約定的維護範圍。" in assigned
    task = assigned.split("#### 任務 1：實作頁面\n\n")[1]
    assert task.startswith(
        "依確認稿實作頁面。\n保留表格中的 | 字元與 🙂。\n\n"
        "##### 成果\n\n**成果 1**\n\n可操作頁面。\n\n"
        "**成果 2**\n\n交付說明。\n\n"
        "##### 工作執行要求\n\n**要求 1**\n\n檢查錯誤情境。\n\n"
        "**要求 2**\n\n逐項列明未解限制。\n\n"
        "##### 所需知識\n\n- 知識 2：資料介面\n- 知識 1：資料介面\n\n"
        "##### 所需技能\n\n- 技能 1：介面實作\n\n"
        "#### 任務 2：確認交付"
    )
    assert unassigned.startswith(
        "#### 任務 1：支援交接\n\n整理操作說明。\n\n"
        "##### 所需技能\n\n- 技能 1：介面實作\n\n"
        "## 所需知識總覽\n\n"
        "### 知識 1：資料介面\n\n請求格式。\n\n"
        "### 知識 2：資料介面\n\n回應語意。\n\n"
        "## 所需技能總覽\n\n### 技能 1：介面實作\n\n實作錯誤處理。"
    )
    assert "## 主要協作對象\n\n### 協作對象 1：設計師\n\n" in result
    assert "確認互動，不代替主管核准。\n\n### 協作對象 2：後端工程師" in result
    assert "後端工程師\n\n負責後端規則。" in result
    assert result.endswith(
        "## 工作條件與責任邊界\n\n### 工時與出差\n\n依約出差。\n\n"
        "### 工作環境\n\n辦公室。\n\n### 共通權限界線\n\n不具採購核准權。\n\n"
        "### 共通協作界線\n\n跨團隊確認變更。\n\n### 必要資格\n\n有效作業許可。\n"
    )
    for text in ("請求格式。", "回應語意。", "實作錯誤處理。", "不具採購核准權。"):
        assert result.count(text) == 1
    assert "read_ref" not in result
    assert "來源" not in result
    assert "Memory" not in result
    for number in range(1, 37):
        assert str(UUID(int=number)) not in result
        assert UUID(int=number).hex not in result
    assert profile.purpose == purpose
    assert work.task_links[0].capability_id == UUID(int=13)


def test_empty_jd_does_not_invent_values_or_absence_claims() -> None:
    work = JdWorkRevision(UUID(int=1), (), (), (), (), (), ())
    assert project_jd_full_text(JdProfile(), work) == "# 職務說明書\n"


def test_nameless_items_and_unlinked_definitions_remain_complete(work: JdWorkRevision) -> None:
    knowledge = replace(work.capabilities[0], name=None)
    skill = replace(work.capabilities[1], name=None)
    work = replace(
        work,
        areas=(replace(work.areas[0], title=None),),
        tasks=(replace(work.tasks[1], title=None, description="  原文\n\n第二段  ", details=()),),
        capabilities=(knowledge, skill, replace(work.capabilities[2], description=None)),
        task_links=(TaskCapabilityLink(UUID(int=6), skill.capability_id),),
        collaborators=(replace(work.collaborators[0], name=None),),
        conditions=(),
    )

    result = project_jd_full_text(JdProfile(), work)

    assert result == (
        "# 職務說明書\n\n## 主要職責與工作任務\n\n"
        "### 職責 1\n\n只負責前端。\n\n#### 任務 1\n\n  原文\n\n第二段  \n\n"
        "##### 所需技能\n\n- 技能 1\n\n"
        "## 所需知識總覽\n\n### 知識 1\n\n請求格式。\n\n### 知識 2：資料介面\n\n"
        "## 所需技能總覽\n\n### 技能 1\n\n實作錯誤處理。\n\n"
        "## 主要協作對象\n\n### 協作對象 1\n\n確認互動，不代替主管核准。\n"
    )
    assert work.tasks[0].title is None
    assert work.capabilities[0].name is None


@pytest.mark.parametrize("missing", ["area", "task", "capability"])
def test_dangling_relationship_is_not_silently_omitted(work: JdWorkRevision, missing: str) -> None:
    if missing == "area":
        work = replace(work, areas=())
    elif missing == "task":
        work = replace(work, tasks=())
    else:
        work = replace(work, capabilities=())

    with pytest.raises(ValueError, match="outside this JD revision"):
        project_jd_full_text(JdProfile(), work)
