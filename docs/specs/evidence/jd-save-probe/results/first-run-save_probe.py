"""P01: fixed Python -> Node -> PostgreSQL JD save/reconciliation probe.

This is an isolated research executable, not a product repository or schema.
It only connects to the dedicated database returned by local_connection.py.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Literal
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from local_connection import DATABASE, load_probe_dsn


ROOT = Path(__file__).resolve().parent
DEFAULT_BRIDGE = ROOT / "node_bridge.mjs"
DEFAULT_FIXTURE = ROOT / "fixture.json"
ENGINE_PROFILE = "platejs@53.3.11/reuseId:true/initialValueIds:always"


class ProbeFailure(RuntimeError):
    pass


class SameOperationDifferentRequest(ProbeFailure):
    pass


class SimulatedTransactionFailure(ProbeFailure):
    pass


class SimulatedLostReply(ProbeFailure):
    pass


@dataclass(frozen=True)
class BridgeSuccess:
    value: list[dict[str, Any]]
    operations: list[dict[str, Any]]
    changed: bool


@dataclass(frozen=True)
class BridgeFailure:
    code: str
    command_index: int | None
    message: str
    durable_effect: Literal["none"]


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def value_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def request_digest(
    *, document_id: str, base_revision: int, commands: list[dict[str, Any]], origin: str
) -> str:
    return value_hash(
        {
            "document_id": document_id,
            "base_revision": base_revision,
            "commands": commands,
            "engine_profile": ENGINE_PROFILE,
            "origin": origin,
        }
    )


def value_counts(value: list[dict[str, Any]]) -> dict[str, Any]:
    elements = texts = characters = 0
    ids: list[str] = []

    def visit(node: Any) -> None:
        nonlocal elements, texts, characters
        if not isinstance(node, dict):
            return
        if isinstance(node.get("text"), str):
            texts += 1
            characters += len(node["text"])
            return
        elements += 1
        if isinstance(node.get("id"), str):
            ids.append(node["id"])
        for child in node.get("children", []):
            visit(child)

    for root in value:
        visit(root)
    return {
        "root_nodes": len(value),
        "elements": elements,
        "text_leaves": texts,
        "characters": characters,
        "ids": len(ids),
        "unique_ids": len(set(ids)),
    }


def run_bridge(
    bridge: Path, value: list[dict[str, Any]], commands: list[dict[str, Any]], *, timeout: float = 20.0
) -> BridgeSuccess | BridgeFailure:
    request = {"value": value, "commands": commands}
    try:
        completed = subprocess.run(
            ["node", str(bridge)],
            input=json.dumps(request, ensure_ascii=False),
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            shell=False,
            cwd=ROOT,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProbeFailure(f"Fixed Node bridge did not complete: {type(error).__name__}") from error
    if completed.returncode != 0:
        raise ProbeFailure(f"Fixed Node bridge exited with code {completed.returncode}")
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ProbeFailure("Fixed Node bridge stdout was not one JSON value") from error
    if not isinstance(response, dict) or type(response.get("ok")) is not bool:
        raise ProbeFailure("Fixed Node bridge returned an invalid envelope")
    if response["ok"]:
        if not isinstance(response.get("value"), list) or not isinstance(response.get("operations"), list):
            raise ProbeFailure("Successful bridge result omitted value or operations")
        if type(response.get("changed")) is not bool:
            raise ProbeFailure("Successful bridge result omitted changed")
        return BridgeSuccess(response["value"], response["operations"], response["changed"])
    error = response.get("error")
    if not isinstance(error, dict) or response.get("durable_effect") != "none":
        raise ProbeFailure("Failed bridge result did not prove its fixed no-durable-effect boundary")
    command_index = error.get("command_index")
    if command_index is not None and type(command_index) is not int:
        raise ProbeFailure("Failed bridge result used an invalid command index")
    if not isinstance(error.get("code"), str) or not isinstance(error.get("message"), str):
        raise ProbeFailure("Failed bridge result omitted its actionable error")
    if "value" in response or "operations" in response:
        raise ProbeFailure("Failed bridge result leaked a partial candidate")
    return BridgeFailure(error["code"], command_index, error["message"], "none")


SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS jd_revision (
        document_id text NOT NULL,
        revision integer NOT NULL CHECK (revision >= 1),
        parent_revision integer,
        value jsonb NOT NULL,
        value_sha256 char(64) NOT NULL,
        engine_profile text NOT NULL,
        origin text NOT NULL CHECK (origin IN ('fixture', 'ai', 'human')),
        operation_id text,
        created_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (document_id, revision),
        FOREIGN KEY (document_id, parent_revision)
            REFERENCES jd_revision (document_id, revision)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS jd_head (
        document_id text PRIMARY KEY,
        revision integer NOT NULL,
        FOREIGN KEY (document_id, revision)
            REFERENCES jd_revision (document_id, revision)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS jd_operation (
        document_id text NOT NULL,
        operation_id text NOT NULL,
        request_digest char(64) NOT NULL,
        base_revision integer NOT NULL,
        status text NOT NULL CHECK (status IN ('committed', 'no_change', 'stale_base')),
        result_revision integer NOT NULL,
        origin text NOT NULL CHECK (origin IN ('ai', 'human')),
        actual_changes jsonb NOT NULL,
        result_value_sha256 char(64) NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (document_id, operation_id),
        FOREIGN KEY (document_id, result_revision)
            REFERENCES jd_revision (document_id, revision)
    )
    """,
)


