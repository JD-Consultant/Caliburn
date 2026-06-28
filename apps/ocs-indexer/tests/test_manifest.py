from jd_ocs_indexer.embeddings.base import EmbeddingSignature
from jd_ocs_indexer.store import manifest as M


def test_bge_signature():
    from jd_ocs_indexer.embeddings.bge_m3 import BGEM3Embedder

    sig = BGEM3Embedder(model_name="BAAI/bge-m3").signature
    assert sig == EmbeddingSignature(provider="bge-m3", model="BAAI/bge-m3", dim=1024, revision=1)


def test_manifest_round_trip():
    from tests.conftest import FakePoint

    sig = EmbeddingSignature("bge-m3", "BAAI/bge-m3", 1024, 1)
    captured: dict = {}

    class C:
        def upsert(self, **kw):
            captured["points"] = kw["points"]

        def retrieve(self, **kw):
            pts = captured.get("points") or []
            return [FakePoint(payload=p.payload) for p in pts]

    c = C()
    M.write_manifest(c, "ocs_v3", sig)
    assert M.read_manifest(c, "ocs_v3") == sig
