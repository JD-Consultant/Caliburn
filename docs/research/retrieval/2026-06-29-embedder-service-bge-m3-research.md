# Research Record — Embedding as a Service (self-built BGE-M3 container, keep dense+sparse)

> Research record (權威資料 + 比對 + 設計). Authored 2026-06-29. Drives ADR
> `docs/adr/0012-embedding-as-a-service.md` + plan
> `docs/plans/2026-06-29-embedder-service.md`.

## 1. Goal

Move BGE-M3 embedding **out of the `ocs-indexer` process** into a dedicated **Linux GPU
container** (FastAPI + FlagEmbedding) behind an HTTP API; the indexer (index + serve) calls it
through the existing 3c `EmbeddingService` port. **Keep dense + sparse (hybrid)**. This
**root-fixes** the Windows torch instability instead of patching it.

## 2. Why (the problem, evidence-based)

Running FlagEmbedding/torch **in-process** in `ocs-indexer` on the **Windows host** is unstable
with the resolved-to-latest `torch 2.12.0+cu130`:
- **OMP segfault** reading BGE-M3 weights (worked around with `OMP_NUM_THREADS=1`).
- **`torch._dynamo` mega-cache double-registration** (`AssertionError: Artifact … already
  registered`) on the lazy import under the uvicorn `serve` runtime → every query 500s.
  Triggered by transformers (4.x `flex_attention` / 5.x `sonicmoe`) importing `torch._dynamo`;
  **version-independent** (torch 2.6 & 2.12, transformers 4.57 & 5.9, numpy 1.26 & 2.4 all
  reproduce; model file sha256-verified intact). `index` (CLI, clean import order) works; `serve`
  fails. See [[windows-openmp-bge-segfault]].

Root cause class: **torch-in-app-process on Windows is fragile**, and the fix isn't a version pin
— it's an architecture change (get torch out of the app, onto Linux).

## 3. Authoritative research & comparison

| Source | Authority | Finding |
|---|---|---|
| HF Text Embeddings Inference (TEI) | HF (model hub owner) | Production embedding server; **but BGE-M3 sparse NOT supported** ([TEI #289](https://github.com/huggingface/text-embeddings-inference/issues/289) — `/embed_sparse` needs a `ForMaskedLM` SPLADE model; BGE-M3 `lexical_weights` ≠ SPLADE). Dense-only. |
| Infinity (michaelfeil, 2.9k★; SAP/Runpod) | Popular OSS embedding server | OpenAI-compatible, GPU; **README explicitly "BAAI/bge-m3, no sparse"**. Dense-only. |
| NVIDIA Triton / TorchServe (Meta+AWS) | Big-company serving frameworks | The "authoritative" way to serve a **custom** model server (Python backend / custom handler). Heavier; run the model in its own service. |
| FastAPI + torch + `nvidia/cuda` Docker | Ubiquitous ML-serving pattern | The standard way to wrap a custom model when off-the-shelf servers don't fit. |
| [m3serve](https://github.com/MauroCE/m3serve) | Purpose-built precedent | BGE-M3 **dense+sparse+ColBERT**, "**identical vectors to FlagEmbedding**", +58% throughput — proves a self-built BGE-M3 hybrid container is sound. |
| Enterprise dep practice | Standard | **Pin** tested versions (don't auto-resolve bleeding-edge — torch 2.12 is the cautionary tale). |

**Convergent conclusion:** the mainstream/enterprise shape is **embedding-as-a-dedicated-service**
(not in-process). **No off-the-shelf server serves BGE-M3 sparse**, so to keep our **hybrid**
retrieval we **self-build a thin BGE-M3 container wrapping FlagEmbedding** (the standard custom-
model-container pattern; m3serve is precedent; TorchServe/Triton are heavier escalations).
Running it as a **Linux** container also removes the Windows-only torch bugs by construction.

**GPU-in-Docker verified on this machine:** `docker run --gpus all … nvidia-smi` →
`NVIDIA GeForce RTX 4060 Laptop GPU, driver 596.49, 8188 MiB`; Docker has the `nvidia` runtime
(Docker Desktop + WSL2). BGE-M3 (~1 GB fp16) fits 8 GB.

## 4. Design (fits the architecture)

- **New service `apps/embedder`** — a thin **FastAPI + FlagEmbedding** app + **Dockerfile**
  (`nvidia/cuda` base + Python + **pinned stable torch (Linux cu12x)** + flagembedding). One
  endpoint family:
  - `POST /embed` → `{dense: float[1024], sparse: {indices:int[], values:float[]}}[]` for a batch
    (and a query variant), reproducing exactly what `BGEM3Embedder` produces today
    (FlagEmbedding `encode(return_dense=True, return_sparse=True)` → our `SparseVector` mapping).
  - `GET /health`. The Windows OMP env-guard is irrelevant in Linux; standard torch.
- **`ocs-indexer` becomes torch-free**: new `adapters/http_embedder.py` implementing the 3c
  `EmbeddingService` (`embed_texts`/`embed_query`/`dense_size`/`supports_sparse`/`signature`) via
  `httpx` to the embedder service; `embeddings/factory.make_embedder` returns it. **Remove
  `torch`/`flagembedding`/`transformers` deps and the in-process `BGEM3Embedder`** from the
  indexer (drops the whole Windows-torch problem + slims the venv). The 3c manifest/signature is
  unchanged (`bge-m3/BAAI/bge-m3/1024`), so existing `ocs_v4` stays valid; re-index for cleanliness.
- **Compose / one-click**: add `embedder` service (`gpus: all`, model-cache volume, `/health`
  healthcheck) to `docker-compose.yml`; `npm run up` brings db + qdrant + **embedder** + app
  servers. The `ocs-indexer dev` (serve) no longer loads torch.
- **env**: `EMBEDDER_URL=http://localhost:<port>` for the indexer.

**Architecture fit:** ADR 0003 (indexer is a separate service) → embedding is a further sub-service
of the knowledge context; 3c `EmbeddingService` **port** absorbs the change as a new adapter
(hexagonal payoff); the indexer↔embedder HTTP shape is a candidate **contract #4** later
(`docs/contract-strategy.md`); one-click via compose (Vercel/Docker dev pattern).

## 5. Safety net & method
- **Net:** indexer suite (41) — the new HTTP adapter is unit-testable with a fake transport;
  keep `assert A is B`-style + golden where relevant. **Vector-parity check is the gate**: before
  re-indexing, assert the container's dense+sparse for sample texts **equals** the current
  FlagEmbedding output (same lib → identical), so retrieval quality is preserved.
- **Method:** (1) build `apps/embedder` image; (2) `docker compose up embedder`, verify
  `/embed` dense+sparse parity vs FlagEmbedding; (3) write `http_embedder` adapter + factory wire;
  (4) drop torch/flagembedding from indexer, remove `BGEM3Embedder`; (5) re-index `ocs_v4` via the
  service; (6) end-to-end query (api→indexer→embedder + qdrant) green; (7) ADR + tag.
- **Risk:** sparse-format drift between container and old index → mitigated by re-indexing via the
  service (index + query both go through it) + the parity check. Pin the container's torch to a
  stable Linux build to avoid repeating the 2.12 saga.

## 6. Out of scope
TorchServe/Triton/m3serve adoption (documented alternatives); production GPU autoscaling / multi-
replica; making indexer↔embedder a formal codegen'd contract (note as future contract #4).
