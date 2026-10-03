"""The same prepared command combines real body edits and short-field changes."""

import pytest

from caliburn.features.work_memory.body_matching import BodyEditError
from caliburn.features.work_memory.edit_intents import (
    InterviewReferenceChange,
    MemoryBodyChange,
    MemoryFieldChange,
    MemoryTextChange,
)
from caliburn.features.work_memory.edit_preparation import (
    describe_body_change,
    prepare_content_changes,
)
from caliburn.features.work_memory.models import InvalidMemoryChangeError, MemoryContent


def test_prepare_combines_title_with_actual_v4a_body_change() -> None:
    content = MemoryContent("盤點", "每月核對", "# 庫存\n每月核對。\n回報主管。")
    changes = prepare_content_changes(
        content,
        (
            MemoryTextChange("title", "月末盤點"),
            MemoryBodyChange("@@\n # 庫存\n-每月核對。\n+每週核對。\n 回報主管。"),
        ),
    )
    assert changes is not None
    assert changes.title == "月末盤點"
    assert changes.description is None
    assert changes.body == "# 庫存\n每週核對。\n回報主管。"


@pytest.mark.parametrize(
    "changes",
    [
        (),
        (MemoryTextChange("title", "一"), MemoryTextChange("title", "二")),
        (MemoryBodyChange("@@\n-a\n+b"), MemoryBodyChange("@@\n-a\n+c")),
        (InterviewReferenceChange(),),
    ],
)
def test_invalid_change_sets_are_rejected(changes: tuple[MemoryFieldChange, ...]) -> None:
    with pytest.raises(InvalidMemoryChangeError):
        prepare_content_changes(MemoryContent("標題", "導覽", "正文"), changes)


def test_later_ambiguous_hunk_does_not_return_partial_preparation() -> None:
    before = MemoryContent("舊名", "導覽", "# 頻率\n每月\n# 重複\n相同\n# 重複\n相同")
    with pytest.raises(BodyEditError) as rejected:
        prepare_content_changes(
            before,
            (
                MemoryTextChange("title", "新名"),
                MemoryBodyChange("@@\n # 頻率\n-每月\n+每週\n@@\n # 重複\n-相同\n+不同"),
            ),
        )
    assert rejected.value.code == "ambiguous_patch_context"
    assert before.title == "舊名"
    assert "每月" in before.body


def test_observation_diff_uses_actual_before_text_and_marks_missing_final_newline() -> None:
    before = "#  工作\r\n原來的正式內容。"
    after = "#  工作\r\n修改後的正式內容。"
    observation = describe_body_change(before, after)
    assert " #  工作\r\n" in observation
    assert "-原來的正式內容。\n" in observation
    assert "+修改後的正式內容。\n" in observation
    assert observation.count("\\ No newline at end of file") == 2
    assert describe_body_change(before, before) == ""


@pytest.mark.parametrize("separator", ["\u2028", "\v", "\r"])
def test_observation_keeps_non_lf_separators_inside_one_source_line(separator: str) -> None:
    before = f"Inventory{separator}Monthly.\n"
    after = f"Inventory{separator}Weekly.\n"
    observation = describe_body_change(before, after)
    assert "@@ -1 +1 @@\n" in observation
    assert "-" + before in observation
    assert "+" + after in observation
    assert "No newline" not in observation
