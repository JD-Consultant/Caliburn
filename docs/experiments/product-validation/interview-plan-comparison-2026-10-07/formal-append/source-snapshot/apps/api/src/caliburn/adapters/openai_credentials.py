"""Read only an explicitly selected direct OpenAI credential; never load legacy settings."""

import re
from pathlib import Path


def read_openai_api_key(path: Path) -> str:
    values = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        name, separator, value = line.strip().partition("=")
        if separator and name.strip() == "OPENAI_API_KEY":
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values.append(value)
    if len(values) != 1 or not re.fullmatch(r"[A-Za-z0-9_-]+", values[0]):
        raise ValueError("Exactly one plain OPENAI_API_KEY value is required")
    return values[0]
