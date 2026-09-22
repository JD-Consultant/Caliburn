"""Layered Memory work recovered by a genuinely new Windows process."""

import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest


APP = Path(__file__).resolve().parents[1]
PROBE = APP / "tests" / "support" / "layered_background_recovery_probe.py"
RESEARCH = APP.parents[1] / ".research-tmp"

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
        reason="explicit isolated PostgreSQL test opt-in required",
    ),
    pytest.mark.skipif(sys.platform != "win32", reason="new Windows process evidence"),
]


def run(mode, target, stop):
    completed = subprocess.run(
        [sys.executable, str(PROBE), mode, str(target), "--stop", stop],
        cwd=APP,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=60,
        env={**os.environ, "JD_RELATIONAL_TEST_DB": "1", "PYTHONUTF8": "1"},
    )
    assert completed.returncode == 0, completed.stderr.strip()[-2000:]
    return json.loads((target / f"{mode}.json").read_text(encoding="utf-8"))


@pytest.fixture
def recovered():
    def recover(stop):
        target = RESEARCH / ("jd-layered-recovery-" + uuid4().hex)
        staged = run("stage", target, stop)
        resumed = run("resume", target, stop)
        assert resumed["pid"] != staged["pid"] != os.getpid()
        return staged, resumed
    return recover


def assert_finished(staged, resumed):
    assert staged["workflow_pending"] is True
    assert resumed["decision"] == "resume_workflow"
    assert resumed["same_target"] is True
    assert resumed["workflow_status"] == "completed"
    assert resumed["workflow_pending"] is False
    assert resumed["published_revision"] == 1
    assert resumed["admission_status"] == "idle"
    assert resumed["admission_source"] is None
    assert resumed["case_requests"] == 0, "completed B1 was bought again"


def test_new_process_resumes_b2_after_completed_b1(recovered):
    staged, resumed = recovered("b2_transport_failure")
    assert staged["published_revision"] is None
    assert "b2 transport failure" in staged["failure"]
    assert resumed["understanding_requests"] > 0
    assert_finished(staged, resumed)


def test_new_process_reconciles_a_committed_publication_reply_loss(recovered):
    staged, resumed = recovered("publication_reply_lost")
    assert staged["published_revision"] == 1
    assert "publication reply loss" in staged["failure"]
    assert resumed["understanding_requests"] == 0, "completed B2 was bought again"
    assert_finished(staged, resumed)
