# Search Reranker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `bge-reranker-v2-m3` cross-encoder rerank stage to `jd-ocs-indexer`'s `POST /search`: hybrid/dense retrieves top-N candidates, the reranker reorders them by `(query, chunk.text)` relevance, and the API returns the top-k with reranker scores.

**Architecture:** A new `BGEReranker` adapter (lazy-loads `FlagReranker`, mirrors the existing `BGEM3Embedder`) is loaded once into `app.state.reranker`. `service.search` gains an optional rerank step: when enabled, it fetches `rerank_candidates` (default 50) instead of `top_k`, scores each candidate's `payload.text` against the query, sorts by score, takes `top_k`, and overwrites each hit's `score` with the reranker score (cross-encoder scores are thresholdable, unlike RRF). The API defaults `rerank=true` at the schema boundary; `service.search` itself defaults `rerank=False` so existing direct-call tests are unaffected. Tests use a `StubReranker` — the 2GB model never loads in CI.

**Tech Stack:** Python 3.11, FlagEmbedding `FlagReranker`, FastAPI, pytest, uv. Builds directly on the query API ([2026-06-13-query-api.md](2026-06-13-query-api.md)).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/jd_ocs_indexer/config.py` | add `rerank_model` + `rerank_candidates` settings | Modify |
| `src/jd_ocs_indexer/embeddings/reranker.py` | `BGEReranker` cross-encoder adapter (lazy) | Create |
| `src/jd_ocs_indexer/api/schemas.py` | `SearchRequest.rerank` field (default true) | Modify |
| `src/jd_ocs_indexer/api/service.py` | rerank step in `search()` | Modify |
| `src/jd_ocs_indexer/api/app.py` | `create_app` reranker param + lazy-load into `app.state` | Modify |
| `src/jd_ocs_indexer/api/routes.py` | thread `reranker`/`rerank`/`rerank_candidates` into `service.search` | Modify |
| `tests/conftest.py` | `StubReranker` + `stub_reranker` fixture + `make_app` injects it | Modify |
| `tests/test_reranker.py` | `BGEReranker` adapter tests | Create |
| `tests/test_service_rerank.py` | `service.search` rerank tests | Create |
| `tests/test_routes.py` | rerank route tests | Modify |
| `.env.example`, `README.md` | document rerank settings + behavior | Modify |

**Run tests with:** `uv run pytest` (Windows / PowerShell; 1 `StarletteDeprecationWarning` is expected).

---

## Task 1: Config settings for the reranker

**Files:**
- Modify: `src/jd_ocs_indexer/config.py`
- Test: `tests/test_config_rerank.py`

- [ ] **Step 1: Write the failing test**

```python
from jd_ocs_indexer.config import load_settings


def test_rerank_settings_defaults():
    s = load_settings()
    assert s.rerank_model == "BAAI/bge-reranker-v2-m3"
    assert s.rerank_candidates == 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config_rerank.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'rerank_model'`.

- [ ] **Step 3: Add the two fields to the `Settings` dataclass**

In `src/jd_ocs_indexer/config.py`, add `rerank_model` and `rerank_candidates` immediately after `manifest_path` and before `extra` (non-default fields must precede the default `extra` field):

```python
    index_batch_size: int
    manifest_path: Path

    rerank_model: str
    rerank_candidates: int

    extra: dict[str, str] = field(default_factory=dict)
```

- [ ] **Step 4: Populate them in `load_settings()`**

In `load_settings()`, add these two lines just before the closing `)` of the `Settings(...)` constructor (after the `manifest_path=manifest_path,` line):

```python
        manifest_path=manifest_path,
        rerank_model=_env("RERANK_MODEL", "BAAI/bge-reranker-v2-m3") or "BAAI/bge-reranker-v2-m3",
        rerank_candidates=_env_int("RERANK_CANDIDATES", 50),
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_config_rerank.py -v`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add src/jd_ocs_indexer/config.py tests/test_config_rerank.py
git commit -m "feat(config): add rerank_model + rerank_candidates settings"
```

---

## Task 2: BGEReranker adapter

