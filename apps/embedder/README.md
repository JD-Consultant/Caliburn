# embedder

BGE-M3 embedding and BGE-reranker-v2-m3 scoring service for the independent RAG pipeline.
It is a thin FastAPI wrapper around FlagEmbedding, run as its own **Linux GPU container**
so torch stays outside the app processes.
`ocs-indexer` calls it over HTTP: index and query use the 3c `EmbeddingService` port,
and the occupation-reference API also uses reranking.

- `POST /embed` `{texts: string[]}` → `{embeddings: [{dense: float[1024], sparse: {indices, values}}], model, model_revision, dim, revision}`
- `POST /rerank` `{query, documents: string[]}` → `{scores: float[], model, revision}`
- `GET /health` → model identity, device and reranker load status.

Runs only as a container (GPU). Built and started by `docker compose` (service `embedder`,
`gpus: all`, port 8082→80). Embedding produces the same vectors as the former in-process embedder.
See embedding research.

The independent occupation-reference API uses BGE-M3 weights
`5617a9f61b028005a4858fdac845db406aefb181` and BGE-reranker-v2-m3 weights
`953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`. The HTTP adapters reject mismatched
identity, response counts and non-finite values. Rebuild the service together with
the updated adapters; older services do not return the required identity metadata.

Reranking is a cross-encoder score for each query/document pair, not a vector of
another dimension. Requests allow at most 32 documents and a nonblank query of at
most 12,000 characters. Long documents are scored over all token windows, with
64-token overlap and the maximum logit returned. Query length also must leave room
within the 8,192-token pair capacity; oversized queries return 422 without silent
truncation. Scores are ranking values, not suitability probabilities.

Both models share the GPU lock. Lifespan releases loaded models on shutdown and
failed startup. Set `RERANKER_ENABLED=false` for an embedding-only service; rerank
then returns 503. No paid model API is required. Pure window and request tests run
without torch: `uv run --project apps/ocs-indexer --extra api pytest apps/embedder/tests -q`.

Boundary and implementation evidence: [公版參考 API](../ocs-indexer/README.md).
