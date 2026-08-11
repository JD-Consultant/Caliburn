# Schema v3 Phase 2 — Query API → v3

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Rework the query layer (`/search`, `/task-pool`, `/pairs`, `/stats`, cli `query`) to read **v3 profile + task points** instead of v2 profile/unit/block, and retire the v2-shaped remnants.

**Architecture:** v3 has only profile + task points (Phase 1). So: `/search` searches profile+task (no OCS-local code filters — v3 doesn't index them); `/task-pool` scrolls **task** points and groups by unit (one task point = one task — no block reconstruction); `/pairs` aggregates K/S/output from **task** points + attitudes from the profile; `stats` counts profile/task. Each task hit/menu-entry carries the Qdrant **point id** so the consumer can by-id retrieve later (decision-log F4, option 1). Decisions: [v3-decision-log.md](../specs/2026-06-14-v3-decision-log.md) §F.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, Qdrant, pytest, uv. Run tests: `uv run pytest`.

**Validated against:** live `ocs_v3` collection (5 acceptance OCS = 5 profile + 50 task points) from Phase 1.

---

## Key contract changes (decision-log §F)

| Area | v2 | v3 |
|---|---|---|
| `/search` level | `profile\|unit\|block` | `profile\|task` |
| `/search` filters | ocs_code, is_current, **k_codes, s_codes, attitude_codes** | ocs_code, is_current (codes **removed** — not indexed in v3) |
| `Hit` | task_ids/task_titles (plural), block_order, unit_order, snippet | **id**, task_id/task_title (singular), activity_examples, output_pairs, competency_level (drop plurals/block_order/unit_order/snippet) |
| `/task-pool` source | scroll `block` points, reconstruct | scroll `task` points, group by `unit_id`; each task carries **id** |
| `/task-pool` ordering | unit_order / task_id | unit by `unit_id`, task by `task_id` (v3 dropped order fields) |
| `/pairs` K/S/output | profile `all_k_pairs`/`all_s_pairs`/`all_output_pairs` | **union of task points'** k/s/output (dedup by code) |
| `/pairs` attitudes | profile `all_a_pairs` | profile `all_a_pairs` (unchanged) |
| `stats` by_level | profile/unit/block | profile/task |
| removed | — | `smoke_query.filter_by_ks_code`, `_project_hit` text snippet |

---

## File Structure

| File | Change |
|---|---|
| `tests/conftest.py` | `FakePoint` gains `id` field (for point-id exposure) |
| `src/jd_ocs_indexer/validation/search.py` | `build_filter`/`dense_search`/`hybrid_search` drop k/s/attitude code params |
| `src/jd_ocs_indexer/validation/smoke_query.py` | `Hit`/`_to_hit` use `id` (drop `chunk_key`); remove `filter_by_ks_code` |
| `src/jd_ocs_indexer/validation/stats.py` | `collection_stats` counts profile/task |
| `src/jd_ocs_indexer/api/schemas.py` | v3 `SearchFilters`/`SearchRequest`/`Hit`/`Task`/`Unit` |
| `src/jd_ocs_indexer/api/service.py` | `_project_hit`, `search`, `build_task_pool`, `get_pairs` → v3 |
| `src/jd_ocs_indexer/cli.py` | `query` + `_print_query_hit` → v3 display, `--level profile/task` |
| `tests/test_*` (query API) | rewrite fixtures/asserts to v3 payloads |

---

## Task 1: conftest `FakePoint.id`

**Files:** Modify `tests/conftest.py`; Test: `tests/test_conftest_fakepoint.py`

- [ ] **Step 1: Failing test** — `tests/test_conftest_fakepoint.py`:
```python
from tests.conftest import FakePoint


def test_fakepoint_carries_id():
    p = FakePoint(payload={"chunk_level": "task"}, score=0.5, id="abc-123")
    assert p.id == "abc-123"
    assert FakePoint(payload={}).id is None
```

- [ ] **Step 2: Run** — `uv run pytest tests/test_conftest_fakepoint.py -v` → FAIL (`id` not a field).

- [ ] **Step 3: Add the field** — in `tests/conftest.py`, change:
```python
@dataclass
class FakePoint:
    payload: dict
    score: float | None = None
```
to:
```python
@dataclass
class FakePoint:
    payload: dict
    score: float | None = None
    id: str | None = None
```
Also extend the `fake_point` fixture factory to accept `id`:
```python
@pytest.fixture
def fake_point():
    def _make(*, payload: dict, score: float | None = None, id: str | None = None):
        return FakePoint(payload=payload, score=score, id=id)
    return _make
```

- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "test(api): FakePoint carries point id for v3"`

---

## Task 2: `search.py` — drop OCS-local code filters

**Files:** Modify `src/jd_ocs_indexer/validation/search.py`; Test: `tests/test_search_filter.py` (rewrite)

- [ ] **Step 1: Failing test** — replace `tests/test_search_filter.py` with:
```python
from jd_ocs_indexer.validation.search import build_filter


def _keys(flt):
    return [c.key for c in flt.must]


def test_build_filter_v3_supported_fields():
    flt = build_filter(level="task", ocs_code="OC1", is_current=True)
    assert _keys(flt) == ["chunk_level", "ocs_code", "is_current"]


def test_build_filter_empty_is_none():
    assert build_filter() is None


def test_build_filter_rejects_code_kwargs():
    # k_codes/s_codes/attitude_codes are gone in v3 — passing them must error
    import pytest
    with pytest.raises(TypeError):
        build_filter(k_codes=["K01"])
```

- [ ] **Step 2: Run** → FAIL (current `build_filter` still accepts `k_codes`).

- [ ] **Step 3: Edit `search.py`** — replace `build_filter` with:
```python
def build_filter(
    *,
    level: str | None = None,
    ocs_code: str | None = None,
    is_current: bool | None = None,
) -> models.Filter | None:
    musts: list[models.Condition] = []
    if level:
        musts.append(models.FieldCondition(key="chunk_level", match=models.MatchValue(value=level)))
    if ocs_code:
        musts.append(models.FieldCondition(key="ocs_code", match=models.MatchValue(value=ocs_code)))
    if is_current is not None:
        musts.append(models.FieldCondition(key="is_current", match=models.MatchValue(value=is_current)))
    return models.Filter(must=musts) if musts else None
```
And in BOTH `dense_search` and `hybrid_search`: remove the `k_codes`/`s_codes`/`attitude_codes` params from the signature AND from the `build_filter(...)` call (keep `level`/`ocs_code`/`is_current`/`limit`/`prefetch_limit`).

- [ ] **Step 4: Run** `uv run pytest tests/test_search_filter.py -v` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(search): v3 filter — drop OCS-local code filters"`

---

## Task 3: `smoke_query.py` — `id` on Hit, remove KS-code filter

**Files:** Modify `src/jd_ocs_indexer/validation/smoke_query.py`; Test: `tests/test_smoke_query_hit.py`

- [ ] **Step 1: Failing test** — `tests/test_smoke_query_hit.py`:
```python
from types import SimpleNamespace
from jd_ocs_indexer.validation.smoke_query import _to_hit, Hit, filter_by_ks_code  # noqa: F401


def test_to_hit_carries_id_not_chunk_key():
    p = SimpleNamespace(id="pt-1", payload={"chunk_level": "task", "ocs_code": "OC1", "job_title": "JT"}, score=0.9)
    h = _to_hit(p)
    assert h.id == "pt-1"
    assert h.chunk_level == "task" and h.ocs_code == "OC1"
    assert not hasattr(h, "chunk_key")
```
Add a second test asserting `filter_by_ks_code` is removed:
```python
def test_filter_by_ks_code_is_removed():
    import jd_ocs_indexer.validation.smoke_query as sq
    assert not hasattr(sq, "filter_by_ks_code")
```
> Note: the import line above will fail at collection once `filter_by_ks_code` is removed — change the import to `from jd_ocs_indexer.validation.smoke_query import _to_hit, Hit` in Step 3.

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Edit `smoke_query.py`**:
  - `Hit` dataclass: replace `chunk_key: str` with `id: str | None`. Keep chunk_level/ocs_code/job_title/score/payload.
  - `_to_hit`: 
```python
def _to_hit(p: Any) -> Hit:
    payload = p.payload or {}
    return Hit(
        id=getattr(p, "id", None),
        chunk_level=payload.get("chunk_level", ""),
        ocs_code=payload.get("ocs_code", ""),
        job_title=payload.get("job_title", ""),
        score=getattr(p, "score", None),
        payload=payload,
    )
```
  - **Delete** the entire `filter_by_ks_code` function.
  - Fix the test import (remove `filter_by_ks_code` from the import in `test_smoke_query_hit.py`).

- [ ] **Step 4: Run** `uv run pytest tests/test_smoke_query_hit.py -v` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(smoke): Hit carries point id; drop KS-code filter (v3)"`

---

## Task 4: `stats.py` — by_level profile/task

**Files:** Modify `src/jd_ocs_indexer/validation/stats.py`; Test: `tests/test_collection_stats.py`

- [ ] **Step 1: Failing test** — `tests/test_collection_stats.py`:
```python
from jd_ocs_indexer.validation.stats import collection_stats
from tests.conftest import FakeQdrant


def test_collection_stats_counts_profile_and_task():
    fake = FakeQdrant(counts={"__total__": 55, "profile": 5, "task": 50})
    c = collection_stats(fake, "ocs_v3")
    assert c.total_points == 55
    assert c.by_level == {"profile": 5, "task": 50}
```
> `FakeQdrant.count` returns `_counts[_level_of(filter)]`; `collection_stats` calls `count` once per level plus a total. The existing total uses `exact=True` with no filter → key `"__total__"`.

- [ ] **Step 2: Run** → FAIL (current iterates profile/unit/block → by_level has unit/block keys).

- [ ] **Step 3: Edit `stats.py`** — in `collection_stats`, change the loop:
```python
    for level in ("profile", "task"):
```

- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(stats): by_level counts profile/task (v3)"`

---

## Task 5: `schemas.py` — v3 request/response models

**Files:** Modify `src/jd_ocs_indexer/api/schemas.py`; Test: `tests/test_schemas.py` (rewrite)

- [ ] **Step 1: Failing test** — replace `tests/test_schemas.py` with:
```python
import pytest
from pydantic import ValidationError
from jd_ocs_indexer.api import schemas


def test_search_request_level_is_profile_or_task():
    schemas.SearchRequest(query="x", level="task")
    schemas.SearchRequest(query="x", level="profile")
    with pytest.raises(ValidationError):
        schemas.SearchRequest(query="x", level="block")


def test_search_filters_have_no_code_fields():
    f = schemas.SearchFilters()
    assert not hasattr(f, "k_codes") and not hasattr(f, "s_codes") and not hasattr(f, "attitude_codes")
    assert {"ocs_code", "is_current"} <= set(schemas.SearchFilters.model_fields)


def test_hit_v3_shape():
    fields = set(schemas.Hit.model_fields)
    assert {"id", "task_id", "task_title", "activity_examples", "output_pairs", "competency_level"} <= fields
    for gone in ("task_ids", "task_titles", "block_order", "unit_order", "snippet"):
        assert gone not in fields


def test_task_carries_id():
    assert "id" in schemas.Task.model_fields


def test_task_pool_request_nonempty():
    with pytest.raises(ValidationError):
        schemas.TaskPoolRequest(ocs_codes=[])
```

- [ ] **Step 2: Run** `uv run pytest tests/test_schemas.py -v` → FAIL.

- [ ] **Step 3: Edit `schemas.py`** — apply:
  - `SearchFilters`: keep only `ocs_code: Optional[str] = None` and `is_current: Optional[bool] = None` (delete k_codes/s_codes/attitude_codes).
  - `SearchRequest.level`: `Optional[Literal["profile", "task"]] = None`. Delete `include_text` and `text_lines` (no stored text).
  - `Hit`: replace with:
```python
class Hit(BaseModel):
    id: Optional[str] = None
    chunk_level: str
    ocs_code: str
    score: Optional[float] = None
    # profile fields
    job_title: Optional[str] = None
    job_description: Optional[str] = None
    version: Optional[str] = None
    is_current: Optional[bool] = None
    ocs_level: Optional[int] = None
    industry_names: list[str] = Field(default_factory=list)
    occupation_names: list[str] = Field(default_factory=list)
    # task fields
    unit_id: Optional[str] = None
    unit_title: Optional[str] = None
    task_id: Optional[str] = None
    task_title: Optional[str] = None
    competency_level: Optional[int] = None
    activity_examples: list[str] = Field(default_factory=list)
    k_pairs: list[Pair] = Field(default_factory=list)
    s_pairs: list[Pair] = Field(default_factory=list)
    output_pairs: list[Pair] = Field(default_factory=list)
    source_file: Optional[str] = None
```
  - `Task`: add `id: Optional[str] = None` (first field).
  - `Unit`: delete `unit_order`.
  - `OcsGroup`, `TaskPoolResponse`, `PairsResponse`, `Health/StatsResponse`: unchanged.

- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(api): v3 request/response schemas"`

---

## Task 6: `service.py` — `_project_hit` + `search`

**Files:** Modify `src/jd_ocs_indexer/api/service.py`; Test: `tests/test_service_search.py` (rewrite)

- [ ] **Step 1: Failing test** — replace `tests/test_service_search.py` with:
```python
from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint, StubEmbedder


def test_search_projects_task_hit_with_id():
    pt = FakePoint(id="pt-1", score=0.9, payload={
        "chunk_level": "task", "ocs_code": "OC1", "unit_id": "U1", "unit_title": "U",
        "task_id": "T1.1", "task_title": "任務一", "competency_level": 3,
        "activity_examples": ["a1"], "k_pairs": [{"code": "K01", "name": "k"}],
        "s_pairs": [], "output_pairs": [{"code": "O01", "name": "o"}],
    })
    fake = FakeQdrant(query_points=[pt])
    out = service.search(fake, StubEmbedder(), "ocs_v3", query="x", hybrid=False, top_k=5)
    assert out["mode"] == "dense"
    h = out["hits"][0]
    assert h["id"] == "pt-1" and h["task_id"] == "T1.1" and h["competency_level"] == 3
    assert h["activity_examples"] == ["a1"] and h["output_pairs"] == [{"code": "O01", "name": "o"}]
    assert "snippet" not in h and "task_titles" not in h


def test_search_projects_profile_hit():
    pt = FakePoint(id="pf-1", score=0.8, payload={
        "chunk_level": "profile", "ocs_code": "OC1", "job_title": "JT",
        "job_description": "desc", "is_current": True, "ocs_level": 4,
    })
    out = service.search(FakeQdrant(query_points=[pt]), StubEmbedder(), "ocs_v3", query="x", hybrid=True)
    h = out["hits"][0]
    assert h["chunk_level"] == "profile" and h["job_title"] == "JT" and h["job_description"] == "desc"
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Edit `service.py`** — replace `_project_hit` and `search`:
```python
def _project_hit(hit) -> dict:
    p = hit.payload or {}
    return {
        "id": getattr(hit, "id", None),
        "chunk_level": p.get("chunk_level", ""),
        "ocs_code": p.get("ocs_code", ""),
        "score": hit.score,
        "job_title": p.get("job_title"),
        "job_description": p.get("job_description"),
        "version": p.get("version"),
        "is_current": p.get("is_current"),
        "ocs_level": p.get("ocs_level"),
        "industry_names": p.get("industry_names") or [],
        "occupation_names": p.get("occupation_names") or [],
        "unit_id": p.get("unit_id"),
        "unit_title": p.get("unit_title"),
        "task_id": p.get("task_id"),
        "task_title": p.get("task_title"),
        "competency_level": p.get("competency_level"),
        "activity_examples": p.get("activity_examples") or [],
        "k_pairs": p.get("k_pairs") or [],
        "s_pairs": p.get("s_pairs") or [],
        "output_pairs": p.get("output_pairs") or [],
        "source_file": p.get("source_file"),
    }


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
) -> dict:
    filters = filters or {}
    vec = embedder.embed_query(query)
    kw = dict(level=level, ocs_code=filters.get("ocs_code"), is_current=filters.get("is_current"), limit=top_k)
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
    return {"mode": mode, "level": level, "hits": [_project_hit(h) for h in hits]}
