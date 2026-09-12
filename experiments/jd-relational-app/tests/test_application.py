import logging
from uuid import UUID

import pytest

from jd_relational import application
from jd_relational.domain import CommandContext, DomainError


REQUEST = UUID("833da1c3-af89-4cdd-b4d5-65399e88a44b")


def context():
    return CommandContext("opaque-document", "base", {}, {}, lambda: "allocated")


def test_preparation_keeps_domain_result_and_records_only_diagnostic_metadata(monkeypatch, caplog):
    candidate = {"private": "不可記入 LOG 的原稿"}
    seen = []

    def builder(snapshot, command, ctx):
        seen.append((snapshot, command, ctx))
        return candidate

    monkeypatch.setattr(application, "build_candidate", builder)
    payload = {"tool": "jd_set_text", "arguments": {"text": "員工私密工作與測試金鑰"}}
    base, ctx = {}, context()
    with caplog.at_level(logging.INFO, logger=application.LOG.name):
        result = application.prepare_edit(base, payload, ctx, request_id=REQUEST)
    assert result is candidate
    assert seen == [(base, payload, ctx)]
    record, = caplog.records
    assert record.event_name == "jd.command.prepare"
    assert record.request_id == str(REQUEST)
    assert record.document_id == "opaque-document"
    assert record.command_kind == "jd_set_text"
    assert record.outcome == "prepared"
    assert record.error_code is None
    assert record.duration_ms >= 0
    assert "private" not in str(record.__dict__)
    assert "員工" not in str(record.__dict__)
    assert record.exc_info is None


def test_expected_error_retains_type_and_refs_but_does_not_log_payload(monkeypatch, caplog):
    error = DomainError("stale_view", "訊息可含私密診斷內容", ("untrusted-ref",))

    def builder(*_):
        raise error

    monkeypatch.setattr(application, "build_candidate", builder)
    with caplog.at_level(logging.INFO, logger=application.LOG.name), pytest.raises(DomainError) as caught:
        application.prepare_edit({}, {"tool": "jd_move_item", "arguments": {"token": "secret"}}, context(), request_id=REQUEST)
    assert caught.value is error
    record, = caplog.records
    assert record.outcome == "rejected"
    assert record.error_code == "stale_view"
    assert record.levelno == logging.INFO
    assert "secret" not in str(record.__dict__)
    assert "untrusted-ref" not in str(record.__dict__)
    assert "私密" not in str(record.__dict__)


def test_unexpected_failure_is_not_swallowed_retried_or_logged_with_raw_exception(monkeypatch, caplog):
    calls = []

    def builder(*_):
        calls.append(1)
        raise RuntimeError("private payload in exception")

    monkeypatch.setattr(application, "build_candidate", builder)
    with caplog.at_level(logging.INFO, logger=application.LOG.name), pytest.raises(RuntimeError):
        application.prepare_edit({}, {"tool": "private bad tool name", "arguments": {}}, context())
    record, = caplog.records
    assert calls == [1]
    assert record.command_kind == "unrecognized"
    assert record.outcome == "failed"
    assert record.error_code == "internal_error"
    assert record.levelno == logging.ERROR
    assert record.exc_info is None
    assert "private" not in str(record.__dict__)


def test_request_id_is_diagnostic_uuid_not_arbitrary_model_text():
    with pytest.raises(TypeError):
        application.prepare_edit({}, {}, context(), request_id="employee free text")


@pytest.mark.parametrize("failure", [None, DomainError("stale_view", "original domain failure"), RuntimeError("original failure")])
def test_logging_failure_never_replaces_candidate_or_original_error(monkeypatch, failure):
    candidate = {"candidate": "preserved"}

    def builder(*_):
        if failure is not None:
            raise failure
        return candidate

    def broken_logger(*args, **kwargs):
        raise OSError("diagnostic output unavailable")

    monkeypatch.setattr(application, "build_candidate", builder)
    monkeypatch.setattr(application.LOG, "log", broken_logger)
    if failure is None:
        assert application.prepare_edit({}, {"tool": "jd_set_text"}, context()) is candidate
    else:
        with pytest.raises(type(failure)) as caught:
            application.prepare_edit({}, {"tool": "jd_set_text"}, context())
        assert caught.value is failure
