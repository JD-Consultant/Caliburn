"""Write version-addressed LLM operation documents."""

from __future__ import annotations

import json
from pathlib import Path

from .operation_documents import OPERATION_DIR, operation_documents


def write_operation_documents(operation_dir: Path = OPERATION_DIR) -> list[Path]:
    operation_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, operation in operation_documents().items():
        path = operation_dir / filename
        path.write_text(
            json.dumps(operation.model_dump(mode="json"), ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


if __name__ == "__main__":
    for item in write_operation_documents():
        print(item)
