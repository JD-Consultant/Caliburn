"""JSON writer implementation."""

from pathlib import Path
from jd_pdf_to_json.writers.base import BaseWriter
from jd_pdf_to_json.core.models import OCSDocument
from jd_pdf_to_json.utils.logger import logger


class JSONWriter(BaseWriter):
    """Write OCS model to JSON file."""

    def write(self, model: OCSDocument, output_path: Path) -> None:
        """
        Write validated model to JSON file with UTF-8 encoding.
        
        Args:
            model: OCSDocument to write
            output_path: Path to output JSON file
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            json_str = model.model_dump_json(indent=2, ensure_ascii=False)
            output_path.write_text(json_str, encoding="utf-8")
            
            logger.info(f"Written JSON to {output_path}")
        except Exception as e:
            logger.error(f"Failed to write JSON: {str(e)}")
            raise
