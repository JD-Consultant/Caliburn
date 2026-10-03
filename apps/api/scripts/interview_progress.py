"""Local evaluation evidence, separate from the product's recovery/state ownership."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def append_record(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_records(path: Path) -> list[dict[str, Any]]:
    # A partial/corrupt line stops recovery; never silently discard evidence.
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class JourneyEvents(list[dict[str, Any]]):
    """Append events immediately, so a harness crash does not erase completed operations."""

    def __init__(self, output: Path) -> None:
        self.path = output.with_suffix(".events.jsonl")
        super().__init__(read_records(self.path) if self.path.exists() else [])

    def append(self, event: dict[str, Any]) -> None:
        record = {"recorded_at": datetime.now(UTC).isoformat(), **event}
        append_record(self.path, record)
        super().append(record)


@dataclass(frozen=True)
class ResumePoint:
    turns: list[dict[str, Any]]
    execution_id: str
    input_text: str


def validate_history(turns: list[dict[str, Any]], messages: list[dict[str, Any]]) -> None:
    expected = []
    for number, turn in enumerate(turns, start=1):
        if turn.get("turn") != number or turn.get("status") != "completed":
            raise ValueError("Resume requires an ordered, completed history prefix")
        expected.extend([("employee", turn["employee"]), ("consultant", turn["consultant"])])
    actual = [(message["speaker"], message["interview_text"]) for message in messages]
    # The official opening is an App-authored source, outside a model Turn.
    if actual and actual[0][0] == "app":
        actual = actual[1:]
    if actual[: len(expected)] != expected:
        raise ValueError("Saved progress does not match the job file's formal interview history")


def seconds_until(deadline: datetime | None) -> float | None:
    if deadline is None:
        return None
    if deadline.tzinfo is None:
        raise ValueError("The journey deadline must include its timezone")
    remaining = (deadline - datetime.now(UTC)).total_seconds()
    if remaining <= 0:
        raise ValueError("The original journey deadline has passed; no new requests are allowed")
    return remaining
