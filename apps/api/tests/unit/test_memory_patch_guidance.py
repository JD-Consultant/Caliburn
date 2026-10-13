"""Rejection guidance preserves parser diagnostics and provides executable syntax."""

import json
import re

import pytest

from caliburn.adapters.body_matching import BodyEditError, BodyMatchPolicy
from caliburn.features.work_memory.body_edits import apply_body_diff
from caliburn.transport.model_tools.memory_writes import _patch_rejection


@pytest.mark.parametrize(
    ("body", "patch", "expected_code", "policy"),
    [
        ("原文\n", "@@", "invalid_patch", BodyMatchPolicy()),
        ("原文\n", "@@\n-原文", "invalid_patch", BodyMatchPolicy()),
        ("原文\n", "@@\n-不存在\n+修改", "patch_context_not_found", BodyMatchPolicy()),
        ("重複\n重複\n", "@@\n-重複\n+修改", "ambiguous_patch_context", BodyMatchPolicy()),
        (
            "原文\n",
            "@@\n-原文\n+修改",
            "patch_limit_exceeded",
            BodyMatchPolicy(max_diff_characters=1),
        ),
    ],
)
def test_real_parser_failures_keep_their_code_message_and_candidate_locations(
    body, patch, expected_code, policy
):
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff(body, patch, policy=policy)
    error = caught.value
    result = json.loads(_patch_rejection(error))
    assert result["status"] == "rejected"
    assert result["code"] == expected_code
    assert str(error) in result["message"]
    assert result["next_action"]
    if error.hunk_number is not None:
        assert f"Hunk {error.hunk_number}:" in result["message"]
    for candidate in error.candidates:
        assert candidate.excerpt in result["message"]


def test_minimal_replacement_example_in_rejection_is_valid_body_v4a():
    result = json.loads(_patch_rejection(BodyEditError("invalid_patch", "Invalid syntax")))
    patch = re.search(r"(@@\n-.*\n\+[^\n]*)", result["next_action"]).group(1)
    lines = patch.splitlines()
    source, replacement = lines[1][1:], lines[2][1:]
    assert apply_body_diff(source + "\n", patch) == replacement + "\n"
