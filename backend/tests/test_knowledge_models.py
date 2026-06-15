from app.services.knowledge.models import SearchResult, TaskDetail, Pairs


def test_search_result_parses_and_ignores_extra():
    r = SearchResult.model_validate({
        "mode": "hybrid",
        "hits": [{"id": "p1", "score": 0.9, "chunk_level": "task",
                  "ocs_code": "OC1", "task_id": "T1", "task_title": "做事",
                  "job_title": "工程師", "unexpected": "ok"}],
    })
    assert r.mode == "hybrid"
    assert r.hits[0].id == "p1" and r.hits[0].task_title == "做事"


def test_pairs_parses_code_name_dicts():
    p = Pairs.model_validate({
        "ocs_code": "OC1",
        "knowledge": [{"code": "K01", "name": "知識一"}],
        "skills": [], "attitudes": [], "outputs": [],
        "prerequisites": ["需先具備X"], "supplements": [],
    })
    assert p.knowledge[0].code == "K01" and p.prerequisites == ["需先具備X"]


def test_task_detail_parses():
    t = TaskDetail.model_validate({
        "id": "OC1-T1.1", "ocs_code": "OC1", "task_id": "T1.1", "task_title": "t",
        "competency_level": 3, "activity_examples": ["a"],
        "k_pairs": [{"code": "K01", "name": "k"}], "s_pairs": [], "output_pairs": [],
    })
    assert t.competency_level == 3 and t.k_pairs[0].name == "k"
