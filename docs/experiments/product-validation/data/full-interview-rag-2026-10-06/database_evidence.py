"""Save a read-only scoped projection; exclude checkpoint and encrypted context tables."""

import argparse
import json
from pathlib import Path

import psycopg
from psycopg import sql

HERE = Path(__file__).resolve().parent
TABLES = ["executions", "formal_interviews", "interview_texts", "memory_batches", "memory_snapshots",
          "memory_positions", "memory_position_members", "memory_objects", "memory_bodies",
          "memory_object_revisions", "memory_interview_references", "memory_situation_references",
          "jd_source_references", "occupation_reference_operations", "occupation_reference_candidates"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    arguments = parser.parse_args()
    file_id = json.loads((HERE / "state.json").read_text(encoding="utf-8"))["file_id"]
    records = {}
    with psycopg.connect("postgresql://caliburn:e2e_local_only_20261006@127.0.0.1:55446/caliburn",
                          options="-c default_transaction_read_only=on -c statement_timeout=15000") as database:
        for table in TABLES:
            query = sql.SQL("select to_jsonb(t) from {} t where job_file_id=%s").format(
                sql.Identifier("caliburn", table))
            records[table] = [row[0] for row in database.execute(query, (file_id,))]
        records["outbound_attempts"] = [row[0] for row in database.execute("""
            select to_jsonb(a) from caliburn.execution_outbound_attempts a
            join caliburn.executions e using(execution_id) where e.job_file_id=%s
            order by a.admitted_at""", (file_id,))]
    with (HERE / (arguments.name + "-database.json")).open("x", encoding="utf-8") as output:
        json.dump(records, output, ensure_ascii=False, indent=2)
    print(json.dumps({table: len(values) for table, values in records.items()}))


if __name__ == "__main__":
    main()
