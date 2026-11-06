"""受訪者姓名的領域規則與值語意測試。"""

import pytest
from pydantic import ValidationError

from caliburn.modules.workspace.domain.interviewee_name import IntervieweeName


@pytest.mark.parametrize(
    "value",
    ["", " ", "\t", "\n", "\r\n", "\u3000", " \t\r\n\u3000"],
    ids=["empty", "space", "tab", "newline", "crlf", "fullwidth", "mixed"],
)
def test_rejects_blank_name(value: str) -> None:
    """拒絕空字串與各種全空白姓名。"""
    with pytest.raises(ValidationError) as error:
        IntervieweeName(value=value)

    detail = error.value.errors()[0]
    assert detail["loc"] == ("value",)
    assert detail["type"] == "value_error"
    assert "受訪者姓名不可為空字串或全空白" in detail["msg"]


@pytest.mark.parametrize("value", ["王小明", " 王 小明 ", "\t王小明\u3000", "王\n小明"])
def test_preserves_valid_name(value: str) -> None:
    """有效姓名原樣保留，不裁切空白或換行。"""
    assert IntervieweeName(value=value).value == value


@pytest.mark.parametrize("value", [None, 123, b"name"])
def test_rejects_non_string_name(value: object) -> None:
    """姓名 Primitive 僅接受字串，不自動轉型。"""
    with pytest.raises(ValidationError) as error:
        IntervieweeName.model_validate({"value": value})

    assert error.value.errors()[0]["type"] == "string_type"


def test_name_equality_uses_the_exact_value() -> None:
    """相同姓名值相等，原文中的空白仍參與比較。"""
    name = IntervieweeName(value="王小明")

    assert name == IntervieweeName(value="王小明")
    assert name != IntervieweeName(value=" 王小明 ")


def test_name_is_not_equal_to_a_raw_string() -> None:
    """姓名值物件與未建模的字串有不同語意。"""
    raw_value: object = "王小明"

    assert IntervieweeName(value="王小明") != raw_value


def test_name_cannot_be_changed_in_place() -> None:
    """姓名值不能原地修改，避免共享時改壞既有 Workspace。"""
    name = IntervieweeName(value="王小明")

    with pytest.raises(ValidationError) as error:
        name.__setattr__("value", "王大明")

    assert error.value.errors()[0]["type"] == "frozen_instance"
    assert name.value == "王小明"
