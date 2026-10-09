"""Wait for owned cleanup without letting a borrower cancel its underlying task."""

import asyncio

import anyio


async def join_owned[T](task: asyncio.Future[T]) -> T:
    """Defer raw repeated cancellation until the owned work really finishes.

    AnyIO shielding handles cancel scopes; asyncio.wait also leaves the task alone
    when a supervisor issues raw Task.cancel(). Never adopt a late result after cancel.
    """
    cancelled = None
    with anyio.CancelScope(shield=True):
        while not task.done():
            try:
                await asyncio.wait((task,))
            except asyncio.CancelledError as error:
                cancelled = error
    if cancelled is not None:
        if not task.cancelled():
            task.exception()
        raise cancelled
    if not task.cancelled():
        task.exception()
    # Leaving a shield does not itself deliver a cancelled enclosing AnyIO scope.
    # Cancellation wins over both a late value and a late worker exception. Observe
    # the exception first so discarding it does not leave an unhandled Future error.
    await anyio.lowlevel.checkpoint_if_cancelled()
    return task.result()
