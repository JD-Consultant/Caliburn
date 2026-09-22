"""Whether a document may admit a new background batch, and what it owes now.

This owns exactly one fact nobody else keeps: which interview range was
admitted, which batch of it is in flight, why it stopped, and how many host
recoveries that work has spent. B1 and B2 progress stays with the Saver, and
published understanding with its one processed-source cursor stays with the
publication store. Neither is copied here. See ADR0076.

B1's own `require_new_source_after` compares a candidate range with B1's
previous range. That is the right rule for B1, but it cannot see whether that
previous range was ever handed over: two adjacent batches look legal even when
the first was never published. Starting the second overwrites the files B2 was
going to take, and the cursor then moves past detail nothing consolidated.
Scanning the Store for those orphans is explicitly not a remedy, so the check
belongs before the batch starts, here.

A row here proves admission, never execution: `running` does not mean the model
ran and `idle` does not mean a publication succeeded. Those are the Saver's
checkpoints and the publication's receipts, and `reconcile` reads them rather
than trusting this row. Nothing requires one transaction across the three.
"""

from dataclasses import dataclass, replace

import sqlalchemy as sa

from caliburn_memory import BackgroundMemoryWorkflow, PublicationStore

from .storage.schema import jd_memory_admission


STATUSES = ("idle", "queued", "running", "blocked")
# Every step the reconciliation below may ask for. There is no other outcome:
# an unrecognised durable combination is reported, never guessed at.
STEPS = ("wait", "resume_workflow", "start_workflow", "next_batch",
         "settle_idle", "record_blocked", "blocked")


class BackgroundAdmissionError(ValueError):
    """A bounded, safe reason admission cannot proceed right now."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class Admission:
    """One document's admission row; absent rows read as idle, never as None."""
    document_id: str
    status: str = "idle"
    target_reference: str | None = None
    source_reference: str | None = None
    error_code: str | None = None
    recovery_count: int = 0

    def __post_init__(self):
        if self.status not in STATUSES:
            raise BackgroundAdmissionError("invalid_admission_status")
        if type(self.recovery_count) is not int or self.recovery_count < 0:
            raise BackgroundAdmissionError("invalid_recovery_count")


def _observed_workflow(workflow: BackgroundMemoryWorkflow,
                       publication: PublicationStore):
    """Read only the outer checkpoint fields the App is allowed to reconcile."""
    try:
        if workflow.publication is not publication:
            raise BackgroundAdmissionError("invalid_admission_input")
        snapshot = workflow.graph.get_state(workflow.config)
    except BackgroundAdmissionError:
        raise
    except (AttributeError, TypeError, ValueError) as error:
        raise BackgroundAdmissionError("invalid_admission_input") from error
    values = snapshot.values
    if not values:
        if snapshot.next:
            raise BackgroundAdmissionError("workflow_checkpoint_incompatible")
        return snapshot, None
    if type(values) is not dict:
        raise BackgroundAdmissionError("workflow_checkpoint_incompatible")
    source = values.get("source_reference")
    status = values.get("status")
    error_code = values.get("error_code")
    if (type(source) is not str or not source
            or status not in {"pending", "completed", "blocked"}
            or (error_code is not None and type(error_code) is not str)
            or status == "blocked" and not error_code):
        raise BackgroundAdmissionError("workflow_checkpoint_incompatible")
    if (status == "pending") != bool(snapshot.next):
        raise BackgroundAdmissionError("workflow_checkpoint_incompatible")
    return snapshot, values


def require_handed_over(workflow: BackgroundMemoryWorkflow,
                        publication: PublicationStore) -> None:
    """Admit only after the preceding outer job reached publication."""
    snapshot, state = _observed_workflow(workflow, publication)
    if state is None:
        return
    if snapshot.next or state["status"] == "pending":
        raise BackgroundAdmissionError("workflow_pending")
    if state["status"] == "blocked":
        raise BackgroundAdmissionError("workflow_blocked")
    head = publication.current()
    if head is None or head.processed_source is None:
        raise BackgroundAdmissionError("handover_incomplete")
    try:
        progress = workflow.case_workflow.reader.source_progress(
            state["source_reference"], head.processed_source)
    except (AttributeError, TypeError, ValueError) as error:
        raise BackgroundAdmissionError("handover_incomplete") from error
    if progress != "covered":
        raise BackgroundAdmissionError("handover_incomplete")


