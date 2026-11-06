"""Clean a source copy without changing its task or note relationships."""

import re

from ocs_contract.models import OCSDocument
from pydantic import JsonValue

from .text import join_wrapped_lines

_CODE_FIELDS = {"code", "ocs_code", "ocu_code"}
_LEVEL_FIELDS = {"ocs_level", "competency_level"}
_SOURCE_MARKER = re.compile(r"^[TOP]\d+(?:[.-]\d+)+[.：:]?(?![A-Za-z0-9.])\s*")
_TASK_MARKER = re.compile(
    r"(?<![A-Za-z0-9【（(「\[])[-－]?T\d+(?:[.-]\d+)+[.：:]?"
    r"(?![A-Za-z0-9.\]】）)」])\s*"
)
_LIST_START = re.compile(
    r"^(?:[-*]\s|[•●▪]|[（(]?[0-9一二三四五六七八九十]+[.)）、](?!\d)|【註\d+】)"
)


def clean_text(value: str) -> str:
    """Join layout wraps, retaining lists, paragraphs, note links and wording."""
    paragraphs: list[str] = []
    value = value.replace("\u200b", "").replace("\ufeff", "")
    for raw_line in value.splitlines():
        line = re.sub(r"[^\S\n]+", " ", raw_line).strip()
        line = _SOURCE_MARKER.sub("", line)
        if line.startswith("職業別（職業代碼）："):
            line = line.replace("職業別（職業代碼）：", "職業別：", 1)
            line = re.sub(r"（\d{2,4}）\s*", "、", line).rstrip("、")
        if not line:
            if paragraphs and paragraphs[-1]:
                paragraphs.append("")
        elif not paragraphs or not paragraphs[-1] or _LIST_START.match(line):
            paragraphs.append(line)
        else:
            paragraphs[-1] = join_wrapped_lines(paragraphs[-1], line)
    return "\n".join(paragraphs).strip()


def _clean_value(value: JsonValue) -> JsonValue:
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, list):
        return [_clean_value(item) for item in value]
    if isinstance(value, dict):
        return clean_source_fields(value)
    return value


def clean_source_fields(source: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Clean source content fields; callers keep lookup identities separately."""
    result: dict[str, JsonValue] = {}
    code = source.get("code") or source.get("ocu_code")
    for key, value in source.items():
        if key in _CODE_FIELDS or key == "version_info":
            continue
        if value is None and key not in _LEVEL_FIELDS:
            continue
        if key in {"name", "text", "ocu_name"} and isinstance(value, str):
            if isinstance(code, str) and code:
                if key == "name" and code.startswith("T"):
                    value = _TASK_MARKER.sub("\n\n", value)
                value = re.sub(
                    rf"^{re.escape(code)}(?=\s|[^\x00-\x7f]|[:：、]|$)[\s:：、]*",
                    "",
                    value,
                )
        result[key] = _clean_value(value)
    return result


def clean_document(document: OCSDocument) -> dict[str, JsonValue]:
    """Remove structural codes; retain source nesting, array order and extras.

    This is a retrieval representation, not a replacement OCS source document.
    Null levels stay unknown; note markers retain their links to supplements.
    """
    return clean_source_fields(document.model_dump(mode="json"))
