"""公版版面的決定性組裝與位置碼（切片 B T1，ADR 0058 決定 1–5）。"""

from __future__ import annotations

from app.job_analysis.application import JobAnalysisState
from app.job_analysis.application.export import assemble_export_document
from app.job_analysis.domain import (
    Duty,
    JdHeader,
    JdTask,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    SourceKind,
    SourceRef,
)


def evidence() -> OpksEvidenceLink:
    return OpksEvidenceLink(
        source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="turn-1"),
        quote="我每週彙整營運週報",
    )


def duty(duty_id: str, order: int, statement: str = "維運門市營運系統") -> Duty:
    return Duty(duty_id=duty_id, statement=statement, display_order=order)


def task(
    task_id: str,
    order: int,
    *,
    duty_id: str | None = None,
    level: int | None = None,
    statement: str = "每週彙整營運週報",
) -> JdTask:
    return JdTask(
        task_id=task_id,
        statement=statement,
        display_order=order,
        duty_id=duty_id,
        competency_level=level,
    )


def opks(
    entity_id: str,
    kind: OpksEntityKind,
    order: int,
    *,
    task_refs: tuple[str, ...] = (),
    text: str = "營運週報",
) -> OpksItem:
    return OpksItem(
        entity_id=entity_id,
        entity_kind=kind,
        text=text,
        display_order=order,
        task_refs=task_refs,
        evidence_links=(evidence(),),
    )


def assemble(state: JobAnalysisState):
    return assemble_export_document(state, title="門市營運專員")


# ── 位置碼 ─────────────────────────────────────────────────────────────────


def test_duty_and_task_codes_renumber_within_each_duty():
    state = JobAnalysisState(
        current_duties=(duty("d1", 0), duty("d2", 1, "處理帳號權限")),
        current_jd=(
            task("t1", 0, duty_id="d1"),
            task("t2", 1, duty_id="d2"),
            task("t3", 2, duty_id="d1"),
        ),
    )

    document = assemble(state)

    assert [section.position_code for section in document.duties] == ["T1", "T2"]
    # T1 底下兩條，各自從 1 重編；T2 底下一條也從 1 開始
    assert [entry.position_code for entry in document.duties[0].tasks] == [
        "T1.1",
        "T1.2",
    ]
    assert [entry.position_code for entry in document.duties[1].tasks] == ["T2.1"]


def test_output_and_indicator_are_three_segment_and_level_with_each_other():
    """官方 F3-3 的 O 與 P 同層三段（ADR 0058 決定 4）。"""

    state = JobAnalysisState(
        current_duties=(duty("d1", 0),),
        current_jd=(task("t1", 0, duty_id="d1"),),
        current_opks={
            "items": (
                opks("o1", OpksEntityKind.OUTPUT, 0, task_refs=("t1",)),
                opks("o2", OpksEntityKind.OUTPUT, 1, task_refs=("t1",)),
                opks("p1", OpksEntityKind.INDICATOR, 0, task_refs=("t1",)),
            )
        },
    )

    entry = assemble(state).duties[0].tasks[0]

    assert [item.position_code for item in entry.outputs] == ["O1.1.1", "O1.1.2"]
    assert [item.position_code for item in entry.indicators] == ["P1.1.1"]


