"""Real-file CLI regressions for rejected data and interrupted replacement."""

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from jd_pdf_to_json.cli import app
from jd_pdf_to_json.conversion import convert_file
from jd_pdf_to_json.core.models import OCSDocument
from jd_pdf_to_json.writers import JSONWriter

CORPUS = Path(__file__).resolve().parents[1] / "data" / "pdfs"


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


def test_mixed_batch_counts_each_source_once_and_preserves_rejected_target(tmp_path):
    source = tmp_path / "pdfs"
    source.mkdir()
    shutil.copyfile(CORPUS / "3D列印設備配修人員-職能基準.pdf", source / "valid.pdf")
    blank_pdf(source / "blank.pdf")
    output = tmp_path / "json"
    output.mkdir()
    previous = b'{"previous":"retain"}'
    (output / "blank.json").write_bytes(previous)
    result = CliRunner().invoke(app, ["batch", str(source), "-o", str(output)])
    assert result.exit_code == 1, result.output
    assert (output / "valid.json").exists(), result.output
    assert (output / "blank.json").read_bytes() == previous
    report = json.loads((tmp_path / "json.diagnostics" / "batch-report.json").read_text("utf-8"))
    assert report["summary"] == {"converted": 1, "rejected": 1, "excluded": 0}
    assert len(report["files"]) == 2
    assert all(len(entry["source_sha256"]) == 64 for entry in report["files"])


def test_no_validate_cannot_allow_empty_content(tmp_path):
    source = tmp_path / "blank.pdf"
    blank_pdf(source)
    output = tmp_path / "blank.json"
    result = CliRunner().invoke(app, ["convert", str(source), "-o", str(output), "--no-validate"])
    assert result.exit_code == 1
    assert not output.exists()
    assert (tmp_path / "blank.diagnostics" / "report.json").exists()


def test_failed_atomic_replace_retains_previous_json(tmp_path, monkeypatch):
    import os

    output = tmp_path / "result.json"
    previous = b'{"previous":"retain"}'
    output.write_bytes(previous)

    def fail_replace(*args):
        raise OSError("simulated interrupted replacement")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="interrupted"):
        JSONWriter().write(OCSDocument(ocs_profile={"ocs_code": "TEST1234"}), output)
    assert output.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [output]


def test_unreadable_source_is_rejected_without_hash_error_escaping(tmp_path, monkeypatch):
    source = tmp_path / "unreadable.pdf"
    source.write_bytes(b"input")

    def unreadable(self):
        raise PermissionError("source permission denied")

    monkeypatch.setattr(Path, "read_bytes", unreadable)
    result = convert_file(source, tmp_path / "out.json", tmp_path / "diagnostics")
    assert result["status"] == "rejected"
    assert result["source_sha256"] is None
    assert any("permission denied" in issue["message"] for issue in result["issues"])
