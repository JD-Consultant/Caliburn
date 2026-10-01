"""The marker checks of the paid interview simulator, on small hand-made runs.

The simulator is never invoked by tests, but its checks decide what the quality evidence says,
so a wrong count there would turn into a wrong conclusion. Only the pure checks are exercised.
"""

from typing import Any

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
