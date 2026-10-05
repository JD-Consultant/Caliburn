"""Immutable preparation artifacts and explicit single-run admission."""

import hashlib
import json
import os
import zipfile
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save_new(path: Path, value: object) -> None:
    """Do not overwrite earlier evidence or allow an implicit paid restart."""
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=_json_value)
        stream.flush()
        os.fsync(stream.fileno())


def _json_value(value: object) -> object:
    return sorted(value, key=str) if isinstance(value, (set, frozenset)) else str(value)


def freeze_files(paths: Iterable[Path], *, root: Path, output: Path) -> dict[str, str]:
    selected = sorted({path.resolve() for path in paths})
    # Resolve before creating anything; never package a secret or outside target.
    names = [p.relative_to(root.resolve()).as_posix() for p in selected]
    if any(p.name == ".env" or ".git" in p.parts for p in selected):
        raise ValueError("Only explicit research/code inputs may be frozen")
    output.mkdir(parents=True, exist_ok=False)
    records = {}
    with zipfile.ZipFile(output / "sources.zip", "x", zipfile.ZIP_DEFLATED) as archive:
        for path, name in zip(selected, names, strict=True):
            data = path.read_bytes()
            records[name] = hashlib.sha256(data).hexdigest()
            archive.writestr(name, data)
    return records


def verify_files(records: Mapping[str, str], *, root: Path) -> None:
    for name, expected in records.items():
        path = (root / name).resolve()
        if (
            not path.is_relative_to(root.resolve())
            or not path.is_file()
            or file_hash(path) != expected
        ):
            raise ValueError(f"source_changed: {name}")


def claim_run(output: Path, authorization: Mapping[str, object]) -> None:
    save_new(
        output / "started.json", {**authorization, "started_at": datetime.now(UTC).isoformat()}
    )
