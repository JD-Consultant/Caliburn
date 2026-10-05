"""Read-only transcription checks for report tables B-28 through B-30.

Run from any directory with Python 3.10+. Uses only preserved local JSON and the
standard library. No network, database, model calls or generated files. These
checks preserve historical model judgments and incomplete relevance labels;
they do not establish semantic correctness, full-corpus recall or fresh speed.
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPORT_DIR = Path(__file__).resolve().parent
EXPERIMENTS = REPORT_DIR.parents[1] / "experiments"


def read_json(relative: str) -> dict | list:
    return json.loads((EXPERIMENTS / relative).read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def table_rows(report: str, number: int) -> list[list[str]]:
    caption = f"表 B-{number}"
    require(report.count(caption) == 1, f"Expected one caption: {caption}")
    tail = report.split(caption, 1)[1]
    lines = tail.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("|"))
    rows = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    require(len(rows) >= 3, f"Missing data rows in B-{number}")
    require(
        all(re.fullmatch(r":?-+:?", cell) for cell in rows[1]),
        f"Invalid separator in B-{number}",
    )
    return rows[2:]


def equal_rows(report: str, number: int, expected: list[list[str]]) -> None:
    actual = table_rows(report, number)
    require(len(actual) == len(expected), f"B-{number} row count differs")
    for index, (observed, source) in enumerate(zip(actual, expected), 1):
        require(
            observed == source,
            f"B-{number} row {index}: report={observed!r}, source={source!r}",
        )


def ratio(retained: int, total: int) -> str:
    return f"{retained}／{total}"


def check_depth_table(report: str) -> dict:
    dual = read_json("2026-10-05-b1-dual-route-retrieval/run-01/summary.json")
    depth = read_json("2026-10-05-initial-retrieval-depth/run-01/summary.json")
    dual_by_key = {(row["variant"], row["depth_each_route"]): row for row in dual}
    depth_by_key = {(row["variant"], row["depth_each_route"]): row for row in depth}
    selection = [
        ("O", 20, "原話整合"),
        ("O", 40, "原話整合"),
        ("O", 80, "原話整合"),
        ("B1-W", 20, "B1 情境整合"),
        ("B1-W", 40, "B1 情境整合"),
        ("B1-S", 40, "B1 逐情境"),
        ("B2-S", 20, "B2 逐理解"),
        ("B2-S", 40, "B2 逐理解"),
    ]
    expected = []
    for variant, n, label in selection:
        row = dual_by_key[variant, n]
        require(
            row["known_targets_total"] == 12 and row["known_facets_total"] == 8,
            "Known-target denominators changed",
        )
        require(
            row["clear_targets_total"] == 10 and row["unassessed_cases"] == ["H01"],
            "Sensitivity or unassessed-case scope changed",
        )
        if variant in ("O", "B2-S"):
            old = depth_by_key["O" if variant == "O" else "B2", n]
            require(
                row["query_parent_pair_workload"] == old["rerank_pair_workload"],
                f"Independent depth summaries differ for {variant}/{n}",
            )
            require(
                row["known_targets_retained"] == old["known_grade3"]["retained"],
                f"Known targets differ for {variant}/{n}",
            )
            require(
                row["known_facets_retained"] == old["known_work_facets"]["retained"],
                f"Known facets differ for {variant}/{n}",
            )
        expected.append(
            [
                label,
                str(row["query_count"]),
                str(n),
                ratio(row["known_targets_retained"], row["known_targets_total"]),
                ratio(row["known_facets_retained"], row["known_facets_total"]),
                f"{row['query_parent_pair_workload']:,}",
            ]
        )
    equal_rows(report, 28, expected)
    multiple = (
        dual_by_key["B1-S", 40]["query_parent_pair_workload"]
        / dual_by_key["B1-W", 40]["query_parent_pair_workload"]
    )
    require(f"{multiple:.2f} 倍" in report, "B1 workload multiple missing or incorrect")
    return {
        "rows": len(expected),
        "b1_query_pair_multiple": multiple,
        "known_pairs": 12,
        "known_facets": 8,
        "unassessed_case": "H01",
    }


def check_selection_table(report: str) -> dict:
    composed = read_json(
        "2026-10-05-adaptive-reference-selection/run-01/composed-summary.json"
    )
    by_id = {row["id"]: row for row in composed}
    selection = [
        ("DT_fixed_20::top5", "D20／T20 → 前五（實作控制）"),
        ("DT_fixed_D5_T20::top5", "D5／T20 → 前五（探索）"),
        ("DT_fixed_D5_T20::absolute_-4_cap5", "D5／T20 → logit ≥ −4、最多五份（探索）"),
        ("T_fixed_20::absolute_-4_cap5", "T20 → logit ≥ −4、最多五份（面向優先探索）"),
    ]
    expected = []
    for policy_id, label in selection:
        row = by_id[policy_id]
        require(row["grades"]["ungraded"] == 0, f"Unassessed output: {policy_id}")
        require(
            sum(row["grades"].values()) == row["selected_count"],
            f"Grade counts do not sum to outputs: {policy_id}",
        )
        expected.append(
            [
                label,
                str(row["candidate_pairs"]),
                str(row["selected_count"]),
                *(str(row["grades"][str(grade)]) for grade in range(4)),
                ratio(row["known_facets_supported"], row["known_facets_total"]),
            ]
        )
    equal_rows(report, 29, expected)
    baseline = by_id[selection[0][0]]
    candidate = by_id[selection[2][0]]
    decrease = (
        100
        * (baseline["candidate_pairs"] - candidate["candidate_pairs"])
        / baseline["candidate_pairs"]
    )
    require(
        f"{decrease:.1f}%" in report, "Candidate-pair reduction missing or incorrect"
    )
    eligible = [
        row
        for row in composed
        if row["final_policy"]["limit"] <= 5 and row["grades"]["ungraded"] == 0
    ]
    sensitivity_full = [
        row for row in eligible if row["sensitivity"]["known_facets_supported"] == 8
    ]
    zero_weak = [
        row for row in eligible if row["grades"]["0"] + row["grades"]["1"] == 0
    ]
    addendum = read_json(
        "2026-10-05-adaptive-reference-selection/main-work-addendum-01/summary.json"
    )
    require(
        len(composed) == addendum["all_combinations"] == 7038,
        "Configuration count differs",
    )
    require(
        len(eligible) == addendum["eligible_universe"] == 3325,
        "Eligible configuration count differs",
    )
    require(
        "3,325" in report and "最後沒有未評來源" in report,
        "Report must retain the eligibility scope of the sensitivity finding",
    )
    require(len(sensitivity_full) == 0, "Eligible sensitivity coverage result differs")
    require(
        len(zero_weak) == 817
        and max(row["known_facets_supported"] for row in zero_weak) == 5,
        "Zero-weak-reference coverage result differs",
    )
    all_sensitivity_full = sum(
        row["sensitivity"]["known_facets_supported"] == 8 for row in composed
    )
    require(all_sensitivity_full == 20, "Unrestricted sensitivity control differs")
    return {
        "rows": len(expected),
        "candidate_pair_reduction_percent": decrease,
        "all_configurations": len(composed),
        "eligible_configurations": len(eligible),
        "eligible_sensitivity_full_coverage": len(sensitivity_full),
        "unrestricted_sensitivity_full_coverage": all_sensitivity_full,
        "zero_weak_max_known_facets": 5,
    }


def check_negation_table(report: str) -> dict:
    summary = read_json("2026-10-05-negated-work-retrieval/run-01/summary.json")
    rows = {(row["case_id"], row["variant"]): row for row in summary["rows"]}
    expected = []
    in_top5 = 0
    for case_id, label in [
        ("N01", "SEO"),
        ("N02", "帳務案例中的採購"),
        ("N03", "倉庫案例中的採購"),
    ]:
        base, denied = rows[case_id, "base"], rows[case_id, "no_short"]
        require(
            denied["document_cosine"] > base["document_cosine"],
            f"Dense delta differs: {case_id}",
        )
        require(
            denied["rerank_logit"] > base["rerank_logit"],
            f"Logit delta differs: {case_id}",
        )
        require(
            base["own_rerank_rank"] is None,
            f"Baseline unexpectedly recalled probe: {case_id}",
        )
        in_top5 += denied["probe_in_top5"]
        expected.append(
            [
                label,
                f"{base['document_cosine']:.4f}",
                f"{denied['document_cosine']:.4f}",
                f"{base['document_parent_rank']} → {denied['document_parent_rank']}",
                str(denied["own_rerank_rank"]),
            ]
        )
    equal_rows(report, 30, expected)
    require(len(summary["rows"]) == 24 and in_top5 == 2, "Negation count differs")
    return {
        "rows": len(expected),
        "variant_results": len(summary["rows"]),
        "short_negation_probe_in_top5": in_top5,
        "interpretation": (
            "Three fixed contrasts, not an estimated employee failure rate"
        ),
    }


def check_section_links(report: str) -> int:
    sections = [
        report.split("### 6.3 ", 1)[1].split("### 6.4 ", 1)[0],
        report.split("### B.14 ", 1)[1],
    ]
    count = 0
    for section in sections:
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", section):
            url = urlsplit(target)
            if url.scheme or not url.path:
                continue
            path = (REPORT_DIR / unquote(url.path)).resolve()
            require(path.is_file(), f"Missing local evidence link: {target}")
            count += 1
    return count


def verify_report(report: str) -> dict:
    return {
        "scope": (
            "Local source transcription and arithmetic only; incomplete qrels "
            "and historical model grades preserved"
        ),
        "table_B28": check_depth_table(report),
        "table_B29": check_selection_table(report),
        "table_B30": check_negation_table(report),
        "local_evidence_links_checked": check_section_links(report),
        "not_verified": [
            "semantic truth",
            "full-corpus recall",
            "fresh latency",
            "consultant or JD quality",
        ],
    }


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = verify_report((REPORT_DIR / "report.md").read_text(encoding="utf-8"))
    print(json.dumps(result, ensure_ascii=False, indent=2))
