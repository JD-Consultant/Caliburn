"""Background work recovered by a genuinely new Windows process, on real PG.

Two runs of this file are two OS processes. The first stages durable state up
to one named stop point and exits; the second opens the same database with
nothing inherited -- no Python object, no connection, no workflow -- finds the
original job and finishes it. What the second process is allowed to spend is
asserted by the caller: the model requests it makes, the publications it
creates, and whose work it turns out to be.

Resources are built exactly as the verified PG tests build them, by importing
those helpers rather than restating them. The only substitution is the OpenAI
HTTP transport, answered in process; no credential, no provider network, no
paid call. This helper never creates, clears or drops a table.

Usage:
  background_recovery_probe.py stage  <directory> --stop <point>
  background_recovery_probe.py resume <directory> --stop <point>
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from uuid import uuid4

APP = Path(__file__).resolve().parents[2]
ROOT = APP.parents[1]
sys.path.insert(0, str(APP / "src"))
sys.path.insert(0, str(APP / "tests"))

STOPS = ("b1_model_saved", "b1_done", "b2_pending", "b2_published_reply_lost")


def directory(value):
    target = Path(value).resolve()
    if (target.parent != ROOT / ".research-tmp"
            or not re.fullmatch(r"jd-b-recovery-[0-9a-f]{32}", target.name)):
        raise ValueError("invalid_probe_directory")
    return target


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


@contextmanager
def resources(dataset, document, *, faulty=False):
    """The same durable B1/B2/publication/admission resources the PG tests use."""
    import sqlalchemy as sa
    from langgraph.store.postgres import PostgresStore
    from jd_relational.background_admission import BackgroundAdmissions
    from test_consolidation_postgres import opened_b2, stages
    from test_extraction_postgres import FaultyStore
    from test_memory_core_postgres import SCHEMA

    engine = sa.create_engine(sa.URL.create(
        "postgresql+psycopg", username="jd_test", password="jd-local-test-only",
        host="127.0.0.1", port=55436, database="caliburn_jd_relational_test"),
        hide_parameters=True, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as check:
            assert check.execute(sa.text(
                "SELECT current_database(), current_user")).one() == (
                    "caliburn_jd_relational_test", "jd_test")
        with opened_b2(dataset, document,
                       store_class=FaultyStore if faulty else PostgresStore) as (
                native, windows, store, saver, store_conn, artifacts, publication):
            with stages(windows, document, store, saver, publication) as (b1, b2, sent, queue):
                yield dict(native=native, windows=windows, store=store, artifacts=artifacts,
                           publication=publication, b1=b1, b2=b2, sent=sent, queue=queue,
                           admissions=BackgroundAdmissions(engine), engine=engine,
                           schema=SCHEMA)
    finally:
        engine.dispose()


def identity(target):
    return json.loads((target / "identity.json").read_text(encoding="utf-8"))


def observed(state, *, admission, publication):
    head = publication.current()
    return {"admission_status": admission.status,
            "admission_target": admission.target_reference,
            "admission_batch": admission.source_reference,
            "admission_recoveries": admission.recovery_count,
            "b1_source_reference": (state.values or {}).get("source_reference"),
            "b1_pending": bool(state.next),
            "published_revision": head.revision if head else None,
            "published_source": head.processed_source if head else None}


def stage(target, stop):
    """Build durable state up to `stop`, record who owns it, then exit."""
    from test_background_admission_postgres import catalogued
    from test_consolidation_app import staged
    from test_extraction_postgres import interviewed

    dataset, document = str(uuid4()), str(uuid4())
    target.mkdir(exist_ok=False)
    write(target / "identity.json", {"dataset_id": dataset, "document_id": document, "stop": stop})
    faulty = stop in {"b1_model_saved", "b2_pending"}
    with resources(dataset, document, faulty=faulty) as r:
        catalogued(r["engine"], document)
        interviewed(r["native"], 3)
        target_reference = r["windows"].capture_window(
            document, **r["windows"].unprocessed_source(document))
        batch = r["windows"].plan_saved_batch(
            target_reference, document, max_windows=1)["source_reference"]
        # The batch is committed before B1 is invoked, never after.
        r["admissions"].admit(document, target_reference=target_reference,
                              extraction=r["b1"], publication=r["publication"])
        r["admissions"].dispatch(document, source_reference=batch)

        failure = None
        if stop == "b1_model_saved":
            r["store"].pass_writes = 0
            try:
                r["b1"].start(batch)
            except RuntimeError as error:
                failure = str(error)
            assert failure, "the stage must really stop inside B1"
        else:
            extracted = r["b1"].start(batch)
            summary = extracted["files"][0]["summary_path"]
            if stop != "b1_done":
                r["queue"].extend(staged(summary, body="中斷前已整併的理解。"))
            if stop == "b2_pending":
                r["store"].pass_writes = 0
                try:
                    r["b2"]().start()
                except RuntimeError as error:
                    failure = str(error)
                assert failure, "the stage must really stop inside B2"
            elif stop == "b2_published_reply_lost":
                from caliburn_memory import PublicationStore
                original, lost = PublicationStore.publish, []

                def commit_then_lose_the_reply(self, request):
                    result = original(self, request)
                    if not lost:
                        lost.append(True)
                        raise ConnectionError("synthetic reply loss after commit")
                    return result

                PublicationStore.publish = commit_then_lose_the_reply
                try:
                    r["b2"]().start()
                except ConnectionError as error:
                    failure = str(error)
                finally:
                    PublicationStore.publish = original
                assert failure, "the stage must really lose the reply after committing"

        write(target / "stage.json", {
            "pid": os.getpid(), "stop": stop, "at": datetime.now(timezone.utc).isoformat(),
            "dataset_id": dataset, "document_id": document,
            "target_reference": target_reference, "batch": batch,
            "model_requests": len(r["sent"]), "failure": failure,
            "queued_answers_left": len(r["queue"]),
            **observed(r["b1"].graph.get_state(r["b1"].config),
                       admission=r["admissions"].read(document), publication=r["publication"])})


def resume(target, stop):
    """A new process: find the original job from durable state and finish it."""
    from jd_relational.background_admission import reconcile
    from jd_relational.background_dispatch import BackgroundDispatcher
    from test_consolidation_app import staged

    saved = identity(target)
    assert saved["stop"] == stop, "resume must name the same stop point"
    dataset, document = saved["dataset_id"], saved["document_id"]
    before = json.loads((target / "stage.json").read_text(encoding="utf-8"))
    assert before["pid"] != os.getpid(), "this must be a different process"

    class Inline:
        """Runs the admitted batch here; the host's worker has its own tests."""

        def admit_background(self, document_id, work):
            from concurrent.futures import Future
            future = Future()
            future.set_result(work())
            return future

    with resources(dataset, document) as r:
        opening = observed(r["b1"].graph.get_state(r["b1"].config),
                           admission=r["admissions"].read(document), publication=r["publication"])
        dispatcher = BackgroundDispatcher(Inline(), r["admissions"], r["windows"], document,
                                          extraction=r["b1"], consolidation=r["b2"](),
                                          publication=r["publication"], max_windows=1)
        steps, decisions, costs = [], [], []
        for _ in range(3):
            decision = reconcile(r["admissions"].read(document), extraction=r["b1"],
                                 consolidation=r["b2"](), publication=r["publication"],
                                 windows=r["windows"], document_id=document)
            decisions.append(decision)
            if decision in {"wait", "blocked", "settle_idle"}:
                break
            if decision in {"consolidate", "resume_consolidation"} and not r["queue"]:
                # Only B2 needs a staged answer; B1 answers with its own default.
                files = (r["b1"].graph.get_state(r["b1"].config).values or {}).get("files")
                if files:
                    r["queue"].extend(staged(files[0]["summary_path"],
                                             body="新程序續作後整併的理解。"))
            spent = len(r["sent"])
            steps.append(dispatcher.wake())
            costs.append(len(r["sent"]) - spent)
            head = r["publication"].current()
            if (head is not None and head.processed_source == before["batch"]
                    and r["admissions"].read(document).source_reference != before["batch"]):
                break  # The original batch is published and no longer owed.

        head = r["publication"].current()
        write(target / "resume.json", {
            "pid": os.getpid(), "stop": stop, "at": datetime.now(timezone.utc).isoformat(),
            "staged_by_pid": before["pid"], "steps": steps, "decisions": decisions, "model_requests_per_step": costs,
            "model_requests_in_this_process": len(r["sent"]),
            "opening": opening,
            "same_target_as_staged": opening["admission_target"] == before["target_reference"],
            "published_covers_staged_batch": head is not None
                and head.processed_source == before["batch"],
            **observed(r["b1"].graph.get_state(r["b1"].config),
                       admission=r["admissions"].read(document), publication=r["publication"])})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("stage", "resume"))
    parser.add_argument("directory", type=directory)
    parser.add_argument("--stop", choices=STOPS, required=True)
    args = parser.parse_args()
    if sys.platform != "win32" or os.environ.get("JD_RELATIONAL_TEST_DB") != "1":
        raise ValueError("explicit_test_scope_required")
    (stage if args.mode == "stage" else resume)(args.directory, args.stop)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as error:
        print(f"background_recovery_probe_failed: {type(error).__name__}: {error}",
              file=sys.stderr, flush=True)
        sys.exit(1)
