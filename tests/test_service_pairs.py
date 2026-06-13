from jd_ocs_indexer.api import service


def test_get_pairs_returns_pools(make_qdrant):
    profile = {
        "ocs_code": "OC1", "chunk_level": "profile", "job_title": "JT",
        "all_k_pairs": [{"code": "K01", "name": "n"}], "all_s_pairs": [],
        "all_a_pairs": [{"code": "A01", "name": "a"}], "all_output_pairs": [],
    }
    fake = make_qdrant(scroll_pages=[([profile], None)])
    out = service.get_pairs(fake, "coll", ocs_code="OC1")
    assert out["job_title"] == "JT"
    assert out["all_k_pairs"] == [{"code": "K01", "name": "n"}]
    assert out["all_a_pairs"][0]["code"] == "A01"


def test_get_pairs_missing_returns_none(make_qdrant):
    fake = make_qdrant(scroll_pages=[([], None)])
    assert service.get_pairs(fake, "coll", ocs_code="NOPE") is None
