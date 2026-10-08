"""Freeze omitted non-Python package resources without replacing prior evidence."""

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
spec = importlib.util.spec_from_file_location(
    "study_manifest",
    HERE.parent / "early-interview-recall-2026-10-05/study_manifest.py",
)
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)
paths = [
    path
    for path in (ROOT / "apps/api/src").rglob("*")
    if path.is_file()
    and path.suffix not in {".py", ".pyc"}
    and "__pycache__" not in path.parts
]
records = manifest.freeze_files(paths, root=ROOT, output=HERE / "resource-freeze")
manifest.save_new(
    HERE / "resource-repair.json",
    {
        "reason": "Generated schema and HTML resources omitted from first code freeze",
        "failure_execution": "40249ab2-1164-4fb2-a620-e41dc18dc33a",
        "external_calls_before_repair": 0,
        "source_hashes": records,
        "archive_sha256": manifest.file_hash(HERE / "resource-freeze/sources.zip"),
    },
)
print({"frozen_resources": len(records)})
