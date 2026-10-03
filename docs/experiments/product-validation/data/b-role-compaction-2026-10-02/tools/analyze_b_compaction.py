"""K1-K5 of the T16 section 12 observation: B1/B2 pre-batch compaction in a real interview. Read-only.

Usage: analyze_b_compaction.py <job_file_id | result.json> [schema]
Per Memory batch: status, outbound attempts by kind and failure code; per role, the counted
`prepared_history` size, whether the provider's compaction was adopted (decoded from the saved
checkpoint), its usage, and the sizes of the requests that followed; then every published
snapshot with the Memory object titles (for the manual continuity read, K3).
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
ROLES = {"work_situation_analyst": "B1", "work_understanding_analyst": "B2", "job_consultant": "A"}


def decode(blob: bytes):
    return ormsgpack.unpackb(blob, ext_hook=lambda code, data: data, option=ormsgpack.OPT_NON_STR_KEYS)


def find_usage(value, found=None):
    """Collect every integer under a key named *_tokens inside the compaction snapshot."""
    found = {} if found is None else found
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, int) and str(key).endswith("tokens"):
                found.setdefault(str(key), item)
            else:
                find_usage(item, found)
    elif isinstance(value, list):
        for item in value:
            find_usage(item, found)
    return found


def item_types(value):
    output = value.get("output") if isinstance(value, dict) else None
    if isinstance(output, list):
        counted: dict[str, int] = {}
        for item in output:
            name = str(item.get("type")) if isinstance(item, dict) else "?"
            counted[name] = counted.get(name, 0) + 1
        return counted
    return {}


with psycopg.connect(URL, autocommit=True, options=f"-c search_path={schema} -c default_transaction_read_only=on") as conn:
    batches = conn.execute(
        "select execution_id::text, status, created_at from executions "
        "where job_file_id=%s and kind='memory_batch' order by created_at", (file_id,)
    ).fetchall()
    index = {execution_id: number for number, (execution_id, _, _) in enumerate(batches, 1)}
    print(f"job file {file_id}: {len(batches)} Memory batches")
    for number, (execution_id, status, created) in enumerate(batches, 1):
        kinds = conn.execute(
            "select kind, count(*), count(*) filter (where failure_code is not null), "
            "string_agg(distinct failure_code, ',') from execution_outbound_attempts "
            "where execution_id=%s group by 1 order by 1", (execution_id,)
        ).fetchall()
        print(f"  batch {number} {status:<10} {created:%H:%M:%S} attempts(kind,n,failed,codes)={kinds}")
    print()
    rows = conn.execute(
        "select thread_id, channel, blob from checkpoint_blobs where thread_id like %s "
        "and channel in ('input_count','compaction_snapshot','compaction_attempt_id') order by thread_id",
        (f"{file_id}:%",),
    ).fetchall()
    per_thread = defaultdict(lambda: defaultdict(list))
    for thread_id, channel, blob in rows:
        parts = thread_id.split(":")
        if len(parts) < 4 or parts[1] not in index or parts[2] not in ROLES:
            continue
        per_thread[(index[parts[1]], parts[2], ":".join(parts[3:5]))][channel].append(decode(bytes(blob)))
    print("K1/K2/K5: per batch and role (counted tokens; compaction adopted?)")
    for (number, role, kind), channels in sorted(per_thread.items()):
        counts = [int(c["input_tokens"]) for c in channels.get("input_count", [])]
        snapshots = channels.get("compaction_snapshot", [])
        line = f"  batch {number} {ROLES[role]} {kind[:26]:<26} counts n={len(counts)} min={min(counts) if counts else '-'} max={max(counts) if counts else '-'}"
        if snapshots:
            usage = find_usage(snapshots[-1])
            line += f" | COMPACTION adopted: output items {item_types(snapshots[-1])} usage {usage}"
        print(line)
    adopted = sorted({(number, ROLES[role]) for (number, role, kind), c in per_thread.items() if c.get("compaction_snapshot") and "prepared_history" in kind})
    print("\nK1 compaction adopted at the pre-batch boundary:", adopted or "none")
    print()
    totals = conn.execute(
        "select a.kind, count(*), count(*) filter (where a.failure_code='rate_limited'), "
        "count(*) filter (where a.failure_code is not null and a.failure_code<>'rate_limited'), "
        "round(coalesce(sum(a.reported_cost_usd),0)::numeric,4) "
        "from execution_outbound_attempts a join executions e on e.execution_id=a.execution_id "
        "where e.job_file_id=%s group by 1 order by 1", (file_id,)
    ).fetchall()
    print("all attempts of the file (kind, n, rate_limited, other failures, ledger USD):", totals)
    print("executions:", conn.execute("select kind, status, count(*) from executions where job_file_id=%s group by 1,2 order by 1,2", (file_id,)).fetchall())
    print("\nK3: published snapshots and their Memory objects (titles)")
    for snapshot_id, position_id, covered, created in conn.execute(
        "select snapshot_id, position_id, covered_through_sequence, created_at from memory_snapshots "
        "where job_file_id=%s order by created_at", (file_id,)
    ).fetchall():
        members = conn.execute(
            "select o.layer, r.title from memory_position_members m "
            "join memory_objects o on o.job_file_id=m.job_file_id and o.object_id=m.object_id "
            "join memory_object_revisions r on r.job_file_id=m.job_file_id and r.object_id=m.object_id and r.revision_id=m.revision_id "
            "where m.job_file_id=%s and m.position_id=%s order by o.layer, r.title", (file_id, position_id)
        ).fetchall()
        print(f"  snapshot {created:%H:%M:%S} covers interview sequence {covered}: {len(members)} objects")
        for layer, title in members:
            print(f"     [{layer}] {title}")
