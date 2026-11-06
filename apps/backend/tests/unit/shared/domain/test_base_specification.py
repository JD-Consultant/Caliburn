"""Specification 的抽象契約、布林組合與求值邊界測試。"""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass
from operator import and_, or_
from typing import Literal

import pytest

from caliburn.shared.domain.base_specification import BaseSpecification

type BinaryComposition = Callable[
    [BaseSpecification[object], BaseSpecification[object]], BaseSpecification[object]
]


@dataclass
class ObservedSpecification(BaseSpecification[object]):
    name: str
    result: bool
    calls: list[tuple[str, object]]
    error: Exception | None = None

    def is_satisfied_by(self, candidate: object) -> bool:
        self.calls.append((self.name, candidate))
        if self.error is not None:
            raise self.error
        return self.result


class IsPositive(BaseSpecification[int]):
    def is_satisfied_by(self, candidate: int) -> bool:
        return candidate > 0


class IsEven(BaseSpecification[int]):
    def is_satisfied_by(self, candidate: int) -> bool:
        return candidate % 2 == 0


def test_base_requires_a_concrete_predicate() -> None:
    """抽象基底與未實作條件的子類均不能建構。"""

    class MissingPredicate(BaseSpecification[int]):
        pass

    with pytest.raises(TypeError, match="abstract"):
        BaseSpecification[int]()  # type: ignore[abstract]
    with pytest.raises(TypeError, match="abstract"):
        MissingPredicate()  # type: ignore[abstract]


@pytest.mark.parametrize(
    ("left_result", "right_result", "expected"),
    [
        (False, False, False),
        (False, True, False),
        (True, False, False),
        (True, True, True),
    ],
)
def test_and_evaluates_left_to_right_with_short_circuit(
    left_result: bool, right_result: bool, expected: bool
) -> None:
    """AND 符合真值表，左側不符合時跳過右側，兩側接收同一候選。"""
    candidate = object()
    calls: list[tuple[str, object]] = []
    left = ObservedSpecification("left", left_result, calls)
    right = ObservedSpecification("right", right_result, calls)

    combined = left & right

    assert isinstance(combined, BaseSpecification)
    assert calls == []
    assert combined.is_satisfied_by(candidate) is expected
    expected_calls = [("left", candidate)]
    if left_result:
        expected_calls.append(("right", candidate))
    assert calls == expected_calls


@pytest.mark.parametrize(
    ("left_result", "right_result", "expected"),
    [
        (False, False, False),
        (False, True, True),
        (True, False, True),
        (True, True, True),
    ],
)
def test_or_evaluates_left_to_right_with_short_circuit(
    left_result: bool, right_result: bool, expected: bool
) -> None:
    """OR 符合真值表，左側符合時跳過右側，兩側接收同一候選。"""
    candidate = object()
    calls: list[tuple[str, object]] = []
    left = ObservedSpecification("left", left_result, calls)
    right = ObservedSpecification("right", right_result, calls)

    combined = left | right

    assert isinstance(combined, BaseSpecification)
    assert calls == []
    assert combined.is_satisfied_by(candidate) is expected
    expected_calls = [("left", candidate)]
    if not left_result:
        expected_calls.append(("right", candidate))
    assert calls == expected_calls


@pytest.mark.parametrize(("result", "expected"), [(False, True), (True, False)])
def test_not_evaluates_its_operand_once(result: bool, expected: bool) -> None:
    """NOT 延後求值，只評估原候選一次並反轉布林結果。"""
    candidate = object()
    calls: list[tuple[str, object]] = []
    operand = ObservedSpecification("operand", result, calls)

    combined = ~operand

    assert isinstance(combined, BaseSpecification)
    assert calls == []
    assert combined.is_satisfied_by(candidate) is expected
    assert calls == [("operand", candidate)]


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [(2, True), (1, False), (-1, True), (-2, False), (0, False)],
)
def test_combinations_can_be_composed_again(candidate: int, expected: bool) -> None:
    """組合結果仍是同候選型別的條件，支援 AND、OR 與 NOT 巢狀組合。"""
    positive = IsPositive()
    even = IsEven()
    positive_even_or_nonpositive_odd = (positive & even) | (~positive & ~even)

    assert positive_even_or_nonpositive_odd.is_satisfied_by(candidate) is expected


