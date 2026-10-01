"""Export the instruction-experiment data pack for the report: raw runs, readable transcripts, metrics.

Usage: export_experiment_pack.py [--schema eval_b]
Reads S:/caliburn/.research-tmp/eval/<version>-<persona>-<n>.json (versions q1, q2, q2b, long) and, for
cost, attempts, model calls and request sizes, the read-only evaluation schema. Writes under
docs/plans/2026-09-29-target-rebuild/evidence/data/instruction-experiments-2026-10-01/:
runs/ (raw JSON, byte-identical copies), transcripts/ (readable Markdown), metrics.csv, summary.txt.
Safe to re-run; it overwrites the generated files only. Everything it reads is synthetic.
"""

import csv
import glob
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import ormsgpack
import psycopg

sys.stdout.reconfigure(encoding="utf-8")
SRC = Path(r"S:\caliburn\.research-tmp\eval")
OUT = Path(
    r"S:\caliburn\docs\plans\2026-09-29-target-rebuild\evidence\data\instruction-experiments-2026-10-01"
)
TOOLS = SRC / "tools"
PYTHON = r"S:\caliburn\apps\api\.venv-target\Scripts\python.exe"
URL = "postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test"
schema = sys.argv[sys.argv.index("--schema") + 1] if "--schema" in sys.argv else "eval_b"
VERSIONS = {
    "q1": ("c0", "d41e75f7 instructions (baseline)"),
    "q2": ("c1", "ec3c143a"),
    "q2b": ("c1b", "4b9da041"),
    "q3": ("c3", "1e9edcea"),
    "long": ("final", "see long-journey section"),
}
HIDDEN = {"limits", "quality_roster", "risk_peak", "tools", "physical", "license"}


def grams(text: str) -> set[str]:
    text = re.sub(r"\s+", "", text)
    return {text[i : i + 2] for i in range(len(text) - 1)}


def jd_markdown(run: dict) -> str:
    work, profile = run["jd"]["work"], run["jd"]["profile"]
    caps = {c["capability_id"]: c for c in work["capabilities"]}
    links: dict[str, list[str]] = defaultdict(list)
    for link in work.get("task_links", []):
        if link.get("capability_id") in caps:
            links[link["task_id"]].append(caps[link["capability_id"]])
    lines = ["## 最終 JD（正式稿）", ""]
    lines += [f"- **基本資料**：{json.dumps(profile, ensure_ascii=False)}", ""]
    areas = {a["area_id"]: a for a in work["areas"]}
    by_area: dict[str | None, list[dict]] = defaultdict(list)
    for task in work["tasks"]:
        by_area[task.get("area_id")].append(task)
    for area_id, tasks in by_area.items():
        area = areas.get(area_id)
        lines.append(f"### 職責：{area['title']}" if area else "### （未歸屬）")
        if area and area.get("scope_text"):
            lines.append(area["scope_text"])
        for task in tasks:
            lines.append(f"- **{task['title']}**：{task['description']}")
            for detail in task["outcomes"]:
                lines.append(f"  - 成果：{detail['text']}")
            for detail in task["requirements"]:
                lines.append(f"  - 要求：{detail['text']}")
            for cap in links.get(task["task_id"], []):
                lines.append(f"  - 能力［{cap['kind']}］：{cap['name']}")
        lines.append("")
    lines.append("### 知識／技能")
    lines += [f"- ［{c['kind']}］{c['name']}：{c.get('description') or ''}" for c in work["capabilities"]] or ["（無）"]
    lines += ["", "### 協作對象"]
    lines += [f"- **{p.get('name')}**：{p.get('scope_text') or ''}" for p in work["collaborators"]] or ["（無）"]
    lines += ["", "### 條件"]
    lines += [f"- ［{c['kind']}］{c['text']}" for c in work["conditions"]] or ["（無）"]
    return "\n".join(lines)


