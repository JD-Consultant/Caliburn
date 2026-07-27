"""對單一模型輸出跑 deterministic checks（設計 §11.1 中不需要網路的那幾條）。

**本模組不判斷「這是不是一個好 Task」。** 它只驗形狀、引用與逐字對應。
Task 邊界品質由 rubric 的人工／model grader 決定。

Segment 2 才會補上需要網路的三條：provider route／model／endpoint 符合 binding、
無隱藏 retry／fallback／cache replay。那些檢查不屬於本模組。
"""

from __future__ import annotations

import re
from typing import Any

from contracts import (
    ANALYSIS_DECISIONS,
    CANONICAL_VIEW_KEYS,
    CHANGE_TYPES,
    FULL_ONLY_LEAK_KEYS,
    MIN_QUOTE_CHARS,
    NEXT_QUESTION_KEYS,
    PROPOSED_TASK_KEYS,
    STATE_CHANGE_VIEW_KEYS,
    Result,
    existing_task_ids,
    source_texts,
)

ARM_CLASS_MINIMAL = "minimal"
ARM_CLASS_FULL = "full"
ARM_CLASSES = (ARM_CLASS_MINIMAL, ARM_CLASS_FULL)

_WHITESPACE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    """比對機械重複用：收掉所有空白並 casefold。"""
    return _WHITESPACE.sub("", text).casefold()


def _check_view_shape(view: dict[str, Any], result: Result) -> None:
    unknown = set(view) - CANONICAL_VIEW_KEYS
    for key in sorted(unknown):
        # full-only 欄位漏進共同視圖是設計 §6.1 最在意的洩漏，單獨標一條 check。
        check = "full_only_leak" if key in FULL_ONLY_LEAK_KEYS else "canonical_view_shape"
        result.error(check, f"共同視圖不得包含欄位 {key}", "canonical_view")

    for key in ("analysis_decision", "proposed_tasks", "limitations"):
        if key not in view:
            result.error("canonical_view_shape", f"缺少必要欄位 {key}", "canonical_view")

    if "analysis_decision" in view and view["analysis_decision"] not in ANALYSIS_DECISIONS:
        result.error(
            "canonical_view_shape",
            f"analysis_decision 必須是 {ANALYSIS_DECISIONS} 之一，實得 {view['analysis_decision']!r}",
            "canonical_view",
        )
    if "proposed_tasks" in view and not isinstance(view["proposed_tasks"], list):
        result.error("canonical_view_shape", "proposed_tasks 必須是陣列", "canonical_view")
    if "limitations" in view and not isinstance(view["limitations"], list):
        result.error("canonical_view_shape", "limitations 必須是陣列", "canonical_view")


def _check_decision_consistency(view: dict[str, Any], result: Result) -> None:
    """設計 §11.1：`clarify`／`no_change` 時可有 0 個 Task。
    反過來說，宣稱 propose_current_tasks 就必須真的提出至少一個。"""
    decision = view.get("analysis_decision")
    tasks = view.get("proposed_tasks")
    if not isinstance(tasks, list):
        return
    if decision == "propose_current_tasks" and not tasks:
        result.error(
            "decision_task_consistency",
            "analysis_decision 為 propose_current_tasks 但沒有任何 proposed_tasks",
            "canonical_view",
        )


def _check_next_question(view: dict[str, Any], result: Result) -> None:
    nq = view.get("next_question")
    if nq is None:
        return
    if not isinstance(nq, dict):
        result.error("next_question_shape", "next_question 必須是物件或 null", "next_question")
        return
    for key in sorted(set(nq) - NEXT_QUESTION_KEYS):
        result.error("next_question_shape", f"next_question 不得包含欄位 {key}", "next_question")
    text = nq.get("text")
    if text is not None and not str(text).strip():
        result.error("next_question_shape", "next_question.text 若非 null 就不得為空白", "next_question")


