from jd_ocs_indexer.api import service


def _payload(**over):
    p = {
        "chunk_key": "k", "chunk_level": "profile", "ocs_code": "OC1", "job_title": "JT",
        "version": "v1", "is_current": True, "ocs_level": 5,
        "k_pairs": [{"code": "K01", "name": "n"}], "s_pairs": [],
        "industry_names": ["ind"], "occupation_names": ["occ"],
        "source_file": "f.json", "text": "# JT (OC1)\nline1\nline2\nline3",
    }
    p.update(over)
    return p


def test_search_dense_projection(make_qdrant, fake_point, stub_embedder):
    fake = make_qdrant(query_points=[fake_point(payload=_payload(), score=0.9)])
    out = service.search(fake, stub_embedder, "coll", query="hi", hybrid=False, top_k=5)
    assert out["mode"] == "dense"
    h = out["hits"][0]
    assert h["ocs_code"] == "OC1" and h["score"] == 0.9
    assert h["k_pairs"] == [{"code": "K01", "name": "n"}]
    assert h["snippet"] is None


def test_search_hybrid_mode(make_qdrant, fake_point, stub_embedder):
    fake = make_qdrant(query_points=[fake_point(payload=_payload(), score=0.5)])
    out = service.search(fake, stub_embedder, "coll", query="hi", hybrid=True)
    assert out["mode"] == "hybrid"


def test_search_include_text_snippet(make_qdrant, fake_point, stub_embedder):
    fake = make_qdrant(query_points=[fake_point(payload=_payload(), score=0.5)])
    out = service.search(fake, stub_embedder, "coll", query="hi", include_text=True, text_lines=2)
    assert out["hits"][0]["snippet"] == "line1\nline2"
