"""CLI entrypoint: index / stats / doctor / smoke-query / query / serve."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from jd_ocs_indexer.config import load_settings
from jd_ocs_indexer.ingestion.normalizer import normalize
from jd_ocs_indexer.ingestion.reader import OCSJSONReader
from jd_ocs_indexer.store.qdrant_client import make_client
from jd_ocs_indexer.validation import search as search_mod, smoke_query, stats as stats_mod

app = typer.Typer(
    add_completion=False,
    help="jd-ocs-indexer: OCS JSON -> Qdrant index builder.",
)
console = Console()


# ---------- index ----------


@app.command()
def index(
    scan_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    limit: int = typer.Option(0, "--limit", help="Stop after N files (0 = all)."),
) -> None:
    """v3 pipeline: reader -> normalize -> build -> embed -> upsert (profile + task points)."""
    from jd_ocs_indexer.pipeline import run_index

    settings = load_settings()
    report = run_index(settings, scan_dir, limit=limit)
    for rel, err in report.failures:
        console.print(f"[red]FAIL[/red] {rel}: {err}")

    table = Table(title="Index v3 report")
    table.add_column("metric")
    table.add_column("value", justify="right")
    table.add_row("collection", report.collection)
    table.add_row("indexed_files", str(report.indexed_files))
    table.add_row("failed_files", str(report.failed_files))
    table.add_row("points", str(report.points))
    table.add_row("elapsed_sec", f"{report.elapsed_sec:.1f}")
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
        from jd_ocs_indexer.store.manifest import read_manifest

        m = read_manifest(client, collection)
        table = Table(title=f"Collection: {c.name}")
        table.add_column("metric")
        table.add_column("value", justify="right")
        table.add_row("total_points", str(c.total_points))
        table.add_row("index_model", f"{m.provider}/{m.model}/{m.dim}" if m else "—")
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

    if probe_vector:
        from jd_ocs_indexer.embeddings.factory import make_embedder

        embedder = make_embedder(settings)
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
        help="Filter chunk level: profile / task.",
    ),
    ocs_code: Optional[str] = typer.Option(None, "--ocs-code"),
    top_k: int = typer.Option(10, "--top-k", "-k"),
    hybrid: bool = typer.Option(
        False, "--hybrid", "-H",
        help="Use dense+sparse RRF fusion instead of dense-only.",
    ),
) -> None:
    """Run a natural-language query against the indexed collection."""
    settings = load_settings()
    coll = collection or settings.qdrant_collection
    client = make_client(url=settings.qdrant_url, api_key=settings.qdrant_api_key, timeout=settings.qdrant_timeout)

    from jd_ocs_indexer.embeddings.base import assert_compatible
    from jd_ocs_indexer.embeddings.factory import make_embedder
    from jd_ocs_indexer.store.manifest import read_manifest

    embedder = make_embedder(settings, batch_size=1)
    assert_compatible(read_manifest(client, coll), embedder.signature)
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
        _print_query_hit(i, h)


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


def _print_query_hit(idx: int, hit) -> None:
    p = hit.payload
    score = f"{hit.score:.4f}" if hit.score is not None else "-"
    level_color = {"profile": "magenta", "task": "green"}.get(hit.chunk_level, "white")
    head = (
        f"[bold][{idx}][/bold] [dim]score=[/dim]{score}  "
        f"[{level_color}]{hit.chunk_level}[/{level_color}]  "
        f"[dim]ocs=[/dim]{hit.ocs_code}"
    )
    cl = p.get("competency_level")
    if cl is not None:
        head += f"  [dim]L{cl}[/dim]"
    if hit.id is not None:
        head += f"  [dim]id=[/dim]{hit.id}"
    console.print(head)

    breadcrumb_parts: list[str] = [hit.job_title or "?"]
    if p.get("unit_title"):
        unit_id = p.get("unit_id") or ""
        breadcrumb_parts.append(f"{unit_id} {p['unit_title']}".strip())
    if p.get("task_title"):
        tid = p.get("task_id") or ""
        breadcrumb_parts.append(f"{tid} {p['task_title']}".strip())
    console.print("    [dim]path:[/dim] " + " / ".join(breadcrumb_parts))

    def _print_pairs(label: str, pairs: list) -> None:
        if not pairs:
            return
        shown = ", ".join(f"{p['code']} {p['name']}" for p in pairs[:5])
        if len(pairs) > 5:
            shown += f" (+{len(pairs) - 5} more)"
        console.print(f"    [dim]{label}:[/dim] {shown}")

    _print_pairs("K", p.get("k_pairs") or [])
    _print_pairs("S", p.get("s_pairs") or [])
    _print_pairs("O", p.get("output_pairs") or [])

    acts = p.get("activity_examples") or []
    if acts:
        console.print(f"    [dim]活動:[/dim] {', '.join(acts[:5])}")

    src = p.get("source_file")
    if src:
        console.print(f"    [dim]src:[/dim] {src}")
    console.print()


def _print_hits(title: str, hits: list) -> None:
    table = Table(title=title)
    table.add_column("score", justify="right")
    table.add_column("level")
    table.add_column("ocs_code")
    table.add_column("job_title")
    table.add_column("id", overflow="fold")
    for h in hits:
        score_str = f"{h.score:.4f}" if h.score is not None else "-"
        table.add_row(score_str, h.chunk_level, h.ocs_code, h.job_title, str(h.id) if h.id is not None else "-")
    console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
