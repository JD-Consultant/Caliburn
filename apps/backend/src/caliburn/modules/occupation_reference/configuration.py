"""Explicit deployment settings; importing the module performs no I/O."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReferenceConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    collection: str = Field(min_length=1)
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_timeout_seconds: int = Field(default=30, gt=0)
    embedding_path: Path | None = None
    reranker_path: Path | None = None
    cache_dir: Path | None = None
    device: Literal["cpu", "cuda"] = "cpu"
    use_fp16: bool = True
    batch_size: int = Field(default=8, ge=1)
    candidate_limit: int = Field(default=20, ge=1, le=80)
    admission_timeout_seconds: float = Field(default=5.0, gt=0)


def load_reference_configuration(path: Path) -> ReferenceConfiguration:
    """Read a deliberately selected file; relative paths use the process cwd."""
    return ReferenceConfiguration.model_validate_json(path.read_bytes())
