"""具型別服務識別及插件初始化可用的唯讀依賴。"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, cast


@dataclass(frozen=True, eq=False)
class ServiceKey[T]:
    """公開契約只宣告一次；以物件身分辨識，name 用於錯誤說明。"""

    name: str

    def bind(self, value: T) -> ServiceBinding[T]:
        return ServiceBinding(self, value)


class ServiceCollection[T](ServiceKey[tuple[T, ...]]):
    """多個 provider 各供一份 tuple，啟動時依配置順序合成固定集合。"""


@dataclass(frozen=True)
class ServiceBinding[T]:
    key: ServiceKey[T]
    value: T


class PluginServices:
    """啟動固定的唯讀服務表；異質儲存與型別轉接留在此邊界。"""

    def __init__(self, services: Mapping[ServiceKey[Any], object]):
        self._services = MappingProxyType(dict(services))

    def require[T](self, key: ServiceKey[T]) -> T:
        try:
            return cast(T, self._services[key])
        except KeyError:
            raise ValueError(
                f"Service was not declared as a dependency: {key.name}"
            ) from None
