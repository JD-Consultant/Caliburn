"""Value Object 的值比較、驗證與不可變契約測試。"""

import pytest
from pydantic import Field, ValidationError

from caliburn.shared.domain.base_value_object import BaseValueObject


class Coordinate(BaseValueObject):
    x: int
    y: int


class OtherCoordinate(BaseValueObject):
    x: int
    y: int


def test_default_values_must_satisfy_the_declared_constraints() -> None:
    """省略輸入時，預設值仍須通過值物件的有效值規則。"""

    class PositiveQuantity(BaseValueObject):
        value: int = Field(default=0, gt=0)

    with pytest.raises(ValidationError) as error:
        PositiveQuantity()

    assert error.value.errors()[0]["type"] == "greater_than"


def test_equality_uses_all_values() -> None:
    """同型別同值相等，任一欄位不同就不相等。"""
    coordinate = Coordinate(x=1, y=2)

    assert coordinate == Coordinate(x=1, y=2)
    assert coordinate != Coordinate(x=2, y=2)
    assert coordinate != Coordinate(x=1, y=3)


@pytest.mark.parametrize("other", [OtherCoordinate(x=1, y=2), {"x": 1, "y": 2}])
def test_different_types_are_not_equal(other: object) -> None:
    """相同欄位值的其他領域型別或字典，不等於此值物件。"""
    assert Coordinate(x=1, y=2) != other


def test_equal_immutable_values_are_deduplicated_in_a_set() -> None:
    """相等且欄位可 hash 的值物件，在 set 中視為同一個值。"""
    assert len({Coordinate(x=1, y=2), Coordinate(x=1, y=2)}) == 1


def test_rejects_implicit_type_conversion() -> None:
    """拒絕將字串自動轉成整數欄位。"""
    with pytest.raises(ValidationError) as error:
        Coordinate.model_validate({"x": "1", "y": 2})

    assert error.value.errors()[0]["type"] == "int_type"


def test_rejects_unknown_fields() -> None:
    """拒絕領域值未定義的額外欄位。"""
    with pytest.raises(ValidationError) as error:
        Coordinate.model_validate({"x": 1, "y": 2, "z": 3})

    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_fields_cannot_be_reassigned() -> None:
    """值物件不能原地修改，失敗後原值保持完整。"""
    coordinate = Coordinate(x=1, y=2)

    with pytest.raises(ValidationError) as error:
        coordinate.__setattr__("x", 3)

    assert error.value.errors()[0]["type"] == "frozen_instance"
    assert coordinate.x == 1


def test_fields_cannot_be_deleted() -> None:
    """值物件不能刪除必要欄位。"""
    coordinate = Coordinate(x=1, y=2)

    with pytest.raises(ValidationError) as error:
        del coordinate.x

    assert error.value.errors()[0]["type"] == "frozen_instance"
    assert coordinate.x == 1
