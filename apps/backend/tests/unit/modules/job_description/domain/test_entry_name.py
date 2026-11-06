"""名稱值自行清洗、判定相等，且不能任意修改。"""

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.domain.errors import InvalidNameError
from caliburn.modules.job_description.domain.models.entry_name import EntryName


def test_name_trims_outer_whitespace_and_preserves_display_case() -> None:
    """只清洗條目名稱的前後空白，不改寫名稱內部內容。"""
    assert EntryName(value=" \tSQL 查詢\n ").value == "SQL 查詢"


def test_existing_immutable_name_can_be_reused() -> None:
    """原始文字仍須驗證；已驗證的不可變名稱可直接共用。"""
    name = EntryName(value=" SQL ")

    assert name.value == "SQL"
    assert EntryName.model_validate(name) is name


def test_name_validation_does_not_convert_bare_strings_to_field_data() -> None:
    """建立名稱須明示 value，不替裸字串推斷欄位。"""
    with pytest.raises(ValidationError):
        EntryName.model_validate("SQL")


def test_equal_names_have_the_same_hash_without_external_comparison_keys() -> None:
    """清洗後完全相同的名稱在集合中只保留一份。"""
    first = EntryName(value=" SQL ")
    second = EntryName(value="SQL")
    assert first == second
    assert hash(first) == hash(second)
    assert len({first, second}) == 1


def test_names_with_different_case_are_distinct() -> None:
    """名稱不合併大小寫，判重集合保留兩個值。"""
    uppercase = EntryName(value="SQL")
    lowercase = EntryName(value="sql")

    assert uppercase != lowercase
    assert len({uppercase, lowercase}) == 2


@pytest.mark.parametrize("value", ["", " \t\n", "\u001c", "界" * 256, " " + "界" * 256])
def test_invalid_names_are_rejected(value: str) -> None:
    """拒絕空白名稱及清洗後超過255字元的名稱。"""
    with pytest.raises(InvalidNameError):
        EntryName(value=value)


def test_name_limit_counts_codepoints_after_trimming() -> None:
    """外圍空白不占名稱長度，內部空白與emoji各算一字元。"""
    name = "😀" + " " * 253 + "界"
    assert EntryName(value="\u001c " + name + "\u3000\n").value == name


def test_name_is_immutable() -> None:
    """建立後不能透過公開屬性改寫值。"""
    name = EntryName(value="原名稱")
    with pytest.raises(ValidationError):
        name.__setattr__("value", "其他名稱")
    assert name.value == "原名稱"
