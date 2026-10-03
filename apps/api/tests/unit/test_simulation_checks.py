"""The marker checks of the paid interview simulator, on small hand-made runs.

The simulator is never invoked by tests, but its checks decide what the quality evidence says,
so a wrong count there would turn into a wrong conclusion. Only the pure checks are exercised.
"""

import asyncio
import json
from typing import Any

import httpx2
import pytest
from openai import RateLimitError

from scripts import simulate_interview as simulation

PERSONA: dict[str, Any] = {
    "facts": [
        {"id": "ack", "kind": "core", "text": "", "keys": ["回簽"]},
        {"id": "limit", "kind": "hidden", "text": "", "keys": ["五十萬"]},
        {"id": "unknown", "kind": "unknown", "text": "", "keys": []},
    ],
    "correction": {"old": ["每季"], "new": ["半年"], "unchanged": [["未交貨"]]},
    "checks": {"source_expect": {}, "collaborators": []},
}


def collected_run(
    *, task_text: str, employee_texts: list[str], cited_texts: list[str]
) -> dict[str, Any]:
    """One task whose text is `task_text`, citing one source per entry of `cited_texts`."""
    return {
        "profile": {},
        "work": {
            "areas": [],
            "tasks": [
                {
                    "task_id": "t1",
                    "title": "採購",
                    "description": task_text,
                    "outcomes": [],
                    "requirements": [],
                }
            ],
            "collaborators": [],
            "conditions": [],
            "capabilities": [],
        },
        "references": [
            {
                "citation_id": f"c{index}",
                "target": {"kind": "task", "field": None, "item_id": "t1"},
            }
            for index, _ in enumerate(cited_texts)
        ],
        "source_contents": {
            f"c{index}": {"interview_text": text} for index, text in enumerate(cited_texts)
        },
        "interviews": [{"speaker": "employee", "interview_text": t} for t in employee_texts],
    }


def test_a_fact_in_an_item_whose_cited_source_lacks_it_is_unsupported() -> None:
    audit = simulation.citation_audit(
        PERSONA,
        collected_run(
            task_text="下採購單並要求供應商回簽",
            employee_texts=["我下採購單，供應商要回簽確認"],
            cited_texts=["我每天處理請購單"],
        ),
    )

    assert audit["checked"] == 1
    assert audit["support_rate"] == 0.0
    assert audit["unsupported"][0]["fact"] == "ack"


def test_a_fact_is_supported_when_any_cited_source_says_it() -> None:
    audit = simulation.citation_audit(
        PERSONA,
        collected_run(
            task_text="下採購單並要求供應商回簽",
            employee_texts=["供應商要回簽確認"],
            cited_texts=["我每天處理請購單", "沒有回簽就追到有為止"],
        ),
    )

    assert audit["checked"] == 1
    assert audit["unsupported"] == []
    assert audit["support_rate"] == 1.0


def test_a_fact_the_employee_never_said_is_not_audited() -> None:
    audit = simulation.citation_audit(
        PERSONA,
        collected_run(
            task_text="五十萬以上要副總核准",
            employee_texts=["我負責採購"],
            cited_texts=["我負責採購"],
        ),
    )

    assert audit == {"checked": 0, "unsupported": [], "support_rate": None}


def test_an_old_value_is_current_only_when_no_history_word_precedes_it() -> None:
    def old_left(text: str) -> int:
        run = collected_run(task_text=text, employee_texts=[], cited_texts=[])
        correction: dict[str, Any] = simulation.evaluate(PERSONA, run)["correction"]
        return int(correction["old_left_as_current"])

    assert old_left("供應商績效評鑑每季一次") == 1
    assert old_left("供應商績效評鑑現在是每半年，以前每季") == 0


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.output_text = text


def employee_says(monkeypatch: pytest.MonkeyPatch, raw: str) -> tuple[str, bool]:
    async def fake_create_response(sdk: Any, request: Any) -> FakeResponse:
        return FakeResponse(raw)

    monkeypatch.setattr(simulation, "create_response", fake_create_response)
    persona = {**PERSONA, "background": "你是採購專員"}
    return asyncio.run(simulation.employee_reply(None, persona, []))


