"""OCS JSON reader.

Scans a source directory, loads each JSON, validates against pydantic models,
computes a canonical sha256 hash, and yields LoadedFile records that downstream
stages consume. Failures are recorded but do not abort the pipeline.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from jd_ocs_indexer.models.ocs import OCSDocument


@dataclass
class LoadedFile:
    path: Path                # absolute path on this machine
    rel_path: str             # path relative to source root, POSIX-style
    source_json_hash: str     # sha256 of canonical bytes
    document: OCSDocument
    raw: dict


@dataclass
class FailedFile:
    path: Path
    rel_path: str
    error: str


def canonical_bytes(obj: dict) -> bytes:
    """Stable serialization for hashing: sorted keys, no extra whitespace, NFC text."""
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relative_source_file(path: Path, source_root: Path) -> str:
    """POSIX-style path relative to source_root.

    If the file is not under source_root (defensive case), fall back to the
    file name only — payloads must not contain absolute drive paths.
    """
    try:
        rel = path.resolve().relative_to(source_root.resolve())
    except ValueError:
        rel = Path(path.name)
    return rel.as_posix()


class OCSJSONReader:
    def __init__(self, source_root: Path):
        self.source_root = source_root

    def iter_files(self, scan_dir: Path) -> Iterator[Path]:
        for p in sorted(scan_dir.glob("*.json")):
            if p.is_file():
                yield p

    def load_one(self, path: Path) -> tuple[LoadedFile | None, FailedFile | None]:
        rel = relative_source_file(path, self.source_root)
        try:
            with path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as exc:
            return None, FailedFile(path=path, rel_path=rel, error=f"json_parse: {exc}")

        try:
            doc = OCSDocument.model_validate(raw)
        except Exception as exc:
            return None, FailedFile(path=path, rel_path=rel, error=f"schema: {exc}")

        h = sha256_hex(canonical_bytes(raw))
        loaded = LoadedFile(
            path=path,
            rel_path=rel,
            source_json_hash=h,
            document=doc,
            raw=raw,
        )
        return loaded, None

    def iter_loaded(self, scan_dir: Path) -> Iterator[tuple[LoadedFile | None, FailedFile | None]]:
        for p in self.iter_files(scan_dir):
            yield self.load_one(p)
