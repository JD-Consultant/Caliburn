"""JSON writer implementation."""

import os
import tempfile
from pathlib import Path

from jd_pdf_to_json.core.models import OCSDocument
from jd_pdf_to_json.utils.logger import logger
from jd_pdf_to_json.writers.base import BaseWriter


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
            write_text_atomically(json_str, output_path)

            logger.info(f"Written JSON to {output_path}")
        except Exception as e:
            logger.error(f"Failed to write JSON: {str(e)}")
            raise


def write_text_atomically(text: str, output_path: Path) -> None:
    """Complete a same-directory temporary file before replacing the target."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=output_path.parent, suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
