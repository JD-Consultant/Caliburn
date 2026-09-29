"""Bounded resaving of intact results; never retry a model or business operation here."""

from asyncio import CancelledError, sleep
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from math import isfinite

from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_random_exponential

from caliburn.adapters.checkpoint_failures import is_transient_checkpoint_failure


class ResultSaveCancelledError(CancelledError):
    """Cancellation during backoff with the original process-local save handoff.

    The immediate caller can retain save_error.recovery before propagating task
    cancellation. This grants neither resume authority nor a durable backup.
    """

    def __init__(self, save_error: Exception) -> None:
        super().__init__("Result-save waiting was cancelled; the original handoff is held")
        self.save_error = save_error


@dataclass(frozen=True, slots=True)
class ResultSaveRetryPolicy:
    """Local resave attempts, separate from durable outbound request budgets.

    Includes the initial entry. Backoff is cancellable; DB I/O timeouts belong to
    the connection owner. Exhaustion returns the original typed recovery handoff.
    """

    max_attempts: int = 3
    initial_delay_seconds: float = 0.25
    max_delay_seconds: float = 1.0

    def __post_init__(self) -> None:
        if type(self.max_attempts) is not int or self.max_attempts < 1:
            raise ValueError("Configure a positive result-save attempt bound")
        if (
            not isfinite(self.initial_delay_seconds)
            or not isfinite(self.max_delay_seconds)
            or not 0 <= self.initial_delay_seconds <= self.max_delay_seconds
        ):
            raise ValueError("Configure finite nonnegative result-save delays in order")


async def retry_result_save[T](
    operation: Callable[[], Awaitable[T]],
    *,
    errors: tuple[type[Exception], ...],
    policy: ResultSaveRetryPolicy,
) -> T:
    """Caller retains exact R/C/count and re-enters its original guarded boundary.

    Only direct driver failures wrapped by the caller's intact-result exception
    qualify. No cause-chain guessing, exception logging, new storage or Graph
    node retry. Later tool/accounting failures must escape without being retried.
    """
    pending_save: Exception | None = None

    def should_retry(error: BaseException) -> bool:
        nonlocal pending_save
        if isinstance(error, errors) and is_transient_checkpoint_failure(error.__cause__):
            pending_save = error
            return True
        return False

    async def wait_with_handoff(seconds: float) -> None:
        nonlocal pending_save
        try:
            await sleep(seconds)
        except CancelledError:
            if pending_save is not None:
                raise ResultSaveCancelledError(pending_save) from None
            raise
        finally:
            # A later operation may save this result and move on. Never attach
            # this older handoff to cancellation inside a subsequent operation.
            pending_save = None

    retrying = AsyncRetrying(
        sleep=wait_with_handoff,
        retry=retry_if_exception(should_retry),
        stop=stop_after_attempt(policy.max_attempts),
        wait=wait_random_exponential(
            multiplier=policy.initial_delay_seconds, max=policy.max_delay_seconds
        ),
        reraise=True,
    )
    return await retrying(operation)
