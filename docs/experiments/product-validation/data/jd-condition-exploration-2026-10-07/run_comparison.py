"""Configure the existing bounded comparison; never replace the product agent loop."""

import argparse
import ast
import importlib.util
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent / "jd-analysis-followup-2026-10-06" / "run_comparison.py"
BASELINE = HERE.parent / "jd-analysis-full-journey-2026-10-06" / "freeze/sources.zip"


def frozen_constant(path, name):
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
    raise ValueError("Requested baseline constant is missing")


def configure():
    spec = importlib.util.spec_from_file_location("condition_comparison", SHARED)
    if spec is None or spec.loader is None:
        raise ValueError("Comparison loader is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.HERE = HERE
    module.OUTPUT = HERE / "live-01"
    module.BASELINE = "jd-analysis-full-journey-2026-10-06/freeze/sources.zip"
    module.old_constant = frozen_constant
    shared_freeze = module.freeze_files

    def freeze_inputs(paths, *, root, output):
        return shared_freeze(
            [
                *paths,
                SHARED,
                BASELINE,
                HERE / "private-answers.json",
                HERE / "README.md",
            ],
            root=root,
            output=output,
        )

    module.freeze_files = freeze_inputs
    return module


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "execute"])
    arguments = parser.parse_args()
    comparison = configure()
    if arguments.mode == "prepare":
        comparison.prepare()
    else:
        comparison.execute()
