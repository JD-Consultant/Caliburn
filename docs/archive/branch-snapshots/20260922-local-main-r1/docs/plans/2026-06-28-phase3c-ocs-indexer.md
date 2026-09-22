# Phase 3c — `apps/ocs-indexer` Embedding-Version Tag + Thin CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement
> this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (A) record the embedding model identity with each Qdrant collection and validate it
before querying (fail fast, never silent garbage); (B) lift pipeline orchestration out of the
394-line CLI into reusable functions so the CLI is a thin interface layer.

**Architecture:** Embedding identity as a stable `EmbeddingSignature` on the embedding
contract, persisted as a reserved **manifest point** (`chunk_level="_manifest"`, fixed id) and
checked with `assert_compatible` at query entry points (Qdrant official migration guidance;
Zilliz versioning FAQ; TianPan "validate compatibility up-front, not at query time"). Pure
orchestration functions (`embeddings/factory.py`, `pipeline.py`) with the CLI/`api.app` as thin
callers (Typer official: business logic in testable pure functions). Research record:
`docs/specs/2026-06-28-ocs-indexer-embedding-version-thin-cli-research.md`.

**Tech Stack:** Python, Typer, Qdrant (qdrant-client), BGE-M3 (FlagEmbedding), pytest.

## Global Constraints

- **Threads:** B (factory + pipeline extraction) is **move-only**; A (signature + manifest +
  validation) is a **feature → TDD** (failing test first).
- **Safety net = pytest.** Baseline: **`uv run --all-extras pytest -q` → 35 passed** (uses
  fakes; no live Qdrant/torch). After each task: all prior tests still pass; feature tasks add
  new passing tests. Run from `apps/ocs-indexer`; prefix `PYTHONUTF8=1`.
- **No behaviour change in Thread B** (function bodies move verbatim); presentation (rich
  tables/console) stays in `cli.py`.
- **Manifest = a single reserved point** (decision D-3c-1), not per-point payload, not
  collection-name encoding. It must never appear in `profile`/`task` search results.
- **Do not** build live model migration (named-vectors/dual-write — future, noted in ADR), or
  change the embedding model. Don't touch `apps/{api,web,pdf-to-json}`.
- Commit per task; suite green first. Working dir: `/s/caliburn/apps/ocs-indexer`; commit from
  `/s/caliburn`.

---

## Task 1: `embeddings/factory.py` — one place to build the embedder (move-only)

**Files:**
- Create: `src/jd_ocs_indexer/embeddings/factory.py`
- Modify: `src/jd_ocs_indexer/cli.py` (`index`, `query`), `src/jd_ocs_indexer/api/app.py`

**Interfaces:**
- Produces: `make_embedder(settings, *, batch_size: int | None = None) -> EmbeddingService`.

- [ ] **Step 1: Write the factory.**

```python
"""Embedding service factory — the single construction site for the embedder."""
from __future__ import annotations

from jd_ocs_indexer.config import Settings
from jd_ocs_indexer.embeddings.base import EmbeddingService


def make_embedder(settings: Settings, *, batch_size: int | None = None) -> EmbeddingService:
    from jd_ocs_indexer.embeddings.bge_m3 import BGEM3Embedder  # lazy: avoid torch on import

    return BGEM3Embedder(
        model_name=settings.bge_m3_model,
        device=settings.bge_m3_device,
        use_fp16=settings.bge_m3_use_fp16,
        batch_size=batch_size if batch_size is not None else settings.bge_m3_batch_size,
    )
```

- [ ] **Step 2: Rewire `cli.index`.** Replace its inline `from ... import BGEM3Embedder` +
  `embedder = BGEM3Embedder(...)` with `from jd_ocs_indexer.embeddings.factory import make_embedder`
  and `embedder = make_embedder(settings)`.

- [ ] **Step 3: Rewire `cli.query`.** Same, but `embedder = make_embedder(settings, batch_size=1)`
  (preserves the current query-time `batch_size=1`).

- [ ] **Step 4: Rewire `api/app.py` lifespan.** Replace the inline `BGEM3Embedder(...)` (the
  `else` branch) with `from jd_ocs_indexer.embeddings.factory import make_embedder` +
  `app.state.embedder = make_embedder(s, batch_size=1)`.

- [ ] **Step 5: Run the suite.** `PYTHONUTF8=1 uv run --all-extras pytest -q` → **35 passed**.

- [ ] **Step 6: Commit.**

