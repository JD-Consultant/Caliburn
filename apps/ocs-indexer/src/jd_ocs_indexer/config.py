"""Runtime settings loaded from environment / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _env_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required env var {name} is not set")
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


@dataclass(frozen=True)
class Settings:
    qdrant_url: str
    qdrant_api_key: str | None
    qdrant_collection: str
    qdrant_timeout: float

    source_root: Path

    index_batch_size: int

    # Embedder service (ADR 0012): BGE-M3 served by apps/embedder over HTTP.
    embedder_url: str

    extra: dict[str, str] = field(default_factory=dict)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return float(value)


def load_settings() -> Settings:
    source_root = Path(_env("OCS_SOURCE_ROOT", "./data") or "")
    return Settings(
        qdrant_url=_env("QDRANT_URL", "http://localhost:6333") or "",
        qdrant_api_key=_env("QDRANT_API_KEY"),
        qdrant_collection=_env("QDRANT_COLLECTION", "ocs_v4") or "ocs_v4",
        qdrant_timeout=_env_float("QDRANT_TIMEOUT", 300.0),
        source_root=source_root,
        index_batch_size=_env_int("INDEX_BATCH_SIZE", 32),
        embedder_url=_env("EMBEDDER_URL", "http://localhost:8082") or "http://localhost:8082",
    )