```

- [ ] **Step 4: Run** `uv run pytest tests/test_service_search.py -v` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(api): v3 hit projection + search (id, profile+task, no code filters)"`

---

## Task 7: `service.py` — `build_task_pool` from task points

**Files:** Modify `src/jd_ocs_indexer/api/service.py`; Test: `tests/test_service_task_pool.py` (rewrite)

- [ ] **Step 1: Failing test** — replace `tests/test_service_task_pool.py` with:
```python
from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint


def _task(ocs, unit, tid, title, acts):
    return FakePoint(id=f"{ocs}-{tid}", payload={
        "chunk_level": "task", "ocs_code": ocs, "unit_id": unit, "unit_title": "U-" + unit,
        "task_id": tid, "task_title": title, "activity_examples": acts,
    })


def test_task_pool_groups_task_points_by_unit_with_id_and_jobtitle():
    profiles = [FakePoint(id="pf", payload={"chunk_level": "profile", "ocs_code": "OC1", "job_title": "工程師"})]
    tasks = [
        _task("OC1", "U1", "T1.2", "任務B", ["a", "b"]),
        _task("OC1", "U1", "T1.1", "任務A", ["c"]),
    ]
    # service scrolls profiles first, then tasks → two scroll pages
    fake = FakeQdrant(scroll_pages=[(profiles, None), (tasks, None)])
    out = service.build_task_pool(fake, "ocs_v3", ocs_codes=["OC1"], activity_examples=1)
    g = out["groups"][0]
    assert g["ocs_code"] == "OC1" and g["job_title"] == "工程師"
    u = g["units"][0]
    assert u["unit_id"] == "U1" and u["unit_title"] == "U-U1"
    # tasks sorted by task_id; activity_examples capped at 1; each carries id
    assert [t["task_id"] for t in u["tasks"]] == ["T1.1", "T1.2"]
    assert u["tasks"][0]["id"] == "OC1-T1.1" and u["tasks"][1]["activity_examples"] == ["a"]
```
> The fake serves scroll pages in order: page 1 = profiles, page 2 = tasks. `build_task_pool` must scroll profiles first (for job_title), then tasks.

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Edit `service.py`** — add a records-preserving scroll helper and replace `build_task_pool`:
```python
def _scroll_records(client, collection: str, flt, *, page: int = 256) -> list:
    out: list = []
    offset = None
    while True:
        records, offset = client.scroll(
            collection_name=collection, scroll_filter=flt,
            with_payload=True, with_vectors=False, limit=page, offset=offset,
        )
        out.extend(records)
        if offset is None:
            break
    return out


def build_task_pool(client, collection: str, *, ocs_codes: list[str], activity_examples: int = 1) -> dict:
    """Round-2 task menu, sourced from v3 task points (one point per task)."""
    prof_flt = models.Filter(must=[
        models.FieldCondition(key="chunk_level", match=models.MatchValue(value="profile")),
        models.FieldCondition(key="ocs_code", match=models.MatchAny(any=list(ocs_codes))),
    ])
    job_titles = {
        (r.payload or {}).get("ocs_code"): (r.payload or {}).get("job_title") or ""
        for r in _scroll_records(client, collection, prof_flt)
    }
    task_flt = models.Filter(must=[
        models.FieldCondition(key="chunk_level", match=models.MatchValue(value="task")),
        models.FieldCondition(key="ocs_code", match=models.MatchAny(any=list(ocs_codes))),
    ])
    groups: dict[str, dict] = {}
    for r in _scroll_records(client, collection, task_flt):
        p = r.payload or {}
        oc = p.get("ocs_code")
        if oc is None:
            continue
        g = groups.setdefault(oc, {"units": {}})
        ukey = p.get("unit_id")
        u = g["units"].setdefault(ukey, {"unit_id": p.get("unit_id"), "unit_title": p.get("unit_title"), "tasks": []})
        u["tasks"].append({
            "id": getattr(r, "id", None),
            "task_id": p.get("task_id"),
            "task_title": p.get("task_title"),
            "activity_examples": (p.get("activity_examples") or [])[:activity_examples],
        })
    out_groups = []
    for oc in ocs_codes:
        g = groups.get(oc)
        if not g:
            continue
        units_sorted = sorted(g["units"].values(), key=lambda u: (u["unit_id"] is None, u["unit_id"] or ""))
        for u in units_sorted:
            u["tasks"].sort(key=lambda t: (t["task_id"] is None, t["task_id"] or ""))
        out_groups.append({"ocs_code": oc, "job_title": job_titles.get(oc, ""), "units": units_sorted})
    return {"groups": out_groups}
```
> The old `_scroll_all` (payload-only) is still used by `get_pairs` — keep it.

