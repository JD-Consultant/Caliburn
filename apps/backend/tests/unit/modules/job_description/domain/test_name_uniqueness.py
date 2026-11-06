"""同範圍名稱判重與占用裁決，保留名稱驗證的錯誤語意。"""

import pytest

from caliburn.modules.job_description.domain.errors import (
    DuplicateNameError,
    InvalidNameError,
)
from caliburn.modules.job_description.domain.models.entry_name import (
    EntryName,
    require_distinct_names,
)


@pytest.mark.parametrize(
    "names",
    [("分析", "分析"), ("分析", " 分析 ")],
)
def test_equivalent_names_are_rejected(names: tuple[str, ...]) -> None:
    """清洗前後空白後相同，視為同範圍重名。"""
    with pytest.raises(DuplicateNameError):
        require_distinct_names(tuple(EntryName(value=name) for name in names))


def test_distinct_names_preserve_case_and_fullwidth_characters() -> None:
    """清洗前後空白，不合併大小寫、Unicode 大小寫等價或全半形。"""
    names = tuple(
        EntryName(value=name)
        for name in (" SQL ", "sql", "Straße", "STRASSE", "Ａ", "A")
    )

    require_distinct_names(iter(names))
    assert tuple(name.value for name in names) == (
        "SQL",
        "sql",
        "Straße",
        "STRASSE",
        "Ａ",
        "A",
    )


def test_no_new_names_is_valid() -> None:
    """沒有新定義時，無須提供名稱或產生比較鍵。"""
    require_distinct_names(())


def test_invalid_name_is_reported_before_batch_duplicates() -> None:
    """先驗證同組全部名稱，不把後續空白名稱誤報為前面的重名。"""
    with pytest.raises(InvalidNameError):
        require_distinct_names(
            tuple(EntryName(value=name) for name in ("分析", "分析", " "))
        )
