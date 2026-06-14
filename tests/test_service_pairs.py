from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint


def test_get_pairs_unions_task_pairs_plus_profile_attitudes():
    profile = [FakePoint(payload={
        "chunk_level": "profile", "ocs_code": "OC1", "job_title": "JT",
        "all_a_pairs": [{"code": "A01", "name": "主動"}],
    })]
    tasks = [
        FakePoint(payload={"chunk_level": "task", "ocs_code": "OC1",
                           "k_pairs": [{"code": "K01", "name": "k1"}], "s_pairs": [{"code": "S01", "name": "s1"}],
                           "output_pairs": [{"code": "O01", "name": "o1"}]}),
        FakePoint(payload={"chunk_level": "task", "ocs_code": "OC1",
                           "k_pairs": [{"code": "K01", "name": "k1"}, {"code": "K02", "name": "k2"}],
                           "s_pairs": [], "output_pairs": []}),
    ]
    # get_pairs scrolls profile (limit 1) then task points
    fake = FakeQdrant(scroll_pages=[(profile, None), (tasks, None)])
    out = service.get_pairs(fake, "ocs_v3", ocs_code="OC1")
    assert out["job_title"] == "JT"
    assert [p["code"] for p in out["all_k_pairs"]] == ["K01", "K02"]   # deduped, in order
    assert [p["code"] for p in out["all_s_pairs"]] == ["S01"]
    assert [p["code"] for p in out["all_output_pairs"]] == ["O01"]
    assert out["all_a_pairs"] == [{"code": "A01", "name": "主動"}]


def test_get_pairs_missing_profile_returns_none():
    fake = FakeQdrant(scroll_pages=[([], None)])
    assert service.get_pairs(fake, "ocs_v3", ocs_code="NOPE") is None