**Files:**
- Create: `src/jd_ocs_indexer/embeddings/reranker.py`
- Test: `tests/test_reranker.py`

- [ ] **Step 1: Write the failing test**

```python
from jd_ocs_indexer.embeddings.reranker import BGEReranker


def test_reranker_lazy_no_model_on_init():
    r = BGEReranker()
    assert r._model is None  # model not loaded until first rerank


def test_reranker_empty_passages_returns_empty():
    assert BGEReranker().rerank("q", []) == []


def test_reranker_normalizes_scalar_and_list(monkeypatch):
    r = BGEReranker()

    class FakeModel:
        def compute_score(self, pairs, **kw):
            # FlagReranker returns a scalar for a single pair, a list for many
            return 0.9 if len(pairs) == 1 else [0.1 * i for i in range(len(pairs))]

    monkeypatch.setattr(r, "_ensure_model", lambda: FakeModel())
    assert r.rerank("q", ["one"]) == [0.9]
    assert r.rerank("q", ["a", "b", "c"]) == [0.0, 0.1, 0.2]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_reranker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'jd_ocs_indexer.embeddings.reranker'`.

- [ ] **Step 3: Create `src/jd_ocs_indexer/embeddings/reranker.py`**

```python
"""BGE cross-encoder reranker adapter.

Reorders retrieved candidates by (query, passage) relevance via FlagEmbedding's
`FlagReranker`. Loaded lazily so importing this module doesn't drag in torch
unless we actually rerank. `normalize=True` gives [0,1] scores that are usable
as absolute thresholds (unlike RRF fusion ranks).
"""

from __future__ import annotations

from typing import Any


class BGEReranker:
    provider = "bge-reranker"

    def __init__(
        self,
        *,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        device: str = "cpu",
        use_fp16: bool = False,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.use_fp16 = use_fp16
        self._model: Any | None = None

    def _ensure_model(self) -> Any:
        if self._model is None:
            from FlagEmbedding import FlagReranker  # heavy import

            self._model = FlagReranker(
                self.model_name,
                use_fp16=self.use_fp16,
                devices=self.device,
                normalize=True,
            )
        return self._model

    def rerank(self, query: str, passages: list[str]) -> list[float]:
        """Return one relevance score per passage, aligned to input order."""
        if not passages:
            return []
        model = self._ensure_model()
        raw = model.compute_score([(query, p) for p in passages])
        # compute_score returns a scalar for a single pair, a list for many.
        if isinstance(raw, (int, float)):
            return [float(raw)]
        return [float(s) for s in raw]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_reranker.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/jd_ocs_indexer/embeddings/reranker.py tests/test_reranker.py
git commit -m "feat(embeddings): BGEReranker cross-encoder adapter (lazy)"
```

---

## Task 3: SearchRequest.rerank field

**Files:**
- Modify: `src/jd_ocs_indexer/api/schemas.py`
- Test: `tests/test_schemas_rerank.py`

- [ ] **Step 1: Write the failing test**

```python
from jd_ocs_indexer.api.schemas import SearchRequest


def test_search_request_rerank_default_true():
    assert SearchRequest(query="hi").rerank is True


def test_search_request_rerank_can_disable():
    assert SearchRequest(query="hi", rerank=False).rerank is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_schemas_rerank.py -v`
