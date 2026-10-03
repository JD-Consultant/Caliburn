"""One native decision-point replay; no business tools or database writes.

Dynamic JSON is confined to saved provider snapshots and research artifacts. The
production request adapter validates the exact outgoing protocol. This is not a
replacement agent runtime. See protocol.md for the pre-registered bounds.
"""

import argparse
import asyncio
import hashlib
import json
import platform
import subprocess
import time
from copy import deepcopy
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import psycopg
from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.adapters.openai_responses import (
    ResponseRequest,
    count_response_input,
    create_response,
    create_responses_client,
)
from caliburn.diagnostics.checkpoints import read_checkpoint_records
from openai import APIError

HERE = Path(__file__).resolve().parent
ROOT = next(parent for parent in HERE.parents if (parent / "AGENTS.md").is_file())
JOB_FILE = UUID("d2b47271-8f0e-4967-a2f2-73d61883ac68")
EXECUTION = UUID("814f3e99-5100-4785-b913-6c3fd1380b04")
RESPONSE_ID = "resp_0dfb1aa7d876747c016ac077e778dc87d0ba3bed399d7c4ab6"
DATABASE_URL = "postgresql://caliburn_test@127.0.0.1:55439/caliburn_target_demo"
ORIGINAL_REVIEW_RULE = """- JD 人工更改不自動成為工作事實；來源待核對或內容有衝突時要重評。
  只有確實核對現有文字與目前可見依據後才確認引用對齊；讀過或重加來源不等於核對完成。"""
ORDER = ("baseline", "candidate", "candidate", "baseline", "baseline", "candidate")


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def make_candidate(snapshot: dict[str, Any], replacement: str) -> dict[str, Any]:
    if snapshot["instructions"].count(ORIGINAL_REVIEW_RULE) != 1:
        raise ValueError("Expected the saved review rule exactly once")
    candidate = deepcopy(snapshot)
    candidate["instructions"] = candidate["instructions"].replace(
        ORIGINAL_REVIEW_RULE, replacement
    )
    return candidate


