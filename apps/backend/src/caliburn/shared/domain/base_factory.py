"""領域建構契約，保留具體 Factory 的輸入及產物型別。"""

from abc import abstractmethod
from typing import Protocol


class BaseFactory[**ParamsT, ProductT](Protocol):
    @abstractmethod
    def create(self, *args: ParamsT.args, **kwargs: ParamsT.kwargs) -> ProductT:
        """產生符合領域規則的完整物件，不承諾持久化或交易。"""
        ...
