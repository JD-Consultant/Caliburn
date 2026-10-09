"""Lifespan-owned Memory tasks; durable discovery, no broker and no nested model retry."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from types import MappingProxyType
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionWriter,
)
from caliburn.features.work_memory.consolidation_models import (
    MemoryEvidenceError,
    MemoryEvidenceIssue,
)
from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow
from caliburn.workflows.runner_failures import (
    RunnerFailure,
    capture_runner_failure,
    has_terminal_outcome,
)

_LOG = logging.getLogger(__name__)


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
        self._sessions = sessions
        self._run = run
        self._check_leadership = check_leadership
        self._interval = poll_interval_seconds
        self._maximum = max_concurrent_batches
        self._wake = asyncio.Event()
        self._scan_lock = asyncio.Lock()
        self._tasks: dict[UUID, asyncio.Task[None]] = {}
        self._attempted: set[ExecutionScope] = set()
        self._failures: dict[ExecutionScope, RunnerFailure] = {}
        self._failure: RunnerFailure | None = None
        self._evidence_issues: frozenset[MemoryEvidenceIssue] = frozenset()
        self._monitor: asyncio.Task[None] | None = None
        self._shutdown: asyncio.Task[None] | None = None
        self._started = False
        self._closing = False

    @property
    def failure(self) -> RunnerFailure | None:
        return self._failure

    @property
    def failures(self) -> Mapping[ExecutionScope, RunnerFailure]:
        """Local recovery data, not HTTP/model text; no exception stacks are retained."""
        return MappingProxyType(self._failures)

    @property
    def evidence_issues(self) -> frozenset[MemoryEvidenceIssue]:
        """Safe current admission diagnostics, separate from unknown runner handoffs."""
        return self._evidence_issues

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

    def forget_deleted_file(self, job_file_id: UUID) -> None:
        """Deletion owner only, after confirmed deletion while holding dispatch."""
        if self.has_file_runner(job_file_id):
            raise ExecutionStateError("The Memory invocation is still finishing")
        for scope in tuple(self._failures):
            if scope.job_file_id == job_file_id:
                del self._failures[scope]
        self._attempted = {scope for scope in self._attempted if scope.job_file_id != job_file_id}
        self._evidence_issues = frozenset(
            issue for issue in self._evidence_issues if issue.job_file_id != job_file_id
        )

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
            discovery = await self._requests.discover()
            ready = frozenset(discovery.ready_file_ids)
            # A claim-only failure stays visible until that file is checked again. A scan
            # which cannot claim because capacity is full has not proved the evidence valid.
            issues = set(discovery.issues) | {
                issue for issue in self._evidence_issues if issue.job_file_id in ready
            }
            for ready_file in discovery.ready_files:
                file_id = ready_file.job_file_id
                if file_id in self._tasks:
                    continue
                if any(scope.job_file_id == file_id for scope in self._failures):
                    continue
                if len(self._tasks) >= self._maximum:
                    break
                # Discovery supplies identity only; claim still rechecks durable eligibility.
                if ready_file.active_scope in self._attempted:
                    continue
                await self._check_leadership()
                try:
                    work = await self._requests.claim(file_id, writer_id=uuid4())
                except MemoryEvidenceError as error:
                    # claim's transaction has already rolled back. Database/fence failures
                    # are deliberately not caught here and still stop all local dispatch.
                    issues = {issue for issue in issues if issue.job_file_id != file_id}
                    issues.add(error.issue)
                    continue
                issues = {issue for issue in issues if issue.job_file_id != file_id}
                if work is None:
                    continue
                await self._check_leadership()
                self._attempted.add(work.writer.scope)
                self._tasks[file_id] = asyncio.create_task(
                    self._run_once(work.writer), name=f"memory-{work.writer.scope.execution_id.hex}"
                )
            self._report_evidence_issues(frozenset(issues))

    def _report_evidence_issues(self, issues: frozenset[MemoryEvidenceIssue]) -> None:
        for issue in sorted(
            issues - self._evidence_issues,
            key=lambda item: (item.job_file_id, item.command_id, item.reason),
        ):
            _LOG.error(
                "memory.evidence_invalid",
                extra={
                    "job_file_id": issue.job_file_id,
                    "execution_id": issue.execution_id,
                    "command_id": issue.command_id,
                    "operation": "consolidation_admission",
                    "failure_kind": issue.reason,
                },
            )
        self._evidence_issues = issues

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
            self._failure = capture_runner_failure(error)
            _LOG.error(
                "supervisor.monitor_failed",
                extra={
                    "execution_kind": ExecutionKind.MEMORY_BATCH.value,
                    "operation": "scan",
                    "failure_kind": type(error).__name__,
                },
            )
        finally:
            self._closing = True
            await self._stop_tasks()

    async def _run_once(self, writer: ExecutionWriter) -> None:
        try:
            await self._run(writer)
        except asyncio.CancelledError as error:
            self._failures[writer.scope] = capture_runner_failure(error)
            raise  # Shutdown is not Memory cancellation/discard or a new batch.
        except Exception as error:
            self._failures[writer.scope] = capture_runner_failure(error)
        finally:
            try:
                if writer.scope in self._failures and await has_terminal_outcome(
                    self._sessions, writer.scope
                ):
                    self._failures.pop(writer.scope, None)
            finally:
                self._tasks.pop(writer.scope.job_file_id, None)
                self._wake.set()

    async def _stop_tasks(self) -> None:
        tasks = tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
