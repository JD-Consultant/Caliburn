"""One-process manual writer ownership, separate from JD rules and checkpoints.

Native futures own the actual SQL callable, not an HTTP waiter. The host supplies
native process ownership and cross-restart death evidence. Without that capability
an orphan remains blocked; absence of a local Future never becomes stopped proof.
This module does not start or rewind an Agent.
"""

from concurrent.futures import Future, ThreadPoolExecutor, wait
from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import Event, Lock, RLock, current_thread, main_thread
from time import monotonic
from typing import Callable, Protocol
from uuid import UUID

from .intents import AdmittedIdentity, BoundEdit
from .storage.receipts import WriteObservation
from .storage.service import JdStorage, WriterAuthority


class RuntimeFailure(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class OperationCheckpoints(Protocol):
    def read(self, document_id: str) -> AdmittedIdentity | None: ...
    def admit(self, identity: AdmittedIdentity) -> None: ...
    def close(self, identity: AdmittedIdentity) -> None: ...


class PreviousHost(Protocol):
    def require_previous_stopped(self) -> None:
        """Check this host's live OS ownership and prior process-group exit proof."""


@dataclass(frozen=True)
class Completion:
    observation: WriteObservation | None
    checkpoint_closed: bool
    error: str | None = None


@dataclass(frozen=True)
class WriterStatus:
    identity: AdmittedIdentity | None
    running: bool
    write_blocked: bool
    error: str | None


@dataclass
class _Attempt:
    mode: str
    future: Future | None = None
    settled: Event = field(default_factory=Event)
    completion: Completion | None = None
    handle: "WriterHandle | None" = None


class WriterHandle:
    """Observation handle; waiting or abandoning it cannot cancel its writer."""
    def __init__(self, attempt):
        self._attempt = attempt

    def wait(self, timeout=None) -> Completion:
        if not self._attempt.settled.wait(timeout):
            raise TimeoutError("writer_still_running")
        return self._attempt.completion


@dataclass
class _Entry:
    identity: AdmittedIdentity
    attempt: _Attempt
    token: object = field(default_factory=object)
    write_future: Future | None = None
    observation: WriteObservation | None = None
    previous_host: PreviousHost | None = None


@dataclass
class _Slot:
    lock: RLock = field(default_factory=RLock)
    entry: _Entry | None = None


def _attempt(mode):
    value = _Attempt(mode)
    value.handle = WriterHandle(value)
    return value


def _checkpoint_failure(error):
    return "document_busy" if getattr(error, "code", None) == "document_busy" else "checkpoint_unavailable"


class ManualRuntime:
    def __init__(self, checkpoints: OperationCheckpoints,
                 storage_factory: Callable[[WriterAuthority], JdStorage], *, max_workers=4,
                 previous_host: PreviousHost | None = None):
        if type(max_workers) is not int or not 1 <= max_workers <= 16:
            raise ValueError("invalid_worker_limit")
        if previous_host is not None and not callable(getattr(previous_host, "require_previous_stopped", None)):
            raise ValueError("invalid_previous_host")
        self.checkpoints = checkpoints
        self._slots = {}
        self._registry = Lock()  # Only dictionary/accepting state, never I/O or waits.
        self._accepting = True
        self._previous_host = previous_host
        self._startup_lock = Lock()
        self._startup_done = Event()
        if previous_host is None:
            self._startup_done.set()  # Standalone in-process owner, no orphan adoption.
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="jd-manual")
        self._execution = ContextVar("jd_manual_execution", default=None)
        self.storage = storage_factory(self)

    def _slot(self, document, *, admit=False):
        with self._registry:
            if admit and not self._accepting:
                raise RuntimeFailure("runtime_closed")
            return self._slots.setdefault(document, _Slot())

    def _require_open(self):
        with self._registry:
            if not self._accepting:
                raise RuntimeFailure("runtime_closed")

    def _require_host(self):
        if self._previous_host is not None:
            try:
                self._previous_host.require_previous_stopped()
            except Exception:
                raise RuntimeFailure("host_not_valid") from None

    @property
    def ready(self) -> bool:
        with self._registry:
            return self._accepting and self._startup_done.is_set()

    def finish_startup(self, *, timeout=10) -> int:
        """Close all previous manual descriptors before enabling new admission.

        The host excludes all catalog writers during this scan. Catalog includes
        archived documents and is never permanently deleted. Timeout retains the
        actual recovery Future; retry on this same owner cannot duplicate it.
        """
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 60:
            raise ValueError("invalid_recovery_timeout")
        if not self._startup_lock.acquire(blocking=False):
            raise RuntimeFailure("startup_busy")
        try:
            self._require_open()
            self._require_host()
            if self._startup_done.is_set():
                return 0
            after, recovered = None, 0
            while True:
                self._require_open()
                self._require_host()
                try:
                    documents = self.storage.document_ids(after=after, limit=100)
                except Exception:
                    raise RuntimeFailure("read_failed") from None
                for document in documents:
                    slot = self._slot(document, admit=True)
                    with slot.lock:
                        self._require_open()
                        self._require_host()
                        try:
                            pending = self.checkpoints.read(document)
                        except Exception as error:
                            raise RuntimeFailure(_checkpoint_failure(error)) from None
                        if pending is not None and slot.entry is None:
                            self._manual(pending)
                            if pending.document_id != document:
                                raise RuntimeFailure("checkpoint_conflict")
                            attempt = _attempt("recover")
                            attempt.completion = Completion(None, False)
                            attempt.settled.set()
                            slot.entry = _Entry(pending, attempt, previous_host=self._previous_host)
                        needs_recovery = slot.entry is not None
                    if needs_recovery:
                        try:
                            result = self.recover(document, timeout=timeout)
                        except TimeoutError:
                            raise RuntimeFailure("startup_recovery_pending") from None
                        if not result.checkpoint_closed:
                            raise RuntimeFailure("startup_recovery_pending")
                        recovered += 1
                if len(documents) < 100:
                    break
                after = documents[-1]
            self._require_host()
            with self._registry:
                if not self._accepting:
                    raise RuntimeFailure("runtime_closed")
                self._startup_done.set()
            return recovered
        finally:
            self._startup_lock.release()

    @staticmethod
    def _manual(identity):
        try:
            if type(identity) is not AdmittedIdentity:
                raise ValueError()
            identity.validate()
            if identity.origin != "manual":
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise RuntimeFailure("invalid_input") from None

    def submit(self, intent: BoundEdit) -> WriterHandle:
        if not isinstance(intent, BoundEdit):
            raise RuntimeFailure("invalid_input")
        identity = intent.identity
        self._manual(identity)
        slot = self._slot(identity.document_id, admit=True)
        with slot.lock:
            self._require_open()
            self._require_host()
            if not self._startup_done.is_set():
                raise RuntimeFailure("startup_pending")
            if slot.entry:
                if slot.entry.identity == identity:
                    return slot.entry.attempt.handle
                if slot.entry.identity.operation_id == identity.operation_id:
                    raise RuntimeFailure("operation_conflict")
            # This read can find an original result, but None is not stopped
            # proof. A new execution still requires durable admission below.
            try:
                original = self.storage.lookup(identity)
            except Exception as error:
                reported = getattr(error, "code", None)
                code = reported if reported in {"operation_conflict", "document_missing"} else "read_failed"
                raise RuntimeFailure(code) from None
            attempt = _attempt("write")
            if original is not None:
                attempt.completion = Completion(original, True)
                attempt.settled.set()
                return attempt.handle
            if slot.entry:
                raise RuntimeFailure("document_busy")
            try:
                pending = self.checkpoints.read(identity.document_id)
            except Exception as error:
                raise RuntimeFailure(_checkpoint_failure(error)) from None
            if pending is not None:
                raise RuntimeFailure("document_busy")
            entry = _Entry(identity, attempt)
            slot.entry = entry
            try:
                self.checkpoints.admit(identity)
            except BaseException as admission_error:
                # Keep this generation even if the Saver acknowledgement was
                # lost. It is known in this process that no SQL was submitted.
                attempt.completion = Completion(None, False, "checkpoint_unavailable")
                attempt.settled.set()
                if not isinstance(admission_error, Exception):
                    raise  # Preserve caller interruption after recording no SQL began.
                return attempt.handle
            self._schedule(slot, entry, attempt, intent)
            return attempt.handle

    def _schedule(self, slot, entry, attempt, intent=None):
        try:
            attempt.future = self._pool.submit(self._run, entry, attempt, intent)
        except RuntimeError:
            attempt.completion = Completion(entry.observation, False, "writer_not_started")
            attempt.settled.set()
            return
        if attempt.mode == "write":
            entry.write_future = attempt.future
        attempt.future.add_done_callback(lambda future: self._finished(slot, entry, attempt, future))

    def _run(self, entry, attempt, intent):
        token = self._execution.set((entry.token, entry.identity.document_id, attempt.mode))
        try:
            if attempt.mode == "write":
                return self.storage.execute(intent)
            if entry.observation is not None and entry.observation.confirmed:
                return entry.observation  # Only checkpoint cleanup remains.
            return self.storage.reconcile_stopped(entry.identity)
        finally:
            self._execution.reset(token)

    def _finished(self, slot, entry, attempt, future):
        with slot.lock:
            if attempt.settled.is_set():
                return
            if slot.entry is not entry or entry.attempt is not attempt:
                attempt.completion = Completion(None, False, "obsolete_attempt")
                attempt.settled.set()
                return
            error = None
            try:
                # Native Future.exception returns the worker's BaseException as
                # data. Never re-raise it into callback/executor logging.
                if future.cancelled() or future.exception() is not None:
                    raise ValueError()
                result = future.result()
                if (not isinstance(result, WriteObservation)
                        or result.document_id != entry.identity.document_id
                        or result.operation_id != entry.identity.operation_id):
                    raise ValueError()
                entry.observation = result
            except Exception:
                error = "writer_failed" if not future.cancelled() else "writer_not_started"
            closed = False
            try:
                if entry.observation is not None and entry.observation.confirmed:
                    self.checkpoints.close(entry.identity)
                    closed = True
                    slot.entry = None
            except BaseException as cleanup_error:
                error = "checkpoint_unavailable"
                # A callback can run inline when its Future already completed.
                # Preserve the main thread's process/interrupt semantics while
                # still settling the owned attempt and retaining its receipt.
                if not isinstance(cleanup_error, Exception) and current_thread() is main_thread():
                    raise
            finally:
                attempt.completion = Completion(entry.observation, closed, error)
                attempt.settled.set()

    def require_bound(self, intent):
        self._require_host()
        context = self._execution.get()
        slot = self._slot(intent.document_id)
        with slot.lock:
            entry = slot.entry
            if (entry is None or entry.identity != intent.identity
                    or context != (entry.token, intent.document_id, "write")
                    or entry.write_future is None or not entry.write_future.running()):
                raise RuntimeFailure("writer_not_valid")

    def require_stopped(self, identity):
        context = self._execution.get()
        slot = self._slot(identity.document_id)
        with slot.lock:
            entry = slot.entry
            if (entry is None or entry.identity != identity
                    or context != (entry.token, identity.document_id, "recover")
                    or entry.write_future is not None and not entry.write_future.done()):
                raise RuntimeFailure("writer_not_stopped")
            if entry.previous_host is not None:
                try:
                    entry.previous_host.require_previous_stopped()
                except Exception:
                    raise RuntimeFailure("writer_not_stopped") from None

    def recover(self, document, *, timeout=10, expected_operation_id: UUID | None = None) -> Completion:
        if expected_operation_id is not None and not isinstance(expected_operation_id, UUID):
            raise RuntimeFailure("invalid_input")
        slot = self._slot(document, admit=True)
        with slot.lock:
            self._require_open()
            self._require_host()
            entry = slot.entry
            if entry is None:
                # No local entry is never a claim about a previous process.
                raise RuntimeFailure("writer_not_stopped")
            if expected_operation_id is not None and entry.identity.operation_id != expected_operation_id:
                raise RuntimeFailure("operation_conflict")
            if not entry.attempt.settled.is_set():
                raise RuntimeFailure("writer_not_stopped")
            try:
                pending = self.checkpoints.read(document)
            except Exception as error:
                raise RuntimeFailure(_checkpoint_failure(error)) from None
            if pending is None:
                if ((entry.write_future is None and entry.previous_host is None)
                        or entry.observation is not None and entry.observation.confirmed):
                    slot.entry = None
                    return Completion(entry.observation, True)
                raise RuntimeFailure("checkpoint_conflict")
            if pending != entry.identity:
                raise RuntimeFailure("checkpoint_conflict")
            attempt = _attempt("recover")
            entry.attempt = attempt
            self._schedule(slot, entry, attempt)
        return attempt.handle.wait(timeout)

    def status(self, document) -> WriterStatus:
        self._require_host()
        slot = self._slot(document)
        with slot.lock:
            entry = slot.entry
            if entry:
                completion = entry.attempt.completion
                return WriterStatus(entry.identity, not entry.attempt.settled.is_set(), True,
                                    completion.error if completion else None)
            try:
                pending = self.checkpoints.read(document)
            except Exception as error:
                return WriterStatus(None, False, True, _checkpoint_failure(error))
            return WriterStatus(pending, False, pending is not None,
                                "writer_not_stopped" if pending is not None else None)

    def close(self, *, timeout=10) -> bool:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 <= timeout <= 60:
            raise ValueError("invalid_shutdown_timeout")
        deadline = monotonic() + timeout
        with self._registry:
            self._accepting = False
            slots = tuple(self._slots.values())
        if not self._startup_lock.acquire(timeout=max(0, deadline - monotonic())):
            return False  # The catalog/Saver scan still owns startup resources.
        self._startup_lock.release()  # Closed admission prevents another scan starting I/O.
        attempts = []
        for slot in slots:
            if not slot.lock.acquire(timeout=max(0, deadline - monotonic())):
                return False  # Admission/checkpoint I/O is still using resources.
            try:
                entry = slot.entry
                if entry and entry.attempt.future:
                    attempts.append(entry.attempt)
            finally:
                slot.lock.release()
        # Graceful shutdown drains admitted work. This is not the user's
        # cancel-edit action and does not invent a failure for queued writes.
        _, running = wait([attempt.future for attempt in attempts],
                          timeout=max(0, deadline - monotonic()))
        if running:
            return False
        for attempt in attempts:
            if not attempt.settled.wait(max(0, deadline - monotonic())):
                return False  # Future.done can precede checkpoint cleanup.
        self._pool.shutdown(wait=True)
        return True
