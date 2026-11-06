"""Cleaning files preserves sources and reports each accepted or rejected input."""

import json
import os
from hashlib import sha256
from pathlib import Path

import pytest

from caliburn.modules.occupation_reference.cli import main


def write_source(path: Path) -> bytes:
    document = {
        "ocs_profile": {
            "ocs_code": "TEST-001",
            "ocs_name": {"occupation_name": "3D工程師"},
            "job_description": "執行\n品質確認",
            "ocs_level": 4,
        },
        "ocs_content": {
            "ocu_units": [
                {
                    "ocu_code": "T1",
                    "ocu_name": "品質確認",
                    "tasks": [
                        {
                            "task_codes": [{"code": "T1.1", "name": "檢查產品"}],
                            "competency_blocks": [
                                {
                                    "competency_level": None,
                                    "outputs": [{"code": None, "name": "產品"}],
                                    "knowledge": [{"code": None, "name": "3D材料"}],
                                    "skills": [{"code": None, "name": "檢驗方法"}],
                                }
                            ],
                        }
                    ],
                }
            ]
        },
        "notes": {"supplements": ["保留【註1】說明"]},
    }
    data = json.dumps(document, ensure_ascii=False).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def test_cli_cleans_a_single_file_without_requiring_knowledge_or_skill_codes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "source.json"
    original = write_source(source)
    output, diagnostics = tmp_path / "cleaned", tmp_path / "diagnostics"

    assert (
        main(
            ["clean-json", str(source), str(output), "--diagnostics", str(diagnostics)]
        )
        == 0
    )

    assert json.loads(capsys.readouterr().out) == {"cleaned": 1, "rejected": 0}
    assert source.read_bytes() == original
    cleaned = json.loads((output / "source.json").read_text(encoding="utf-8"))
    assert cleaned["ocs_profile"]["job_description"] == "執行品質確認"
    assert "ocs_code" not in cleaned["ocs_profile"]
    block = cleaned["ocs_content"]["ocu_units"][0]["tasks"][0]["competency_blocks"][0]
    assert block["knowledge"] == [{"name": "3D材料"}]
    assert block["skills"] == [{"name": "檢驗方法"}]
    assert block["competency_level"] is None
    report = json.loads((diagnostics / "files/source.json").read_text("utf-8"))
    assert report["status"] == "cleaned"
    assert report["source"] == "source.json"
    assert report["source_sha256"] == sha256(original).hexdigest()
    assert (
        report["output_sha256"]
        == sha256((output / "source.json").read_bytes()).hexdigest()
    )


def test_recursive_cleaning_isolates_invalid_files_and_keeps_relative_paths(
    tmp_path: Path,
) -> None:
    source, output, diagnostics = (
        tmp_path / "source",
        tmp_path / "cleaned",
        tmp_path / "diagnostics",
    )
    original = write_source(source / "nested/report.json")
    write_source(source / "other/report.json")
    (source / "broken.json").write_bytes(b"{")
    (source / "wrong-shape.json").write_bytes(b'{"ocs_profile": 42}')
    (source / "ignored.txt").write_bytes(b"not JSON")
    output.mkdir()
    (output / "broken.json").write_bytes(b"previous accepted output")

    assert (
        main(
            ["clean-json", str(source), str(output), "--diagnostics", str(diagnostics)]
        )
        == 1
    )

    report = json.loads((diagnostics / "report.json").read_text("utf-8"))
    assert (report["cleaned"], report["rejected"]) == (2, 2)
    assert [item["source"] for item in report["files"]] == [
        "broken.json",
        "nested/report.json",
        "other/report.json",
        "wrong-shape.json",
    ]
    assert [item["status"] for item in report["files"]] == [
        "rejected",
        "cleaned",
        "cleaned",
        "rejected",
    ]
    assert (output / "nested/report.json").is_file()
    assert (output / "other/report.json").is_file()
    assert (output / "broken.json").read_bytes() == b"previous accepted output"
    assert not (output / "wrong-shape.json").exists()
    assert (source / "nested/report.json").read_bytes() == original
    assert (diagnostics / "files/nested/report.json").is_file()


