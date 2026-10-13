from pathlib import Path
from unittest.mock import Mock

import pytest

from jd_ocs_indexer.config import load_settings
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


def test_payload_index_failure_stops_before_reading_or_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jd_ocs_indexer import pipeline
    from jd_ocs_indexer.store import manifest

    client = Mock()
    client.collection_exists.return_value = True
    client.create_payload_index.side_effect = ConnectionError("index unavailable")
    embedder = Mock(dense_size=4, supports_sparse=False)
    reader = Mock()
    reader.iter_loaded.return_value = []
    monkeypatch.setattr(pipeline, "OCSJSONReader", Mock(return_value=reader))
    write_manifest = Mock()
    monkeypatch.setattr(manifest, "write_manifest", write_manifest)

    with pytest.raises(ConnectionError, match="index unavailable"):
        run_index(load_settings(), tmp_path, embedder=embedder, client=client)

    reader.iter_loaded.assert_not_called()
    embedder.embed_texts.assert_not_called()
    client.upsert.assert_not_called()
    write_manifest.assert_not_called()


@pytest.mark.parametrize(
    "borrow_embedder,borrow_client",
    [(False, False), (False, True), (True, False), (True, True)],
)
@pytest.mark.parametrize("bootstrap_fails", [False, True])
def test_pipeline_closes_only_owned_resources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    borrow_embedder: bool,
    borrow_client: bool,
    bootstrap_fails: bool,
) -> None:
    from jd_ocs_indexer import pipeline

    embedder = Mock(dense_size=4, supports_sparse=False)
    client = Mock()
    client.collection_exists.return_value = True
    if bootstrap_fails:
        client.collection_exists.side_effect = ConnectionError("bootstrap unavailable")
    monkeypatch.setattr(pipeline, "make_embedder", Mock(return_value=embedder))
    monkeypatch.setattr(pipeline, "make_client", Mock(return_value=client))

    kwargs = {
        "embedder": embedder if borrow_embedder else None,
        "client": client if borrow_client else None,
    }
    if bootstrap_fails:
        with pytest.raises(ConnectionError, match="bootstrap unavailable"):
            run_index(load_settings(), tmp_path, **kwargs)
    else:
        assert run_index(load_settings(), tmp_path, **kwargs).indexed_files == 0

    assert embedder.close.call_count == (0 if borrow_embedder else 1)
    assert client.close.call_count == (0 if borrow_client else 1)


def test_client_construction_failure_closes_created_embedder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jd_ocs_indexer import pipeline

    embedder = Mock()
    monkeypatch.setattr(pipeline, "make_embedder", Mock(return_value=embedder))
    monkeypatch.setattr(
        pipeline, "make_client", Mock(side_effect=ConnectionError("client unavailable"))
    )

    with pytest.raises(ConnectionError, match="client unavailable"):
        run_index(load_settings(), tmp_path)

    embedder.close.assert_called_once_with()
