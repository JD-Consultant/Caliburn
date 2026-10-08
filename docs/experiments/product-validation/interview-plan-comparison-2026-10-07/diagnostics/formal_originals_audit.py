"""Match actual accepted source IDs to saved formal HTTP employee bodies, read-only."""

import json
import sys
from hashlib import sha256
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify_turn(command, accepted, messages):
    if command["command_id"] != accepted["command_id"]:
        raise ValueError("Actual input and accepted command IDs differ")
    matches = [item for item in messages if item["source_id"] == accepted["source_id"]]
    if len(matches) != 1:
        raise ValueError("The current accepted source must occur exactly once in formal HTTP data")
    actual = matches[0]
    if actual["speaker"] != "employee":
        raise ValueError("The current accepted source is not an employee original")
    if actual["interview_text"] != command["text"]:
        raise ValueError("Formal employee text differs from the actual submitted input")
    return {
        "command_id": accepted["command_id"],
        "accepted_source_id": accepted["source_id"],
        "execution_id": accepted["execution_id"],
        "formal_employee_navigation_execution_id": actual["execution_id"],
        "formal_interview_sequence": actual["interview_sequence"],
        "employee_text_sha256": sha256(command["text"].encode()).hexdigest(),
        "same_accepted_source_employee_exact_text": True,
        "earlier_same_text_source_ids": [
            item["source_id"]
            for item in messages
            if item["speaker"] == "employee"
            and item["interview_text"] == command["text"]
            and item["interview_sequence"] < actual["interview_sequence"]
        ],
    }


def collect(audit_path):
    audit = read(audit_path)
    hashes = {str(audit_path): sha256(audit_path.read_bytes()).hexdigest()}
    rows = []
    for scope in audit["scope"]:
        directory = Path(scope)
        paths = [directory / "formal-interviews.json", directory / "initial-interviews.json"]
        formal, initial = (read(path)["messages"] for path in paths)
        initial_ids = {item["source_id"] for item in initial}
        accepted_ids, sequences, job_files = set(), [], set()
        case_rows = []
        for accepted_path in sorted(directory.glob("turn-*-accepted.json")):
            command_path = accepted_path.with_name(
                accepted_path.name.replace("-accepted", "-input")
            )
            paths.extend([command_path, accepted_path])
            command, accepted = read(command_path), read(accepted_path)
            source_id = accepted["source_id"]
            if source_id in initial_ids or source_id in accepted_ids:
                raise ValueError("A current accepted source is initial or reused across Turns")
            witness = verify_turn(command, accepted, formal)
            accepted_ids.add(source_id)
            job_files.add(accepted["job_file_id"])
            sequences.append(witness["formal_interview_sequence"])
            case_rows.append(
                {"case_path": str(directory), "turn": int(accepted_path.name[5:7]), **witness}
            )
        if len(job_files) != 1 or any(
            a >= b for a, b in zip(sequences, sequences[1:], strict=False)
        ):
            raise ValueError("Actual inputs do not form one job file's strictly ordered originals")
        current_employee_ids = {
            item["source_id"] for item in formal if item["speaker"] == "employee"
        } - initial_ids
        if current_employee_ids != accepted_ids:
            raise ValueError("Formal employee IDs differ from actual accepted input IDs")
        rows.extend(case_rows)
        for path in paths:
            hashes[str(path)] = sha256(path.read_bytes()).hexdigest()
    by_source = {(row["case_path"], row["accepted_source_id"]): row for row in rows}
    selected = []
    for row in audit["rows"]:
        current = by_source[(str(Path(row["case_path"])), row["accepted_source_id"])]
        if current["turn"] != row["answer_turn"]:
            raise ValueError("Independent disclosure audit and accepted Turn positions disagree")
        selected.append(current["accepted_source_id"])
    return {
        "scope": audit["scope"],
        "status": "All actual input/accepted IDs match exact formal HTTP employee originals",
        "actual_accepted_inputs_checked": len(rows),
        "independent_selected_answer_rows_checked": len(selected),
        "rows_with_earlier_same_text_sources": sum(
            bool(row["earlier_same_text_source_ids"]) for row in rows
        ),
        "rows": rows,
        "source_hashes": hashes,
        "collector_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "limits": (
            "Saved formal HTTP data only; no new HTTP, key, provider, DB, JD, "
            "notes or blind review. "
            "This is a preservation check, not a semantic disclosure-policy or JD quality judgment."
        ),
        "formal_execution_id_contract": (
            "Public history execution_id is consultant reply navigation and is null for employee "
            "originals; accepted execution lineage is checked by the independent binding audit."
        ),
    }


def main():
    audit, output = Path(sys.argv[1]), Path(sys.argv[2])
    if output.exists():
        raise RuntimeError("Formal original audit evidence already exists")
    result = collect(audit)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key not in {"rows", "source_hashes", "scope"}
            }
            | {"output_sha256": sha256(output.read_bytes()).hexdigest()}
        )
    )


if __name__ == "__main__":
    main()