def _check_tasks(case: dict[str, Any], view: dict[str, Any], result: Result) -> None:
    tasks = view.get("proposed_tasks")
    if not isinstance(tasks, list):
        return

    texts = source_texts(case)
    seen_statements: dict[str, int] = {}

    for index, task in enumerate(tasks):
        locator = f"proposed_tasks[{index}]"
        if not isinstance(task, dict):
            result.error("task_shape", "Task 必須是物件", locator)
            continue

        for key in sorted(set(task) - PROPOSED_TASK_KEYS):
            result.error("task_shape", f"Task 不得包含欄位 {key}", locator)

        statement = (task.get("task_statement") or "").strip()
        if not statement:
            result.error("task_shape", "task_statement 不得為空", locator)
        else:
            norm = _normalize(statement)
            if norm in seen_statements:
                result.error(
                    "mechanical_duplication",
                    f"task_statement 與 proposed_tasks[{seen_statements[norm]}] 機械重複",
                    locator,
                )
            else:
                seen_statements[norm] = index

        if not (task.get("intended_outcome") or "").strip():
            result.error("task_shape", "intended_outcome 不得為空", locator)

        quotes = task.get("source_quotes")
        if not isinstance(quotes, list):
            result.error("task_shape", "source_quotes 必須是陣列", locator)
            continue
        if not quotes:
            # ADR 0040 決定 25：每個 Task 至少一個 source anchor。
            result.error("source_anchor", "Task 至少要有一個 source_quote", locator)

        seen_quotes: set[str] = set()
        for q_index, quote in enumerate(quotes):
            q_locator = f"{locator}.source_quotes[{q_index}]"
            if not isinstance(quote, str):
                result.error("quote_verbatim", "source_quote 必須是字串", q_locator)
                continue
            stripped = quote.strip()
            if len(stripped) < MIN_QUOTE_CHARS:
                result.error(
                    "quote_verbatim",
                    f"quote 長度不足（至少 {MIN_QUOTE_CHARS} 字）：{quote!r}",
                    q_locator,
                )
                continue
            if not any(quote in text for text in texts.values()):
                result.error(
                    "quote_verbatim",
                    f"quote 不是任何 source 的逐字子字串：{quote!r}",
                    q_locator,
                )
            norm_quote = _normalize(quote)
            if norm_quote in seen_quotes:
                result.error("mechanical_duplication", f"同一 Task 內 quote 重複：{quote!r}", q_locator)
            seen_quotes.add(norm_quote)


def _check_state_change(
    case: dict[str, Any],
    state_change_view: dict[str, Any] | None,
    arm_class: str,
    result: Result,
) -> None:
    """full-only 診斷視圖。minimal arm 不該產生它；產生了就是契約違規，
    但這條**不進 A1 vs A6 的 Task-boundary 分數**（設計 §6.1、§11.2）。"""
    if state_change_view is None:
        if arm_class == ARM_CLASS_FULL and existing_task_ids(case):
            result.error(
                "state_change_shape",
                "案例帶有 initial_work_model，full arm 必須輸出 StateChangeDiagnosticView",
                "state_change_view",
            )
        return

    if arm_class == ARM_CLASS_MINIMAL:
        result.error(
            "arm_contract",
            "minimal arm 看不到 Current Work Model，不得輸出 StateChangeDiagnosticView",
            "state_change_view",
        )
        return

    for key in sorted(set(state_change_view) - STATE_CHANGE_VIEW_KEYS):
        result.error("state_change_shape", f"診斷視圖不得包含欄位 {key}", "state_change_view")

    change_type = state_change_view.get("change_type")
    if change_type not in CHANGE_TYPES:
        result.error(
            "state_change_shape",
            f"change_type 必須是 {CHANGE_TYPES} 之一，實得 {change_type!r}",
            "state_change_view",
        )

    affected = state_change_view.get("affected_existing_task_ids")
    if affected is None:
        affected = []
    if not isinstance(affected, list):
        result.error("state_change_shape", "affected_existing_task_ids 必須是陣列", "state_change_view")
        return

    known = existing_task_ids(case)
    for task_id in affected:
        if task_id not in known:
            result.error(
                "existing_task_reference",
                f"指向不存在的既有 Task：{task_id}",
                "state_change_view",
            )

    # 設計 §11.1「correction target 存在」：宣稱改動既有 Task 就必須指名對象。
    if change_type in ("revise", "withdraw", "merge", "split") and not affected:
        result.error(
            "existing_task_reference",
            f"change_type={change_type} 必須指名至少一個 affected_existing_task_ids",
            "state_change_view",
        )


def verify_output(
    case: dict[str, Any],
    canonical_view: dict[str, Any],
    arm_class: str,
    state_change_view: dict[str, Any] | None = None,
) -> Result:
    """對單一 trial 的輸出跑所有不需網路的 deterministic checks。"""
    result = Result()
    if arm_class not in ARM_CLASSES:
        result.error("arm_contract", f"arm_class 必須是 {ARM_CLASSES} 之一", "arm_class")
        return result

    if not isinstance(canonical_view, dict):
        result.error("canonical_view_shape", "共同視圖必須是物件", "canonical_view")
        return result

    _check_view_shape(canonical_view, result)
    _check_decision_consistency(canonical_view, result)
    _check_next_question(canonical_view, result)
    _check_tasks(case, canonical_view, result)
    _check_state_change(case, state_change_view, arm_class, result)
    return result