- [ ] **Step 4: Run** `uv run pytest tests/test_service_task_pool.py -v` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(api): task-pool from v3 task points (per-unit, with id + job_title)"`

---

## Task 8: `service.py` — `get_pairs` aggregated from task points

**Files:** Modify `src/jd_ocs_indexer/api/service.py`; Test: `tests/test_service_pairs.py` (rewrite)

- [ ] **Step 1: Failing test** — replace `tests/test_service_pairs.py` with:
```python
from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint


def test_get_pairs_unions_task_pairs_plus_profile_attitudes():
    profile = [FakePoint(payload={
        "chunk_level": "profile", "ocs_code": "OC1", "job_title": "JT",
        "all_a_pairs": [{"code": "A01", "name": "主動"}],
    })]
    tasks = [
        FakePoint(payload={"chunk_level": "task", "ocs_code": "OC1",
                           "k_pairs": [{"code": "K01", "name": "k1"}], "s_pairs": [{"code": "S01", "name": "s1"}],
                           "output_pairs": [{"code": "O01", "name": "o1"}]}),
        FakePoint(payload={"chunk_level": "task", "ocs_code": "OC1",
                           "k_pairs": [{"code": "K01", "name": "k1"}, {"code": "K02", "name": "k2"}],
                           "s_pairs": [], "output_pairs": []}),
    ]
    # get_pairs scrolls profile (limit 1) then task points
    fake = FakeQdrant(scroll_pages=[(profile, None), (tasks, None)])
    out = service.get_pairs(fake, "ocs_v3", ocs_code="OC1")
    assert out["job_title"] == "JT"
    assert [p["code"] for p in out["all_k_pairs"]] == ["K01", "K02"]   # deduped, in order
    assert [p["code"] for p in out["all_s_pairs"]] == ["S01"]
    assert [p["code"] for p in out["all_output_pairs"]] == ["O01"]
    assert out["all_a_pairs"] == [{"code": "A01", "name": "主動"}]


def test_get_pairs_missing_profile_returns_none():
    fake = FakeQdrant(scroll_pages=[([], None)])
    assert service.get_pairs(fake, "ocs_v3", ocs_code="NOPE") is None
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Edit `service.py`** — replace `get_pairs`:
```python
def get_pairs(client, collection: str, *, ocs_code: str) -> dict | None:
    """OCS-wide K/S/output pools (union of task points) + attitudes (profile)."""
    prof_flt = models.Filter(must=[
        models.FieldCondition(key="ocs_code", match=models.MatchValue(value=ocs_code)),
        models.FieldCondition(key="chunk_level", match=models.MatchValue(value="profile")),
    ])
    prof_recs, _ = client.scroll(
        collection_name=collection, scroll_filter=prof_flt,
        with_payload=True, with_vectors=False, limit=1,
    )
    if not prof_recs:
        return None
    pp = prof_recs[0].payload or {}

    task_flt = models.Filter(must=[
        models.FieldCondition(key="ocs_code", match=models.MatchValue(value=ocs_code)),
        models.FieldCondition(key="chunk_level", match=models.MatchValue(value="task")),
    ])
    task_payloads = _scroll_all(client, collection, task_flt)

    def _union(key: str) -> list[dict]:
        out: list[dict] = []
        seen: set = set()
        for p in task_payloads:
            for pair in (p.get(key) or []):
                code = pair.get("code")
                if code not in seen:
                    seen.add(code)
                    out.append(pair)
        return out

    return {
        "ocs_code": ocs_code,
        "job_title": pp.get("job_title") or "",
        "all_k_pairs": _union("k_pairs"),
        "all_s_pairs": _union("s_pairs"),
        "all_a_pairs": pp.get("all_a_pairs") or [],
        "all_output_pairs": _union("output_pairs"),
    }
