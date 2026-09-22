"""Layered dispatcher on real Saver, Store, publication and admission tables."""

from concurrent.futures import Future
import os
from uuid import uuid4

import pytest

from caliburn_memory import PublicationStore
from jd_relational.background_admission import BackgroundAdmissions
from jd_relational.background_dispatch import BackgroundDispatcher

from support.layered_background_support import opened_layered
from test_background_admission_postgres import catalogued
from test_extraction_postgres import interviewed
from test_interview_window_source import asked, settled
from test_storage_postgres import engine  # noqa: F401
from langchain_core.messages import AIMessage


pytestmark = pytest.mark.skipif(
    os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required",
)


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
        [*asked("layered-request"), AIMessage(id="layered-answer", content="回" * 1250)],
        text="問" * 1250,
    )


def build_dispatch(engine, document, resources):
    worker = DirectWorker()
    dispatcher = BackgroundDispatcher(
        worker,
        BackgroundAdmissions(engine),
        resources["windows"],
        document,
        workflow=resources["workflow"],
        publication=resources["publication"],
        max_windows=2,
        max_chars=24000,
    )
    return dispatcher, worker


def test_one_notification_runs_one_complete_layered_publication(engine):
    dataset, document = str(uuid4()), str(uuid4())
    catalogued(engine, document)
    with opened_layered(dataset, document) as resources:
        interviewed(resources["native"], 3)
        requested(resources["native"])
        dispatcher, worker = build_dispatch(engine, document, resources)

        assert dispatcher.wake() == "next_batch"
        assert worker.futures[0].exception() is None
        head = resources["publication"].current()
        assert head.revision == 1
        assert BackgroundAdmissions(engine).read(document).status == "idle"
        bundle = resources["workflow"].artifacts.bundle_manifest(head.memory)
        assert len(bundle.cases) == 1 and len(bundle.understandings) == 1


def test_b1_complete_b2_transport_failure_resumes_without_repeating_b1(engine):
    dataset, document = str(uuid4()), str(uuid4())
    catalogued(engine, document)
    with opened_layered(dataset, document, b2_fails_first=True) as resources:
        interviewed(resources["native"], 3)
        requested(resources["native"])
        dispatcher, worker = build_dispatch(engine, document, resources)
        assert dispatcher.wake() == "next_batch"
        assert isinstance(worker.futures[0].exception(), ConnectionError)
        row = BackgroundAdmissions(engine).read(document)
        assert row.status == "running" and resources["publication"].current() is None

    with opened_layered(dataset, document) as reopened:
        dispatcher, worker = build_dispatch(engine, document, reopened)
        assert dispatcher.wake() == "resume_workflow"
        assert worker.futures[0].exception() is None
        assert reopened["case_model"].requests == [], "completed B1 was repeated"
        assert reopened["understanding_model"].requests
        assert reopened["publication"].current().revision == 1
        assert BackgroundAdmissions(engine).read(document).status == "idle"


def test_committed_publication_with_lost_reply_is_reconciled_once(engine, monkeypatch):
    dataset, document = str(uuid4()), str(uuid4())
    catalogued(engine, document)
    with opened_layered(dataset, document) as resources:
        interviewed(resources["native"], 3)
        requested(resources["native"])
        dispatcher, worker = build_dispatch(engine, document, resources)
        original = PublicationStore.publish
        lost = []

        def commit_then_lose(self, request):
            head = original(self, request)
            if not lost:
                lost.append(head)
                raise ConnectionError("synthetic publication reply loss")
            return head

        monkeypatch.setattr(PublicationStore, "publish", commit_then_lose)
        assert dispatcher.wake() == "next_batch"
        assert isinstance(worker.futures[0].exception(), ConnectionError)
        assert resources["publication"].current().revision == 1
        first_case_calls = len(resources["case_model"].requests)
        first_understanding_calls = len(resources["understanding_model"].requests)

        monkeypatch.setattr(PublicationStore, "publish", original)
        assert dispatcher.wake() == "resume_workflow"
        assert worker.futures[1].exception() is None
        assert resources["publication"].current().revision == 1
        assert len(resources["case_model"].requests) == first_case_calls
        assert len(resources["understanding_model"].requests) == first_understanding_calls
        assert BackgroundAdmissions(engine).read(document).status == "idle"
