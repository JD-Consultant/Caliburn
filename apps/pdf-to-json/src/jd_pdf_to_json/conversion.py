"""Single-file conversion outcome, shared by both CLI entry points."""

import json
from hashlib import sha256
from pathlib import Path

from jd_pdf_to_json.parsers import PDFPlumberParser
from jd_pdf_to_json.transformers import OCSTransformer
from jd_pdf_to_json.utils.exceptions import ValidationError
from jd_pdf_to_json.validators import OCSSchemaValidator
from jd_pdf_to_json.writers import JSONWriter
from jd_pdf_to_json.writers.json_writer import write_text_atomically


def write_report(report: dict, path: Path) -> None:
    write_text_atomically(json.dumps(report, ensure_ascii=False, indent=2), path)


def convert_file(
    source_path: Path, output_path: Path, diagnostics_dir: Path, expected_sha256: str | None = None
) -> dict:
    result = {
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
        candidate = OCSTransformer().transform(source)
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
        JSONWriter().write(candidate, output_path)
        result["status"] = "converted"
        result["stage"] = "complete"
        units = candidate.ocs_content.ocu_units
        tasks = [task for unit in units for task in unit.tasks]
        blocks = [block for task in tasks for block in task.competency_blocks]
        result["counts"] = {
            "units": len(units),
            "tasks": len(tasks),
            "blocks": len(blocks),
            "indicators": sum(len(block.indicators) for block in blocks),
            "knowledge": sum(len(block.knowledge) for block in blocks),
            "skills": sum(len(block.skills) for block in blocks),
            "attitudes": len(candidate.ocs_attitude.attitudes),
            "prerequisites": len(candidate.notes.prerequisites),
            "supplements": len(candidate.notes.supplements),
        }
    except Exception as exc:
        if result["source_sha256"] is None and source_path.exists():
            try:
                result["source_sha256"] = sha256(source_path.read_bytes()).hexdigest()
            except OSError as hash_error:
                result["issues"].append({"type": "SourceReadError", "message": str(hash_error)})
        result["issues"].append({"type": type(exc).__name__, "message": str(exc)})
        if candidate is not None:
            rejected = diagnostics_dir / "rejected" / output_path.name
            try:
                JSONWriter().write(candidate, rejected)
                result["candidate"] = str(rejected)
            except OSError as write_error:
                result["issues"].append(
                    {"type": "CandidateWriteError", "message": str(write_error)}
                )
    return result
