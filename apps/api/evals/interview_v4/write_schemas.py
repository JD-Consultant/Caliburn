"""Publish Pydantic contracts as portable JSON Schema.

Run from ``apps/api``:
    uv run python -m evals.interview_v4.write_schemas
"""
from __future__ import annotations

import json
from pathlib import Path

from evals.interview_v4.contracts import SCHEMA_MODELS


SCHEMA_DIR = Path(__file__).with_name("schemas")


def write_schemas(schema_dir: Path = SCHEMA_DIR) -> list[Path]:
    schema_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, model in SCHEMA_MODELS.items():
        path = schema_dir / filename
        path.write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


if __name__ == "__main__":
    for item in write_schemas():
        print(item)
