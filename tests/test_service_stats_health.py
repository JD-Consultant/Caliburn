from jd_ocs_indexer.api import service


def test_get_stats(make_qdrant):
    fake = make_qdrant(counts={"__total__": 55, "profile": 5, "task": 50})
    out = service.get_stats(fake, "coll")
    assert out["total_points"] == 55
    assert out["by_level"] == {"profile": 5, "task": 50}


def test_healthcheck_ok(make_qdrant, stub_embedder):
    out = service.healthcheck(make_qdrant(), stub_embedder, "coll")
    assert out["status"] == "ok" and out["model_loaded"] is True
    assert out["qdrant"] == "reachable"


def test_healthcheck_qdrant_down(stub_embedder):
    class Down:
        def get_collections(self):
            raise RuntimeError("boom")

    out = service.healthcheck(Down(), stub_embedder, "coll")
    assert out["status"] == "degraded" and out["qdrant"] == "unreachable"
