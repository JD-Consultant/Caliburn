"""從公開純編輯介面驗證原文保留與完整拒絕。"""

import pytest

from caliburn.modules.plan.domain.editing.body_edits import (
    apply_body_diff,
)
from caliburn.modules.plan.domain.errors import BodyEditError, InvalidPlanTextError
from caliburn.shared.domain.text_editing.body_edits import describe_body_change


def test_empty_body_can_receive_first_plan_at_explicit_eof() -> None:
    assert apply_body_diff("", "@@\n+## 未釐清\n+- 盤點範圍\n*** End of File") == (
        "## 未釐清\n- 盤點範圍"
    )


@pytest.mark.parametrize("invalid", ["\x00", "\ud800", "\udfff"])
def test_unsavable_source_text_is_rejected_before_patch(invalid: str) -> None:
    with pytest.raises(InvalidPlanTextError):
        apply_body_diff(invalid, "@@\n+新增\n*** End of File")


@pytest.mark.parametrize("invalid", ["\x00", "\ud800", "\udfff"])
def test_unsavable_patch_text_is_rejected_before_matching(invalid: str) -> None:
    with pytest.raises(InvalidPlanTextError):
        apply_body_diff("舊", "@@\n-舊\n+" + invalid)


def test_fuzzy_context_keeps_actual_chinese_text_and_mixed_line_endings() -> None:
    body = (
        "# 工作情境\r\n保留：🧾\n## 訂單異常處理\r\n"
        "本人每月核對訂單並交由後端同事處理。\r\n"
        "未確認：跨部門升級條件與責任分界。\r\n\n# 其他\n  原樣保留\t"
    )
    diff = (
        "@@\n ## 訂單異常處理\n"
        "-本人每月核對訂單並交由後端同事處理。\n"
        "+本人每週核對訂單並交由後端同事處理。\n"
        " 未確認：跨部門升級条件與責任分界。"
    )
    assert apply_body_diff(body, diff) == (
        "# 工作情境\r\n保留：🧾\n## 訂單異常處理\r\n"
        "本人每週核對訂單並交由後端同事處理。\r\n"
        "未確認：跨部門升級條件與責任分界。\r\n\n# 其他\n  原樣保留\t"
    )


@pytest.mark.parametrize(
    ("body", "context"),
    [
        ("重複\n重複\n", "重複"),
        ("重複\n重複\n重複\n", "重複\n重複"),
        (
            "本人每月核對訂單並追蹤付款紀錄。\n本人每月核對訂單並追蹤付款記錄。",
            "本人每月核對訂單並追蹤付款紀錄。",
        ),
        (
            "本人每月核對訂單並追蹤付款紀錄與異常處理結果。\n"
            "本人每月核對訂單並追蹤付款記錄與異常處理結果。",
            "本人每月核對訂單並追蹤付欵紀錄與異常處理結果。",
        ),
    ],
    ids=["duplicate", "overlap", "exact-and-fuzzy", "unequal-fuzzy-scores"],
)
def test_every_qualifying_location_counts_toward_ambiguity(
    body: str, context: str
) -> None:
    diff = "@@\n" + "\n".join("-" + line for line in context.split("\n")) + "\n+修正"
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff(body, diff)
    assert caught.value.code == "ambiguous_patch_context"
    assert caught.value.hunk_number == 1
    assert len(caught.value.candidates) == 2
    assert caught.value.candidates[0].start_line < caught.value.candidates[1].start_line
    assert context not in str(caught.value)


@pytest.mark.parametrize(
    "diff",
    [
        "@@\n-不存在\n+修正",
        "@@\n-付款\n+帳款",
        "@@\n-每週核對\n+每年核對",
        "@@ missing heading\n-每月核對\n+每年核對",
        "@@\n-每月核對\n+每年核對\n*** End of File",
    ],
)
def test_missing_context_is_distinct_from_ambiguity_or_capacity(diff: str) -> None:
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff("每月核對\n付款紀錄\n", diff)
    assert caught.value.code == "patch_context_not_found"