def test_knowledge_and_skills_hang_under_each_task_with_document_level_codes():
    """官方主表的最後兩欄是 K 與 S，**同一個 `K01` 會在多個 Task 列重複出現**。

    這與 ADR 0048 決定 7 一致：「不必複製」講的是 identity（不鑄 `K01-a`／`K01-b`），
    而同一條決定明文允許「UI 可把 K/S 投影在 Task 底下」。逐份核對七份官方範例確認。
    """

    state = JobAnalysisState(
        current_duties=(duty("d1", 0),),
        current_jd=(task("t1", 0, duty_id="d1"), task("t2", 1, duty_id="d1")),
        current_opks={
            "items": (
                opks("k1", OpksEntityKind.KNOWLEDGE, 0, task_refs=("t1", "t2")),
                opks("k2", OpksEntityKind.KNOWLEDGE, 1, task_refs=("t2",)),
                opks("s1", OpksEntityKind.SKILL, 0, task_refs=("t1",)),
                opks("a1", OpksEntityKind.ATTITUDE, 0),
            )
        },
    )

    first, second = assemble(state).duties[0].tasks

    # K01 同時出現在兩個 Task 底下,而且**是同一個碼**
    assert [item.position_code for item in first.knowledge] == ["K01"]
    assert [item.position_code for item in second.knowledge] == ["K01", "K02"]
    assert [item.position_code for item in first.skills] == ["S01"]
    assert second.skills == ()
    assert [item.position_code for item in assemble(state).attitudes] == ["A01"]


def test_knowledge_linked_only_through_an_indicator_still_reaches_its_task():
    """ADR 0048 決定 6：K/S 與 Task／Indicator 多對多。只看 `task_refs` 會漏掉這些。"""

    state = JobAnalysisState(
        current_duties=(duty("d1", 0),),
        current_jd=(task("t1", 0, duty_id="d1"),),
        current_opks={
            "items": (
                opks("p1", OpksEntityKind.INDICATOR, 0, task_refs=("t1",)),
                OpksItem(
                    entity_id="k1",
                    entity_kind=OpksEntityKind.KNOWLEDGE,
                    text="營運指標定義",
                    display_order=0,
                    indicator_refs=("p1",),
                    evidence_links=(evidence(),),
                ),
            )
        },
    )

    document = assemble(state)

    assert [item.position_code for item in document.duties[0].tasks[0].knowledge] == [
        "K01"
    ]
    assert document.unlinked_knowledge == ()


def test_knowledge_that_reaches_no_task_is_still_carried():
    """主表放不下它，但不得從成品上消失。"""

    state = JobAnalysisState(
        current_duties=(duty("d1", 0),),
        current_jd=(task("t1", 0, duty_id="d1"),),
        current_opks={
            "items": (
                opks("k1", OpksEntityKind.KNOWLEDGE, 0, task_refs=("t1",)),
                opks("k2", OpksEntityKind.KNOWLEDGE, 1, text="孤兒知識"),
                opks("s1", OpksEntityKind.SKILL, 0, text="孤兒技能"),
            )
        },
    )

    document = assemble(state)

    assert [item.position_code for item in document.unlinked_knowledge] == ["K02"]
    assert [item.text for item in document.unlinked_skills] == ["孤兒技能"]
    # 已連結的沒有被重複列進未連結區
    assert "K01" not in [item.position_code for item in document.unlinked_knowledge]


def test_no_competency_is_ever_lost():
    state = JobAnalysisState(
        current_duties=(duty("d1", 0),),
        current_jd=(task("t1", 0, duty_id="d1"), task("t2", 1)),
        current_opks={
            "items": (
                opks("k1", OpksEntityKind.KNOWLEDGE, 0, task_refs=("t1",)),
                opks("k2", OpksEntityKind.KNOWLEDGE, 1, task_refs=("t2",)),
                opks("k3", OpksEntityKind.KNOWLEDGE, 2, text="孤兒"),
            )
        },
    )

    document = assemble(state)
    seen = {
        item.position_code
        for section in document.duties
        for entry in section.tasks
        for item in entry.knowledge
    }
    seen |= {
        item.position_code
        for entry in document.unassigned_tasks
        for item in entry.knowledge
    }
    seen |= {item.position_code for item in document.unlinked_knowledge}

    assert seen == {"K01", "K02", "K03"}


