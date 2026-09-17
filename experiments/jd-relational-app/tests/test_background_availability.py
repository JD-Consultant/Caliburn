"""A turn must know when recent interviews are not in Memory yet.

Counter-examples are fixed in docs/specs/2026-09-14-jd-consultant-guidance-and-skills-slice.md.
The readers here are stand-ins for the App's own owners; this unit is about
what the consultant is told, not about how admission or publication decide.
No provider, no connection.
"""

from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
import pytest

from jd_relational.background_admission import Admission
from jd_relational.background_availability import (
    BLOCK, NOTICE, BackgroundAvailability, availability_notice,
)
from jd_relational.consultant_context import ConsultantContext, ConsultantContextError
from jd_relational.memory_context import MemoryReadSession
from jd_relational.notice_history import NoticeBoundary, NoticeMaterial
from jd_relational.references import ReferenceCodec

DOCUMENT = "0d6de1cd-52e0-4b2f-9a19-5f0e86a2ed6a"
TARGET = "interview-window:target"


class Admissions:
    def __init__(self, admission):
        self.admission, self.calls = admission, 0

    def read(self, document_id):
        assert document_id == DOCUMENT
        self.calls += 1
        return self.admission


class Head:
    def __init__(self, processed_source):
        self.processed_source = processed_source


class Windows:
    """Coverage answers come from the source owner, never recomputed here."""

    def __init__(self, remaining):
        self.remaining, self.seen = remaining, []

    def plan_saved_batch(self, target_reference, document_id, *, after_reference=None):
        self.seen.append((target_reference, document_id, after_reference))
        return {"source_reference": self.remaining, "covers_whole_range": True}


class Forbidden(Windows):
    def __getattr__(self, name):  # start/resume/wake must never be reached
        raise AssertionError(f"availability must not call {name}")


def blocked(**changes):
    return Admission(DOCUMENT, status="blocked", target_reference=TARGET,
                     error_code="source_unavailable", **changes)


def _runtime(document=DOCUMENT, *, head=None, background_availability=None):
    dataset, run = str(uuid4()), str(uuid4())
    boundary = NoticeBoundary(uuid4(), 1)
    notice = NoticeMaterial(document, None, boundary, (), 0, 0, 0)
    session = MemoryReadSession(dataset, document, run, object(), object(), head, "", object())
    context = ConsultantContext(dataset, document, run, object(),
        ReferenceCodec(b"x" * 32, dataset), notice, memory_session=session,
        background_availability=background_availability)
    return SimpleNamespace(context=context)


def test_nothing_is_said_when_background_work_is_not_blocked():
    for status in ("idle", "queued", "running"):
        admission = Admission(DOCUMENT, status=status, target_reference=TARGET)
        windows = Windows("interview-window:rest")
        assert availability_notice(Admissions(admission), windows, DOCUMENT, None) == ""
        assert windows.seen == [], "a healthy row needs no coverage question"


def test_nothing_is_said_when_the_blocked_target_turned_out_to_be_published():
    windows = Windows(None)
    notice = availability_notice(Admissions(blocked()), windows, DOCUMENT,
                                 Head("interview-window:after"))
    assert notice == ""
    assert windows.seen == [(TARGET, DOCUMENT, "interview-window:after")]


def test_a_blocked_and_uncovered_range_is_named():
    notice = availability_notice(Admissions(blocked()), Windows("rest"), DOCUMENT, None)
    assert notice.startswith(NOTICE)
    assert TARGET in notice
    assert "不要假定記憶已包含這段資料" in notice


def test_a_blocked_row_without_a_target_says_nothing():
    admission = replace(blocked(), target_reference=None)
    windows = Windows("rest")
    assert availability_notice(Admissions(admission), windows, DOCUMENT, None) == ""
    assert windows.seen == []


def _middleware():
    return BackgroundAvailability()


def test_the_notice_is_read_once_per_employee_input():
    admissions = Admissions(blocked())
    middleware = BackgroundAvailability()
    state = {"messages": [HumanMessage(id="m1", content="我每週巡檢設備")]}
    runtime = _runtime(background_availability=lambda document_id, head: availability_notice(
        admissions, Windows("rest"), document_id, head))
    first = middleware.before_agent(state, runtime)
    assert first["background_turn_id"] == "m1" and first["background_notice"]
    assert admissions.calls == 1
    again = middleware.before_agent({**state, **first}, runtime)
    assert again is None, "later model steps in the same turn reuse the one read"
    assert admissions.calls == 1


def test_a_new_employee_input_is_read_again():
    admissions = Admissions(blocked())
    middleware = BackgroundAvailability()
    state = {"messages": [HumanMessage(id="m1", content="第一段")],
             "background_turn_id": "m0", "background_notice": ""}
    update = middleware.before_agent(state, _runtime(
        background_availability=lambda document_id, head: availability_notice(
            admissions, Windows("rest"), document_id, head)))
    assert update["background_turn_id"] == "m1"
    assert admissions.calls == 1