def connect(dsn: str):
    # Keep transaction scope visible at each write site. This avoids mistaking
    # a released nested savepoint for the durable outer commit under test.
    return psycopg.connect(dsn, row_factory=dict_row, autocommit=True)


def setup_schema(dsn: str) -> None:
    with connect(dsn) as connection:
        for statement in SCHEMA:
            connection.execute(statement)


def bootstrap_document(
    dsn: str, document_id: str, value: list[dict[str, Any]]
) -> dict[str, Any]:
    digest = value_hash(value)
    with connect(dsn) as connection:
        with connection.transaction():
            connection.execute(
                """
                INSERT INTO jd_revision
                    (document_id, revision, parent_revision, value, value_sha256,
                     engine_profile, origin, operation_id)
                VALUES (%s, 1, NULL, %s, %s, %s, 'fixture', NULL)
                """,
                (document_id, Jsonb(value), digest, ENGINE_PROFILE),
            )
            connection.execute(
                "INSERT INTO jd_head (document_id, revision) VALUES (%s, 1)",
                (document_id,),
            )
    return {"document_id": document_id, "revision": 1, "value_sha256": digest}


def counts(dsn: str, document_id: str) -> dict[str, int]:
    with connect(dsn) as connection:
        row = connection.execute(
            """
            SELECT
                (SELECT count(*) FROM jd_head WHERE document_id = %s) AS heads,
                (SELECT count(*) FROM jd_revision WHERE document_id = %s) AS revisions,
                (SELECT count(*) FROM jd_operation WHERE document_id = %s) AS operations
            """,
            (document_id, document_id, document_id),
        ).fetchone()
    return dict(row)


def read_head(dsn: str, document_id: str) -> dict[str, Any]:
    with connect(dsn) as connection:
        row = connection.execute(
            """
            SELECT h.document_id, h.revision, r.parent_revision, r.value,
                   r.value_sha256, r.engine_profile, r.origin, r.operation_id
            FROM jd_head h
            JOIN jd_revision r USING (document_id, revision)
            WHERE h.document_id = %s
            """,
            (document_id,),
        ).fetchone()
    if row is None:
        raise ProbeFailure("Probe document head is missing")
    return dict(row)


def read_operation(dsn: str, document_id: str, operation_id: str) -> dict[str, Any] | None:
    with connect(dsn) as connection:
        row = connection.execute(
            """
            SELECT document_id, operation_id, request_digest, base_revision,
                   status, result_revision, origin, actual_changes,
                   result_value_sha256
            FROM jd_operation
            WHERE document_id = %s AND operation_id = %s
            """,
            (document_id, operation_id),
        ).fetchone()
    return dict(row) if row is not None else None


