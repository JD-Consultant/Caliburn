"""Write immutable, version-addressed execution taxonomy documents."""

from __future__ import annotations

import json
from pathlib import Path

from .taxonomy import EXECUTION_TAXONOMIES


TAXONOMY_DIR = Path(__file__).with_name("taxonomies")


def taxonomy_filename(taxonomy_id: str, version: str) -> str:
    return f"{taxonomy_id.replace('.', '-')}.{version}.json"


def write_taxonomies(taxonomy_dir: Path = TAXONOMY_DIR) -> list[Path]:
    taxonomy_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for (taxonomy_id, version), taxonomy in sorted(EXECUTION_TAXONOMIES.items()):
        path = taxonomy_dir / taxonomy_filename(taxonomy_id, version)
        path.write_text(
            json.dumps(taxonomy.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written.append(path)
    return written


if __name__ == "__main__":
    for item in write_taxonomies():
        print(item)