def test_a_turn_with_no_employee_input_reads_nothing():
    calls = []
    middleware = BackgroundAvailability()
    assert middleware.before_agent(
        {"messages": [AIMessage(id="a1", content="hi")]},
        _runtime(background_availability=lambda *args: calls.append(args)),
    ) is None
    assert calls == []


class Request:
    def __init__(self, state, system_message=None):
        self.state, self.system_message = state, system_message
        self.overridden = None

    def override(self, *, system_message):
        self.overridden = system_message
        return self


def test_the_notice_arrives_as_an_app_system_block_not_as_the_employee():
    middleware = _middleware()
    notice = availability_notice(Admissions(blocked()), Windows("rest"), DOCUMENT, None)
    request = Request({"background_notice": notice}, SystemMessage(content="顧問指引"))
    seen = {}
    middleware.wrap_model_call(request, lambda value: seen.setdefault("request", value))
    blocks = seen["request"].overridden.content
    assert isinstance(seen["request"].overridden, SystemMessage)
    assert blocks[0] == {"type": "text", "text": "顧問指引"}
    assert blocks[1]["text"] == BLOCK.format(notice=notice)
    assert "整理完成" not in blocks[1]["text"] and "已更新" not in blocks[1]["text"]


def test_an_empty_notice_leaves_the_request_untouched():
    middleware = _middleware()
    request = Request({"background_notice": ""}, SystemMessage(content="顧問指引"))
    seen = {}
    middleware.wrap_model_call(request, lambda value: seen.setdefault("request", value))
    assert seen["request"] is request and request.overridden is None


def test_availability_never_reaches_for_a_way_to_run_background_work():
    notice = availability_notice(Admissions(blocked()), Forbidden("rest"), DOCUMENT, None)
    assert notice.startswith(NOTICE)
    with pytest.raises(AssertionError):
        Forbidden("rest").start()


def test_one_shared_middleware_uses_each_invocations_own_provider_once():
    other = str(uuid4())
    calls = []

    def provider(document_id, head):
        calls.append((document_id, head))
        return f"notice:{document_id}"

    middleware = BackgroundAvailability()
    first = middleware.before_agent(
        {"messages": [HumanMessage(id="turn-a", content="a")]},
        _runtime(DOCUMENT, head="head-a", background_availability=provider),
    )
    second = middleware.before_agent(
        {"messages": [HumanMessage(id="turn-b", content="b")]},
        _runtime(other, head="head-b", background_availability=provider),
    )

    assert first == {"background_turn_id": "turn-a", "background_notice": f"notice:{DOCUMENT}"}
    assert second == {"background_turn_id": "turn-b", "background_notice": f"notice:{other}"}
    assert calls == [(DOCUMENT, "head-a"), (other, "head-b")]


def test_missing_provider_records_an_empty_notice_without_reading_resources():
    middleware = BackgroundAvailability()
    assert middleware.before_agent(
        {"messages": [HumanMessage(id="turn", content="a")]}, _runtime(),
    ) == {"background_turn_id": "turn", "background_notice": ""}


def test_provider_cannot_project_a_non_string_notice():
    middleware = BackgroundAvailability()
    with pytest.raises(ConsultantContextError, match="^background_notice_not_available$"):
        middleware.before_agent(
            {"messages": [HumanMessage(id="turn", content="a")]},
            _runtime(background_availability=lambda *_: {"not": "text"}),
        )


def test_provider_read_failure_omits_only_the_optional_notice():
    middleware = BackgroundAvailability()

    def unavailable(*_):
        raise OSError("synthetic background read failure")

    assert middleware.before_agent(
        {"messages": [HumanMessage(id="turn", content="a")]},
        _runtime(background_availability=unavailable),
    ) == {"background_turn_id": "turn", "background_notice": ""}


def test_missing_or_crossed_runtime_memory_scope_stops_before_any_read():
    calls = []
    middleware = BackgroundAvailability()
    with pytest.raises(ConsultantContextError, match="^invalid_background_scope$"):
        middleware.before_agent(
            {"messages": [HumanMessage(id="m1", content="內容")]}, SimpleNamespace(context=None))
    runtime = _runtime(background_availability=lambda *args: calls.append(args))
    runtime.context = replace(runtime.context, memory_session=replace(
        runtime.context.memory_session, document_id=str(uuid4())))
    with pytest.raises(ConsultantContextError, match="^invalid_background_scope$"):
        middleware.before_agent(
            {"messages": [HumanMessage(id="m1", content="內容")]}, runtime)
    assert calls == []
