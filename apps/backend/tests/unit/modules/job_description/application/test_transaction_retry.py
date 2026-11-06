"""時間與隨機接縫只驗有限政策；真交易生命週期由 PostgreSQL 測試驗證。"""

from asyncio import CancelledError
from collections.abc import Iterator

import pytest

from caliburn.modules.job_description.application import transaction_retry
from caliburn.modules.job_description.application.errors import (
    JobDescriptionConcurrencyError,
    JobDescriptionPersistenceError,
    JobDescriptionRetryableTransactionError,
)


def test_exhaustion_preserves_last_error_and_uses_two_full_jitter_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failures = [
        JobDescriptionRetryableTransactionError(str(index)) for index in range(3)
    ]
    windows: list[tuple[float, float]] = []
    delays: list[float] = []
    attempts = 0

    def jitter(lower: float, upper: float) -> float:
        windows.append((lower, upper))
        return upper / 2

    monkeypatch.setattr(transaction_retry, "uniform", jitter)
    monkeypatch.setattr(transaction_retry, "sleep", delays.append)

    @transaction_retry.retry_transaction
    def write() -> None:
        nonlocal attempts
        failure = failures[attempts]
        attempts += 1
        raise failure

    with pytest.raises(JobDescriptionRetryableTransactionError) as error:
        write()
    assert attempts == 3
    assert error.value is failures[-1]
    assert windows == [(0.0, 0.05), (0.0, 0.1)]
    assert delays == [0.025, 0.05]


@pytest.mark.parametrize("times", [(0.0, 5.0), (0.0, 4.99, 5.0)])
def test_budget_is_checked_after_failure_and_after_backoff(
    monkeypatch: pytest.MonkeyPatch, times: tuple[float, ...]
) -> None:
    clock: Iterator[float] = iter(times)
    delays: list[float] = []
    attempts = 0
    failure = JobDescriptionRetryableTransactionError("預算已耗盡")
    monkeypatch.setattr(transaction_retry, "monotonic", lambda: next(clock))
    monkeypatch.setattr(transaction_retry, "sleep", delays.append)

    @transaction_retry.retry_transaction
    def write() -> None:
        nonlocal attempts
        attempts += 1
        raise failure

    with pytest.raises(JobDescriptionRetryableTransactionError) as error:
        write()
    assert attempts == 1
    assert error.value is failure
    assert len(delays) == len(times) - 2


@pytest.mark.parametrize(
    "failure",
    [
        JobDescriptionConcurrencyError("舊版本"),
        JobDescriptionPersistenceError(commit_status="unknown"),
        JobDescriptionPersistenceError(commit_status="committed"),
        ValueError("不合法輸入"),
        CancelledError("取消"),
    ],
)
def test_other_failures_propagate_without_replay(failure: BaseException) -> None:
    attempts = 0

    @transaction_retry.retry_transaction
    def write() -> None:
        nonlocal attempts
        attempts += 1
        raise failure

    with pytest.raises(type(failure)) as error:
        write()
    assert error.value is failure
    assert attempts == 1


def test_cancellation_during_backoff_prevents_another_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    def cancel(delay: float) -> None:
        raise CancelledError("退避時取消")

    monkeypatch.setattr(transaction_retry, "sleep", cancel)

    @transaction_retry.retry_transaction
    def write() -> None:
        nonlocal attempts
        attempts += 1
        raise JobDescriptionRetryableTransactionError("未提交")

    with pytest.raises(CancelledError):
        write()
    assert attempts == 1
