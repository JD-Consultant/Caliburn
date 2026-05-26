"""CLI entrypoint: render / index / stats / doctor / smoke-query."""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from jd_ocs_indexer.config import Settings, load_settings
from jd_ocs_indexer.ingestion import manifest as manifest_mod
from jd_ocs_indexer.ingestion.builder import BuilderContext, ChunkBuilder
from jd_ocs_indexer.ingestion.normalizer import normalize
from jd_ocs_indexer.ingestion.reader import OCSJSONReader
from jd_ocs_indexer.ingestion.renderer import MarkdownRenderer
from jd_ocs_indexer.models.chunk import ChunkRecord, EmbeddedChunk
from jd_ocs_indexer.store.qdrant_client import make_client
from jd_ocs_indexer.store.writer import QdrantWriter
from jd_ocs_indexer.validation import smoke_query, stats as stats_mod

app = typer.Typer(
    add_completion=False,
    help="jd-ocs-indexer: OCS JSON -> Qdrant index builder.",
)
console = Console()


_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._\-]+")


def _safe_filename(chunk_key: str) -> str:
    return _SAFE_FILENAME.sub("_", chunk_key).strip("._-")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


# ---------- render ----------


@app.command()
def render(
    scan_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    output: Path = typer.Option(Path("output/md"), "-o", "--output"),
    limit: int = typer.Option(0, "--limit", help="Stop after N files (0 = all)."),
) -> None:
    """Render JSON -> Markdown chunks. Does not touch Qdrant."""
    settings = load_settings()
    reader = OCSJSONReader(settings.source_root)
    builder = ChunkBuilder()
    renderer = MarkdownRenderer()

    output.mkdir(parents=True, exist_ok=True)
    total_files = 0
    total_chunks = 0
    failed = 0

    for i, (loaded, fail) in enumerate(reader.iter_loaded(scan_dir)):
        if limit and i >= limit:
            break
        if fail is not None:
            failed += 1
            console.print(f"[red]FAIL[/red] {fail.rel_path}: {fail.error}")
            continue
        assert loaded is not None
        norm = normalize(loaded.document)
        ctx = BuilderContext(
            source_root_alias=settings.source_root_alias,
            source_file=loaded.rel_path,
            source_json_hash=loaded.source_json_hash,
            schema_version=settings.schema_version,
            embedding_provider=settings.embedding_provider,
        )
        records = builder.build(norm, ctx)
        renderer.render(norm, records)

        sub = output / norm.ocs_code
        sub.mkdir(parents=True, exist_ok=True)
        for rec in records:
            fname = _safe_filename(rec.chunk_key) + ".md"
            (sub / fname).write_text(rec.text, encoding="utf-8")

        total_files += 1
        total_chunks += len(records)

    console.print(
        f"[green]Rendered[/green] files={total_files} chunks={total_chunks} failed={failed} -> {output}"
    )


# ---------- index ----------


@app.command()
def index(
    scan_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    limit: int = typer.Option(0, "--limit", help="Stop after N files (0 = all)."),
    rebuild: bool = typer.Option(False, "--rebuild", help="Ignore manifest, re-embed everything."),
) -> None:
    """Full pipeline: render -> embed -> upsert to Qdrant. Uses manifest for incremental skip."""
    settings = load_settings()
    _index_impl(settings, scan_dir, limit=limit, rebuild=rebuild)


