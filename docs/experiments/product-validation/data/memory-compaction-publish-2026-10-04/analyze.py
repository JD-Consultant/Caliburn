"""Read fixed published objects back; no model, writes, schema cleanup or regrading."""

import argparse
import asyncio
import hashlib
import json
import os
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import psycopg
from caliburn.adapters.database import Database
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.settings import DatabaseSettings
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from psycopg.conninfo import conninfo_to_dict


def document(value):
    if is_dataclass(value):
        return document(asdict(value))
    if isinstance(value, dict):
        return {key: document(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = sorted(value, key=str) if isinstance(value, (set, frozenset)) else value
        return [document(item) for item in items]
    if isinstance(value, UUID):
        return str(value)
    return value


async def read_fixed(candidates, snapshot):
    # The original driver serialized sets as repr. Preserve that raw result and
    # derive a structured public-query readback, without repeating any model work.
    objects = []
    for layer in MemoryLayer:
        entries = await candidates.read_snapshot_map(
            snapshot.job_file_id, snapshot.snapshot_id, layer
        )
        for entry in entries:
            objects.append(
                document(
                    await candidates.read_snapshot_object(
                        snapshot.job_file_id, snapshot.snapshot_id, entry.object_id
                    )
                )
            )
    return {"objects": objects}


async def analyze(run_dir: Path, url: str) -> None:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    settings = DatabaseSettings(url=url, schema=manifest["schema"])
    info = conninfo_to_dict(url)
    if info.get("host") not in ("127.0.0.1", "localhost", "::1") or not info.get(
        "dbname", ""
    ).endswith("_test"):
        raise ValueError("Only explicit loopback test database permitted")
    rows = [
        json.loads(line)
        for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    traces = [
        json.loads(line)
        for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    groups = defaultdict(
        lambda: {
            "model_calls": 0,
            "compactions": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
        }
    )
    compaction_handoffs = []
    for index, trace in enumerate(traces):
        if trace["event"] != "response":
            continue
        group = groups[(trace["arm"], trace["batch"])]
        payload = trace["payload"]
        if trace["path"].endswith("/responses"):
            group["model_calls"] += 1
        if trace["path"].endswith("/compact"):
            group["compactions"] += 1
            next_generation = next(
                item
                for item in traces[index + 1 :]
                if item["event"] == "request" and item["path"].endswith("/responses")
            )
            output = payload["output"]
            compaction_handoffs.append(
                {
                    "arm": trace["arm"],
                    "batch": trace["batch"],
                    "full_output_prefix_preserved": next_generation["payload"]["input"][
                        : len(output)
                    ]
                    == output,
                }
            )
        usage = payload.get("usage")
        if usage:
            group["input_tokens"] += usage["input_tokens"]
            group["output_tokens"] += usage["output_tokens"]
            group["cached_tokens"] += usage.get("input_tokens_details", {}).get(
                "cached_tokens", 0
            )
    database = Database(settings)
    readbacks = []
    try:
        candidates = MemoryCandidateWorkflow(database.sessions)
        for row in rows:
            fixed = row["fixed"]
            snapshot = SimpleNamespace(
                job_file_id=UUID(fixed["snapshot"]["job_file_id"]),
                snapshot_id=UUID(fixed["snapshot"]["snapshot_id"]),
            )
            structured = await read_fixed(candidates, snapshot)
            actual = {item["object_id"]: item for item in structured["objects"]}
            selected_revisions = {
                key: item["revision_id"] for key, item in actual.items()
            }
            exact_content = all(
                actual[item["object_id"]]["content"] == item["content"]
                and selected_revisions[item["object_id"]] == item["revision_id"]
                for item in fixed["objects"]
            ) and len(actual) == len(fixed["objects"])
            coherent = all(
                selected_revisions.get(ref["object_id"]) == ref["revision_id"]
                for item in actual.values()
                for ref in item["work_situation_references"]
            )
            with psycopg.connect(
                url,
                options=f"-c search_path={settings.schema} -c default_transaction_read_only=on",
            ) as connection:
                sources = {
                    str(source): sequence
                    for source, sequence in connection.execute(
                        "SELECT source_id,interview_sequence FROM formal_interviews WHERE job_file_id=%s AND interview_sequence <= %s",
                        (
                            snapshot.job_file_id,
                            fixed["snapshot"]["covered_through_sequence"],
                        ),
                    ).fetchall()
                }
            valid_sources = all(
                source in sources
                for item in actual.values()
                for source in item["interview_references"]
            )
            for item in structured["objects"]:
                item["interview_sequences"] = [
                    sources[source] for source in item["interview_references"]
                ]
            readbacks.append(
                {
                    "arm": row["arm"],
                    "batch": row["batch"],
                    "snapshot": fixed["snapshot"],
                    "content_and_revision_unchanged": exact_content,
                    "fixed_chain_coherent": coherent,
                    "sources_within_frontier": valid_sources,
                    **structured,
                }
            )
    finally:
        await database.close()
    summary = {
        "published_batches": len(rows),
        "all_reentries_no_outbound": all(row["reentry_no_outbound"] for row in rows),
        "all_old_snapshots_unchanged": all(
            row["old_snapshot_unchanged"] for row in rows
        ),
        "all_role_heads_adopted": all(
            role["head_matches_completed"]
            for row in rows
            for role in row["role_history"].values()
        ),
        "readback_checks": [
            {
                key: row[key]
                for key in (
                    "arm",
                    "batch",
                    "content_and_revision_unchanged",
                    "fixed_chain_coherent",
                    "sources_within_frontier",
                )
            }
            for row in readbacks
        ],
        "compaction_handoffs": compaction_handoffs,
        "groups": [
            {"arm": key[0], "batch": key[1], **value}
            for key, value in sorted(groups.items())
        ],
        "source_hashes": {
            name: hashlib.sha256((run_dir / name).read_bytes()).hexdigest()
            for name in ("manifest.json", "results.jsonl", "trace.jsonl", "run.jsonl")
        },
        "analysis_script_sha256": hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
    }
    for name, content in (("readback.json", readbacks), ("summary.json", summary)):
        (run_dir / name).write_text(
            json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    asyncio.run(
        analyze(args.run, os.environ["CALIBURN_TEST_DATABASE_URL"]),
        loop_factory=asyncio.SelectorEventLoop,
    )
