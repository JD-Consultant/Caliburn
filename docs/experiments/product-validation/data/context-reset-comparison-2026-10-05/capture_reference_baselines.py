"""One-off, read-only capture of JD review anchors missing from product-052.json.

Reads only the fixed historical research database. No model, service startup or
original data changes. The output is immutable gzip JSON, not a model input.
"""

import asyncio
import gzip
import hashlib
import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from caliburn.adapters.database import Database
from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.features.job_description import persistence, source_persistence, work_queries
from sqlalchemy import text

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


async def capture() -> None:
    output = HERE / "reference-review-anchors.json.gz"
    if output.exists():
        raise ValueError("Reference capture exists; do not replace it")
    old = HERE.parent / "compaction-long-interview-2026-10-04"
    sys.path.insert(0, str(old))
    spec = importlib.util.spec_from_file_location(
        "reset_source_database", old / "continuation_database.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Historical research database helper is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = json.loads((HERE / "baseline.json").read_text(encoding="utf-8"))
    source = next(s for s in manifest["source_files"] if s["role"] == "jd_and_formal_interviews")
    raw = (ROOT / source["path"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != source["sha256"]:
        raise ValueError("Original baseline hash changed")
    product = json.loads(raw)
    revision_id = UUID(product["profile"]["revision_id"])
    database = Database(DatabaseSettings(url=module.cloned_database_url(), schema=module.SCHEMA))
    try:
        async with database.sessions.begin() as session:
            await session.execute(
                text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            )
            references = await source_persistence.read_source_references(
                session, module.FILE_ID, revision_id
            )
            if len(references) != len(product["evidence"]):
                raise ValueError("Historical reference count mismatch")
            revisions = sorted(
                {r.reviewed_revision_id for r in references if r.reviewed_revision_id}
            )
            anchors = []
            for anchor in revisions:
                needed = {r.citation_id for r in references if r.reviewed_revision_id == anchor}
                historical = await source_persistence.read_source_references(
                    session, module.FILE_ID, anchor
                )
                selected = [r for r in historical if r.citation_id in needed]
                if len(selected) != len(needed) or any(
                    r.needs_review or r.reviewed_revision_id != anchor for r in selected
                ):
                    raise ValueError("Original citation review anchors are incomplete")
                anchors.append(
                    {
                        "profile": asdict(
                            await persistence.read_revision(session, module.FILE_ID, anchor)
                        ),
                        "work": asdict(
                            await work_queries.read_work_at(session, module.FILE_ID, anchor)
                        ),
                        "references": [asdict(r) for r in selected],
                    }
                )
        payload = {
            "source_database": "caliburn_compaction_main03",
            "source_schema": module.SCHEMA,
            "source_job_file_id": str(module.FILE_ID),
            "revision_id": str(revision_id),
            "product_sha256": source["sha256"],
            "references": [asdict(r) for r in references],
            "anchors": anchors,
        }
        encoded = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        compressed = gzip.compress(encoded, mtime=0)
        with output.open("xb") as stream:
            stream.write(compressed)
        print(
            json.dumps(
                {
                    "references": len(references),
                    "pending": sum(r.needs_review for r in references),
                    "anchors": len(anchors),
                    "bytes": len(compressed),
                    "sha256": hashlib.sha256(compressed).hexdigest(),
                }
            )
        )
    finally:
        await database.close()


if __name__ == "__main__":
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(capture())
