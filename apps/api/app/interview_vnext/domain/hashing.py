"""Canonical serialization for deterministic state and artifact hashes."""

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


def sha256_utf8_text(text: str) -> str:
    """Hash raw text bytes with no trimming, newline, or NFKC normalization.

    QuestionFrame ``question_text_hash`` must prove the exact stored characters,
    so this deliberately hashes ``text`` as-is (see amendment plan §6.3).
    """

    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def canonical_hash_excluding(value: Any, *, exclude: str) -> str:
    """Canonical hash of ``value`` with one field removed.

    Self-referential hashes (target/option/definition) are computed over every
    field except the hash field itself, so builders and validators agree on the
    payload regardless of the stored hash value.
    """

    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json")
    else:
        payload = dict(value)
    payload.pop(exclude, None)
    return canonical_hash(payload)
