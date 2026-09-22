"""App-captured textarea offsets, without a browser or a model invocation."""

import pytest

from jd_relational.selection import SelectionError, replace_utf16


@pytest.mark.parametrize("text,start,end,selected,replacement,expected", [
    ("甲😀按月檢查\n按月回報", 3, 5, "按月", "每季", "甲😀每季檢查\n按月回報"),
    ("𠮷按月", 2, 4, "按月", "  ", "𠮷  "),
    ("👩‍💻診斷", 2, 3, "‍", "", "👩💻診斷"),
    ("é工時", 1, 2, "́", "", "e工時"),
    ("甲乙丙", 1, 2, "乙", "\r\n", "甲\n丙"),
    ("甲乙", 0, 2, "甲乙", "", ""),
])
def test_exact_utf16_replacement_preserves_everything_outside_range(text, start, end, selected, replacement, expected):
    assert replace_utf16(text, start, end, selected, replacement) == expected


@pytest.mark.parametrize("text,start,end,selected,replacement", [
    ("😀甲", 1, 2, "", "乙"),
    ("甲😀", 0, 2, "甲", "乙"),
    ("甲", -1, 1, "甲", "乙"),
    ("甲", 1, 0, "", "乙"),
    ("甲", 0, 0, "", "乙"),
    ("甲", 0, 2, "甲", "乙"),
    ("甲", False, 1, "甲", "乙"),
    ("甲", 0, 1, "別段", "乙"),
    ("甲\r\n乙", 0, 1, "甲", "乙"),
    ("甲", 0, 1, "甲", "\ud800"),
    ("\ud800", 0, 1, "\ud800", "乙"),
])
def test_invalid_capture_is_rejected_without_fuzzy_search(text, start, end, selected, replacement):
    with pytest.raises(SelectionError):
        replace_utf16(text, start, end, selected, replacement)
