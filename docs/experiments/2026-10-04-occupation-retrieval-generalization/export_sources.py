"""Read-only PostgreSQL receipts; the research schemas are retained."""
import json
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

HERE = Path(__file__).resolve().parent
run = HERE / "run-02"
manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
captures = [json.loads(line) for line in (run / "capture.jsonl").read_text().splitlines()]
assert len(captures) == 14
evidence = {}
with psycopg.connect("postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test",
        options=f"-c search_path={manifest['schema']}", row_factory=dict_row) as connection:
    connection.execute("SET TRANSACTION READ ONLY")
    for capture in captures:
        messages = connection.execute(
            "SELECT f.interview_sequence,t.source_id,t.speaker,t.interview_text AS text FROM formal_interviews f JOIN interview_texts t ON t.job_file_id=f.job_file_id AND t.source_id=f.source_id WHERE f.job_file_id=%s ORDER BY f.interview_sequence",
            (capture["job_file_id"],)).fetchall()
        head = connection.execute("SELECT snapshot_id FROM memory_heads WHERE job_file_id=%s", (capture["job_file_id"],)).fetchone()
        batch = connection.execute("SELECT status,through_sequence FROM memory_batches WHERE job_file_id=%s AND execution_id=%s", (capture["job_file_id"], capture["execution_id"])).fetchone()
        assert str(head["snapshot_id"]) == capture["snapshot_id"]
        assert batch == {"status": "published", "through_sequence": 6}
        evidence[capture["case_id"]] = {"messages": messages,
            "published_snapshot_id": str(head["snapshot_id"]), "batch": batch}
(run / "source-evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(f"Exported {len(evidence)} published batch source receipts, read only")
