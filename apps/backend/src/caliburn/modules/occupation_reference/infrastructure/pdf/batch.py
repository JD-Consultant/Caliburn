"""Convert a fixed PDF selection, retaining each outcome before the next file."""

from hashlib import sha256
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from .conversion import ConversionResult, convert_file, write_report


class InputSnapshot(TypedDict):
    source: str
    source_sha256: str | None
    read_error: NotRequired[str]


class ExcludedFile(TypedDict):
    source: str
    source_sha256: str | None
    status: Literal["excluded"]
    reason: str


class ConversionSummary(TypedDict):
    converted: int
    rejected: int
    excluded: int


def convert_pdfs(
    source: Path,
    output: Path,
    diagnostics: Path,
    *,
    exclude_historical: bool = False,
) -> ConversionSummary:
    """Fix source hashes before conversion; keep accepted JSON and reports apart."""
    output_root, diagnostics_root = output.resolve(), diagnostics.resolve()
    if output_root.is_relative_to(diagnostics_root) or diagnostics_root.is_relative_to(
        output_root
    ):
        raise ValueError("output and diagnostics directories must not overlap")
    files = sorted(source.rglob("*.pdf")) if source.is_dir() else [source]
    if not files or any(not path.is_file() for path in files):
        raise ValueError("select at least one existing PDF")
    source_root = source if source.is_dir() else source.parent
    manifest: list[InputSnapshot] = []
    for path in files:
        entry: InputSnapshot = {
            "source": path.relative_to(source_root).as_posix(),
            "source_sha256": None,
        }
        try:
            entry["source_sha256"] = sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            entry["read_error"] = str(error)
        manifest.append(entry)
    write_report(
        {
            "input_directory": str(source_root),
            "exclude_historical": exclude_historical,
            "files": manifest,
        },
        diagnostics / "input-manifest.json",
    )
    results: list[ConversionResult | ExcludedFile] = []
    for path, entry in zip(files, manifest, strict=True):
        relative = path.relative_to(source_root)
        result: ConversionResult | ExcludedFile
        if exclude_historical and "歷史資料" in path.name:
            result = ExcludedFile(
                source=entry["source"],
                source_sha256=entry["source_sha256"],
                status="excluded",
                reason=(
                    "Filename contains 歷史資料; latest official status not verified"
                ),
            )
        elif entry["source_sha256"] is None:
            result = ConversionResult(
                source=entry["source"],
                source_sha256=None,
                output=str(output / relative.with_suffix(".json")),
                status="rejected",
                stage="parse",
                issues=[{"type": "SourceReadError", "message": entry["read_error"]}],
            )
        else:
            result = convert_file(
                path,
                output / relative.with_suffix(".json"),
                diagnostics / "candidates" / relative.parent,
                expected_sha256=entry["source_sha256"],
            )
            result["source"] = entry["source"]
        write_report(result, diagnostics / "files" / relative.with_suffix(".json"))
        results.append(result)
    summary = ConversionSummary(
        converted=sum(result["status"] == "converted" for result in results),
        rejected=sum(result["status"] == "rejected" for result in results),
        excluded=sum(result["status"] == "excluded" for result in results),
    )
    write_report({**summary, "files": results}, diagnostics / "report.json")
    return summary
