"""CLI entrypoint: index / stats / doctor / smoke-query / query / serve."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from jd_ocs_indexer.config import load_settings
from jd_ocs_indexer.ingestion.builder import BuildContext, build
from jd_ocs_indexer.ingestion.normalizer import normalize
from jd_ocs_indexer.ingestion.reader import OCSJSONReader
from jd_ocs_indexer.models.chunk import EmbeddedChunk
from jd_ocs_indexer.store.qdrant_client import make_client
from jd_ocs_indexer.store.writer import QdrantWriter
from jd_ocs_indexer.validation import search as search_mod, smoke_query, stats as stats_mod

app = typer.Typer(
    add_completion=False,
    help="jd-ocs-indexer: OCS JSON -> Qdrant index builder.",
)
console = Console()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


# ---------- index ----------


@app.command()
def index(
    scan_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    limit: int = typer.Option(0, "--limit", help="Stop after N files (0 = all)."),
) -> None:
    """v3 pipeline: reader -> normalize -> build -> embed -> upsert (profile + task points)."""
    settings = load_settings()
    reader = OCSJSONReader(settings.source_root)

    from jd_ocs_indexer.embeddings.bge_m3 import BGEM3Embedder
    from jd_ocs_indexer.store import schema

    embedder = BGEM3Embedder(
        model_name=settings.bge_m3_model,
        device=settings.bge_m3_device,
        use_fp16=settings.bge_m3_use_fp16,
        batch_size=settings.bge_m3_batch_size,
    )
    client = make_client(url=settings.qdrant_url, api_key=settings.qdrant_api_key, timeout=settings.qdrant_timeout)
    writer = QdrantWriter(
        client,
        settings.qdrant_collection,
        dense_size=embedder.dense_size,
        supports_sparse=embedder.supports_sparse,
        batch_size=settings.index_batch_size,
    )
    writer.ensure_collection()
    writer.ensure_payload_indexes(schema.PAYLOAD_INDEXES)

    started = time.time()
    indexed = failed = total = 0
    for i, (loaded, fail) in enumerate(reader.iter_loaded(scan_dir)):
        if limit and i >= limit:
            break
        if fail is not None:
            failed += 1
            console.print(f"[red]FAIL[/red] {fail.rel_path}: {fail.error}")
            continue
        assert loaded is not None
        norm = normalize(loaded.document)
        ctx = BuildContext(source_file=loaded.rel_path, indexed_at=_now_iso())
        records = build(norm, ctx)
        vecs = embedder.embed_texts([r.text for r in records])
        embedded = [EmbeddedChunk(record=r, dense=v.dense, sparse=v.sparse) for r, v in zip(records, vecs)]
        report = writer.upsert(embedded)
        total += report.upserted
        indexed += 1

    elapsed = time.time() - started
    table = Table(title="Index v3 report")
    table.add_column("metric")
    table.add_column("value", justify="right")
    table.add_row("collection", settings.qdrant_collection)
    table.add_row("indexed_files", str(indexed))
    table.add_row("failed_files", str(failed))
    table.add_row("points", str(total))
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
        client = make_client(url=settings.qdrant_url, api_key=settings.qdrant_api_key, timeout=settings.qdrant_timeout)
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
    client = make_client(url=settings.qdrant_url, api_key=settings.qdrant_api_key, timeout=settings.qdrant_timeout)

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


# ---------- query ----------


@app.command()
def query(
    text: str = typer.Argument(..., help="Natural-language query."),
    collection: Optional[str] = typer.Option(None, "--collection"),
    level: Optional[str] = typer.Option(
        None, "--level", "-l",
        help="Filter chunk level: profile / unit / block.",
    ),
    ocs_code: Optional[str] = typer.Option(None, "--ocs-code"),
    top_k: int = typer.Option(10, "--top-k", "-k"),
    hybrid: bool = typer.Option(
        False, "--hybrid", "-H",
        help="Use dense+sparse RRF fusion instead of dense-only.",
    ),
    text_lines: int = typer.Option(
        4, "--text-lines",
        help="Number of body lines to show per hit (0 = no body).",
    ),
) -> None:
    """Run a natural-language query against the indexed collection."""
    settings = load_settings()
    coll = collection or settings.qdrant_collection
    client = make_client(url=settings.qdrant_url, api_key=settings.qdrant_api_key, timeout=settings.qdrant_timeout)

    from jd_ocs_indexer.embeddings.bge_m3 import BGEM3Embedder

    embedder = BGEM3Embedder(
        model_name=settings.bge_m3_model,
        device=settings.bge_m3_device,
        use_fp16=settings.bge_m3_use_fp16,
        batch_size=1,
    )
    vec = embedder.embed_query(text)

    if hybrid:
        hits = search_mod.hybrid_search(
            client,
            coll,
            vec.dense,
            vec.sparse.indices if vec.sparse else [],
            vec.sparse.values if vec.sparse else [],
            level=level,
            ocs_code=ocs_code,
            limit=top_k,
        )
        mode = "hybrid"
    else:
        hits = search_mod.dense_search(
            client,
            coll,
            vec.dense,
            level=level,
            ocs_code=ocs_code,
            limit=top_k,
        )
        mode = "dense"

    console.print(
        f"[bold]query[/bold]={text!r}  [dim]mode={mode}  collection={coll}  "
        f"level={level or '*'}  ocs_code={ocs_code or '*'}  top_k={top_k}[/dim]"
    )
    if not hits:
        console.print("[yellow]no hits[/yellow]")
        return

    for i, h in enumerate(hits, start=1):
        _print_query_hit(i, h, text_lines=text_lines)


# ---------- serve ----------


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host (localhost by default)."),
    port: int = typer.Option(8000, "--port"),
) -> None:
    """Run the query API (FastAPI + uvicorn, single worker, loads BGE-M3 once)."""
    import uvicorn

    uvicorn.run(
        "jd_ocs_indexer.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        workers=1,
    )


def _print_query_hit(idx: int, hit, text_lines: int) -> None:
    p = hit.payload
    score = f"{hit.score:.4f}" if hit.score is not None else "-"
    level_color = {"profile": "magenta", "unit": "cyan", "block": "green"}.get(
        hit.chunk_level, "white"
    )
    head = (
        f"[bold][{idx}][/bold] [dim]score=[/dim]{score}  "
        f"[{level_color}]{hit.chunk_level}[/{level_color}]  "
        f"[dim]ocs=[/dim]{hit.ocs_code}"
    )
    cl = p.get("competency_level")
    if cl is not None:
        head += f"  [dim]L{cl}[/dim]"
    console.print(head)

    breadcrumb_parts: list[str] = [hit.job_title or "?"]
    if p.get("unit_title"):
        unit_id = p.get("unit_id") or ""
        breadcrumb_parts.append(f"{unit_id} {p['unit_title']}".strip())
    task_titles = p.get("task_titles") or []
    if task_titles:
        task_ids = p.get("task_ids") or []
        tid = task_ids[0] if task_ids else ""
        breadcrumb_parts.append(f"{tid} {task_titles[0]}".strip())
    if p.get("block_order") is not None and hit.chunk_level == "block":
        breadcrumb_parts.append(f"區塊#{p['block_order']}")
    elif p.get("block_title"):  # legacy v1 payload fallback
        breadcrumb_parts.append(p["block_title"])
    console.print("    [dim]path:[/dim] " + " / ".join(breadcrumb_parts))

    # v2: prefer pair structures for human-readable display.
    k_pairs = p.get("k_pairs") or []
    s_pairs = p.get("s_pairs") or []
    if k_pairs:
        shown = ", ".join(f"{kp['code']} {kp['name']}" for kp in k_pairs[:5])
        if len(k_pairs) > 5:
            shown += f" (+{len(k_pairs) - 5} more)"
        console.print(f"    [dim]K:[/dim] {shown}")
    if s_pairs:
        shown = ", ".join(f"{sp['code']} {sp['name']}" for sp in s_pairs[:5])
        if len(s_pairs) > 5:
            shown += f" (+{len(s_pairs) - 5} more)"
        console.print(f"    [dim]S:[/dim] {shown}")
    # legacy v1 fallback: show codes-only if pairs missing
    if not k_pairs and not s_pairs:
        k = p.get("k_codes") or []
        s = p.get("s_codes") or []
        if k or s:
            console.print(
                "    [dim]codes:[/dim] "
                + (f"K={','.join(k)}" if k else "")
                + ("  " if k and s else "")
                + (f"S={','.join(s)}" if s else "")
            )

    src = p.get("source_file")
    if src:
        console.print(f"    [dim]src:[/dim] {src}")

    if text_lines > 0:
        body = (p.get("text") or "").strip().splitlines()
        # Skip the title line (always `# job_title (ocs_code)`)
        body_lines = [ln for ln in body[1:] if ln.strip()][:text_lines]
        if body_lines:
            for ln in body_lines:
                console.print(f"    [dim]│[/dim] {ln}")
    console.print()


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
