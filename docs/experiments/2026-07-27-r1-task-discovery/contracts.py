"""R1 Task Discovery：case 與模型輸出的最小契約。

authority 是 `docs/specs/2026-07-27-professional-consultant-r1-task-discovery-experiment-design.md`。
本模組只固定 Segment 1 真正用得到的欄位，不是完整 JSON Schema，也不代表 production 形狀。

刻意不做：provider binding、route 驗證、retry 偵測（屬 Segment 2）、
Task 語意是否成立的判斷（屬人工／model grader 的 rubric，規則程式不裁決）。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CASE_SCHEMA_ID = "professional-consultant-r1-case.v1"

# ADR 0040 決定 13：依實際來源分類，八案全為人工構造。
SOURCE_TYPES = ("constructed_edge", "human_manual_test", "real_employee_interview")

SOURCE_KINDS = ("employee_turn", "consultant_turn")

# 設計 §6.1：共同盲評視圖的 analysis_decision。
ANALYSIS_DECISIONS = ("propose_current_tasks", "clarify", "no_change")

# 設計 §6.1：full-only 診斷視圖，不進共同盲評。
CHANGE_TYPES = ("add", "revise", "merge", "split", "withdraw", "no_change")

# 設計 §11.2 的 semantic rubric 維度，適用所有 arm。
COMMON_DIMENSIONS = (
    "meaningful_outcome",
    "employee_responsibility",
    "assignability_checkability",
    "stability_formal_low_frequency",
    "merge_split_boundary",
    "past_other_one_off_exclusion",
    "correction_authority",
    "source_grounding",
    "uncertainty_honesty",
    "next_question_value",
)

# 設計 §4.2／§6.1：只有 full harness arm 具備操作既有 Task ID 的能力。
FULL_HARNESS_ONLY_DIMENSIONS = ("state_change_targets_existing_task",)

# 共同視圖允許出現的 key。多一個 key 就視為洩漏或越界（設計 §11.1）。
CANONICAL_VIEW_KEYS = frozenset(
    {"analysis_decision", "proposed_tasks", "next_question", "limitations", "decision_basis"}
)
PROPOSED_TASK_KEYS = frozenset({"task_statement", "intended_outcome", "source_quotes"})
NEXT_QUESTION_KEYS = frozenset({"text", "purpose"})
STATE_CHANGE_VIEW_KEYS = frozenset({"change_type", "affected_existing_task_ids"})

# 共同視圖若出現這些 key，代表 full-only 診斷欄位漏進盲評視圖。
FULL_ONLY_LEAK_KEYS = frozenset({"change_type", "affected_existing_task_ids"})

# quote 最小長度。ADR 0040 決定 25 只要求「非空與最小長度」，未給數字；
# 這裡取 4（中文四字已足以定位原句），凍結前可調，調了要升 case_revision。
MIN_QUOTE_CHARS = 4

SEVERITY_ERROR = "error"


@dataclass(frozen=True)
class Finding:
    """一條檢查結果。`check` 對應設計 §11.1 的條目。"""

    check: str
    message: str
    severity: str = SEVERITY_ERROR
    locator: str = ""

    def __str__(self) -> str:  # pragma: no cover - 只給 CLI 輸出用
        where = f" [{self.locator}]" if self.locator else ""
        return f"{self.severity}: {self.check}{where} — {self.message}"


@dataclass
class Result:
    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(f.severity == SEVERITY_ERROR for f in self.findings)

    def error(self, check: str, message: str, locator: str = "") -> None:
        self.findings.append(Finding(check=check, message=message, locator=locator))

    def extend(self, other: "Result") -> None:
        self.findings.extend(other.findings)


def canonical_json(payload: Any) -> str:
    """決定性序列化：排序 key、無多餘空白、保留非 ASCII 原字。"""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def load_case(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_case_dir(cases_dir: Path) -> list[dict[str, Any]]:
    """依檔名排序載入 case，確保 suite hash 不受檔案系統順序影響。"""
    return [load_case(p) for p in sorted(cases_dir.glob("TI-R1-*.json"))]


def suite_hash(cases: list[dict[str, Any]]) -> str:
    """整批案例的 canonical hash（設計 §4.3 凍結規則第 2 條）。"""
    ordered = sorted(cases, key=lambda c: c.get("case_id", ""))
    return canonical_hash(ordered)


def source_texts(case: dict[str, Any]) -> dict[str, str]:
    return {s["source_id"]: s["text"] for s in case.get("sources", [])}


def existing_task_ids(case: dict[str, Any]) -> set[str]:
    model = case.get("initial_work_model") or {}
    return {t["task_id"] for t in model.get("task_candidates", [])}
