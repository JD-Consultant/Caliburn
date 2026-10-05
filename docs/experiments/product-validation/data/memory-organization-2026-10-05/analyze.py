"""Project saved public traces; this script never calls a provider or grades meaning."""

import argparse
import json
from collections import Counter
from pathlib import Path


def summarize(run_dir):
    cells = {}
    for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        name = event["cell"]
        if not name:
            continue
        cell = cells.setdefault(
            name,
            {
                "model_responses": 0,
                "input_tokens": 0,
                "cached_tokens": 0,
                "cache_write_tokens": 0,
                "output_tokens": 0,
                "reasoning_tokens": 0,
                "rate_wait_seconds": 0,
                "tool_calls": [],
                "tool_outputs": {},
                "incomplete_responses": [],
            },
        )
        if event["event"] == "rate_wait":
            cell["rate_wait_seconds"] += event["seconds"]
        elif event["event"] == "response" and event["path"].endswith("/responses"):
            payload = event["payload"]
            usage = payload["usage"]
            cell["model_responses"] += 1
            cell["input_tokens"] += usage["input_tokens"]
            cell["cached_tokens"] += usage.get("input_tokens_details", {}).get(
                "cached_tokens", 0
            )
            cell["cache_write_tokens"] += usage.get("input_tokens_details", {}).get(
                "cache_write_tokens", 0
            )
            cell["output_tokens"] += usage["output_tokens"]
            cell["reasoning_tokens"] += usage.get("output_tokens_details", {}).get(
                "reasoning_tokens", 0
            )
            if payload.get("status", "completed") != "completed":
                cell["incomplete_responses"].append(
                    {
                        "reason": payload.get("incomplete_details", {}).get("reason"),
                        "unexecuted_call_names": [
                            item["name"]
                            for item in payload["output"]
                            if item["type"] == "function_call"
                        ],
                    }
                )
                continue
            for item in payload["output"]:
                if item["type"] == "function_call":
                    cell["tool_calls"].append(
                        {
                            "call_id": item["call_id"],
                            "name": item["name"],
                            "arguments": json.loads(item["arguments"]),
                        }
                    )
        elif event["event"] == "request" and event["path"].endswith("/responses"):
            for item in event["payload"]["input"]:
                if item.get("type") == "function_call_output":
                    # Native history is repeated in later requests; count a call once.
                    cell["tool_outputs"][item["call_id"]] = item["output"]
    for name, cell in cells.items():
        cell["tools_by_name"] = dict(
            Counter(item["name"] for item in cell["tool_calls"])
        )
        cell["read_path"] = [
            item for item in cell["tool_calls"] if item["name"].startswith("read_")
        ]
        cell["tool_errors"] = [
            {"call_id": key, "output": value}
            for key, value in cell["tool_outputs"].items()
            if isinstance(value, str)
            and value.lstrip().startswith("{")
            and json.loads(value).get("status") == "rejected"
        ]
        cell["read_output_characters"] = sum(
            len(str(cell["tool_outputs"].get(item["call_id"], "")))
            for item in cell["read_path"]
        )
        output = run_dir / f"output-{name}.json"
        if output.exists():
            material = json.loads(output.read_text(encoding="utf-8"))
            units = [
                value
                for key, value in material["objects"].items()
                if key.startswith("work_understanding:")
            ]
            cell["understandings"] = [
                {
                    "title": unit["title"],
                    "body_characters": len(unit["body"]),
                    "sources": [
                        ref["target_title"] for ref in unit["work_situation_references"]
                    ],
                }
                for unit in units
            ]
            cell["understanding_body_characters"] = sum(
                len(unit["body"]) for unit in units
            )
            cell["map_characters"] = len(
                json.dumps(material["maps"]["work_understanding"], ensure_ascii=False)
            )
        del cell["tool_outputs"]
    return cells


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    result = summarize(args.run_dir)
    (args.run_dir / "analysis.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: {
                    field: value[field]
                    for field in (
                        "model_responses",
                        "input_tokens",
                        "cached_tokens",
                        "output_tokens",
                        "reasoning_tokens",
                        "tools_by_name",
                        "read_output_characters",
                    )
                }
                for key, value in result.items()
            },
            ensure_ascii=False,
            indent=2,
        )
    )
