"""協調來源解析、向量計算、索引寫入與完成標記。"""

from __future__ import annotations

import time
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from qdrant_client import QdrantClient

from jd_ocs_indexer.config import Settings
from jd_ocs_indexer.embeddings.base import EmbeddingService
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


def run_index(
    settings: Settings,
    scan_dir: Path,
    *,
    limit: int = 0,
    embedder: EmbeddingService | None = None,
    client: QdrantClient | None = None,
) -> IndexReport:
    """完成索引後回報；只釋放本次建立的資源，借入資源由呼叫端管理。"""
    with ExitStack() as resources:
        if embedder is None:
            owned_embedder = make_embedder(settings)
            resources.callback(owned_embedder.close)
            embedder = owned_embedder
        if client is None:
            client = make_client(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
                timeout=settings.qdrant_timeout,
            )
            resources.callback(client.close)
        writer = QdrantWriter(
            client,
            settings.qdrant_collection,
            dense_size=embedder.dense_size,
            supports_sparse=embedder.supports_sparse,
            batch_size=settings.index_batch_size,
        )
        writer.ensure_collection()
        writer.ensure_payload_indexes(schema.PAYLOAD_INDEXES)

        reader = OCSJSONReader(settings.source_root)
        report = IndexReport(collection=settings.qdrant_collection)
        started = time.time()
        for index, (loaded, failure) in enumerate(reader.iter_loaded(scan_dir)):
            if limit and index >= limit:
                break
            if failure is not None:
                report.failed_files += 1
                report.failures.append((str(failure.rel_path), str(failure.error)))
                continue
            assert loaded is not None
            normalized = normalize(loaded.document)
            context = BuildContext(source_file=loaded.rel_path, indexed_at=_now_iso())
            records = build(normalized, context)
            vectors = embedder.embed_texts([record.text for record in records])
            embedded = [
                EmbeddedChunk(record=record, dense=vector.dense, sparse=vector.sparse)
                for record, vector in zip(records, vectors)
            ]
            upsert_report = writer.upsert(embedded)
            report.points += upsert_report.upserted
            report.indexed_files += 1
        report.elapsed_sec = time.time() - started
        if report.indexed_files:
            from jd_ocs_indexer.store.manifest import write_manifest

            write_manifest(client, settings.qdrant_collection, embedder.signature)
        return report
