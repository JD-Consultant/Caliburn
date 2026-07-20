"""Content-free metrics for an exported interview evaluation candidate."""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from evals.interview_v4.privacy_scan import scan_case


def _percentile(values: list[int], quantile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[index]


def _guard_category(value: Any) -> str:
    text = str(value).lower()
    checks = (
        ("verify_reject", "verify-reject"),
        ("conflict", "conflict"),
        ("drop", "drop:"),
        ("pending_add", "pending-add"),
        ("pending_modify", "pending-mod"),
        ("pending_delete", "pending-del"),
        ("curation", "curation"),
        ("harvest", "harvest"),
        ("scribe", "scribe"),
        ("failure", "失敗"),
        ("abandoned", "放棄"),
        ("rejected", "拒"),
        ("timeout", "timeout"),
        ("error", "error"),
    )
    for category, marker in checks:
        if marker in text:
            return category
    return "other"


def _verify_reason(check: str, text: str) -> str:
    if check == "invariant":
        if "位置碼" in text or "代碼欄" in text:
            return "protected_code_field"
        if "態度只能" in text:
            return "attitude_scope"
        if "已存在" in text or "重複" in text:
            return "duplicate_entry"
        if "主基準" in text:
            return "header_reference_domain"
    if check == "hygiene":
        if "超長" in text:
            return "over_length"
        if "控制字元" in text or "程式碼圍欄" in text or "單行" in text:
            return "non_plain_single_line"
    return "other"


def _shape(value: Any) -> Counter[str]:
    counts: Counter[str] = Counter()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            counts["objects"] += 1
            counts["object_fields"] += len(node)
            for item in node.values():
                walk(item)
        elif isinstance(node, list):
            counts["arrays"] += 1
            counts["array_items"] += len(node)
            for item in node:
                walk(item)
        elif isinstance(node, str):
            counts["strings"] += 1
            counts["string_chars"] += len(node)
        elif node is not None:
            counts["scalars"] += 1

    walk(value)
    return counts


def _call_metrics(calls: list[dict[str, Any]]) -> dict[str, Any]:
    durations = [int(call["duration_ms"]) for call in calls if call.get("duration_ms") is not None]
    prompt_tokens = [
        int(call["prompt_tokens"])
        for call in calls
        if call.get("prompt_tokens") is not None
    ]
    completion_tokens = [
        int(call["completion_tokens"])
        for call in calls
        if call.get("completion_tokens") is not None
    ]
    guards = Counter(
        _guard_category(verdict)
        for call in calls
        for verdict in (call.get("guard_verdicts") or [])
    )
    verify_checks: Counter[str] = Counter()
    verify_reasons: Counter[str] = Counter()
    for call in calls:
        for verdict in call.get("guard_verdicts") or []:
            verdict_text = str(verdict)
            match = re.search(
                r"verify-reject:op\[\d+\]\s+([a-z_]+):",
                verdict_text.lower(),
            )
            if match:
                check = match.group(1)
                verify_checks[check] += 1
                verify_reasons[_verify_reason(check, verdict_text)] += 1
    return {
        "count": len(calls),
        "duration_ms_total": sum(durations),
        "duration_ms_p50": _percentile(durations, 0.50),
        "duration_ms_p95": _percentile(durations, 0.95),
        "prompt_tokens": {
            "recorded_calls": len(prompt_tokens),
            "total": sum(prompt_tokens) if prompt_tokens else None,
        },
        "completion_tokens": {
            "recorded_calls": len(completion_tokens),
            "total": sum(completion_tokens) if completion_tokens else None,
        },
        "guard_categories": dict(sorted(guards.items())),
        "verify_reject_checks": dict(sorted(verify_checks.items())),
        "verify_reject_reasons": dict(sorted(verify_reasons.items())),
    }


def summarize_candidate(case_dir: str | Path) -> dict[str, Any]:
    root = Path(case_dir).resolve()
    transcript = [
        json.loads(line)
        for line in (root / "transcript.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    audit = json.loads((root / "source_audit.json").read_text(encoding="utf-8"))
    reviews = json.loads((root / "review_events.json").read_text(encoding="utf-8"))
    observed_document_path = root / "observed_document.json"
    observed_document = (
        json.loads(observed_document_path.read_text(encoding="utf-8"))
        if observed_document_path.exists()
        else None
    )
    calls = audit.get("llm_calls") or []
    calls_by_role: dict[str, list[dict[str, Any]]] = {}
    calls_by_stage: dict[str, list[dict[str, Any]]] = {}
    calls_by_turn: dict[int, list[dict[str, Any]]] = {}
    for call in calls:
        calls_by_role.setdefault(str(call.get("role")), []).append(call)
        calls_by_stage.setdefault(str(call.get("stage") or call.get("role")), []).append(call)
        calls_by_turn.setdefault(int(call.get("turn_seq") or 0), []).append(call)
    role_counts = Counter(str(turn.get("role")) for turn in transcript)
    role_chars = Counter()
    for turn in transcript:
        role_chars[str(turn.get("role"))] += len(str(turn.get("text") or ""))
    privacy = scan_case(root)
    return {
        "schema_version": "interview_eval_candidate_metrics.v0.1",
        "case_id": json.loads((root / "case.json").read_text(encoding="utf-8"))["case_id"],
        "transcript": {
            "turns_by_role": dict(sorted(role_counts.items())),
            "characters_by_role": dict(sorted(role_chars.items())),
        },
        "review_decisions": dict(sorted(Counter(
            str(review.get("decision")) for review in reviews
        ).items())),
        "llm_calls": {
            **_call_metrics(calls),
            "roles": dict(sorted(Counter(str(call.get("role")) for call in calls).items())),
            "stages": dict(sorted(Counter(
                str(call.get("stage") or call.get("role")) for call in calls
            ).items())),
            "outcomes": dict(sorted(Counter(
                str(call.get("outcome") or "legacy_unknown") for call in calls
            ).items())),
            "models": dict(sorted(Counter(str(call.get("model")) for call in calls).items())),
            "by_role": {
                role: _call_metrics(role_calls)
                for role, role_calls in sorted(calls_by_role.items())
            },
            "by_stage": {
                stage: _call_metrics(stage_calls)
                for stage, stage_calls in sorted(calls_by_stage.items())
            },
            "by_turn": [
                {
                    "turn_seq": turn_seq,
                    "roles": dict(sorted(Counter(
                        str(call.get("role")) for call in turn_calls
                    ).items())),
                    **_call_metrics(turn_calls),
                }
                for turn_seq, turn_calls in sorted(calls_by_turn.items())
            ],
        },
        "observed_document_shape": dict(sorted(_shape(observed_document).items())),
        "fixture_provenance": audit.get("fixture_provenance") or {},
        "privacy_prescreen": {
            "finding_counts": privacy["finding_counts"],
            "manual_review_still_required": privacy["manual_review_still_required"],
        },
        "replay_ready": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("case_dir")
    args = parser.parse_args()
    print(json.dumps(summarize_candidate(args.case_dir), ensure_ascii=False, indent=2))
