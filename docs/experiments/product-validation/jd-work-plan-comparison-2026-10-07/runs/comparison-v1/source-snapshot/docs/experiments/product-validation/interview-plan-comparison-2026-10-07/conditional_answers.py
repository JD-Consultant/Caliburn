"""Frozen private, conditional employee facts. No employee SDK or turn-number facts.

The last question paragraph selects at most two relevant disclosures. The complete
oracle is never passed to the app. Every selection retains its matched cue for audit.
"""

import json
import re
from pathlib import Path

PROFILES = json.loads(
    Path(__file__).with_name("private_facts.json").read_text(encoding="utf-8")
)
CLOSURE = "今天先到這裡。請把目前已確認的工作整理、保存成正式職務說明書，檢查各欄是否一致；尚未取得或說不清的內容請指出，不補猜，我沒有新增事實。"
CONTINUE = "可以依我已說過的工作範圍繼續訪談；我沒有新增事實。"


class Employee:
    def __init__(self, profile):
        self.profile_name = profile
        self.profile = PROFILES[profile]
        self.disclosed = set()
        self.seen_topics = set()
        self.gaps = set()
        self.refused_topics = set()
        self.audit = []
        self.disclosure_order = []
        self.gap_opened_at = {}

    def initial(self):
        return self.profile["initial"]

    def answer(self, text):
        paragraphs = [
            part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()
        ]
        questions = [
            part
            for part in paragraphs
            if re.search(r"[？?]|請|想了解|可以說|能說", part)
        ]
        question = (
            questions[-1] if questions else (paragraphs[-1] if paragraphs else "")
        )
        sentences = re.split(r"(?<=[。！!?？])", question)
        actual = [
            sentence
            for sentence in sentences
            if re.search(r"[？?]|請|想了解|可以說|能說|我們先釐清", sentence)
        ]
        question = "".join(actual) if actual else question
        question = re.sub(
            r"(?:不用再談|不再談|已了解|已整理)[^；;。]*[；;。]", "", question
        )
        candidates = []
        for fact in self.profile["facts"]:
            cue = max(
                (word for word in fact["match"] if word in question),
                key=len,
                default=None,
            )
            if not cue or fact["id"] in self.disclosed:
                continue
            if fact.get("requires") not in (None, *self.disclosed):
                continue
            if fact.get("after_topic") and fact["after_topic"] not in self.seen_topics:
                continue
            if fact["topic"] in self.refused_topics:
                continue
            # Generic authorization/handoff words do not establish the topic.
            required_topic = {
                "inventory-authority": ["盤點", "庫存", "調帳", "帳差"],
                "training-boundary": ["新人", "上線", "帶教", "考核"],
                "absence-partial": ["代課", "缺課", "臨時", "不能到", "請假"],
                "absence-handoff": ["代課", "缺課", "臨時", "不能到", "請假"],
                "annual-count": [
                    "年度",
                    "一年",
                    "低頻",
                    "偶爾",
                    "其他工作",
                    "整份工作",
                    "未提到",
                ],
                "annual-grant": [
                    "年度",
                    "一年",
                    "低頻",
                    "偶爾",
                    "其他工作",
                    "整份工作",
                    "未提到",
                ],
                "privacy": ["個資", "保密", "保存", "權限", "名單"],
            }.get(fact["id"])
            if required_topic and not any(word in question for word in required_topic):
                continue
            candidates.append((fact, cue))
        # Return a known gap before optional deepening, when the question supplies
        # its topic and the factual availability condition has actually changed.
        explicit_annual = any(
            word in question for word in ["年度", "每年", "不定期", "低頻"]
        )
        candidates.sort(
            key=lambda entry: (
                0 if explicit_annual and entry[0]["topic"] == "annual" else 1,
                0 if entry[0].get("closes_gap") in self.gaps else 1,
                -len(entry[1]),
            )
        )
        chosen = candidates[:1]
        if chosen:
            fact, cue = chosen[0]
            self.disclosed.add(fact["id"])
            self.seen_topics.add(fact["topic"])
            if fact.get("opens_gap"):
                self.gaps.add(fact["opens_gap"])
            if fact.get("closes_gap"):
                self.gaps.discard(fact["closes_gap"])
            if fact.get("refused"):
                self.refused_topics.add(fact["topic"])
            answer = fact["answer"]
            details = {
                "fact_id": fact["id"],
                "topic": fact["topic"],
                "matched_cue": cue,
                "unknown": fact.get("unknown", False),
                "refused": fact.get("refused", False),
                "opens_gap": fact.get("opens_gap"),
                "closes_gap": fact.get("closes_gap"),
                "correction": fact.get("correction", False),
            }
        else:
            answer = "這一題我目前沒有其他確定資料，請先保留說不清的部分；若要釐清，可以具體問我實際做的步驟或責任。"
            details = {"fact_id": None, "unmapped_or_already_answered": True}
        self.audit.append(
            {"actual_question": question, "employee_text": answer, **details}
        )
        return answer

    def state(self):
        return {
            "disclosed": sorted(self.disclosed),
            "seen_topics": sorted(self.seen_topics),
            "open_gaps": sorted(self.gaps),
            "refused_topics": sorted(self.refused_topics),
            "audit": self.audit,
            "disclosure_order": self.disclosure_order,
            "gap_opened_at": self.gap_opened_at,
        }

    def reviewed_answer(self, question, decision):
        """Apply only frozen, eligible facts selected by the independent human-policy judge."""
        ids = decision.get("fact_ids")
        mode = decision.get("mode")
        if (
            not isinstance(ids, list)
            or len(ids) > 4
            or len(ids) != len(set(ids))
            or mode not in {"answer", "unknown", "refused", "clarify", "no_question"}
            or not isinstance(decision.get("reason"), str)
            or not decision["reason"].strip()
        ):
            raise ValueError("Invalid semantic review decision")
        if (mode == "answer") != bool(ids):
            raise ValueError("Answer mode must select frozen facts")
        unknown = decision.get("unknown_subtopics", [])
        if not isinstance(unknown, list) or any(
            not isinstance(part, str) or not part.strip() or part not in question
            for part in unknown
        ):
            raise ValueError("Unknown subtopics must quote the actual question")
        facts = {fact["id"]: fact for fact in self.profile["facts"]}
        answers = []
        known = []
        new = []
        for fact_id in ids:
            if fact_id not in facts:
                raise ValueError("Unknown private fact ID")
            fact = facts[fact_id]
            if fact_id in self.disclosed:
                known.append(fact_id)
            else:
                if fact.get("requires") and fact["requires"] not in self.disclosed:
                    raise ValueError("The related earlier disclosure is missing")
                if (
                    fact.get("after_topic")
                    and fact["after_topic"] not in self.seen_topics
                ):
                    raise ValueError(
                        "The factual availability condition has not changed"
                    )
                if fact.get("after_topic"):
                    opened = self.gap_opened_at.get(fact_id)
                    if opened is None or not any(
                        facts[seen]["topic"] == fact["after_topic"]
                        for seen in self.disclosure_order[opened + 1 :]
                    ):
                        raise ValueError(
                            "The topic must follow the actual partial gap disclosure"
                        )
                if fact["topic"] in self.refused_topics:
                    raise ValueError("The employee has not reopened the refused topic")
                new.append(fact_id)
            answers.append(fact["answer"])
        for fact_id in new:
            fact = facts[fact_id]
            self.disclosed.add(fact_id)
            self.seen_topics.add(fact["topic"])
            if fact.get("opens_gap"):
                self.gaps.add(fact["opens_gap"])
                self.gap_opened_at[fact["opens_gap"]] = len(
                    self.disclosure_order
                ) + ids.index(fact_id)
            if fact.get("closes_gap"):
                self.gaps.discard(fact["closes_gap"])
            if fact.get("refused"):
                self.refused_topics.add(fact["topic"])
        self.disclosure_order.extend(ids)
        fixed = {
            "unknown": "這一題我目前沒有其他確定資料，請先保留說不清的部分。",
            "refused": "這個個案我不想談，也不能提供他人個資，請先保留。",
            "clarify": "這個問題我還沒理解，請用實際工作步驟或責任再具體問一次。",
            "no_question": CONTINUE,
        }
        answer = "\n\n".join(answers) if ids else fixed[mode]
        if decision.get("omitted_subtopics"):
            answer += "\n\n其餘這次還沒說明，請保留，之後再具體問。"
        if unknown:
            answer += (
                "\n\n關於你問的「"
                + "」、「".join(unknown)
                + "」，我目前沒有確定資料，請保留未知，不補猜。"
            )
        self.audit.append(
            {
                "actual_question": question,
                "employee_text": answer,
                "fact_ids": ids,
                "known_confirmation_ids": known,
                "new_fact_ids": new,
                "review_mode": mode,
                "review_reason": decision["reason"],
                "omitted_subtopics": decision.get("omitted_subtopics", []),
                "unknown_subtopics": unknown,
                "driver_reminder": mode == "no_question",
            }
        )
        return answer
