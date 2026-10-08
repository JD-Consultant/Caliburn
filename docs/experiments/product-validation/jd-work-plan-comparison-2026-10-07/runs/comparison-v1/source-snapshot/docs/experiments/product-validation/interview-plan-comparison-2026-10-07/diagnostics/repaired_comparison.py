"""One repaired comparison revision; reuse the original HTTP journey and finite guard."""

import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

from completion_batch_v2 import (
    ARTIFACT_ROOT,
    DEADLINE,
    HERE,
    LIMITS,
    ROOT,
    SCHEDULED,
    carried_guard,
    file_hash,
    read_json,
    validate_accounting,
)

sys.path.insert(0, str(HERE))
from guard import digest, role

REPAIRED_ROOT = ARTIFACT_ROOT / "repaired-comparison"
SMOKE = ARTIFACT_ROOT / "note-tool-smoke/note-smoke-repair-20261007"
RECEIPT_SHA = "850e1b4e643a40a68ea11464b23c18f3109834d3f8e22201e3b756747201acf6"
P1_PROOF = ARTIFACT_ROOT / "operational-evidence/repaired-p1-reuse-proof.json"
P1_PROOF_SHA = "22ccc65476cb887a9ffcd6f6eece15d21f5e76410e0af251d3c18c4a237441fc"
REPAIR_MODULE = "apps/api/src/caliburn/transport/model_tools/interview_plans.py"
RETAINED = ["warehouse-r1-P1", "course_admin-r1-P1"]
FRESH = [name for name in SCHEDULED if name not in RETAINED]


