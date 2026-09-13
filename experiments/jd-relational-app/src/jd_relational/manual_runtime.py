"""One-process document writer ownership, separate from JD rules/checkpoints.

Native futures own the actual SQL callable, not an HTTP waiter. The host supplies
native process ownership and cross-restart death evidence. Without that capability
an orphan remains blocked; absence of a local Future never becomes stopped proof.
Foreground callbacks may invoke the native Agent; this owner never rewinds it
or writes an active child checkpoint. AI and SQL use separate native pools.
"""

from concurrent.futures import Future, ThreadPoolExecutor, wait
from contextvars import ContextVar
from dataclasses import dataclass, field
import re
from threading import Event, Lock, RLock, current_thread, get_ident, main_thread
from time import monotonic
from typing import TYPE_CHECKING, Callable, Protocol
from uuid import UUID

from .intents import AdmittedIdentity, BoundEdit
from .storage.receipts import WriteObservation
from .storage.service import JdStorage, WriterAuthority

if TYPE_CHECKING:
    from .storage.service import CatalogRecord


class RuntimeFailure(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ForegroundIdentity:
    document_id: str
    run_id: str
    request_digest: str

    def __post_init__(self):
        try:
            if (any(type(value) is not str or str(UUID(value)) != value
                    for value in (self.document_id, self.run_id))
                    or type(self.request_digest) is not str
                    or re.fullmatch(r"[0-9a-f]{64}", self.request_digest) is None):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise RuntimeFailure("invalid_input") from None


class ForegroundPermit:
    """App-held capability; only the exact live object in its slot is valid."""
    __slots__ = ("_identity", "_stop_event")

    def __init__(self, identity: ForegroundIdentity):
        self._identity = identity
        self._stop_event = Event()

    @property
    def identity(self) -> ForegroundIdentity:
        return self._identity

    @property
    def stop_event(self) -> Event:
        return self._stop_event


@dataclass(frozen=True)
class ForegroundStatus:
    running: bool
    write_blocked: bool
    error: str | None


@dataclass
class _Foreground:
    permit: ForegroundPermit
    future: Future | None = None
    settled: Event = field(default_factory=Event)
    closed: bool = False
    error: str | None = None
    handle: "ForegroundHandle | None" = None
    previous_host: "PreviousHost | None" = None


class ForegroundHandle:
    """Only observes and requests a cooperative stop; never exposes worker errors."""
    def __init__(self, entry: _Foreground):
        self._entry = entry

    @property
    def permit(self) -> ForegroundPermit:
        return self._entry.permit

    def request_stop(self) -> None:
        if self._entry.future is None or not self._entry.future.done():
            self.permit.stop_event.set()

    def add_done_callback(self, callback: Callable[["ForegroundHandle"], None]) -> None:
        """Observe native completion and the owner's actual callback completion."""
        if not callable(callback):
            raise RuntimeFailure("invalid_input")
        def after_owner(_):
            # A newly registered callback on a FINISHED Future runs immediately
            # in its registering thread, even while earlier callbacks still run.
            self._entry.settled.wait()
            callback(self)
        if self._entry.future is None:
            after_owner(None)
        else:
            self._entry.future.add_done_callback(after_owner)

    def wait(self, timeout=None) -> ForegroundStatus:
        if not self._entry.settled.wait(timeout):
            raise TimeoutError("foreground_still_running")
        return ForegroundStatus(False, not self._entry.closed, self._entry.error)


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
    token: object = field(default_factory=object, repr=False)
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
    foreground: ForegroundPermit | None = None


@dataclass
class _Slot:
    lock: RLock = field(default_factory=RLock)
    entry: _Entry | None = None
    catalog_token: object | None = None
    start_token: object | None = None
    foreground: _Foreground | None = None


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
        self._foreground_coordinator_claimed = False
        self._startup_recover = None
        self._startup_active = None
        self._previous_host = previous_host
        self._startup_lock = Lock()
        self._startup_done = Event()
        if previous_host is None:
            self._startup_done.set()  # Standalone in-process owner, no orphan adoption.
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="jd-manual")
        self._foreground_pool = ThreadPoolExecutor(max_workers=max_workers,
                                                  thread_name_prefix="jd-foreground")
        self._execution = ContextVar("jd_manual_execution", default=None)
        self._catalog_execution = ContextVar("jd_catalog_execution", default=None)
        self._startup_execution = ContextVar("jd_startup_execution", default=None)
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

    def claim_foreground_coordinator(self, *, startup_recover: Callable[[str, float], int] | None = None) -> None:
        """One coordinator owns each host's AI attempts and configured ports."""
        if startup_recover is not None and not callable(startup_recover):
            raise RuntimeFailure("invalid_input")
        if not self._startup_lock.acquire(blocking=False):
            raise RuntimeFailure("startup_busy")
        try:
            with self._registry:
                if not self._accepting:
                    raise RuntimeFailure("runtime_closed")
                if self._foreground_coordinator_claimed:
                    raise RuntimeFailure("foreground_coordinator_already_configured")
                self._foreground_coordinator_claimed = True
                self._startup_recover = startup_recover
        finally:
            self._startup_lock.release()

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
        """Close previous AI and manual work before enabling new admission.

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
                    self._require_open()
                    self._require_host()
                    if self._startup_recover is not None:
                        self._startup_active = (object(), document, get_ident())
                        token = self._startup_execution.set(self._startup_active)
                        try:
                            count = self._startup_recover(document, timeout)
                            if type(count) is not int or count not in (0, 1):
                                raise RuntimeFailure("checkpoint_unavailable")
                            recovered += count
                        except TimeoutError:
                            raise RuntimeFailure("startup_recovery_pending") from None
                        except RuntimeFailure:
                            raise
                        except Exception:
                            raise RuntimeFailure("checkpoint_unavailable") from None
                        finally:
                            self._startup_execution.reset(token)
                            self._startup_active = None
                    slot = self._slot(document, admit=True)
                    with slot.lock:
                        self._require_open()
                        self._require_host()
                        try:
                            pending = self.checkpoints.read(document)
                        except Exception as error:
                            raise RuntimeFailure(_checkpoint_failure(error)) from None
                        if self._foreground_busy(slot):
                            raise RuntimeFailure("startup_recovery_pending")
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

    def adopt_previous_foreground(self, identity: ForegroundIdentity,
                                  confirm_original: Callable[[ForegroundIdentity], None]) -> ForegroundHandle:
        """Adopt an exact persisted run only inside this host's startup callback.

        There is no invented stopped Future. The stored prior-host capability
        permits only original-result recovery and durable terminal closure.
        """
        if type(identity) is not ForegroundIdentity or not callable(confirm_original):
            raise RuntimeFailure("invalid_input")
        identity.__post_init__()
        active = self._startup_active
        if (self._previous_host is None or self._startup_done.is_set() or active is None
                or active != self._startup_execution.get()
                or active[1:] != (identity.document_id, get_ident())
                or not self._startup_lock.locked()):
            raise RuntimeFailure("startup_recovery_required")
        self._require_open()
        self._require_host()
        slot = self._slot(identity.document_id, admit=True)
        with slot.lock:
            self._require_open()
            self._require_host()
            if slot.catalog_token is not None or slot.start_token is not None:
                raise RuntimeFailure("document_busy")
            original = slot.foreground
            if original is not None:
                if original.previous_host is not self._previous_host or original.future is not None:
                    raise RuntimeFailure("document_busy")
                if original.permit.identity != identity:
                    raise RuntimeFailure("operation_conflict")
                if slot.entry is not None and slot.entry.foreground is not original.permit:
                    raise RuntimeFailure("document_busy")
            elif slot.entry is not None:
                raise RuntimeFailure("document_busy")
            self._confirm(confirm_original, identity)
            self._require_open()
            self._require_host()
            if slot.foreground is not original:
                raise RuntimeFailure("document_busy")
            if original is not None:
                return original.handle
            entry = _Foreground(ForegroundPermit(identity), error="foreground_interrupted",
                                previous_host=self._previous_host)
            entry.settled.set()
            entry.handle = ForegroundHandle(entry)
            slot.foreground = entry
            return entry.handle

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

    def _require_catalog_admission(self, slot):
        self._require_open()
        self._require_host()
        if not self._startup_done.is_set():
            raise RuntimeFailure("startup_pending")
        if slot.catalog_token is not None or slot.start_token is not None or self._foreground_busy(slot):
            raise RuntimeFailure("document_busy")

    @staticmethod
    def _foreground_busy(slot):
        return slot.foreground is not None and not slot.foreground.closed

    def _foreground_for(self, slot, permit):
        self._require_host()
        current = slot.foreground
        if (type(permit) is not ForegroundPermit or current is None
                or current.permit is not permit or current.closed):
            raise RuntimeFailure("writer_not_valid")
        return current

    def _require_foreground_stopped(self, current, *, allow_not_started=False):
        if not current.settled.is_set():
            raise RuntimeFailure("writer_not_stopped")
        if current.previous_host is not None:
            if current.previous_host is not self._previous_host or current.future is not None:
                raise RuntimeFailure("writer_not_stopped")
            try:
                current.previous_host.require_previous_stopped()
            except Exception:
                raise RuntimeFailure("writer_not_stopped") from None
            return
        if current.future is None:
            # Only this owner's known executor-submit failure may close without
            # a Future. It never authorizes SQL recovery or foreign adoption.
            if allow_not_started and current.error == "foreground_not_started":
                return
            raise RuntimeFailure("writer_not_stopped")
        if not current.future.done():
            raise RuntimeFailure("writer_not_stopped")

    def inspect_foreground_start(self, document_id: str, read: Callable[[], object]):
        """Track the synchronous original-run lookup through the same host drain.

        This grants no storage writer capability. A same-thread reentrant close
        must also see the in-flight read before releasing its Saver connection.
        """
        try:
            if type(document_id) is not str or str(UUID(document_id)) != document_id or not callable(read):
                raise ValueError()
        except (TypeError, ValueError):
            raise RuntimeFailure("invalid_input") from None
        slot = self._slot(document_id, admit=True)
        with slot.lock:
            self._require_catalog_admission(slot)
            if slot.entry is not None:
                raise RuntimeFailure("document_busy")
            slot.start_token = object()
            try:
                return read()
            finally:
                slot.start_token = None

    def start_foreground(self, identity: ForegroundIdentity,
                         work: Callable[[ForegroundPermit], object]) -> ForegroundHandle:
        if type(identity) is not ForegroundIdentity or not callable(work):
            raise RuntimeFailure("invalid_input")
        identity.__post_init__()
        slot = self._slot(identity.document_id, admit=True)
        with slot.lock:
            self._require_open()
            self._require_host()
            if not self._startup_done.is_set():
                raise RuntimeFailure("startup_pending")
            original = slot.foreground
            if original is not None and original.permit.identity.run_id == identity.run_id:
                if original.permit.identity != identity:
                    raise RuntimeFailure("operation_conflict")
                return original.handle
            if self._foreground_busy(slot) or slot.entry is not None or slot.catalog_token is not None or slot.start_token is not None:
                raise RuntimeFailure("document_busy")
            try:
                pending = self.checkpoints.read(identity.document_id)
            except Exception as error:
                raise RuntimeFailure(_checkpoint_failure(error)) from None
            if pending is not None:
                raise RuntimeFailure("document_busy")
            entry = _Foreground(ForegroundPermit(identity))
            entry.handle = ForegroundHandle(entry)
            slot.foreground = entry
            try:
                entry.future = self._foreground_pool.submit(self._run_foreground, slot, entry, work)
            except RuntimeError:
                entry.error = "foreground_not_started"
                entry.settled.set()
                return entry.handle
            entry.future.add_done_callback(lambda future: self._foreground_finished(slot, entry, future))
            return entry.handle

    def _run_foreground(self, slot, entry, work):
        # start_foreground retains this lock until the actual Future is attached.
        with slot.lock:
            self._foreground_for(slot, entry.permit)
        return work(entry.permit)

    def _foreground_finished(self, slot, entry, future):
        with slot.lock:
            if slot.foreground is not entry:
                entry.error = "obsolete_attempt"
            elif future.cancelled():
                entry.error = "foreground_not_started"
            elif future.exception() is not None:
                entry.error = "foreground_failed"
            entry.settled.set()  # Never claims the durable graph is closed.

    @staticmethod
    def _confirm(callback, *args):
        if not callable(callback):
            raise RuntimeFailure("invalid_input")
        try:
            if callback(*args) is not None:
                raise ValueError()
        except Exception:
            raise RuntimeFailure("checkpoint_unavailable") from None

    @staticmethod
    def _foreground_identity(permit, identity):
        try:
            if type(permit) is not ForegroundPermit or type(identity) is not AdmittedIdentity:
                raise ValueError()
            identity.validate()
            if (identity.origin != "ai" or identity.document_id != permit.identity.document_id
                    or identity.ai_run_id != permit.identity.run_id):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise RuntimeFailure("invalid_input") from None

    def execute_foreground(self, permit: ForegroundPermit, intent: BoundEdit,
                           confirm_bound: Callable[[AdmittedIdentity], None]) -> WriterHandle:
        if not isinstance(intent, BoundEdit):
            raise RuntimeFailure("invalid_input")
        self._foreground_identity(permit, intent.identity)
        slot = self._slot(intent.document_id)
        with slot.lock:
            current = self._foreground_for(slot, permit)
            self._require_open()
            if current.previous_host is not None or current.future is None or not current.future.running():
                raise RuntimeFailure("writer_not_valid")
            if permit.stop_event.is_set():
                raise RuntimeFailure("foreground_stopping")
            if slot.entry is not None:
                if slot.entry.foreground is permit and slot.entry.identity == intent.identity:
                    return slot.entry.attempt.handle
                if slot.entry.identity.operation_id == intent.operation_id:
                    raise RuntimeFailure("operation_conflict")
                raise RuntimeFailure("document_busy")
            self._confirm(confirm_bound, intent.identity)
            self._foreground_for(slot, permit)
            if permit.stop_event.is_set():
                raise RuntimeFailure("foreground_stopping")
            try:
                original = self.storage.lookup(intent.identity)
            except Exception as error:
                code = getattr(error, "code", None)
                raise RuntimeFailure(code if code in {"operation_conflict", "document_missing"}
                                     else "read_failed") from None
            attempt = _attempt("write")
            if original is not None:
                attempt.completion = Completion(original, False)
                attempt.settled.set()
                return attempt.handle
            entry = _Entry(intent.identity, attempt, foreground=permit)
            slot.entry = entry
            self._schedule(slot, entry, attempt, intent)
            return attempt.handle

    def recover_foreground(self, permit: ForegroundPermit, identity: AdmittedIdentity,
                           confirm_bound: Callable[[AdmittedIdentity], None], *, timeout=10) -> Completion:
        self._foreground_identity(permit, identity)
        slot = self._slot(identity.document_id)
        with slot.lock:
            current = self._foreground_for(slot, permit)
            self._require_foreground_stopped(current)
            entry = slot.entry
            if entry is not None:
                if entry.foreground is not permit or entry.identity != identity:
                    raise RuntimeFailure("operation_conflict")
                if not entry.attempt.settled.is_set():
                    raise RuntimeFailure("writer_not_stopped")
            self._confirm(confirm_bound, identity)
            if entry is None:
                entry = _Entry(identity, _attempt("recover"), foreground=permit)
                slot.entry = entry
            attempt = _attempt("recover")
            entry.attempt = attempt
            self._schedule(slot, entry, attempt)
        return attempt.handle.wait(timeout)

    def finish_foreground(self, permit: ForegroundPermit,
                          confirm_closed: Callable[[], None]) -> None:
        if type(permit) is not ForegroundPermit:
            raise RuntimeFailure("invalid_input")
        slot = self._slot(permit.identity.document_id)
        with slot.lock:
            current = self._foreground_for(slot, permit)
            self._require_foreground_stopped(current, allow_not_started=True)
            if slot.entry is not None:
                raise RuntimeFailure("writer_not_stopped")
            self._confirm(confirm_closed)
            self._foreground_for(slot, permit)
            self._require_foreground_stopped(current, allow_not_started=True)
            current.closed = True

    def create_document(self, request_key: UUID, title: str) -> str:
        if not isinstance(request_key, UUID) or type(title) is not str:
            raise RuntimeFailure("invalid_input")
        key = ("create", request_key)
        slot = self._slot(key, admit=True)
        with slot.lock:
            self._require_catalog_admission(slot)
            slot.catalog_token = object()
            context = self._catalog_execution.set((key, slot.catalog_token, get_ident()))
            try:
                return self.storage.create_document(request_key, title,
                    catalog_guard=lambda: self.require_catalog(key))
            finally:
                self._catalog_execution.reset(context)
                slot.catalog_token = None

    def update_catalog(self, document_id: str, metadata_version: int, *,
                       title: str | None = None, archived: bool | None = None) -> "CatalogRecord":
        try:
            if (type(document_id) is not str or str(UUID(document_id)) != document_id
                    or type(metadata_version) is not int or metadata_version < 1
                    or title is not None and type(title) is not str
                    or archived is not None and type(archived) is not bool
                    or title is None and archived is None):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise RuntimeFailure("invalid_input") from None
        slot = self._slot(document_id, admit=True)
        with slot.lock:
            self._require_catalog_admission(slot)
            if slot.entry is not None:
                raise RuntimeFailure("document_busy")
            slot.catalog_token = object()
            context = None
            try:
                try:
                    pending = self.checkpoints.read(document_id)
                except Exception as error:
                    raise RuntimeFailure(_checkpoint_failure(error)) from None
                if pending is not None:
                    raise RuntimeFailure("document_busy")
                # Track Saver I/O for close(), but issue SQL authority only
                # after the native root has proved idle.
                context = self._catalog_execution.set((document_id, slot.catalog_token, get_ident()))
                return self.storage.update_catalog(document_id, metadata_version,
                    title=title, archived=archived,
                    catalog_guard=lambda: self.require_catalog(document_id))
            finally:
                if context is not None:
                    self._catalog_execution.reset(context)
                slot.catalog_token = None

    def require_catalog(self, key: str | tuple[str, UUID]) -> None:
        """Authorize only this active synchronous call, including its final SQL check."""
        self._require_host()
        context = self._catalog_execution.get()
        if context is None or context[0] != key or context[2] != get_ident():
            raise RuntimeFailure("writer_not_valid")
        slot = self._slot(key)
        with slot.lock:
            if slot.catalog_token is not context[1]:
                raise RuntimeFailure("writer_not_valid")
        # Closing admission does not revoke already-admitted SQL. close() must
        # instead drain this slot through the storage call's COMMIT/exception.

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
            if slot.entry or self._foreground_busy(slot) or slot.catalog_token is not None or slot.start_token is not None:
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
        # Each recovery gets its own native Future and capability. An old copied
        # context cannot borrow a later attempt or survive its own Future ending.
        token = self._execution.set((entry.token, attempt.token, entry.identity.document_id,
                                     attempt.mode, get_ident()))
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
                    if entry.foreground is None:
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
                    or entry.attempt.mode != "write"
                    or context != (entry.token, entry.attempt.token, intent.document_id, "write", get_ident())
                    or entry.write_future is not entry.attempt.future
                    or entry.write_future is None or not entry.write_future.running()):
                raise RuntimeFailure("writer_not_valid")
            if entry.foreground is not None:
                self._foreground_for(slot, entry.foreground)

    def require_stopped(self, identity):
        self._require_host()
        context = self._execution.get()
        slot = self._slot(identity.document_id)
        with slot.lock:
            entry = slot.entry
            if (entry is None or entry.identity != identity
                    or entry.attempt.mode != "recover"
                    or context != (entry.token, entry.attempt.token, identity.document_id, "recover", get_ident())
                    or entry.attempt.future is None or not entry.attempt.future.running()
                    or entry.write_future is not None and not entry.write_future.done()):
                raise RuntimeFailure("writer_not_stopped")
            if entry.foreground is not None:
                current = self._foreground_for(slot, entry.foreground)
                self._require_foreground_stopped(current)
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
            if self._foreground_busy(slot):
                raise RuntimeFailure("document_busy")
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
            foreground = slot.foreground if self._foreground_busy(slot) else None
            if foreground is not None:
                running = (foreground.future is not None and not foreground.future.done()
                           or entry is not None and not entry.attempt.settled.is_set())
                return WriterStatus(entry.identity if entry is not None else None, running, True,
                                    foreground.error)
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
        attempts, foregrounds = [], []
        for slot in slots:
            if not slot.lock.acquire(timeout=max(0, deadline - monotonic())):
                return False  # Admission/checkpoint I/O is still using resources.
            try:
                if slot.catalog_token is not None or slot.start_token is not None:
                    return False  # A same-thread RLock reentry did not drain its call.
                if self._foreground_busy(slot):
                    foregrounds.append(slot.foreground)
                    if slot.foreground.future is None or not slot.foreground.future.done():
                        slot.foreground.permit.stop_event.set()
                entry = slot.entry
                if entry and entry.attempt.future:
                    attempts.append(entry.attempt)
            finally:
                slot.lock.release()
        # Graceful shutdown drains admitted work. This is not the user's
        # cancel-edit action and does not invent a failure for queued writes.
        futures = [attempt.future for attempt in attempts]
        futures.extend(entry.future for entry in foregrounds if entry.future is not None)
        _, running = wait(futures,
                          timeout=max(0, deadline - monotonic()))
        if running:
            return False
        for attempt in attempts:
            if not attempt.settled.wait(max(0, deadline - monotonic())):
                return False  # Future.done can precede checkpoint cleanup.
        for entry in foregrounds:
            if not entry.settled.wait(max(0, deadline - monotonic())) or not entry.closed:
                return False  # The actual run ending is not native checkpoint closure.
        self._foreground_pool.shutdown(wait=True)
        self._pool.shutdown(wait=True)
        return True
