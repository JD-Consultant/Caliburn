"""Base classes for parsers."""

from abc import ABC, abstractmethod
from pathlib import Path


class BasePDFParser(ABC):
    """Abstract base class for PDF parsers."""

    @abstractmethod
    def parse(self, pdf_path: Path) -> dict:
        """
        Parse PDF and extract raw data.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with extracted raw data
            
        Raises:
            PDFParsingError: If parsing fails
        """
        pass

    @abstractmethod
    def validate_source(self, pdf_path: Path) -> bool:
        """
        Verify PDF is readable OCS format.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            True if PDF appears to be valid OCS document
        """
        pass
