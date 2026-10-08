"""Observation-only wrapper for the existing formal original identity checker."""

import argparse
import json
from hashlib import sha256
from pathlib import Path

from formal_originals_audit import read, verify_turn

METHOD_SHA = "20ce9516e61dff66f009c0f8351bbf0463f628ef919b2e262ef694f31e244916"


def collect_case(directory, partial_turns):
    initial_path = directory / "initial-interviews.json"
    initial_ids = {item["source_id"] for item in read(initial_path)["messages"]}
    paths = [initial_path]
    final = None
    if partial_turns is None:
        result_path = directory / "result.json"
        result = read(result_path)
        if not result["closure_submitted"] or result["turns"][-1]["status"] != "completed":
            raise ValueError("The case has no completed common closure")
        final_path = directory / "formal-interviews.json"
        final = read(final_path)["messages"]
        paths.extend([result_path, final_path])
    rows, accepted_ids, job_files, sequences = [], set(), set(), []
    for accepted_path in sorted(directory.glob("turn-*-accepted.json")):
        turn = int(accepted_path.name[5:7])
        if partial_turns is not None and turn > partial_turns:
            continue
        command_path = accepted_path.with_name(accepted_path.name.replace("-accepted", "-input"))
        turn_path = accepted_path.with_name(accepted_path.name.replace("-accepted", "-result"))
        command, accepted, turn_result = read(command_path), read(accepted_path), read(turn_path)
        if turn_result["status"]["status"] != "completed":
            raise ValueError("A selected Turn is not completed")
        if accepted["source_id"] in initial_ids | accepted_ids:
            raise ValueError("Current accepted source was initial or reused across Turns")
        current = verify_turn(command, accepted, turn_result["interviews"]["messages"])
        if final is not None:
            saved = verify_turn(command, accepted, final)
            if current != saved:
                raise ValueError("The final formal original differs from its Turn export")
        rows.append({"turn": turn, **current})
        accepted_ids.add(accepted["source_id"])
        job_files.add(accepted["job_file_id"])
        sequences.append(current["formal_interview_sequence"])
        paths.extend([command_path, accepted_path, turn_path])
    if (
        not rows
        or len(job_files) != 1
        or any(a >= b for a, b in zip(sequences, sequences[1:], strict=False))
    ):
        raise ValueError("Accepted inputs must belong to one strictly ordered job file")
    if partial_turns is not None and len(rows) != partial_turns:
        raise ValueError("The bounded partial Turn range is not fully exported")
    if final is not None:
        current_ids = {item["source_id"] for item in final if item["speaker"] == "employee"}
        if current_ids - initial_ids != accepted_ids:
            raise ValueError("Final formal employee IDs differ from actual accepted input IDs")
    return {
        "case_path": str(directory),
        "complete_case": final is not None,
        "accepted_inputs_checked": len(rows),
        "earlier_same_text_rows": sum(bool(row["earlier_same_text_source_ids"]) for row in rows),
        "rows": rows,
        "source_hashes": {str(path): sha256(path.read_bytes()).hexdigest() for path in paths},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--partial-turns", type=int)
    args = parser.parse_args()
    if args.partial_turns is not None and args.partial_turns <= 0:
        raise ValueError("Partial Turn count must be positive")
    method = Path(__file__).with_name("formal_originals_audit.py")
    if sha256(method.read_bytes()).hexdigest() != METHOD_SHA:
        raise ValueError("The existing pure identity checker changed")
    result = {
        "cases": [collect_case(directory, args.partial_turns) for directory in args.case],
        "existing_method_sha256": METHOD_SHA,
        "wrapper_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "authority": (
            "Actual submitted input + accepted current source_id + formal HTTP employee body"
        ),
        "selected_snapshot_authority": False,
        "limits": (
            "Observation-only saved HTTP exports; no key, provider, PostgreSQL, new HTTP, "
            "JD content or quality review. Partial Turns are not a completed case. "
            "Earlier identical text sources cannot replace the current accepted source. "
            "Employee navigation execution_id may be null; this is not a lineage audit."
        ),
    }
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "output_sha256": sha256(args.output.read_bytes()).hexdigest(),
                "accepted_inputs_checked": sum(
                    case["accepted_inputs_checked"] for case in result["cases"]
                ),
                "all_cases_completed": all(case["complete_case"] for case in result["cases"]),
            }
        )
    )


if __name__ == "__main__":
    main()
