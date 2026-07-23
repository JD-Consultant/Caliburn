"""Publish Job Authoring Pydantic contracts as portable JSON Schema.

Run from ``apps/api``:
    uv run python -m app.job_authoring.write_schemas
"""

from __future__ import annotations

import json
from pathlib import Path

from .schema_exports import SCHEMA_EXPORTS, published_schema

SCHEMA_DIR = Path(__file__).with_name("schemas")


def write_schemas(schema_dir: Path = SCHEMA_DIR) -> list[Path]:
    schema_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename in SCHEMA_EXPORTS:
        path = schema_dir / filename
        path.write_text(
            json.dumps(published_schema(filename), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


if __name__ == "__main__":
    for item in write_schemas():
        print(item)
