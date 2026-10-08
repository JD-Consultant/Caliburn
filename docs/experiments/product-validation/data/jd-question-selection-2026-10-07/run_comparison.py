"""Adapt the existing real-runner comparison to frozen question-selection cases."""

import argparse
import ast
import importlib.util
import sys
import zipfile
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "jd-condition-exploration-2026-10-07"
SHARED = HERE.parent / "jd-analysis-followup-2026-10-06/run_comparison.py"
BASELINE = PRIOR / "live-01/sources.zip"


def frozen_constant(path: str, name: str) -> str:
    with zipfile.ZipFile(BASELINE) as archive:
        source = archive.read(path).decode("utf-8-sig")
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            value = node.value
            if (
                isinstance(value, ast.Call)
                and not value.args
                and not value.keywords
                and isinstance(value.func, ast.Attribute)
                and value.func.attr == "strip"
            ):
                return ast.literal_eval(value.func.value).strip()
            return ast.literal_eval(value)
    raise ValueError("Missing frozen prompt constant")


def configure() -> ModuleType:
    spec = importlib.util.spec_from_file_location("question_comparison", SHARED)
    if spec is None or spec.loader is None:
        raise ValueError("Comparison loader is unavailable")
    comparison = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = comparison
    spec.loader.exec_module(comparison)
    comparison.HERE = HERE
    comparison.OUTPUT = HERE / "live-02"
    comparison.BASELINE = "jd-condition-exploration-2026-10-07/live-01/sources.zip"
    comparison.old_constant = frozen_constant
    read_json = comparison.read_json
    freeze_files = comparison.freeze_files

    def read_inputs(path: Path) -> dict:
        if path == HERE / "holdout-cases.json":
            return {"cases": []}
        if path != HERE / "cases.json":
            return read_json(path)
        cases = read_json(PRIOR / "cases.json")
        overrides = read_json(HERE / "case-overrides.json")
        for case in cases["cases"]:
            override = overrides.get(case["case_id"])
            if override is not None:
                case["prior_employee_statements"].append(override["append_statement"])
                case["employee_input"] = override["employee_input"]
        return cases

    def freeze_inputs(paths: list[Path], *, root: Path, output: Path) -> dict[str, str]:
        return freeze_files(
            [
                *(
                    p
                    for p in paths
                    if p not in {HERE / "cases.json", HERE / "holdout-cases.json"}
                ),
                SHARED,
                BASELINE,
                PRIOR / "cases.json",
                HERE / "case-overrides.json",
                HERE / "reply-policy.json",
                HERE / "protocol.md",
                HERE / "README.md",
            ],
            root=root,
            output=output,
        )

    comparison.read_json = read_inputs
    comparison.freeze_files = freeze_inputs
    return comparison


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "execute"])
    arguments = parser.parse_args()
    comparison = configure()
    if arguments.mode == "prepare":
        comparison.prepare()
    else:
        comparison.execute()
