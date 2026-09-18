# Embedder Service (self-built BGE-M3 container) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Checkbox steps.
> Implements ADR 0012 / research record `docs/specs/2026-06-29-embedder-service-bge-m3-research.md`.

**Goal:** BGE-M3 dense+sparse runs in a dedicated Linux GPU container (`apps/embedder`,
FastAPI+FlagEmbedding); `ocs-indexer` becomes torch-free and calls it over HTTP via the 3c
`EmbeddingService` port. Root-fixes the Windows torch instability; keeps hybrid retrieval.

## Global Constraints
- **Vector parity is the gate:** the container's dense+sparse for sample texts must equal current
  FlagEmbedding output (same lib) before re-indexing.
- **Safety net:** `ocs-indexer` suite (41) stays green; new HTTP adapter unit-tested with a fake transport.
- GPU verified (RTX 4060, `nvidia` runtime). Pin a **stable Linux torch** in the container (no 2.12).
- Commit per task; from `/s/caliburn` (bash: `cd /s/caliburn`).

---

## Task 1: `apps/embedder` — BGE-M3 FastAPI service + image
**Files:** `apps/embedder/Dockerfile`, `apps/embedder/app.py`, `apps/embedder/requirements.txt`, `apps/embedder/README.md`; modify `docker-compose.yml` (+`embedder` service).

- [ ] **Step 1:** `requirements.txt` — pinned: `fastapi`, `uvicorn[standard]`, `FlagEmbedding==1.4.0`, `torch==2.6.0` (Linux cu124 via `--index-url` in Dockerfile), `transformers>=4.44,<5`.
- [ ] **Step 2:** `app.py` — FastAPI: load `BGEM3FlagModel('BAAI/bge-m3', use_fp16=True, devices='cuda')` once at startup; `POST /embed {texts: string[]}` → `{embeddings: [{dense: float[1024], sparse: {indices: int[], values: float[]}}]}` using `encode(return_dense=True, return_sparse=True)` + the same lexical_weights→indices/values mapping as `bge_m3.py::_sparse_from_lexical_weights`; `GET /health` → `{status, model, dim}`.
- [ ] **Step 3:** `Dockerfile` — `FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04`; install python3.11 + pip; `pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cu124`; `pip install -r requirements.txt`; copy `app.py`; `CMD uvicorn app:app --host 0.0.0.0 --port 80`.
- [ ] **Step 4:** compose `embedder` service: `build: ./apps/embedder`, `gpus: all`, `ports: ["8082:80"]`, volume `hf_cache:/root/.cache/huggingface` (avoid re-download), healthcheck `CMD curl -f http://localhost:80/health` (cuda image has curl) interval/retries, `restart: unless-stopped`. Add `hf_cache` volume.
- [ ] **Step 5:** build + run: `docker compose -p caliburn -f S:/caliburn/docker-compose.yml up -d --build embedder`; wait `/health` ok.
- [ ] **Step 6 (PARITY GATE):** compare container `/embed` vs in-process FlagEmbedding for 2 sample texts — dense cosine ≈ 1.0 and sparse indices/values match. Must pass before proceeding.
- [ ] **Step 7:** Commit.

## Task 2: `ocs-indexer` HTTP embedder adapter (3c port)
**Files:** `apps/ocs-indexer/src/jd_ocs_indexer/adapters/http_embedder.py`, modify `embeddings/factory.py`; `tests/test_http_embedder.py`.

- [ ] **Step 1:** `HttpEmbedder` implements `EmbeddingService`: `provider="bge-m3"`, `dense_size=1024`, `supports_sparse=True`, `signature` = `EmbeddingSignature("bge-m3","BAAI/bge-m3",1024,1)`; `embed_texts(texts)` POSTs `EMBEDDER_URL/embed`, maps JSON → `list[EmbeddedVector]` (`SparseVector`); `embed_query(t)=embed_texts([t])[0]`.
- [ ] **Step 2:** `factory.make_embedder(settings)` → `HttpEmbedder(settings.embedder_url)`; add `embedder_url` to indexer `config.py` (default `http://localhost:8082`).
- [ ] **Step 3:** unit test with a fake httpx transport (respx) → adapter maps dense+sparse correctly.
- [ ] **Step 4:** `uv run --all-extras pytest -q` → 41 + new test green.
- [ ] **Step 5:** Commit.

## Task 3: drop torch from `ocs-indexer`
**Files:** modify `apps/ocs-indexer/pyproject.toml`, `src/jd_ocs_indexer/__init__.py`, `api/app.py`; remove `embeddings/bge_m3.py`.

- [ ] **Step 1:** remove `torch`, `flagembedding`, `transformers`, the `[tool.uv.index] pytorch-cu130` + `[tool.uv.sources] torch` from pyproject. Remove `bge_m3.py`. Remove the Windows OMP guard in `__init__.py` and the serve warmup in `api/app.py` (no longer needed — no torch in-process). Keep `EmbeddingSignature`/`assert_compatible`/manifest (still used).
- [ ] **Step 2:** `uv sync --all-extras` (now light — no torch); grep no residual `bge_m3`/`FlagEmbedding`/`torch` imports in indexer src.
- [ ] **Step 3:** `uv run --all-extras pytest -q` → green (41). Import smoke `python -c "import jd_ocs_indexer.cli, jd_ocs_indexer.api.app"`.
- [ ] **Step 4:** Commit.

## Task 4: re-index + end-to-end verify
- [ ] **Step 1:** ensure embedder + qdrant up (`npm run infra` builds/starts; embedder healthy).
- [ ] **Step 2:** re-index: `cd apps/ocs-indexer && uv run jd-ocs-indexer index ./data/jd-json` (now calls the service; no torch locally). Expect ~9449 pts.
- [ ] **Step 3:** verify `stats --collection ocs_v4` (count + `index_model`); `query "3D列印 設備 維護" --level task` returns relevant hits (hybrid).
- [ ] **Step 4:** restart `turbo dev`; api→indexer→embedder smoke: `POST /api/v1/job-profiles/{id}/occupations {ocs_codes:[...]}` after an `ocs-search` returns hits (no 500).
- [ ] **Step 5:** Commit (if any fixups).

## Task 5: docs + one-click + tag
- [ ] **Step 1:** update `docker-compose.yml` already has embedder; ensure `npm run up` brings it (compose up -d builds/starts embedder + turbo dev runs api/web/indexer — indexer no longer needs torch). Note: `apps/ocs-indexer dev` (serve) now starts instantly (no model load).
- [ ] **Step 2:** CONTRIBUTING: note embedder service (built image, GPU) + first-time `--build`.
- [ ] **Step 3:** ADR 0012 (done) + tag `embedder-service`.

## Self-Review
- 3c port makes the swap a pure adapter change; manifest signature unchanged → `ocs_v4` valid.
- Parity gate (T1 S6) guarantees retrieval quality preserved before reindex.
- Indexer loses torch entirely → Windows OMP/dynamo bugs gone by construction.
