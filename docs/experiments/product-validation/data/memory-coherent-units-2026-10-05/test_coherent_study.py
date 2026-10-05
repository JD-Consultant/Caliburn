"""Offline boundaries for the new paired schedule and frozen input package."""

import coherent_study
import pytest
from coherent_study import (
    Workspace,
    context,
    load,
    prepare,
    prepared_material,
    reader_context,
    run,
    verify,
)


def test_maintainer_and_reader_do_not_receive_grades_or_future_messages():
    material, grading = prepared_material()
    first, second = (
        Workspace("one_collection", material["messages"]) for _ in range(2)
    )
    first.read_through = 10
    reference = context(first, "single", material["batches"][0])
    assert set(reference) == {"資料性質", "maps", "new_interview_messages"}
    assert [
        item["interview_sequence"] for item in reference["new_interview_messages"]
    ] == list(range(1, 11))
    first.invoke(
        "single",
        "create_work_understanding",
        {
            "title": "測試",
            "description": "測試",
            "body": "合成工作",
            "interview_references": [2],
        },
    )
    assert second.map("work_understanding") == {"items": []}
    assert set(reader_context(first, "question")) == {
        "question",
        "work_understanding_map",
    }
    assert len(grading["probe_checks"]) == 4


def test_prepared_artifact_edit_is_rejected_before_run(tmp_path):
    run_dir = tmp_path / "frozen"
    prepare(run_dir)
    verify(run_dir)
    assert (
        load(run_dir / "manifest.json")["budget"]["prior_occupied_usd"] == "1.270089235"
    )
    (run_dir / "instructions.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Frozen artifact changed"):
        verify(run_dir)


@pytest.mark.asyncio
async def test_started_batch_cannot_be_replayed_even_if_it_has_no_results(
    tmp_path, monkeypatch
):
    run_dir = tmp_path / "once"
    monkeypatch.setattr(coherent_study, "FUNDED_DIRECTORY", run_dir)
    prepare(run_dir)
    (run_dir / "started.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError):
        await run(run_dir)


@pytest.mark.asyncio
async def test_another_directory_cannot_reuse_the_paid_authorization(
    tmp_path, monkeypatch
):
    def verification_must_not_be_reached(_):
        raise AssertionError("paid directory boundary bypassed")

    monkeypatch.setattr(coherent_study, "verify", verification_must_not_be_reached)
    with pytest.raises(ValueError, match="Only the funded directory"):
        await run(tmp_path / "another-run")
