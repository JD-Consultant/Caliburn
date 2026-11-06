"""The maintenance entry point preserves batch outcomes and source-relative paths."""

import io
import json
import os
import shutil
import sys
from hashlib import sha256
from pathlib import Path

import pytest

from caliburn.modules.occupation_reference.cli import main

FIXTURES = Path(__file__).parent / "pdf/fixtures"


def test_conversion_reports_rejection_and_continues_other_sources(
    tmp_path: Path,
) -> None:
    source = tmp_path / "pdfs"
    (source / "nested").mkdir(parents=True)
    fixture = (
        Path(__file__).parent / "pdf/fixtures/sample_pdfs/3D珠寶設計人員-職能基準.pdf"
    )
    shutil.copyfile(fixture, source / "nested/valid.pdf")
    (source / "broken.pdf").write_bytes(b"not a PDF")
    output = tmp_path / "json"
    diagnostics = tmp_path / "diagnostics"
    result = main(
        ["convert-pdf", str(source), str(output), "--diagnostics", str(diagnostics)]
    )
    assert result == 1
    assert (output / "nested/valid.json").is_file()
    assert not (output / "broken.json").exists()
    report = json.loads((diagnostics / "report.json").read_text(encoding="utf-8"))
    assert (report["converted"], report["rejected"]) == (1, 1)
    assert [item["status"] for item in report["files"]] == ["rejected", "converted"]


