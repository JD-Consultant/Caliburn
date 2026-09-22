"""Process-local assembly and recovery for document background work."""

from concurrent.futures import ThreadPoolExecutor
import logging
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest

import jd_relational.background_coordinator as module
from jd_relational.background_coordinator import BackgroundCoordinator
from jd_relational.background_memory_limits import FORMAL_BACKGROUND_MEMORY_LIMITS


class Storage:
    def __init__(self, documents=()):
        self.documents = tuple(sorted(documents))

    def document_ids(self, *, after=None, limit=100):
        remaining = (
            value for value in self.documents
            if after is None or value > after
        )
        return tuple(remaining)[:limit]


class Owner:
    def __init__(self, documents=()):
        self.ready = True
        self.storage = Storage(documents)


def coordinator(owner, **overrides):
    ports = {
        "engine": object(),
        "service": object(),
        "store": object(),
        "checkpointer": object(),
        "memory_engine": object(),
        "case_model": object(),
        "understanding_model": object(),
    }
    ports.update(overrides)
    return BackgroundCoordinator(owner=owner, **ports)


def test_same_document_concurrent_wakes_share_one_dispatcher(monkeypatch):
    document = str(uuid4())
    first_build_started = Event()
    release_first_build = Event()
    duplicate_build_started = Event()
    second_wake_started = Event()
    built = []

    def workflow(**kwargs):
        token = object()
        built.append((kwargs["document_id"], token))
        if len(built) == 1:
            first_build_started.set()
            assert release_first_build.wait(timeout=2)
        else:
            duplicate_build_started.set()
            release_first_build.set()
        return SimpleNamespace(publication=object(), token=token)

    class Dispatcher:
        def __init__(self, owner, admissions, windows, document_id, *, workflow, **kwargs):
            self.token = workflow.token

        def wake(self):
            return self.token

    monkeypatch.setattr(module, "build_background_memory_workflow", workflow)
    monkeypatch.setattr(module, "BackgroundDispatcher", Dispatcher)
    value = coordinator(Owner())

    def second_wake():
        second_wake_started.set()
        return value.wake(document)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(value.wake, document)
        assert first_build_started.wait(timeout=1)
        second = pool.submit(second_wake)
        assert second_wake_started.wait(timeout=1)
        duplicate_build_started.wait(timeout=0.1)
        release_first_build.set()
        results = (first.result(timeout=2), second.result(timeout=2))

    assert results[0] is results[1]
    assert [built_document for built_document, _ in built] == [document]


def test_different_documents_and_fresh_coordinators_build_separate_dispatchers(monkeypatch):
    built = []

    def workflow(**kwargs):
        value = SimpleNamespace(publication=object(), token=object())
        built.append((kwargs["document_id"], value))
        return value

    class Dispatcher:
        def __init__(self, owner, admissions, windows, document_id, *, workflow, **kwargs):
            self.token = workflow.token

        def wake(self):
            return self.token

    monkeypatch.setattr(module, "build_background_memory_workflow", workflow)
    monkeypatch.setattr(module, "BackgroundDispatcher", Dispatcher)
    owner = Owner()
    ports = {
        "engine": object(),
        "service": object(),
        "store": object(),
        "checkpointer": object(),
        "memory_engine": object(),
        "case_model": object(),
        "understanding_model": object(),
    }
    first_document, second_document = str(uuid4()), str(uuid4())
    first = coordinator(owner, **ports)

    first_token = first.wake(first_document)
    assert first.wake(first_document) is first_token
    assert first.wake(second_document) is not first_token
    second = coordinator(owner, **ports)
    assert second.wake(first_document) is not first_token
    assert [document for document, _ in built].count(first_document) == 2
    assert [document for document, _ in built].count(second_document) == 1


