"""Exact App-captured UTF-16 textarea selections; no locator or token issuance."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Selection:
    field_ref: str
    field_text: str
    start_utf16: int
    end_utf16: int
    selected_text: str


class SelectionError(ValueError):
    pass


def replace_utf16(text: str, start: int, end: int, selected_text: str, replacement: str) -> str:
    """Replace a nonempty exact range, retaining code points outside its boundaries.

    Capture text must already be the saved LF value. Only replacement line endings
    are normalized here; whole-field empty/whitespace rules belong to the domain.
    Splitting a grapheme is allowed when it is a valid native code-unit boundary.
    """
    if not all(isinstance(value, str) for value in (text, selected_text, replacement)):
        raise SelectionError("A selection must capture text and a text replacement.")
    if "\r" in text or type(start) is not int or type(end) is not int:
        raise SelectionError("Capture the saved LF field value and integer UTF-16 offsets.")
    replacement = replacement.replace("\r\n", "\n").replace("\r", "\n")
    try:
        encoded = text.encode("utf-16-le", errors="strict")
        replacement.encode("utf-16-le", errors="strict")
        if not 0 <= start < end <= len(encoded) // 2:
            raise SelectionError("Select a nonempty range within the captured field.")
        prefix = encoded[:start * 2].decode("utf-16-le", errors="strict")
        selected = encoded[start * 2:end * 2].decode("utf-16-le", errors="strict")
        suffix = encoded[end * 2:].decode("utf-16-le", errors="strict")
    except UnicodeError as exc:
        raise SelectionError("The selection or replacement splits or contains an invalid Unicode surrogate.") from exc
    if selected != selected_text:
        raise SelectionError("The exact selected text no longer matches the captured range.")
    return prefix + replacement + suffix
