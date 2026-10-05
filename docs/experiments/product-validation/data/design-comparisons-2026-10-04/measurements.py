"""Scoring and public trace projection, independent of the fixture generator."""

import hashlib
from copy import deepcopy
from typing import Any


def score_context(
    expected: dict[str, str], sources: list[int], answer: object
) -> dict[str, bool]:
    payload = answer if isinstance(answer, dict) else {}
    facts = payload.get("facts", {})
    facts = facts if isinstance(facts, dict) else {}
    checks = {name: facts.get(name) == value for name, value in expected.items()}
    selected = payload.get("interview_sequences")
    checks["sources"] = (
        isinstance(selected, list)
        and all(type(value) is int for value in selected)
        and len(selected) == len(set(selected))
        and set(selected) == set(sources)
    )
    return checks


def score_locator(expected: list[int], selected: list[int]) -> bool:
    return expected == selected


def public_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = deepcopy(items)
    for item in result:
        if item.get("type") == "reasoning":
            item.pop("content", None)
        encrypted = item.pop("encrypted_content", None)
        if encrypted is not None:
            item["encrypted_length"] = len(encrypted)
            item["encrypted_sha256"] = hashlib.sha256(encrypted.encode()).hexdigest()
    return result
