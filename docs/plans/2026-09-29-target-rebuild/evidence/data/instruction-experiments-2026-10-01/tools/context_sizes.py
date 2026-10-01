"""Provider-counted request sizes per execution of one job file, from the saved checkpoints.

Usage: context_sizes.py <result.json | job_file_id> [schema]
Reads the msgpack `input_count` channel of every saved checkpoint (read-only). Prints, in creation
order, one line per execution: kind, status, number of counted requests, max counted input tokens,
and compaction attempts. The totals show how the A and B histories grew and when compaction fired.
"""

import json
import sys
from collections import defaultdict

import ormsgpack
import psycopg

sys.stdout.reconfigure(encoding="utf-8")
target = sys.argv[1]
schema = sys.argv[2] if len(sys.argv) > 2 else "eval_b"
file_id = json.load(open(target, encoding="utf-8"))["job_file_id"] if target.endswith(".json") else target
URL = "postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test"


def decode(blob: bytes) -> dict:
    return ormsgpack.unpackb(blob, ext_hook=lambda code, data: data, option=ormsgpack.OPT_NON_STR_KEYS)


with psycopg.connect(URL, autocommit=True, options=f"-c search_path={schema} -c default_transaction_read_only=on") as conn:
    executions = conn.execute(
        "select e.execution_id::text, e.kind, e.status, e.created_at, "
        "count(a.attempt_id) filter (where a.kind = 'model'), count(a.attempt_id) filter (where a.kind = 'compaction') "
        "from executions e left join execution_outbound_attempts a on a.execution_id = e.execution_id "
        "where e.job_file_id = %s group by 1,2,3,4 order by e.created_at",
        (file_id,),
    ).fetchall()
    sizes: dict[str, list[int]] = defaultdict(list)
    for thread_id, blob in conn.execute(
        "select thread_id, blob from checkpoint_blobs where thread_id like %s and channel = 'input_count'",
        (f"{file_id}:%",),
    ):
        parts = thread_id.split(":")
        if len(parts) >= 2:
            sizes[parts[1]].append(int(decode(bytes(blob))["input_tokens"]))

per_kind: dict[str, list[int]] = defaultdict(list)
print(f"{'#':>3} {'kind':<18} {'status':<10} {'model':>5} {'compact':>7} {'counts':>6} {'max_input_tokens':>16}")
for number, (execution_id, kind, status, created, models, compactions) in enumerate(executions, 1):
    counted = sizes.get(execution_id, [])
    top = max(counted) if counted else 0
    per_kind[kind].append(top)
    print(f"{number:>3} {kind:<18} {status:<10} {models:>5} {compactions:>7} {len(counted):>6} {top:>16}")
print()
for kind, values in per_kind.items():
    print(f"{kind}: executions {len(values)}, max request {max(values)}, last {values[-1]}")
