"""Integration checks for frozen artifacts; supplements the test-first guard."""

import layered_study
import pytest


def test_frozen_artifacts_and_same_reader_cannot_be_changed(tmp_path):
    directory = tmp_path / "frozen"
    layered_study.prepare(directory)
    layered_study.verify(directory)
    prompts = layered_study.load(directory / "instructions.json")
    assert set(prompts) == {"b1", "b2", "reader"}
    material = layered_study.load(directory / "materials.json")
    assert len(material["probes"]) == 4
    assert [batch["read_through_sequence"] for batch in material["batches"]] == [
        10,
        14,
        18,
    ]
    assert (
        layered_study.load(directory / "manifest.json")["budget"]["max_additional_usd"]
        == "0.10"
    )
    (directory / "instructions.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Frozen artifact changed"):
        layered_study.verify(directory)


@pytest.mark.asyncio
async def test_runner_rejects_unfunded_directory_before_verification(
    tmp_path, monkeypatch
):
    def must_not_reach(_):
        raise AssertionError("directory check bypassed")

    monkeypatch.setattr(layered_study, "verify", must_not_reach)
    with pytest.raises(ValueError, match="Only the funded directory"):
        await layered_study.run(tmp_path)


@pytest.mark.asyncio
async def test_runner_cannot_replay_started_batch(tmp_path, monkeypatch):
    directory = tmp_path / "started"
    layered_study.prepare(directory)
    monkeypatch.setattr(layered_study, "FUNDED_DIRECTORY", directory)
    (directory / "started.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError):
        await layered_study.run(directory)
