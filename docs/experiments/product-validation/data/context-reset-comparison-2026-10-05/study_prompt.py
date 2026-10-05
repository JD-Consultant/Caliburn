"""Frozen research instructions, independent of the evolving production prompt."""

from pathlib import Path

_PROMPTS = Path(__file__).resolve().with_name("prompts")
_ARM_FILES = {"raw": "raw.md", "summary": "summary.md", "memory": "memory.md"}


def instructions_for(arm: str) -> str:
    """Load only frozen Markdown; no product prompt, employee data, grading or model I/O.

    The caller supplies this text as request instructions and keeps turn data in input.
    Missing or empty files fail explicitly; no fallback silently changes an arm.
    """
    if arm not in _ARM_FILES:
        raise ValueError("Unsupported study arm; choose raw, summary or memory")
    sections = []
    for filename in ("common.md", _ARM_FILES[arm]):
        text = (_PROMPTS / filename).read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError(f"Empty study prompt: {filename}")
        sections.append(text)
    return "\n\n".join(sections) + "\n"
