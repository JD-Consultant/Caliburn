"""Base classes for parsers."""

from abc import ABC, abstractmethod
from pathlib import Path

from jd_pdf_to_json.parsers.models import PDFDocument


class BasePDFParser(ABC):
    """Abstract base class for PDF parsers."""

    @abstractmethod
    def parse(self, pdf_path: Path) -> PDFDocument:
        """
        Parse PDF and extract raw data.

        Args:
            pdf_path: Path to PDF file

        Returns:
            PDFDocument with extracted text, tables and source positions

        Raises:
            PDFParsingError: If parsing fails
        """
        pass

    @abstractmethod
    def validate_source(self, source: PDFDocument) -> bool:
        """
        Verify PDF is readable OCS format.

        Args:
            source: Detached PDFDocument

        Returns:
            True if PDF appears to be valid OCS document
        """
        pass
