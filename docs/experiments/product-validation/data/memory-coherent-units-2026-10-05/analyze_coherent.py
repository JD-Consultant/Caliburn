"""Recompute usage and observed selection; never infer semantic quality from counts."""

import argparse
from collections import Counter
from decimal import Decimal
from pathlib import Path

from coherent_study import ARMS, SOURCE, dump, load, support

spec = support.importlib.util.spec_from_file_location(
    "structure_analysis", SOURCE / "analyze.py"
)
analysis_module = support.importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis_module)


def analyze(run_dir: Path) -> dict:
    result = analysis_module.analyze(run_dir)
    totals = {}
    for arm in ARMS:
        for phase in ("maintenance", "reading"):
            selected = [
                value
                for name, value in result["cells"].items()
                if name.endswith(f"-{arm}")
                and name.startswith("read-") == (phase == "reading")
            ]
            stats = Counter()
            cost = Decimal(0)
            for value in selected:
                stats.update(
                    {
                        key: amount
                        for key, amount in value.items()
                        if key != "estimated_generation_usd"
                    }
                )
                cost += Decimal(value["estimated_generation_usd"])
            stats["max_input_tokens"] = max(
                (v.get("max_input_tokens", 0) for v in selected), default=0
            )
            totals[f"{arm}/{phase}"] = {**stats, "estimated_generation_usd": str(cost)}
    result["totals"] = totals
    result["reader_selection"] = {}
    material = load(run_dir / "materials.json")
    for probe in material["probes"]:
        for arm in ARMS:
            cell = f"read-{probe['probe_id']}-{arm}"
            path = run_dir / f"result-{cell}.json"
            if not path.exists():
                continue
            outcome = load(path)
            objects = load(
                run_dir / f"workspace-{probe['snapshot_batch_id']}-{arm}.json"
            )["objects"]
            selected = {
                read[1] for read in outcome["reads"] if read[0] == "work_understanding"
            }
            result["reader_selection"][cell] = {
                "available_understandings": len(objects),
                "read_understandings": len(selected),
                "read_titles": sorted(selected),
                "raw_sequences": [
                    read[1] for read in outcome["reads"] if read[0] == "interview"
                ],
            }
    result["run_summary"] = load(run_dir / "run-summary.json")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()
    result = analyze(args.run_directory)
    dump(args.run_directory / "analysis.json", result)
    print(support.json.dumps(result["totals"], ensure_ascii=False, indent=2))
