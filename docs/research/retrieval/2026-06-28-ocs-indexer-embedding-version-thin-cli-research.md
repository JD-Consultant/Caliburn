# Phase 3c Research Record — `apps/ocs-indexer` Embedding-Version Tag + Thin CLI

> Research record (權威資料 + 診斷). Authored 2026-06-28. Sub-project of the Caliburn
> per-project internal-optimization phase (Phase 3). Companion to the implementation
> plan `docs/plans/2026-06-28-phase3c-ocs-indexer.md`.

## 1. Goal

Two threads for the OCS knowledge service (`apps/ocs-indexer`: pdfplumber-JSON → BGE-M3 →
Qdrant; FastAPI query API consumed by `apps/api`):

- **A. Embedding-version tag** — record *which embedding model* produced a collection's
  vectors and **validate it up-front** so a model/dim change can never silently return
  garbage similarities. Today this identity is recorded **nowhere**.
- **B. Thin CLI** — the 394-line `cli.py` embeds pipeline orchestration inside its command
  bodies. Extract that into reusable functions so the CLI is a thin interface layer and the
  same logic is reusable (API, batch, tests).

## 2. Current state (what the code actually does)

Evidence from reading the modules + grep.

### 2.1 Embedding identity is untracked
- `BGEM3Embedder` (`embeddings/bge_m3.py`): `provider = "bge-m3"`, `dense_size = 1024`,
  `model_name` configurable (`BGE_M3_MODEL`, default `BAAI/bge-m3`). The `EmbeddingService`
  Protocol (`embeddings/base.py`) exposes `provider`/`dense_size`/`supports_sparse` but **no
  stable signature** combining model + dim + a revision.
- Index (`cli.py::index`): builds the embedder from settings, `writer.ensure_collection()`,
  upserts points whose payload is just `record.payload`. **No embedding metadata is written.**
- Collection is `ocs_v3` (config default). The `version` payload index
  (`store/schema.py`) is the **OCS document version**, not the embedding model — confirmed by
  grep: the only embedding-identity datum anywhere is the `dense_size = 1024` constant.
- Query (`api/service.py::search_tasks/search_occupations`, `cli.py::query`): call
  `embedder.embed_query(...)` then search. **No check** that the query embedder matches what
  built the index. A changed `BGE_M3_MODEL` or dim ⇒ silent garbage or a runtime dim error.
- `healthcheck` reports `model_loaded` but not *which* model nor index compatibility.

### 2.2 CLI carries orchestration (not thin)
- `cli.py` is a Typer app: `index, stats, doctor, smoke-query, query, serve` (394 lines).
- `index` (~60 lines) inlines the whole pipeline: construct embedder + Qdrant client +
  `QdrantWriter`, `ensure_collection`/`ensure_payload_indexes`, then loop
  `reader → normalize → build → embed → upsert` + build a rich report table.
- `query` re-constructs the embedder and calls `validation.search` directly — **duplicating**
  the embed-then-search logic that already exists, in cleaner form, in `api/service.py`.
- Embedder construction (`BGEM3Embedder(model_name=…, device=…, …)`) is **copy-pasted** in
  `index`, `query`, and `api/app.py`.

What is **already clean** and must be preserved: `api/service.py` is pure-sync, FastAPI-free,
fake-testable orchestration over `(client, embedder, collection)` — the right "core action"
shape; the CLI `query`/`index` should converge on that style. `store/writer.py` already does
collection bootstrap + retrying batch upsert.

## 3. Authoritative sources & what they prescribe

| Source | Authority | Prescription relevant here |
|---|---|---|
| Qdrant — *Migrate to a New Embedding Model* (official tutorial) + *Collections* docs | Vector-DB owner | No native collection-level free-form metadata → record model identity in **payload**; a model change shifts vector geometry ⇒ **re-embed & reindex**; migrate with **named vectors / aliases / dual-write**, treating an index as an atomic unit. |
| Zilliz — *How do I handle versioning of embedding models in production?* | Vector-DB vendor FAQ | Record **provider + model name + dimension**; assign **semantic versions** per model; **explicitly track which model generated each embedding**; full re-embed pipeline on upgrade. |
| TianPan — *Embedding Models in Production: Versioning & the Index Drift Problem* (2026) | Practitioner reference | "**Validate config-time model/provider compatibility rather than allowing errors to surface only at query time.**" Different models = incompatible spaces; mixing makes similarity meaningless. |
| Typer (official, fastapi/typer) + Click CLI patterns | Framework owner | Keep **business logic in pure Python functions/services testable without the CLI**; the CLI is the **interface layer** (flags/prompts/output) so logic is reusable by API/batch/lambda. Three layers: **core actions / adapters / interface**. |

