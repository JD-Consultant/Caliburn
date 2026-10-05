"""Join the exact native exit tasks handed back by the pinned LangGraph runtime."""

import asyncio


async def await_native_cleanup(error: BaseException) -> None:
    """Join available exit handles without treating a cancelled carrier as proof.

    LangGraph 1.2.12 attaches its exit task to cancellation args. App wrappers
    retain that exception as a cause/context; do not discover unrelated tasks,
    restart work, or interpret an exception as permission to adopt a result.
    A cancelled exit carrier may leave saver work behind; whole-file deletion
    additionally relies on the checkpoint adapter's transactional file fence.
    """
    errors = [error]
    visited: set[int] = set()
    pending: set[asyncio.Task[object]] = set()
    while errors:
        current = errors.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))
        pending.update(arg for arg in current.args if isinstance(arg, asyncio.Task))
        if current.__cause__ is not None:
            errors.append(current.__cause__)
        if current.__context__ is not None:
            errors.append(current.__context__)

    cancellation = None
    while pending:
        try:
            done, pending = await asyncio.wait(pending)
        except asyncio.CancelledError as interrupted:
            # wait() does not cancel borrowed native tasks. Finish joining them
            # even when shutdown or a repeated user control interrupts this wait.
            if not isinstance(error, asyncio.CancelledError):
                cancellation = interrupted
            continue
        for task in done:
            if not task.cancelled():
                task.exception()  # Observe cleanup failure; original task refs remain on error.
    if cancellation is not None:
        raise cancellation from error
