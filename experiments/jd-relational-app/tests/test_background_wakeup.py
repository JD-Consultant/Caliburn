"""Where ordinary turn completion wakes background work.

An ordinary turn wakes only after it settles. A turn that could not be closed
wakes nothing, because the background must never be pointed at a turn whose
own ending is still unknown. A wake that fails is the background's own problem:
it must not change what the employee's turn did. Low-level startup recovery
does not wake; after Runtime readiness, startup resume belongs to the managed
App/coordinator.
"""
import logging
from uuid import uuid4

import pytest

from jd_relational.ai_checkpoints import AiRunCheckpoints
from jd_relational.ai_runtime import AiRuntime, AiRuntimeError

from test_ai_runtime import HEAD, make_runtime  # noqa: F401
from test_ai_restart import saved_turn


class Woken:
    """Records the documents the runtime asked the background to look at."""

    def __init__(self, fail=False):
        self.documents = []
        self._fail = fail

    def __call__(self, document_id):
        self.documents.append(document_id)
        if self._fail:
            raise RuntimeError("synthetic background failure")


def test_a_settled_turn_wakes_the_background_for_its_own_document(make_runtime):
    """One safe ending, one wake, naming the document that just finished."""
    make, _ = make_runtime
    woken = Woken()
    runtime, _, calls = make(background=woken)
    document, run = str(uuid4()), str(uuid4())
    result = runtime.start(document, run, "第一輪原話", expected_revision_id=HEAD).wait(5)
    assert result.status == "completed" and len(calls) == 1
    assert woken.documents == [document]


def test_a_turn_that_could_not_be_closed_wakes_nothing(make_runtime, monkeypatch):
    """An unknown ending is not something to point the background at."""
    make, _ = make_runtime
    woken = Woken()
    runtime, _, _ = make(background=woken)

    def refuse(*args, **kwargs):
        raise OSError("synthetic close failure")

    monkeypatch.setattr(AiRunCheckpoints, "close", refuse)
    handle = runtime.start(str(uuid4()), str(uuid4()), "第一輪原話", expected_revision_id=HEAD)
    with pytest.raises(AiRuntimeError, match="^run_recovery_required$"):
        handle.wait(5)
    assert woken.documents == []
    # Leave the turn settled: an explicit reconciliation is what ends it, and
    # it is also the point at which the background finally hears about it.
    monkeypatch.undo()
    assert handle.recover().status in {"completed", "failed"}
    assert woken.documents, "the recovered ending is what the background gets"


def test_a_failing_wake_is_diagnosed_without_changing_what_the_turn_did(
        make_runtime, caplog):
    """Background trouble is recorded by the background, not by the employee."""
    make, _ = make_runtime
    woken = Woken(fail=True)
    runtime, graph, _ = make(background=woken)
    document, run = str(uuid4()), str(uuid4())
    with caplog.at_level(logging.WARNING, logger="caliburn.jd.background"):
        result = runtime.start(
            document, run, "第一輪原話", expected_revision_id=HEAD,
        ).wait(5)
    assert result.status == "completed" and result.input_saved
    assert woken.documents == [document]
    saved = graph.get_state({"configurable": {"thread_id": document}}).values["messages"]
    assert saved and runtime.lookup(document, run).wait() == result
    records = [record for record in caplog.records
               if record.name == "caliburn.jd.background"]
    assert len(records) == 1
    record = records[0]
    assert record.getMessage() == "background_turn_wake_failed"
    assert record.event_code == "background_turn_wake_failed"
    assert record.document_id == document
    assert record.exc_info is None
    assert "synthetic background failure" not in caplog.text


def test_low_level_startup_recovery_does_not_wake_before_runtime_is_ready():
    woken = Woken()
    runtime, _, *_ = saved_turn(background=woken)
    assert runtime.owner.finish_startup() == 1
    assert runtime.owner.ready
    assert woken.documents == []


def test_a_runtime_without_a_background_entry_still_settles(make_runtime):
    """The background is optional wiring, not a requirement of a turn."""
    make, _ = make_runtime
    runtime, _, _ = make()
    document = str(uuid4())
    assert runtime.start(document, str(uuid4()), "第一輪原話",
                         expected_revision_id=HEAD).wait(5).status == "completed"


def test_an_uncallable_background_entry_is_refused_at_assembly(make_runtime):
    """Bad wiring fails where it is assembled, not inside an employee's turn."""
    make, _ = make_runtime
    with pytest.raises(AiRuntimeError, match="^invalid_ai_runtime$"):
        make(background="not callable")
