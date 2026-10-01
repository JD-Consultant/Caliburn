"""Per run: which turn first wrote a JD task, and how many task/area/collaborator/condition/capability edits each turn made.

Usage: timeline.py <version> [<version> ...]   (reads eval JSON for job_file_id, queries the isolated eval schema)
"""
import glob
import json
import sys

import psycopg

sys.stdout.reconfigure(encoding="utf-8")
URL = "postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test"
DIR = r"S:\caliburn\.research-tmp\eval"
SHORT = {
    "edit_tasks": "T", "edit_areas": "A", "edit_collaborators": "C", "edit_conditions": "K", "edit_capabilities": "S",
    "revise_profile": "P",
}

import os

SCHEMA = os.environ.get("EVAL_SCHEMA", "eval_a")
with psycopg.connect(URL, autocommit=True, options=f"-c search_path={SCHEMA} -c default_transaction_read_only=on") as conn:
    for version in sys.argv[1:]:
        for path in sorted(glob.glob(f"{DIR}\{version}-*-?.json")):
            run = json.load(open(path, encoding="utf-8"))
            rows = conn.execute(
                "select row_number() over (order by e.created_at) as turn, "
                "coalesce(string_agg(o.kind, ',' order by o.created_at) filter (where o.kind <> 'edit_sources' and o.kind <> 'adopt_candidate' and o.kind <> 'discard_candidate'), '') as ops, "
                "(select count(*) from execution_outbound_attempts a where a.execution_id = e.execution_id and a.kind not like '%%count%%') as requests "
                "from executions e left join jd_operations o on o.candidate_execution_id = e.execution_id "
                "where e.job_file_id = %s and e.kind = 'consultant_turn' group by e.execution_id, e.created_at order by e.created_at",
                (run["job_file_id"],),
            ).fetchall()
            first_task = next((t for t, ops, _ in rows if "edit_tasks" in ops.split(",")), None)
            cells = []
            for turn, ops, requests in rows:
                letters = "".join(sorted(SHORT.get(op, "?") for op in ops.split(",") if op))
                cells.append(f"{turn}:{letters or '-'}({requests})")
            name = path.split("\\")[-1].removesuffix(".json")
            print(f"{name:22s} first_task_turn={first_task} | " + " ".join(cells))
