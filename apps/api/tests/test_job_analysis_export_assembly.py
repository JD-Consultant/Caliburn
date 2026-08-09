"""公版欄位的決定性組裝與 render-time 位置碼。"""

from __future__ import annotations

from app.job_analysis.application import JobAnalysisState
from app.job_analysis.application.export import assemble_export_document
from app.job_analysis.domain import (
    CurrentJdOpks,
    Duty,
    JdHeader,
    JdTask,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    SourceKind,
    SourceRef,
)


def _evidence() -> OpksEvidenceLink:
    return OpksEvidenceLink(
        source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="turn-1"),
        quote="我每週彙整營運週報",
    )


def _duty(duty_id: str, order: int, statement: str = "維運門市營運系統") -> Duty:
    return Duty(duty_id=duty_id, statement=statement, display_order=order)


def _task(
    task_id: str,
    order: int,
    *,
    duty_id: str | None = None,
    competency_level: int | None = None,
    statement: str = "每週彙整營運週報",
) -> JdTask:
    return JdTask(
        task_id=task_id,
        statement=statement,
        display_order=order,
        duty_id=duty_id,
        competency_level=competency_level,
    )


def _opks(
    entity_id: str,
    kind: OpksEntityKind,
    order: int,
    *,
    task_refs: tuple[str, ...] = (),
    indicator_refs: tuple[str, ...] = (),
    text: str = "營運週報",
) -> OpksItem:
    return OpksItem(
        entity_id=entity_id,
        entity_kind=kind,
        text=text,
        display_order=order,
        task_refs=task_refs,
        indicator_refs=indicator_refs,
        evidence_links=(_evidence(),),
    )


def _assemble(state: JobAnalysisState):
    return assemble_export_document(state, title="門市營運專員")


def _state(**kwargs) -> JobAnalysisState:
    kwargs.setdefault("jd_header", JdHeader())
    return JobAnalysisState(**kwargs)


def test_position_codes_are_render_time_only_and_follow_display_order():
    state = _state(
        current_duties=(_duty("d1", 0),),
        current_jd=(_task("t1", 0, duty_id="d1"),),
        current_opks=CurrentJdOpks(
            items=(
                _opks("o-late", OpksEntityKind.OUTPUT, 1, task_refs=("t1",), text="第二"),
                _opks("o-first", OpksEntityKind.OUTPUT, 0, task_refs=("t1",), text="第一"),
                _opks("p1", OpksEntityKind.INDICATOR, 0, task_refs=("t1",)),
            )
        ),
    )

    document = _assemble(state)
    task = document.duties[0].tasks[0]

    assert document.duties[0].position_code == "T1"
    assert task.position_code == "T1.1"
    assert [item.position_code for item in task.outputs] == ["O1.1.1", "O1.1.2"]
    assert [item.text for item in task.outputs] == ["第一", "第二"]
    assert task.indicators[0].position_code == "P1.1.1"
    assert not hasattr(state.current_jd[0], "position_code")


def test_duties_and_tasks_are_renumbered_by_their_explicit_orders():
    state = _state(
        current_duties=(_duty("d1", 0), _duty("d2", 1, "處理帳號權限")),
        current_jd=(
            _task("t1", 0, duty_id="d1"),
            _task("t2", 1, duty_id="d2"),
            _task("t3", 2, duty_id="d1"),
        ),
    )

    document = _assemble(state)

    assert [section.position_code for section in document.duties] == ["T1", "T2"]
    assert [task.position_code for task in document.duties[0].tasks] == [
        "T1.1",
        "T1.2",
    ]
    assert [task.position_code for task in document.duties[1].tasks] == ["T2.1"]


def test_shared_knowledge_and_skills_keep_one_document_level_code():
    state = _state(
        current_duties=(_duty("d1", 0),),
        current_jd=(
            _task("t1", 0, duty_id="d1"),
            _task("t2", 1, duty_id="d1"),
        ),
        current_opks=CurrentJdOpks(
            items=(
                _opks("k1", OpksEntityKind.KNOWLEDGE, 0, task_refs=("t1", "t2")),
                _opks("k2", OpksEntityKind.KNOWLEDGE, 1, task_refs=("t2",)),
                _opks("s1", OpksEntityKind.SKILL, 0, task_refs=("t1",)),
                _opks("a1", OpksEntityKind.ATTITUDE, 0),
            )
        ),
    )

    first, second = _assemble(state).duties[0].tasks

    assert [item.position_code for item in first.knowledge] == ["K01"]
    assert [item.position_code for item in second.knowledge] == ["K01", "K02"]
    assert first.knowledge[0].text == second.knowledge[0].text
    assert [item.position_code for item in first.skills] == ["S01"]
    assert second.skills == ()


def test_indicator_refs_resolve_knowledge_back_to_the_task():
    state = _state(
        current_duties=(_duty("d1", 0),),
        current_jd=(_task("t1", 0, duty_id="d1"),),
        current_opks=CurrentJdOpks(
            items=(
                _opks("p1", OpksEntityKind.INDICATOR, 0, task_refs=("t1",)),
                _opks(
                    "k1",
                    OpksEntityKind.KNOWLEDGE,
                    0,
                    indicator_refs=("p1",),
                    text="營運指標定義",
                ),
            )
        ),
    )

    document = _assemble(state)

    assert [item.position_code for item in document.duties[0].tasks[0].knowledge] == [
        "K01"
    ]


def test_unlinked_knowledge_and_skills_are_not_in_public_projection():
    state = _state(
        current_duties=(_duty("d1", 0),),
        current_jd=(_task("t1", 0, duty_id="d1"),),
        current_opks=CurrentJdOpks(
            items=(
                _opks("k1", OpksEntityKind.KNOWLEDGE, 0, task_refs=("t1",)),
                _opks("k2", OpksEntityKind.KNOWLEDGE, 1, text="孤兒知識"),
                _opks("s1", OpksEntityKind.SKILL, 0, text="孤兒技能"),
            )
        ),
    )

    document = _assemble(state)
    dumped = document.model_dump()

    assert [item.position_code for item in document.duties[0].tasks[0].knowledge] == [
        "K01"
    ]
    assert "孤兒知識" not in str(dumped)
    assert "孤兒技能" not in str(dumped)
    assert "unlinked_knowledge" not in dumped
    assert "unlinked_skills" not in dumped


def test_unassigned_task_is_preserved_with_blank_duty_and_position_codes():
    state = _state(
        current_duties=(_duty("d1", 0),),
        current_jd=(
            _task("t1", 0, duty_id="d1"),
            _task("t2", 1, statement="盤點耗材"),
        ),
        current_opks=CurrentJdOpks(
            items=(_opks("o1", OpksEntityKind.OUTPUT, 0, task_refs=("t2",)),)
        ),
    )

    document = _assemble(state)

    assert [task.task_id for task in document.unassigned_tasks] == ["t2"]
    task = document.unassigned_tasks[0]
    assert task.position_code is None
    assert task.statement == "盤點耗材"
    assert task.outputs[0].position_code is None


def test_empty_duty_and_task_level_are_projected_without_inventing_values():
    state = JobAnalysisState(
        jd_header=JdHeader(competency_name="門市營運專員"),
        current_duties=(_duty("d1", 0),),
        current_jd=(_task("t1", 0, duty_id="d1"),),
    )

    document = _assemble(state)

    assert document.duties[0].tasks[0].competency_level is None
    assert document.header == state.jd_header
    assert document.attitudes == ()
