"""One entry point for a document's background work; nothing here schedules.

Waking is cheap and repeatable. What may actually run is decided by durable
state -- the admission row, the Saver's pending jobs and the publication head
-- and never by how often something knocked. Each wake admits at most one
bounded batch to the host's own worker and returns; there is no loop, no queue
and nothing living between batches.

A new target requires a real saved consolidation request. The word-count
fallback of the verified dispatcher is deliberately not enabled here: the
employee's own notification is what decides when background work starts.
"""

from threading import Lock

from .background_admission import BackgroundAdmissionError, reconcile
from .background_memory_limits import FORMAL_BACKGROUND_MEMORY_LIMITS


class BackgroundDispatcher:
    """One document's background decisions, over resources the App assembled."""

    def __init__(self, owner, admissions, windows, document_id, *, workflow,
                 publication,
                 max_windows: int = FORMAL_BACKGROUND_MEMORY_LIMITS.case_max_windows,
                 max_chars: int = FORMAL_BACKGROUND_MEMORY_LIMITS.case_max_chars,
                 context_chars: int = FORMAL_BACKGROUND_MEMORY_LIMITS.case_context_chars):
        self._owner, self._admissions, self._windows = owner, admissions, windows
        self._document_id = document_id
        self._workflow = workflow
        self._publication = publication
        self._max_windows, self._max_chars = max_windows, max_chars
        self._context_chars = context_chars
        self._running = None
        self._wake_lock = Lock()

    def wake(self) -> str:
        """Decide, admit at most one bounded batch, and say what was decided.

        Waking again while a batch runs is not a second batch: the answer is
        that this document is busy. Waking on blocked work does not override
        the block, and waking with nothing asked for does not start anything.
        """
        with self._wake_lock:
            if self._running is not None and not self._running.done():
                return "busy"
            step = reconcile(self._admissions.read(self._document_id),
                             workflow=self._workflow,
                             publication=self._publication, windows=self._windows,
                             document_id=self._document_id)
            if step == "wait":
                step = self._admit_new_target()
            if step in {"wait", "blocked"}:
                return step
            self._running = self._owner.admit_background(
                self._document_id, lambda: self._perform(step))
            return step

    def _cursor(self):
        head = self._publication.current()
        return head.processed_source if head is not None else None

    def _admit_new_target(self) -> str:
        """Start new work only when a turn actually asked for consolidation."""
        cursor = self._cursor()
        if not self._windows.pending_windows(self._document_id, cursor):
            return "wait"
        bounds = self._windows.unprocessed_source(self._document_id, cursor)
        if bounds is None:
            return "wait"
        target = self._windows.capture_window(self._document_id, **bounds)
        self._admissions.admit(self._document_id, target_reference=target,
                               workflow=self._workflow, publication=self._publication)
        return "next_batch"

    def _plan(self, target_reference):
        return self._windows.plan_saved_batch(
            target_reference, self._document_id, after_reference=self._cursor(),
            max_chars=self._max_chars, context_chars=self._context_chars,
            max_windows=self._max_windows)

    def _perform(self, step):
        if step == "resume_workflow":
            return self._after_workflow(self._workflow.resume())
        if step == "start_workflow":
            source = self._admissions.read(self._document_id).source_reference
            return self._after_workflow(self._workflow.start(source))
        if step == "next_batch":
            return self._next_batch()
        if step == "settle_idle":
            return self._admissions.settle(self._document_id)
        if step == "record_blocked":
            return self._record_blocked()
        raise BackgroundAdmissionError("unknown_background_step")

    def _next_batch(self):
        """Cut the target's next batch, record it, and only then invoke B1."""
        admission = self._admissions.read(self._document_id)
        batch = self._plan(admission.target_reference)
        if batch["source_reference"] is None:
            return self._admissions.settle(self._document_id)
        self._admissions.dispatch(self._document_id, source_reference=batch["source_reference"])
        return self._after_workflow(self._workflow.start(batch["source_reference"]))

    def _record_blocked(self):
        state = self._workflow.graph.get_state(self._workflow.config).values
        admission = self._admissions.read(self._document_id)
        if (not state or state.get("status") != "blocked"
                or state.get("source_reference") != admission.source_reference
                or not state.get("error_code")):
            raise BackgroundAdmissionError("workflow_checkpoint_incompatible")
        return self._admissions.block(
            self._document_id, error_code=state["error_code"])

    def _after_workflow(self, result):
        """Move admission on only from a publication that really happened.

        A pending or failed workflow leaves the row exactly where it was, so
        the next wake resumes the same outer checkpoint. A bounded terminal
        block is copied to admission only after the outer graph records it.
        """
        if type(result) is not dict:
            raise BackgroundAdmissionError("workflow_result_incompatible")
        if result.get("status") == "blocked":
            error_code = result.get("error_code")
            if not error_code:
                raise BackgroundAdmissionError("workflow_result_incompatible")
            self._admissions.block(self._document_id, error_code=error_code)
            return result
        if result.get("status") != "completed":
            return result
        admission = self._admissions.read(self._document_id)
        cursor = self._cursor()
        if cursor is None or admission.source_reference is None:
            raise BackgroundAdmissionError("workflow_publication_missing")
        try:
            progress = self._windows.source_progress(
                admission.source_reference, cursor, self._document_id)
        except (AttributeError, TypeError, ValueError) as error:
            raise BackgroundAdmissionError("workflow_publication_mismatch") from error
        if progress != "covered":
            raise BackgroundAdmissionError("workflow_publication_missing")
        if self._plan(admission.target_reference)["source_reference"] is None:
            self._admissions.settle(self._document_id)
        else:
            self._admissions.advance(self._document_id)
        return result
