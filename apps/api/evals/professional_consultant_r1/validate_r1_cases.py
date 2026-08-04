"""檢查八個凍結案例的完整性，並輸出 suite canonical hash。

只驗**能確定的事**：形狀、ID、引用、白名單、模板殘留。
案例的語意品質（Task 邊界切得對不對）由人工 adjudication 決定，程式不裁決。

用法：
    uv run python validate_cases.py            # 驗證並印出 suite hash
"""

from __future__ import annotations

import sys
from typing import Any

from .contracts import (
    CASE_SCHEMA_ID,
    COMMON_DIMENSIONS,
    FULL_HARNESS_ONLY_DIMENSIONS,
    SOURCE_KINDS,
    SOURCE_TYPES,
    Result,
    load_case_dir,
    suite_hash,
)
from .paths import CASES_DIR

EXPECTED_CASE_IDS = tuple(f"TI-R1-0{i}" for i in range(1, 9))

# experiment revision 1 的凍結指紋。案例只要改一個字就會對不上。
# 真的要改案例：升該案的 `case_revision`、記錄理由、更新這個常數，並視為新實驗。
FROZEN_SUITE_HASH = "6c8863863a233830a9216a3ebae46389c91082f097b337c25404400bc93694f7"

# ADR 0041 決定 15：兩案標為 locked regression anchors。
LOCKED_REGRESSION_ANCHORS = ("TI-R1-02", "TI-R1-07")

# 常見模板殘留 / 佔位字樣。出現即視為案例尚未寫完。
TEMPLATE_MARKERS = ("TODO", "TBD", "FIXME", "XXX", "<", "待填", "範例文字", "lorem")

REQUIRED_CASE_KEYS = ("schema_id", "case_id", "case_revision", "source_type", "case_family_id", "sources", "expected")
REQUIRED_EXPECTED_KEYS = (
    "required_behaviors",
    "forbidden_behaviors",
    "common_applicable_rubric_dimensions",
    "full_harness_only_dimensions",
)


def _check_shape(case: dict[str, Any], result: Result) -> None:
    cid = case.get("case_id", "<unknown>")
    for key in REQUIRED_CASE_KEYS:
        if key not in case:
            result.error("case_shape", f"缺少必要欄位 {key}", cid)

    if case.get("schema_id") != CASE_SCHEMA_ID:
        result.error("case_shape", f"schema_id 必須是 {CASE_SCHEMA_ID}", cid)
    if not isinstance(case.get("case_revision"), int) or case.get("case_revision", 0) < 1:
        result.error("case_shape", "case_revision 必須是 >= 1 的整數", cid)
    if case.get("source_type") not in SOURCE_TYPES:
        result.error("source_type", f"source_type 必須是 {SOURCE_TYPES} 之一", cid)
    # ADR 0040 風險段：owner 已裁定目前沒有真實員工訪談資料。
    if case.get("source_type") == "real_employee_interview":
        result.error("source_type", "第一批八案不得標為 real_employee_interview", cid)

    expected = case.get("expected") or {}
    for key in REQUIRED_EXPECTED_KEYS:
        if key not in expected:
            result.error("case_shape", f"expected 缺少 {key}", cid)
    if not expected.get("required_behaviors"):
        result.error("case_shape", "required_behaviors 不得為空", cid)
    if not expected.get("forbidden_behaviors"):
        result.error("case_shape", "forbidden_behaviors 不得為空", cid)


def _check_sources(case: dict[str, Any], result: Result) -> None:
    cid = case.get("case_id", "<unknown>")
    sources = case.get("sources") or []
    if not sources:
        result.error("sources", "至少要有一個 source", cid)

    seen: set[str] = set()
    for src in sources:
        sid = src.get("source_id", "")
        if not sid:
            result.error("sources", "source 缺少 source_id", cid)
            continue
        if sid in seen:
            result.error("sources", f"source_id 重複：{sid}", cid)
        seen.add(sid)
        if src.get("source_kind") not in SOURCE_KINDS:
            result.error("sources", f"{sid} 的 source_kind 必須是 {SOURCE_KINDS} 之一", cid)
        if not (src.get("text") or "").strip():
            result.error("sources", f"{sid} 的 text 不得為空", cid)

    # 每個案例至少要有一句員工發言，否則沒有工作證據可分析。
    if not any(s.get("source_kind") == "employee_turn" for s in sources):
        result.error("sources", "至少要有一個 employee_turn", cid)


