# embedder

BGE-M3 embedding service (dense + sparse) — a thin FastAPI wrapper around FlagEmbedding,
run as its own **Linux GPU container** so torch lives outside the app processes (ADR 0012).
`ocs-indexer` (index + query) calls it over HTTP via the 3c `EmbeddingService` port.

- `POST /embed` `{texts: string[]}` → `{embeddings: [{dense: float[1024], sparse: {indices, values}}]}`
- `GET /health` → `{status, model, dim, device}`

Runs only as a container (GPU). Built + started by `docker compose` (service `embedder`,
`gpus: all`, port 8082→80). Produces the same vectors as the former in-process embedder.
See `docs/specs/2026-06-29-embedder-service-bge-m3-research.md`.