def test_json_named_directory_does_not_reject_its_valid_json_children(
    tmp_path: Path,
) -> None:
    source, output, diagnostics = (
        tmp_path / "source",
        tmp_path / "cleaned",
        tmp_path / "diagnostics",
    )
    write_source(source / "nested.json/child.json")
    write_source(source / "root.json")

    assert (
        main(
            ["clean-json", str(source), str(output), "--diagnostics", str(diagnostics)]
        )
        == 0
    )

    report = json.loads((diagnostics / "report.json").read_text("utf-8"))
    assert (report["cleaned"], report["rejected"]) == (2, 0)
    assert (output / "nested.json/child.json").is_file()
    assert (output / "root.json").is_file()


@pytest.mark.parametrize(
    ("source_name", "output_name", "diagnostics_name"),
    [
        ("source", "source", "diagnostics"),
        ("source", "source/cleaned", "diagnostics"),
        ("parent/source", "parent", "diagnostics"),
        ("source", "cleaned", "source"),
        ("source", "cleaned", "source/diagnostics"),
        ("parent/source", "cleaned", "parent"),
        ("source", "cleaned", "cleaned"),
        ("source", "cleaned", "cleaned/diagnostics"),
        ("source", "diagnostics/cleaned", "diagnostics"),
    ],
)
def test_overlapping_directories_are_rejected_before_any_writes(
    tmp_path: Path, source_name: str, output_name: str, diagnostics_name: str
) -> None:
    source = tmp_path / source_name
    original = write_source(source / "input.json")

    with pytest.raises(ValueError, match="overlap"):
        main(
            [
                "clean-json",
                str(source),
                str(tmp_path / output_name),
                "--diagnostics",
                str(tmp_path / diagnostics_name),
            ]
        )

    assert (source / "input.json").read_bytes() == original
    assert list(tmp_path.rglob("*.json")) == [source / "input.json"]


@pytest.mark.parametrize("target", ["output", "diagnostics"])
def test_single_source_cannot_be_inside_a_destination_directory(
    tmp_path: Path, target: str
) -> None:
    source = tmp_path / target / "report.json"
    original = write_source(source)

    with pytest.raises(ValueError, match="overlap"):
        main(
            [
                "clean-json",
                str(source),
                str(tmp_path / "output"),
                "--diagnostics",
                str(tmp_path / "diagnostics"),
            ]
        )

    assert source.read_bytes() == original


def test_failed_output_replace_preserves_previous_file_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, output, diagnostics = (
        tmp_path / "source",
        tmp_path / "cleaned",
        tmp_path / "diagnostics",
    )
    write_source(source / "a.json")
    write_source(source / "b.json")
    output.mkdir()
    (output / "a.json").write_bytes(b"previous accepted output")
    replace = os.replace

    def fail_first_output(temporary: Path, destination: Path) -> None:
        if destination == output / "a.json":
            raise PermissionError("output not writable")
        replace(temporary, destination)

    monkeypatch.setattr(os, "replace", fail_first_output)

    assert (
        main(
            ["clean-json", str(source), str(output), "--diagnostics", str(diagnostics)]
        )
        == 1
    )

    assert (output / "a.json").read_bytes() == b"previous accepted output"
    assert (output / "b.json").is_file()
    assert not list(tmp_path.rglob("*.tmp"))
    result = json.loads((diagnostics / "files/a.json").read_text("utf-8"))
    assert result["status"] == "rejected"
    assert result["stage"] == "write"
    assert result["issues"][0]["type"] == "PermissionError"


@pytest.mark.parametrize("selection", ["missing", "empty"])
def test_missing_or_empty_input_is_rejected_without_output(
    tmp_path: Path, selection: str
) -> None:
    source = tmp_path / selection
    if selection == "empty":
        source.mkdir()
    with pytest.raises(ValueError, match="existing JSON"):
        main(
            [
                "clean-json",
                str(source),
                str(tmp_path / "cleaned"),
                "--diagnostics",
                str(tmp_path / "diagnostics"),
            ]
        )
    assert not (tmp_path / "cleaned").exists()
    assert not (tmp_path / "diagnostics").exists()
