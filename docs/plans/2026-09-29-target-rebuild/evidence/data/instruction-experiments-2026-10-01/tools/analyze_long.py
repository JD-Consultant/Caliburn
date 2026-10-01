"""Quantitative summary of one long simulated interview. Usage: analyze_long.py <result.json> [schema]"""

import json
import os
import statistics
import sys

import psycopg

sys.stdout.reconfigure(encoding="utf-8")
path = sys.argv[1]
schema = sys.argv[2] if len(sys.argv) > 2 else "eval_b"
run = json.load(open(path, encoding="utf-8"))
turns = [t for t in run["turns"] if t.get("seconds")]
secs = [t["seconds"] for t in turns]
print(f"{path}: persona {run['persona']}, {len(run['turns'])} turns ({sum(t['status']=='completed' for t in run['turns'])} completed)")
print(f"seconds/turn: mean {statistics.mean(secs):.0f}, median {statistics.median(secs):.0f}, max {max(secs):.0f}; first 10 mean {statistics.mean(secs[:10]):.0f}, last 10 mean {statistics.mean(secs[-10:]):.0f}")
print("events:", json.dumps(run.get("events", []), ensure_ascii=False))
print("turn statuses:", {st: sum(t.get("status") == st for t in run["turns"]) for st in {t.get("status") for t in run["turns"]}})
shape = run["checks"]["shape"]
print("shape:", shape)
print("citations:", {k: v for k, v in run["checks"]["citations"].items() if k != "unsupported"}, "unsupported:", run["checks"]["citations"]["unsupported"][:5])
print("recording gaps:", run["checks"]["recording_gaps"], "| elicitation gaps:", run["checks"]["elicitation_gaps"])
print("correction:", run["checks"]["correction"])
print("late correction:", run["checks"].get("late_correction"))
work = run["jd"]["work"]
print("human edit preserved? purpose:", run["jd"]["profile"].get("purpose"))
print("human task present?", any("人工" in t["title"] for t in work["tasks"]))
sizes = [len(t["description"]) for t in work["tasks"]]
print("task description chars: max", max(sizes) if sizes else 0, "mean", round(statistics.mean(sizes)) if sizes else 0)

URL = "postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test"
with psycopg.connect(URL, autocommit=True, options=f"-c search_path={schema} -c default_transaction_read_only=on") as conn:
    fid = run["job_file_id"]
    rows = conn.execute(
        "select e.kind, e.status, count(distinct e.execution_id), count(a.attempt_id) filter (where a.kind='model'), "
        "count(a.attempt_id) filter (where a.kind='compaction'), count(*) filter (where a.failure_code is not null), "
        "round(coalesce(sum(a.reported_cost_usd),0)::numeric, 3) "
        "from executions e left join execution_outbound_attempts a on a.execution_id=e.execution_id where e.job_file_id=%s group by 1,2 order by 1,2",
        (fid,),
    ).fetchall()
    print("executions (kind, status, n, model attempts, compactions, failed attempts, est USD):")
    for r in rows:
        print("  ", r)
    print("failure codes:", conn.execute("select a.failure_code, count(*) from execution_outbound_attempts a join executions e on e.execution_id=a.execution_id where e.job_file_id=%s and a.failure_code is not null group by 1", (fid,)).fetchall())
    print("memory snapshots:", conn.execute("select count(*), max(covered_through_sequence) from memory_snapshots where job_file_id=%s", (fid,)).fetchone())
    print("memory ops:", conn.execute("select kind, count(*) from memory_operations where job_file_id=%s group by 1 order by 2 desc", (fid,)).fetchall())
    print("formal frontier:", conn.execute("select max(interview_sequence) from formal_interviews where job_file_id=%s", (fid,)).fetchone())
    print("checkpoint bytes (all threads of this file, KiB):", conn.execute(
        "select round((coalesce((select sum(length(blob)) from checkpoint_blobs where thread_id like %s),0) + coalesce((select sum(length(blob)) from checkpoint_writes where thread_id like %s),0))/1024.0)",
        (f"{fid}:%", f"{fid}:%"),
    ).fetchone())
