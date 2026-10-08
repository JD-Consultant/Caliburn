"""Verify frozen inputs and project observable results; semantic grading stays manual."""

import argparse
import ast
import json
import zipfile
from collections import Counter
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def verify_archive(name, records, expected_hash):
    path = HERE / name
    assert sha256(path.read_bytes()).hexdigest() == expected_hash, "Archive changed"
    with zipfile.ZipFile(path) as archive:
        assert set(archive.namelist()) == set(records)
        for filename, expected in records.items():
            assert sha256(archive.read(filename)).hexdigest() == expected, filename
    return len(records)


def constant(archive, filename, name):
    syntax = ast.parse(archive.read(filename).decode("utf-8"))
    for node in syntax.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        ):
            value = node.value
            if (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute)
                and value.func.attr == "strip"
                and not value.args
                and not value.keywords
            ):
                return ast.literal_eval(value.func.value).strip()
            return ast.literal_eval(value)
    raise ValueError(name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--turn", required=True, type=int)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    manifest, repair = load("manifest.json"), load("resource-repair.json")
    frozen_count = verify_archive(
        "freeze/sources.zip",
        manifest["source_hashes"],
        manifest["source_archive_sha256"],
    )
    resource_count = verify_archive(
        "resource-freeze/sources.zip", repair["source_hashes"], repair["archive_sha256"]
    )
    with zipfile.ZipFile(HERE / "freeze/sources.zip") as archive:
        prefix = "apps/api/src/caliburn/agents/job_consultant/"
        instructions = constant(
            archive, prefix + "instructions.py", "CONSULTANT_INSTRUCTIONS"
        )
        instructions += "\n\n" + constant(
            archive,
            prefix + "reference_instructions.py",
            "OCCUPATION_REFERENCE_INSTRUCTIONS",
        )
    consultant_hash = sha256(instructions.encode()).hexdigest()
    rows = [
        json.loads(line)
        for line in (HERE / "provider-trace.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    roles = {
        row["attempt"]: "A"
        if row["instructions_sha256"] == consultant_hash
        else "Memory"
        for row in rows
        if row["event"] == "admitted"
    }
    role_counts = {
        role: {"tools": Counter(), "usage": Counter()} for role in ["A", "Memory"]
    }
    responses = {}
    for row in rows:
        if row["event"] != "received":
            continue
        role = role_counts[roles[row["attempt"]]]
        role["tools"].update(
            item["name"]
            for item in row.get("output", [])
            if item["type"] == "function_call"
        )
        if row["usage"]:
            role["usage"].update(
                {key: row["usage"][key] for key in ["input_tokens", "output_tokens"]}
            )
        for item in row.get("output", []):
            if item.get("type") == "function_call":
                responses[item["call_id"]] = {
                    "time": row["time"],
                    "name": item["name"],
                    "arguments": item["arguments"],
                }
    tool_outputs = {
        item["call_id"]: item.get("output")
        for row in rows
        for item in row.get("input", [])
        if item.get("type") == "function_call_output"
    }
    rejected = []
    for call_id, content in tool_outputs.items():
        if not isinstance(content, str):
            continue
        try:
            value = json.loads(content)
        except ValueError:
            continue
        if isinstance(value, dict) and value.get("status") == "rejected":
            rejected.append(
                {"call_id": call_id, "call": responses[call_id], "result": value}
            )
    after = load(f"turn-{arguments.turn:02}-result.json")
    work, references = after["jd"]["work"], after["jd"]["sources"]["references"]
    result = {
        "frozen_files_verified": frozen_count,
        "resource_files_verified": resource_count,
        "consultant_instructions_sha256": consultant_hash,
        "role_counts": role_counts,
        "unique_tool_results": len(tool_outputs),
        "rejected_calls": rejected,
        "max_counted_input_tokens": max(
            row["input_tokens"] for row in rows if row["event"] == "count"
        ),
        "jd_at_turn": arguments.turn,
        "jd_revision_id": work["revision_id"],
        "areas": len(work["areas"]),
        "tasks": len(work["tasks"]),
        "capabilities": dict(Counter(item["kind"] for item in work["capabilities"])),
        "task_links": len(work["task_links"]),
        "collaborators": len(work["collaborators"]),
        "conditions": len(work["conditions"]),
        "current_sources": len(references),
        "source_kinds": dict(Counter(item["source_kind"] for item in references)),
        "pending_recheck": sum(item["needs_recheck"] for item in references),
        "scope": "Observable counts only; not a completeness score or causal comparison",
    }
    with (HERE / arguments.output).open("x", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key not in ["rejected_calls", "role_counts"]
            },
            ensure_ascii=False,
        )
    )
    print(json.dumps(role_counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
