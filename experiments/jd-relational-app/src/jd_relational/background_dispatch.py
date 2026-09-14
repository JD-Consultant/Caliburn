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

from .background_admission import BackgroundAdmissionError, reconcile
from .conversation_sources import (
    MAX_CONTEXT_CHARACTERS, MAX_PLANNED_WINDOWS, MAX_WINDOW_CHARACTERS,
)


class BackgroundDispatcher:
    """One document's background decisions, over resources the App assembled."""

    def __init__(self, owner, admissions, windows, document_id, *, extraction, consolidation,
                 publication, max_windows: int = MAX_PLANNED_WINDOWS,
                 max_chars: int = MAX_WINDOW_CHARACTERS,
                 context_chars: int = MAX_CONTEXT_CHARACTERS):
        self._owner, self._admissions, self._windows = owner, admissions, windows
        self._document_id = document_id
        self._extraction, self._consolidation = extraction, consolidation
        self._publication = publication
        self._max_windows, self._max_chars = max_windows, max_chars
        self._context_chars = context_chars
        self._running = None

    def wake(self) -> str:
        """Decide, admit at most one bounded batch, and say what was decided.

        Waking again while a batch runs is not a second batch: the answer is
        that this document is busy. Waking on blocked work does not override
        the block, and waking with nothing asked for does not start anything.
        """
        if self._running is not None and not self._running.done():
            return "busy"
        step = reconcile(self._admissions.read(self._document_id),
                         extraction=self._extraction, consolidation=self._consolidation,
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
                               extraction=self._extraction, publication=self._publication)
        return "next_batch"

    def _plan(self, target_reference):
        return self._windows.plan_saved_batch(
            target_reference, self._document_id, after_reference=self._cursor(),
            max_chars=self._max_chars, context_chars=self._context_chars,
            max_windows=self._max_windows)

    def _perform(self, step):
        if step == "resume_extraction":
            return self._extraction.resume()
        if step == "resume_consolidation":
            return self._after_publication(self._consolidation.resume())
        if step == "consolidate":
            return self._after_publication(self._consolidation.start())
        if step == "start_batch":
            # The batch was committed before B1 was invoked and B1 never ran it.
            return self._extraction.start(
                self._admissions.read(self._document_id).source_reference)
        if step == "next_batch":
            return self._next_batch()
        if step == "settle_idle":
            return self._admissions.settle(self._document_id)
        raise BackgroundAdmissionError("unknown_background_step")

    def _next_batch(self):
        """Cut the target's next batch, record it, and only then invoke B1."""
        admission = self._admissions.read(self._document_id)
        batch = self._plan(admission.target_reference)
        if batch["source_reference"] is None:
            return self._admissions.settle(self._document_id)
        self._admissions.dispatch(self._document_id, source_reference=batch["source_reference"])
        return self._extraction.start(batch["source_reference"])

    def _after_publication(self, result):
        """Move admission on only from a publication that really happened.

        A consolidation that did not reach the head leaves the row exactly
        where it was, so the next wake sees the same work still owed rather
        than a target that quietly advanced.
        """
        admission = self._admissions.read(self._document_id)
        cursor = self._cursor()
        if cursor is None or cursor != admission.source_reference:
            return result
        if self._plan(admission.target_reference)["source_reference"] is None:
            self._admissions.settle(self._document_id)
        else:
            self._admissions.advance(self._document_id)
        return result