def _index_impl(settings: Settings, scan_dir: Path, *, limit: int, rebuild: bool) -> None:
    reader = OCSJSONReader(settings.source_root)
    builder = ChunkBuilder()
    renderer = MarkdownRenderer()

    # Lazy import — heavy
    from jd_ocs_indexer.embeddings.bge_m3 import BGEM3Embedder

    embedder = BGEM3Embedder(
        model_name=settings.bge_m3_model,
        device=settings.bge_m3_device,
        use_fp16=settings.bge_m3_use_fp16,
        batch_size=settings.bge_m3_batch_size,
    )

    client = make_client(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    writer = QdrantWriter(
        client,
        settings.qdrant_collection,
        dense_size=embedder.dense_size,
        supports_sparse=embedder.supports_sparse,
        batch_size=settings.index_batch_size,
    )

    writer.ensure_collection()
    writer.ensure_payload_indexes()

    manifest = manifest_mod.load(settings.manifest_path)
    manifest.collection = settings.qdrant_collection
    manifest.embedding_provider = settings.embedding_provider
    manifest.source_root_alias = settings.source_root_alias
    manifest.schema_version = settings.schema_version

    started = time.time()
    skipped = 0
    indexed = 0
    failed = 0
    total_chunks = 0

    pending_records: list[ChunkRecord] = []
    pending_file_chunks: dict[str, list[str]] = {}
    pending_files: dict[str, str] = {}  # rel_path -> source_json_hash

    def flush_batch() -> None:
        nonlocal total_chunks
        if not pending_records:
            return
        texts = [r.text for r in pending_records]
        vecs = embedder.embed_texts(texts)
        embedded = [
            EmbeddedChunk(record=r, dense=v.dense, sparse=v.sparse)
            for r, v in zip(pending_records, vecs)
        ]
        writer.upsert(embedded)
        total_chunks += len(embedded)
        pending_records.clear()

    for i, (loaded, fail) in enumerate(reader.iter_loaded(scan_dir)):
        if limit and i >= limit:
            break
        if fail is not None:
            failed += 1
            console.print(f"[red]FAIL[/red] {fail.rel_path}: {fail.error}")
            continue
        assert loaded is not None

        prev = manifest.files.get(loaded.rel_path)
        if (
            not rebuild
            and prev is not None
            and prev.source_json_hash == loaded.source_json_hash
        ):
            skipped += 1
            continue

        norm = normalize(loaded.document)
        ctx = BuilderContext(
            source_root_alias=settings.source_root_alias,
            source_file=loaded.rel_path,
            source_json_hash=loaded.source_json_hash,
            schema_version=settings.schema_version,
            embedding_provider=settings.embedding_provider,
            indexed_at=_now_iso(),
        )
        records = builder.build(norm, ctx)
        renderer.render(norm, records)

        # If we previously had different chunk keys for this file, delete the stale ones.
        if prev is not None:
            new_keys = {r.chunk_key for r in records}
            stale = [k for k in prev.chunk_keys if k not in new_keys]
            if stale:
                writer.delete_by_chunk_keys(stale)

        pending_records.extend(records)
        pending_file_chunks[loaded.rel_path] = [r.chunk_key for r in records]
        pending_files[loaded.rel_path] = loaded.source_json_hash
        indexed += 1

        if len(pending_records) >= settings.index_batch_size:
            flush_batch()
            # Persist manifest progress after each flush.
            for rel, h in pending_files.items():
                manifest.files[rel] = manifest_mod.FileEntry(
                    source_json_hash=h,
                    chunk_keys=pending_file_chunks[rel],
                    indexed_at=_now_iso(),
                )
            manifest_mod.save(settings.manifest_path, manifest)
            pending_files.clear()
            pending_file_chunks.clear()

    flush_batch()
    for rel, h in pending_files.items():
        manifest.files[rel] = manifest_mod.FileEntry(
            source_json_hash=h,
            chunk_keys=pending_file_chunks[rel],
            indexed_at=_now_iso(),
        )
    manifest_mod.save(settings.manifest_path, manifest)

    elapsed = time.time() - started
    table = Table(title="Index report")
    table.add_column("metric")
    table.add_column("value", justify="right")
    table.add_row("collection", settings.qdrant_collection)
    table.add_row("embedding_provider", settings.embedding_provider)
    table.add_row("indexed_files", str(indexed))
    table.add_row("skipped_files", str(skipped))
    table.add_row("failed_files", str(failed))
    table.add_row("chunks", str(total_chunks))
    table.add_row("elapsed_sec", f"{elapsed:.1f}")
    console.print(table)


# ---------- stats ----------


@app.command()
def stats(
    scan_dir: Optional[Path] = typer.Argument(None),
    collection: Optional[str] = typer.Option(None, "--collection"),
) -> None:
    """Show source-side stats (when scan_dir given) and/or Qdrant collection stats."""
    settings = load_settings()

    if scan_dir is not None:
        s = stats_mod.source_stats(scan_dir, settings.source_root)
        table = Table(title=f"Source stats: {scan_dir}")
        table.add_column("metric")
        table.add_column("value", justify="right")
        table.add_row("files", str(s.files))
        table.add_row("failed", str(s.failed))
        table.add_row("units", str(s.units))
        table.add_row("tasks", str(s.tasks))
        table.add_row("blocks", str(s.blocks))
        table.add_row("missing_version", str(s.missing_version))
        table.add_row("missing_job_category", str(s.missing_job_category))
        table.add_row("multi_task_groups", str(s.multi_task_groups))
        table.add_row("zero_block_units", str(s.zero_block_units))
        table.add_row("empty_attitudes", str(s.empty_attitudes))
        console.print(table)

    if collection:
        client = make_client(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        c = stats_mod.collection_stats(client, collection)
        table = Table(title=f"Collection: {c.name}")
        table.add_column("metric")
        table.add_column("value", justify="right")
        table.add_row("total_points", str(c.total_points))
        for lvl, n in c.by_level.items():
            table.add_row(f"level_{lvl}", str(n))
        console.print(table)


# ---------- doctor ----------


@app.command()
def doctor(
    scan_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    show_files: int = typer.Option(10, "--show-files", help="Sample up to N problematic files."),
) -> None:
    """Report known data issues — does not abort on missing version / category."""
    settings = load_settings()
    reader = OCSJSONReader(settings.source_root)
    issues_missing_version: list[str] = []
    issues_missing_category: list[str] = []
    issues_zero_block: list[str] = []
    issues_multi_task: list[str] = []
    failed: list[tuple[str, str]] = []

    for loaded, fail in reader.iter_loaded(scan_dir):
        if fail is not None:
            failed.append((fail.rel_path, fail.error))
            continue
        assert loaded is not None
        norm = normalize(loaded.document)
        if norm.version is None:
            issues_missing_version.append(loaded.rel_path)
        if norm.job_category is None:
            issues_missing_category.append(loaded.rel_path)
        for u in norm.units:
            block_count = sum(len(g.blocks) for g in u.task_groups)
            if block_count == 0:
                issues_zero_block.append(f"{loaded.rel_path}::{u.unit_key}")
            for g in u.task_groups:
                if len(g.task_ids) > 1:
                    issues_multi_task.append(
                        f"{loaded.rel_path}::{u.unit_key}::{','.join(g.task_ids)}"
                    )

    table = Table(title="Doctor")
    table.add_column("metric")
    table.add_column("value", justify="right")
    table.add_row("parse_failed", str(len(failed)))
    table.add_row("missing_version", str(len(issues_missing_version)))
    table.add_row("missing_job_category", str(len(issues_missing_category)))
    table.add_row("zero_block_units", str(len(issues_zero_block)))
    table.add_row("multi_task_groups", str(len(issues_multi_task)))
    console.print(table)

    def _print_sample(label: str, items: list, key=lambda x: x) -> None:
        if not items:
            return
        console.print(f"\n[bold]{label}[/bold] (first {show_files}):")
        for it in items[:show_files]:
            console.print(f"  - {key(it)}")

    _print_sample("parse_failed", failed, key=lambda x: f"{x[0]}: {x[1]}")
    _print_sample("missing_version", issues_missing_version)
    _print_sample("missing_job_category", issues_missing_category)
    _print_sample("zero_block_units", issues_zero_block)
    _print_sample("multi_task_groups", issues_multi_task)


# ---------- smoke-query ----------


@app.command(name="smoke-query")
def smoke_query_cmd(
    collection: str = typer.Option(..., "--collection"),
    ocs_code: Optional[str] = typer.Option(None, "--ocs-code"),
    knowledge: Optional[list[str]] = typer.Option(None, "--knowledge", "-k"),
    skill: Optional[list[str]] = typer.Option(None, "--skill", "-s"),
    probe_vector: Optional[str] = typer.Option(None, "--probe-vector"),
    limit: int = typer.Option(10, "--limit"),
) -> None:
    """Validate the indexed collection. Output is not a stable API."""
    settings = load_settings()
    client = make_client(url=settings.qdrant_url, api_key=settings.qdrant_api_key)

    if ocs_code:
        hits = smoke_query.retrieve_by_ocs_code(client, collection, ocs_code, limit=200)
        _print_hits(f"by ocs_code={ocs_code}", hits[:limit])
        console.print(f"[dim]total matched: {len(hits)}[/dim]")

    if knowledge or skill:
        hits = smoke_query.filter_by_ks_code(
            client,
            collection,
            knowledge=knowledge or None,
            skill=skill or None,
            limit=limit,
        )
        _print_hits(f"by k={knowledge} s={skill}", hits)

    if probe_vector:
        from jd_ocs_indexer.embeddings.bge_m3 import BGEM3Embedder

        embedder = BGEM3Embedder(
            model_name=settings.bge_m3_model,
            device=settings.bge_m3_device,
            use_fp16=settings.bge_m3_use_fp16,
            batch_size=1,
        )
        vec = embedder.embed_query(probe_vector)
        dense_hits = smoke_query.probe_dense(client, collection, vec.dense, limit=limit)
        _print_hits(f"dense probe: {probe_vector!r}", dense_hits)

        if vec.sparse and vec.sparse.indices:
            sparse_hits = smoke_query.probe_sparse(
                client,
                collection,
                vec.sparse.indices,
                vec.sparse.values,
                limit=limit,
            )
            _print_hits(f"sparse probe: {probe_vector!r}", sparse_hits)


def _print_hits(title: str, hits: list) -> None:
    table = Table(title=title)
    table.add_column("score", justify="right")
    table.add_column("level")
    table.add_column("ocs_code")
    table.add_column("job_title")
    table.add_column("chunk_key", overflow="fold")
    for h in hits:
        score_str = f"{h.score:.4f}" if h.score is not None else "-"
        table.add_row(score_str, h.chunk_level, h.ocs_code, h.job_title, h.chunk_key)
    console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
