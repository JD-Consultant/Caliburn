"""Only new-batch compatibility changes; predecessor owns reservation arithmetic."""

import sys
from pathlib import Path

OLD = Path(__file__).resolve().parent.with_name("interview-plan-comparison-2026-10-07")
sys.path.insert(0, str(OLD))
from guard import BatchGuard as OriginalGuard
from guard import role


class BatchGuard(OriginalGuard):
    def __init__(self, **kwargs):
        if "seconds" in kwargs:
            raise ValueError("This batch has no absolute or elapsed batch deadline")
        super().__init__(seconds=float("inf"), **kwargs)
        self.templates = None
        self.group = None
        self.phase_start = None
        self.phase = None

    def check(self, payload):
        super().check(payload)
        if self.templates is not None and role(payload) == "A":
            expected = self.templates[self.group]
            if (
                payload.get("instructions") != expected["instructions"]
                or payload.get("tools") != expected["tools"]
            ):
                self.refuse(
                    "Actual A instructions or ordered tools differ from frozen arm"
                )
            if self.group == "P1":
                for item in payload.get("input", []):
                    text = str(item)
                    if "interview_plan" in text or "interview-plan" in text:
                        self.refuse("P1 contains a Plan context or projection")

    def admit(self, payload):
        if (
            self.phase == "pilot"
            and self.phase_start is not None
            and self.generations - self.phase_start["generations"] >= 160
        ):
            self.refuse("pilot generation allowance reached")
        return super().admit(payload)

    def admit_compact(self, payload):
        if (
            self.phase == "pilot"
            and self.phase_start is not None
            and self.compacts - self.phase_start["compacts"] >= 2
        ):
            self.refuse("pilot compact allowance reached")
        return super().admit_compact(payload)

    def state(self):
        return {**super().state(), "batch_deadline": None, "limit_usd": str(self.limit)}


def accepted_source(command, accepted, messages):
    """A matching old sentence cannot satisfy the current accepted source identity."""
    if accepted.get("command_id") != command["command_id"]:
        raise ValueError("HTTP accepted a different command")
    originals = [
        item
        for item in messages
        if item.get("source_id") == accepted.get("source_id")
        and item.get("speaker") == "employee"
    ]
    if len(originals) != 1 or originals[0]["interview_text"] != command["text"]:
        raise ValueError("Exact accepted employee source is not formally visible")
    return originals[0]


def checked_decision(path, question_id, started, clock, maximum=300):
    import json

    if clock() - started >= maximum:
        raise TimeoutError("Late semantic decision cannot disclose an answer")
    decision = json.loads(path.read_text(encoding="utf-8"))
    if clock() - started >= maximum:
        raise TimeoutError("Semantic decision expired during reading")
    if decision.get("question_id") != question_id:
        raise ValueError("Semantic decision belongs to another question")
    return decision