def transcript_markdown(run: dict, version: str, instruction: str, commit: str) -> str:
    out = [
        f"# {version} · {run['persona']} · {run['label']}",
        "",
        f"- 指引：{instruction}（{commit}）；人設：`{run['persona']}`；開始：{run['started']}；職務檔案：`{run['job_file_id']}`",
        f"- 事件：{json.dumps(run.get('events', []), ensure_ascii=False)}",
        "- 全部為合成資料（員工由模擬模型依人設回答）。",
        "",
        "## 逐字稿（公開訪談）",
        "",
    ]
    for turn in run["turns"]:
        out.append(f"### 第 {turn['turn']} 輪（{turn.get('status')}，{turn.get('seconds')} 秒）")
        out += ["", f"**員工**：{turn.get('employee')}", "", f"**顧問**：{turn.get('consultant')}", ""]
    out.append(jd_markdown(run))
    checks = run["checks"]
    out += [
        "",
        "## 自動檢查（粗略標記檢查，不取代人工閱讀）",
        "",
        "```json",
        json.dumps({k: v for k, v in checks.items() if k != "facts"}, ensure_ascii=False, indent=1),
        "```",
    ]
    return "\n".join(out) + "\n"


def decode(blob: bytes) -> dict:
    return ormsgpack.unpackb(blob, ext_hook=lambda code, data: data, option=ormsgpack.OPT_NON_STR_KEYS)


def database_metrics(conn: psycopg.Connection, file_id: str) -> dict:
    executions = conn.execute(
        "select e.execution_id::text, e.kind, e.status, "
        "count(a.attempt_id) filter (where a.kind = 'model'), "
        "count(a.attempt_id) filter (where a.kind = 'compaction'), "
        "count(a.attempt_id), count(a.attempt_id) filter (where a.failure_code is not null), "
        "coalesce(sum(a.reported_cost_usd), 0)::float "
        "from executions e left join execution_outbound_attempts a on a.execution_id = e.execution_id "
        "where e.job_file_id = %s group by 1,2,3,e.created_at order by e.created_at",
        (file_id,),
    ).fetchall()
    sizes: dict[str, int] = defaultdict(int)
    totals: dict[str, int] = defaultdict(int)
    for thread_id, blob in conn.execute(
        "select thread_id, blob from checkpoint_blobs where thread_id like %s and channel = 'input_count'",
        (f"{file_id}:%",),
    ):
        parts = thread_id.split(":")
        if len(parts) >= 2:
            tokens = int(decode(bytes(blob))["input_tokens"])
            sizes[parts[1]] = max(sizes[parts[1]], tokens)
            totals[parts[1]] += tokens
    a_calls = [e[3] for e in executions if e[1] == "consultant_turn"]
    memory = [e for e in executions if e[1] == "memory_batch"]
    return {
        "executions_not_completed": sum(e[2] != "completed" for e in executions),
        "a_turns": len(a_calls),
        "a_model_calls": sum(a_calls),
        "a_max_calls_in_a_turn": max(a_calls, default=0),
        "memory_batches": len(memory),
        "memory_model_calls": sum(e[3] for e in memory),
        "compactions": sum(e[4] for e in executions),
        "attempts": sum(e[5] for e in executions),
        "failed_attempts": sum(e[6] for e in executions),
        "cost_usd": round(sum(e[7] for e in executions), 4),
        "counted_input_tokens_a": sum(totals[e[0]] for e in executions if e[1] == "consultant_turn"),
        "counted_input_tokens_memory": sum(totals[e[0]] for e in memory),
        "max_a_request_tokens": max((sizes[e[0]] for e in executions if e[1] == "consultant_turn"), default=0),
        "max_memory_request_tokens": max((sizes[e[0]] for e in memory), default=0),
    }