```bash
cd /s/caliburn && git add -A && git commit -m "refactor(ocs-indexer): extract embeddings/factory.make_embedder (Phase 3c T1)

Single construction site for BGEM3Embedder; index/query/api.app now call
make_embedder instead of copy-pasting construction. Move-only; 35 passed."
```

---

## Task 2: `pipeline.py` — extract `run_index` so the CLI is thin (move-only + 1 test)

**Files:**
- Create: `src/jd_ocs_indexer/pipeline.py`
- Create: `tests/test_pipeline.py`
- Modify: `src/jd_ocs_indexer/cli.py` (`index` becomes a thin wrapper)

**Interfaces:**
- Produces: `IndexReport(collection, indexed_files, failed_files, points, elapsed_sec, failures)`;
  `run_index(settings, scan_dir, *, limit=0, embedder=None, client=None) -> IndexReport`.
  (`embedder`/`client` injectable for tests; default to real factory/`make_client`.)

- [ ] **Step 1: Write `pipeline.py`** — move the orchestration body verbatim from `cli.index`,
  returning a report instead of printing. Collect per-file failures into `report.failures`.

```python
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
```

- [ ] **Step 2: Thin `cli.index`.** Replace its body with a `run_index` call + the rich table
  + the per-failure red lines (preserve the existing output columns):

```python
@app.command()
def index(scan_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
          limit: int = typer.Option(0, "--limit", help="Stop after N files (0 = all).")) -> None:
    """v3 pipeline: reader -> normalize -> build -> embed -> upsert (profile + task points)."""
    from jd_ocs_indexer.pipeline import run_index
    settings = load_settings()
    report = run_index(settings, scan_dir, limit=limit)
    for rel, err in report.failures:
        console.print(f"[red]FAIL[/red] {rel}: {err}")
    table = Table(title="Index v3 report")
    table.add_column("metric"); table.add_column("value", justify="right")
    table.add_row("collection", report.collection)
    table.add_row("indexed_files", str(report.indexed_files))
    table.add_row("failed_files", str(report.failed_files))
    table.add_row("points", str(report.points))
    table.add_row("elapsed_sec", f"{report.elapsed_sec:.1f}")
    console.print(table)
```

  Then remove now-unused imports from `cli.py` (e.g. `BuildContext, build, normalize,
  OCSJSONReader, EmbeddedChunk, QdrantWriter`, `_now_iso` if unused elsewhere) — verify with
  `ruff`/grep that each removed name has no other use in `cli.py` first.

- [ ] **Step 3: Write `tests/test_pipeline.py`** — `run_index` with injected fakes (a fake
  reader dir via tmp + `StubEmbedder` + a fake writer/client) OR the lighter unit: assert the
  report aggregates counts. Minimal fake-client test:

```python
from pathlib import Path
from jd_ocs_indexer.pipeline import run_index, IndexReport

def test_run_index_empty_dir_reports_zero(tmp_path: Path, stub_embedder, monkeypatch):
    from jd_ocs_indexer import pipeline
    class _W:  # writer stand-in
        def __init__(self,*a,**k): pass
        def ensure_collection(self): pass
        def ensure_payload_indexes(self,*a,**k): pass
        def upsert(self, chunks): raise AssertionError("no files → no upsert")
    monkeypatch.setattr(pipeline, "QdrantWriter", _W)
    from jd_ocs_indexer.config import load_settings
    rep = run_index(load_settings(), tmp_path, embedder=stub_embedder, client=object())
    assert isinstance(rep, IndexReport) and rep.indexed_files == 0 and rep.points == 0
```

- [ ] **Step 4: Run the suite.** `PYTHONUTF8=1 uv run --all-extras pytest -q` → **36 passed**.

- [ ] **Step 5: Commit.**

```bash
cd /s/caliburn && git add -A && git commit -m "refactor(ocs-indexer): extract pipeline.run_index; thin cli.index (Phase 3c T2)

Index orchestration moves to pipeline.py as run_index()->IndexReport; cli.index
is a thin wrapper that renders the report. cli.query already delegates to the
shared validation.search lib (factory removed its duplication in T1). +1 test."
```

---

## Task 3: `EmbeddingSignature` + manifest write (TDD)

