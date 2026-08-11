# tests/test_occupation_search.py
from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint, StubEmbedder

def test_search_occupations_projects_hits_with_raw_score():
    hit = FakePoint(payload={"chunk_level": "profile", "ocs_code": "OC1",
                             "ocs_name": {"occupation_name": "資料分析師"},
                             "job_description": "負責資料分析", "ocs_level": 4}, score=0.83)
    fake = FakeQdrant(query_points=[hit])
    out = service.search_occupations(fake, StubEmbedder(), "ocs_v3", query="資料", top_k=5)
    h = out["hits"][0]
    assert h["ocs_code"] == "OC1" and h["urn"] == "ocs:OC1"
    assert h["ocs_name"] == "資料分析師" and h["job_description"] == "負責資料分析"
    assert h["ocs_level"] == 4 and h["score"] == 0.83