def test_batch_rejects_source_changed_after_its_input_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "pdfs"
    source.mkdir()
    original = (FIXTURES / "sample_pdfs/3D珠寶設計人員-職能基準.pdf").read_bytes()
    replacement = (
        FIXTURES / "sample_pdfs/3D列印設備配修人員-職能基準.pdf"
    ).read_bytes()
    (source / "a.pdf").write_bytes(original)
    (source / "b.pdf").write_bytes(original)
    output, diagnostics = tmp_path / "json", tmp_path / "diagnostics"
    replace = os.replace

    def change_later_source(source_path: Path, target_path: Path) -> None:
        replace(source_path, target_path)
        if target_path == output / "a.json":
            (source / "b.pdf").write_bytes(replacement)

    monkeypatch.setattr(os, "replace", change_later_source)
    assert (
        main(
            ["convert-pdf", str(source), str(output), "--diagnostics", str(diagnostics)]
        )
        == 1
    )
    report = json.loads((diagnostics / "report.json").read_text(encoding="utf-8"))
    assert (report["converted"], report["rejected"]) == (1, 1)
    assert not (output / "b.json").exists()
    assert "Source changed" in report["files"][1]["issues"][0]["message"]
    manifest = json.loads(
        (diagnostics / "input-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["files"][1]["source_sha256"] == sha256(original).hexdigest()


def test_interrupted_batch_keeps_manifest_and_completed_file_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "pdfs"
    source.mkdir()
    original = (FIXTURES / "sample_pdfs/3D珠寶設計人員-職能基準.pdf").read_bytes()
    for name in ("a.pdf", "b.pdf"):
        (source / name).write_bytes(original)
    output, diagnostics = tmp_path / "json", tmp_path / "diagnostics"
    read_bytes = Path.read_bytes

    def interrupt_second_file(path: Path) -> bytes:
        if path == source / "b.pdf" and (output / "a.json").exists():
            raise KeyboardInterrupt
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", interrupt_second_file)
    with pytest.raises(KeyboardInterrupt):
        main(
            ["convert-pdf", str(source), str(output), "--diagnostics", str(diagnostics)]
        )
    assert (output / "a.json").is_file()
    assert (diagnostics / "input-manifest.json").is_file()
    first = json.loads((diagnostics / "files/a.json").read_text(encoding="utf-8"))
    assert first["status"] == "converted"


@pytest.mark.parametrize("layout", ["same", "diagnostics_child", "output_child"])
def test_output_and_diagnostics_overlap_is_rejected_before_writing(
    tmp_path: Path, layout: str
) -> None:
    source = tmp_path / "report.pdf"
    source.write_bytes(b"invalid PDF")
    output = tmp_path / "output"
    diagnostics = output
    if layout == "diagnostics_child":
        diagnostics = output / "diagnostics"
    elif layout == "output_child":
        output = diagnostics / "json"
    output.mkdir(parents=True)
    target = output / "report.json"
    target.write_bytes(b"previous accepted source")
    with pytest.raises(ValueError, match="overlap"):
        main(
            ["convert-pdf", str(source), str(output), "--diagnostics", str(diagnostics)]
        )
    assert target.read_bytes() == b"previous accepted source"


def test_historical_exclusion_is_explicit_and_recorded(tmp_path: Path) -> None:
    source = tmp_path / "pdfs"
    source.mkdir()
    (source / "歷史資料.pdf").write_bytes(b"not parsed when explicitly excluded")
    output, diagnostics = tmp_path / "json", tmp_path / "diagnostics"
    assert (
        main(
            [
                "convert-pdf",
                str(source),
                str(output),
                "--diagnostics",
                str(diagnostics),
                "--exclude-historical",
            ]
        )
        == 0
    )
    assert not (output / "歷史資料.json").exists()
    report = json.loads((diagnostics / "report.json").read_text(encoding="utf-8"))
    assert (report["converted"], report["rejected"], report["excluded"]) == (0, 0, 1)
    item = json.loads((diagnostics / "files/歷史資料.json").read_text(encoding="utf-8"))
    assert item["status"] == "excluded"


@pytest.mark.parametrize("contents", ["valid", "malformed", "invalid", "empty"])
def test_json_validation_is_available_without_conversion(
    tmp_path: Path, contents: str
) -> None:
    source = tmp_path / "source.json"
    data = (FIXTURES / "golden/3D珠寶設計人員-職能基準.json").read_bytes()
    if contents == "malformed":
        data = b"{"
    elif contents == "invalid":
        data = b'{"ocs_profile": 123}'
    elif contents == "empty":
        document = json.loads(data)
        document["ocs_content"]["ocu_units"] = []
        data = json.dumps(document).encode()
    source.write_bytes(data)
    assert main(["validate-json", str(source)]) == (0 if contents == "valid" else 1)
    assert source.read_bytes() == data


def test_unreadable_manifest_source_is_rejected_even_if_it_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "pdfs"
    source.mkdir()
    data = (FIXTURES / "sample_pdfs/3D珠寶設計人員-職能基準.pdf").read_bytes()
    for name in ("a.pdf", "b.pdf"):
        (source / name).write_bytes(data)
    output, diagnostics = tmp_path / "json", tmp_path / "diagnostics"
    read_bytes = Path.read_bytes
    attempts = 0

    def fail_first_read(path: Path) -> bytes:
        nonlocal attempts
        if path == source / "a.pdf":
            attempts += 1
            if attempts == 1:
                raise OSError("temporarily unreadable")
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail_first_read)
    assert (
        main(
            ["convert-pdf", str(source), str(output), "--diagnostics", str(diagnostics)]
        )
        == 1
    )
    assert not (output / "a.json").exists()
    assert (output / "b.json").is_file()
    result = json.loads((diagnostics / "files/a.json").read_text(encoding="utf-8"))
    assert result["status"] == "rejected"
    assert result["source_sha256"] is None
    assert result["issues"][0]["type"] == "SourceReadError"


def test_nested_source_reports_do_not_overwrite_rejected_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "pdfs"
    data = (FIXTURES / "sample_pdfs/3D珠寶設計人員-職能基準.pdf").read_bytes()
    for directory in ("files", "rejected"):
        (source / directory).mkdir(parents=True)
        (source / directory / "a.pdf").write_bytes(data)
    output, diagnostics = tmp_path / "json", tmp_path / "diagnostics"
    replace = os.replace

    def reject_first_write(source_path: Path, target_path: Path) -> None:
        if target_path == output / "files/a.json":
            raise PermissionError("output not writable")
        replace(source_path, target_path)

    monkeypatch.setattr(os, "replace", reject_first_write)
    assert (
        main(
            ["convert-pdf", str(source), str(output), "--diagnostics", str(diagnostics)]
        )
        == 1
    )
    report = json.loads((diagnostics / "report.json").read_text(encoding="utf-8"))
    candidate = json.loads(Path(report["files"][0]["candidate"]).read_text("utf-8"))
    assert "ocs_profile" in candidate
    second = json.loads(
        (diagnostics / "files/rejected/a.json").read_text(encoding="utf-8")
    )
    assert second["status"] == "converted"
    assert second["source"] == "rejected/a.pdf"


def test_validation_diagnostics_support_non_utf8_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "invalid.json"
    source.write_text('{"ocs_profile":"😀"}', encoding="utf-8")
    buffer = io.BytesIO()
    with io.TextIOWrapper(buffer, encoding="cp950") as terminal:
        with monkeypatch.context() as patch:
            patch.setattr(sys, "stdout", terminal)
            assert main(["validate-json", str(source)]) == 1
        terminal.flush()
        result = json.loads(buffer.getvalue().decode("cp950"))
        assert result["valid"] is False
        assert result["errors"]