def run_metrics(run: dict, db: dict) -> dict:
    work, checks = run["jd"]["work"], run["checks"]
    near = total = 0
    for task in work["tasks"]:
        base = grams(task["title"] + task["description"])
        for detail in task["outcomes"] + task["requirements"]:
            mine = grams(detail["text"])
            if mine:
                total += 1
                near += len(mine & base) / len(mine) >= 0.7
    restating = sum(
        max(
            (len(grams(c["name"]) & grams(t["title"] + t["description"])) / max(1, len(grams(c["name"]))) for t in work["tasks"]),
            default=0,
        )
        >= 0.6
        for c in work["capabilities"]
    )
    correction = checks["correction"]
    return {
        "persona": run["persona"],
        "run": run["label"],
        "turns": len(run["turns"]),
        "turns_completed": sum(t.get("status") == "completed" for t in run["turns"]),
        "minutes": round(sum(t.get("seconds") or 0 for t in run["turns"]) / 60, 1),
        "areas": checks["shape"]["areas"],
        "tasks": checks["shape"]["tasks"],
        "max_task_chars": max((len(t["description"]) for t in work["tasks"]), default=0),
        "outcomes": checks["shape"]["outcomes"],
        "requirements": checks["shape"]["requirements"],
        "capabilities": checks["shape"]["capabilities"],
        "capabilities_restating_task": restating,
        "collaborators": checks["shape"]["collaborator_items"],
        "conditions": checks["shape"]["condition_items"],
        "near_copy_details": near,
        "details_total": total,
        "purpose_written": bool(run["jd"]["profile"].get("purpose")),
        "hidden_aspects_asked": ";".join(sorted(k for k, v in checks["facts"].items() if k in HIDDEN and v["surfaced"])),
        "elicitation_gaps": ";".join(checks["elicitation_gaps"]),
        "recording_gaps": ";".join(checks["recording_gaps"]),
        "questions_per_turn": checks["style"]["questions_per_turn"],
        "chars_per_turn": checks["style"]["mean_consultant_chars"],
        "leading_phrases": checks["style"]["leading_phrases"],
        "citations_checked": checks["citations"]["checked"],
        "citations_unsupported": len(checks["citations"]["unsupported"]),
        "correction_effective": correction["new_present"] and correction["old_left_as_current"] == 0 and all(correction["unchanged_kept"]),
        **db,
        "job_file_id": run["job_file_id"],
    }


def main() -> None:
    (OUT / "runs").mkdir(parents=True, exist_ok=True)
    (OUT / "transcripts").mkdir(parents=True, exist_ok=True)
    rows = []
    with psycopg.connect(URL, autocommit=True, options=f"-c search_path={schema} -c default_transaction_read_only=on") as conn:
        for version, (instruction, commit) in VERSIONS.items():
            for path in sorted(glob.glob(str(SRC / f"{version}-*-?.json")) + glob.glob(str(SRC / f"{version}-*-??.json"))):
                source = Path(path)
                run = json.loads(source.read_text(encoding="utf-8"))
                shutil.copyfile(source, OUT / "runs" / source.name)
                if source.with_suffix(".pdf").exists():
                    shutil.copyfile(source.with_suffix(".pdf"), OUT / "runs" / source.with_suffix(".pdf").name)
                (OUT / "transcripts" / source.with_suffix(".md").name).write_text(
                    transcript_markdown(run, version, instruction, commit), encoding="utf-8"
                )
                row = {"version": version, "instruction": instruction, "instruction_commit": commit, **run_metrics(run, database_metrics(conn, run["job_file_id"]))}
                row["counted_input_tokens_per_minute"] = round((row["counted_input_tokens_a"] + row["counted_input_tokens_memory"]) / max(row["minutes"], 0.1))
                rows.append(row)
    with (OUT / "metrics.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [f"runs exported: {len(rows)}"]
    for version in VERSIONS:
        group = [r for r in rows if r["version"] == version]
        if group:
            lines.append(
                f"{version}: n={len(group)}, tasks mean {statistics.mean(r['tasks'] for r in group):.2f}, "
                f"capabilities mean {statistics.mean(r['capabilities'] for r in group):.2f}, minutes mean {statistics.mean(r['minutes'] for r in group):.1f}, "
                f"cost sum US${sum(r['cost_usd'] for r in group):.3f}, failed attempts {sum(r['failed_attempts'] for r in group)}/{sum(r['attempts'] for r in group)}"
            )
    for base, cand, extra in (("q1", "q2", []), ("q1", "q2b", ["--supplemental"]), ("q1", "q3", ["--supplemental"])):
        if any(r["version"] == cand for r in rows):
            result = subprocess.run([PYTHON, "-B", str(TOOLS / "compare_versions.py"), base, cand, *extra], capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONUTF8": "1"})
            lines += ["", f"=== compare_versions.py {base} {cand} {' '.join(extra)}", result.stdout.strip() or result.stderr.strip()]
    (OUT / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    sums = [
        f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.name}\n"
        for f in sorted((OUT / "runs").iterdir())
        if f.suffix in (".json", ".pdf")
    ]
    (OUT / "runs" / "SHA256SUMS.txt").write_bytes("".join(sums).encode("utf-8"))
    print("\n".join(lines[:8]))


main()
