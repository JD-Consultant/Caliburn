"""Background work continued by a real new Windows process, on real PostgreSQL.

Every case here is two OS processes: one builds durable state up to a named
stop point and exits, another starts cold and finds the same job. Nothing is
handed over in memory -- not a workflow, not a connection, not a checkpoint
object -- so what the second process knows, it read from PostgreSQL.

What each recovery is allowed to spend is asserted, because "it finished" is
not the claim. A saved model result is progress, and a committed publication is
committed: neither may be bought again.

Run `scripts/init_test_runtime.py` and `scripts/init_test_memory.py` first.
This file never sets up, clears or drops anything.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest

APP = Path(__file__).resolve().parents[1]
PROBE = APP / "tests" / "support" / "background_recovery_probe.py"
RESEARCH = APP.parents[1] / ".research-tmp"

pytestmark = [
    pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
                       reason="explicit isolated PostgreSQL test opt-in required"),
    pytest.mark.skipif(sys.platform != "win32", reason="new Windows process evidence"),
]


def run(mode, target, stop):
    done = subprocess.run(
        [sys.executable, str(PROBE), mode, str(target), "--stop", stop],
        cwd=APP, capture_output=True, text=True, errors="replace",
        env={**os.environ, "JD_RELATIONAL_TEST_DB": "1", "PYTHONUTF8": "1"})
    assert done.returncode == 0, done.stderr.strip()[-1000:]
    return json.loads((target / f"{mode}.json").read_text(encoding="utf-8"))


@pytest.fixture
def recovered():
    """Stage one stop point, then continue it from a genuinely new process."""
    def go(stop):
        target = RESEARCH / ("jd-b-recovery-" + uuid4().hex)
        staged = run("stage", target, stop)
        resumed = run("resume", target, stop)
        assert resumed["pid"] != staged["pid"] != os.getpid()
        return staged, resumed
    return go


def _finished(staged, resumed):
    """The staged batch is published exactly once and is no longer owed."""
    assert resumed["same_target_as_staged"] is True, "a new process invented a new target"
    assert resumed["published_covers_staged_batch"] is True
    assert resumed["published_revision"] == 1, "the batch was published more than once"
    assert resumed["admission_batch"] is None and resumed["admission_status"] == "queued"
    assert resumed["admission_target"] == staged["target_reference"]
    assert resumed["admission_recoveries"] == 0, "recovery allowance is not spent by reopening"


def test_a_saved_b1_model_result_is_not_bought_again(recovered):
    """B1 stopped after the model answered: resuming it costs no model call."""
    staged, resumed = recovered("b1_model_saved")
    assert staged["b1_pending"] is True and staged["published_revision"] is None
    assert staged["model_requests"] == 1, "the stage really reached the model once"
    assert resumed["decisions"][0] == "resume_extraction"
    assert resumed["model_requests_per_step"][0] == 0, "B1 re-called the model after a save"
    assert resumed["decisions"][1] == "consolidate"
    assert resumed["model_requests_per_step"][1] > 0, "B2 really ran in the new process"
    _finished(staged, resumed)


def test_a_finished_b1_batch_is_handed_to_b2_by_the_new_process(recovered):
    """B1 done, B2 not started: the new process makes the handover, once."""
    staged, resumed = recovered("b1_done")
    assert staged["b1_pending"] is False and staged["published_revision"] is None
    assert resumed["decisions"] == ["consolidate"] and resumed["steps"] == ["consolidate"]
    assert resumed["model_requests_per_step"] == [resumed["model_requests_in_this_process"]]
    assert resumed["model_requests_in_this_process"] > 0, "B2 has to run somewhere"
    _finished(staged, resumed)


def test_a_pending_b2_attempt_is_resumed_not_consolidated_again(recovered):
    """The saved attempt is progress; a new process never re-consolidates it."""
    staged, resumed = recovered("b2_pending")
    assert staged["published_revision"] is None
    assert staged["model_requests"] > 1, "the attempt really reached the model"
    assert resumed["decisions"] == ["resume_consolidation"]
    assert resumed["model_requests_in_this_process"] == 0
    _finished(staged, resumed)


def test_a_publication_whose_reply_was_lost_is_recognised_not_repeated(recovered):
    """Committed and unanswered is still committed, to a process that never saw it."""
    staged, resumed = recovered("b2_published_reply_lost")
    assert staged["published_revision"] == 1, "the stage really committed before losing the reply"
    assert "reply loss" in (staged["failure"] or "")
    assert resumed["opening"]["published_revision"] == 1, "the new process reads the commit"
    assert resumed["model_requests_in_this_process"] == 0, "a committed publication was repeated"
    assert resumed["published_revision"] == 1
    _finished(staged, resumed)
