"""Convert one PDF snapshot and report accepted output or rejection diagnostics."""

import json
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from .errors import ValidationError
from .parsers import PDFPlumberParser
from .transformers.ocs_transformer import transform_document
from .validators import OCSSchemaValidator
from .writers.json_writer import write_document, write_text_atomically


class ConversionIssue(TypedDict):
    type: str
    message: str


class ConversionResult(TypedDict):
    source: str
    source_sha256: str | None
    output: str
    status: Literal["converted", "rejected"]
    stage: Literal["parse", "transform", "validate", "write", "complete"]
    issues: list[ConversionIssue]
    pages: NotRequired[int]
    counts: NotRequired[dict[str, int]]
    candidate: NotRequired[str]


def write_report(report: Mapping[str, object], path: Path) -> None:
    write_text_atomically(json.dumps(report, ensure_ascii=False, indent=2), path)


def convert_file(
    source_path: Path,
    output_path: Path,
    diagnostics_dir: Path,
    expected_sha256: str | None = None,
) -> ConversionResult:
    """Convert a fixed PDF snapshot, preserving the target on any rejection.

    Returns the source hash, final stage and issues for maintenance reporting.
    A rejected transformed candidate is saved under diagnostics_dir/rejected;
    diagnostics write errors are included in the result. No model is loaded.
    """
    result: ConversionResult = {
        "source": source_path.name,
        "source_sha256": None,
        "output": str(output_path),
        "status": "rejected",
        "stage": "parse",
        "issues": [],
    }
    candidate = None
    try:
        parser = PDFPlumberParser()
        source = parser.parse(source_path)
        result["source_sha256"] = source.source_sha256
        result["pages"] = len(source.pages)
        if expected_sha256 is not None and source.source_sha256 != expected_sha256:
            raise ValidationError("Source changed after input manifest was fixed")
        if not parser.validate_source(source):
            raise ValidationError(
                "Missing OCS source text; scanned PDFs require another extraction path"
            )
        result["stage"] = "transform"
        candidate = transform_document(source)
        result["stage"] = "validate"
        # Typed schema and necessary content/relationship checks always apply.
        validator = OCSSchemaValidator()
        valid, errors = validator.validate(candidate)
        source_valid, source_errors = validator.validate_source(source, candidate)
        errors.extend(source_errors)
        valid = valid and source_valid
        if not valid:
            raise ValidationError("; ".join(errors))
        result["stage"] = "write"
        write_document(candidate, output_path)
        result["status"] = "converted"
        result["stage"] = "complete"
        assert candidate.ocs_content is not None
        assert candidate.ocs_attitude is not None
        assert candidate.notes is not None
        units = candidate.ocs_content.ocu_units or []
        tasks = [task for unit in units for task in (unit.tasks or [])]
        blocks = [block for task in tasks for block in (task.competency_blocks or [])]
        result["counts"] = {
            "units": len(units),
            "tasks": len(tasks),
            "blocks": len(blocks),
            "indicators": sum(len(block.indicators or []) for block in blocks),
            "knowledge": sum(len(block.knowledge or []) for block in blocks),
            "skills": sum(len(block.skills or []) for block in blocks),
            "attitudes": len(candidate.ocs_attitude.attitudes or []),
            "prerequisites": len(candidate.notes.prerequisites or []),
            "supplements": len(candidate.notes.supplements or []),
        }
    except Exception as exc:
        if result["source_sha256"] is None and source_path.exists():
            try:
                result["source_sha256"] = sha256(source_path.read_bytes()).hexdigest()
            except OSError as hash_error:
                result["issues"].append(
                    {"type": "SourceReadError", "message": str(hash_error)}
                )
        result["issues"].append({"type": type(exc).__name__, "message": str(exc)})
        if candidate is not None:
            rejected = diagnostics_dir / "rejected" / output_path.name
            try:
                write_document(candidate, rejected)
                result["candidate"] = str(rejected)
            except OSError as write_error:
                result["issues"].append(
                    {"type": "CandidateWriteError", "message": str(write_error)}
                )
    return result
