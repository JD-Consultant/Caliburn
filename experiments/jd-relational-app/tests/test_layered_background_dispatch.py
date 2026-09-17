"""One cheap wake around one complete layered Memory workflow."""

from concurrent.futures import Future
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event, Lock
from types import SimpleNamespace

from jd_relational.background_admission import Admission
from jd_relational.background_dispatch import BackgroundDispatcher


class DirectWorker:
    def __init__(self):
        self.jobs = []

    def admit_background(self, document_id, work):
        self.jobs.append((document_id, work))
        future = Future()
        try:
            future.set_result(work())
        except Exception as error:
            future.set_exception(error)
        return future


class PendingWorker(DirectWorker):
    def admit_background(self, document_id, work):
        self.jobs.append((document_id, work))
        return Future()


class RacingWorker(PendingWorker):
    """Hold the first submission open while a concurrent wake tries to enter."""

    def __init__(self):
        super().__init__()
        self.first_submission = Event()
        self.second_submission = Event()
        self._calls_lock = Lock()

    def admit_background(self, document_id, work):
        with self._calls_lock:
            call = len(self.jobs) + 1
            self.jobs.append((document_id, work))
        if call == 1:
            self.first_submission.set()
            self.second_submission.wait(timeout=0.25)
        else:
            self.second_submission.set()
        return Future()


class Admissions:
    def __init__(self, document_id="document"):
        self.row = Admission(document_id)

    def read(self, document_id):
        assert document_id == self.row.document_id
        return self.row

    def admit(self, document_id, *, target_reference, workflow, publication):
        assert workflow.publication is publication
        self.row = replace(
            self.row,
            status="queued",
            target_reference=target_reference,
            source_reference=None,
            error_code=None,
            recovery_count=0,
        )
        return self.row

    def dispatch(self, document_id, *, source_reference):
        self.row = replace(
            self.row,
            status="running",
            source_reference=source_reference,
            error_code=None,
        )
        return self.row

    def advance(self, document_id):
        self.row = replace(
            self.row,
            status="queued",
            source_reference=None,
            error_code=None,
        )
        return self.row

    def settle(self, document_id):
        self.row = Admission(document_id)
        return self.row

    def block(self, document_id, *, error_code):
        self.row = replace(self.row, status="blocked", error_code=error_code)
        return self.row


class Publication:
    def __init__(self, processed_source=None):
        self.processed_source = processed_source

    def current(self):
        if self.processed_source is None:
            return None
        return SimpleNamespace(processed_source=self.processed_source)


class Windows:
    def __init__(self, batches=(), *, notified=False):
        self.batches = tuple(batches)
        self.notified = notified

    def pending_windows(self, document_id, cursor):
        return self.notified and bool(self.batches)

    def unprocessed_source(self, document_id, cursor):
        return {"first_run_id": "first", "last_run_id": "last"}

    def capture_window(self, document_id, **bounds):
        return "target"

    def source_progress(self, reference, previous, document_id):
        if reference == previous or (
            reference in self.batches and previous in self.batches
            and self.batches.index(previous) >= self.batches.index(reference)
        ):
            return "covered"
        return "next"

    def plan_saved_batch(self, target_reference, document_id, *, after_reference=None,
                         **_budgets):
        if after_reference is None:
            index = 0
        else:
            index = self.batches.index(after_reference) + 1
        return {
            "source_reference": self.batches[index] if index < len(self.batches) else None,
        }


class Workflow:
    def __init__(self, publication, *, status=None, source=None, pending=False,
                 blocked_code=None, fail=None):
        self.publication = publication
        self.status = status
        self.source = source
        self.pending = pending
        self.blocked_code = blocked_code
        self.fail = fail
        self.starts = []
        self.resumes = 0
        self.graph = SimpleNamespace(get_state=self._state)
        self.config = {"configurable": {"thread_id": "outer"}}

    def _state(self, _config):
        values = ({
            "source_reference": self.source,
            "status": self.status,
            "error_code": self.blocked_code,
            "result": None,
        } if self.status is not None else {})
        return SimpleNamespace(values=values, next=("run_b1",) if self.pending else ())

    def _finish(self):
        if self.fail is not None:
            raise self.fail
        if self.blocked_code is not None:
            self.status = "blocked"
            self.pending = False
            return self._state(self.config).values
        self.publication.processed_source = self.source
        self.status = "completed"
        self.pending = False
        return self._state(self.config).values

    def start(self, source_reference):
        self.starts.append(source_reference)
        self.source = source_reference
        self.status = "pending"
        return self._finish()

    def resume(self):
        self.resumes += 1
        return self._finish()


