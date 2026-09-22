from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


EXPECTED_CASES = {
    "CR-01-tools-not-tasks": "CR-01",
    "CR-02-one-story-many-work": "CR-02",
    "CR-03-many-stories-one-task": "CR-03",
    "CR-04-responsibility-boundary": "CR-04",
    "CR-05-correction-and-negation": "CR-05",
    "CR-06-insufficient-evidence": "CR-06",
}
TOP_LEVEL_FIELDS = {
    "case_id",
    "case_family_id",
    "source_type",
    "title",
    "primary_risk",
    "applicable_critical_checks",
    "transcript",
    "claim_table",
    "relevant_span_ids",
    "adjudication",
}
CLAIM_FIELDS = {
    "claim_id",
    "speaker",
    "literal_text",
    "source_turn_ids",
    "sequence_index",
}
ADJUDICATION_FIELDS = {
    "must_retain_tasks",
    "must_not_create_tasks_from",
    "allowed_task_variants",
    "required_uncertainties",
    "notes",
}
CRITICAL_CHECKS = {
    "C1_TOOL_BOUNDARY",
    "C2_RESPONSIBILITY_BOUNDARY",
    "C3_MERGE_SPLIT",
    "C4_CORRECTION_NEGATION",
    "C5_ZERO_EVIDENCE",
    "C6_SOURCE_FIDELITY",
}
PLACEHOLDERS = {
    "案例正式內容會在執行前寫入",
    "正式裁決在 trial 前固定",
    "必須是 source_turn_ids 所指 turn text 的逐字子字串",
    "實際填入",
    "TODO",
    "TBD",
}


class CaseValidationError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CaseValidationError(message)


def _non_empty_text(value: Any, field: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), f"{field} 必須是非空字串")
    return value


