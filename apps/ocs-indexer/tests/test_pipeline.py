from pathlib import Path

from jd_ocs_indexer.pipeline import IndexReport, run_index


def test_run_index_empty_dir_reports_zero(tmp_path: Path, stub_embedder, monkeypatch):
    from jd_ocs_indexer import pipeline

    class _W:  # writer stand-in — empty dir means it must never upsert
        def __init__(self, *a, **k):
            pass

        def ensure_collection(self):
            pass

        def ensure_payload_indexes(self, *a, **k):
            pass

        def upsert(self, chunks):
            raise AssertionError("no files → no upsert")

    monkeypatch.setattr(pipeline, "QdrantWriter", _W)
    from jd_ocs_indexer.config import load_settings

    rep = run_index(load_settings(), tmp_path, embedder=stub_embedder, client=object())
    assert isinstance(rep, IndexReport)
    assert rep.indexed_files == 0
    assert rep.points == 0
    assert rep.failures == []
