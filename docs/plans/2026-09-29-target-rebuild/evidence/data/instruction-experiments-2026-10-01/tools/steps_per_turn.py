"""Model calls per A turn and Memory batches per run, for one or more versions.

Usage: steps_per_turn.py <version> [<version> ...] [--schema eval_b]
A heavy turn shows up as a high maximum; the mean is the usual cost driver. Read-only.
"""

import glob
import json
import statistics
import sys

import psycopg

sys.stdout.reconfigure(encoding="utf-8")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
schema = "eval_b"
URL = "postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test"
with psycopg.connect(URL, autocommit=True, options=f"-c search_path={schema} -c default_transaction_read_only=on") as conn:
    for version in args:
        print(f"== {version}")
        for path in sorted(glob.glob(rf"S:\caliburn\.research-tmp\eval\{version}-*-?.json")):
            run = json.load(open(path, encoding="utf-8"))
            rows = conn.execute(
                "select e.kind, count(a.attempt_id) filter (where a.kind = 'model') "
                "from executions e left join execution_outbound_attempts a on a.execution_id = e.execution_id "
                "where e.job_file_id = %s group by e.execution_id, e.kind, e.created_at order by e.created_at",
                (run["job_file_id"],),
            ).fetchall()
            turns = [n for kind, n in rows if kind == "consultant_turn"]
            batches = [n for kind, n in rows if kind == "memory_batch"]
            print(
                f"{run['persona']:<13}{run['label']:<8} A turns {len(turns):>2}: model calls mean {statistics.mean(turns):5.1f} "
                f"max {max(turns):>3} total {sum(turns):>3} | Memory batches {len(batches)}: calls total {sum(batches):>3}"
            )
