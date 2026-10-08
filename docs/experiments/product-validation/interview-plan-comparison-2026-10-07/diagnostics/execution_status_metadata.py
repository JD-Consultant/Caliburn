"""Read-only execution-kind counts in this experiment's isolated PostgreSQL schema."""

import json
import re
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import psycopg
from psycopg import sql

DSN = "postgresql://intplan_test:intplan-local-test@127.0.0.1:55447/caliburn_intplan_test"


def collect(directory):
    source = directory / "case.json"
    case = json.loads(source.read_text(encoding="utf-8"))
    schema = case["schema"]
    if not isinstance(schema, str) or not re.fullmatch(r"intplan_formal_[a-z0-9_]+", schema):
        raise ValueError("Expected this experiment's isolated formal schema")
    result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    if not result["closure_submitted"] or result["turns"][-1]["status"] != "completed":
        raise ValueError("Execution status evidence requires a mechanically completed case")
    with psycopg.connect(
        DSN,
        options="-c default_transaction_read_only=on -c statement_timeout=10000",
    ) as connection:
        counts = connection.execute(
            sql.SQL(
                "SELECT kind, status, count(*) FROM {}.executions GROUP BY kind, status"
            ).format(sql.Identifier(schema))
        ).fetchall()
    return {
        "case": directory.name,
        "schema": schema,
        "observed_at": datetime.now(UTC).isoformat(),
        "case_source_sha256": sha256(source.read_bytes()).hexdigest(),
        "transaction_read_only": True,
        "query_template": (
            "SELECT kind, status, count(*) FROM <case.json schema>.executions GROUP BY kind, status"
        ),
        "filter_keys": {"schema": schema},
        "collector_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "counts": [
            {"kind": kind, "status": status, "count": count}
            for kind, status, count in sorted(counts)
        ],
        "scope": "One fresh synthetic job file in the named isolated test database/schema.",
    }


def main():
    directory, output = Path(sys.argv[1]), Path(sys.argv[2])
    if output.exists():
        raise RuntimeError("Execution status evidence already exists")
    result = collect(directory)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
