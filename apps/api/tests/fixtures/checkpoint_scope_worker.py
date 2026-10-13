"""Bound a cancel-scope starvation probe without a database or provider."""

import asyncio
import json
import sys
from uuid import uuid4

import anyio

from caliburn.adapters.job_file_checkpointer import JobFilePostgresSaver


class Transaction:
    def __init__(self):
        self.locked = False

    async def __aenter__(self):
        self.locked = True

    async def __aexit__(self, *_):
        self.locked = False


class Cursor:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    async def execute(self, *_):
        pass

    async def fetchone(self):
        return (1,)


class Connection:
    def __init__(self):
        self.fence = Transaction()

    def transaction(self):
        return self.fence

    def cursor(self):
        return Cursor()


async def run(mode, fails):
    # Only the wait policy is under test. Real same-connection KEY SHARE and
    # deletion serialization are covered by test_job_file_deletion on PostgreSQL.
    saver = object.__new__(JobFilePostgresSaver)
    saver.lock = asyncio.Lock()
    connection = Connection()
    saver._connection = connection
    entered, release = asyncio.Event(), asyncio.Event()
    scopes, adopted, saved = [], [], []
    unobserved = []
    asyncio.get_running_loop().set_exception_handler(
        lambda _loop, context: unobserved.append(context)
    )

    async def save():
        entered.set()
        await release.wait()
        assert connection.fence.locked
        saved.append(True)
        if fails:
            raise RuntimeError("synthetic late saver failure")
        return "late original"

    async def borrower():
        with anyio.CancelScope() as scope:
            scopes.append(scope)
            adopted.append(
                await saver._save_for_job_file(
                    {"configurable": {"thread_id": f"{uuid4()}:scope"}}, save
                )
            )

    task = asyncio.create_task(borrower())
    await entered.wait()
    if mode == "scope":
        scopes[0].cancel()
    else:
        task.cancel()
    await asyncio.sleep(0.01)
    assert not task.done()
    assert connection.fence.locked
    if mode == "repeated":
        task.cancel()
    release.set()
    try:
        await task
    except asyncio.CancelledError:
        assert mode != "scope"
    assert saved == [True]
    assert adopted == []
    assert not connection.fence.locked
    assert unobserved == [], [
        (context.get("message"), repr(context.get("exception"))) for context in unobserved
    ]
    print(json.dumps({"saved": True, "adopted": False, "released": True}))


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1], sys.argv[2] == "failure"))