**Files:**
- Modify: `src/jd_ocs_indexer/embeddings/base.py` (add `EmbeddingSignature` + `signature` to Protocol)
- Modify: `src/jd_ocs_indexer/embeddings/bge_m3.py` (add `signature` property + revision const)
- Create: `src/jd_ocs_indexer/store/manifest.py` (write/read + fixed id)
- Modify: `src/jd_ocs_indexer/pipeline.py` (`run_index` writes the manifest at the end)
- Modify: `tests/conftest.py` (`StubEmbedder.signature`)
- Create: `tests/test_manifest.py`

**Interfaces:**
- Produces: `EmbeddingSignature(provider, model, dim, revision)`; `EmbeddingService.signature`;
  `MANIFEST_POINT_ID`; `write_manifest(client, collection, sig, *, built_at=None)`;
  `read_manifest(client, collection) -> EmbeddingSignature | None`.

- [ ] **Step 1 (failing test): `tests/test_manifest.py`.**

```python
from jd_ocs_indexer.embeddings.base import EmbeddingSignature
from jd_ocs_indexer.store import manifest as M

def test_bge_signature():
    from jd_ocs_indexer.embeddings.bge_m3 import BGEM3Embedder
    sig = BGEM3Embedder(model_name="BAAI/bge-m3").signature
    assert sig == EmbeddingSignature(provider="bge-m3", model="BAAI/bge-m3", dim=1024, revision=1)

def test_manifest_round_trip(make_qdrant):
    sig = EmbeddingSignature("bge-m3", "BAAI/bge-m3", 1024, 1)
    captured = {}
    class C:
        def upsert(self, **kw): captured["points"] = kw["points"]
        def retrieve(self, **kw):
            from tests.conftest import FakePoint
            pts = captured.get("points") or []
            return [FakePoint(payload=p.payload) for p in pts]
    c = C()
    M.write_manifest(c, "ocs_v3", sig)
    assert M.read_manifest(c, "ocs_v3") == sig
```

- [ ] **Step 2: Run → fails** (`EmbeddingSignature` / `manifest` absent).
  `PYTHONUTF8=1 uv run --all-extras pytest tests/test_manifest.py -q`.

- [ ] **Step 3: Add the signature contract.** In `embeddings/base.py`:

```python
@dataclass(frozen=True)
class EmbeddingSignature:
    provider: str
    model: str
    dim: int
    revision: int
```

  Add to the `EmbeddingService` Protocol: `signature: "EmbeddingSignature"` (and import not
  needed — same module). In `embeddings/bge_m3.py` add `REVISION = 1` and:

```python
    @property
    def signature(self) -> EmbeddingSignature:
        return EmbeddingSignature(provider=self.provider, model=self.model_name,
                                  dim=self.dense_size, revision=self.REVISION)
```

  (import `EmbeddingSignature` from `.base`.)

- [ ] **Step 4: Add `store/manifest.py`.**

```python
"""Embedding-identity manifest: one reserved point per collection.

Stored as a single point (fixed id) with payload chunk_level="_manifest" so it is
naturally excluded from profile/task searches. Single source of truth for "which
embedder built this index"; read it to validate compatibility before querying.
"""
from __future__ import annotations

from datetime import datetime, timezone

from qdrant_client.http import models

from jd_ocs_indexer.embeddings.base import EmbeddingSignature

MANIFEST_POINT_ID = "00000000-0000-0000-0000-0000000a11fe"  # reserved sentinel
MANIFEST_LEVEL = "_manifest"


def write_manifest(client, collection: str, sig: EmbeddingSignature, *, built_at=None) -> None:
    payload = {"chunk_level": MANIFEST_LEVEL, "built_at": built_at or datetime.now(timezone.utc).isoformat(),
               "embedding": {"provider": sig.provider, "model": sig.model, "dim": sig.dim, "revision": sig.revision}}
    client.upsert(collection_name=collection, wait=True, points=[
        models.PointStruct(id=MANIFEST_POINT_ID, vector={"dense": [0.0] * sig.dim}, payload=payload)])


def read_manifest(client, collection: str) -> EmbeddingSignature | None:
    recs = client.retrieve(collection_name=collection, ids=[MANIFEST_POINT_ID],
                           with_payload=True, with_vectors=False)
    if not recs:
        return None
    emb = (recs[0].payload or {}).get("embedding") or {}
    if not emb:
        return None
    return EmbeddingSignature(provider=emb.get("provider", ""), model=emb.get("model", ""),
                              dim=int(emb.get("dim", 0)), revision=int(emb.get("revision", 0)))
```