class BackgroundAdmissions:
    """Read and write admission rows; this never creates or migrates the table."""

    def __init__(self, engine):
        self._engine = engine

    def _archived(self, document_id: str) -> bool:
        from .storage.schema import jd_document
        with self._engine.connect() as connection:
            return bool(connection.execute(sa.select(jd_document.c.archived).where(
                jd_document.c.id == document_id)).scalar())

    def read(self, document_id: str) -> Admission:
        with self._engine.connect() as connection:
            row = connection.execute(sa.select(jd_memory_admission).where(
                jd_memory_admission.c.document_id == document_id)).mappings().one_or_none()
        return Admission(document_id) if row is None else Admission(**row)

    def save(self, admission: Admission) -> None:
        """One row per document. The table's own checks reject an invalid mix."""
        values = {"status": admission.status, "target_reference": admission.target_reference,
                  "source_reference": admission.source_reference,
                  "error_code": admission.error_code, "recovery_count": admission.recovery_count}
        from sqlalchemy.dialects.postgresql import insert
        statement = insert(jd_memory_admission).values(
            document_id=admission.document_id, **values)
        with self._engine.begin() as connection:
            connection.execute(statement.on_conflict_do_update(
                index_elements=[jd_memory_admission.c.document_id], set_=values))

    def admit(self, document_id: str, *, target_reference: str,
              workflow: BackgroundMemoryWorkflow, publication: PublicationStore) -> Admission:
        """Fix a target for work that is genuinely free to start.

        The recovery allowance resets here because this establishes new work,
        not because the program was reopened.
        """
        current = self.read(document_id)
        if current.status != "idle":
            raise BackgroundAdmissionError("admission_in_flight")
        if self._archived(document_id):
            # Archiving stops new admission. Work already in flight keeps its
            # row and finishes; nothing here deletes state or resets an
            # allowance, so restoring the document resumes the same work.
            raise BackgroundAdmissionError("document_archived")
        require_handed_over(workflow, publication)
        admitted = replace(current, status="queued", target_reference=target_reference,
                           source_reference=None, error_code=None, recovery_count=0)
        self.save(admitted)
        return admitted

    def dispatch(self, document_id: str, *, source_reference: str) -> Admission:
        """Record the batch before B1 is invoked, never after."""
        current = self.read(document_id)
        if current.status not in {"queued", "running"} or current.target_reference is None:
            raise BackgroundAdmissionError("no_admitted_target")
        running = replace(current, status="running", source_reference=source_reference,
                          error_code=None)
        self.save(running)
        return running

    def advance(self, document_id: str) -> Admission:
        """This batch is published; the target keeps its remaining tail."""
        current = self.read(document_id)
        if current.target_reference is None:
            raise BackgroundAdmissionError("no_admitted_target")
        queued = replace(current, status="queued", source_reference=None, error_code=None)
        self.save(queued)
        return queued

    def settle(self, document_id: str) -> Admission:
        """The whole target is covered. Only completing it clears the count."""
        done = Admission(document_id)
        self.save(done)
        return done

    def block(self, document_id: str, *, error_code: str) -> Admission:
        """Stop with a named reason, keeping the work exactly where it is."""
        if not error_code or not isinstance(error_code, str) or len(error_code) > 64:
            raise BackgroundAdmissionError("invalid_error_code")
        current = self.read(document_id)
        blocked = replace(current, status="blocked", error_code=error_code)
        self.save(blocked)
        return blocked

    def recovered(self, document_id: str) -> Admission:
        """One more host recovery spent on this same work; never reset on reopen."""
        current = self.read(document_id)
        counted = replace(current, recovery_count=current.recovery_count + 1)
        self.save(counted)
        return counted


def reconcile(admission: Admission, *, workflow: BackgroundMemoryWorkflow,
              publication: PublicationStore,
              windows, document_id: str) -> str:
    """What this document owes now, read from every durable owner, in order.

    The admission row says what was admitted; it is never taken as proof that
    the model ran or that a publication succeeded. An unfinished job is always
    continued before anything new is considered, and a batch that publication
    already names is recognised as handed over even when this row has not
    caught up, which is why a stale row never causes a second consolidation.
    """
    if admission.status == "blocked":
        return "blocked"
    snapshot, state = _observed_workflow(workflow, publication)
    batch = admission.source_reference
    if snapshot.next:
        if (state is None or state["status"] != "pending"
                or admission.status != "running"
                or batch is None
                or state["source_reference"] != batch):
            raise BackgroundAdmissionError("workflow_source_mismatch")
        return "resume_workflow"
    if admission.target_reference is None:
        if state is not None and state["status"] == "pending":
            raise BackgroundAdmissionError("workflow_checkpoint_incompatible")
        return "wait"
    if batch is None:
        return "next_batch"

    head = publication.current()
    published = head.processed_source if head is not None else None
    if published is not None:
        try:
            progress = windows.source_progress(batch, published, document_id)
        except (AttributeError, TypeError, ValueError) as error:
            raise BackgroundAdmissionError("workflow_publication_mismatch") from error
        if progress == "covered":
            remaining = windows.plan_saved_batch(
                admission.target_reference, document_id, after_reference=published)
            return ("next_batch" if remaining["source_reference"] is not None
                    else "settle_idle")
        if progress != "next":
            raise BackgroundAdmissionError("workflow_publication_mismatch")

    if state is None:
        return "start_workflow"
    if state["source_reference"] == batch:
        if state["status"] == "blocked":
            return "record_blocked"
        if state["status"] == "completed":
            raise BackgroundAdmissionError("workflow_publication_missing")
        raise BackgroundAdmissionError("workflow_checkpoint_incompatible")
    if state["status"] == "completed" and published is not None:
        return "start_workflow"
    raise BackgroundAdmissionError("workflow_source_mismatch")