def test_wrong_short_fact_is_not_diluted_by_long_matching_context() -> None:
    fact = "本人處理訂單資料、交接付款異常並追蹤結果。" * 10
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff(f"## 銷售\n{fact}\n", f"@@\n ## 庫存\n-{fact}\n+修正")
    assert caught.value.code == "patch_context_not_found"


@pytest.mark.parametrize(
    ("body", "expected"), [("abcdefghiX", "abcdefghij"), ("abcdefghijX", "abcdefghij")]
)
def test_fuzzy_match_accepts_at_least_ten_characters_at_ninety_percent(
    body: str, expected: str
) -> None:
    assert apply_body_diff(body, "@@\n-" + expected + "\n+修正") == "修正"


@pytest.mark.parametrize(
    ("body", "expected"), [("abcdefghX", "abcdefghi"), ("abcdefghXX", "abcdefghij")]
)
def test_fuzzy_match_rejects_short_lines_or_similarity_below_threshold(
    body: str, expected: str
) -> None:
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff(body, "@@\n-" + expected + "\n+修正")
    assert caught.value.code == "patch_context_not_found"


def test_hunks_locate_original_positions_despite_earlier_line_count_changes() -> None:
    body = "# 頻率\n每月\n\n# 範圍\n本人處理\n同事處理\n\n# 未知\n待確認\n"
    diff = (
        "@@\n # 頻率\n-每月\n+每週\n+旺季例外\n"
        "@@\n # 範圍\n 本人處理\n-同事處理\n"
        "@@\n # 未知\n-待確認\n+已釐清\n*** End of File\n*** End Patch\n"
    )
    assert apply_body_diff(body, diff) == (
        "# 頻率\n每週\n旺季例外\n\n# 範圍\n本人處理\n\n# 未知\n已釐清\n"
    )


@pytest.mark.parametrize(
    "invalid",
    [
        "",
        "@@",
        "+無來源插入",
        "@@\n unchanged",
        "*** Begin Patch\n*** Update File: x.md\n@@\n-舊\n+新\n*** End Patch",
        "@@ -1,1 +1,1 @@\n-舊\n+新",
        "```diff\n@@\n-舊\n+新\n```",
        "@@\n-舊\n+新\n*** Add File: ../x\n+非法",
        "@@\n-舊\n+新\n*** Delete File: x",
        "@@\n-舊\n+新\n*** Move to: x",
        "@@\n-舊\n+新\n*** End Patch\n-其他\n+丟失",
        "@@\n-舊\n+新\n*** End of File\n@@\n-其他\n+丟失",
        "@@\n-舊\n+新\n*** End Patch trailing",
        "@@\n-舊\n+新\r多",
    ],
)
def test_invalid_syntax_and_file_operations_cannot_apply_valid_prefix(
    invalid: str,
) -> None:
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff("舊\n其他\n", invalid)
    assert caught.value.code == "invalid_patch"


@pytest.mark.parametrize("ending", ["", "\n", "\r\n"])
def test_replacement_preserves_existing_final_newline(ending: str) -> None:
    assert apply_body_diff("舊" + ending, "@@\n-舊\n+新") == "新" + ending


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("原文", "原文\n新增"),
        ("原文\n", "原文\n新增\n"),
        ("原文\r\n", "原文\r\n新增\r\n"),
        ("原文\n\n", "原文\n\n新增\n"),
    ],
)
def test_explicit_eof_uniquely_locates_insertion_and_preserves_line_endings(
    body: str, expected: str
) -> None:
    assert apply_body_diff(body, "@@\n+新增\n*** End of File") == expected


def test_multiple_edit_chunks_keep_original_context_and_local_newline() -> None:
    body = "# 工作\r\n每月\r\n  保留縮排\n主管\n"
    diff = "@@\n # 工作\n-每月\n+每週\n 保留縮排\n-主管\n+同事"
    assert apply_body_diff(body, diff) == "# 工作\r\n每週\r\n  保留縮排\n同事\n"


