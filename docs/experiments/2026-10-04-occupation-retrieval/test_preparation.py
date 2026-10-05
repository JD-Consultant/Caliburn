import pytest

from evaluation import fuse_rankings
from prepare import memory_case


def test_zero_sparse_scores_have_no_vote():
    dense = [("Z", 1), ("A", .9), ("B", .8), ("C", .7)]
    sparse = [("A", 0), ("B", 0), ("C", 0), ("Z", 0)]
    assert fuse_rankings(dense, sparse)[0] == ("Z", 1 / 60)


@pytest.mark.parametrize("revision", ["right", "wrong"])
def test_every_b1_reference_must_resolve_at_exact_published_revision(revision):
    snapshot = {"snapshot": {}, "objects": [
        {"object_id": "b2", "layer": "work_understanding", "content": {"body": "內容"},
         "work_situation_references": [{"object_id": "a", "revision_id": "right"},
                                       {"object_id": "missing", "revision_id": "r"}]},
        {"object_id": "a", "revision_id": revision, "layer": "work_situation", "content": {"body": "情境"}},
    ]}
    with pytest.raises(ValueError):
        memory_case("test", "test", snapshot, "基準", [], {}, "", [])
