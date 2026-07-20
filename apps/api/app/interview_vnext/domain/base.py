"""Shared Pydantic policy for immutable domain values."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    """Strict immutable value object.

    Frozen Pydantic models prevent attribute assignment. Collection fields use
    tuples so callers cannot mutate nested state through a retained list.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