def _check_dimensions(case: dict[str, Any], result: Result) -> None:
    cid = case.get("case_id", "<unknown>")
    expected = case.get("expected") or {}

    common = expected.get("common_applicable_rubric_dimensions") or []
    if not common:
        result.error("dimensions", "common_applicable_rubric_dimensions 不得為空", cid)
    for dim in common:
        if dim not in COMMON_DIMENSIONS:
            result.error("dimensions", f"未知的共同維度：{dim}", cid)
    if len(set(common)) != len(common):
        result.error("dimensions", "共同維度有重複", cid)

    full_only = expected.get("full_harness_only_dimensions") or []
    for dim in full_only:
        if dim not in FULL_HARNESS_ONLY_DIMENSIONS:
            result.error("dimensions", f"未知的 full-only 維度：{dim}", cid)
        if dim in common:
            result.error("dimensions", f"{dim} 不得同時列為共同維度與 full-only 維度", cid)


def _check_initial_work_model(case: dict[str, Any], result: Result) -> None:
    """有 initial_work_model 的案例，其 task 必須引用實際存在的 source，
    且必須宣告 full-only 維度 —— 否則 minimal arm 會在看不到的東西上被評分。"""
    cid = case.get("case_id", "<unknown>")
    model = case.get("initial_work_model")
    if model is None:
        return

    source_ids = {s.get("source_id") for s in case.get("sources") or []}
    candidates = model.get("task_candidates") or []
    if not candidates:
        result.error("initial_work_model", "initial_work_model 存在但沒有 task_candidates", cid)

    seen: set[str] = set()
    for task in candidates:
        tid = task.get("task_id", "")
        if not tid:
            result.error("initial_work_model", "task_candidate 缺少 task_id", cid)
            continue
        if tid in seen:
            result.error("initial_work_model", f"task_id 重複：{tid}", cid)
        seen.add(tid)
        if not (task.get("task_statement") or "").strip():
            result.error("initial_work_model", f"{tid} 缺少 task_statement", cid)
        refs = task.get("source_ids") or []
        if not refs:
            result.error("initial_work_model", f"{tid} 至少要引用一個 source_id", cid)
        for ref in refs:
            if ref not in source_ids:
                result.error("initial_work_model", f"{tid} 引用了不存在的 source_id：{ref}", cid)

    full_only = (case.get("expected") or {}).get("full_harness_only_dimensions") or []
    if not full_only:
        result.error(
            "arm_applicability",
            "帶 initial_work_model 的案例必須宣告 full_harness_only_dimensions，"
            "否則 minimal arm 會在結構上做不到的維度被記 fail",
            cid,
        )


def _check_template_residue(case: dict[str, Any], result: Result) -> None:
    cid = case.get("case_id", "<unknown>")

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, str):
            for marker in TEMPLATE_MARKERS:
                if marker.lower() in node.lower():
                    result.error("template_residue", f"{path} 疑似模板殘留：包含 {marker!r}", cid)

    walk(case, "")


def validate_suite(cases: list[dict[str, Any]]) -> Result:
    result = Result()

    ids = [c.get("case_id") for c in cases]
    if sorted(i for i in ids if i) != sorted(EXPECTED_CASE_IDS):
        result.error("suite", f"案例集合必須恰好是 {EXPECTED_CASE_IDS}，實得 {sorted(ids)}", "suite")
    if len(set(ids)) != len(ids):
        result.error("suite", "case_id 有重複", "suite")

    for case in cases:
        cid = case.get("case_id", "<unknown>")
        _check_shape(case, result)
        _check_sources(case, result)
        _check_dimensions(case, result)
        _check_initial_work_model(case, result)
        _check_template_residue(case, result)

        # 第一批八案沒有衍生案例（設計 §11.4）。
        if case.get("case_family_id") != cid:
            result.error("case_family", "第一批八案的 case_family_id 必須等於 case_id", cid)

        if cid in LOCKED_REGRESSION_ANCHORS and not case.get("locked_regression_anchor"):
            result.error("anchor", "此案為 locked regression anchor，必須標記", cid)
        if cid not in LOCKED_REGRESSION_ANCHORS and case.get("locked_regression_anchor"):
            result.error("anchor", "非 anchor 案例不得標記 locked_regression_anchor", cid)

    return result


def main() -> int:
    cases = load_case_dir(CASES_DIR)
    result = validate_suite(cases)
    for finding in result.findings:
        print(finding)
    if not result.ok:
        print(f"\n案例驗證失敗：{len(result.findings)} 項")
        return 1

    actual = suite_hash(cases)
    print(f"八案驗證通過（{len(cases)} 個案例）")
    print(f"suite_canonical_hash = {actual}")
    if actual != FROZEN_SUITE_HASH:
        print(
            "\n凍結指紋不符！案例已被改動。\n"
            f"  expected = {FROZEN_SUITE_HASH}\n"
            f"  actual   = {actual}\n"
            "若為刻意修改：升該案 case_revision、記錄理由、更新 FROZEN_SUITE_HASH，並視為新實驗。"
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