**Convergent conclusion.** (A) Put a **stable embedding signature** (provider + model + dim +
revision) on the embedding contract; **persist it with the index** and **validate it before
querying** — fail fast, never silently. (B) Lift orchestration out of the CLI into pure
functions; the CLI (and `api/app`) become thin callers. Both align with the existing
`api/service.py` style.

## 4. Target design

### A. Embedding-version tag
- **Contract**: add a stable identity to `EmbeddingService` —
  `signature -> EmbeddingSignature{provider, model, dim, revision}` (revision bumped when
  preprocessing/normalization changes even if the model name does not). `BGEM3Embedder`
  returns `{"bge-m3", "BAAI/bge-m3", 1024, 1}`.
- **Persist (write side)**: at index time write a **manifest** holding the signature +
  `built_at`. Stored as a single **reserved Qdrant point** (fixed sentinel id) with payload
  `chunk_level="_manifest"`. It is **naturally excluded** from `profile`/`task` searches
  (which already filter on those levels), so it never pollutes results. New helpers in
  `store/manifest.py`: `write_manifest(client, collection, signature)` /
  `read_manifest(client, collection) -> EmbeddingSignature | None`.
- **Validate (read side)**: a single `assert_compatible(manifest, embedder.signature)` used by
  `api/service` query entry points and `cli query`; on mismatch raise a clear
  `EmbeddingMismatchError` (model/dim differs) **before** searching. Surface the manifest in
  `healthcheck`/`doctor`/`stats` (so ops sees the index's model).
- **Decision D-3c-1**: manifest as a reserved point (not per-point payload, not collection
  name). Rationale: single source of truth, O(1) to write/read/validate, no per-point bloat,
  no rename coupling — and Qdrant has no collection metadata. (Per-point `embedding_model` is
  the Qdrant-FAQ fallback but is redundant on every point; rejected for our single-embedder
  index.)

### B. Thin CLI
- **`embeddings/factory.py`**: `make_embedder(settings) -> EmbeddingService` — the one place
  that constructs `BGEM3Embedder` from settings (dedupes `index`/`query`/`api.app`).
- **`pipeline.py`**: `run_index(settings, scan_dir, *, limit=0) -> IndexReport` — the index
  orchestration moved verbatim out of `cli.index` (reader→normalize→build→embed→upsert,
  returns a dataclass report; writes the manifest at the end). `cli.index` becomes a thin
  wrapper that calls it and renders the rich table.
- **`cli query`**: delegate to `api/service.search_tasks/search_occupations` (or a shared
  search function), removing the duplicated embed-then-search; keep rich rendering in the CLI.
- **Decision D-3c-2**: presentation (rich tables/console) stays in `cli.py` (interface
  concern); all orchestration moves to `pipeline.py` / `api.service` / `embeddings.factory`.

## 5. Safety net & method

- **Net**: the pytest suite — **baseline 35 passed** (uses fakes; no live Qdrant/torch needed).
- **Method**:
  - Thread B (factory + pipeline extraction, CLI query delegation) is **move-only** — guarded
    by the existing suite (green-before == green-after), plus one new `run_index` fake-based
    unit test.
  - Thread A (signature + manifest + validation) is a **feature** → **TDD**: write failing
    tests first (signature value; manifest round-trip with a fake Qdrant client; `query`
    raises `EmbeddingMismatchError` on a mismatched manifest; passes when matched), then
    implement.
  - One commit per task; suite green before each commit.
- **Risk**: the manifest point leaking into search results — mitigated by the `_manifest`
  level filter + an explicit test asserting searches never return it. Stats double-count —
  exclude the manifest from counts (covered by a test).

## 6. Proposed task breakdown (detailed in the plan)

- **T1** — `embeddings/factory.py` `make_embedder`; rewire `index`/`query`/`api.app`. *(move-only)*
- **T2** — `pipeline.py` `run_index`; thin `cli.index`; `cli query` → `api.service`. *(move-only + 1 new test)*
- **T3** — `EmbeddingSignature` on the contract + `BGEM3Embedder.signature`; `store/manifest.py` write/read; `run_index` writes manifest. *(TDD)*
- **T4** — `assert_compatible` + `EmbeddingMismatchError`; wire into `api/service` query entry points, `cli query`, and `healthcheck`/`doctor`/`stats`. *(TDD)*
- **T5** — ADR `0009-embedding-version-manifest.md` + tag `phase3c-ocs-indexer`.

## 7. Out of scope
Live zero-downtime model migration (named-vectors/dual-write — documented as the future path
in the ADR, not built now); changing the embedding model itself; sparse-vector reindex
strategy; `apps/api`, `apps/web`, `apps/pdf-to-json`.
