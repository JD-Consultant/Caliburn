"""Repository paths for the R1 experiment's frozen documentation assets."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
EXPERIMENT_ROOT = REPO_ROOT / "docs" / "experiments" / "2026-07-27-r1-task-discovery"
CASES_DIR = EXPERIMENT_ROOT / "cases"
RUBRIC_PATH = EXPERIMENT_ROOT / "rubric.md"
