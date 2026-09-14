"""Independent READ ONLY check of what the browser journey really saved.

Opens its own REPEATABLE READ / READ ONLY connection to the journey's dedicated
database, separate from the App's. It never writes, never reaches a provider,
and only accepts a fresh jd-ui-gate-<hex> fixture. Field text is reported here
because this synthetic JD is fixed test data authored by the journey script.

Usage: db_readonly_probe.py <fixture directory> <restore|undo>
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

import sqlalchemy as sa

sys.path.insert(0, "S:/caliburn/experiments/jd-relational-app/src")
from jd_relational.storage import schema as db  # noqa: E402
from jd_relational.storage.rows import read_domain  # noqa: E402
from jd_relational.snapshots import snapshot_from_domain, snapshot_digest  # noqa: E402

target = Path(sys.argv[1]).resolve()
assert target.parent == Path("S:/caliburn/.research-tmp")
assert re.fullmatch(r"jd-ui-gate-[0-9a-f]{32}", target.name)
stage = sys.argv[2]
assert stage in {"restore", "undo"}

config = json.loads((target / "fixture.json").read_text(encoding="utf-8"))
database = "caliburn_jd_setup_test_" + target.name.removeprefix("jd-ui-gate-")
assert config["database"] == database and config["port"] == 55436

url = sa.URL.create("postgresql+psycopg", username="jd_test", password="jd-local-test-only",
                    host="127.0.0.1", port=55436, database=database)
engine = sa.create_engine(url, connect_args={"connect_timeout": 5})
report = {"stage": stage, "checked_at_utc": datetime.now(timezone.utc).isoformat(),
          "database": database, "port": 55436, "mode": "REPEATABLE READ / READ ONLY",
          "provider_calls": 0, "database_writes": 0}

with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
    with connection.begin():
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")
        assert connection.exec_driver_sql(
            "SELECT current_database(),current_user").one() == (database, "jd_test")

        documents = connection.execute(sa.select(db.jd_document)).mappings().all()
        assert len(documents) == 1, len(documents)
        document = documents[0]["id"]
        report.update(document_id=document, title=documents[0]["title"],
                      archived=documents[0]["archived"])

        head = connection.execute(sa.select(db.jd_head).where(
            db.jd_head.c.document_id == document)).mappings().one()
        revisions = connection.execute(sa.select(db.jd_revision).where(
            db.jd_revision.c.document_id == document).order_by(
            db.jd_revision.c.revision_number)).mappings().all()
        operations = connection.execute(sa.select(db.jd_operation).where(
            db.jd_operation.c.document_id == document).order_by(
            db.jd_operation.c.created_at)).mappings().all()

        current = read_domain(connection, document, str(head["current_revision_id"]))
        snapshot = snapshot_from_domain(current)
        assert snapshot == revisions[-1]["snapshot"]
        assert snapshot_digest(snapshot) == revisions[-1]["content_digest"]
        report.update(head_revision_number=head["revision_number"],
                      revision_count=len(revisions), operation_count=len(operations),
                      revision_origins=[row["origin"] for row in revisions],
                      operation_kinds=[row["receipt"].get("command_kind") for row in operations],
                      operation_statuses=[row["status"] for row in operations],
                      content_digest=snapshot_digest(snapshot),
                      current_equals_head_snapshot=True)

        profile = current["profile"]
        report.update(job_title=profile.get("job_title"), purpose=profile.get("purpose"))

        # The relational content the restore/undo was supposed to leave alone.
        report.update(task_count=len(current["tasks"]), duty_count=len(current["duties"]))

        if stage == "restore":
            assert head["revision_number"] == 4 and len(revisions) == 4, head["revision_number"]
            assert len(operations) == 3, len(operations)
            assert report["operation_kinds"][-1] == "restore_revision", report["operation_kinds"]
            assert all(row["status"] == "committed" for row in operations)
            # Restoring reproduces an earlier content exactly, as a NEW revision.
            assert revisions[3]["content_digest"] == revisions[1]["content_digest"]
            assert revisions[3]["revision_id"] != revisions[1]["revision_id"]
            assert revisions[3]["parent_revision_id"] == revisions[2]["revision_id"]
            # Nothing in history was rewritten or removed.
            assert revisions[2]["snapshot"] != revisions[3]["snapshot"]
            assert revisions[2]["snapshot"]["profile"]["purpose"], "revision 3 kept its purpose"
            assert profile.get("purpose") in (None, "")
            assert profile.get("job_title") == "資深設備維運工程師"
            report.update(restored_revision_reproduces_revision_2=True,
                          restore_added_a_new_revision=True,
                          replaced_revision_still_readable=True,
                          later_content_removed_from_current=True)
        else:
            assert report["operation_kinds"][-1] == "undo_ai_turn", report["operation_kinds"]
            ai = [row for row in operations if row["origin"] == "ai"]
            assert ai, "the journey needs a real AI turn to take back"
            run = ai[0]["ai_run_id"]
            assert run and all(row["ai_run_id"] == run for row in ai)
            undone = operations[-1]
            assert undone["origin"] == "manual" and undone["status"] == "committed"
            base = {row["base_revision_id"] for row in ai}
            starts = base - {row["result_revision_id"] for row in ai}
            assert len(starts) == 1
            before = starts.pop()
            restored_to = next(row for row in revisions if row["revision_id"] == before)
            assert revisions[-1]["content_digest"] == restored_to["content_digest"]
            assert revisions[-1]["revision_id"] != restored_to["revision_id"]
            report.update(ai_run_id=run, ai_operation_count=len(ai),
                          undo_reproduces_state_before_the_turn=True,
                          undo_added_a_new_revision=True)

        # Only JD moved: the conversation and memory the turn produced stay.
        checkpoints = connection.exec_driver_sql(
            "SELECT count(*) FROM jd_runtime.checkpoints").scalar_one()
        writes = connection.exec_driver_sql(
            "SELECT count(*) FROM jd_runtime.checkpoint_writes").scalar_one()
        store = connection.exec_driver_sql("SELECT count(*) FROM jd_runtime.store").scalar_one()
        report.update(conversation_checkpoints=checkpoints, conversation_writes=writes,
                      memory_store_rows=store)

engine.dispose()
(target / f"db-{stage}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
(Path(__file__).resolve().parent / f"db-{stage}.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False))
