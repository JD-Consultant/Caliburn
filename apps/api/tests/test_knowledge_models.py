def test_competency_pool_parses_citable_items():
    from app.core.knowledge_dto import CompetencyPool
    p = CompetencyPool.model_validate({
        "ocs_code": "OC1",
        "knowledge": [{"id": "ocs:OC1:K:K01", "type": "K", "code": "K01", "name": "k1",
                       "ocs_code": "OC1", "ocs_name": "JT",
                       "sources": [{"task_code": "T1.1", "competency_level": 3}]}],
        "skills": [], "outputs": [], "indicators": [], "attitudes": [], "extra": "ok"})
    assert p.knowledge[0].code == "K01"
    assert p.knowledge[0].sources[0].task_code == "T1.1"


def test_occupation_detail_parses_nested_ocs_name():
    from app.core.knowledge_dto import OccupationDetail
    d = OccupationDetail.model_validate({
        "ocs_code": "OC1", "urn": "ocs:OC1",
        "ocs_name": {"job_category_name": None, "occupation_name": "資料分析師"},
        "job_categories": [{"code": "JC1", "name": "資訊類"}],
        "occupations": [], "industries": [], "attitudes": [],
        "job_description": "x", "ocs_level": 4, "prerequisites": ["a"], "supplements": []})
    assert d.ocs_name.occupation_name == "資料分析師" and d.ocs_level == 4
    assert d.job_categories[0].code == "JC1" and d.prerequisites == ["a"]
