"""公版查找入口共用的有界執行能力，由 Host 管理實際 worker。"""

from collections.abc import Callable
from typing import Protocol


class SearchRunner(Protocol):
    """Run blocking model work under the host's lifetime and capacity limit."""

    async def run[T](self, operation: Callable[[], T]) -> T: ...