def test_codes_follow_display_order_not_tuple_order():
    """`CurrentJdOpks` 不保證 tuple 已排好，位置碼的正確性由組裝端明確排序負責。"""

    state = JobAnalysisState(
        current_duties=(duty("d1", 0),),
        current_jd=(task("t1", 0, duty_id="d1"),),
        current_opks={
            "items": (
                opks("o-late", OpksEntityKind.OUTPUT, 1, task_refs=("t1",), text="第二"),
                opks("o-first", OpksEntityKind.OUTPUT, 0, task_refs=("t1",), text="第一"),
            )
        },
    )

    outputs = assemble(state).duties[0].tasks[0].outputs

    assert [item.text for item in outputs] == ["第一", "第二"]
    assert [item.position_code for item in outputs] == ["O1.1.1", "O1.1.2"]


# ── 未指派主要職責 ─────────────────────────────────────────────────────────


def test_an_unassigned_task_keeps_its_content_but_gets_no_code():
    """不得為了湊位置碼而虛構 Duty（ADR 0052 決定 13 的匯出端體現）。"""

    state = JobAnalysisState(
        current_duties=(duty("d1", 0),),
        current_jd=(task("t1", 0, duty_id="d1"), task("t2", 1, statement="盤點耗材")),
        current_opks={
            "items": (opks("o1", OpksEntityKind.OUTPUT, 0, task_refs=("t2",)),)
        },
    )

    document = assemble(state)

    assert [entry.task_id for entry in document.unassigned_tasks] == ["t2"]
    orphan = document.unassigned_tasks[0]
    assert orphan.position_code is None
    assert orphan.statement == "盤點耗材"
    # 排不進表格不是把內容刪掉的理由——O 仍然帶出來,只是沒有位置碼
    assert [item.text for item in orphan.outputs] == ["營運週報"]
    assert orphan.outputs[0].position_code is None


def test_no_task_is_ever_lost_or_duplicated():
    state = JobAnalysisState(
        current_duties=(duty("d1", 0), duty("d2", 1, "處理帳號權限")),
        current_jd=(
            task("t1", 0, duty_id="d1"),
            task("t2", 1),
            task("t3", 2, duty_id="d2"),
            task("t4", 3),
        ),
    )

    document = assemble(state)
    seen = [
        entry.task_id
        for section in document.duties
        for entry in section.tasks
    ] + [entry.task_id for entry in document.unassigned_tasks]

    assert sorted(seen) == ["t1", "t2", "t3", "t4"]
    assert len(set(seen)) == len(seen)


def test_an_empty_duty_still_appears():
    """空職責就是 readiness 的 `duty_without_task`——藏起來缺漏就看不見了。"""

    state = JobAnalysisState(current_duties=(duty("d1", 0),))

    document = assemble(state)

    assert len(document.duties) == 1
    assert document.duties[0].tasks == ()


# ── 邊界與決定性 ───────────────────────────────────────────────────────────


def test_an_empty_document_assembles_without_raising():
    document = assemble(JobAnalysisState())

    assert document.duties == ()
    assert document.unassigned_tasks == ()
    assert document.unlinked_knowledge == ()
    assert document.attitudes == ()
    assert document.header == JdHeader()


def test_the_header_is_carried_through_untouched():
    header = JdHeader(competency_name="門市營運專員", competency_level=4)
    state = JobAnalysisState(jd_header=header)

    assert assemble(state).header == header


def test_assembly_is_deterministic():
    state = JobAnalysisState(
        current_duties=(duty("d1", 0),),
        current_jd=(task("t1", 0, duty_id="d1", level=4),),
        current_opks={
            "items": (opks("o1", OpksEntityKind.OUTPUT, 0, task_refs=("t1",)),)
        },
    )

    assert assemble(state) == assemble(state)


def test_the_task_competency_level_is_projected():
    state = JobAnalysisState(
        current_duties=(duty("d1", 0),),
        current_jd=(task("t1", 0, duty_id="d1", level=4),),
    )

    assert assemble(state).duties[0].tasks[0].competency_level == 4
