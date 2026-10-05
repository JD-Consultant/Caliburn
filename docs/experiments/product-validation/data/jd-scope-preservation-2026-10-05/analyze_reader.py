"""Recompute counts from recorded events; never grade meaning automatically."""

import importlib.util
from collections import Counter
from decimal import Decimal

from reader_study import ARMS, FUNDED_DIRECTORY, dump, load, reused


def analyze(run_dir):
    spec = importlib.util.spec_from_file_location(
        "incremental_analysis", reused.SOURCE / "analyze.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.analyze(run_dir)
    totals = {}
    for arm in ARMS:
        for scope in ("regression", "narrow", "all"):
            cells = [
                value
                for name, value in result["cells"].items()
                if name.endswith(f"-{arm}")
                and (scope == "all" or ("_only-" in name) == (scope == "narrow"))
            ]
            counter = Counter()
            for value in cells:
                counter.update(
                    {
                        key: count
                        for key, count in value.items()
                        if key != "estimated_generation_usd"
                    }
                )
            counter["max_input_tokens"] = max(
                (value.get("max_input_tokens", 0) for value in cells), default=0
            )
            totals[f"{arm}/{scope}"] = {
                **counter,
                "estimated_generation_usd": str(
                    sum(
                        (Decimal(value["estimated_generation_usd"]) for value in cells),
                        Decimal(0),
                    )
                ),
            }
    result["totals"] = totals
    result["outputs"] = {
        value["cell"]: {
            "reads": value["reads"],
            "work_characters": len(value["final"]["task"]["work"]),
            "unknowns": value["final"]["unknowns"],
            "seconds": value["seconds"],
        }
        for value in (load(path) for path in run_dir.glob("result-*.json"))
    }
    summary = run_dir / "run-summary.json"
    result["run_summary"] = load(summary) if summary.exists() else None
    return result


if __name__ == "__main__":
    value = analyze(FUNDED_DIRECTORY)
    dump(FUNDED_DIRECTORY / "analysis.json", value)
    print(reused.support.json.dumps(value["totals"], ensure_ascii=False, indent=2))
