"""Stage and recover one layered background job in separate Windows processes."""

import argparse
from concurrent.futures import Future
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

import sqlalchemy as sa
from caliburn_memory import PublicationStore
from jd_relational.background_admission import BackgroundAdmissions
from jd_relational.background_dispatch import BackgroundDispatcher
from langchain_core.messages import AIMessage

from support.layered_background_support import opened_layered
from test_background_admission_postgres import catalogued
from test_extraction_postgres import interviewed
from test_interview_window_source import asked, settled


STOPS = ("b2_transport_failure", "publication_reply_lost")
DATABASE_URL = sa.URL.create(
    "postgresql+psycopg",
    username="jd_test",
    password="jd-local-test-only",
    host="127.0.0.1",
    port=55436,
    database="caliburn_jd_relational_test",
)


def directory(value):
    target = Path(value).resolve()
    if (target.parent != ROOT / ".research-tmp"
            or re.fullmatch(r"jd-layered-recovery-[0-9a-f]{32}", target.name) is None):
        raise ValueError("invalid_probe_directory")
    return target


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class DirectWorker:
    def __init__(self):
        self.futures = []

    def admit_background(self, document_id, work):
        future = Future()
        try:
            future.set_result(work())
        except Exception as error:
            future.set_exception(error)
        self.futures.append(future)
        return future


def requested(native):
    return settled(
        native,
        [*asked("process-request"), AIMessage(id="process-answer", content="回" * 1250)],
        text="問" * 1250,
    )


def dispatcher(engine, document, resources):
    worker = DirectWorker()
    value = BackgroundDispatcher(
        worker,
        BackgroundAdmissions(engine),
        resources["windows"],
        document,
        workflow=resources["workflow"],
        publication=resources["publication"],
        max_windows=2,
        max_chars=24000,
    )
    return value, worker


def observed(engine, document, resources):
    snapshot = resources["workflow"].graph.get_state(resources["workflow"].config)
    head = resources["publication"].current()
    row = BackgroundAdmissions(engine).read(document)
    return {
        "workflow_status": (snapshot.values or {}).get("status"),
        "workflow_pending": bool(snapshot.next),
        "workflow_source": (snapshot.values or {}).get("source_reference"),
        "published_revision": head.revision if head else None,
        "published_source": head.processed_source if head else None,
        "admission_status": row.status,
        "admission_target": row.target_reference,
        "admission_source": row.source_reference,
        "case_requests": len(resources["case_model"].requests),
        "understanding_requests": len(resources["understanding_model"].requests),
    }


def stage(target, stop):
    dataset, document = str(uuid4()), str(uuid4())
    target.mkdir(exist_ok=False)
    write(target / "identity.json", {
        "dataset_id": dataset,
        "document_id": document,
        "stop": stop,
    })
    engine = sa.create_engine(DATABASE_URL, hide_parameters=True,
                              connect_args={"connect_timeout": 5})
    try:
        catalogued(engine, document)
        with opened_layered(
            dataset,
            document,
            b2_fails_first=stop == "b2_transport_failure",
        ) as resources:
            interviewed(resources["native"], 3)
            requested(resources["native"])
            built, worker = dispatcher(engine, document, resources)
            original = PublicationStore.publish
            lost = []
            if stop == "publication_reply_lost":
                def commit_then_lose(self, request):
                    head = original(self, request)
                    if not lost:
                        lost.append(head)
                        raise ConnectionError("synthetic publication reply loss")
                    return head
                PublicationStore.publish = commit_then_lose
            try:
                decision = built.wake()
                failure = worker.futures[0].exception()
            finally:
                PublicationStore.publish = original
            if not isinstance(failure, ConnectionError):
                raise AssertionError("the named stop point did not interrupt the workflow")
            write(target / "stage.json", {
                "pid": os.getpid(),
                "decision": decision,
                "failure": str(failure),
                **observed(engine, document, resources),
            })
    finally:
        engine.dispose()


def resume(target, stop):
    identity = json.loads((target / "identity.json").read_text(encoding="utf-8"))
    before = json.loads((target / "stage.json").read_text(encoding="utf-8"))
    if identity["stop"] != stop or before["pid"] == os.getpid():
        raise AssertionError("resume did not open the named job in a new process")
    dataset, document = identity["dataset_id"], identity["document_id"]
    engine = sa.create_engine(DATABASE_URL, hide_parameters=True,
                              connect_args={"connect_timeout": 5})
    try:
        with opened_layered(dataset, document) as resources:
            opening_admission = BackgroundAdmissions(engine).read(document)
            same_target = before["admission_target"] == opening_admission.target_reference
            built, worker = dispatcher(engine, document, resources)
            decision = built.wake()
            failure = worker.futures[0].exception()
            if failure is not None:
                raise failure
            write(target / "resume.json", {
                "pid": os.getpid(),
                "decision": decision,
                "staged_pid": before["pid"],
                "same_target": same_target,
                **observed(engine, document, resources),
            })
    finally:
        engine.dispose()


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
        print(
            f"layered_background_recovery_probe_failed: {type(error).__name__}: {error}",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(1)
