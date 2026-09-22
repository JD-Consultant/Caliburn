"""App-owned lifecycle seam for existing document-scoped background work."""

from threading import Lock

from .background_admission import BackgroundAdmissions
from .background_availability import availability_notice
from .background_diagnostics import record_background_failure
from .background_dispatch import BackgroundDispatcher
from .background_memory_app import build_background_memory_workflow
from .background_memory_limits import FORMAL_BACKGROUND_MEMORY_LIMITS


_CATALOG_SCAN_FAILED = "background_catalog_scan_failed"
_DOCUMENT_WAKE_FAILED = "background_document_wake_failed"


class BackgroundCoordinator:
    def __init__(
        self,
        *,
        owner,
        engine,
        service,
        store,
        checkpointer,
        memory_engine,
        case_model,
        understanding_model,
        limits=FORMAL_BACKGROUND_MEMORY_LIMITS,
    ):
        self._owner = owner
        self._service = service
        self._store = store
        self._checkpointer = checkpointer
        self._memory_engine = memory_engine
        self._case_model = case_model
        self._understanding_model = understanding_model
        self._limits = limits
        self._admissions = BackgroundAdmissions(engine)
        self._dispatchers = {}
        self._lock = Lock()

    def _dispatcher(self, document_id: str):
        with self._lock:
            existing = self._dispatchers.get(document_id)
            if existing is not None:
                return existing
            workflow = build_background_memory_workflow(
                service=self._service,
                document_id=document_id,
                store=self._store,
                checkpointer=self._checkpointer,
                memory_engine=self._memory_engine,
                case_model=self._case_model,
                understanding_model=self._understanding_model,
                limits=self._limits,
            )
            dispatcher = BackgroundDispatcher(
                self._owner,
                self._admissions,
                self._service,
                document_id,
                workflow=workflow,
                publication=workflow.publication,
                max_windows=self._limits.case_max_windows,
                max_chars=self._limits.case_max_chars,
                context_chars=self._limits.case_context_chars,
            )
            self._dispatchers[document_id] = dispatcher
            return dispatcher

    def wake(self, document_id: str) -> str:
        return self._dispatcher(document_id).wake()

    def availability(self, document_id: str, published_head: object | None) -> str:
        return availability_notice(
            self._admissions,
            self._service,
            document_id,
            published_head,
        )

    def resume_pending(self) -> int:
        if not self._owner.ready:
            raise RuntimeError("background_recovery_before_runtime_ready")
        after, attempted = None, 0
        while True:
            try:
                documents = self._owner.storage.document_ids(after=after, limit=100)
            except Exception:
                record_background_failure(_CATALOG_SCAN_FAILED, attempted=attempted)
                return attempted
            for document_id in documents:
                attempted += 1
                try:
                    self.wake(document_id)
                except Exception:
                    record_background_failure(
                        _DOCUMENT_WAKE_FAILED,
                        attempted=attempted,
                        document_id=document_id,
                    )
            if len(documents) < 100:
                return attempted
            after = documents[-1]