@pytest.mark.parametrize("combine", [and_, or_])
def test_left_predicate_error_propagates_without_evaluating_right(
    combine: BinaryComposition,
) -> None:
    """左側例外原樣傳出，不當成不符合，也不繼續評估右側。"""
    candidate = object()
    calls: list[tuple[str, object]] = []
    error = ValueError("predicate failed")
    left = ObservedSpecification("left", False, calls, error)
    right = ObservedSpecification("right", True, calls)

    with pytest.raises(ValueError) as caught:
        combine(left, right).is_satisfied_by(candidate)

    assert caught.value is error
    assert calls == [("left", candidate)]


@pytest.mark.parametrize(("combine", "left_result"), [(and_, True), (or_, False)])
def test_right_predicate_error_propagates_when_evaluation_is_required(
    combine: BinaryComposition, left_result: bool
) -> None:
    """需要評估右側時，其原例外不被轉換或吞成布林結果。"""
    candidate = object()
    calls: list[tuple[str, object]] = []
    error = ValueError("predicate failed")
    left = ObservedSpecification("left", left_result, calls)
    right = ObservedSpecification("right", False, calls, error)

    with pytest.raises(ValueError) as caught:
        combine(left, right).is_satisfied_by(candidate)

    assert caught.value is error
    assert calls == [("left", candidate), ("right", candidate)]


@pytest.mark.parametrize(("combine", "left_result"), [(and_, False), (or_, True)])
def test_short_circuit_does_not_raise_an_unneeded_predicate_error(
    combine: BinaryComposition, left_result: bool
) -> None:
    """短路時不呼叫會失敗的右側條件。"""
    calls: list[tuple[str, object]] = []
    left = ObservedSpecification("left", left_result, calls)
    right = ObservedSpecification("right", False, calls, ValueError("must not run"))

    assert combine(left, right).is_satisfied_by(object()) is left_result


def test_not_propagates_the_original_predicate_error() -> None:
    """NOT 保留原例外，不把失敗當成不符合後再反轉為符合。"""
    candidate = object()
    calls: list[tuple[str, object]] = []
    error = ValueError("predicate failed")
    operand = ObservedSpecification("operand", False, calls, error)

    with pytest.raises(ValueError) as caught:
        (~operand).is_satisfied_by(candidate)

    assert caught.value is error
    assert calls == [("operand", candidate)]


@pytest.mark.parametrize(
    ("kind", "operand_name", "expected"),
    [
        ("and", "_left", False),
        ("and", "_right", False),
        ("or", "_left", True),
        ("or", "_right", True),
        ("not", "_operand", True),
    ],
)
@pytest.mark.parametrize("mutation", ["replace", "delete"])
def test_composed_operands_cannot_be_replaced_or_deleted(
    kind: str,
    operand_name: str,
    expected: bool,
    mutation: Literal["replace", "delete"],
) -> None:
    """組合建立後禁止替換或刪除運算元，失敗後仍能評估原條件。"""
    left = IsPositive()
    right = IsEven()
    combined = {"and": left & right, "or": left | right, "not": ~left}[kind]

    with pytest.raises(FrozenInstanceError):
        if mutation == "replace":
            setattr(combined, operand_name, ~right)
        else:
            delattr(combined, operand_name)

    assert combined.is_satisfied_by(-2) is expected


@pytest.mark.parametrize("combine", [and_, or_])
def test_binary_operators_reject_non_specifications(
    combine: Callable[[object, object], object],
) -> None:
    """不合法運算元在組合當下失敗，不延後到候選評估時才出錯。"""
    with pytest.raises(TypeError):
        combine(IsPositive(), object())
