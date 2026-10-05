"""Text normalization helpers (moved verbatim from OCSTransformer, Phase 3b)."""

import re
import unicodedata
from typing import Any


def normalize_code_spacing(text: str) -> str:
    """Join a spaced item prefix and its number without joining Latin words."""
    return re.sub(r"\b([PTOKS])\s+(?=\.?\d)", r"\1", text, flags=re.IGNORECASE)


def join_wrapped_lines(previous: str, following: str) -> str:
    """Join layout wrapping while retaining a separator between Latin words."""
    if not previous:
        return following
    separator = (
        " "
        if previous[-1].isascii()
        and previous[-1].isalnum()
        and following[:1].isascii()
        and following[:1].isalnum()
        else ""
    )
    return previous + separator + following


def section_lines(pdf, start: str, *, end: str | None = None, qualifier: str = "") -> list[str]:
    """Locate source headings, excluding repeated headings and pagination only."""
    lines = []
    active = False
    for page in pdf.pages:
        for raw_line in (page.text or "").splitlines():
            line = raw_line.strip()
            normalized = normalize_text(line)
            prefix = re.split(r"[：:]", line, maxsplit=1)[0]
            heading = normalize_text(prefix)
            starts_section = (
                any(
                    normalized.startswith(label)
                    for label in (("職能內涵", "職業內涵") if start == "職能內涵" else (start,))
                )
                and qualifier in normalized
                if qualifier
                else heading in {start, start + "事項"}
            )
            if starts_section:
                active = True
                if re.search(r"[：:]", line):
                    line = re.split(r"[：:]", line, maxsplit=1)[1].strip()
                else:
                    continue
            if active and end and heading in {end, end + "事項"}:
                return lines
            if (
                not active
                or not line
                or re.fullmatch(r"第\s*\d+\s*頁[，,、\s]*(?:總共|共)\s*\d+\s*頁", line)
            ):
                continue
            lines.append(line)
    return lines


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
    # Keep separators between Latin words; Chinese layout wrapping has no
    # semantic space. Header matching uses a separate, more aggressive helper.
    text = re.sub(r"(?<=[A-Za-z0-9])\s+(?=[A-Za-z0-9])", "\0", text)
    text = re.sub(r"\s+", "", text)
    return text.replace("\0", " ").strip()


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
