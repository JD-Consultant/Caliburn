"""Task 離開 Current JD 時的 OPKS 缺口清理(ADR 0054 決定 26–27)。

`prune_opks_for_current_jd()` 只收／回 `CurrentJdOpks`,碰不到 `work_model.open_issues`;
缺口的清理是相鄰的另一個純函式。呼叫點是否真的接上,由
`test_job_analysis_opks_authoring_postgres.py` 走真 PostgreSQL 驗收。
"""

from __future__ import annotations

from app.job_analysis.application import prune_opks_gaps_for_current_jd
from app.core.domain import (
    JdTask,
    OpenIssue,
    OpenIssueKind,
    OpksGapAxis,
    SourceAnchor,
    SourceKind,
    SourceRef,
)

def anchor() -> SourceAnchor:
    return SourceAnchor(
        source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="turn-1"),
        quote="我每週彙整營運週報",
    )

def opks_gap_issue(issue_id: str, task_id: str) -> OpenIssue:
    return OpenIssue(
        id=issue_id,
        kind=OpenIssueKind.INSUFFICIENT_EVIDENCE,
        summary="還看不出這項工作交出什麼",
        source_anchors=(anchor(),),
        subject_task_id=task_id,
        opks_axis=OpksGapAxis.OUTPUT,
    )

def general_issue(issue_id: str = "general-1") -> OpenIssue:
    return OpenIssue(
        id=issue_id,
        kind=OpenIssueKind.RESPONSIBILITY_UNCLEAR,
        summary="責任邊界還不清楚",
        source_anchors=(anchor(),),
    )

def jd(task_id: str, statement: str = "彙整營運週報") -> JdTask:
    return JdTask(task_id=task_id, statement=statement, display_order=0)

    kept = jd("task-1")

    remaining = prune_opks_gaps_for_current_jd(
        (opks_gap_issue("gap-1", "task-1"), opks_gap_issue("gap-2", "task-gone")),
        (kept,),
    )

    assert [issue.id for issue in remaining] == ["gap-1"]

def test_removal_never_fabricates_a_terminal_resolution():
    """`terminal_resolution` 的兩個值都是**員工的回答**。

    Task 被刪除／撤回／合併／拆分時員工並沒有回答任何事;借用它們等於偽造一筆不存在
    的回答,而那筆假回答會進到 packet 的「已問過、勿重問」記憶區,被主顧問與
    specialist 當真。
    """

    remaining = prune_opks_gaps_for_current_jd(
        (opks_gap_issue("gap-1", "task-gone"),),
        (),
    )

    assert remaining == ()

def test_non_opks_open_issues_are_untouched():
    """一般 open issue 沒有 `opks_axis`,不歸這個 seam 管。"""

    remaining = prune_opks_gaps_for_current_jd((general_issue(),), ())

    assert [issue.id for issue in remaining] == ["general-1"]

def test_a_merge_or_split_replacement_does_not_inherit_the_gap():
    """決定 27:不遷移。沒有人知道新 Task 是不是還缺同一件事。

    真的還缺,下次分析會自己重新提出——那是有依據的判斷,不是猜的。
    """

    replacement = jd("merged-1", "彙整並發佈營運週報")

    remaining = prune_opks_gaps_for_current_jd(
        (opks_gap_issue("gap-1", "task-1"),),
        (replacement,),
    )

    assert remaining == ()
