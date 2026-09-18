from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ARMS = {"raw_only", "raw_plus_spans", "hybrid", "structured_only"}
COMMON_INSTRUCTION = """你是受測的職務分析模型。你只能根據 INPUT_CONTEXT 判斷，不得使用外部知識、repo、工具或其他對話。

目標是辨識員工目前、穩定、屬於本人責任，且具有可辨識目的或結果的工作任務。工具、技術、知識、
技能、單一步驟、一次性事件、過去工作、假設工作與他人責任不得直接升格成 Task。資訊不足時可以不建立 Task。

引用來源時只能使用 turn ID（形如 turn-001）。即使 INPUT_CONTEXT 含 claim ID，也不得引用 claim ID。

只輸出一個 JSON object：
{
  "tasks": [
    {
      "statement": "動詞開頭的工作敘述",
      "source_ids": ["可直接支持此 Task 的 turn ID"]
    }
  ],
  "excluded_mentions": [
    {
      "source_id": "turn ID",
      "reason": "tool_or_skill|step|past_work|hypothetical|other_person|one_off|insufficient"
    }
  ],
  "uncertainties": ["目前無法安全判斷的事項"],
  "next_question": "最能降低目前關鍵不確定性的單一問題；若不需要則為 null"
}

不要輸出 JSON 以外的文字。不得為填滿欄位而推測。"""


def build_context(case: dict[str, Any], arm: str) -> tuple[dict[str, Any], int]:
    if arm not in ARMS:
        raise ValueError(f"unknown arm: {arm}")

    transcript = case["transcript"]
    turns = {turn["source_id"]: turn for turn in transcript}
    relevant_spans = [turns[source_id] for source_id in case["relevant_span_ids"]]
    duplicated_char_count = sum(len(turn["text"]) for turn in relevant_spans)

    if arm == "raw_only":
        return {"transcript": transcript}, 0
    if arm == "raw_plus_spans":
        return {
            "transcript": transcript,
            "relevant_spans": relevant_spans,
        }, duplicated_char_count
    if arm == "hybrid":
        return {
            "transcript": transcript,
            "relevant_spans": relevant_spans,
            "claim_table": case["claim_table"],
        }, duplicated_char_count

    claims_by_turn: dict[str, list[dict[str, Any]]] = {}
    for claim in case["claim_table"]:
        source_id = claim["source_turn_ids"][0]
        claims_by_turn.setdefault(source_id, []).append(claim)
    stream: list[dict[str, Any]] = []
    for turn in transcript:
        if turn["role"] == "consultant":
            stream.append(turn)
        else:
            stream.append(
                {
                    "source_id": turn["source_id"],
                    "role": "employee_claims",
                    "claims": claims_by_turn[turn["source_id"]],
                }
            )
    return {"stream": stream}, 0


def assemble(case: dict[str, Any], arm: str) -> dict[str, Any]:
    context_payload, duplicated_char_count = build_context(case, arm)
    rendered_context = json.dumps(context_payload, ensure_ascii=False, indent=2)
    subject_request = f"{COMMON_INSTRUCTION}\n\nINPUT_CONTEXT:\n{rendered_context}"
    return {
        "context_payload": context_payload,
        "subject_request": subject_request,
        "visible_input_char_count": len(subject_request),
        "span_duplicated_char_count": duplicated_char_count,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: assemble_context.py <case.json> <arm>", file=sys.stderr)
        return 2
    case_path = Path(argv[1])
    arm = argv[2]
    try:
        case = json.loads(case_path.read_text(encoding="utf-8"))
        result = assemble(case, arm)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        print(f"context assembly failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