def _assert_no_placeholders(value: Any, location: str) -> None:
    if isinstance(value, str):
        for placeholder in PLACEHOLDERS:
            _require(placeholder not in value, f"{location} 含模板占位文字：{placeholder}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_placeholders(item, f"{location}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            _assert_no_placeholders(item, f"{location}.{key}")


def validate_case(record: Any, path: Path) -> None:
    label = path.name
    _require(isinstance(record, dict), f"{label}: root 必須是 JSON object")
    _require(set(record) == TOP_LEVEL_FIELDS, f"{label}: top-level 欄位不符")
    _assert_no_placeholders(record, label)

    case_id = _non_empty_text(record["case_id"], f"{label}.case_id")
    family_id = _non_empty_text(record["case_family_id"], f"{label}.case_family_id")
    _require(case_id in EXPECTED_CASES, f"{label}: 未知 case_id {case_id}")
    _require(EXPECTED_CASES[case_id] == family_id, f"{label}: case_family_id 不符")
    _require(path.stem == case_id, f"{label}: 檔名必須等於 case_id")
    _require(record["source_type"] == "constructed_edge", f"{label}: source_type 必須是 constructed_edge")
    _non_empty_text(record["title"], f"{label}.title")
    _non_empty_text(record["primary_risk"], f"{label}.primary_risk")

    checks = record["applicable_critical_checks"]
    _require(isinstance(checks, list) and bool(checks), f"{label}: applicable_critical_checks 不得為空")
    _require(len(checks) == len(set(checks)), f"{label}: applicable_critical_checks 不得重複")
    _require(set(checks).issubset(CRITICAL_CHECKS), f"{label}: 含未知 critical check")
    _require("C6_SOURCE_FIDELITY" in checks, f"{label}: 每案都必須檢查 C6_SOURCE_FIDELITY")

    transcript = record["transcript"]
    _require(isinstance(transcript, list) and bool(transcript), f"{label}: transcript 不得為空")
    turns: dict[str, dict[str, str]] = {}
    turn_positions: dict[str, int] = {}
    for index, turn in enumerate(transcript, start=1):
        _require(isinstance(turn, dict), f"{label}: transcript[{index}] 必須是 object")
        _require(set(turn) == {"source_id", "role", "text"}, f"{label}: transcript[{index}] 欄位不符")
        source_id = _non_empty_text(turn["source_id"], f"{label}.transcript[{index}].source_id")
        _require(source_id == f"turn-{index:03d}", f"{label}: turn ID 必須依序連號")
        _require(source_id not in turns, f"{label}: turn ID 重複")
        role = turn["role"]
        _require(role in {"consultant", "employee"}, f"{label}: turn role 無效")
        text = _non_empty_text(turn["text"], f"{label}.transcript[{index}].text")
        turns[source_id] = {"role": role, "text": text}
        turn_positions[source_id] = index
    _require(any(turn["role"] == "consultant" for turn in turns.values()), f"{label}: 缺 consultant turn")
    employee_turn_ids = {source_id for source_id, turn in turns.items() if turn["role"] == "employee"}
    _require(bool(employee_turn_ids), f"{label}: 缺 employee turn")

    claims = record["claim_table"]
    _require(isinstance(claims, list) and bool(claims), f"{label}: claim_table 不得為空")
    _require(
        [claim.get("sequence_index") for claim in claims] == list(range(1, len(claims) + 1)),
        f"{label}: sequence_index 必須從 1 連續遞增",
    )
    seen_claim_ids: set[str] = set()
    represented_employee_turns: set[str] = set()
    previous_location = (0, -1, -1)
    for index, claim in enumerate(claims, start=1):
        _require(isinstance(claim, dict), f"{label}: claim[{index}] 必須是 object")
        _require(set(claim) == CLAIM_FIELDS, f"{label}: claim 欄位必須恰為 {sorted(CLAIM_FIELDS)}")
        claim_id = _non_empty_text(claim["claim_id"], f"{label}.claim[{index}].claim_id")
        _require(claim_id == f"claim-{index:03d}", f"{label}: claim ID 必須依序連號")
        _require(claim_id not in seen_claim_ids, f"{label}: claim ID 重複")
        seen_claim_ids.add(claim_id)
        _require(claim["speaker"] == "employee", f"{label}: claim speaker 必須是 employee")

        source_ids = claim["source_turn_ids"]
        _require(
            isinstance(source_ids, list) and len(source_ids) == 1 and isinstance(source_ids[0], str),
            f"{label}: 每個 claim 必須恰好指向一個 source turn",
        )
        source_id = source_ids[0]
        _require(source_id in employee_turn_ids, f"{label}: claim 必須指向 employee turn")
        literal_text = _non_empty_text(claim["literal_text"], f"{label}.claim[{index}].literal_text")
        turn_text = turns[source_id]["text"]
        start = turn_text.find(literal_text)
        _require(start >= 0, f"{label}: {claim_id} 不是 {source_id} 的逐字子字串")
        end = start + len(literal_text)
        location = (turn_positions[source_id], start, end)
        _require(location[:2] >= previous_location[:2], f"{label}: claim 順序不符合 transcript")
        if location[0] == previous_location[0]:
            _require(start >= previous_location[2], f"{label}: 同一 turn 的 claims 不得重疊")
        previous_location = location
        represented_employee_turns.add(source_id)
    _require(
        represented_employee_turns == employee_turn_ids,
        f"{label}: 每個 employee turn 至少需要一個 literal claim",
    )

    relevant_span_ids = record["relevant_span_ids"]
    _require(isinstance(relevant_span_ids, list) and bool(relevant_span_ids), f"{label}: relevant_span_ids 不得為空")
    _require(len(relevant_span_ids) == len(set(relevant_span_ids)), f"{label}: relevant_span_ids 不得重複")
    _require(set(relevant_span_ids).issubset(turns), f"{label}: relevant_span_ids 含未知 turn")

    adjudication = record["adjudication"]
    _require(isinstance(adjudication, dict), f"{label}: adjudication 必須是 object")
    _require(set(adjudication) == ADJUDICATION_FIELDS, f"{label}: adjudication 欄位不符")
    for field in ADJUDICATION_FIELDS - {"notes"}:
        value = adjudication[field]
        _require(isinstance(value, list), f"{label}: adjudication.{field} 必須是 array")
        for item in value:
            _non_empty_text(item, f"{label}.adjudication.{field}")
    _non_empty_text(adjudication["notes"], f"{label}.adjudication.notes")


def validate_directory(directory: Path) -> int:
    _require(directory.is_dir(), f"找不到案例目錄：{directory}")
    paths = sorted(directory.glob("CR-*.json"))
    _require(len(paths) == len(EXPECTED_CASES), f"案例目錄必須恰有 {len(EXPECTED_CASES)} 份 CR-*.json")
    found_ids: set[str] = set()
    for path in paths:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CaseValidationError(f"{path.name}: 無法讀取 JSON：{error}") from error
        validate_case(record, path)
        found_ids.add(record["case_id"])
    _require(found_ids == set(EXPECTED_CASES), "案例集合與預先登記的六案不符")
    return len(paths)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_cases.py <case-directory>", file=sys.stderr)
        return 2
    try:
        count = validate_directory(Path(argv[1]))
    except CaseValidationError as error:
        print(f"case validation failed: {error}", file=sys.stderr)
        return 1
    print(f"validated {count} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
