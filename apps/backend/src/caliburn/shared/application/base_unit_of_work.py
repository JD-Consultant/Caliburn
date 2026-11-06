"""用例擁有的交易與資源生命週期契約。"""

from abc import abstractmethod
from types import TracebackType
from typing import Protocol, Self


class BaseUnitOfWork(Protocol):
    @abstractmethod
    def __enter__(self) -> Self:
        """取得交易資源；進入失敗由實作清理已取得的資源。"""
        ...

    @abstractmethod
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """釋放資源，未提交時回滾；不自動提交或抑制例外。"""
        ...

    @abstractmethod
    def commit(self) -> None:
        """正常返回代表提交已確認；拋錯不保證資料尚未保存。"""
        ...
