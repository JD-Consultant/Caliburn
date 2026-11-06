"""只重試確定未提交的 JD 序列化失敗，不重用失敗交易或工作根。"""

from collections.abc import Callable
from functools import wraps
from random import uniform
from time import monotonic, sleep

from caliburn.modules.job_description.application.errors import (
    JobDescriptionRetryableTransactionError,
)


def retry_transaction[**P, R](operation: Callable[P, R]) -> Callable[P, R]:
    """至多三次完整嘗試；五秒只限制新重試准入，不中斷進行中的 SQL。"""

    @wraps(operation)
    def run(*args: P.args, **kwargs: P.kwargs) -> R:
        deadline = monotonic() + 5.0
        for attempt in range(3):
            try:
                return operation(*args, **kwargs)
            except JobDescriptionRetryableTransactionError:
                if attempt == 2 or monotonic() >= deadline:
                    raise
                sleep(uniform(0.0, 0.05 * (2**attempt)))
                if monotonic() >= deadline:
                    raise
        raise AssertionError("重試次數已由最後一次例外封閉")

    return run
