"""Writer module."""

from jd_pdf_to_json.writers.base import BaseWriter
from jd_pdf_to_json.writers.json_writer import JSONWriter

__all__ = ["BaseWriter", "JSONWriter"]
