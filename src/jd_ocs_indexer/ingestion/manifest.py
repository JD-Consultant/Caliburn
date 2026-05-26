"""Local manifest tracking incremental indexing state.

Shape:

{
  "collection": "ocs_bgem3_v1",
  "embedding_provider": "bge-m3",
  "source_root_alias": "jd-pdf-to-json",
  "schema_version": "ocs-index-v1",
  "files": {
    "output/0518/example.json": {
      "source_json_hash": "...",
      "chunk_keys": ["ocs:...:profile", ...],
      "indexed_at": "2026-05-26T00:00:00+00:00"
    }
  }
}
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class FileEntry:
    source_json_hash: str
    chunk_keys: list[str] = field(default_factory=list)
    indexed_at: str = ""


@dataclass
class Manifest:
    collection: str = ""
    embedding_provider: str = ""
    source_root_alias: str = ""
    schema_version: str = ""
    files: dict[str, FileEntry] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "collection": self.collection,
            "embedding_provider": self.embedding_provider,
            "source_root_alias": self.source_root_alias,
            "schema_version": self.schema_version,
            "files": {k: asdict(v) for k, v in self.files.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Manifest":
        files = {
            k: FileEntry(
                source_json_hash=v.get("source_json_hash", ""),
                chunk_keys=list(v.get("chunk_keys", [])),
                indexed_at=v.get("indexed_at", ""),
            )
            for k, v in (data.get("files") or {}).items()
        }
        return cls(
            collection=data.get("collection", ""),
            embedding_provider=data.get("embedding_provider", ""),
            source_root_alias=data.get("source_root_alias", ""),
            schema_version=data.get("schema_version", ""),
            files=files,
        )


def load(path: Path) -> Manifest:
    if not path.exists():
        return Manifest()
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return Manifest.from_dict(data)


def save(path: Path, manifest: Manifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, ensure_ascii=False, indent=2)
    tmp.replace(path)
