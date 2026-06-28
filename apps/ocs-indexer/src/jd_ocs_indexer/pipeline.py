"""Index pipeline: reader -> normalize -> build -> embed -> upsert (+ manifest in T3).

Pure orchestration, no Typer/console — reusable by the CLI, a batch job, or tests.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from jd_ocs_indexer.config import Settings
from jd_ocs_indexer.embeddings.factory import make_embedder
from jd_ocs_indexer.ingestion.builder import BuildContext, build
from jd_ocs_indexer.ingestion.normalizer import normalize
from jd_ocs_indexer.ingestion.reader import OCSJSONReader
from jd_ocs_indexer.models.chunk import EmbeddedChunk
from jd_ocs_indexer.store import schema
from jd_ocs_indexer.store.qdrant_client import make_client
from jd_ocs_indexer.store.writer import QdrantWriter


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class IndexReport:
    collection: str
    indexed_files: int = 0
    failed_files: int = 0
    points: int = 0
    elapsed_sec: float = 0.0
    failures: list[tuple[str, str]] = field(default_factory=list)  # (rel_path, error)


def run_index(settings: Settings, scan_dir: Path, *, limit: int = 0,
              embedder=None, client=None) -> IndexReport:
    reader = OCSJSONReader(settings.source_root)
    embedder = embedder or make_embedder(settings)
    client = client or make_client(url=settings.qdrant_url, api_key=settings.qdrant_api_key,
                                   timeout=settings.qdrant_timeout)
    writer = QdrantWriter(client, settings.qdrant_collection,
                          dense_size=embedder.dense_size,
                          supports_sparse=embedder.supports_sparse,
                          batch_size=settings.index_batch_size)
    writer.ensure_collection()
    writer.ensure_payload_indexes(schema.PAYLOAD_INDEXES)

    report = IndexReport(collection=settings.qdrant_collection)
    started = time.time()
    for i, (loaded, fail) in enumerate(reader.iter_loaded(scan_dir)):
        if limit and i >= limit:
            break
        if fail is not None:
            report.failed_files += 1
            report.failures.append((str(fail.rel_path), str(fail.error)))
            continue
        assert loaded is not None
        norm = normalize(loaded.document)
        ctx = BuildContext(source_file=loaded.rel_path, indexed_at=_now_iso())
        records = build(norm, ctx)
        vecs = embedder.embed_texts([r.text for r in records])
        embedded = [EmbeddedChunk(record=r, dense=v.dense, sparse=v.sparse)
                    for r, v in zip(records, vecs)]
        rep = writer.upsert(embedded)
        report.points += rep.upserted
        report.indexed_files += 1
    report.elapsed_sec = time.time() - started
    # (T3 will append: write_manifest(client, settings.qdrant_collection, embedder.signature))
    return report
