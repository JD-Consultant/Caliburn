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


class BaseValueMismatch(ProbeFailure):
    pass


class SimulatedTransactionFailure(ProbeFailure):
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
    *,
    document_id: str,
    base_revision: int,
    base_value_sha256: str,
    commands: list[dict[str, Any]],
    origin: str,
) -> str:
    return value_hash(
        {
            "document_id": document_id,
            "base_revision": base_revision,
            "base_value_sha256": base_value_sha256,
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


def walk_nodes(node: dict[str, Any]):
    yield node
    for child in node.get("children", []):
        if isinstance(child, dict):
            yield from walk_nodes(child)


def node_text(node: dict[str, Any]) -> str:
    return "".join(
        descendant["text"]
        for descendant in walk_nodes(node)
        if isinstance(descendant.get("text"), str)
    )


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
    connection = psycopg.connect(dsn, row_factory=dict_row, autocommit=True)
    actual = connection.execute("SELECT current_database() AS name").fetchone()["name"]
    if actual != DATABASE:
        connection.close()
        raise ProbeFailure("Refusing a database other than the dedicated P01 target")
    return connection


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


def read_revision(dsn: str, document_id: str, revision: int) -> dict[str, Any]:
    with connect(dsn) as connection:
        row = connection.execute(
            """
            SELECT document_id, revision, parent_revision, value, value_sha256,
                   engine_profile, origin, operation_id
            FROM jd_revision
            WHERE document_id = %s AND revision = %s
            """,
            (document_id, revision),
        ).fetchone()
    if row is None:
        raise ProbeFailure("Requested saved base revision is missing")
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
    base_value_sha256: str,
    origin: Literal["ai", "human"],
    candidate: BridgeSuccess,
    fault_at: Literal["after_revision", "after_head"] | None = None,
    hard_exit_after_commit: bool = False,
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
        # The pre-lock lookup is only a fast path. Re-read under the document
        # writer lock so two callers of the same operation converge on the
        # committed receipt rather than surfacing a primary-key race.
        prior = connection.execute(
            """
            SELECT document_id, operation_id, request_digest, base_revision,
                   status, result_revision, origin, actual_changes,
                   result_value_sha256
            FROM jd_operation
            WHERE document_id = %s AND operation_id = %s
            """,
            (document_id, operation_id),
        ).fetchone()
        if prior is not None:
            if prior["request_digest"] != digest:
                raise SameOperationDifferentRequest(
                    "Same operation ID belongs to a different request digest"
                )
            return dict(prior)
        current_revision = head["revision"]
        saved_base = connection.execute(
            """
            SELECT value_sha256 FROM jd_revision
            WHERE document_id = %s AND revision = %s
            """,
            (document_id, base_revision),
        ).fetchone()
        if saved_base is None or saved_base["value_sha256"] != base_value_sha256:
            raise BaseValueMismatch("Candidate base does not match the saved revision")
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

    if hard_exit_after_commit:
        # P01-only fault: prove another process can reconcile after the writer
        # disappears after commit and before any application response/lookup.
        os._exit(91)
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
    hard_exit_after_commit: bool = False,
) -> dict[str, Any] | BridgeFailure:
    saved_base = read_revision(dsn, document_id, base_revision)
    supplied_base_hash = value_hash(base_value)
    if supplied_base_hash != saved_base["value_sha256"]:
        raise BaseValueMismatch("Supplied base value does not match the saved revision")
    digest = request_digest(
        document_id=document_id,
        base_revision=base_revision,
        base_value_sha256=supplied_base_hash,
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
        base_value_sha256=supplied_base_hash,
        origin=origin,
        candidate=candidate,
        fault_at=fault_at,
        hard_exit_after_commit=hard_exit_after_commit,
    )


def new_document_id(label: str) -> str:
    return f"p01-{label}-{uuid4()}"


def run_probe_child(arguments: list[str], *, expected_exit: int = 0) -> bytes:
    child_environment = os.environ.copy()
    child_environment["PYTHONUTF8"] = "1"
    child_environment["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
        cwd=ROOT,
        env=child_environment,
        timeout=30,
    )
    if completed.returncode != expected_exit:
        raise ProbeFailure(
            f"Probe child returned {completed.returncode}; expected {expected_exit}"
        )
    return completed.stdout


def new_process_lookup(document_id: str, operation_id: str) -> dict[str, Any]:
    try:
        result = json.loads(run_probe_child(["lookup", document_id, operation_id]).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProbeFailure("New-process receipt lookup did not return one JSON value") from error
    if not isinstance(result, dict) or result.get("operation_id") != operation_id:
        raise ProbeFailure("New-process receipt lookup returned the wrong operation")
    return result


def new_process_inspect(document_id: str, revision: int) -> dict[str, Any]:
    try:
        result = json.loads(
            run_probe_child(["inspect", document_id, str(revision), "--include-value"]).decode("utf-8")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProbeFailure("New-process revision inspection did not return one JSON value") from error
    if not isinstance(result, dict) or result.get("revision") != revision or not isinstance(result.get("value"), list):
        raise ProbeFailure("New-process revision inspection returned the wrong full value")
    return result


def run_writer_that_exits_after_commit(document_id: str, operation_id: str) -> None:
    stdout = run_probe_child(["writer-exit", document_id, operation_id], expected_exit=91)
    if stdout:
        raise ProbeFailure("Interrupted writer emitted a response after its commit")


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
    with connect(dsn) as metadata_connection:
        postgres_version = metadata_connection.execute("SHOW server_version").fetchone()["server_version"]
    node_version = subprocess.run(
        ["node", "--version"], capture_output=True, text=True, check=True, shell=False
    ).stdout.strip()
    report: dict[str, Any] = {
        "probe": "P01-fixed-python-node-postgresql",
        "database": DATABASE,
        "engine_profile": ENGINE_PROFILE,
        "runtime_versions": {
            "python": sys.version.split()[0],
            "psycopg": psycopg.__version__,
            "node": node_version,
            "postgresql": postgres_version,
        },
        "source_sha256": {
            "save_probe.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "node_bridge.mjs": hashlib.sha256(bridge.read_bytes()).hexdigest(),
            "fixture.json": hashlib.sha256(fixture.read_bytes()).hexdigest(),
            "PROTOCOL.md": hashlib.sha256((ROOT / "PROTOCOL.md").read_bytes()).hexdigest(),
        },
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
    inserted_text = "P01 AI 新增段落（唯一）"
    full_commands = [
        {"type": "insert_paragraph_after", "target_id": "purpose", "text": inserted_text}
    ]
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
    reopened = new_process_inspect(full_document, 2)
    assert_equal(reopened["revision"], 2, "Full-r2 reopened revision")
    assert_equal(reopened["value_sha256"], value_hash(reopened["value"]), "Reopened value hash")
    inserted_occurrences = sum(
        1
        for root in reopened["value"]
        for node in walk_nodes(root)
        if node.get("text") == inserted_text
    )
    assert_equal(inserted_occurrences, 1, "Inserted paragraph occurrence after first save")
    inserted_root_indexes = [
        index
        for index, node in enumerate(reopened["value"])
        if node.get("type") == "p" and node_text(node) == inserted_text
    ]
    assert_equal(len(inserted_root_indexes), 1, "Inserted paragraph root identity")
    value_without_insert = [
        node for index, node in enumerate(reopened["value"]) if index != inserted_root_indexes[0]
    ]
    assert_equal(value_without_insert, base_value, "Full-r2 content/metadata preservation oracle")
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
    replay_reopened = new_process_inspect(full_document, 2)
    replay_occurrences = sum(
        1
        for root in replay_reopened["value"]
        for node in walk_nodes(root)
        if node.get("text") == inserted_text
    )
    assert_equal(replay_occurrences, 1, "Same operation duplicated inserted content")
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
        "inserted_paragraph_occurrences_after_replay": replay_occurrences,
        "remove_inserted_paragraph_equals_original_value": value_without_insert == base_value,
        "same_id_different_payload": conflict,
        "saved_value_query": "SELECT value FROM jd_revision WHERE document_id = <document_id> AND revision = 2",
    }

    # Node partially mutates its disposable candidate, then fails: no DB rows change.
    partial_document = new_document_id("partial")
    bootstrap_document(dsn, partial_document, base_value)
    partial_before = counts(dsn, partial_document)
    partial_head_before = read_head(dsn, partial_document)
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
    partial_head_after = read_head(dsn, partial_document)
    assert_equal(partial_head_after, partial_head_before, "Partial bridge failure changed the saved head")
    assert_equal(
        read_operation(dsn, partial_document, "p01-partial-engine-failure"),
        None,
        "Partial bridge failure created an operation row",
    )
    report["scenarios"]["partial_bridge_failure"] = {
        "document_id": partial_document,
        "error": {"code": partial.code, "command_index": partial.command_index},
        "before_counts": partial_before,
        "after_counts": counts(dsn, partial_document),
        "before_head_sha256": partial_head_before["value_sha256"],
        "after_head_sha256": partial_head_after["value_sha256"],
        "head_objects_equal": partial_head_after == partial_head_before,
        "operation_row": None,
        "durable_effect": partial.durable_effect,
    }

    # A correct revision paired with the wrong clean value must fail before the
    # bridge; revision CAS alone cannot bind a candidate to its actual base.
    mismatch_document = new_document_id("base-mismatch")
    bootstrap_document(dsn, mismatch_document, base_value)
    mismatch_before_counts = counts(dsn, mismatch_document)
    mismatch_before_head = read_head(dsn, mismatch_document)
    wrong_base_value = json.loads(json.dumps(base_value, ensure_ascii=False))
    wrong_base_value.append(
        {"type": "p", "id": "p01-wrong-base-only", "children": [{"text": "錯誤基底"}]}
    )
    mismatch_rejected = False
    try:
        execute_operation(
            dsn,
            bridge,
            document_id=mismatch_document,
            operation_id="p01-base-value-mismatch",
            base_revision=1,
            base_value=wrong_base_value,
            commands=[{"type": "append_text", "target_id": "purpose", "text": "不得執行"}],
            origin="ai",
        )
    except BaseValueMismatch:
        mismatch_rejected = True
    assert_equal(mismatch_rejected, True, "Same revision with a different base value was accepted")
    assert_equal(counts(dsn, mismatch_document), mismatch_before_counts, "Base mismatch changed DB rows")
    assert_equal(read_head(dsn, mismatch_document), mismatch_before_head, "Base mismatch changed saved head")
    assert_equal(
        read_operation(dsn, mismatch_document, "p01-base-value-mismatch"),
        None,
        "Base mismatch created an operation row",
    )
    report["scenarios"]["base_value_binding"] = {
        "document_id": mismatch_document,
        "revision": 1,
        "saved_base_sha256": mismatch_before_head["value_sha256"],
        "supplied_wrong_base_sha256": value_hash(wrong_base_value),
        "result": "rejected before bridge/save",
        "before_counts": mismatch_before_counts,
        "after_counts": counts(dsn, mismatch_document),
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
    run_writer_that_exits_after_commit(lost_document, lost_operation)
    recovered = new_process_lookup(lost_document, lost_operation)
    assert_equal(recovered["status"], "committed", "New process did not recover committed receipt")
    assert_equal(read_head(dsn, lost_document)["revision"], recovered["result_revision"], "Recovered result is not current head")
    report["scenarios"]["lost_reply_reconciliation"] = {
        "document_id": lost_document,
        "operation_id": lost_operation,
        "writer_exit_after_commit": 91,
        "writer_response_bytes": 0,
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
    race_base = read_revision(dsn, race_document, 1)
    ai_candidate = run_bridge(bridge, race_base["value"], ai_commands)
    human_candidate = run_bridge(bridge, race_base["value"], human_commands)
    stale_no_change_candidate = run_bridge(bridge, race_base["value"], [])
    if (
        not isinstance(ai_candidate, BridgeSuccess)
        or not isinstance(human_candidate, BridgeSuccess)
        or not isinstance(stale_no_change_candidate, BridgeSuccess)
    ):
        raise ProbeFailure("All interleaved candidates must finish before the first commit")
    human_digest = request_digest(
        document_id=race_document,
        base_revision=1,
        base_value_sha256=race_base["value_sha256"],
        commands=human_commands,
        origin="human",
    )
    human_result = commit_candidate(
        dsn,
        document_id=race_document,
        operation_id="p01-human-first",
        digest=human_digest,
        base_revision=1,
        base_value_sha256=race_base["value_sha256"],
        origin="human",
        candidate=human_candidate,
    )
    ai_digest = request_digest(
        document_id=race_document,
        base_revision=1,
        base_value_sha256=race_base["value_sha256"],
        commands=ai_commands,
        origin="ai",
    )
    ai_result = commit_candidate(
        dsn,
        document_id=race_document,
        operation_id="p01-ai-stale-after-compute",
        digest=ai_digest,
        base_revision=1,
        base_value_sha256=race_base["value_sha256"],
        origin="ai",
        candidate=ai_candidate,
    )
    assert_equal(human_result["status"], "committed", "Human command did not use the save boundary")
    assert_equal(ai_result["status"], "stale_base", "Computed AI candidate was not rejected as stale")
    assert_equal(counts(dsn, race_document)["revisions"], 2, "Stale AI candidate published a revision")

    stale_no_change_before = read_head(dsn, race_document)
    stale_no_change_digest = request_digest(
        document_id=race_document,
        base_revision=1,
        base_value_sha256=race_base["value_sha256"],
        commands=[],
        origin="ai",
    )
    stale_no_change_result = commit_candidate(
        dsn,
        document_id=race_document,
        operation_id="p01-stale-no-change",
        digest=stale_no_change_digest,
        base_revision=1,
        base_value_sha256=race_base["value_sha256"],
        origin="ai",
        candidate=stale_no_change_candidate,
    )
    stale_no_change_after = read_head(dsn, race_document)
    assert_equal(stale_no_change_result["status"], "stale_base", "Stale no-change skipped its baseline check")
    assert_equal(stale_no_change_after, stale_no_change_before, "Stale no-change altered the saved head")
    assert_equal(counts(dsn, race_document)["revisions"], 2, "Stale no-change published a revision")

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
    report["scenarios"]["interleaved_connections_cas_human_and_no_change"] = {
        "document_id": race_document,
        "concurrency_claim": "two candidates completed before sequential commits on separate connections; not a simultaneous concurrency test",
        "human_operation": human_result["status"],
        "already_computed_ai_operation": ai_result["status"],
        "already_computed_no_change_operation": stale_no_change_result["status"],
        "stale_no_change_before_revision": stale_no_change_before["revision"],
        "stale_no_change_after_revision": stale_no_change_after["revision"],
        "stale_no_change_before_sha256": stale_no_change_before["value_sha256"],
        "stale_no_change_after_sha256": stale_no_change_after["value_sha256"],
        "no_change_operation": no_change_result["status"],
        "final_revision": read_head(dsn, race_document)["revision"],
        "table_counts": counts(dsn, race_document),
        "final_sha256": read_head(dsn, race_document)["value_sha256"],
    }

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["status"] = "passed"
    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = results / f"save-probe-{stamp}.json"
    snapshots = results / f"save-probe-{stamp}-snapshots.json"
    snapshots.write_text(
        json.dumps(
            {
                "fixture_value": base_value,
                "fullr2_saved_revision": reopened,
                "fullr2_operation_receipt": full_result,
                "lost_reply_operation_receipt": recovered,
                "interleaved_final_head": read_head(dsn, race_document),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    report["report_file"] = str(output.relative_to(ROOT))
    report["snapshots_file"] = str(snapshots.relative_to(ROOT))
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
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
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("document_id")
    inspect.add_argument("revision", type=int)
    inspect.add_argument("--include-value", action="store_true")
    writer = subparsers.add_parser("writer-exit")
    writer.add_argument("document_id")
    writer.add_argument("operation_id")
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
    if arguments.command == "inspect":
        saved = read_revision(dsn, arguments.document_id, arguments.revision)
        result = {
            "document_id": saved["document_id"],
            "revision": saved["revision"],
            "parent_revision": saved["parent_revision"],
            "value_sha256": saved["value_sha256"],
            "computed_value_sha256": value_hash(saved["value"]),
            "counts": value_counts(saved["value"]),
            "engine_profile": saved["engine_profile"],
            "origin": saved["origin"],
            "operation_id": saved["operation_id"],
        }
        if arguments.include_value:
            result["value"] = saved["value"]
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    if arguments.command == "writer-exit":
        saved = read_head(dsn, arguments.document_id)
        result = execute_operation(
            dsn,
            DEFAULT_BRIDGE,
            document_id=arguments.document_id,
            operation_id=arguments.operation_id,
            base_revision=saved["revision"],
            base_value=saved["value"],
            commands=[
                {
                    "type": "insert_paragraph_after",
                    "target_id": "purpose",
                    "text": "writer process committed before os._exit",
                }
            ],
            origin="ai",
            hard_exit_after_commit=True,
        )
        raise ProbeFailure(f"Writer was expected to exit after commit, got {result!r}")
    report = run_probe(dsn, arguments.fixture.resolve(), arguments.bridge.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
