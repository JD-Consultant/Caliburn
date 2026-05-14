"""CLI entry point."""

import json
import typer
from datetime import datetime
from pathlib import Path
from typing import Optional

from jd_pdf_to_json.parsers import PDFPlumberParser
from jd_pdf_to_json.transformers import OCSTransformer
from jd_pdf_to_json.validators import OCSSchemaValidator
from jd_pdf_to_json.writers import JSONWriter
from jd_pdf_to_json.utils.logger import logger
from jd_pdf_to_json.utils.exceptions import (
    PDFParsingError,
    TransformationError,
    ValidationError,
)

app = typer.Typer(
    help="OCS vocational competency PDF to JSON converter",
    no_args_is_help=True,
)


@app.command()
def convert(
    pdf_path: Path = typer.Argument(..., help="Input PDF file", exists=True),
    output_path: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output JSON file (default: input_name.json)"
    ),
    validate: bool = typer.Option(True, "--validate/--no-validate", help="Enable schema validation"),
) -> None:
    """Convert single OCS PDF to JSON.
    
    Pipeline: PDF → Parse → Transform → Validate → Write JSON
    """
    if output_path is None:
        output_path = pdf_path.with_suffix(".json")
    
    try:
        logger.info(f"開始轉換: {pdf_path}")
        logger.info(f"輸出: {output_path}")
        logger.info(f"驗證: {'啟用' if validate else '停用'}")
        
        # =========== PARSE ===========
        logger.info("【1/4】解析 PDF...")
        parser = PDFPlumberParser()
        raw_data = parser.parse(pdf_path)
        
        if not parser.validate_source(pdf_path):
            logger.warning("⚠️  PDF 可能不是 OCS 文件（未找到關鍵字）")
        
        logger.info("✓ 解析完成")
        
        # =========== TRANSFORM ===========
        logger.info("【2/4】轉換為 OCS 模型...")
        transformer = OCSTransformer()
        ocs_doc = transformer.transform({
            "file_path": str(pdf_path),
            "metadata": raw_data.get("metadata", {}),
            "pages": raw_data.get("pages", []),
        })
        logger.info("✓ 轉換完成")
        
        # =========== VALIDATE ===========
        if validate:
            logger.info("【3/4】驗證 Schema...")
            validator = OCSSchemaValidator()
            is_valid, errors = validator.validate(ocs_doc)

            if is_valid:
                logger.info("✓ 驗證通過")
            else:
                logger.warning(f"⚠️  驗證失敗，發現 {len(errors)} 個錯誤:")
                # 記錄驗證錯誤到 log 檔
                log_dir = Path("logs")
                log_dir.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                log_name = pdf_path.stem.replace(" ", "_")
                log_path = log_dir / f"convert_{log_name}_{timestamp}.log"
                log_lines = [
                    f"=== Conversion Validation Log ===",
                    f"PDF  : {pdf_path.name}",
                    f"Time : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    f"",
                ]
                for err in errors:
                    logger.warning(f"  - {err}")
                    log_lines.append(f"- {err}")
                log_path.write_text("\n".join(log_lines), encoding="utf-8")
                logger.info(f"Log  : {log_path}")
        else:
            logger.info("【3/4】略過驗證")
        
        # =========== WRITE ===========
        logger.info("【4/4】輸出 JSON...")
        writer = JSONWriter()
        writer.write(ocs_doc, output_path)
        logger.info(f"✓ 轉換完成，已輸出至: {output_path}")
        
        typer.echo(f"\n✅ 成功轉換: {pdf_path} → {output_path}")
        
    except PDFParsingError as e:
        logger.error(f"❌ 解析錯誤: {str(e)}")
        typer.echo(f"解析失敗: {str(e)}", err=True)
        raise typer.Exit(1)
    except TransformationError as e:
        logger.error(f"❌ 轉換錯誤: {str(e)}")
        typer.echo(f"轉換失敗: {str(e)}", err=True)
        raise typer.Exit(1)
    except ValidationError as e:
        logger.error(f"❌ 驗證錯誤: {str(e)}")
        typer.echo(f"驗證失敗: {str(e)}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        logger.error(f"❌ 輸出錯誤: {str(e)}")
        typer.echo(f"輸出失敗: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def batch(
    input_dir: Path = typer.Argument(..., help="Directory with PDFs", exists=True),
    output_dir: Path = typer.Option(..., "--output", "-o", help="Output directory"),
    validate: bool = typer.Option(True, "--validate/--no-validate", help="Enable schema validation"),
) -> None:
    """Batch convert OCS PDFs from directory.
    
    Converts all PDF files in input_dir to JSON in output_dir.
    """
    try:
        # 建立輸出目錄
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 尋找所有 PDF 檔案
        pdf_files = list(input_dir.glob("*.pdf"))
        
        if not pdf_files:
            logger.warning(f"在 {input_dir} 中未找到 PDF 檔案")
            typer.echo(f"未找到 PDF 檔案: {input_dir}")
            raise typer.Exit(0)
        
        logger.info(f"找到 {len(pdf_files)} 個 PDF 檔案")

        # 建立 log 目錄與本次紀錄檔
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = log_dir / f"batch_{timestamp}.log"
        log_lines: list[str] = [
            f"=== Batch Validation Log ===",
            f"Run : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"PDFs: {len(pdf_files)}",
            f"Out : {output_dir}",
            "",
        ]

        success_count = 0
        fail_count = 0
        validation_fail_count = 0

        for idx, pdf_path in enumerate(pdf_files, 1):
            output_path = output_dir / pdf_path.with_suffix(".json").name

            typer.echo(f"\n[{idx}/{len(pdf_files)}] 轉換: {pdf_path.name}")

            try:
                parser = PDFPlumberParser()
                raw_data = parser.parse(pdf_path)

                transformer = OCSTransformer()
                ocs_doc = transformer.transform({
                    "file_path": str(pdf_path),
                    "metadata": raw_data.get("metadata", {}),
                    "pages": raw_data.get("pages", []),
                })

                if validate:
                    validator = OCSSchemaValidator()
                    is_valid, errors = validator.validate(ocs_doc)
                    if not is_valid:
                        logger.warning(f"[{pdf_path.name}] 驗證失敗: {len(errors)} 個錯誤")
                        log_lines.append(f"[FAIL] {pdf_path.name} ({len(errors)} errors)")
                        for err in errors:
                            log_lines.append(f"  - {err}")
                        log_lines.append("")
                        validation_fail_count += 1

                writer = JSONWriter()
                writer.write(ocs_doc, output_path)

                logger.info(f"✓ {pdf_path.name} → {output_path.name}")
                success_count += 1

            except Exception as e:
                logger.error(f"✗ 轉換失敗: {pdf_path.name} - {str(e)}")
                log_lines.append(f"[ERROR] {pdf_path.name}: {str(e)}")
                log_lines.append("")
                fail_count += 1

        # 摘要
        log_lines += [
            "=== Summary ===",
            f"Total             : {len(pdf_files)}",
            f"OK                : {success_count}",
            f"Validation errors : {validation_fail_count}",
            f"Convert errors    : {fail_count}",
        ]
        log_path.write_text("\n".join(log_lines), encoding="utf-8")

        typer.echo(f"\n{'='*60}")
        typer.echo(f"批次轉換摘要:")
        typer.echo(f"  總計: {len(pdf_files)} 個")
        typer.echo(f"  成功: {success_count} (OK)")
        typer.echo(f"  驗證錯誤: {validation_fail_count}")
        typer.echo(f"  轉換失敗: {fail_count} (FAIL)")
        typer.echo(f"輸出目錄: {output_dir}")
        typer.echo(f"驗證 Log: {log_path}")
        typer.echo(f"{'='*60}")
        
        if fail_count > 0 or validation_fail_count > 0:
            raise typer.Exit(1)
            
    except Exception as e:
        logger.error(f"錯誤: {str(e)}")
        typer.echo(f"批次轉換失敗: {str(e)}", err=True)
        raise typer.Exit(1)


@app.command()
def validate(
    json_path: Path = typer.Argument(..., help="JSON file to validate", exists=True),
) -> None:
    """Validate OCS JSON against schema."""
    try:
        logger.info(f"驗證: {json_path}")
        
        # 讀取 JSON
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 驗證
        validator = OCSSchemaValidator()
        is_valid, errors = validator.validate(data)
        
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
        raise typer.Exit(1)
    except Exception as e:
        logger.error(f"驗證失敗: {str(e)}")
        typer.echo(f"驗證失敗: {str(e)}", err=True)
        raise typer.Exit(1)


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
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
