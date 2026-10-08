"""Plan editing reuses the bounded V4A editor while allowing nullable/empty bodies."""

import pytest

from caliburn.adapters.body_edits import apply_body_diff
from caliburn.adapters.body_matching import BodyEditError, BodyMatchPolicy


def test_plan_can_be_created_from_empty_body_at_explicit_eof() -> None:
    assert (
        apply_body_diff(
            "", "@@\n+## 未釐清子任務\n+- 盤點範圍\n*** End of File", allow_blank_body=True
        )
        == "## 未釐清子任務\n- 盤點範圍"
    )


def test_plan_can_be_cleared_to_empty_body() -> None:
    assert (
        apply_body_diff(
            "## 未釐清子任務\n- 盤點範圍",
            "@@\n-## 未釐清子任務\n-- 盤點範圍\n*** End of File",
            allow_blank_body=True,
        )
        == ""
    )


def test_empty_eof_line_insertion_has_no_text_effect() -> None:
    assert apply_body_diff("", "@@\n+\n*** End of File", allow_blank_body=True) == ""


def test_blank_plan_policy_does_not_strip_whitespace_or_change_line_endings() -> None:
    assert (
        apply_body_diff(" \r\n", "@@\n+保留\n*** End of File", allow_blank_body=True)
        == " \r\n保留\r\n"
    )


def test_blank_plan_policy_keeps_capacity_rejection() -> None:
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff(
            "",
            "@@\n+too long\n*** End of File",
            policy=BodyMatchPolicy(max_body_characters=1),
            allow_blank_body=True,
        )
    assert caught.value.code == "patch_limit_exceeded"