def test_repeated_parent_anchor_keeps_current_search_floor() -> None:
    body = "# 情境\n## 第一\n甲\n## 第二\n乙\n"
    diff = "@@ # 情境\n ## 第一\n-甲\n+新甲\n@@ # 情境\n ## 第二\n-乙\n+新乙"
    assert apply_body_diff(body, diff) == "# 情境\n## 第一\n新甲\n## 第二\n新乙\n"


def test_stacked_anchors_only_advance_search_without_rewriting_source() -> None:
    body = "# 總覽\n舊\n## 第一\n舊\n## 第二\n舊\n"
    assert apply_body_diff(body, "@@ # 總覽\n@@ ## 第二\n-舊\n+新") == (
        "# 總覽\n舊\n## 第一\n舊\n## 第二\n新\n"
    )


def test_unicode_separators_and_lone_cr_are_preserved_as_unedited_source_text() -> None:
    assert apply_body_diff("保留\u2028原文\r原文\n舊\n", "@@\n-舊\n+新") == (
        "保留\u2028原文\r原文\n新\n"
    )


@pytest.mark.parametrize("ending", ["", "\n", "\r\n"])
def test_multiline_noop_preserves_all_original_line_endings(ending: str) -> None:
    body = "first\r\nsecond\nlast" + ending
    assert (
        apply_body_diff(body, "@@\n-first\n-second\n-last\n+first\n+second\n+last")
        == body
    )


def test_body_at_sixteen_thousand_character_limit_can_be_edited() -> None:
    body = "x" * 15_996 + "\nold"
    assert apply_body_diff(body, "@@\n-old\n+new") == "x" * 15_996 + "\nnew"


def test_source_over_limit_is_rejected_before_partial_scan() -> None:
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff("x" * 16_001, "@@\n-absent\n+new")
    assert caught.value.code == "patch_limit_exceeded"


def test_patch_at_sixteen_thousand_character_limit_is_accepted() -> None:
    diff = "@@\n+" + "x" * 15_980 + "\n*** End of File"
    assert len(diff) == 16_000
    assert apply_body_diff("", diff) == "x" * 15_980


def test_patch_over_limit_is_rejected() -> None:
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff("", "@@\n+" + "x" * 15_981 + "\n*** End of File")
    assert caught.value.code == "patch_limit_exceeded"


def test_result_at_sixteen_thousand_character_limit_is_accepted() -> None:
    assert apply_body_diff("x" * 15_997 + "\n", "@@\n+y\n*** End of File") == (
        "x" * 15_997 + "\ny\n"
    )


def test_result_over_limit_is_rejected() -> None:
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff("x" * 15_998 + "\n", "@@\n+y\n*** End of File")
    assert caught.value.code == "patch_limit_exceeded"


def test_thirty_two_hunks_are_accepted() -> None:
    body = "\n".join(f"old{index:02}" for index in range(32))
    diff = "\n".join(f"@@\n-old{index:02}\n+new{index:02}" for index in range(32))
    assert apply_body_diff(body, diff) == "\n".join(
        f"new{index:02}" for index in range(32)
    )


def test_thirty_three_hunks_are_rejected() -> None:
    body = "\n".join(f"old{index:02}" for index in range(33))
    diff = "\n".join(f"@@\n-old{index:02}\n+new{index:02}" for index in range(33))
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff(body, diff)
    assert caught.value.code == "patch_limit_exceeded"


@pytest.mark.parametrize(
    "diff",
    ["@@\n-" + "x" * 3_000 + "\n+y", "@@ " + "x" * 3_000 + "\n-z\n+y"],
    ids=["context", "anchor"],
)
def test_complete_scan_over_limit_is_capacity_rejection_not_missing_context(
    diff: str,
) -> None:
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff("z\n" * 7_500, diff)
    assert caught.value.code == "patch_limit_exceeded"


def test_actual_change_description_uses_real_source_and_marks_missing_newline() -> None:
    assert describe_body_change("old", "new") == (
        "--- body_before\n+++ body_after\n@@ -1 +1 @@\n"
        "-old\n\\ No newline at end of file\n"
        "+new\n\\ No newline at end of file\n"
    )
    assert describe_body_change("原文\r\n", "原文\r\n") == ""
