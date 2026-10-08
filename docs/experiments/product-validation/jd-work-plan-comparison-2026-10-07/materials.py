"""New materials, composed with the frozen predecessor's eligibility mechanism.

The journey prepares a deepcopy. This object's state becomes effective only after
the exact accepted source_id is publicly adopted. No keyword answer is dispatched.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.with_name("interview-plan-comparison-2026-10-07")
sys.path.insert(0, str(OLD))
from conditional_answers import CLOSURE, CONTINUE
from conditional_answers import Employee as OriginalEmployee

__all__ = ["CLOSURE", "CONTINUE", "CUES", "MANUAL_TEXT", "PROFILES", "Employee"]

PROFILES = json.loads((HERE / "private_facts.json").read_text(encoding="utf-8"))
CUES = {name: profile["availability_cue"] for name, profile in PROFILES.items()}
MANUAL_TEXT = {
    name: profile["manual_edit"]["required_text"] for name, profile in PROFILES.items()
}


class Employee(OriginalEmployee):
    def __init__(self, profile):
        super().__init__(profile)
        self.profile = PROFILES[profile]
        self.visible_cues = []

    def reviewed_answer(self, question, decision):
        cue = CUES[self.profile_name]
        eligible = (
            cue["partial"] in self.disclosed
            and cue["gap"] in self.gaps
            and not self.visible_cues
            and any(
                fact["id"] in decision.get("fact_ids", [])
                and fact["topic"] == cue["topic"]
                for fact in self.profile["facts"]
            )
        )
        # This one frozen fact contains the anonymous public process AND its
        # explicit complaint refusal. Admitting that exact answer releases no
        # complaint details and does not reopen the refused case. The old gate
        # grouped both under one topic and therefore overblocked this sequence.
        public_refusal_flow = {
            fact["topic"]
            for fact in self.profile["facts"]
            if fact["id"] == "sensitive-evaluation"
            and fact.get("refused") is True
            and fact["id"] in decision.get("fact_ids", [])
        }
        retained_refusals = self.refused_topics.copy()
        self.refused_topics.difference_update(public_refusal_flow)
        try:
            answer = super().reviewed_answer(question, decision)
        finally:
            self.refused_topics.update(retained_refusals)
        if eligible:
            answer += "\n\n" + cue["text"]
            self.visible_cues.append(
                {
                    "gap": cue["gap"],
                    "text": cue["text"],
                    "audit_index": len(self.audit) - 1,
                }
            )
            self.audit[-1]["availability_cue"] = cue["text"]
            self.audit[-1]["employee_text"] = answer
        return answer

    def state(self):
        return {**super().state(), "visible_cues": self.visible_cues}