```

- [ ] **Step 4: Run** `uv run pytest tests/test_service_pairs.py -v` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(api): /pairs unions task K/S/output + profile attitudes (v3)"`

---

## Task 9: cli `query` + `_print_query_hit` → v3

**Files:** Modify `src/jd_ocs_indexer/cli.py`; manual verify (no unit test — display only).

- [ ] **Step 1:** In the `query` command, change the `--level` help to `"Filter chunk level: profile / task."`.
- [ ] **Step 2:** Replace `_print_query_hit` body to read v3 fields off `hit.payload` (`p`): use `p.get("task_title")`/`p.get("task_id")` (singular), `p.get("unit_title")`/`p.get("unit_id")`, `competency_level`, `k_pairs`/`s_pairs`/`output_pairs`, `activity_examples`. Remove the `task_titles`/`task_ids` (plural), `block_order`/`block_title`, `k_codes`/`s_codes` fallback, and the `p.get("text")` body block (v3 stores no text). `level_color` dict → `{"profile": "magenta", "task": "green"}`. Show `hit.id` (point id) on the head line. Drop the `--text-lines` option.
- [ ] **Step 3: Verify** — `uv run jd-ocs-indexer --help` and `uv run python -c "from jd_ocs_indexer.cli import app"` → import-ok; `query --help` shows `--level` profile/task and no `--text-lines`.
- [ ] **Step 4: Commit** — `git commit -m "feat(cli): v3 query display (task singular, point id, no text body)"`

