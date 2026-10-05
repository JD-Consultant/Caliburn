"""Lifespan-owned Memory tasks; durable discovery, no broker and no nested model retry."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from types import MappingProxyType
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions.models import ExecutionScope, ExecutionWriter
from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow


class MemorySupervisor:
    """Borrow the App's existing single-host leader guard; own only Memory tasks.

    Bootstrap starts this AFTER acquiring leadership and closes it BEFORE releasing
    that guard. check_leadership must fail when the original session/OS fence is lost;
    never reconnect/reacquire inside it. No user pause/cancel/retry API is offered.
    """

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        run: Callable[[ExecutionWriter], Awaitable[object]],
        check_leadership: Callable[[], Awaitable[None]],
        poll_interval_seconds: float = 1.0,
        max_concurrent_batches: int = 2,
    ) -> None:
        if (
            not 0 < poll_interval_seconds <= 60
            or type(max_concurrent_batches) is not int
            or max_concurrent_batches < 1
        ):
            raise ValueError("Memory supervision requires finite bounded polling and concurrency")
        self._requests = MemoryConsolidationWorkflow(sessions)
        self._run = run
        self._check_leadership = check_leadership
        self._interval = poll_interval_seconds
        self._maximum = max_concurrent_batches
        self._wake = asyncio.Event()
        self._scan_lock = asyncio.Lock()
        self._tasks: dict[UUID, asyncio.Task[None]] = {}
        self._attempted: set[ExecutionScope] = set()
        self._failures: dict[ExecutionScope, BaseException] = {}
        self._failure: Exception | None = None
        self._monitor: asyncio.Task[None] | None = None
        self._shutdown: asyncio.Task[None] | None = None
        self._started = False
        self._closing = False

    @property
    def failure(self) -> Exception | None:
        return self._failure

    @property
    def failures(self) -> Mapping[ExecutionScope, BaseException]:
        """Local recovery handoffs, not safe UI/model text; may hold original R/C objects."""
        return MappingProxyType(self._failures)

    async def start(self) -> None:
        if self._started:
            raise RuntimeError("Create one Memory supervisor per lifespan")
        self._started = True
        try:
            await self.scan()
            self._monitor = asyncio.create_task(self._monitor_work(), name="memory-supervisor")
        except BaseException:
            self._closing = True
            await self._stop_tasks()
            raise

    def notify(self) -> None:
        """Optional after-A-commit hint only; periodic discovery is authoritative."""
        if self._started and not self._closing:
            self._wake.set()

    def has_file_runner(self, job_file_id: UUID) -> bool:
        """Publication can commit before the invocation's native cleanup finishes."""
        return job_file_id in self._tasks

    @asynccontextmanager
    async def hold_dispatch(self) -> AsyncIterator[None]:
        """Exclude discovery/task launch during a short whole-file deletion transaction."""
        async with self._scan_lock:
            yield

    async def scan(self) -> None:
        """Bounded discovery; no retry authorization and no liveness inference from SQL."""
        async with self._scan_lock, asyncio.timeout(10):
            if self._closing:
                return
            await self._check_leadership()
            for file_id in await self._requests.discover():
                if file_id in self._tasks:
                    continue
                if any(scope.job_file_id == file_id for scope in self._failures):
                    continue
                if len(self._tasks) >= self._maximum:
                    break
                # Check already-returned active work before replacing its writer again.
                async with self._requests.sessions() as session:
                    from caliburn.features.executions.memory_discovery import read_active_memory

                    active = await read_active_memory(session, file_id)
                if active is not None and active.scope in self._attempted:
                    continue
                await self._check_leadership()
                work = await self._requests.claim(file_id, writer_id=uuid4())
                if work is None:
                    continue
                await self._check_leadership()
                self._attempted.add(work.writer.scope)
                self._tasks[file_id] = asyncio.create_task(
                    self._run_once(work.writer), name=f"memory-{work.writer.scope.execution_id.hex}"
                )

    async def close(self) -> None:
        if self._shutdown is None:
            self._shutdown = asyncio.create_task(self._close(), name="memory-shutdown")
        await asyncio.shield(self._shutdown)

    async def _close(self) -> None:
        self._closing = True
        if self._monitor is not None:
            self._monitor.cancel()
            await asyncio.gather(self._monitor, return_exceptions=True)
        await self._stop_tasks()

    async def _monitor_work(self) -> None:
        try:
            while True:
                try:
                    await asyncio.wait_for(self._wake.wait(), self._interval)
                except TimeoutError:
                    pass
                self._wake.clear()
                await self.scan()
        except Exception as error:
            self._failure = error
        finally:
            self._closing = True
            await self._stop_tasks()

    async def _run_once(self, writer: ExecutionWriter) -> None:
        try:
            await self._run(writer)
        except asyncio.CancelledError as error:
            self._failures[writer.scope] = error
            raise  # Shutdown is not Memory cancellation/discard or a new batch.
        except Exception as error:
            self._failures[writer.scope] = error
        finally:
            self._tasks.pop(writer.scope.job_file_id, None)
            self._wake.set()

    async def _stop_tasks(self) -> None:
        tasks = tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
