from app.core.knowledge_dto import CitableItem, CompetencyPool, SourceRef
from app.services.knowledge.task_detail import task_competencies


def _item(type_, code, *, name=None, text=None, task_codes=()):
    return CitableItem(id=f"ocs:OC1:{type_}:{code}", type=type_, code=code, name=name,
                       text=text, ocs_code="OC1", ocs_name="JT",
                       sources=[SourceRef(task_code=tc) for tc in task_codes])


def test_task_competencies_filters_by_task_code():
    pool = CompetencyPool(
        ocs_code="OC1",
        knowledge=[_item("K", "K01", name="k1", task_codes=["T1.1", "T1.2"]),
                   _item("K", "K02", name="k2", task_codes=["T1.2"])],
        skills=[_item("S", "S01", name="s1", task_codes=["T1.1"])],
        outputs=[_item("O", "O01", name="o1", task_codes=["T1.1"])],
        indicators=[_item("P", "P01", text="p text", task_codes=["T1.1"])])
    out = task_competencies(pool, "T1.1")
    assert out["knowledge"] == [{"code": "K01", "name": "k1"}]
    assert out["skills"] == [{"code": "S01", "name": "s1"}]
    assert out["outputs"] == [{"code": "O01", "name": "o1"}]
    assert out["indicators"] == [{"code": "P01", "text": "p text"}]


def test_task_competencies_unknown_task_code_is_empty():
    pool = CompetencyPool(ocs_code="OC1",
                          knowledge=[_item("K", "K01", name="k1", task_codes=["T1.1"])])
    assert task_competencies(pool, "T9.9") == {
        "knowledge": [], "skills": [], "outputs": [], "indicators": [], "competency_level": None}
