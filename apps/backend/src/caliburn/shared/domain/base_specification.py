"""可組合的領域條件。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class BaseSpecification[CandidateT](ABC):
    """具體條件負責判斷與純度；組合保留短路並原樣傳播例外。

    組合僅固定運算元引用，不會凍結具體條件的內部狀態。
    """

    @abstractmethod
    def is_satisfied_by(self, candidate: CandidateT) -> bool:
        """判斷候選是否符合領域條件。"""

    def __and__(
        self, other: BaseSpecification[CandidateT]
    ) -> BaseSpecification[CandidateT]:
        if not isinstance(other, BaseSpecification):
            return NotImplemented
        return _AndSpecification(self, other)

    def __or__(
        self, other: BaseSpecification[CandidateT]
    ) -> BaseSpecification[CandidateT]:
        if not isinstance(other, BaseSpecification):
            return NotImplemented
        return _OrSpecification(self, other)

    def __invert__(self) -> BaseSpecification[CandidateT]:
        return _NotSpecification(self)


@dataclass(frozen=True, eq=False)
class _AndSpecification[CandidateT](BaseSpecification[CandidateT]):
    _left: BaseSpecification[CandidateT]
    _right: BaseSpecification[CandidateT]

    def is_satisfied_by(self, candidate: CandidateT) -> bool:
        return self._left.is_satisfied_by(candidate) and self._right.is_satisfied_by(
            candidate
        )


@dataclass(frozen=True, eq=False)
class _OrSpecification[CandidateT](BaseSpecification[CandidateT]):
    _left: BaseSpecification[CandidateT]
    _right: BaseSpecification[CandidateT]

    def is_satisfied_by(self, candidate: CandidateT) -> bool:
        return self._left.is_satisfied_by(candidate) or self._right.is_satisfied_by(
            candidate
        )


@dataclass(frozen=True, eq=False)
class _NotSpecification[CandidateT](BaseSpecification[CandidateT]):
    _operand: BaseSpecification[CandidateT]

    def is_satisfied_by(self, candidate: CandidateT) -> bool:
        return not self._operand.is_satisfied_by(candidate)