def require_closed_listener():
    command = (
        "$ErrorActionPreference='Stop'; "
        "$listeners=@(Get-NetTCPConnection -State Listen -ErrorAction Stop "
        "| Where-Object {$_.LocalPort -eq 8177}); "
        "@{count=$listeners.Count} | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode != 0 or result.stderr.strip():
            raise RuntimeError("Official listener query failed")
        data = json.loads(result.stdout)
        if (
            not isinstance(data, dict)
            or set(data) != {"count"}
            or type(data["count"]) is not int
            or data["count"] < 0
        ):
            raise RuntimeError("Invalid official listener inventory")
    except (OSError, subprocess.TimeoutExpired, ValueError) as error:
        raise RuntimeError("Cannot establish prior server is closed") from error
    if data["count"] != 0:
        raise RuntimeError("Prior server listener is still active")


def checkpoint_stage(thread_id, values):
    if values.get("adopted") is not True or values.get("compaction_snapshot") is None:
        return "unknown"
    policy = values.get("preparation_policy", "missing")
    if isinstance(policy, dict) and thread_id.endswith(":job_consultant:prepared_history"):
        return "pre-work"
    if (
        policy is None
        and ":job_consultant:completed_work:compact:" in thread_id
        and role(values.get("request_snapshot", {})) == "A"
    ):
        return "mid-work"
    return "unknown"


def read_gate():
    """Require the actual completed smoke and existing P1 byte-equivalence evidence."""
    from manifest import source_hashes

    from caliburn.agents.job_consultant.instructions import CONSULTANT_INSTRUCTIONS
    from caliburn.agents.job_consultant.planning_instructions import FOCUS_INSTRUCTIONS
    from caliburn.agents.job_consultant.tools import consultant_tool_definitions

    receipt_path = SMOKE / "semantic-receipt.json"
    if file_hash(receipt_path) != RECEIPT_SHA or file_hash(P1_PROOF) != P1_PROOF_SHA:
        raise ValueError("Actual repair smoke or P1 proof is missing/changed")
    receipt = read_json(receipt_path)
    if (
        receipt["passed"] is not True
        or receipt["reviewer"] != "/root"
        or receipt["completed_turns"] != 2
        or receipt["successful_edits"] != 3
        or not receipt["checks"]
        or any(value is not True for value in receipt["checks"].values())
    ):
        raise ValueError("Actual repair semantic review did not pass")
    evidence = {str(receipt_path): RECEIPT_SHA, str(P1_PROOF): P1_PROOF_SHA}
    for item in receipt["artifacts"]:
        path = Path(item["path"])
        if path.parent != SMOKE or file_hash(path) != item["sha256"]:
            raise ValueError("Actual smoke artifacts changed")
        evidence[str(path)] = item["sha256"]
    manifest = read_json(SMOKE / "manifest.json")
    ledger = read_json(SMOKE / "final-ledger.json")
    if (
        manifest["offline_only"] is not False
        or manifest["runtime"] != "3.14.7"
        or ledger["mechanical_smoke_passed"] is not True
        or ledger["completed_turns"] != 2
        or file_hash(ROOT / REPAIR_MODULE) != manifest["files"][REPAIR_MODULE]
    ):
        raise ValueError("Actual repaired runtime/mechanism evidence does not match")
    prior_path = Path(manifest["prior_path"])
    if file_hash(prior_path) != manifest["prior_sha256"]:
        raise ValueError("Smoke inherited accounting changed")
    evidence[str(prior_path)] = manifest["prior_sha256"]
    audit = SMOKE / "mechanism-audit.json"
    if file_hash(audit) != "9f0797f7f4b2dcf47d1d730618eccafe558affd67848f3d289a9d60151745103":
        raise ValueError("Actual repair mechanism audit changed")
    evidence[str(audit)] = file_hash(audit)
    prior = validate_accounting(ledger["guard"], manifest["prior_guard"])
    for turn in [1, 2]:
        if read_json(SMOKE / f"turn-{turn:02d}-status.json")["status"] != "completed":
            raise ValueError("Actual repair Turn did not complete")
    if not any(
        json.loads(line).get("event") == "admitted"
        for line in (SMOKE / "provider-trace.jsonl").read_text(encoding="utf-8").splitlines()
    ):
        raise ValueError("Repair smoke did not actually call the provider")
    current = source_hashes()
    proof = read_json(P1_PROOF)

    def encode(value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    instructions = (CONSULTANT_INSTRUCTIONS + "\n\n" + FOCUS_INSTRUCTIONS).encode("utf-8")
    tools = encode(consultant_tool_definitions(interview_plans_enabled=False))
    for case in proof["cases"]:
        directory = Path(case["case"])
        for name in ["manifest.json", "result.json", "provider-trace.jsonl"]:
            path = directory.parent / name if name == "manifest.json" else directory / name
            if (
                file_hash(path)
                != case[
                    name.replace(".jsonl", "").replace(".json", "").replace("-", "_") + "_sha256"
                ]
            ):
                raise ValueError("Retained P1 original changed")
            evidence[str(path)] = file_hash(path)
        old = read_json(directory.parent / "manifest.json")["source_sha256"]
        changed = {path for path in set(old) | set(current) if old.get(path) != current.get(path)}
        if (
            changed != {REPAIR_MODULE}
            or sha256(instructions).hexdigest() != case["instructions_utf8_sha256"]
            or sha256(tools).hexdigest() != case["ordered_tools_serialized_sha256"]
        ):
            raise ValueError("P1 payload/source equivalence no longer holds")
    return prior, {
        "retained_completed_cases": RETAINED,
        "new_scheduled_cases": FRESH,
        "prior_accounting": prior,
        "prior_evidence_sha256": evidence,
        "smoke_semantic_scope": receipt["scope"],
        "smoke_limitations": receipt["limitations"],
    }


def bind_case_observers(run_batch, guard, directory):
    """Defer the original pressure-release callback until official C adoption is saved."""
    from caliburn.adapters.openai_responses import ResponseRequest
    from caliburn.agent_execution.context_compaction import read_compacted_window

    base_transport, base_saver = run_batch.GuardedTransport, run_batch.ObservedSaver
    release = []
    released = False

    class RecordedTransport(base_transport):
        def __init__(self, current_guard, *args, **kwargs):
            if not release:
                release.append(current_guard.on_a_compact)
                current_guard.on_a_compact = lambda: None
            super().__init__(current_guard, *args, **kwargs)

    class AdoptedSaver(base_saver):
        async def aput(self, config, checkpoint, metadata, new_versions):
            nonlocal released
            result = await super().aput(config, checkpoint, metadata, new_versions)
            values = checkpoint["channel_values"]
            if (
                values.get("compaction_snapshot") is None
                or role(values.get("request_snapshot", {})) != "A"
            ):
                return result
            thread = config["configurable"]["thread_id"]
            stage = checkpoint_stage(thread, values)
            verified = False
            if stage == "mid-work":
                await read_compacted_window(
                    self,
                    thread_id=thread,
                    checkpoint_id=checkpoint["id"],
                    request=ResponseRequest.from_snapshot(values["request_snapshot"]),
                    input_count=values["input_count"],
                )
                verified = True
                if not released:
                    if not release:
                        raise ValueError("Mid-work adoption has no original pressure callback")
                    release[0]()
                    released = True
            with (directory / "pressure-adoption.jsonl").open("a", encoding="utf-8") as output:
                output.write(
                    json.dumps(
                        {
                            "thread_id": thread,
                            "checkpoint_id": checkpoint["id"],
                            "stage": stage,
                            "adopted": values.get("adopted"),
                            "official_saver_acknowledged": True,
                            "saved_midwork_read_verified": verified,
                            "pressure_released": released,
                            "parent_input_sha256": digest(
                                values.get("request_snapshot", {}).get("input", [])
                            ),
                        }
                    )
                    + "\n"
                )
            return result

    run_batch.GuardedTransport, run_batch.ObservedSaver = RecordedTransport, AdoptedSaver
    return base_transport, base_saver


def verify_revision(data):
    from manifest import verify

    verify(data)
    for relative, expected in data["revision_source_sha256"].items():
        if file_hash(ROOT / relative) != expected:
            raise RuntimeError("Repaired comparison entry changed")
    for path, expected in data["continuation"]["prior_evidence_sha256"].items():
        if file_hash(Path(path)) != expected:
            raise RuntimeError("Repaired comparison evidence changed")


def freeze_revision(path, note):
    from manifest import freeze

    data = freeze("formal", path)
    extras = [
        Path(__file__),
        Path(__file__).with_name("test_repaired_comparison.py"),
        Path(__file__).with_name("repaired-comparison-protocol.md"),
        Path(__file__).with_name("completion_batch_v2.py"),
        HERE / "append_stream.py",
    ]
    hashes = {}
    for source in extras:
        relative = source.relative_to(ROOT).as_posix()
        target = path.parent / "source-snapshot" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        hashes[relative] = file_hash(source)
    data.update(
        {
            "limits": LIMITS,
            "absolute_deadline_utc": DEADLINE.isoformat(),
            "continuation": note,
            "revision_source_sha256": hashes,
            "revision": "P2 body-diff guidance repair; 2 equivalent P1 retained, 6 fresh",
            "controlled_repeat_2": (
                "45000 until actual official saved/read-verified A mid-work C adoption; "
                "pre-work C cannot release"
            ),
        }
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


async def main():
    import argparse
    import platform
    import re

    import guard as experiment_guard
    import run_batch
    from append_stream import OwnedObservedStream

    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-name", default="formal-repaired-v2")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if re.fullmatch(r"[a-z][a-z0-9_-]{0,60}", args.batch_name) is None:
        raise ValueError("Invalid repaired batch name")
    prior, note = read_gate()
    guard = carried_guard(prior)
    if args.dry_run:
        print(
            json.dumps(
                {
                    "provider_calls": 0,
                    "credential_read": False,
                    "retained": RETAINED,
                    "fresh": FRESH,
                    "prior_accounting": prior,
                    "deadline": DEADLINE.isoformat(),
                    "limits": LIMITS,
                }
            )
        )
        return
    if platform.python_version() != "3.14.7" or run_batch.HERE != HERE:
        raise RuntimeError("Original repaired runtime/driver route changed")
    require_closed_listener()
    directory = REPAIRED_ROOT / args.batch_name
    directory.mkdir(parents=True)
    run_batch.HERE = REPAIRED_ROOT
    data = freeze_revision(directory / "manifest.json", note)
    guard.verify_frozen = lambda: verify_revision(data)
    experiment_guard.ObservedStream = OwnedObservedStream
    verify_revision(data)
    print(
        json.dumps(
            {
                "launch_directory": str(directory),
                "manifest_sha256": file_hash(directory / "manifest.json"),
            }
        ),
        flush=True,
    )
    completed = list(RETAINED)
    processed = []
    try:
        for name in FRESH:
            if guard.stop_reason:
                break
            profile, repeat, group = name.rsplit("-", 2)
            case = directory / name
            original = bind_case_observers(run_batch, guard, case)
            try:
                await run_batch.run_case(
                    "formal", profile, group, int(repeat[1:]), case, guard, data, 20
                )
            finally:
                run_batch.GuardedTransport, run_batch.ObservedSaver = original
            processed.append(name)
            result = read_json(case / "result.json")
            if result["closure_submitted"] and result["turns"][-1]["status"] == "completed":
                completed.append(name)
            run_batch.save(
                directory / "batch-state.json",
                {
                    "completed_cases": completed,
                    "processed_new_cases": processed,
                    "guard": guard.state(),
                },
            )
    finally:
        run_batch.save(
            directory / "batch-state.json",
            {
                "completed_cases": completed,
                "processed_new_cases": processed,
                "all_scheduled_cases": SCHEDULED,
                "new_scheduled_cases": FRESH,
                "guard": guard.state(),
            },
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