def dispatcher(*, batches=(), notified=False, workflow=None, worker=None,
               admissions=None, publication=None):
    publication = publication or Publication()
    workflow = workflow or Workflow(publication)
    worker = worker or DirectWorker()
    admissions = admissions or Admissions()
    windows = Windows(batches, notified=notified)
    built = BackgroundDispatcher(
        worker,
        admissions,
        windows,
        "document",
        workflow=workflow,
        publication=publication,
        max_windows=2,
    )
    return built, worker, admissions, windows, workflow, publication


def test_a_wake_without_a_saved_request_starts_nothing():
    built, worker, admissions, _, workflow, _ = dispatcher(batches=("batch-1",))

    assert built.wake() == "wait"
    assert worker.jobs == []
    assert workflow.starts == []
    assert admissions.read("document") == Admission("document")


def test_one_saved_request_runs_one_complete_layered_batch():
    built, worker, admissions, _, workflow, publication = dispatcher(
        batches=("batch-1",),
        notified=True,
    )

    assert built.wake() == "next_batch"
    assert workflow.starts == ["batch-1"]
    assert publication.processed_source == "batch-1"
    assert admissions.read("document") == Admission("document")
    assert len(worker.jobs) == 1


def test_repeated_wake_while_the_worker_is_live_never_cuts_a_second_batch():
    worker = PendingWorker()
    built, worker, admissions, _, workflow, _ = dispatcher(
        batches=("batch-1",),
        notified=True,
        worker=worker,
    )

    assert built.wake() == "next_batch"
    for _ in range(3):
        assert built.wake() == "busy"
    assert len(worker.jobs) == 1
    assert workflow.starts == []
    assert admissions.read("document").status == "queued"


def test_concurrent_wakes_on_one_dispatcher_submit_only_one_worker_job():
    worker = RacingWorker()
    built, worker, admissions, _, workflow, _ = dispatcher(
        batches=("batch-1",),
        notified=True,
        worker=worker,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(built.wake)
        assert worker.first_submission.wait(timeout=1)
        second = executor.submit(built.wake)
        decisions = {first.result(timeout=2), second.result(timeout=2)}

    assert decisions == {"next_batch", "busy"}
    assert len(worker.jobs) == 1
    assert workflow.starts == []
    assert admissions.read("document").status == "queued"


def test_a_pending_outer_checkpoint_is_resumed_not_restarted():
    publication = Publication()
    workflow = Workflow(
        publication,
        status="pending",
        source="batch-1",
        pending=True,
    )
    admissions = Admissions()
    admissions.row = Admission("document", "running", "target", "batch-1")
    built, _, admissions, _, workflow, publication = dispatcher(
        batches=("batch-1",),
        workflow=workflow,
        admissions=admissions,
        publication=publication,
    )

    assert built.wake() == "resume_workflow"
    assert workflow.resumes == 1 and workflow.starts == []
    assert publication.processed_source == "batch-1"
    assert admissions.read("document") == Admission("document")


def test_a_stale_running_row_uses_the_publication_cursor_to_take_the_tail():
    publication = Publication("batch-1")
    workflow = Workflow(publication, status="completed", source="batch-1")
    admissions = Admissions()
    admissions.row = Admission("document", "running", "target", "batch-1")
    built, _, admissions, _, workflow, publication = dispatcher(
        batches=("batch-1", "batch-2"),
        workflow=workflow,
        admissions=admissions,
        publication=publication,
    )

    assert built.wake() == "next_batch"
    assert workflow.starts == ["batch-2"]
    assert publication.processed_source == "batch-2"
    assert admissions.read("document") == Admission("document")


def test_a_terminal_workflow_block_is_persisted_in_the_admission_row():
    publication = Publication()
    workflow = Workflow(publication, blocked_code="case_rework_limit_reached")
    built, _, admissions, _, _, _ = dispatcher(
        batches=("batch-1",),
        notified=True,
        workflow=workflow,
        publication=publication,
    )

    assert built.wake() == "next_batch"
    row = admissions.read("document")
    assert row.status == "blocked"
    assert row.source_reference == "batch-1"
    assert row.error_code == "case_rework_limit_reached"
