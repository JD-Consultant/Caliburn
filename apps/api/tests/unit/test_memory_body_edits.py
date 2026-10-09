"""Memory body edits preserve real context instead of copying approximate context."""

import pytest

from caliburn.adapters.body_matching import BodyEditError, BodyMatchPolicy
from caliburn.features.work_memory.body_edits import apply_body_diff


def test_fuzzy_context_preserves_actual_chinese_text_and_mixed_line_endings() -> None:
    body = (
        "# 工作情境\r\n保留：🧾\n"
        "## 訂單異常處理\r\n"
        "本人每月核對訂單並交由後端同事處理。\r\n"
        "未確認：跨部門升級條件與責任分界。\r\n"
        "\n# 其他\n  原樣保留\t"
    )
    diff = (
        "@@\n ## 訂單異常處理\n"
        "-本人每月核對訂單並交由後端同事處理。\n"
        "+本人每週核對訂單並交由後端同事處理。\n"
        " 未確認：跨部門升級条件與責任分界。"
    )
    assert apply_body_diff(body, diff) == body.replace("每月", "每週")


def test_context_selects_the_intended_section_not_the_first_repeated_edit_line() -> None:
    body = "## 庫存\n每月檢查。\n交主管。\n## 網站\n每月檢查。\n交同事。\n"
    diff = "@@\n ## 網站\n-每月檢查。\n+每週檢查。\n 交同事。"
    assert apply_body_diff(body, diff) == body.replace("## 網站\n每月", "## 網站\n每週")


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
        (
            "\n".join(["本人每月核對訂單並追蹤付款紀錄。"] * 3),
            "本人每月核對訂單並追蹤付欵紀錄。\n本人每月核對訂單並追蹤付款紀錄。",
        ),
    ],
)
def test_all_qualifying_locations_including_overlaps_and_exact_plus_fuzzy_are_rejected(
    body: str, context: str
) -> None:
    diff = "@@\n" + "\n".join("-" + line for line in context.split("\n")) + "\n+修正"
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff(body, diff)
    assert caught.value.code == "ambiguous_patch_context"
    assert caught.value.hunk_number == 1
    assert len(caught.value.candidates) == 2
    assert caught.value.candidates[0].start_line < caught.value.candidates[1].start_line
    assert all(candidate.excerpt in body for candidate in caught.value.candidates)


@pytest.mark.parametrize(
    "diff",
    [
        "@@\n-不存在\n+修正",
        "@@\n-付款\n+帳款",  # A fragment is not a whole source line.
        "@@\n-每週核對\n+每年核對",  # No textual fuzz for short facts.
        "@@ missing heading\n-每月核對\n+每年核對",
        "@@\n-每月核對\n+每年核對\n*** End of File",  # Not at EOF.
    ],
)
def test_no_match_is_distinct_from_ambiguity_and_capacity(diff: str) -> None:
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff("每月核對\n付款紀錄\n", diff)
    assert caught.value.code == "patch_context_not_found"


def test_wrong_short_context_is_not_diluted_by_long_matching_lines() -> None:
    long_fact = "本人處理訂單資料、交接付款異常並追蹤結果。" * 10
    body = f"## 銷售\n{long_fact}\n"
    with pytest.raises(BodyEditError, match="No qualifying"):
        apply_body_diff(body, f"@@\n ## 庫存\n-{long_fact}\n+修正")


def test_many_hunks_use_original_positions_despite_earlier_insertions_and_deletions() -> None:
    body = "# 頻率\n每月\n\n# 範圍\n本人處理\n同事處理\n\n# 未知\n待確認\n"
    diff = (
        "@@\n # 頻率\n-每月\n+每週\n+旺季例外\n"
        "@@\n # 範圍\n 本人處理\n-同事處理\n"
        "@@\n # 未知\n-待確認\n+已釐清\n*** End of File\n*** End Patch\n"
    )
    assert apply_body_diff(body, diff) == (
        "# 頻率\n每週\n旺季例外\n\n# 範圍\n本人處理\n\n# 未知\n已釐清\n"
    )


def test_later_hunk_failure_returns_no_partial_body() -> None:
    original = "# 頻率\n每月\n# 其他\n保留\n"
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff(original, "@@\n # 頻率\n-每月\n+每週\n@@\n-不存在\n+增加")
    assert caught.value.hunk_number == 2
    assert caught.value.code == "patch_context_not_found"
    assert original == "# 頻率\n每月\n# 其他\n保留\n"


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
        "@@\n-舊\n+新\n***",
        "@@\n-舊\n+新\n*** End Patch trailing",
        "@@\n-舊\n+\x00",
        "@@\n-舊\n+新\r多",
    ],
)
def test_invalid_syntax_and_non_body_operations_never_apply_a_valid_prefix(invalid: str) -> None:
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff("舊\n其他\n", invalid)
    assert caught.value.code == "invalid_patch"


@pytest.mark.parametrize("ending", ["", "\n", "\r\n"])
def test_replacement_preserves_existing_final_newline(ending: str) -> None:
    assert apply_body_diff("舊" + ending, "@@\n-舊\n+新") == "新" + ending


