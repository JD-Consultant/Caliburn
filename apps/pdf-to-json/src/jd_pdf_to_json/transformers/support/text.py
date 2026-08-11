"""Text normalization helpers (moved verbatim from OCSTransformer, Phase 3b)."""

import re
import unicodedata
from typing import Any


def normalize_text(value: Any) -> str:
    """Normalize text for robust header matching across layouts."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\n", " ").replace("\r", " ")
    text = re.sub(r"[\s　]+", "", text)
    text = re.sub(r"[：:()（）\[\]【】、,，.-]+", "", text)
    return text.lower().strip()


def compact_wrapped_text(value: Any) -> str:
    """Collapse a wrapped cell value into a single readable line."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("\r", "").replace("\n", "")
    return re.sub(r"\s+", "", text).strip()


def split_lines(value: Any) -> list[str]:
    """Split cell text by newline, keeping slash-combined phrases intact."""
    if not value:
        return []
    text = unicodedata.normalize("NFKC", str(value)).replace("\r", "\n")
    return [line.strip() for line in text.split("\n") if line and line.strip()]


def split_multi_value(value: str) -> list[str]:
    """Split a profile cell into candidate items on common delimiters."""
    normalized = unicodedata.normalize("NFKC", value)
    parts = re.split(r"[、,，;；\n]+", normalized)
    return [p.strip() for p in parts if p and p.strip()]


def append_text_if_new(original: str, tail: str) -> str:
    """Append continuation text only when it is not already present."""
    if not tail:
        return original
    if not original:
        return tail
    if tail in original:
        return original
    return f"{original}{tail}"
