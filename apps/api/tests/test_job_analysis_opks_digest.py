"""`analysis_input_digest` 與推導的 child operation ID(ADR 0054 決定 7、12–14)。

digest 回答一個問題:**這個 Task 的分析輸入變了嗎**。它決定要不要再花一次錢,
所以納入與排除都是契約,不是實作細節——排除錯了會 ping-pong 或形成付費 reject loop,
納入錯了會漏掉該重分析的狀態。
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from app.job_analysis.application import (
    ScheduledOpks,
    build_opks_context_packet,
    compute_analysis_input_digest,
    scheduled_opks_operation_id,
)
from app.core.domain import (
    CurrentJdOpks,
    Enabler,
    EnablerKind,
    SourceKind,
    SourceRef,
    SupportLink,
    Task,
)


def employee_link(
    quote: str = "我每週彙整營運週報",
    *,
    source_id: str = "turn-1",
    superseded_by: SourceRef | None = None,
) -> SupportLink:
    return SupportLink(
        source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id=source_id),
        quote=quote,
        superseded_by=superseded_by,
    )


def decision_link() -> SupportLink:
    return SupportLink(
        source_ref=SourceRef(kind=SourceKind.PROPOSAL_DECISION, id="decision-1"),
    )


def task(*support_links: SupportLink, **overrides) -> Task:
    return Task(
        **{
            "task_id": "task-1",
            "statement": "彙整營運週報，提供主管追蹤營運狀況",
            "action": "彙整",
            "object": "營運週報",
            "purpose_result": "提供主管追蹤營運狀況",
            "support_links": support_links or (employee_link(),),
            **overrides,
        }
    )


def test_the_same_input_yields_the_same_digest():
    assert compute_analysis_input_digest(task()) == compute_analysis_input_digest(task())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("statement", "彙整營運月報，提供主管追蹤營運狀況"),
        ("action", "撰寫"),
        ("object", "營運月報"),
        ("purpose_result", "提供董事會追蹤營運狀況"),
        ("context", "每月最後一個工作天"),
        ("enablers", (Enabler(kind=EnablerKind.TOOL_SYSTEM, name="ERP"),)),
    ],
)
def test_every_task_semantic_field_changes_the_digest(field, value):
    """決定 12:六個語意欄位全部納入。少納一個就會漏掉該重分析的狀態。"""

    assert compute_analysis_input_digest(
        task(**{field: value})
    ) != compute_analysis_input_digest(task())


def test_new_effective_employee_evidence_changes_the_digest():
    before = task(employee_link())
    after = task(employee_link(), employee_link("也要附上異常說明", source_id="turn-3"))

    assert compute_analysis_input_digest(after) != compute_analysis_input_digest(before)


def test_superseding_evidence_changes_the_digest():
    """失效的依據不再投影給模型,輸入因此不同。"""

    superseded = task(
        employee_link(superseded_by=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="t-9")),
        employee_link("其實是每月一次", source_id="t-9"),
    )
    kept = task(
        employee_link(),
        employee_link("其實是每月一次", source_id="t-9"),
    )

    assert compute_analysis_input_digest(superseded) != compute_analysis_input_digest(kept)


def test_non_employee_support_does_not_change_the_digest():
    """0049 決定 13:proposal_decision 不是 Evidence,也就不是分析輸入。"""

    assert compute_analysis_input_digest(
        task(employee_link(), decision_link())
    ) == compute_analysis_input_digest(task(employee_link()))


def test_the_digest_reads_nothing_but_the_task():
    """決定 13–14 的結構保證。

    `CurrentJdOpks`、`OpksProposal` 狀態與 `rejection_reason` 都排除在外——把它們
    納入會分別造成「接受 Proposal → digest 變 → 再分析」的 ping-pong,以及
    「拒絕必帶 reason → digest 變 → 再分析」的付費 reject loop。這裡把「函式除了
    Task 之外拿不到任何東西」釘成簽章層事實,而不是靠呼叫端記得不要傳。
    """

    from inspect import signature

    assert list(signature(compute_analysis_input_digest).parameters) == ["task"]


def test_the_digest_projection_matches_the_packet_projection():
    """決定 12 的「實際投影」必須與 specialist 真正看到的依據同一組。

    兩邊各寫一份篩選遲早失步,gate 就會擋在跟送進模型的輸入不同的東西上。
    """

    subject = task(
        employee_link(),
        decision_link(),
        employee_link(superseded_by=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="t-9")),
        employee_link("其實是每月一次", source_id="t-9"),
    )
    packet = build_opks_context_packet(
        selected_task=subject,
        current_opks=CurrentJdOpks(),
    )

    assert tuple(view.support_link for view in packet.evidence) == (
        subject.effective_employee_support_links
    )


def test_the_digest_is_stable_across_processes():
    """PYTHONHASHSEED 隨機化:內建 `hash()` 每個行程不同,會讓同一輸入付兩次錢。"""

    script = (
        "from app.job_analysis.application import compute_analysis_input_digest;"
        "from app.core.domain import SourceKind, SourceRef, SupportLink, Task;"
        "link=SupportLink(source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN,"
        " id='turn-1'), quote='我每週彙整營運週報');"
        "print(compute_analysis_input_digest(Task(task_id='task-1',"
        " statement='彙整營運週報，提供主管追蹤營運狀況', action='彙整',"
        " object='營運週報', purpose_result='提供主管追蹤營運狀況',"
        " support_links=(link,))))"
    )
    runs = {
        subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            env={"PYTHONHASHSEED": seed, "PYTHONUTF8": "1", "PATH": ""},
        ).stdout.strip()
        for seed in ("0", "12345")
    }

    assert runs == {compute_analysis_input_digest(task())}


def test_child_operation_id_is_derived_from_the_task_and_the_digest():
    """決定 7:child ID 由兩者推導,**不重複持久化**。

    `journal.get()` 因此就是「這個輸入分析過了嗎」的完整答案,不需要新 query port。
    """

    scheduled = ScheduledOpks(task_id="task-1", analysis_input_digest="abc123")

    assert scheduled_opks_operation_id(scheduled) == "opks:auto:task-1:abc123"


def test_the_same_task_and_digest_always_derive_the_same_child_id():
    scheduled = ScheduledOpks(
        task_id="task-1",
        analysis_input_digest=compute_analysis_input_digest(task()),
    )
    replayed = ScheduledOpks(
        task_id="task-1",
        analysis_input_digest=compute_analysis_input_digest(task()),
    )

    assert scheduled_opks_operation_id(scheduled) == scheduled_opks_operation_id(replayed)
