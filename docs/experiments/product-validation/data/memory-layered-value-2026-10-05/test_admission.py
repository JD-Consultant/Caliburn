"""No network is needed to enforce one-shot execution."""

import pytest
from admission import claim_run


def test_unfunded_directory_never_creates_start_marker(tmp_path):
    with pytest.raises(ValueError, match="funded"):
        claim_run(tmp_path, tmp_path / "funded")
    assert not (tmp_path / "started.json").exists()


def test_funded_directory_cannot_be_replayed(tmp_path):
    claim_run(tmp_path, tmp_path)
    original = (tmp_path / "started.json").read_bytes()
    with pytest.raises(FileExistsError):
        claim_run(tmp_path, tmp_path)
    assert (tmp_path / "started.json").read_bytes() == original
