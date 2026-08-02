"""對單一模型輸出跑 deterministic checks（設計 §11.1 中不需要網路的那幾條）。

**本模組不判斷「這是不是一個好 Task」。** 它只驗形狀、引用與逐字對應。
Task 邊界品質由 rubric 的人工／model grader 決定。

**fail-closed**：模型輸出是不可信輸入。任意 JSON 值都必須回 typed finding，
絕不可以拋例外把 trial runner 打掛。

Segment 2 才會補上需要網路的三條：provider route／model／endpoint 符合 binding、
無隱藏 retry／fallback／cache replay。那些檢查不屬於本模組。
"""

from __future__ import annotations

import re
from typing import Any

from .contracts import (
    ANALYSIS_DECISIONS,
    CANONICAL_VIEW_KEYS,
    CHANGE_TYPES,
    FULL_ONLY_LEAK_KEYS,
    GRADER_FORBIDDEN_KEYS,
    MIN_QUOTE_CHARS,
    NEXT_QUESTION_KEYS,
    PROPOSED_TASK_KEYS,
    SOURCE_ANCHOR_KEYS,
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


def _text_or_none(value: Any) -> str | None:
    """只接受字串。任何其他型別回 None，由呼叫端記 finding。"""
    return value if isinstance(value, str) else None


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

    if "limitations" in view:
        limitations = view["limitations"]
        if not isinstance(limitations, list):
            result.error("canonical_view_shape", "limitations 必須是陣列", "canonical_view")
        else:
            for i, item in enumerate(limitations):
                if _text_or_none(item) is None:
                    result.error(
                        "canonical_view_shape",
                        "limitations 的每一項都必須是字串",
                        f"limitations[{i}]",
                    )


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
    if "text" in nq and nq["text"] is not None:
        text = _text_or_none(nq["text"])
        if text is None:
            result.error("next_question_shape", "next_question.text 必須是字串或 null", "next_question")
        elif not text.strip():
            result.error(
                "next_question_shape", "next_question.text 若非 null 就不得為空白", "next_question"
            )
    if "purpose" in nq and nq["purpose"] is not None and _text_or_none(nq["purpose"]) is None:
        result.error("next_question_shape", "next_question.purpose 必須是字串或 null", "next_question")


def _check_source_anchors(
    anchors: Any,
    texts: dict[str, str],
    locator: str,
    result: Result,
) -> None:
    """設計 §4.4：每個 Task 至少一個 `source_id` ＋ 對應的逐字 quote，
    且 quote 必須是**該筆** source 的子字串（不是「某一筆」）。"""
    if not isinstance(anchors, list):
        result.error("task_shape", "source_anchors 必須是陣列", locator)
        return
    if not anchors:
        # ADR 0040 決定 25：每個 Task 至少一個 source anchor。
        result.error("source_anchor", "Task 至少要有一個 source_anchor", locator)
        return

    seen: set[tuple[str, str]] = set()
    for index, anchor in enumerate(anchors):
        a_locator = f"{locator}.source_anchors[{index}]"
        if not isinstance(anchor, dict):
            result.error("source_anchor", "source_anchor 必須是物件", a_locator)
            continue
        for key in sorted(set(anchor) - SOURCE_ANCHOR_KEYS):
            result.error("source_anchor", f"source_anchor 不得包含欄位 {key}", a_locator)

        source_id = _text_or_none(anchor.get("source_id"))
        quote = _text_or_none(anchor.get("quote"))
        if source_id is None:
            result.error("source_anchor", "source_anchor 缺少字串 source_id", a_locator)
        elif source_id not in texts:
            result.error(
                "source_reference", f"source_id 不存在於本 case：{source_id!r}", a_locator
            )

        if quote is None:
            result.error("source_anchor", "source_anchor 缺少字串 quote", a_locator)
            continue
        if len(quote.strip()) < MIN_QUOTE_CHARS:
            result.error(
                "quote_verbatim", f"quote 長度不足（至少 {MIN_QUOTE_CHARS} 字）：{quote!r}", a_locator
            )
            continue
        if source_id is not None and source_id in texts and quote not in texts[source_id]:
            result.error(
                "quote_verbatim",
                f"quote 不是 {source_id} 的逐字子字串：{quote!r}",
                a_locator,
            )

        if source_id is not None:
            key = (source_id, _normalize(quote))
            if key in seen:
                result.error("mechanical_duplication", f"同一 Task 內 anchor 重複：{quote!r}", a_locator)
            seen.add(key)


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

        statement = _text_or_none(task.get("task_statement"))
        if statement is None:
            result.error("task_shape", "task_statement 必須是字串", locator)
        elif not statement.strip():
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

        outcome = _text_or_none(task.get("intended_outcome"))
        if outcome is None:
            result.error("task_shape", "intended_outcome 必須是字串", locator)
        elif not outcome.strip():
            result.error("task_shape", "intended_outcome 不得為空", locator)

        if "source_anchors" not in task:
            result.error("source_anchor", "Task 缺少 source_anchors", locator)
        else:
            _check_source_anchors(task["source_anchors"], texts, locator, result)


def _check_state_change(
    case: dict[str, Any],
    state_change_view: Any,
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

    if not isinstance(state_change_view, dict):
        result.error("state_change_shape", "診斷視圖必須是物件", "state_change_view")
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
    for i, task_id in enumerate(affected):
        if _text_or_none(task_id) is None:
            result.error(
                "state_change_shape",
                "affected_existing_task_ids 的每一項都必須是字串",
                f"state_change_view.affected_existing_task_ids[{i}]",
            )
            continue
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


def verify_grader_packet(packet: Any) -> Result:
    """盲評 packet 的乾淨性檢查：不得攜帶 rationale、arm、model、schema 等識別資訊。

    這是 `project_canonical_view` 的守門測試，用來證明 grader 看不到 arm 身分。
    """
    result = Result()
    if not isinstance(packet, dict):
        result.error("grader_packet", "grader packet 必須是物件", "grader_packet")
        return result
    for key in sorted(set(packet) & GRADER_FORBIDDEN_KEYS):
        result.error("grader_packet", f"grader packet 不得包含欄位 {key}", "grader_packet")
    for key in sorted(set(packet) - CANONICAL_VIEW_KEYS):
        if key not in GRADER_FORBIDDEN_KEYS:
            result.error("grader_packet", f"grader packet 出現未知欄位 {key}", "grader_packet")
    return result


def verify_output(
    case: dict[str, Any],
    canonical_view: Any,
    arm_class: str,
    state_change_view: Any = None,
) -> Result:
    """對單一 trial 的**已投影**共同視圖跑所有不需網路的 deterministic checks。

    傳進來的應該是 `project_canonical_view()` 的結果，不是 raw 模型輸出。
    """
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
