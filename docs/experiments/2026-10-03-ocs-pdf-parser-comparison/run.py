"""Isolated raw PDF extraction probe; does not run or change OCS production conversion."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time

import psutil


def make_extractor(engine: str, model_dir: Path):
    if engine == "pdfplumber":
        import pdfplumber

        def extract(path: Path) -> dict:
            pages = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    tables = []
                    for table in page.find_tables():
                        tables.append({"bbox": table.bbox, "grid": table.extract(),
                                       "cell_boxes": table.cells})
                    pages.append({"number": page.page_number,
                                  "text": page.extract_text() or "", "tables": tables})
            return {"pages": pages}

        return extract
    if engine in {"camelot", "camelot-lattice"}:
        import camelot

        def extract(path: Path) -> dict:
            tables = camelot.read_pdf(str(path), pages="all",
                                      flavor="lattice" if engine.endswith("lattice") else "auto",
                                      suppress_stdout=True)
            pages = {}
            for table in tables:
                number = int(table.page)
                page = pages.setdefault(number, {"number": number, "text": "", "tables": []})
                cells = [{"text": cell.text, "bbox": [cell.x1, cell.y1, cell.x2, cell.y2],
                          "hspan": cell.hspan, "vspan": cell.vspan}
                         for row in table.cells for cell in row]
                page["tables"].append({"bbox": table._bbox, "grid": table.df.values.tolist(),
                                       "cells": cells, "parsing_report": table.parsing_report})
            # Camelot is a table extractor. This text is table text, not full-page text.
            for page in pages.values():
                page["text"] = "\n".join(str(value) for table in page["tables"]
                                          for row in table["grid"] for value in row if value)
            return {"pages": sorted(pages.values(), key=lambda page: page["number"]),
                    "text_scope": "tables_only"}

        return extract
    if engine == "docling":
        from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
        from docling.document_converter import DocumentConverter, PdfFormatOption

        options = PdfPipelineOptions(artifacts_path=model_dir, do_ocr=False,
                                     enable_remote_services=False, do_table_structure=True)
        options.accelerator_options = AcceleratorOptions(num_threads=4, device=AcceleratorDevice.CPU)
        options.table_structure_options.mode = TableFormerMode.ACCURATE
        converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})

        def extract(path: Path) -> dict:
            result = converter.convert(path)
            document = result.document
            pages = {int(number): {"number": int(number), "text": "", "tables": []}
                     for number in document.pages}
            for item in document.texts:
                for provenance in item.prov:
                    pages[provenance.page_no]["text"] += item.text + "\n"
            for table in document.tables:
                grid = [[None] * table.data.num_cols for _ in range(table.data.num_rows)]
                cells = []
                for cell in table.data.table_cells:
                    grid[cell.start_row_offset_idx][cell.start_col_offset_idx] = cell.text
                    cells.append(cell.model_dump(mode="json"))
                provenance = [item.model_dump(mode="json") for item in table.prov]
                page_number = table.prov[0].page_no
                pages[page_number]["tables"].append({"grid": grid, "cells": cells, "prov": provenance})
                pages[page_number]["text"] += "\n".join(cell.text for cell in table.data.table_cells) + "\n"
            return {"pages": sorted(pages.values(), key=lambda page: page["number"]),
                    "conversion_status": str(result.status),
                    "errors": [error.model_dump(mode="json") for error in result.errors]}

        return extract
    raise ValueError(engine)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("engine", choices=["pdfplumber", "camelot", "camelot-lattice", "docling"])
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--models", required=True, type=Path)
    args = parser.parse_args()
    os.environ.setdefault("OMP_NUM_THREADS", "4")
    args.output.mkdir(parents=True, exist_ok=True)
    temporary_dir = args.output / "temporary"
    temporary_dir.mkdir(exist_ok=True)
    tempfile.tempdir = str(temporary_dir)
    cases = json.loads(Path(__file__).with_name("cases.json").read_text(encoding="utf-8"))
    process = psutil.Process()
    peak = [0]
    stop = threading.Event()

    def monitor() -> None:
        while not stop.wait(0.05):
            peak[0] = max(peak[0], process.memory_info().rss)

    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    start = time.perf_counter()
    extract = make_extractor(args.engine, args.models)
    initialization_seconds = time.perf_counter() - start
    metrics = {"engine": args.engine, "python": sys.version,
               "versions": {name: importlib.metadata.version(name) for name in
                            ["pdfplumber", "camelot-py", "docling", "torch", "docling-core", "docling-parse"]},
               "initialization_seconds": initialization_seconds, "documents": []}
    metrics["settings"] = {"pdfplumber": "default find_tables/extract_text",
                           "camelot": "auto; tables only",
                           "camelot-lattice": "lattice; tables only",
                           "docling": "standard pipeline; CPU 4 threads; OCR off; accurate; cell matching on"}[args.engine]
    try:
        for case in cases:
            path = args.repo / case["path"]
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != case["sha256"]:
                raise ValueError(f"Source changed: {path}")
            started = time.perf_counter()
            try:
                extracted = extract(path)
                record = {"id": case["id"], "status": "ok",
                          "seconds": time.perf_counter() - started,
                          "pages": len(extracted["pages"]),
                          "tables": sum(len(page["tables"]) for page in extracted["pages"])}
                (args.output / f"{args.engine}-{case['id']}.json").write_text(
                    json.dumps(extracted, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as error:
                record = {"id": case["id"], "status": "error",
                          "seconds": time.perf_counter() - started,
                          "error": f"{type(error).__name__}: {error}"}
            metrics["documents"].append(record)
            metrics["peak_rss_mib"] = round(peak[0] / 1024 ** 2, 1)
            (args.output / f"{args.engine}-metrics.json").write_text(
                json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(record, ensure_ascii=False), flush=True)
    finally:
        stop.set()
        thread.join()


if __name__ == "__main__":
    main()
