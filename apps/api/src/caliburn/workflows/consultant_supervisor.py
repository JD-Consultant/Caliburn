"""Bounded local supervision, not a second model retry or product lifecycle engine."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from types import MappingProxyType
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.process_lock import PostgresProcessLock
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionScope,
    ExecutionStateError,
    ExecutionWriter,
)


class ConsultantSupervisor:
    """Own the leader session and strong task refs; borrow sessions and runner.

    Construct only once per lifespan. All consultant runners in the local deployment
    must enter here. A completed/failed invocation is never automatically reinvoked
    by polling; the existing runner owns request reconciliation and retry budgets.
    """

    def __init__(
        self,
        *,
        sessions: async_sessionmaker[AsyncSession],
        run: Callable[[ExecutionWriter], Awaitable[object]],
        process_lock: PostgresProcessLock,
        before_leader_release: Callable[[], Awaitable[None]] | None = None,
        poll_interval_seconds: float = 1.0,
        scan_timeout_seconds: float = 10.0,
        max_concurrent_turns: int = 4,
    ) -> None:
        if not 0 < poll_interval_seconds <= 60 or not 0 < scan_timeout_seconds <= 30:
            raise ValueError("Supervisor polling and scan timeouts must be positive and bounded")
        if type(max_concurrent_turns) is not int or max_concurrent_turns < 1:
            raise ValueError("Supervisor concurrency must be positive")
        self._sessions = sessions
        self._run = run
        self._lock = process_lock
        self._before_leader_release = before_leader_release
        self._poll_interval = poll_interval_seconds
        self._scan_timeout = scan_timeout_seconds
        self._max_concurrent = max_concurrent_turns
        self._wake = asyncio.Event()
        self._dispatch_lock = asyncio.Lock()
        self._tasks: dict[ExecutionScope, asyncio.Task[None]] = {}
        self._attempted: set[ExecutionScope] = set()
        self._failures: dict[ExecutionScope, BaseException] = {}
        self._failure: Exception | None = None
        self._monitor: asyncio.Task[None] | None = None
        self._shutdown: asyncio.Task[None] | None = None
        self._leader_release: asyncio.Task[None] | None = None
        self._started = False
        self._closing = False

    @property
    def running(self) -> bool:
        return self._monitor is not None and not self._monitor.done() and not self._closing

    @property
    def failure(self) -> Exception | None:
        """Local diagnostic only; never serialize raw exceptions into HTTP/model output."""
        return self._failure

    @property
    def failures(self) -> Mapping[ExecutionScope, BaseException]:
        """Retain typed original-result handoffs for reconciliation, without logging payloads."""
        return MappingProxyType(self._failures)

    def stopped_reason(self, scope: ExecutionScope) -> str | None:
        """Safe disposition hint, not product completion/failure or retry permission."""
        error = self._failures.get(scope)
        if isinstance(error, asyncio.CancelledError):
            return "runner_interrupted"
        if error is not None:
            return "runner_failed"
        if scope in self._attempted and scope not in self._tasks:
            return "runner_returned"
        return None

    def has_runner(self, scope: ExecutionScope) -> bool:
        return scope in self._tasks

    async def start(self) -> None:
        if self._started or self._closing:
            raise RuntimeError("Create a new supervisor for a new lifespan")
        self._started = True
        acquired = False
        try:
            await self._lock.acquire()
            acquired = True
            await self._scan()
            self._monitor = asyncio.create_task(self._monitor_work(), name="consultant-supervisor")
        except BaseException:
            # Cancellation is cleanup, not cancellation of a product Turn.
            self._closing = True
            if acquired:
                await self._release_leadership()
            else:
                await self._lock.close()
            raise

    def notify(self, scope: ExecutionScope | None = None) -> None:
        """Wake discovery after commit; the database, not this optional hint, is the queue.

        Call on the supervisor's event loop. No status transition, writer replacement,
        interrupt resume or retry authorization is conveyed by this hint.
        """
        if self.running:
            self._wake.set()

    @asynccontextmanager
    async def hold_dispatch(self) -> AsyncIterator[None]:
        """Serialize short product control coordination with writer claim/task launch."""
        async with self._dispatch_lock:
            yield

    async def wait_for_runner(self, scope: ExecutionScope) -> None:
        """Wait for a paused invocation to return; never cancel it as a resume shortcut."""
        task = self._tasks.get(scope)
        if task is not None:
            done, _ = await asyncio.wait((task,), timeout=self._scan_timeout)
            if not done:
                raise TimeoutError("The original consultant invocation has not exited")

    async def stop_runner(self, scope: ExecutionScope) -> None:
        """Only after product fencing/abandonment commits; no product transition here."""
        task = self._tasks.get(scope)
        if task is not None:
            task.cancel()
            await self.wait_for_runner(scope)

    def allow_reentry(self, scope: ExecutionScope) -> None:
        """Control owner only: after durable resume authorization and original task exit."""
        if not self.running or scope in self._tasks:
            raise ExecutionStateError("The supervisor cannot reenter this Turn now")
        self._attempted.discard(scope)
        self._failures.pop(scope, None)
        self._wake.set()

    async def close(self) -> None:
        if self._monitor is None and self._leader_release is None:
            return
        if self._shutdown is None:
            self._shutdown = asyncio.create_task(self._close(), name="consultant-shutdown")
        await asyncio.shield(self._shutdown)

    async def _close(self) -> None:
        monitor = self._monitor
        if monitor is not None:
            if not self._closing:
                self._closing = True
                monitor.cancel()
            await asyncio.gather(monitor, return_exceptions=True)
        # A task cancelled before its first execution never enters its finally block.
        await self._release_leadership()

    async def _monitor_work(self) -> None:
        try:
            while True:
                try:
                    await asyncio.wait_for(self._wake.wait(), self._poll_interval)
                except TimeoutError:
                    pass
                self._wake.clear()
                await self._scan()
        except Exception as error:
            # One failed supervision I/O attempt is the bounded policy. No reconnect
            # followed by writer takeover, no provider retry, no product status change.
            self._failure = error
        finally:
            self._closing = True
            try:
                await self._release_leadership()
            except Exception as error:
                # close() observes the same failed release task. Keep the original
                # scan failure, if any, without letting a monitor exception go unread.
                if self._failure is None:
                    self._failure = error

    async def _release_leadership(self) -> None:
        if self._leader_release is None:
            self._leader_release = asyncio.create_task(
                self._stop_and_release_leader(), name="consultant-leader-release"
            )
        await asyncio.shield(self._leader_release)

    async def _stop_and_release_leader(self) -> None:
        """Stop all borrowers before releasing the one existing local/PG fence.

        The callback must not call this supervisor's close(). Failed cleanup is
        retained, not retried: never force-release a fence around live workers.
        """
        await self._stop_runners()
        if self._before_leader_release is not None:
            await self._before_leader_release()
        await self._lock.close()

    async def _scan(self) -> None:
        async with self._dispatch_lock, asyncio.timeout(self._scan_timeout):
            await self._lock.check()
            async with self._sessions() as session:
                active = await executions.list_active_consultants(session)
            for info in active:
                if info.scope in self._attempted:
                    continue
                if len(self._tasks) >= self._max_concurrent:
                    break
                await self._lock.check()
                proposed_writer = uuid4()
                try:
                    async with self._sessions.begin() as session:
                        writer = await executions.claim_writer(
                            session,
                            info.scope,
                            writer_id=proposed_writer,
                            replaces_writer_id=info.writer_id,
                        )
                except ExecutionStateError:
                    # A concurrent product control won; discovery confers no authority.
                    continue
                # A commit error propagates and stops supervision, never blindly retries
                # a new writer. Start runner only after confirmed claim and live lock.
                await self._lock.check()
                self._attempted.add(info.scope)
                self._tasks[info.scope] = asyncio.create_task(
                    self._run_once(writer), name=f"consultant-{info.scope.execution_id.hex}"
                )

    async def _run_once(self, writer: ExecutionWriter) -> None:
        try:
            await self._run(writer)
        except asyncio.CancelledError as error:
            # Includes ResultSaveCancelledError: retain its original typed handoff.
            self._failures[writer.scope] = error
            raise
        except Exception as error:
            self._failures[writer.scope] = error
        finally:
            self._tasks.pop(writer.scope, None)
            self._wake.set()

    async def _stop_runners(self) -> None:
        tasks = tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