def test_wake_binds_existing_host_ports_and_formal_limits(monkeypatch):
    owner = Owner()
    ports = {
        "engine": object(),
        "service": object(),
        "store": object(),
        "checkpointer": object(),
        "memory_engine": object(),
        "case_model": object(),
        "understanding_model": object(),
    }
    document = str(uuid4())
    composition = {}
    publication = object()

    def workflow(**kwargs):
        composition["workflow"] = kwargs
        return SimpleNamespace(publication=publication)

    class Dispatcher:
        def __init__(self, owner, admissions, windows, document_id, **kwargs):
            composition["dispatcher"] = {
                "owner": owner,
                "admissions": admissions,
                "windows": windows,
                "document_id": document_id,
                **kwargs,
            }

        def wake(self):
            return "wait"

    monkeypatch.setattr(module, "build_background_memory_workflow", workflow)
    monkeypatch.setattr(module, "BackgroundDispatcher", Dispatcher)

    assert coordinator(owner, **ports).wake(document) == "wait"
    assert composition["workflow"] == {
        "service": ports["service"],
        "document_id": document,
        "store": ports["store"],
        "checkpointer": ports["checkpointer"],
        "memory_engine": ports["memory_engine"],
        "case_model": ports["case_model"],
        "understanding_model": ports["understanding_model"],
        "limits": FORMAL_BACKGROUND_MEMORY_LIMITS,
    }
    dispatcher = composition["dispatcher"]
    assert dispatcher["owner"] is owner
    assert dispatcher["windows"] is ports["service"]
    assert dispatcher["document_id"] == document
    assert dispatcher["workflow"].publication is publication
    assert dispatcher["publication"] is publication
    assert dispatcher["max_windows"] == FORMAL_BACKGROUND_MEMORY_LIMITS.case_max_windows
    assert dispatcher["max_chars"] == FORMAL_BACKGROUND_MEMORY_LIMITS.case_max_chars
    assert dispatcher["context_chars"] == FORMAL_BACKGROUND_MEMORY_LIMITS.case_context_chars


def test_availability_delegates_to_the_existing_read_only_rule(monkeypatch):
    calls = []
    service = object()
    monkeypatch.setattr(
        module,
        "availability_notice",
        lambda admissions, windows, document, head: calls.append(
            (admissions, windows, document, head)
        ) or "notice",
    )
    value = coordinator(Owner(), service=service)
    document, head = str(uuid4()), object()

    assert value.availability(document, head) == "notice"
    assert len(calls) == 1
    assert calls[0][1:] == (service, document, head)


def test_resume_logs_one_document_failure_and_continues(caplog, monkeypatch):
    documents = tuple(str(uuid4()) for _ in range(2))
    owner = Owner(documents)
    value = coordinator(owner)
    called = []
    failed_document = owner.storage.documents[0]

    def wake(document):
        called.append(document)
        if document == failed_document:
            raise RuntimeError("private employee content")
        return "wait"

    monkeypatch.setattr(value, "wake", wake)

    with caplog.at_level(logging.WARNING, logger="caliburn.jd.background"):
        assert value.resume_pending() == 2
    assert called == list(owner.storage.documents)
    records = [record for record in caplog.records
               if record.name == "caliburn.jd.background"]
    assert len(records) == 1
    record = records[0]
    assert record.getMessage() == "background_document_wake_failed"
    assert record.event_code == "background_document_wake_failed"
    assert record.attempted == 1
    assert record.document_id == failed_document
    assert record.exc_info is None
    assert "private employee content" not in caplog.text


def test_resume_requires_ready():
    owner = Owner()
    value = coordinator(owner)
    owner.ready = False

    with pytest.raises(RuntimeError, match="^background_recovery_before_runtime_ready$"):
        value.resume_pending()


def test_resume_reads_every_catalog_page(monkeypatch):
    documents = tuple(str(uuid4()) for _ in range(101))
    owner = Owner(documents)
    value = coordinator(owner)
    called = []
    monkeypatch.setattr(value, "wake", lambda document: called.append(document) or "wait")

    assert value.resume_pending() == 101
    assert called == list(owner.storage.documents)


def test_catalog_read_failure_logs_scan_progress_and_stays_background_side(
    caplog, monkeypatch,
):
    owner = Owner(tuple(str(uuid4()) for _ in range(100)))
    first_page = owner.storage.document_ids

    def document_ids(*, after=None, limit=100):
        if after is not None:
            raise RuntimeError("private employee content")
        return first_page(after=after, limit=limit)

    owner.storage.document_ids = document_ids
    value = coordinator(owner)
    monkeypatch.setattr(value, "wake", lambda document: "wait")

    with caplog.at_level(logging.WARNING, logger="caliburn.jd.background"):
        assert value.resume_pending() == 100
    records = [record for record in caplog.records
               if record.name == "caliburn.jd.background"]
    assert len(records) == 1
    record = records[0]
    assert record.getMessage() == "background_catalog_scan_failed"
    assert record.event_code == "background_catalog_scan_failed"
    assert record.attempted == 100
    assert not hasattr(record, "document_id")
    assert record.exc_info is None
    assert "private employee content" not in caplog.text
