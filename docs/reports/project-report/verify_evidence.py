"""Read-only checks of report tables against preserved synthetic experiment data.

Run with Python 3.13+ from any directory. No network, database, credentials or
generated files. This checks transcription and arithmetic, not semantic quality.
"""

import csv
import hashlib
import json
from pathlib import Path
from statistics import mean

REPORT_DIR = Path(__file__).resolve().parent
DATA_DIR = REPORT_DIR.parents[1] / "experiments/product-validation/data"
COMPARISON_DIR = DATA_DIR / "instruction-experiments-2026-10-01"
SOURCE_DIR = DATA_DIR / "runtime-probes-2026-10-01/sources"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check_archive_hashes() -> int:
    entries = (COMPARISON_DIR / "runs/SHA256SUMS.txt").read_text().splitlines()
    for entry in entries:
        expected, name = entry.split(maxsplit=1)
        path = COMPARISON_DIR / "runs" / name.strip()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
    return len(entries)


def check_comparison_tables(report: str) -> dict:
    with (COMPARISON_DIR / "metrics.csv").open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 24
    for row in rows:
        version, persona = row["version"], row["persona"]
        number = row["run"].rsplit("-", 1)[1]
        run = read_json(COMPARISON_DIR / f"runs/{version}-{persona}-{number}.json")
        tasks = run["jd"]["work"]["tasks"]
        assert int(row["turns_completed"]) == sum(
            turn.get("status") == "completed" for turn in run["turns"]
        )
        assert int(row["tasks"]) == len(tasks)
        assert int(row["max_task_chars"]) == max(len(task["description"]) for task in tasks)
        assert int(row["capabilities"]) == len(run["jd"]["work"]["capabilities"])
        assert int(row["citations_checked"]) == run["checks"]["citations"]["checked"]
        assert int(row["citations_unsupported"]) == len(run["checks"]["citations"]["unsupported"])
        purpose = bool(run["jd"]["profile"].get("purpose"))
        assert purpose == (row["purpose_written"] == "True")
        persona_label = "課程" if persona == "course_admin" else "倉庫"
        label = f"{version.replace('q', 'Q')}-{persona_label}-{number}"
        facets = len([key for key in row["hidden_aspects_asked"].split(";") if key])
        first = [
            label,
            row["turns_completed"],
            str(facets),
            "有" if purpose else "無",
            row["tasks"],
            row["max_task_chars"],
        ]
        second = [
            label,
            f"{row['near_copy_details']}/{row['details_total']}",
            row["capabilities"],
            row["capabilities_restating_task"],
            row["citations_checked"],
            row["citations_unsupported"],
        ]
        for cells in (first, second):
            assert f"| {' | '.join(cells)} |" in report, cells
    summaries = {}
    for version in ("q1", "q2", "q2b", "q3"):
        group = [row for row in rows if row["version"] == version]
        course = [row for row in group if row["persona"] == "course_admin"]
        summaries[version] = {
            "completed_turns": sum(int(row["turns_completed"]) for row in group),
            "facets_total": sum(
                len([key for key in row["hidden_aspects_asked"].split(";") if key]) for row in group
            ),
            "course_tasks_mean": mean(int(row["tasks"]) for row in course),
            "course_max_chars_mean": mean(int(row["max_task_chars"]) for row in course),
            **{
                field: sum(int(row[field]) for row in group)
                for field in (
                    "near_copy_details",
                    "details_total",
                    "capabilities",
                    "capabilities_restating_task",
                    "citations_checked",
                    "citations_unsupported",
                )
            },
        }
    assert summaries["q1"]["near_copy_details"] == 36
    assert summaries["q1"]["details_total"] == 95
    assert summaries["q3"]["near_copy_details"] == 15
    assert summaries["q3"]["details_total"] == 75
    assert summaries["q3"]["facets_total"] == 13
    assert summaries["q2"]["capabilities_restating_task"] == 20
    assert summaries["q2"]["capabilities"] == 37
    return summaries


