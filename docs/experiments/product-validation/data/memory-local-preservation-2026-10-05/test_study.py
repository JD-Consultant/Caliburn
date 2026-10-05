"""Integration characterization of reused admission and new frozen inputs."""

import pytest
import study


def test_new_inputs_are_frozen_before_run(tmp_path):
    directory = tmp_path / "trial"
    study.prepare(directory)
    study.verify(directory)
    (directory / "cases.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="Frozen input changed"):
        study.verify(directory)


@pytest.mark.asyncio
async def test_other_directory_never_reaches_paid_execution(tmp_path):
    with pytest.raises(ValueError, match="Only the funded directory"):
        await study.run(tmp_path)


@pytest.mark.asyncio
async def test_started_batch_cannot_be_replayed(tmp_path, monkeypatch):
    directory = tmp_path / "trial"
    study.prepare(directory)
    monkeypatch.setattr(study, "FUNDED", directory)
    (directory / "started.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError):
        await study.run(directory)
