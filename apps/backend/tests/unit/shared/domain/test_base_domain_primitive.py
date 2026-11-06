"""Domain Primitive 泛型值與繼承契約測試。"""

import pytest
from pydantic import ValidationError

from caliburn.shared.domain.base_domain_primitive import BaseDomainPrimitive


class IntegerValue(BaseDomainPrimitive[int]):
    pass


class TextValue(BaseDomainPrimitive[str]):
    pass


def test_concrete_types_preserve_their_typed_value() -> None:
    """具體 Primitive 可使用整數或字串，並保留原值。"""
    assert IntegerValue(value=42).value == 42
    assert TextValue(value=" 代碼 ").value == " 代碼 "


@pytest.mark.parametrize("value", ["42", 42.0, True, None])
def test_rejects_values_outside_the_declared_type(value: object) -> None:
    """整數 Primitive 拒絕隱式轉型與空值。"""
    with pytest.raises(ValidationError) as error:
        IntegerValue.model_validate({"value": value})

    assert error.value.errors()[0]["type"] == "int_type"


def test_value_is_required() -> None:
    """Primitive 必須提供 value。"""
    with pytest.raises(ValidationError) as error:
        IntegerValue.model_validate({})

    assert error.value.errors()[0]["type"] == "missing"


def test_value_cannot_be_reassigned() -> None:
    """Primitive 繼承不可變契約，不能替換既有值。"""
    primitive = IntegerValue(value=42)

    with pytest.raises(ValidationError) as error:
        primitive.__setattr__("value", 43)

    assert error.value.errors()[0]["type"] == "frozen_instance"
    assert primitive.value == 42
