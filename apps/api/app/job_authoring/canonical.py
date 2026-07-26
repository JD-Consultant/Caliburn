"""Canonical serialization for deterministic authoring hashes.

Line-for-line the same rules as the interview vNext hash helper
(``ensure_ascii=False``, ``sort_keys=True``, ``separators=(",", ":")``,
``allow_nan=False``). Kept as an independent 15-line copy per plan §6.2 so the
Authoring core never imports the interview vNext domain; a parity test proves
byte/hash equality. Do not widen the R5 blast radius for this — extract a shared
utility only if a genuine third consumer appears.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def canonical_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_hash(value: Any) -> str:
    encoded = canonical_json(value).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def canonical_hash_excluding(value: Any, *, exclude: str) -> str:
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json")
    else:
        payload = dict(value)
    payload.pop(exclude, None)
    return canonical_hash(payload)
