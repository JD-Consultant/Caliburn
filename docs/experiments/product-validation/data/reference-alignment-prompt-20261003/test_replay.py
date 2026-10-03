"""Protect the experiment's single-factor and opaque-data boundaries."""

from copy import deepcopy

import pytest
from replay import ORIGINAL_REVIEW_RULE, make_candidate, public_copy


def test_candidate_changes_only_instructions_without_mutating_original():
    original = {
        "instructions": "before\n" + ORIGINAL_REVIEW_RULE + "\nafter",
        "input": [{"type": "reasoning", "encrypted_content": "secret-state"}],
        "tools": [{"name": "read_jd"}],
        "model": "gpt-6-luna",
    }
    before = deepcopy(original)
    candidate = make_candidate(original, "replacement rule")
    assert original == before
    assert candidate["instructions"] == "before\nreplacement rule\nafter"
    assert {k: v for k, v in candidate.items() if k != "instructions"} == {
        k: v for k, v in original.items() if k != "instructions"
    }


@pytest.mark.parametrize(
    "instructions", ["not the saved rule", ORIGINAL_REVIEW_RULE * 2]
)
def test_unexpected_baseline_is_rejected(instructions):
    with pytest.raises(ValueError, match="exactly once"):
        make_candidate({"instructions": instructions}, "replacement")


def test_public_copy_excludes_opaque_values_but_preserves_native_input():
    original = [
        {"type": "reasoning", "encrypted_content": "private-state", "summary": []}
    ]
    exported = public_copy({"input": original})
    assert exported == {
        "input": [
            {"type": "reasoning", "encrypted_content": "[omitted]", "summary": []}
        ]
    }
    assert original[0]["encrypted_content"] == "private-state"
