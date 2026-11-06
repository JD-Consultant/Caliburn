"""聚合新增的共用 port；查詢與其他變更由具體用例定義。"""

from abc import abstractmethod
from typing import Protocol


class BaseRepository[AggregateT](Protocol):
    @abstractmethod
    def add(self, aggregate: AggregateT, /) -> None:
        """新增完整聚合，保留身分；不自行提交、不覆寫既有 ID。"""
        ...