def test_the_employee_reply_is_read_from_the_json_the_model_was_asked_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = '{"reply": "我會先核對採購單", "nothing_more": true}'

    assert employee_says(monkeypatch, raw) == ("我會先核對採購單", True)


@pytest.mark.parametrize(("flag", "done"), [("false", False), ("true", True)])
def test_a_flag_appended_to_a_plain_text_reply_is_not_something_the_employee_said(
    monkeypatch: pytest.MonkeyPatch, flag: str, done: bool
) -> None:
    raw = f'我會先核對採購單。{{"nothing_more":{flag}}}'

    assert employee_says(monkeypatch, raw) == ("我會先核對採購單。", done)


def late_run(*, jd_text: str, employee_texts: list[str]) -> dict[str, Any]:
    return collected_run(task_text=jd_text, employee_texts=employee_texts, cited_texts=[])


LATE_PERSONA: dict[str, Any] = {
    **PERSONA,
    "late_correction": {
        "turn": 2,
        "requires": ["五十萬"],
        "text": "核准金額更正為一百萬",
        "old": ["五十萬"],
        "new": ["一百萬"],
    },
}


def test_a_late_correction_counts_when_it_was_sent_and_the_old_value_is_gone() -> None:
    run = late_run(
        jd_text="五萬到一百萬由主管核准，以前是五十萬",
        employee_texts=["五萬到五十萬由主管核准", "對了，核准金額更正為一百萬"],
    )

    assert simulation.evaluate(LATE_PERSONA, run)["late_correction"] == {
        "sent": True,
        "new_present": True,
        "old_left_as_current": 0,
    }


def test_a_late_correction_that_never_reached_the_jd_leaves_the_old_value_current() -> None:
    run = late_run(jd_text="五萬到五十萬由主管核准", employee_texts=["核准金額更正為一百萬"])

    assert simulation.evaluate(LATE_PERSONA, run)["late_correction"] == {
        "sent": True,
        "new_present": False,
        "old_left_as_current": 1,
    }


def test_a_persona_without_a_late_correction_reports_none() -> None:
    run = late_run(jd_text="五萬到五十萬由主管核准", employee_texts=[])

    assert simulation.evaluate(PERSONA, run)["late_correction"] is None


def personas() -> dict[str, dict[str, Any]]:
    loaded = json.loads(simulation.PERSONAS.read_text(encoding="utf-8"))
    return {name: persona for name, persona in loaded.items() if not name.startswith("_")}


@pytest.mark.parametrize("name", sorted(personas()))
def test_each_persona_has_everything_the_simulator_reads(name: str) -> None:
    persona = personas()[name]

    assert {"background", "opening", "max_turns", "correction", "facts", "checks"} <= persona.keys()
    assert {"source_expect", "collaborators"} <= persona["checks"].keys()
    assert all({"id", "kind", "text", "keys"} <= fact.keys() for fact in persona["facts"])
    assert {fact["kind"] for fact in persona["facts"]} <= {"core", "hidden", "rare", "unknown"}
    for correction in (persona["correction"], persona.get("late_correction")):
        if correction is None:
            continue
        assert {"turn", "text", "old", "new"} <= correction.keys()
        assert any(word in correction["text"] for word in correction["new"])
    if "late_correction" in persona:
        assert persona["late_correction"]["requires"]
        assert persona["late_correction"]["turn"] > persona["correction"]["turn"]


def test_the_employee_model_is_retried_when_the_accounts_tokens_per_minute_are_used_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[int] = []
    waits: list[float] = []

    async def flaky_create_response(sdk: Any, request: Any) -> FakeResponse:
        attempts.append(1)
        if len(attempts) < 3:
            response = httpx2.Response(
                429, request=httpx2.Request("POST", "https://api.openai.com")
            )
            raise RateLimitError("rate limit", response=response, body=None)
        return FakeResponse('{"reply": "好的", "nothing_more": false}')

    async def no_wait(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr(simulation, "create_response", flaky_create_response)
    monkeypatch.setattr(simulation.asyncio, "sleep", no_wait)
    persona = {**PERSONA, "background": "你是採購專員"}

    reply = asyncio.run(simulation.employee_reply(None, persona, []))

    assert reply == ("好的", False)
    assert len(attempts) == 3
    assert waits == [5, 10]
