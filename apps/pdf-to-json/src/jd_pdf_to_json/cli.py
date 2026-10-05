"""CLI entry point."""

import io
import json
import sys
from typing import Annotated

import typer

if isinstance(sys.stdout, io.TextIOWrapper) and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if isinstance(sys.stderr, io.TextIOWrapper) and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")
from hashlib import sha256
from pathlib import Path

from jd_pdf_to_json.conversion import convert_file, write_report
from jd_pdf_to_json.core.models import OCSDocument
from jd_pdf_to_json.utils.logger import logger
from jd_pdf_to_json.validators import OCSSchemaValidator

app = typer.Typer(
    help="OCS vocational competency PDF to JSON converter",
    no_args_is_help=True,
)


@app.command()
def convert(
    pdf_path: Annotated[Path, typer.Argument(help="Input PDF file", exists=True)],
    output_path: Annotated[
        Path | None, typer.Option("--output", "-o", help="Output JSON file")
    ] = None,
    validate: Annotated[
        bool,
        typer.Option(
            "--validate/--no-validate", help="Compatibility flag; required checks always apply"
        ),
    ] = True,
) -> None:
    """Convert one PDF, preserving the target when conversion is rejected."""
    output_path = output_path or pdf_path.with_suffix(".json")
    diagnostics = output_path.parent / f"{output_path.stem}.diagnostics"
    result = convert_file(pdf_path, output_path, diagnostics)
    write_report(result, diagnostics / "report.json")
    typer.echo(f"{result['status']}: {pdf_path.name}")
    if result["status"] != "converted":
        typer.echo(json.dumps(result["issues"], ensure_ascii=False), err=True)
        raise typer.Exit(1)


@app.command()
def batch(
    input_dir: Annotated[Path, typer.Argument(help="Directory with PDFs", exists=True)],
    output_dir: Annotated[Path, typer.Option("--output", "-o", help="Output directory")],
    validate: Annotated[
        bool,
        typer.Option(
            "--validate/--no-validate", help="Compatibility flag; required checks always apply"
        ),
    ] = True,
    exclude_historical: Annotated[
        bool, typer.Option("--exclude-historical", help="Exclude filenames containing 歷史資料")
    ] = False,
) -> None:
    """Convert a fixed, sorted directory listing; record exactly one outcome per PDF."""
    pdfs = sorted(input_dir.glob("*.pdf"))
    diagnostics = output_dir.parent / f"{output_dir.name}.diagnostics"
    manifest = []
    for pdf in pdfs:
        entry = {"source": pdf.name, "source_sha256": None}
        try:
            entry["source_sha256"] = sha256(pdf.read_bytes()).hexdigest()
        except OSError as error:
            entry["read_error"] = str(error)
        manifest.append(entry)
    write_report(
        {
            "input_directory": str(input_dir),
            "exclude_historical": exclude_historical,
            "files": manifest,
        },
        diagnostics / "input-manifest.json",
    )
    files = []
    for index, pdf in enumerate(pdfs, 1):
        if exclude_historical and "歷史資料" in pdf.name:
            files.append(
                {
                    "source": pdf.name,
                    "source_sha256": manifest[index - 1]["source_sha256"],
                    "status": "excluded",
                    "reason": "Filename contains 歷史資料; latest official status not verified",
                }
            )
        else:
            files.append(
                convert_file(
                    pdf,
                    output_dir / pdf.with_suffix(".json").name,
                    diagnostics,
                    manifest[index - 1]["source_sha256"],
                )
            )
        write_report(files[-1], diagnostics / "files" / pdf.with_suffix(".json").name)
        typer.echo(f"[{index}/{len(pdfs)}] {files[-1]['status']}: {pdf.name}")
    summary = {
        status: sum(item["status"] == status for item in files)
        for status in ("converted", "rejected", "excluded")
    }
    write_report({"summary": summary, "files": files}, diagnostics / "batch-report.json")
    typer.echo(json.dumps(summary, ensure_ascii=False))
    typer.echo(f"Report: {diagnostics / 'batch-report.json'}")
    if summary["rejected"]:
        raise typer.Exit(1)


@app.command()
def validate(
    json_path: Annotated[Path, typer.Argument(help="JSON file to validate", exists=True)],
) -> None:
    """Validate OCS JSON against schema."""
    try:
        logger.info(f"驗證: {json_path}")

        # 讀取 JSON
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        # 驗證
        ocs_doc = OCSDocument.model_validate(data)
        validator = OCSSchemaValidator()
        is_valid, errors = validator.validate(ocs_doc)

        if is_valid:
            typer.echo(f"✅ 驗證通過: {json_path}")
            logger.info(f"✓ {json_path} 驗證通過")
        else:
            typer.echo(f"❌ 驗證失敗: {json_path}")
            typer.echo(f"\n錯誤列表 ({len(errors)} 個):")
            for i, err in enumerate(errors, 1):
                typer.echo(f"  {i}. {err}")
            logger.error(f"✗ {json_path} 發現 {len(errors)} 個錯誤")
            raise typer.Exit(1)

    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失敗: {str(e)}")
        typer.echo(f"JSON 格式錯誤: {str(e)}", err=True)
        raise typer.Exit(1) from e
    except Exception as e:
        logger.error(f"驗證失敗: {str(e)}")
        typer.echo(f"驗證失敗: {str(e)}", err=True)
        raise typer.Exit(1) from e


@app.callback()
def main(
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose logging")
    ] = False,
) -> None:
    """OCS PDF to JSON Converter.

    支援的命令:
      convert   轉換單個 PDF 為 JSON
      batch     批次轉換目錄中的所有 PDF
      validate  驗證 JSON 是否符合 schema
    """
    if verbose:
        logger.enable("jd_pdf_to_json")


if __name__ == "__main__":
    app()
