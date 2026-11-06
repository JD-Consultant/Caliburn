"""Write separate cleaned JSON copies and retain each file's source identity."""

import json
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from typing import Literal, TypedDict

from ocs_contract.models import OCSDocument

from caliburn.modules.occupation_reference.domain.cleaning import clean_document

from .pdf.writers.json_writer import write_text_atomically


class CleaningIssue(TypedDict):
    type: str
    message: str


class CleaningResult(TypedDict):
    source: str
    source_sha256: str | None
    output: str
    output_sha256: str | None
    status: Literal["cleaned", "rejected"]
    stage: Literal["read", "validate", "clean", "write", "complete"]
    issues: list[CleaningIssue]


class CleaningSummary(TypedDict):
    cleaned: int
    rejected: int


def _clean_file(source: Path, output: Path, relative: Path) -> CleaningResult:
    result: CleaningResult = {
        "source": relative.as_posix(),
        "source_sha256": None,
        "output": str(output),
        "output_sha256": None,
        "status": "rejected",
        "stage": "read",
        "issues": [],
    }
    try:
        data = source.read_bytes()
        result["source_sha256"] = sha256(data).hexdigest()
        result["stage"] = "validate"
        document = OCSDocument.model_validate_json(data)
        result["stage"] = "clean"
        cleaned = clean_document(document)
        result["stage"] = "write"
        write_text_atomically(json.dumps(cleaned, ensure_ascii=False, indent=2), output)
        result["output_sha256"] = sha256(output.read_bytes()).hexdigest()
        result["status"] = "cleaned"
        result["stage"] = "complete"
    except Exception as error:
        result["issues"].append({"type": type(error).__name__, "message": str(error)})
    return result


def clean_json_files(source: Path, output: Path, diagnostics: Path) -> CleaningSummary:
    """Clean one JSON or a recursive selection, never overwriting source files.

    Output and diagnostics are separate directories, disjoint from the selected
    source. Input and cleaning failures are recorded per file; a diagnostics
    write failure propagates rather than claiming an unrecorded batch completed.
    """
    roots = (source.resolve(), output.resolve(), diagnostics.resolve())
    if any(
        left.is_relative_to(right) or right.is_relative_to(left)
        for left, right in combinations(roots, 2)
    ):
        raise ValueError("source, output and diagnostics must not overlap")
    files = (
        sorted(path for path in source.rglob("*.json") if path.is_file())
        if source.is_dir()
        else [source]
    )
    if not files or any(not path.is_file() for path in files):
        raise ValueError("select at least one existing JSON")
    source_root = source if source.is_dir() else source.parent
    for path in files:
        relative = path.relative_to(source_root)
        if any(path.resolve().is_relative_to(root) for root in roots[1:]):
            raise ValueError("source files and destinations must not overlap")
        for target, root in (
            (output / relative, roots[1]),
            (diagnostics / "files" / relative, roots[2]),
        ):
            if not target.resolve().is_relative_to(root):
                raise ValueError("resolved destination paths must not overlap sources")
    results = []
    for path in files:
        relative = path.relative_to(source_root)
        result = _clean_file(path, output / relative, relative)
        write_text_atomically(
            json.dumps(result, ensure_ascii=False, indent=2),
            diagnostics / "files" / relative,
        )
        results.append(result)
    summary = CleaningSummary(
        cleaned=sum(result["status"] == "cleaned" for result in results),
        rejected=sum(result["status"] == "rejected" for result in results),
    )
    write_text_atomically(
        json.dumps({**summary, "files": results}, ensure_ascii=False, indent=2),
        diagnostics / "report.json",
    )
    return summary
