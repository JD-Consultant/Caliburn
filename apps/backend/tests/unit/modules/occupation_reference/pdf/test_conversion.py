"""File conversion preserves Golden outputs and isolates rejected inputs."""

import json
import os
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import jsonschema
import pdfplumber
import pytest
from pdfplumber.pdf import PDF

from caliburn.modules.occupation_reference.infrastructure.pdf import conversion
from caliburn.modules.occupation_reference.infrastructure.pdf.parsers import (
    PDFPlumberParser,
)
from caliburn.modules.occupation_reference.infrastructure.pdf.transformers import (
    ocs_transformer,
)
from caliburn.modules.occupation_reference.infrastructure.pdf.validators import (
    OCSSchemaValidator,
)

FIXTURES = Path(__file__).parent / "fixtures"
PDFS = sorted((FIXTURES / "sample_pdfs").glob("*.pdf"))


@pytest.mark.parametrize("pdf", PDFS, ids=[p.stem for p in PDFS])
def test_conversion_matches_golden(pdf: Path, tmp_path: Path) -> None:
    target = tmp_path / "result.json"
    result = conversion.convert_file(pdf, target, tmp_path / "diagnostics")
    assert result["status"] == "converted", result
    assert result["source_sha256"] == sha256(pdf.read_bytes()).hexdigest()
    output = json.loads(target.read_text("utf-8"))
    schema = (
        Path(__file__).resolve().parents[7]
        / "packages/ocs-contract/schema/ocs-document.schema.json"
    )
    jsonschema.validate(output, json.loads(schema.read_text("utf-8")))
    assert output == json.loads(
        (FIXTURES / "golden" / (pdf.stem + ".json")).read_text("utf-8")
    )


def test_changed_input_is_rejected_without_overwriting_output(tmp_path: Path) -> None:
    target = tmp_path / "result.json"
    target.write_bytes(b"previous")
    result = conversion.convert_file(
        PDFS[0], target, tmp_path / "diagnostics", "outdated"
    )
    assert result["status"] == "rejected"
    assert result["stage"] == "parse"
    assert "Source changed" in result["issues"][0]["message"]
    assert target.read_bytes() == b"previous"


def test_extracted_document_remains_usable_after_source_is_removed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "source.pdf"
    path.write_bytes(PDFS[0].read_bytes())
    source = PDFPlumberParser().parse(path)
    path.unlink()
    document = ocs_transformer.transform_document(source)
    assert OCSSchemaValidator().validate_source(source, document) == (True, [])


def test_source_coverage_rejects_truncated_indicator() -> None:
    source = PDFPlumberParser().parse(PDFS[0])
    document = ocs_transformer.transform_document(source)
    assert document.ocs_content is not None
    assert document.ocs_content.ocu_units
    tasks = document.ocs_content.ocu_units[0].tasks
    assert tasks and tasks[0].competency_blocks
    indicators = tasks[0].competency_blocks[0].indicators
    assert indicators
    indicators[0].text = "truncated"
    valid, errors = OCSSchemaValidator().validate_source(source, document)
    assert not valid
    assert any("behavioral" in error for error in errors)


def blank_pdf(path: Path) -> None:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Contents 4 0 R >>",
        b"<< /Length 0 >>\nstream\n\nendstream",
    ]
    content = b"%PDF-1.4\n"
    offsets = []
    for index, value in enumerate(objects, 1):
        offsets.append(len(content))
        content += f"{index} 0 obj\n".encode() + value + b"\nendobj\n"
    start = len(content)
    content += b"xref\n0 5\n0000000000 65535 f \n"
    content += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    content += f"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF".encode()
    path.write_bytes(content)


def test_blank_pdf_reports_rejection_and_preserves_output(tmp_path: Path) -> None:
    source = tmp_path / "blank.pdf"
    blank_pdf(source)
    target = tmp_path / "result.json"
    target.write_bytes(b"previous")
    result = conversion.convert_file(source, target, tmp_path / "diagnostics")
    assert result["status"] == "rejected"
    assert result["stage"] == "parse"
    assert result["source_sha256"] == sha256(source.read_bytes()).hexdigest()
    assert "scanned PDFs" in result["issues"][0]["message"]
    assert target.read_bytes() == b"previous"


def test_interrupted_replace_preserves_output_and_records_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "result.json"
    target.write_bytes(b"previous")

    def interrupted_replace(source: Path, destination: Path) -> None:
        raise OSError("interrupted replacement")

    monkeypatch.setattr(os, "replace", interrupted_replace)
    result = conversion.convert_file(PDFS[0], target, tmp_path / "diagnostics")
    assert result["status"] == "rejected"
    assert result["stage"] == "write"
    assert result["issues"][0]["message"] == "interrupted replacement"
    assert result["issues"][1]["type"] == "CandidateWriteError"
    assert target.read_bytes() == b"previous"
    assert list(tmp_path.rglob("*.tmp")) == []


def test_unreadable_source_reports_both_parse_and_hash_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "unreadable.pdf"
    source.write_bytes(b"input")

    def unreadable(path: Path) -> bytes:
        raise PermissionError("source permission denied")

    monkeypatch.setattr(Path, "read_bytes", unreadable)
    result = conversion.convert_file(
        source, tmp_path / "out.json", tmp_path / "diagnostics"
    )
    assert result["status"] == "rejected"
    assert result["source_sha256"] is None
    assert [issue["type"] for issue in result["issues"]] == [
        "SourceReadError",
        "PDFParsingError",
    ]


def test_conversion_extracts_the_pdf_only_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_open = pdfplumber.open
    opens = 0

    def open_snapshot(snapshot: BytesIO) -> PDF:
        nonlocal opens
        opens += 1
        return original_open(snapshot)

    monkeypatch.setattr(pdfplumber, "open", open_snapshot)
    result = conversion.convert_file(
        PDFS[0], tmp_path / "out.json", tmp_path / "diagnostics"
    )
    assert result["status"] == "converted", result
    assert opens == 1


def test_write_failure_keeps_rejected_candidate_for_diagnosis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "result.json"
    target.write_bytes(b"previous")
    original_replace = os.replace

    def reject_target(source: Path, destination: Path) -> None:
        if destination == target:
            raise PermissionError("output is unavailable")
        original_replace(source, destination)

    monkeypatch.setattr(os, "replace", reject_target)
    result = conversion.convert_file(PDFS[0], target, tmp_path / "diagnostics")
    assert result["status"] == "rejected"
    assert result["stage"] == "write"
    candidate = Path(result["candidate"])
    assert candidate == tmp_path / "diagnostics" / "rejected" / "result.json"
    assert json.loads(candidate.read_text("utf-8"))["ocs_profile"]["ocs_code"]
    assert target.read_bytes() == b"previous"
