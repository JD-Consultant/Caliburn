"""Test evidence isolation and one-shot payment admission, not prompt wording."""

import pytest
import reader_study as study


def test_pair_uses_same_frozen_content_without_grades_or_future_access(tmp_path):
    run_dir = tmp_path / "prepared"
    study.prepare(run_dir)
    cases = study.load(run_dir / "cases.json")
    probe = cases[0]
    first, first_context = study.reader_input(run_dir, probe)
    second, second_context = study.reader_input(run_dir, probe)
    assert first_context == second_context
    assert set(first_context) == {"question", "work_understanding_map"}
    assert first.read_through == 14
    with pytest.raises(ValueError, match="interview_out_of_scope"):
        first.read_interview({"kind": "messages", "sequences": [16]})
    first.objects.clear()
    assert len(second.objects) == 2
    assert len(study.schedule(cases)) == 16


def test_tampered_snapshot_is_rejected_before_network(tmp_path):
    run_dir = tmp_path / "frozen"
    study.prepare(run_dir)
    study.verify(run_dir)
    (run_dir / "workspace-corrections.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Frozen artifact changed"):
        study.verify(run_dir)


@pytest.mark.asyncio
async def test_paid_authorization_cannot_run_in_a_second_directory(tmp_path):
    with pytest.raises(ValueError, match="Only the funded directory"):
        await study.run(tmp_path / "unfunded")


@pytest.mark.asyncio
async def test_started_batch_is_not_replayed(tmp_path, monkeypatch):
    run_dir = tmp_path / "once"
    monkeypatch.setattr(study, "FUNDED_DIRECTORY", run_dir)
    study.prepare(run_dir)
    (run_dir / "started.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError):
        await study.run(run_dir)
