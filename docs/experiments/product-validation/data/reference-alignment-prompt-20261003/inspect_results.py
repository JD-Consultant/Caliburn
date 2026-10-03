"""Read saved responses without provider calls; report observable choices, not semantic grades."""

import json
from collections import defaultdict
from pathlib import Path

from caliburn.contracts.generated.tools.revise_jd_item_arguments import (
    ReviseJdItemArguments,
)
from pydantic import ValidationError

HERE = Path(__file__).resolve().parent
EXPECTED_READ_REF = "task_d8aff2474e6847edbe235aa4f3fc4d09"
PENDING_CITATION = "citation_2e6dba21c7c14d5ebd38979d317347bb"


def inspect() -> dict:
    rows = []
    totals = defaultdict(
        lambda: {"responses": 0, "input_tokens": 0, "output_tokens": 0}
    )
    for path in sorted((HERE / "paired-run-02").glob("response-*.json")):
        saved = json.loads(path.read_text(encoding="utf-8"))
        response = saved["response"]
        row = {
            "response_file": path.name,
            "arm": saved["arm"],
            "status": response["status"],
            "elapsed_seconds": saved["elapsed_seconds"],
            "tools": [],
            "messages": [],
        }
        for item in response["output"]:
            if item["type"] == "function_call":
                call = {
                    "name": item["name"],
                    "arguments": json.loads(item["arguments"]),
                }
                if item["name"] == "revise_jd_item":
                    try:
                        ReviseJdItemArguments.model_validate_json(item["arguments"])
                    except ValidationError:
                        call["schema_valid"] = False
                    else:
                        call["schema_valid"] = True
                    args = call["arguments"]
                    call["correct_read_ref"] = args.get("read_ref") == EXPECTED_READ_REF
                    call["addresses_pending_citation"] = any(
                        change.get("citation_ref") == PENDING_CITATION
                        and change.get("target") == {"kind": "item"}
                        for change in args.get("changes", [])
                    )
                row["tools"].append(call)
            elif item["type"] == "message":
                row["messages"].append(
                    {
                        "phase": item.get("phase"),
                        "text": "".join(
                            part.get("text", "") for part in item.get("content", [])
                        ),
                    }
                )
        rows.append(row)
        group = totals[saved["arm"]]
        group["responses"] += 1
        group["input_tokens"] += response["usage"]["input_tokens"]
        group["output_tokens"] += response["usage"]["output_tokens"]
    return {"trials": rows, "totals": dict(totals)}


if __name__ == "__main__":
    print(json.dumps(inspect(), ensure_ascii=False, indent=2))
