"""Chunk records produced by the builder + payload sent to Qdrant.

A ChunkRecord is the logical unit (text + metadata) before embedding.
After embedding, it becomes an EmbeddedChunk and finally a Qdrant point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ChunkLevel = Literal["profile", "unit", "block", "task"]


@dataclass
class ChunkRecord:
    chunk_key: str
    chunk_level: ChunkLevel
    text: str
    payload: dict[str, Any]


@dataclass
class Pair:
    """Code-name pair for K/S/A/output/evidence.

    Always written together — never separate code from name. Code-only
    lookups still use parallel `*_codes` arrays for Qdrant payload index
    filters; pairs prevent silent misalignment when source JSON has partial
    entries (filter conditions on parallel lists could otherwise drift).
    """

    code: str
    name: str


@dataclass
class SparseVector:
    indices: list[int]
    values: list[float]


@dataclass
class EmbeddedChunk:
    record: ChunkRecord
    dense: list[float]
    sparse: SparseVector | None = None
