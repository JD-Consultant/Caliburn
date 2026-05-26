"""Deterministic point ids."""

from __future__ import annotations

import uuid


NAMESPACE = uuid.UUID("6f1c8a3e-3e0b-4f0f-9c2e-0c5000000001")


def point_id(chunk_key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, chunk_key))
