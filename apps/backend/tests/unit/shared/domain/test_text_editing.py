"""兩個業務模組共用編修演算法，各自保留容量政策。"""

import pytest


def test_shared_edit_preserves_actual_context_and_supports_memory_capacity() -> None:
    from caliburn.shared.domain.text_editing.body_edits import (
        EditLimits,
        apply_body_diff,
    )

    body = "背景" * 9000 + "\n每週執行完整資料核對流程\r\n原內容\r\n"
    result = apply_body_diff(
        body,
        "@@\n 每週執行完整資料核對流成\n-原內容\n+新內容\n",
        limits=EditLimits(50000, 50000, 32, 20000000),
    )
    assert result == body.replace("原內容", "新內容")


def test_shared_edit_rejects_ambiguous_match_without_changing_original() -> None:
    from caliburn.shared.domain.text_editing.body_edits import (
        EditLimits,
        apply_body_diff,
    )
    from caliburn.shared.domain.text_editing.errors import TextEditError

    body = "共同項目\n共同項目\n"
    with pytest.raises(TextEditError, match="Multiple"):
        apply_body_diff(
            body,
            "@@\n-共同項目\n+更正項目\n",
            limits=EditLimits(100, 100, 2, 10000),
        )
    assert body == "共同項目\n共同項目\n"


def test_shared_edit_applies_explicit_capacity_and_rejects_unstorable_text() -> None:
    from caliburn.shared.domain.text_editing.body_edits import (
        EditLimits,
        apply_body_diff,
    )
    from caliburn.shared.domain.text_editing.errors import (
        InvalidTextError,
        TextEditError,
    )

    with pytest.raises(TextEditError) as exceeded:
        apply_body_diff("abcd", "@@\n+z\n", limits=EditLimits(3, 100, 2, 10000))
    assert exceeded.value.code == "patch_limit_exceeded"
    with pytest.raises(InvalidTextError):
        apply_body_diff("a", "@@\n+\x00\n", limits=EditLimits(100, 100, 2, 10000))


def test_plan_retains_its_lower_capacity_after_shared_engine_extraction() -> None:
    from caliburn.modules.plan.domain.editing.body_edits import apply_body_diff
    from caliburn.modules.plan.domain.errors import BodyEditError

    with pytest.raises(BodyEditError) as exceeded:
        apply_body_diff("x" * 16001, "@@\n+y\n")
    assert exceeded.value.code == "patch_limit_exceeded"
