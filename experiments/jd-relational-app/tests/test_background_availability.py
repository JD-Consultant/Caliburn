"""A turn must know when recent interviews are not in Memory yet.

Counter-examples are fixed in docs/specs/2026-09-14-jd-consultant-guidance-and-skills-slice.md.
The readers here are stand-ins for the App's own owners; this unit is about
what the consultant is told, not about how admission or publication decide.
No provider, no connection.
"""

from dataclasses import replace

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
import pytest

from jd_relational.background_admission import Admission
from jd_relational.background_availability import (
    BLOCK, NOTICE, BackgroundAvailability, availability_notice,
)

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


class Publication:
    def __init__(self, head=None):
        self.head = head

    def current(self):
        return self.head


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


def test_nothing_is_said_when_background_work_is_not_blocked():
    for status in ("idle", "queued", "running"):
        admission = Admission(DOCUMENT, status=status, target_reference=TARGET)
        windows = Windows("interview-window:rest")
        assert availability_notice(Admissions(admission), Publication(), windows, DOCUMENT) == ""
        assert windows.seen == [], "a healthy row needs no coverage question"


def test_nothing_is_said_when_the_blocked_target_turned_out_to_be_published():
    windows = Windows(None)
    notice = availability_notice(Admissions(blocked()), Publication(Head("interview-window:after")),
                                 windows, DOCUMENT)
    assert notice == ""
    assert windows.seen == [(TARGET, DOCUMENT, "interview-window:after")]


def test_a_blocked_and_uncovered_range_is_named():
    notice = availability_notice(Admissions(blocked()), Publication(), Windows("rest"), DOCUMENT)
    assert notice.startswith(NOTICE)
    assert TARGET in notice
    assert "不要假定記憶已包含這段資料" in notice


def test_a_blocked_row_without_a_target_says_nothing():
    admission = replace(blocked(), target_reference=None)
    windows = Windows("rest")
    assert availability_notice(Admissions(admission), Publication(), windows, DOCUMENT) == ""
    assert windows.seen == []


def _middleware(admission, windows=None, head=None):
    return BackgroundAvailability(Admissions(admission), Publication(head),
                                  windows or Windows("rest"), DOCUMENT)


def test_the_notice_is_read_once_per_employee_input():
    admissions = Admissions(blocked())
    middleware = BackgroundAvailability(admissions, Publication(), Windows("rest"), DOCUMENT)
    state = {"messages": [HumanMessage(id="m1", content="我每週巡檢設備")]}
    first = middleware.before_agent(state, None)
    assert first["background_turn_id"] == "m1" and first["background_notice"]
    assert admissions.calls == 1
    again = middleware.before_agent({**state, **first}, None)
    assert again is None, "later model steps in the same turn reuse the one read"
    assert admissions.calls == 1


def test_a_new_employee_input_is_read_again():
    admissions = Admissions(blocked())
    middleware = BackgroundAvailability(admissions, Publication(), Windows("rest"), DOCUMENT)
    state = {"messages": [HumanMessage(id="m1", content="第一段")],
             "background_turn_id": "m0", "background_notice": ""}
    update = middleware.before_agent(state, None)
    assert update["background_turn_id"] == "m1"
    assert admissions.calls == 1


def test_a_turn_with_no_employee_input_reads_nothing():
    admissions = Admissions(blocked())
    middleware = BackgroundAvailability(admissions, Publication(), Windows("rest"), DOCUMENT)
    assert middleware.before_agent({"messages": [AIMessage(id="a1", content="hi")]}, None) is None
    assert admissions.calls == 0


class Request:
    def __init__(self, state, system_message=None):
        self.state, self.system_message = state, system_message
        self.overridden = None

    def override(self, *, system_message):
        self.overridden = system_message
        return self


def test_the_notice_arrives_as_an_app_system_block_not_as_the_employee():
    middleware = _middleware(blocked())
    notice = availability_notice(Admissions(blocked()), Publication(), Windows("rest"), DOCUMENT)
    request = Request({"background_notice": notice}, SystemMessage(content="顧問指引"))
    seen = {}
    middleware.wrap_model_call(request, lambda value: seen.setdefault("request", value))
    blocks = seen["request"].overridden.content
    assert isinstance(seen["request"].overridden, SystemMessage)
    assert blocks[0] == {"type": "text", "text": "顧問指引"}
    assert blocks[1]["text"] == BLOCK.format(notice=notice)
    assert "整理完成" not in blocks[1]["text"] and "已更新" not in blocks[1]["text"]


def test_an_empty_notice_leaves_the_request_untouched():
    middleware = _middleware(Admission(DOCUMENT))
    request = Request({"background_notice": ""}, SystemMessage(content="顧問指引"))
    seen = {}
    middleware.wrap_model_call(request, lambda value: seen.setdefault("request", value))
    assert seen["request"] is request and request.overridden is None


def test_availability_never_reaches_for_a_way_to_run_background_work():
    notice = availability_notice(Admissions(blocked()), Publication(), Forbidden("rest"), DOCUMENT)
    assert notice.startswith(NOTICE)
    with pytest.raises(AssertionError):
        Forbidden("rest").start()
