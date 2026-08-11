"""Parser module."""

from jd_pdf_to_json.parsers.base import BasePDFParser
from jd_pdf_to_json.parsers.pdf_parser import PDFPlumberParser

__all__ = ["BasePDFParser", "PDFPlumberParser"]
