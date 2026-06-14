from jd_ocs_indexer.validation.stats import collection_stats
from tests.conftest import FakeQdrant


def test_collection_stats_counts_profile_and_task():
    fake = FakeQdrant(counts={"__total__": 55, "profile": 5, "task": 50})
    c = collection_stats(fake, "ocs_v3")
    assert c.total_points == 55
    assert c.by_level == {"profile": 5, "task": 50}
