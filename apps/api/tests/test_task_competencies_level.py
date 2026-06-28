from app.core.knowledge_dto import CitableItem, CompetencyPool, SourceRef
from app.services.knowledge.task_detail import task_competencies


def _pool() -> CompetencyPool:
    return CompetencyPool(
        ocs_code="INM3513-009v1",
        knowledge=[
            CitableItem(code="K01", name="net", sources=[SourceRef(task_code="T1.1", competency_level=3)]),
            CitableItem(code="K02", name="other", sources=[SourceRef(task_code="T2.1", competency_level=5)]),
        ],
        skills=[],
        outputs=[],
        indicators=[],
    )


def test_task_competencies_returns_level_for_task():
    detail = task_competencies(_pool(), "T1.1")
    assert detail["competency_level"] == 3


def test_task_competencies_level_none_when_no_match():
    detail = task_competencies(_pool(), "T9.9")
    assert detail["competency_level"] is None