- [ ] **Step 5: `run_index` writes the manifest.** In `pipeline.py`, replace the T2 placeholder
  comment with, after the loop: `from jd_ocs_indexer.store.manifest import write_manifest` and
  `write_manifest(client, settings.qdrant_collection, embedder.signature)` (only if
  `report.indexed_files` > 0, to avoid stamping an empty/aborted run).

- [ ] **Step 6: Add `signature` to the test fake.** In `tests/conftest.py` `StubEmbedder`:

```python
    @property
    def signature(self):
        from jd_ocs_indexer.embeddings.base import EmbeddingSignature
        return EmbeddingSignature(provider="stub", model="stub", dim=1024, revision=1)
```

- [ ] **Step 7: Run the suite.** `PYTHONUTF8=1 uv run --all-extras pytest -q` → **38 passed**
  (36 + 2 new).

- [ ] **Step 8: Commit.**

```bash
cd /s/caliburn && git add -A && git commit -m "feat(ocs-indexer): embedding signature + manifest point (Phase 3c T3)

EmbeddingService.signature (provider/model/dim/revision); run_index writes a
reserved _manifest point recording it. store/manifest.py read/write. TDD; 38 passed."
```

---

## Task 4: `assert_compatible` + validate before querying (TDD)

**Files:**
- Modify: `src/jd_ocs_indexer/embeddings/base.py` (`EmbeddingMismatchError`, `assert_compatible`)
- Modify: `src/jd_ocs_indexer/api/service.py` (validate in `search_tasks`/`search_occupations`; surface in `healthcheck`)
- Modify: `src/jd_ocs_indexer/api/app.py` (exception handler → 409/503)
- Modify: `src/jd_ocs_indexer/cli.py` (`query` validates; `doctor`/`stats` show index model)
- Create: `tests/test_compat.py`

**Interfaces:**
- Produces: `EmbeddingMismatchError`; `assert_compatible(manifest: EmbeddingSignature | None,
  current: EmbeddingSignature) -> None` — raises on provider/model/dim mismatch; `None`
  manifest = soft (log warning, allow — back-compat with pre-manifest indexes); revision
  mismatch = warning only.

- [ ] **Step 1 (failing test): `tests/test_compat.py`.**

```python
import pytest
from jd_ocs_indexer.embeddings.base import EmbeddingSignature, EmbeddingMismatchError, assert_compatible
from jd_ocs_indexer.api import service
from jd_ocs_indexer.store.manifest import MANIFEST_POINT_ID  # noqa: F401

def test_assert_compatible_raises_on_model_diff():
    cur = EmbeddingSignature("bge-m3", "BAAI/bge-m3", 1024, 1)
    with pytest.raises(EmbeddingMismatchError):
        assert_compatible(EmbeddingSignature("bge-m3", "other/model", 1024, 1), cur)

def test_assert_compatible_allows_match_and_missing():
    cur = EmbeddingSignature("bge-m3", "BAAI/bge-m3", 1024, 1)
    assert_compatible(cur, cur)          # match → ok
    assert_compatible(None, cur)         # no manifest → soft allow

def test_search_tasks_raises_on_mismatch(make_qdrant, stub_embedder, fake_point):
    # manifest point retrieved with a different model → mismatch before searching
    mani = fake_point(payload={"chunk_level": "_manifest",
                               "embedding": {"provider": "stub", "model": "DIFFERENT", "dim": 1024, "revision": 1}})
    client = make_qdrant(retrieve_points=[mani], query_points=[])
    with pytest.raises(EmbeddingMismatchError):
        service.search_tasks(client, stub_embedder, "ocs_v3", query="x")
```

- [ ] **Step 2: Run → fails.** `PYTHONUTF8=1 uv run --all-extras pytest tests/test_compat.py -q`.

- [ ] **Step 3: Add error + checker** in `embeddings/base.py`:

```python
class EmbeddingMismatchError(RuntimeError):
    """Index was built with a different embedding model than the live embedder."""


def assert_compatible(manifest: "EmbeddingSignature | None", current: "EmbeddingSignature") -> None:
    import logging
    log = logging.getLogger("jd_ocs_indexer")
    if manifest is None:
        log.warning("No embedding manifest in collection; cannot verify compatibility (pre-manifest index?).")
        return
    if (manifest.provider, manifest.model, manifest.dim) != (current.provider, current.model, current.dim):
        raise EmbeddingMismatchError(
            f"index embedder {manifest.provider}/{manifest.model}/{manifest.dim} "
            f"!= query embedder {current.provider}/{current.model}/{current.dim}")
    if manifest.revision != current.revision:
        log.warning("Embedding revision differs (index r%s vs query r%s).", manifest.revision, current.revision)
```

