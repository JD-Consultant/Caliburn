"""Base writer class."""

from abc import ABC, abstractmethod
from pathlib import Path
from jd_pdf_to_json.core.models import OCSDocument


class BaseWriter(ABC):
    """Abstract base class for writers."""

    @abstractmethod
    def write(self, model: OCSDocument, output_path: Path) -> None:
        """
        Write OCS model to file.
        
        Args:
            model: OCSDocument to write
            output_path: Path to output file
        """
        pass
