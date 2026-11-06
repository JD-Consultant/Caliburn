"""JSON writer implementation."""

import os
import tempfile
from pathlib import Path

from ocs_contract.models import OCSDocument


def write_document(model: OCSDocument, output_path: Path) -> None:
    """Write the validated OCS model atomically as UTF-8 JSON."""
    write_text_atomically(
        model.model_dump_json(indent=2, ensure_ascii=False), output_path
    )


def write_text_atomically(text: str, output_path: Path) -> None:
    """Complete a same-directory temporary file before replacing the target."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