def operation_or_conflict(
    dsn: str, document_id: str, operation_id: str, digest: str
) -> dict[str, Any] | None:
    existing = read_operation(dsn, document_id, operation_id)
    if existing is not None and existing["request_digest"] != digest:
        raise SameOperationDifferentRequest("Same operation ID belongs to a different request digest")
    return existing


def commit_candidate(
    dsn: str,
    *,
    document_id: str,
    operation_id: str,
    digest: str,
    base_revision: int,
    origin: Literal["ai", "human"],
    candidate: BridgeSuccess,
    fault_at: Literal["after_revision", "after_head"] | None = None,
    lose_reply: bool = False,
) -> dict[str, Any]:
    existing = operation_or_conflict(dsn, document_id, operation_id, digest)
    if existing is not None:
        return existing

    with connect(dsn) as connection, connection.transaction():
        head = connection.execute(
            "SELECT revision FROM jd_head WHERE document_id = %s FOR UPDATE",
            (document_id,),
        ).fetchone()
        if head is None:
            raise ProbeFailure("Probe document head is missing")
        current_revision = head["revision"]
        current = connection.execute(
            """
            SELECT value_sha256 FROM jd_revision
            WHERE document_id = %s AND revision = %s
            """,
            (document_id, current_revision),
        ).fetchone()

        if current_revision != base_revision:
            connection.execute(
                """
                INSERT INTO jd_operation
                    (document_id, operation_id, request_digest, base_revision,
                     status, result_revision, origin, actual_changes,
                     result_value_sha256)
                VALUES (%s, %s, %s, %s, 'stale_base', %s, %s, '[]'::jsonb, %s)
                """,
                (
                    document_id,
                    operation_id,
                    digest,
                    base_revision,
                    current_revision,
                    origin,
                    current["value_sha256"],
                ),
            )
        elif not candidate.changed:
            connection.execute(
                """
                INSERT INTO jd_operation
                    (document_id, operation_id, request_digest, base_revision,
                     status, result_revision, origin, actual_changes,
                     result_value_sha256)
                VALUES (%s, %s, %s, %s, 'no_change', %s, %s, %s, %s)
                """,
                (
                    document_id,
                    operation_id,
                    digest,
                    base_revision,
                    current_revision,
                    origin,
                    Jsonb(candidate.operations),
                    current["value_sha256"],
                ),
            )
        else:
            result_revision = base_revision + 1
            result_hash = value_hash(candidate.value)
            connection.execute(
                """
                INSERT INTO jd_revision
                    (document_id, revision, parent_revision, value, value_sha256,
                     engine_profile, origin, operation_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    document_id,
                    result_revision,
                    base_revision,
                    Jsonb(candidate.value),
                    result_hash,
                    ENGINE_PROFILE,
                    origin,
                    operation_id,
                ),
            )
            if fault_at == "after_revision":
                raise SimulatedTransactionFailure("Injected after revision insert")
            updated = connection.execute(
                """
                UPDATE jd_head SET revision = %s
                WHERE document_id = %s AND revision = %s
                """,
                (result_revision, document_id, base_revision),
            )
            if updated.rowcount != 1:
                raise ProbeFailure("Conditional head update lost its expected base")
            if fault_at == "after_head":
                raise SimulatedTransactionFailure("Injected after conditional head update")
            connection.execute(
                """
                INSERT INTO jd_operation
                    (document_id, operation_id, request_digest, base_revision,
                     status, result_revision, origin, actual_changes,
                     result_value_sha256)
                VALUES (%s, %s, %s, %s, 'committed', %s, %s, %s, %s)
                """,
                (
                    document_id,
                    operation_id,
                    digest,
                    base_revision,
                    result_revision,
                    origin,
                    Jsonb(candidate.operations),
                    result_hash,
                ),
            )

    if lose_reply:
        raise SimulatedLostReply("Injected after commit; caller did not receive the result")
    result = read_operation(dsn, document_id, operation_id)
    if result is None:
        raise ProbeFailure("Committed operation was not readable")
    return result


def execute_operation(
    dsn: str,
    bridge: Path,
    *,
    document_id: str,
    operation_id: str,
    base_revision: int,
    base_value: list[dict[str, Any]],
    commands: list[dict[str, Any]],
    origin: Literal["ai", "human"],
    fault_at: Literal["after_revision", "after_head"] | None = None,
    lose_reply: bool = False,
) -> dict[str, Any] | BridgeFailure:
    digest = request_digest(
        document_id=document_id,
        base_revision=base_revision,
        commands=commands,
        origin=origin,
    )
    existing = operation_or_conflict(dsn, document_id, operation_id, digest)
    if existing is not None:
        return existing
    candidate = run_bridge(bridge, base_value, commands)
    if isinstance(candidate, BridgeFailure):
        return candidate
    return commit_candidate(
        dsn,
        document_id=document_id,
        operation_id=operation_id,
        digest=digest,
        base_revision=base_revision,
        origin=origin,
        candidate=candidate,
        fault_at=fault_at,
        lose_reply=lose_reply,
    )


def new_document_id(label: str) -> str:
    return f"p01-{label}-{uuid4()}"


def new_process_lookup(document_id: str, operation_id: str) -> dict[str, Any]:
    child_environment = os.environ.copy()
    child_environment["PYTHONUTF8"] = "1"
    child_environment["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "lookup", document_id, operation_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
        cwd=ROOT,
        env=child_environment,
        timeout=30,
    )
    if completed.returncode != 0:
        raise ProbeFailure(f"New-process receipt lookup failed with code {completed.returncode}")
    try:
        result = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProbeFailure("New-process receipt lookup did not return one JSON value") from error
    if not isinstance(result, dict) or result.get("operation_id") != operation_id:
        raise ProbeFailure("New-process receipt lookup returned the wrong operation")
    return result


def assert_equal(actual: Any, expected: Any, detail: str) -> None:
    if actual != expected:
        raise ProbeFailure(f"{detail}: expected {expected!r}, got {actual!r}")


def run_probe(dsn: str, fixture: Path, bridge: Path) -> dict[str, Any]:
    if DATABASE != "jd_editor_probe_p01_20260909":
        raise ProbeFailure("Connection helper is not pinned to the dedicated P01 database")
    base_value = json.loads(fixture.read_text(encoding="utf-8"))
    if not isinstance(base_value, list):
        raise ProbeFailure("Fixture must be one raw Plate value array")
    setup_schema(dsn)
    report: dict[str, Any] = {
        "probe": "P01-fixed-python-node-postgresql",
        "database": DATABASE,
        "engine_profile": ENGINE_PROFILE,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "fixture": {
            "sha256": value_hash(base_value),
            "counts": value_counts(base_value),
        },
        "scenarios": {},
    }

    # Full-r2 save, reopen, same-op receipt replay, and same-ID conflict.
    full_document = new_document_id("fullr2")
    bootstrap_document(dsn, full_document, base_value)
    full_commands = [{"type": "append_text", "target_id": "purpose", "text": "〔P01 AI 保存〕"}]
    full_operation = "p01-fullr2-ai-save"
    full_result = execute_operation(
        dsn,
        bridge,
        document_id=full_document,
        operation_id=full_operation,
        base_revision=1,
        base_value=base_value,
        commands=full_commands,
        origin="ai",
    )
    assert isinstance(full_result, dict)
    assert_equal(full_result["status"], "committed", "Full-r2 operation status")
    reopened = read_head(dsn, full_document)
    assert_equal(reopened["revision"], 2, "Full-r2 reopened revision")
    assert_equal(reopened["value_sha256"], value_hash(reopened["value"]), "Reopened value hash")
    first_counts = counts(dsn, full_document)
    replay = execute_operation(
        dsn,
        bridge,
        document_id=full_document,
        operation_id=full_operation,
        base_revision=1,
        base_value=base_value,
        commands=full_commands,
        origin="ai",
    )
    assert isinstance(replay, dict)
    assert_equal(replay, full_result, "Same-operation receipt replay")
    assert_equal(counts(dsn, full_document), first_counts, "Same operation added durable rows")
    conflict = "not_observed"
    try:
        execute_operation(
            dsn,
            bridge,
            document_id=full_document,
            operation_id=full_operation,
            base_revision=1,
            base_value=base_value,
            commands=[{"type": "append_text", "target_id": "purpose", "text": "不同 payload"}],
            origin="ai",
        )
    except SameOperationDifferentRequest:
        conflict = "rejected"
    assert_equal(conflict, "rejected", "Same operation ID with different payload")
    report["scenarios"]["fullr2_save_reopen_and_receipt"] = {
        "document_id": full_document,
        "operation_id": full_operation,
        "before_sha256": value_hash(base_value),
        "after_sha256": reopened["value_sha256"],
        "before_counts": value_counts(base_value),
        "after_counts": value_counts(reopened["value"]),
        "table_counts": first_counts,
        "same_operation": "same receipt; no new rows",
        "same_id_different_payload": conflict,
        "saved_value_query": "SELECT value FROM jd_revision WHERE document_id = <document_id> AND revision = 2",
    }

    # Node partially mutates its disposable candidate, then fails: no DB rows change.
    partial_document = new_document_id("partial")
    bootstrap_document(dsn, partial_document, base_value)
    partial_before = counts(dsn, partial_document)
    partial = execute_operation(
        dsn,
        bridge,
        document_id=partial_document,
        operation_id="p01-partial-engine-failure",
        base_revision=1,
        base_value=base_value,
        commands=[
            {"type": "insert_paragraph_after", "target_id": "purpose", "text": "不可保存的前半步"},
            {"type": "append_text", "target_id": "__missing__", "text": "必定失敗"},
        ],
        origin="ai",
    )
    if not isinstance(partial, BridgeFailure):
        raise ProbeFailure("Partial native failure unexpectedly reached the save boundary")
    assert_equal(partial.code, "target_missing", "Partial failure code")
    assert_equal(partial.command_index, 1, "Partial failure index")
    assert_equal(counts(dsn, partial_document), partial_before, "Partial bridge failure changed DB rows")
    report["scenarios"]["partial_bridge_failure"] = {
        "document_id": partial_document,
        "error": {"code": partial.code, "command_index": partial.command_index},
        "before_counts": partial_before,
        "after_counts": counts(dsn, partial_document),
        "durable_effect": partial.durable_effect,
    }

    # Transaction failure after head update rolls back revision, head and receipt.
    rollback_document = new_document_id("rollback")
    bootstrap_document(dsn, rollback_document, base_value)
    rollback_before = counts(dsn, rollback_document)
    rollback_head = read_head(dsn, rollback_document)
    rolled_back = False
    try:
        execute_operation(
            dsn,
            bridge,
            document_id=rollback_document,
            operation_id="p01-transaction-rollback",
            base_revision=1,
            base_value=base_value,
            commands=[{"type": "append_text", "target_id": "purpose", "text": "交易故障"}],
            origin="ai",
            fault_at="after_head",
        )
    except SimulatedTransactionFailure:
        rolled_back = True
    assert_equal(rolled_back, True, "Transaction failure was not injected")
    assert_equal(counts(dsn, rollback_document), rollback_before, "Transaction failure did not roll back all rows")
    assert_equal(read_head(dsn, rollback_document)["value_sha256"], rollback_head["value_sha256"], "Rollback changed head")
    assert_equal(read_operation(dsn, rollback_document, "p01-transaction-rollback"), None, "Rollback left receipt")
    report["scenarios"]["transaction_rollback"] = {
        "document_id": rollback_document,
        "fault_at": "after_head",
        "before_counts": rollback_before,
        "after_counts": counts(dsn, rollback_document),
        "head_sha256": rollback_head["value_sha256"],
    }

    # Commit succeeds but caller loses the reply; a new Python process finds it.
    lost_document = new_document_id("lostreply")
    bootstrap_document(dsn, lost_document, base_value)
    lost_operation = "p01-lost-reply"
    lost_reply_seen = False
    try:
        execute_operation(
            dsn,
            bridge,
            document_id=lost_document,
            operation_id=lost_operation,
            base_revision=1,
            base_value=base_value,
            commands=[{"type": "insert_paragraph_after", "target_id": "purpose", "text": "回覆遺失但已保存"}],
            origin="ai",
            lose_reply=True,
        )
    except SimulatedLostReply:
        lost_reply_seen = True
    assert_equal(lost_reply_seen, True, "Lost-reply boundary was not injected")
    recovered = new_process_lookup(lost_document, lost_operation)
    assert_equal(recovered["status"], "committed", "New process did not recover committed receipt")
    assert_equal(read_head(dsn, lost_document)["revision"], recovered["result_revision"], "Recovered result is not current head")
    report["scenarios"]["lost_reply_reconciliation"] = {
        "document_id": lost_document,
        "operation_id": lost_operation,
        "new_process_status": recovered["status"],
        "result_revision": recovered["result_revision"],
        "result_value_sha256": recovered["result_value_sha256"],
        "table_counts": counts(dsn, lost_document),
    }

    # Two independently computed candidates share base 1. Human commits first;
    # the already-computed AI candidate is stale and publishes no new revision.
    race_document = new_document_id("race")
    bootstrap_document(dsn, race_document, base_value)
    ai_commands = [{"type": "append_text", "target_id": "purpose", "text": "AI stale 候選"}]
    human_commands = [{"type": "append_text", "target_id": "purpose", "text": "人工先保存"}]
    ai_candidate = run_bridge(bridge, base_value, ai_commands)
    human_candidate = run_bridge(bridge, base_value, human_commands)
    if not isinstance(ai_candidate, BridgeSuccess) or not isinstance(human_candidate, BridgeSuccess):
        raise ProbeFailure("Race candidates did not both finish before the first commit")
    human_digest = request_digest(
        document_id=race_document, base_revision=1, commands=human_commands, origin="human"
    )
    human_result = commit_candidate(
        dsn,
        document_id=race_document,
        operation_id="p01-human-first",
        digest=human_digest,
        base_revision=1,
        origin="human",
        candidate=human_candidate,
    )
    ai_digest = request_digest(document_id=race_document, base_revision=1, commands=ai_commands, origin="ai")
    ai_result = commit_candidate(
        dsn,
        document_id=race_document,
        operation_id="p01-ai-stale-after-compute",
        digest=ai_digest,
        base_revision=1,
        origin="ai",
        candidate=ai_candidate,
    )
    assert_equal(human_result["status"], "committed", "Human command did not use the save boundary")
    assert_equal(ai_result["status"], "stale_base", "Computed AI candidate was not rejected as stale")
    assert_equal(counts(dsn, race_document)["revisions"], 2, "Stale AI candidate published a revision")

    # A no-change still checks the now-current baseline and records a receipt,
    # while creating no document revision.
    current_race = read_head(dsn, race_document)
    no_change_commands: list[dict[str, Any]] = []
    no_change_result = execute_operation(
        dsn,
        bridge,
        document_id=race_document,
        operation_id="p01-no-change",
        base_revision=current_race["revision"],
        base_value=current_race["value"],
        commands=no_change_commands,
        origin="human",
    )
    assert isinstance(no_change_result, dict)
    assert_equal(no_change_result["status"], "no_change", "No-change operation status")
    assert_equal(read_head(dsn, race_document)["revision"], 2, "No-change created a revision")
    report["scenarios"]["post_compute_cas_human_and_no_change"] = {
        "document_id": race_document,
        "human_operation": human_result["status"],
        "already_computed_ai_operation": ai_result["status"],
        "no_change_operation": no_change_result["status"],
        "final_revision": read_head(dsn, race_document)["revision"],
        "table_counts": counts(dsn, race_document),
        "final_sha256": read_head(dsn, race_document)["value_sha256"],
    }

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["status"] = "passed"
    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    output = results / f"save-probe-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_file"] = str(output.relative_to(ROOT))
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    run.add_argument("--bridge", type=Path, default=DEFAULT_BRIDGE)
    lookup = subparsers.add_parser("lookup")
    lookup.add_argument("document_id")
    lookup.add_argument("operation_id")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    dsn = load_probe_dsn()
    if arguments.command == "lookup":
        result = read_operation(dsn, arguments.document_id, arguments.operation_id)
        if result is None:
            raise ProbeFailure("Operation receipt was not found")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    report = run_probe(dsn, arguments.fixture.resolve(), arguments.bridge.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