- [ ] **Step 4: Validate in `api/service.py`.** At the top of `search_tasks` and
  `search_occupations`, before `embedder.embed_query`:
  `assert_compatible(read_manifest(client, collection), embedder.signature)`
  (import `read_manifest` from `jd_ocs_indexer.store.manifest`, `assert_compatible` from
  `jd_ocs_indexer.embeddings.base`). Extend `healthcheck` to read the manifest and add
  `"index_model": f"{m.provider}/{m.model}/{m.dim}" if m else None`.

- [ ] **Step 5: Map the error to HTTP** in `api/app.py`:

```python
    from jd_ocs_indexer.embeddings.base import EmbeddingMismatchError

    @app.exception_handler(EmbeddingMismatchError)
    async def _embed_mismatch(request, exc):  # noqa: ANN001
        return JSONResponse(status_code=409, content={"detail": f"embedding mismatch: {exc}"})
```

- [ ] **Step 6: `cli query` validates; `doctor`/`stats` show the index model.** In `cli.query`,
  after building `embedder` and `client`: `assert_compatible(read_manifest(client, coll),
  embedder.signature)` (let it raise — Typer prints the error, non-zero exit). In `doctor` and
  the Qdrant branch of `stats`, read the manifest and print an `index_model` row (best-effort;
  ignore if collection absent).

- [ ] **Step 7: Run the suite.** `PYTHONUTF8=1 uv run --all-extras pytest -q` → **41 passed**
  (38 + 3 new). If `test_service_stats_health.py` asserted the exact `healthcheck` dict shape,
  update it for the new `index_model` key.

- [ ] **Step 8: Commit.**

```bash
cd /s/caliburn && git add -A && git commit -m "feat(ocs-indexer): validate embedding compatibility before query (Phase 3c T4)

assert_compatible() reads the manifest and fails fast (EmbeddingMismatchError,
HTTP 409) when the query embedder != the index embedder; healthcheck/doctor/stats
surface the index model. TDD; 41 passed."
```

---

## Task 5: ADR + tag

**Files:** Create `docs/adr/0009-embedding-version-manifest.md`; modify `docs/adr/README.md`.

- [ ] **Step 1: Write ADR 0009** (Chinese, Nygard-style like 0008): context (embedding identity
  untracked → silent-garbage risk on model/dim change; CLI carried orchestration); decision
  (stable `EmbeddingSignature`; reserved `_manifest` point; `assert_compatible` fail-fast before
  query; `make_embedder`/`run_index` thin the CLI); consequences (no silent space-mismatch; CLI
  reusable); status Accepted 2026-06-28; known follow-ups (live named-vectors/dual-write
  migration; per-query manifest read could be cached/startup-validated). Link the research
  record. Add the index row to `docs/adr/README.md`.

- [ ] **Step 2: Commit + tag.**

```bash
cd /s/caliburn
git add docs/adr/0009-embedding-version-manifest.md docs/adr/README.md
git commit -m "docs(adr): 0009 embedding-version manifest + thin CLI (Phase 3c)"
git tag -a phase3c-ocs-indexer -m "Phase 3c: embedding signature + manifest validation (fail-fast) + thin CLI (factory/run_index). 41 passed."
```

---

## Self-Review notes
- **Spec coverage:** research §6 T1–T5 ↔ plan Tasks 1–5. Thread B = T1–T2 (move-only), Thread
  A = T3–T4 (TDD), T5 = ADR/tag.
- **Type consistency:** `make_embedder`, `IndexReport`, `run_index`, `EmbeddingSignature`
  (provider/model/dim/revision), `MANIFEST_POINT_ID`, `write_manifest`/`read_manifest`,
  `EmbeddingMismatchError`, `assert_compatible` — names stable across tasks; `BGEM3Embedder`
  exposes `model_name`/`dense_size`/`provider` (already present) → `signature` derives from them.
- **Risk:** manifest leaking into search results — searches filter `chunk_level` ∈
  {profile,task}; the `_manifest` point can't match. Add/keep a test if a search-level test
  exists. Stats may +1 — exclude manifest from counts if `stats` totals are asserted.
- **Net:** counts must climb 35→36(T2)→38(T3)→41(T4); any prior test regressing = stop & fix.
