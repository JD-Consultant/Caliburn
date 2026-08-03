"""R1 fixture authority and runtime/evaluation isolation tests."""

from __future__ import annotations

from pathlib import Path
import shutil

from evals.professional_consultant.r1.contracts import SourceType
from evals.professional_consultant.r1.loader import (
    load_evaluation_suite,
    load_job_analysis_rubric,
    load_runtime_case,
    load_runtime_suite,
)


CASES_ROOT = (
    Path(__file__).parents[1]
    / "evals"
    / "professional_consultant"
    / "r1"
    / "cases"
)


def test_runtime_suite_loads_the_eight_re_adjudicated_r1_cases() -> None:
    cases = load_runtime_suite(CASES_ROOT)

    assert [case.metadata.case_id for case in cases] == [
        "TI-R1-01-tools-not-task",
        "TI-R1-02-tool-work-with-outcome",
        "TI-R1-03-one-story-multiple-work",
        "TI-R1-04-multiple-stories-one-task",
        "TI-R1-05-past-work",
        "TI-R1-06-other-person-handoff",
        "TI-R1-07-one-off-support",
        "TI-R1-08-correction",
    ]
    assert all(
        case.metadata.source_type is SourceType.CONSTRUCTED_EDGE for case in cases
    )
    assert all(case.runtime_input.schema_version == "task_discovery_input.v1" for case in cases)


def test_runtime_loader_is_blind_to_expectations_and_adjudication(tmp_path: Path) -> None:
    copied = tmp_path / "TI-R1-01-tools-not-task"
    shutil.copytree(CASES_ROOT / copied.name, copied)
    (copied / "expectations.json").write_text("not-json", encoding="utf-8")
    (copied / "adjudication.md").write_text(
        "GOLD_ONLY_SENTINEL", encoding="utf-8"
    )

    runtime = load_runtime_case(copied)

    assert runtime.metadata.case_id == copied.name
    assert "GOLD_ONLY_SENTINEL" not in repr(runtime)
    assert not hasattr(runtime, "expectations")


def test_evaluation_suite_and_quality_rubric_are_separate_authorities() -> None:
    evaluations = load_evaluation_suite(CASES_ROOT)
    rubric = load_job_analysis_rubric(CASES_ROOT.parent / "rubric")

    assert len(evaluations) == 8
    assert all(
        item.expectations.case_id == item.metadata.case_id for item in evaluations
    )
    assert all(item.adjudication_markdown.startswith("# ") for item in evaluations)
    assert rubric.schema_version == "job_analysis_quality_rubric.v1"
    assert {rule.code for rule in rubric.critical_rules} == {
        "tool_as_task",
        "step_as_task",
        "past_work_leakage",
        "other_person_leakage",
        "one_off_leakage",
        "correction_resurrection",
        "unsupported_task",
        "schema_forced_task",
    }
    assert rubric.material_improvement.normalized_mean_delta == 0.10
    assert rubric.material_improvement.family_net_win_rate == 0.20
