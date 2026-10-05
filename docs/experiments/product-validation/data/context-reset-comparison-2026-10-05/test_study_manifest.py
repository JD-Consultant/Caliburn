"""The paid runner must reject changed sources and replay of an already started batch."""

import json

import pytest
from study_manifest import claim_run, freeze_files, verify_files


def test_new_migration_is_not_silently_added_to_a_frozen_run(tmp_path):
    from prepare_study import verify_code_inventory

    original = tmp_path / "original.py"
    added = tmp_path / "new_migration.py"
    original.write_text("pass", encoding="utf-8")
    records = freeze_files([original], root=tmp_path, output=tmp_path / "prepared")
    added.write_text("pass", encoding="utf-8")
    with pytest.raises(ValueError, match="source_inventory_changed"):
        verify_code_inventory(records, [original, added], root=tmp_path)


def test_freeze_preserves_content_and_detects_change(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("old", encoding="utf-8")
    output = tmp_path / "prepared"
    records = freeze_files([source], root=tmp_path, output=output)
    verify_files(records, root=tmp_path)
    source.write_text("new", encoding="utf-8")
    with pytest.raises(ValueError, match="source_changed"):
        verify_files(records, root=tmp_path)
    import zipfile

    with zipfile.ZipFile(output / "sources.zip") as archive:
        assert archive.read("source.txt") == b"old"
    with pytest.raises(FileExistsError):
        freeze_files([source], root=tmp_path, output=output)


def test_only_one_run_can_claim_a_prepared_directory(tmp_path):
    claim_run(tmp_path, {"budget": "0.20", "seconds": 1800})
    first = (tmp_path / "started.json").read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        claim_run(tmp_path, {"budget": "0.40"})
    assert json.loads(first)["budget"] == "0.20"


def test_freeze_rejects_files_outside_repo(tmp_path):
    source = tmp_path / "outside.txt"
    source.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        freeze_files([source], root=tmp_path / "repo", output=tmp_path / "prepared")