---

## Task 10: rewrite remaining route tests + full green

**Files:** `tests/test_routes.py`, `tests/test_service_stats_health.py` (rewrite to v3 payloads).

- [ ] **Step 1:** Update `tests/test_routes.py`: replace v2 payloads (`chunk_level: "block"`, `unit_order`, `task_ids`) with v3 task/profile payloads carrying `id`; the `/search` route assertion checks `hits[0]["id"]`/`task_id`; the `/stats` route counts use `{"__total__":..,"profile":..,"task":..}`. Update `tests/test_service_stats_health.py` counts to `{"profile":5,"task":50}` and assert `by_level == {"profile":5,"task":50}`.
- [ ] **Step 2: Run full suite** — `uv run pytest -q` → all green.
- [ ] **Step 3: Commit** — `git commit -m "test(api): v3 route + stats/health fixtures"`

---

## Manual acceptance (live `ocs_v3`, needs BGE-M3 + Qdrant)

```bash
QDRANT_COLLECTION=ocs_v3 uv run jd-ocs-indexer serve &   # or call service.* directly
# /search profile:  query="資料分析" level=profile  → profile hits with id+job_title
# /search task:     query="清洗資料" level=task     → task hits with id+k_pairs
# /task-pool:       ocs_codes=[<one acceptance OCS>]  → units→tasks each with id
# /pairs:           ocs_code=<one acceptance OCS>     → all_k/s/output unioned + all_a from profile
```
Expect: task-pool task count per OCS matches that OCS's task points; `/pairs` K/S non-empty.

---

## Notes for the implementer
- **Read `tests/conftest.py` first** — `FakeQdrant` (`query_points`/`scroll`/`count`) + `FakePoint` are the harness. `query_points` returns canned points ignoring the filter; `scroll` serves `scroll_pages` in order; `count` keys off the filter's `chunk_level` (`_level_of`).
- v3 payloads have **no** `chunk_key`, `text`, `task_ids`/`task_titles`, `block_*`, `unit_order`, `k_codes`/`s_codes`. Don't read them.
- **point id** is exposed via `getattr(hit, "id", None)` (Qdrant points carry `.id`; FakePoint gets `id` in Task 1).
- The by-id **retrieve endpoint** (consuming the exposed ids) is intentionally **out of scope** — add it when jobintel-ai needs it.
- No Co-Authored-By trailer on commits (repo convention).
