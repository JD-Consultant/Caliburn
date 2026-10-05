"""Reconcile observed usage and native continuations without grading by keywords."""

import json
from itertools import pairwise
from pathlib import Path

from reading_probe_materials import invoke
from run_reading_probe import OUTPUT, ROOT
from study_manifest import file_hash, save_new, verify_files


def audit() -> dict[str, object]:
    manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    verify_files(manifest["files"], root=ROOT)
    result = json.loads((OUTPUT / "result.json").read_text(encoding="utf-8"))
    materials = json.loads((OUTPUT / "materials.json").read_text(encoding="utf-8"))
    prepared = json.loads((OUTPUT / "requests.json").read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in (OUTPUT / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    totals = dict.fromkeys(
        (
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "cached_input_tokens",
            "generation_calls",
        ),
        0,
    )
    evidence = []
    for phase in manifest["schedule"]:
        key = f"{phase['arm']}-{phase['case_id']}"
        answer = json.loads((OUTPUT / f"answer-{key}.json").read_text(encoding="utf-8"))
        events = [
            row
            for row in rows
            if all(row.get(k) == v for k, v in phase.items())
            and row.get("path") == "/v1/responses"
        ]
        requests = [row for row in events if row["event"] == "request"]
        responses = {
            row["request_id"]: row for row in events if row["event"] == "response"
        }
        assert requests[0]["payload"] == prepared[key]
        for row in requests:
            assert (
                row["payload"]["instructions"] == manifest["instructions"][phase["arm"]]
            )
            assert row["payload"]["tools"] == manifest["tools"][phase["arm"]]
        native_transitions = 0
        actual_reads = []
        for previous, following in pairwise(requests):
            output = responses[previous["request_id"]]["payload"]["output"]
            prefix = previous["payload"]["input"] + [
                {k: v for k, v in item.items() if k != "status"} for item in output
            ]
            assert following["payload"]["input"][: len(prefix)] == prefix
            calls = [item for item in output if item["type"] == "function_call"]
            returned = following["payload"]["input"][len(prefix) :]
            assert len(calls) == len(returned)
            for call, tool_result in zip(calls, returned, strict=True):
                assert tool_result["type"] == "function_call_output"
                assert tool_result["call_id"] == call["call_id"]
                expected = invoke(materials, call["name"], call["arguments"])
                assert json.loads(tool_result["output"]) == expected
                actual_reads.append(
                    {
                        "name": call["name"],
                        "arguments": call["arguments"],
                        "output": expected,
                    }
                )
            native_transitions += 1
        assert actual_reads == answer["reads"]
        for name in totals:
            field = {
                "reasoning_tokens": ("output_tokens_details", "reasoning_tokens"),
                "cached_input_tokens": ("input_tokens_details", "cached_tokens"),
            }.get(name)
            observed = (
                len(requests)
                if name == "generation_calls"
                else sum(
                    row["payload"]["usage"][field[0]][field[1]]
                    if field
                    else row["payload"]["usage"][name]
                    for row in responses.values()
                )
            )
            assert observed == answer["usage"][name]
            totals[name] += observed
        evidence.append(
            {
                **phase,
                "usage": answer["usage"],
                "native_transitions": native_transitions,
                "reads": [read["name"] for read in answer["reads"]],
                "generation_request_ids": [r["request_id"] for r in requests],
                "answer_sha256": file_hash(OUTPUT / f"answer-{key}.json"),
            }
        )
    assert all(totals[name] == result["usage"][name] for name in totals)
    assert result["status"] == "completed" and len(result["completed"]) == 10
    assert result["usage"]["pending_request_sha256"] is None
    assert result["usage"]["compaction_calls"] == 0
    return {
        "trace_sha256": file_hash(OUTPUT / "trace.jsonl"),
        "result_sha256": file_hash(OUTPUT / "result.json"),
        "audit_script_sha256": file_hash(Path(__file__)),
        "frozen_files_unchanged": True,
        "native_continuation_and_tool_results_verified": True,
        "usage_reconciled": True,
        "episodes": evidence,
        "totals": totals,
    }


if __name__ == "__main__":
    evidence = audit()
    target = OUTPUT / "audit.json"
    if target.exists():
        assert json.loads(target.read_text(encoding="utf-8")) == evidence
    else:
        save_new(target, evidence)
    print(
        json.dumps(
            {
                "verified_episodes": len(evidence["episodes"]),
                "totals": evidence["totals"],
            }
        )
    )