def public_copy(value: Any) -> Any:
    """Only exports are redacted; never use the result as a native model request."""
    if isinstance(value, dict):
        return {
            key: "[omitted]" if key == "encrypted_content" else public_copy(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [public_copy(item) for item in value]
    return value


def save_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(public_copy(value), handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def read_native_case() -> tuple[dict[str, Any], dict[str, Any]]:
    with psycopg.connect(
        DATABASE_URL,
        autocommit=True,
        connect_timeout=5,
        options=(
            "-c default_transaction_read_only=on -c statement_timeout=20000 "
            "-c search_path=caliburn"
        ),
    ) as connection:
        records = list(
            read_checkpoint_records(
                connection, job_file_id=JOB_FILE, execution_id=EXECUTION
            )
        )
    records.sort(
        key=lambda row: (
            row["checkpoint_time"],
            row["checkpoint_id"],
            row["source"] == "pending_write",
        )
    )
    for record in records:
        values = record["values"]
        response = values.get("response_snapshot")
        if isinstance(response, dict) and response.get("id") == RESPONSE_ID:
            snapshot = values["request_snapshot"]
            if snapshot["model"] != "gpt-6-luna" or len(snapshot["input"]) != 255:
                raise ValueError(
                    "Saved case differs from the registered decision point"
                )
            ResponseRequest.from_snapshot(snapshot)
            return snapshot, response
    raise ValueError(
        "The registered native request is unavailable; do not reconstruct it"
    )


def read_demo_state() -> dict[str, Any]:
    base = f"http://127.0.0.1:8100/api/job-files/{JOB_FILE}"
    with httpx.Client(timeout=15, follow_redirects=False) as client:
        state = {}
        for route in (
            "jd/work",
            "jd/sources",
            "interviews",
            "consultant-turns/current",
        ):
            response = client.get(f"{base}/{route}")
            response.raise_for_status()
            state[route] = response.json()
    return state


async def run(args: argparse.Namespace) -> None:
    if not args.run_label or any(
        c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in args.run_label
    ):
        raise ValueError("run-label must be a lowercase hyphenated name")
    snapshots = {}
    snapshots["baseline"], original_response = await asyncio.to_thread(read_native_case)
    snapshots["candidate"] = make_candidate(
        snapshots["baseline"],
        (HERE / "candidate-review-rule.txt").read_text(encoding="utf-8").strip(),
    )
    baseline_hash = digest(snapshots["baseline"])
    if args.execute and args.expected_request_sha != baseline_hash:
        raise ValueError("Paid replay requires the exact preflight request hash")
    requests = {
        name: ResponseRequest.from_snapshot(value) for name, value in snapshots.items()
    }
    before = await asyncio.to_thread(read_demo_state)
    if before["consultant-turns/current"].get("turn") is not None:
        raise ValueError("The recording file has an active Turn; leave it alone")
    destination = HERE / args.run_label
    destination.mkdir(exist_ok=False)
    manifest = {
        "registered_at": datetime.now(UTC).isoformat(),
        "execute": args.execute,
        "job_file_id": str(JOB_FILE),
        "execution_id": str(EXECUTION),
        "original_response_id": RESPONSE_ID,
        "git_head": (
            await asyncio.to_thread(
                subprocess.check_output,
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                text=True,
            )
        ).strip(),
        "python": platform.python_version(),
        "openai": version("openai"),
        "psycopg": version("psycopg"),
        "order": ORDER,
        "requests_sha256": {name: digest(value) for name, value in snapshots.items()},
        "input_sha256": digest(snapshots["baseline"]["input"]),
        "tools_sha256": digest(snapshots["baseline"]["tools"]),
        "before_sha256": digest(before),
        "artifact_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                HERE / "replay.py",
                HERE / "protocol.md",
                HERE / "candidate-review-rule.txt",
                ROOT / "apps/api/src/caliburn/adapters/openai_responses.py",
                ROOT / "apps/api/src/caliburn/adapters/response_streaming.py",
            )
        },
    }
    save_json(destination / "manifest.json", manifest)
    save_json(destination / "baseline-request-public.json", snapshots["baseline"])
    save_json(destination / "original-response-public.json", original_response)
    save_json(destination / "demo-before.json", before)
    print(
        json.dumps({"request_sha256": baseline_hash, "execute": args.execute}),
        flush=True,
    )
    if not args.execute:
        return

    completed = 0
    failure = None
    try:
        async with create_responses_client(
            api_key=read_openai_api_key(ROOT / "apps/api/.env"), timeout_seconds=90
        ) as client:
            counts = {}
            for name, request in requests.items():
                async with asyncio.timeout(120):
                    count = await count_response_input(client, request)
                counts[name] = count.input_tokens
                save_json(
                    destination / f"count-{name}.json", count.model_dump(mode="json")
                )
                if count.input_tokens > 90000:
                    raise ValueError("Input exceeds the registered capacity bound")
            for ordinal, name in enumerate(ORDER, start=1):
                started = time.monotonic()
                save_json(
                    destination / f"attempt-{ordinal:02d}.json",
                    {
                        "arm": name,
                        "started_at": datetime.now(UTC).isoformat(),
                        "request_sha256": digest(snapshots[name]),
                    },
                )
                async with asyncio.timeout(120):
                    response = await create_response(client, requests[name])
                snapshot = response.model_dump(mode="json", exclude_none=True)
                result = {
                    "ordinal": ordinal,
                    "arm": name,
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "response": snapshot,
                }
                save_json(destination / f"response-{ordinal:02d}.json", result)
                completed += 1
                print(
                    json.dumps(
                        {
                            "ordinal": ordinal,
                            "arm": name,
                            "status": response.status,
                            "tools": [
                                item.get("name")
                                for item in snapshot["output"]
                                if item["type"] == "function_call"
                            ],
                            "usage": snapshot.get("usage"),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                if response.status != "completed":
                    raise ValueError("Incomplete response; stop rather than retry")
    except (APIError, TimeoutError, ValueError) as error:
        # Do not dump HTTP bodies, credentials, native items or exception strings.
        failure = {
            "type": type(error).__name__,
            "status_code": getattr(error, "status_code", None),
        }
        save_json(destination / "failure.json", failure)
        print(json.dumps({"stopped": failure}), flush=True)
    finally:
        after = await asyncio.to_thread(read_demo_state)
        save_json(destination / "demo-after.json", after)
        save_json(
            destination / "outcome.json",
            {
                "responses_saved": completed,
                "failure": failure,
                "demo_unchanged": digest(before) == digest(after),
                "after_sha256": digest(after),
                "business_tools_executed": 0,
            },
        )
    if failure:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-label", required=True)
    parser.add_argument(
        "--execute", action="store_true", help="Make the pre-registered paid requests"
    )
    parser.add_argument("--expected-request-sha")
    asyncio.run(run(parser.parse_args()))
