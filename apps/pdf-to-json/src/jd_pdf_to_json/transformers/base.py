"""Base transformer class."""

from abc import ABC, abstractmethod

from jd_pdf_to_json.core.models import OCSDocument
from jd_pdf_to_json.parsers.models import PDFDocument


class BaseOCSTransformer(ABC):
    """Abstract transformer: raw data → OCS model."""

    @abstractmethod
    def transform(self, raw_data: PDFDocument) -> OCSDocument:
        """
        Transform parsed PDF data into structured OCS model.

        Args:
            raw_data: Detached PDFDocument from parser

        Returns:
            Validated OCSDocument model

        Raises:
            TransformationError: If transformation fails
        """
        pass
