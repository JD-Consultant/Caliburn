"""Shutdown order on a real host: drain the batch, then close its resources.

A background batch reads the real Store and writes the real admission row, so
closing those connections while it runs would fail work that had already been
admitted. This pins the order the plan asks for -- stop new admission, wait for
registered work to actually exit, then close Store, Saver and engine -- against
a real PostgreSQL host rather than a description of one.

A process may bootstrap exactly one host, so this whole lifecycle is one test:
startup gating, the drain, and admission being closed afterwards.
"""
import os
from threading import Event, Thread
from uuid import uuid4

import pytest

from jd_relational.background_admission import BackgroundAdmissions
from jd_relational.host_runtime import open_manual_host
from jd_relational.inspection_model import build_inspection_consultant_node
from jd_relational.manual_runtime import RuntimeFailure

from test_background_admission_postgres import catalogued


pytestmark = pytest.mark.skipif(os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required")
DATABASE_URL = "postgresql+psycopg://jd_test:jd-local-test-only@127.0.0.1:55436/caliburn_jd_relational_test"
SCHEMA = "jd_host_test"


def test_a_real_host_gates_admits_drains_and_then_closes_its_resources():
    """One background lifecycle end to end, in the order shutdown must take."""
    host = open_manual_host(str(uuid4()), DATABASE_URL, checkpoint_schema=SCHEMA,
                            consultant=build_inspection_consultant_node())
    try:
        document = catalogued(host.engine, str(uuid4()))
        admissions = BackgroundAdmissions(host.engine)

        # Startup recovery decides what original work continues, so a new batch
        # cannot race the very job that recovery would have resumed.
        with pytest.raises(RuntimeFailure, match="^startup_pending$"):
            host.runtime.admit_background(document, lambda: None)
        host.runtime.finish_startup(timeout=10)

        release, started, outcome = Event(), Event(), {}

        def batch():
            started.set()
            assert release.wait(10)
            # Both resources must still be usable: this is admitted work, not
            # work that may be cut off because a shutdown started meanwhile.
            list(host.store.search(("q019-memory", document, "interviews")))
            admissions.save(admissions.read(document))
            outcome["ok"] = True
            return "done"

        future = host.runtime.admit_background(document, batch)
        assert started.wait(10)
        closing = {}
        thread = Thread(target=lambda: closing.setdefault("result", host.close(timeout=10)))
        thread.start()
        release.set()
        thread.join(15)
        assert not thread.is_alive() and closing["result"] is True
        assert future.result(0) == "done" and outcome == {"ok": True}
        assert host.store_connection.closed and host.saver_connection.closed
        # Admission closed first, so nothing could have joined that drain.
        with pytest.raises(RuntimeFailure, match="^runtime_closed$"):
            host.runtime.admit_background(document, lambda: None)
    finally:
        host.close(timeout=10)