def check_source_recheck(report: str) -> dict:
    names_and_hashes = (
        (
            "source-only-recheck-luna-20261001.json",
            "6d739c480a35f15058a771a7ce8d82aa5091603b8c15e2f9b19825a44184a991",
        ),
        (
            "source-only-recheck-luna-audit-20261001.json",
            "4d6416ed271b6242ea633e2126b7f84e743d0fc3a916712dafc424332eecf956",
        ),
    )
    for name, expected in names_and_hashes:
        assert hashlib.sha256((SOURCE_DIR / name).read_bytes()).hexdigest() == expected, name
    run = read_json(SOURCE_DIR / "source-only-recheck-luna-20261001.json")
    audit = read_json(SOURCE_DIR / "source-only-recheck-luna-audit-20261001.json")
    assert run["status"]["status"] == "completed"
    assert run["elapsed_seconds"] == 33.64
    assert audit["reopened_jd_matches"] is True
    assert len(audit["requests"]) == len(audit["responses"]) == 6
    assert len({item["app_data_sha256"] for item in audit["requests"]}) == 1
    for index, (request, response) in enumerate(
        zip(audit["requests"], audit["responses"], strict=True), start=1
    ):
        usage = response["usage"]
        assert response["status"] == "completed" and response["model"] == "gpt-6-luna"
        assert (
            f"| {index} | {request['items']} | {usage['input_tokens']:,} | "
            f"{usage['output_tokens']:,} |"
        ) in report
    calls = audit["calls"]
    assert [call["name"] for call in calls] == [
        "read_jd",
        "read_work_situation_map",
        "read_work_understanding_map",
        "read_interview",
        "read_jd",
        "read_work_situation",
        "read_work_understanding",
        "read_jd_changes",
        "revise_jd_item",
        "read_jd",
    ]
    assert calls[3]["arguments"]["query"] == {
        "kind": "range",
        "start_sequence": 6,
        "end_sequence": 8,
    }
    assert calls[7]["arguments"]["query"]["kind"] == "source"
    assert len(calls[7]["output"]) == 1066
    assert "新增訪談引用序號：8" in calls[7]["output"]
    assert [change["action"] for change in calls[8]["arguments"]["changes"]] == [
        "set_field",
        "remove_source",
        "add_source",
        "confirm_reference_alignment",
    ]
    for point in ("before", "after"):
        assert run[point]["work"]["tasks"][0]["description"] in report
        assert audit["source_chains"][point][0]["understanding"]["content"]["body"] in report
    interview = next(
        item for item in run["before"]["interviews"]["messages"] if item["interview_sequence"] == 8
    )
    assert run["input"] in report and interview["interview_text"] in report
    old = audit["source_chains"]["before"][0]["reference"]
    new = audit["source_chains"]["after"][0]["reference"]
    assert old["citation_id"] == new["citation_id"]
    assert old["source"]["snapshot_id"] != new["source"]["snapshot_id"]
    assert new["source"]["snapshot_id"] == run["setup"]["new_snapshot"]
    references = run["after"]["sources"]["references"]
    assert len(references) == 2 and all(not ref["needs_recheck"] for ref in references)
    totals = {
        key: sum(item["usage"][key] for item in audit["responses"])
        for key in ("input_tokens", "output_tokens")
    }
    assert totals == {"input_tokens": 83809, "output_tokens": 1727}
    return {
        "requests": 6,
        "tool_calls": len(calls),
        **totals,
        "archive_hashes_checked": len(names_and_hashes),
    }


def main() -> None:
    report = (REPORT_DIR / "report.md").read_text(encoding="utf-8")
    result = {
        "archive_hashes_checked": check_archive_hashes(),
        "comparison_rows_checked": 24,
        "report_table_rows_checked": 48,
        "comparison": check_comparison_tables(report),
        "source_recheck": check_source_recheck(report),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
