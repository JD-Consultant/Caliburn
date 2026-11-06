"""Application DTO 共用設定的行為測試。"""

import pytest
from pydantic import ValidationError

from caliburn.shared.application.base_dto import BaseDTO


class SampleDTO(BaseDTO):
    name: str
    count: int


def test_preserves_declared_values_without_requiring_identity() -> None:
    """DTO 原樣保留宣告值，不要求或附加 Entity 身分。"""
    dto = SampleDTO(name=" 範例 ", count=2)

    assert dto.model_dump() == {"name": " 範例 ", "count": 2}


@pytest.mark.parametrize(
    ("field", "value", "error_type"),
    [("name", b"sample", "string_type"), ("count", "2", "int_type")],
)
def test_rejects_implicit_type_conversion(
    field: str, value: object, error_type: str
) -> None:
    """子類繼承嚴格驗證，不把 bytes 轉字串或字串轉整數。"""
    payload: dict[str, object] = {"name": "範例", "count": 2}
    payload[field] = value

    with pytest.raises(ValidationError) as error:
        SampleDTO.model_validate(payload)

    detail = error.value.errors()[0]
    assert detail["loc"] == (field,)
    assert detail["type"] == error_type


def test_rejects_undeclared_fields() -> None:
    """子類拒絕額外欄位，不默默捨棄未知輸入。"""
    with pytest.raises(ValidationError) as error:
        SampleDTO.model_validate({"name": "範例", "count": 2, "unexpected": True})

    detail = error.value.errors()[0]
    assert detail["loc"] == ("unexpected",)
    assert detail["type"] == "extra_forbidden"


def test_fields_cannot_be_reassigned() -> None:
    """建立後禁止一般欄位重新賦值，原值保持不變。"""
    dto = SampleDTO(name="範例", count=2)

    with pytest.raises(ValidationError) as error:
        dto.__setattr__("name", "修改")

    assert error.value.errors()[0]["type"] == "frozen_instance"
    assert dto.name == "範例"


def test_fields_cannot_be_deleted() -> None:
    """建立後禁止刪除欄位，原資料仍可讀取。"""
    dto = SampleDTO(name="範例", count=2)

    with pytest.raises(ValidationError) as error:
        del dto.name

    assert error.value.errors()[0]["type"] == "frozen_instance"
    assert dto.name == "範例"
