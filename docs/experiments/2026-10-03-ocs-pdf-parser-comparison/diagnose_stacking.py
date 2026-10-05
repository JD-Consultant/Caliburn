"""Check Camelot's table stacking separately from the main extraction comparison."""

import argparse
import json
from pathlib import Path
import tempfile

import camelot


parser = argparse.ArgumentParser()
parser.add_argument("--repo", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
temporary = args.output.parent / "temporary"
temporary.mkdir(exist_ok=True)
tempfile.tempdir = str(temporary)
cases = json.loads(Path(__file__).with_name("cases.json").read_text(encoding="utf-8"))
results = []
for case in cases:
    if case["id"] not in {"01", "02", "06"}:
        continue
    tables = camelot.read_pdf(str(args.repo / case["path"]), pages="all", flavor="lattice")
    stacked = tables.stack_contiguous(match="column_count")
    results.append({"id": case["id"],
                    "before": [{"page": table.page, "shape": table.df.shape} for table in tables],
                    "after": [{"page": table.page, "shape": table.df.shape,
                               "grid": table.df.values.tolist()} for table in stacked]})
args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print([(record["id"], len(record["before"]), len(record["after"])) for record in results])
