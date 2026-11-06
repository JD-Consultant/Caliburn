"""Extract text, tables and positions once, from a fixed PDF byte snapshot."""

from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pdfplumber

from ..errors import PDFParsingError
from .models import (
    PDFDocument,
    PDFPage,
    PDFTable,
)


class PDFPlumberParser:
    def parse(self, pdf_path: Path) -> PDFDocument:
        try:
            source = pdf_path.read_bytes()
            pages = []
            with pdfplumber.open(BytesIO(source)) as pdf:
                for number, page in enumerate(pdf.pages, 1):
                    tables = [
                        PDFTable(
                            rows=table.extract(),
                            cells=[row.cells for row in table.rows],
                            bbox=table.bbox,
                            page_number=number,
                            table_number=index,
                        )
                        for index, table in enumerate(page.find_tables(), 1)
                    ]
                    pages.append(
                        PDFPage(
                            page_number=number,
                            text=page.extract_text() or "",
                            tables=tables,
                            words=[
                                {
                                    "text": word["text"],
                                    "x0": word["x0"],
                                    "x1": word["x1"],
                                    "top": word["top"],
                                    "bottom": word["bottom"],
                                }
                                for word in page.extract_words()
                            ],
                            width=page.width,
                            height=page.height,
                        )
                    )
            if not pages:
                raise PDFParsingError("PDF has no pages")
            return PDFDocument(pdf_path, sha256(source).hexdigest(), pages)
        except Exception as exc:
            raise PDFParsingError(f"Failed to parse {pdf_path.name}: {exc}") from exc

    def validate_source(self, source: PDFDocument) -> bool:
        return bool(source.pages) and any(
            keyword in source.pages[0].text
            for keyword in ("職能基準", "職能", "工作任務", "行為指標")
        )