Expected: FAIL — `SearchRequest(query="hi").rerank` raises `AttributeError` (field doesn't exist).

- [ ] **Step 3: Add the `rerank` field to `SearchRequest`**

In `src/jd_ocs_indexer/api/schemas.py`, add the `rerank` field to `SearchRequest` immediately after the `hybrid` field:

```python
class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    level: Optional[Literal["profile", "unit", "block"]] = None
    hybrid: bool = True
    rerank: bool = True
    top_k: int = Field(10, ge=1, le=50)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    include_text: bool = False
    text_lines: int = Field(6, ge=0, le=50)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_schemas_rerank.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/jd_ocs_indexer/api/schemas.py tests/test_schemas_rerank.py
git commit -m "feat(api): SearchRequest.rerank field (default true)"
```

---

## Task 4: service.search rerank step

**Files:**
- Modify: `src/jd_ocs_indexer/api/service.py`
- Modify: `tests/conftest.py` (add `StubReranker` + `stub_reranker` fixture)
- Test: `tests/test_service_rerank.py`

- [ ] **Step 1: Add `StubReranker` + fixture to `tests/conftest.py`**

Add the `StubReranker` class after the `StubEmbedder` class (after its `embed_texts` method):

```python
class StubReranker:
    """Deterministic reranker for tests: longer passage = higher score."""

    def rerank(self, query: str, passages: list[str]) -> list[float]:
        return [float(len(p)) for p in passages]
```

Add the fixture after the `stub_embedder` fixture:

```python
@pytest.fixture
def stub_reranker():
    return StubReranker()
```

- [ ] **Step 2: Write the failing test**

```python
from jd_ocs_indexer.api import service


def _pts(fake_point):
    # retrieval order = [short "a", long "b"]; rerank-by-length should reorder to [b, a]
    return [
        fake_point(
            payload={"chunk_key": "a", "chunk_level": "block", "ocs_code": "OC",
                     "job_title": "J", "text": "short"},
            score=0.9,
        ),
        fake_point(
            payload={"chunk_key": "b", "chunk_level": "block", "ocs_code": "OC",
                     "job_title": "J", "text": "a much longer passage"},
            score=0.1,
        ),
    ]


def test_rerank_reorders_and_sets_score(make_qdrant, fake_point, stub_embedder, stub_reranker):
    fake = make_qdrant(query_points=_pts(fake_point))
    out = service.search(fake, stub_embedder, "coll", query="q", hybrid=False,
                         top_k=2, reranker=stub_reranker, rerank=True)
    assert [h["chunk_key"] for h in out["hits"]] == ["b", "a"]
    assert out["hits"][0]["score"] == float(len("a much longer passage"))


def test_rerank_false_keeps_retrieval_order(make_qdrant, fake_point, stub_embedder, stub_reranker):
    fake = make_qdrant(query_points=_pts(fake_point))
    out = service.search(fake, stub_embedder, "coll", query="q", hybrid=False,
                         top_k=2, reranker=stub_reranker, rerank=False)
    assert [h["chunk_key"] for h in out["hits"]] == ["a", "b"]


def test_rerank_no_reranker_skips(make_qdrant, fake_point, stub_embedder):
    fake = make_qdrant(query_points=_pts(fake_point))
    out = service.search(fake, stub_embedder, "coll", query="q", hybrid=False,
                         top_k=2, reranker=None, rerank=True)
    assert [h["chunk_key"] for h in out["hits"]] == ["a", "b"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_service_rerank.py -v`
Expected: FAIL — `service.search()` got an unexpected keyword argument `reranker`.

- [ ] **Step 4: Add rerank params + step to `service.search`**

Replace the `search` function in `src/jd_ocs_indexer/api/service.py` with this version (adds `reranker` / `rerank` / `rerank_candidates` params + the rerank step; everything else unchanged):

```python
def search(
    client,
    embedder,
    collection: str,
    *,
    query: str,
    level: str | None = None,
    hybrid: bool = True,
    top_k: int = 10,
    filters: dict | None = None,
    include_text: bool = False,
    text_lines: int = 6,
    reranker=None,
    rerank: bool = False,
    rerank_candidates: int = 50,
) -> dict:
    filters = filters or {}
    vec = embedder.embed_query(query)
    use_rerank = rerank and reranker is not None
    fetch_limit = rerank_candidates if use_rerank else top_k
    kw = dict(
        level=level,
        ocs_code=filters.get("ocs_code"),
        is_current=filters.get("is_current"),
        k_codes=filters.get("k_codes"),
        s_codes=filters.get("s_codes"),
        attitude_codes=filters.get("attitude_codes"),
        limit=fetch_limit,
    )
    if hybrid:
        hits = search_mod.hybrid_search(
            client, collection, vec.dense,
            vec.sparse.indices if vec.sparse else [],
            vec.sparse.values if vec.sparse else [],
            **kw,
        )
        mode = "hybrid"
    else:
        hits = search_mod.dense_search(client, collection, vec.dense, **kw)
        mode = "dense"

    if use_rerank and len(hits) > 1:
        passages = [(h.payload or {}).get("text", "") for h in hits]
        scores = reranker.rerank(query, passages)
        ranked = sorted(zip(hits, scores), key=lambda pair: pair[1], reverse=True)[:top_k]
        for hit, score in ranked:
            hit.score = score  # cross-encoder score is thresholdable (unlike RRF)
        hits = [hit for hit, _ in ranked]
    else:
        hits = hits[:top_k]

    return {
        "mode": mode,
        "level": level,
        "hits": [_project_hit(h, include_text=include_text, text_lines=text_lines) for h in hits],
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_service_rerank.py tests/test_service_search.py -v`
Expected: PASS (3 new + 3 existing = 6 passed; the existing `test_service_search` tests still pass because `rerank` defaults to `False` in `service.search`).

- [ ] **Step 6: Commit**

```bash
git add src/jd_ocs_indexer/api/service.py tests/conftest.py tests/test_service_rerank.py
git commit -m "feat(api): rerank step in service.search (cross-encoder reorder)"
```

---

## Task 5: Wire reranker through app + routes

**Files:**
- Modify: `src/jd_ocs_indexer/api/app.py`
- Modify: `src/jd_ocs_indexer/api/routes.py`
- Modify: `tests/conftest.py` (`make_app` injects `stub_reranker`)
- Test: `tests/test_routes.py`

- [ ] **Step 1: Update `make_app` in `tests/conftest.py` to inject the stub reranker**

Replace the `make_app` fixture with:

```python
@pytest.fixture
def make_app(stub_embedder, stub_reranker):
    from jd_ocs_indexer.api.app import create_app
    from jd_ocs_indexer.config import load_settings

    def _make(client):
        return create_app(
            settings=load_settings(),
            embedder=stub_embedder,
            reranker=stub_reranker,
            client=client,
        )
    return _make
```

- [ ] **Step 2: Write the failing route tests**

Append to `tests/test_routes.py`:

```python
def _rerank_pts(fake_point):
    return [
        fake_point(payload={"chunk_key": "a", "chunk_level": "block", "ocs_code": "OC",
                            "job_title": "J", "text": "short"}, score=0.9),
        fake_point(payload={"chunk_key": "b", "chunk_level": "block", "ocs_code": "OC",
                            "job_title": "J", "text": "a much longer passage"}, score=0.1),
    ]


def test_search_route_reranks_by_default(make_app, make_qdrant, fake_point):
    fake = make_qdrant(query_points=_rerank_pts(fake_point))
    with TestClient(make_app(fake)) as c:
        r = c.post("/search", json={"query": "q", "hybrid": False})
        assert r.status_code == 200
        assert [h["chunk_key"] for h in r.json()["hits"]] == ["b", "a"]


def test_search_route_rerank_false(make_app, make_qdrant, fake_point):
    fake = make_qdrant(query_points=_rerank_pts(fake_point))
    with TestClient(make_app(fake)) as c:
        r = c.post("/search", json={"query": "q", "hybrid": False, "rerank": False})
        assert r.status_code == 200
        assert [h["chunk_key"] for h in r.json()["hits"]] == ["a", "b"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_routes.py::test_search_route_reranks_by_default -v`
Expected: FAIL — `create_app()` got an unexpected keyword argument `reranker` (or AttributeError on `app.state.reranker`).

- [ ] **Step 4: Add the `reranker` param + lazy-load to `create_app`**

In `src/jd_ocs_indexer/api/app.py`, change the `create_app` signature to add `reranker=None`:

```python
def create_app(*, settings: Settings | None = None, embedder=None, client=None, reranker=None) -> FastAPI:
```

Then, inside `lifespan`, add the reranker block immediately after the embedder block (after `app.state.embedder` is set, before the `if client is not None:` block):

```python
        if reranker is not None:
            app.state.reranker = reranker
        else:
            from jd_ocs_indexer.embeddings.reranker import BGEReranker

            app.state.reranker = BGEReranker(
                model_name=s.rerank_model,
                device=s.bge_m3_device,
                use_fp16=s.bge_m3_use_fp16,
            )
```

- [ ] **Step 5: Thread rerank args into `service.search` in `routes.py`**

In `src/jd_ocs_indexer/api/routes.py`, update the `_run` closure inside `post_search` to pass the reranker args:

```python
    def _run():
        with app.state.embed_lock:
            return service.search(
                app.state.client,
                app.state.embedder,
                app.state.settings.qdrant_collection,
                query=req.query,
                level=req.level,
                hybrid=req.hybrid,
                top_k=req.top_k,
                filters=req.filters.model_dump(),
                include_text=req.include_text,
                text_lines=req.text_lines,
                reranker=app.state.reranker,
                rerank=req.rerank,
                rerank_candidates=app.state.settings.rerank_candidates,
            )
```

> The existing `embed_lock` already wraps the whole `service.search` call, so it also serializes the (non-thread-safe) reranker — no new lock needed.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_routes.py -v`
Expected: PASS (all route tests, including the 2 new rerank tests; the existing `test_search_route_ok` still passes because its single-hit response skips reranking — `len(hits) > 1` is false).

- [ ] **Step 7: Commit**

```bash
git add src/jd_ocs_indexer/api/app.py src/jd_ocs_indexer/api/routes.py tests/conftest.py tests/test_routes.py
git commit -m "feat(api): wire reranker through app.state + /search route"
```

---

## Task 6: Docs + full green

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Document the rerank settings in `.env.example`**

Append to the Query API section of `.env.example`:

```bash

# Reranker (cross-encoder rerank on /search; rerank=true by default per request)
RERANK_MODEL=BAAI/bge-reranker-v2-m3
RERANK_CANDIDATES=50          # how many hybrid/dense candidates to rerank down to top_k
```

- [ ] **Step 2: Add a rerank note to the `POST /search` docs in `README.md`**

In the `POST /search` request-body table in `README.md`, add a `rerank` row immediately after the `hybrid` row:

```markdown
| `rerank` | bool | `true` | 取回後用 bge-reranker-v2-m3 cross-encoder 重排；分數改為 reranker 相關度（可閾值化） |
```

- [ ] **Step 3: Run the full suite**

Run: `uv run pytest -q`
Expected: all tests pass (the prior 29 + the new reranker tests: config 1, reranker 3, schemas_rerank 2, service_rerank 3, routes 2 = 11 new → 40 passed), 1 `StarletteDeprecationWarning`.

- [ ] **Step 4: Commit**

```bash
git add .env.example README.md
git commit -m "docs: document /search reranker settings + behavior"
```

---

## Manual smoke test (optional — needs live Qdrant + both models)

Not in CI (loads BGE-M3 + bge-reranker-v2-m3). Run once to confirm end-to-end:

```bash
jd-ocs-indexer serve &       # wait for "Application startup complete"
# reranked (default) vs not — compare ordering + scores
curl -s localhost:8000/search -H 'content-type: application/json' \
  -d '{"query":"資料分析 Python SQL","level":"profile","top_k":5}'
curl -s localhost:8000/search -H 'content-type: application/json' \
  -d '{"query":"資料分析 Python SQL","level":"profile","top_k":5,"rerank":false}'
```

Expected: first call's hits are reranker-ordered with `score` in ~[0,1] (cross-encoder); second call keeps RRF order/scores. First request after boot is slower (lazy-loads the reranker once).

---

## Notes for the implementer

- **YAGNI:** only `/search` reranks (scroll endpoints don't rank). Passage = full `payload.text`, truncated by the cross-encoder's 512-token limit — do NOT build per-level curated passages yet (revisit only if rerank quality proves insufficient).
- **Default split:** `SearchRequest.rerank` defaults `True` (product default — quality); `service.search`'s own `rerank` param defaults `False` so existing direct-call service tests are unaffected.
- **Single-hit skip:** rerank only runs when `len(hits) > 1` (reranking one item is pointless and would needlessly mutate its score).
- **Score semantics:** when reranking, `hit.score` becomes the reranker's normalized [0,1] score (thresholdable — this is what the downstream confidence gateway should threshold on).
- **No Co-Authored-By trailer** on commits (repo convention).
```
