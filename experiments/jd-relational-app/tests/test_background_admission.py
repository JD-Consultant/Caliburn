"""Admission decisions for one durable layered Memory workflow."""

from types import SimpleNamespace

import pytest

from jd_relational.background_admission import (
    Admission,
    BackgroundAdmissionError,
    reconcile,
    require_handed_over,
)


class Workflow:
    """Only the durable observations the App is allowed to inspect."""

    def __init__(self, publication, *, values=None, pending=False, progress="covered"):
        snapshot = SimpleNamespace(values=values or {}, next=("run_b1",) if pending else ())
        self.graph = SimpleNamespace(get_state=lambda _config: snapshot)
        self.config = {"configurable": {"thread_id": "outer"}}
        self.publication = publication
        reader = SimpleNamespace(source_progress=lambda _reference, _previous: progress)
        self.case_workflow = SimpleNamespace(reader=reader)


class Publication:
    def __init__(self, processed_source=None):
        self.head = (None if processed_source is None else
                     SimpleNamespace(processed_source=processed_source))

    def current(self):
        return self.head


class Windows:
    def __init__(self, *, progress="covered", next_source=None):
        self.progress = progress
        self.next_source = next_source
        self.plans = []

    def source_progress(self, reference, previous, document_id):
        assert reference and previous and document_id == "document"
        return self.progress

    def plan_saved_batch(self, target_reference, document_id, *, after_reference=None):
        self.plans.append((target_reference, document_id, after_reference))
        return {"source_reference": self.next_source}


def state(source, status, *, error_code=None):
    return {
        "source_reference": source,
        "status": status,
        "error_code": error_code,
        "result": None,
    }


def test_a_document_that_has_never_started_admits_its_first_target():
    publication = Publication()
    require_handed_over(Workflow(publication), publication)


def test_a_completed_outer_job_must_be_covered_before_another_target_is_admitted():
    publication = Publication()
    workflow = Workflow(publication, values=state("batch-1", "completed"))

    with pytest.raises(BackgroundAdmissionError, match="^handover_incomplete$"):
        require_handed_over(workflow, publication)

    publication.head = SimpleNamespace(processed_source="batch-1")
    require_handed_over(workflow, publication)


def test_a_pending_outer_job_blocks_new_admission():
    publication = Publication()
    workflow = Workflow(
        publication,
        values=state("batch-1", "pending"),
        pending=True,
    )
    with pytest.raises(BackgroundAdmissionError, match="^workflow_pending$"):
        require_handed_over(workflow, publication)


def test_reconcile_resumes_the_exact_pending_outer_job():
    publication = Publication()
    workflow = Workflow(
        publication,
        values=state("batch-1", "pending"),
        pending=True,
    )
    admission = Admission(
        "document", "running", "target", "batch-1",
    )

    assert reconcile(
        admission,
        workflow=workflow,
        publication=publication,
        windows=Windows(),
        document_id="document",
    ) == "resume_workflow"


@pytest.mark.parametrize(
    ("workflow_state", "has_pending_node", "admission"),
    [
        (
            state("batch-1", "pending"),
            False,
            Admission("document", "queued", "target"),
        ),
        (
            state("batch-1", "completed"),
            True,
            Admission("document", "running", "target", "batch-1"),
        ),
        (
            state("batch-1", "blocked", error_code="bounded_stop"),
            True,
            Admission("document", "running", "target", "batch-1"),
        ),
    ],
)
def test_reconcile_rejects_a_checkpoint_whose_status_and_pending_node_disagree(
    workflow_state, has_pending_node, admission,
):
    publication = Publication()
    workflow = Workflow(
        publication,
        values=workflow_state,
        pending=has_pending_node,
    )
    with pytest.raises(
        BackgroundAdmissionError,
        match="^workflow_checkpoint_incompatible$",
    ):
        reconcile(
            admission,
            workflow=workflow,
            publication=publication,
            windows=Windows(),
            document_id="document",
        )


def test_reconcile_never_attaches_a_pending_job_to_a_different_batch():
    publication = Publication()
    workflow = Workflow(
        publication,
        values=state("other-batch", "pending"),
        pending=True,
    )
    admission = Admission(
        "document", "running", "target", "batch-1",
    )

    with pytest.raises(BackgroundAdmissionError, match="^workflow_source_mismatch$"):
        reconcile(
            admission,
            workflow=workflow,
            publication=publication,
            windows=Windows(),
            document_id="document",
        )


def test_reconcile_records_a_terminal_outer_block_for_the_same_batch():
    publication = Publication()
    workflow = Workflow(
        publication,
        values=state("batch-1", "blocked", error_code="stale_retry_limit_reached"),
    )
    admission = Admission(
        "document", "running", "target", "batch-1",
    )

    assert reconcile(
        admission,
        workflow=workflow,
        publication=publication,
        windows=Windows(),
        document_id="document",
    ) == "record_blocked"


def test_reconcile_uses_publication_to_advance_a_stale_running_row():
    publication = Publication("batch-2")
    workflow = Workflow(
        publication,
        values=state("batch-1", "completed"),
    )
    windows = Windows(progress="covered", next_source="batch-3")
    admission = Admission(
        "document", "running", "target", "batch-1",
    )

    assert reconcile(
        admission,
        workflow=workflow,
        publication=publication,
        windows=windows,
        document_id="document",
    ) == "next_batch"
    assert windows.plans == [("target", "document", "batch-2")]


def test_reconcile_waits_when_nothing_was_admitted():
    publication = Publication()
    workflow = Workflow(publication)
    assert reconcile(
        Admission("document"),
        workflow=workflow,
        publication=publication,
        windows=Windows(),
        document_id="document",
    ) == "wait"