@pytest.mark.parametrize("ending", ["", "\n", "\r\n"])
def test_append_at_eof_preserves_final_newline_policy(ending: str) -> None:
    body = "原文" + ending
    expected = "原文" + (ending or "\n") + "新增" + ending
    assert apply_body_diff(body, "@@\n 原文\n+新增\n*** End of File") == expected


def test_multiple_edit_chunks_in_one_hunk_keep_real_context() -> None:
    body = "# 工作\r\n每月\r\n  保留縮排\n主管\n"
    diff = "@@\n # 工作\n-每月\n+每週\n 保留縮排\n-主管\n+同事"
    assert apply_body_diff(body, diff) == "# 工作\r\n每週\r\n  保留縮排\n同事\n"


def test_stacked_anchors_only_skip_source_and_do_not_rewrite_it() -> None:
    body = "# 總覽\n舊\n## 第一\n舊\n## 第二\n舊\n"
    diff = "@@ # 總覽\n@@ ## 第二\n-舊\n+新"
    assert apply_body_diff(body, diff) == body.removesuffix("舊\n") + "新\n"


def test_source_text_that_looks_like_a_patch_command_is_ordinary_prefixed_text() -> None:
    body = "舊\n*** End Patch\n"
    assert apply_body_diff(body, "@@\n-舊\n+新\n *** End Patch") == "新\n*** End Patch\n"


def test_long_markdown_with_unique_typo_changes_only_requested_lines() -> None:
    filler = "".join(f"- 保留 {index:04d}：辦公室設備與庶務資料。\n" for index in range(6000))
    body = filler + "## 訂單\n本人每月核對訂單與付款紀錄。\n交由後端同事完成後續處理。\n"
    diff = "@@\n ## 訂單\n-本人每月核對訂單與付欵紀錄。\n+本人每週核對訂單與付款紀錄。"
    assert len(body) > 100_000
    assert apply_body_diff(body, diff) == body.replace("每月", "每週")


@pytest.mark.parametrize(
    "policy",
    [
        BodyMatchPolicy(max_scan_characters=1),
        BodyMatchPolicy(max_body_characters=1),
        BodyMatchPolicy(max_diff_characters=1),
        BodyMatchPolicy(max_hunks=1),
    ],
)
def test_resource_limit_never_masquerades_as_unique_or_no_match(policy: BodyMatchPolicy) -> None:
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff("舊\n另一段\n", "@@\n-舊\n+新\n@@\n-另一段\n+另一新段", policy=policy)
    assert caught.value.code == "patch_limit_exceeded"


def test_body_cannot_be_removed_using_update() -> None:
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff("原文\n", "@@\n-原文")
    assert caught.value.code == "invalid_patch"


def test_same_old_and_new_text_is_unchanged() -> None:
    assert apply_body_diff("# 工作\n原文\n", "@@\n # 工作\n-原文\n+原文") == "# 工作\n原文\n"


@pytest.mark.parametrize("body", ["原文", "原文\n", "原文\r\n", "原文\n\n"])
def test_eof_itself_uniquely_locates_a_pure_insertion(body: str) -> None:
    newline = "\r\n" if "\r\n" in body else "\n"
    expected = body + ("" if body.endswith("\n") else newline) + "新增"
    if body.endswith("\n"):
        expected += newline
    assert apply_body_diff(body, "@@\n+新增\n*** End of File") == expected


def test_repeated_parent_anchor_does_not_rewind_or_skip_current_search_floor() -> None:
    body = "# 情境\n## 第一\n甲\n## 第二\n乙\n"
    diff = "@@ # 情境\n ## 第一\n-甲\n+新甲\n@@ # 情境\n ## 第二\n-乙\n+新乙"
    assert apply_body_diff(body, diff) == "# 情境\n## 第一\n新甲\n## 第二\n新乙\n"


def test_anchor_scanning_is_also_charged_to_the_work_limit() -> None:
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff(
            "# 情境\n舊\n",
            "@@ # 情境\n-舊\n+新",
            policy=BodyMatchPolicy(max_scan_characters=10),
        )
    assert caught.value.code == "patch_limit_exceeded"


def test_revised_body_cannot_exceed_the_limit_for_future_edits() -> None:
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff(
            "原文\n", "@@\n+新增\n*** End of File", policy=BodyMatchPolicy(max_body_characters=5)
        )
    assert caught.value.code == "patch_limit_exceeded"


@pytest.mark.parametrize("ending", ["", "\n", "\r\n"])
def test_multiline_noop_preserves_each_original_line_ending(ending: str) -> None:
    body = "first\r\nsecond\nlast" + ending
    diff = "@@\n-first\n-second\n-last\n+first\n+second\n+last"
    assert apply_body_diff(body, diff) == body


@pytest.mark.parametrize("body", ["", " \n\t\n"])
def test_update_requires_a_nonblank_source_body(body: str) -> None:
    with pytest.raises(BodyEditError) as caught:
        apply_body_diff(body, "@@\n+新增\n*** End of File")
    assert caught.value.code == "invalid_patch"
