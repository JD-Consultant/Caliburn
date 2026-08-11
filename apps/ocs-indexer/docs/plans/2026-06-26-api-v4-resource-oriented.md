# Indexer API v4 (Resource-Oriented + Provenance) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the jd-ocs-indexer query API into a self-documenting, resource-oriented surface that reads the new **v4 Qdrant payload** and returns every K/S/O/P/A item with provenance (a stable URN + source path).

**Architecture:** Stateless service over Qdrant + BGE-M3. The v4 builder (already committed, `9e5091e`) writes profile points (`ocs_name` nested, `job_categories/occupations/industries` as `[{code,name}]`, `attitudes`) and task points (per task_code, nested `competency_blocks[{competency_level, indicators[{code,text}], outputs/knowledge/skills[{code,name}]}]`). This plan rewrites `schemas.py` / `service.py` / `routes.py` to project that payload into resource-oriented responses. Provenance URNs are **composed at query time** from payload fields (never stored). Dedup similarity (`findSimilar`) returns candidate pairs only; clustering/merge lives in the v3 consumer (out of scope here).

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, Qdrant client, pytest, uv, numpy.

## Global Constraints

- Repo: `S:\jd-ocs-indexer`, branch `dev`. Run tests with: `cd /s/jd-ocs-indexer && uv run pytest`.
- **Do NOT touch** `ingestion/builder.py`, `ingestion/normalizer.py`, `ingestion/payloads.py` — Phase A is done & committed (`9e5091e`). This plan only consumes the v4 payload they produce.
- **Do NOT re-ingest** and **do NOT touch live Qdrant**. Tests use `FakeQdrant` (in `tests/conftest.py`) with hand-written v4 payloads. Re-ingest is a later cross-repo step after the v3 consumer is updated.
- Commits: no `Co-Authored-By` trailer.
- `SCHEMA_VERSION = "v4"`. URN scheme: occupation `ocs:{ocs_code}`, unit `ocs:{ocs_code}:U:{ocu_code}`, task `ocs:{ocs_code}:T:{task_code}`, item `ocs:{ocs_code}:{K|S|O|P|A}:{code}`.
- The OLD endpoints/functions are **replaced** (not kept additively): old `service.search/build_task_pool/get_pairs/get_profile/retrieve_tasks`, old `schemas.*`, old routes, and old tests (`test_service_*`, `test_routes`, `test_schemas`) get deleted/rewritten. Task 9 does the cleanup.
- TDD strictly: write the failing test, watch it fail, minimal code, watch it pass, commit. No production code without a failing test first.

**v4 payload reference** (what `FakeQdrant` fixtures must mimic):

```python
# profile point
{"chunk_level":"profile","schema_version":"v4","ocs_code":"OC1v2","ocs_code_base":"OC1",
 "is_current":True,"ocs_name":{"job_category_name":None,"occupation_name":"資料分析師"},
 "job_description":"負責資料分析","ocs_level":4,
 "job_categories":[{"code":"JC1","name":"資訊類"}],"occupations":[{"code":"OCC1","name":"分析師"}],
 "industries":[{"code":"I1","name":"資訊業"}],"attitudes":[{"code":"A01","name":"主動積極"}],
 "prerequisites":["大學以上學歷"],"supplements":["須具備證照"],
 "indexed_at":"...","source_file":"OC1v2.json"}

# task point (one per task_code)
{"chunk_level":"task","schema_version":"v4","ocs_code":"OC1v2","ocs_name":"資料分析師",
 "ocu_code":"T1","ocu_name":"資料處理","task_code":"T1.1","task_name":"資料清理",
 "competency_blocks":[{"competency_level":3,
   "indicators":[{"code":"P01","text":"用Python清洗資料"}],
   "outputs":[{"code":"O01","name":"清理後資料集"}],
   "knowledge":[{"code":"K01","name":"資料處理概念"}],
   "skills":[{"code":"S01","name":"Python"}]}],
 "source_file":"OC1v2.json"}
```

## File Structure

- Create `src/jd_ocs_indexer/api/urn.py` — pure URN composition functions.
- Rewrite `src/jd_ocs_indexer/api/schemas.py` — request/response models (incl. `SourceRef`, `CitableItem`).
- Rewrite `src/jd_ocs_indexer/api/service.py` — projection functions over Qdrant.
- Rewrite `src/jd_ocs_indexer/api/routes.py` — resource-oriented routes.
- Tests: `tests/test_urn.py`, `tests/test_occupation_detail.py`, `tests/test_competencies.py`, `tests/test_occupation_tasks.py`, `tests/test_task_batch_get.py`, `tests/test_occupation_search.py`, `tests/test_task_search.py`, `tests/test_find_similar.py`. Delete old `tests/test_service_*.py`, `tests/test_routes.py`, `tests/test_schemas.py` in Task 9.
- `tests/conftest.py` `FakeQdrant` stays as-is (it already covers `scroll`/`query_points`/`retrieve`); Task 8 adds a `with_vectors` payload variant via the existing `FakePoint`.

---

### Task 1: URN helpers + provenance contract (`urn.py`, `SourceRef`, `CitableItem`)

**Files:**
- Create: `src/jd_ocs_indexer/api/urn.py`
- Modify: `src/jd_ocs_indexer/api/schemas.py` (add `SourceRef`, `CitableItem`; leave old models for now — removed in Task 9)
- Test: `tests/test_urn.py`

**Interfaces:**
- Produces: `urn.occupation_urn(ocs_code)->str`, `urn.unit_urn(ocs_code,ocu_code)->str`, `urn.task_urn(ocs_code,task_code)->str`, `urn.item_urn(ocs_code,type_,code)->str`. Pydantic `SourceRef{ocu_code,ocu_name,task_code,task_name,competency_level}`, `CitableItem{id,type,code,name?,text?,ocs_code,ocs_name,sources:list[SourceRef]}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_urn.py
from jd_ocs_indexer.api import urn

def test_urn_scheme():
    assert urn.occupation_urn("OC1v2") == "ocs:OC1v2"
    assert urn.unit_urn("OC1v2", "T1") == "ocs:OC1v2:U:T1"
    assert urn.task_urn("OC1v2", "T1.1") == "ocs:OC1v2:T:T1.1"
    assert urn.item_urn("OC1v2", "K", "K01") == "ocs:OC1v2:K:K01"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /s/jd-ocs-indexer && uv run pytest tests/test_urn.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'jd_ocs_indexer.api.urn'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/jd_ocs_indexer/api/urn.py
"""Stable citable identifiers (URN) for OCS entities. Composed at query time
from payload fields; never stored. Scheme: ocs:{ocs_code}[:{TYPE}:{code}]."""
from __future__ import annotations


def occupation_urn(ocs_code: str) -> str:
    return f"ocs:{ocs_code}"


def unit_urn(ocs_code: str, ocu_code: str) -> str:
    return f"ocs:{ocs_code}:U:{ocu_code}"


def task_urn(ocs_code: str, task_code: str) -> str:
    return f"ocs:{ocs_code}:T:{task_code}"


def item_urn(ocs_code: str, type_: str, code: str) -> str:
    return f"ocs:{ocs_code}:{type_}:{code}"
```

Then add to `src/jd_ocs_indexer/api/schemas.py` (append; keep existing models until Task 9):

```python
class SourceRef(BaseModel):
    ocu_code: Optional[str] = None
    ocu_name: Optional[str] = None
    task_code: Optional[str] = None
    task_name: Optional[str] = None
    competency_level: Optional[int] = None


class CitableItem(BaseModel):
    id: str                      # URN
    type: str                    # K | S | O | P | A
    code: str
    name: Optional[str] = None   # K/S/O/A
    text: Optional[str] = None   # P
    ocs_code: str
    ocs_name: str
    sources: list[SourceRef] = Field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /s/jd-ocs-indexer && uv run pytest tests/test_urn.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /s/jd-ocs-indexer && git add src/jd_ocs_indexer/api/urn.py src/jd_ocs_indexer/api/schemas.py tests/test_urn.py
git commit -m "feat(api): URN helpers + SourceRef/CitableItem provenance contract"
```

---

### Task 2: `GET /occupations/{ocs_code}` — occupation detail (profile + category)

**Files:**
- Modify: `src/jd_ocs_indexer/api/service.py` (add `get_occupation`), `schemas.py` (add `OccupationDetail`, `CodeName` if not present), `routes.py` (add route)
- Test: `tests/test_occupation_detail.py`

**Interfaces:**
- Produces: `service.get_occupation(client, collection, *, ocs_code) -> dict | None`. Response `OccupationDetail{ocs_code, urn, ocs_name:{job_category_name,occupation_name}, job_categories:list[CodeName], occupations:list[CodeName], industries:list[CodeName], job_description, ocs_level, attitudes:list[CodeName], prerequisites:list[str], supplements:list[str]}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_occupation_detail.py
from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint

_PROFILE = {
    "chunk_level": "profile", "schema_version": "v4", "ocs_code": "OC1v2",
    "ocs_name": {"job_category_name": None, "occupation_name": "資料分析師"},
    "job_description": "負責資料分析", "ocs_level": 4,
    "job_categories": [{"code": "JC1", "name": "資訊類"}],
    "occupations": [{"code": "OCC1", "name": "分析師"}],
    "industries": [{"code": "I1", "name": "資訊業"}],
    "attitudes": [{"code": "A01", "name": "主動積極"}],
    "prerequisites": ["大學以上學歷"], "supplements": ["須具備證照"],
}

def test_get_occupation_projects_v4_profile():
    fake = FakeQdrant(scroll_pages=[([FakePoint(payload=_PROFILE)], None)])
    out = service.get_occupation(fake, "ocs_v3", ocs_code="OC1v2")
    assert out["ocs_code"] == "OC1v2" and out["urn"] == "ocs:OC1v2"
    assert out["ocs_name"] == {"job_category_name": None, "occupation_name": "資料分析師"}
    assert out["job_categories"] == [{"code": "JC1", "name": "資訊類"}]
    assert out["occupations"] == [{"code": "OCC1", "name": "分析師"}]
    assert out["industries"] == [{"code": "I1", "name": "資訊業"}]
    assert out["attitudes"] == [{"code": "A01", "name": "主動積極"}]
    assert out["job_description"] == "負責資料分析" and out["ocs_level"] == 4

def test_get_occupation_missing_returns_none():
    assert service.get_occupation(FakeQdrant(scroll_pages=[([], None)]), "c", ocs_code="X") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /s/jd-ocs-indexer && uv run pytest tests/test_occupation_detail.py -q`
Expected: FAIL — `AttributeError: module 'jd_ocs_indexer.api.service' has no attribute 'get_occupation'`

- [ ] **Step 3: Write minimal implementation**

Add to `service.py` (top: `from jd_ocs_indexer.api import urn`):

```python
def _profile_point(client, collection, ocs_code):
    flt = models.Filter(must=[
        models.FieldCondition(key="ocs_code", match=models.MatchValue(value=ocs_code)),
        models.FieldCondition(key="chunk_level", match=models.MatchValue(value="profile")),
    ])
    recs, _ = client.scroll(collection_name=collection, scroll_filter=flt,
                            with_payload=True, with_vectors=False, limit=1)
    return (recs[0].payload or {}) if recs else None


def _resolve_ocs_name(profile_payload: dict) -> str:
    n = profile_payload.get("ocs_name") or {}
    return n.get("occupation_name") or n.get("job_category_name") or profile_payload.get("ocs_code", "")


def get_occupation(client, collection: str, *, ocs_code: str) -> dict | None:
    p = _profile_point(client, collection, ocs_code)
    if p is None:
        return None
    return {
        "ocs_code": p.get("ocs_code", ""),
        "urn": urn.occupation_urn(p.get("ocs_code", "")),
        "ocs_name": p.get("ocs_name") or {"job_category_name": None, "occupation_name": None},
        "job_categories": p.get("job_categories") or [],
        "occupations": p.get("occupations") or [],
        "industries": p.get("industries") or [],
        "job_description": p.get("job_description") or "",
        "ocs_level": p.get("ocs_level"),
        "attitudes": p.get("attitudes") or [],
        "prerequisites": p.get("prerequisites") or [],
        "supplements": p.get("supplements") or [],
    }
```

Add schemas (`schemas.py`):

```python
class OcsName(BaseModel):
    job_category_name: Optional[str] = None
    occupation_name: Optional[str] = None

class OccupationDetail(BaseModel):
    ocs_code: str
    urn: str
    ocs_name: OcsName
    job_categories: list[CodeName] = Field(default_factory=list)
    occupations: list[CodeName] = Field(default_factory=list)
    industries: list[CodeName] = Field(default_factory=list)
    job_description: str = ""
    ocs_level: Optional[int] = None
    attitudes: list[CodeName] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)
```

Add route (`routes.py`, import `OccupationDetail`):

```python
@router.get("/occupations/{ocs_code}", response_model=OccupationDetail)
async def get_occupation(ocs_code: str, request: Request):
    app = request.app
    result = await run_in_threadpool(
        service.get_occupation, app.state.client,
        app.state.settings.qdrant_collection, ocs_code=ocs_code)
    if result is None:
        raise HTTPException(status_code=404, detail="ocs_code not found")
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /s/jd-ocs-indexer && uv run pytest tests/test_occupation_detail.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /s/jd-ocs-indexer && git add src/jd_ocs_indexer/api/service.py src/jd_ocs_indexer/api/schemas.py src/jd_ocs_indexer/api/routes.py tests/test_occupation_detail.py
git commit -m "feat(api): GET /occupations/{ocs_code} — v4 profile + category auto-fill"
```

---

### Task 3: `GET /occupations/{ocs_code}/competencies` — K/S/O/P/A pool with provenance

**Files:**
- Modify: `service.py` (add `get_competencies`), `schemas.py` (add `CompetencyPool`), `routes.py` (add route)
- Test: `tests/test_competencies.py`

**Interfaces:**
- Consumes: `urn.item_urn`, `service._profile_point`, `service._resolve_ocs_name`, `SourceRef`/`CitableItem` shapes.
- Produces: `service.get_competencies(client, collection, *, ocs_code) -> dict | None`. Response `CompetencyPool{ocs_code, knowledge:list[CitableItem], skills:list[CitableItem], outputs:list[CitableItem], indicators:list[CitableItem], attitudes:list[CitableItem]}`. K/S dedup by URN, **multi-source** (sources accumulate across tasks/blocks). O/P single-source. A from profile, `sources=[]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_competencies.py
from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint

_PROFILE = {"chunk_level": "profile", "ocs_code": "OC1", "ocs_name": {"occupation_name": "JT"},
            "attitudes": [{"code": "A01", "name": "主動"}]}
_T1 = {"chunk_level": "task", "ocs_code": "OC1", "ocs_name": "JT", "ocu_code": "U1", "ocu_name": "單元一",
       "task_code": "T1.1", "task_name": "任務一", "competency_blocks": [
           {"competency_level": 3, "indicators": [{"code": "P1.1.1", "text": "p text"}],
            "outputs": [{"code": "O1.1.1", "name": "o1"}],
            "knowledge": [{"code": "K01", "name": "k1"}], "skills": [{"code": "S01", "name": "s1"}]}]}
_T2 = {"chunk_level": "task", "ocs_code": "OC1", "ocs_name": "JT", "ocu_code": "U1", "ocu_name": "單元一",
       "task_code": "T1.2", "task_name": "任務二", "competency_blocks": [
           {"competency_level": 3, "indicators": [], "outputs": [],
            "knowledge": [{"code": "K01", "name": "k1"}], "skills": []}]}  # K01 reused -> multi-source

def test_competencies_citable_items_with_provenance():
    fake = FakeQdrant(scroll_pages=[([FakePoint(payload=_PROFILE)], None),
                                    ([FakePoint(payload=_T1), FakePoint(payload=_T2)], None)])
    out = service.get_competencies(fake, "ocs_v3", ocs_code="OC1")
    k = out["knowledge"]
    assert len(k) == 1 and k[0]["id"] == "ocs:OC1:K:K01" and k[0]["type"] == "K" and k[0]["name"] == "k1"
    # K01 appears in T1.1 and T1.2 -> two sources
    assert [s["task_code"] for s in k[0]["sources"]] == ["T1.1", "T1.2"]
    assert k[0]["sources"][0]["competency_level"] == 3
    assert out["indicators"][0]["id"] == "ocs:OC1:P:P1.1.1" and out["indicators"][0]["text"] == "p text"
    assert out["outputs"][0]["id"] == "ocs:OC1:O:O1.1.1"
    assert out["attitudes"][0]["id"] == "ocs:OC1:A:A01" and out["attitudes"][0]["sources"] == []

def test_competencies_missing_profile_returns_none():
    assert service.get_competencies(FakeQdrant(scroll_pages=[([], None)]), "c", ocs_code="X") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /s/jd-ocs-indexer && uv run pytest tests/test_competencies.py -q`
Expected: FAIL — `AttributeError: ... has no attribute 'get_competencies'`

- [ ] **Step 3: Write minimal implementation**

Add to `service.py`:

```python
def _task_points(client, collection, ocs_code):
    flt = models.Filter(must=[
        models.FieldCondition(key="ocs_code", match=models.MatchValue(value=ocs_code)),
        models.FieldCondition(key="chunk_level", match=models.MatchValue(value="task")),
    ])
    return _scroll_all(client, collection, flt)


def get_competencies(client, collection: str, *, ocs_code: str) -> dict | None:
    prof = _profile_point(client, collection, ocs_code)
    if prof is None:
        return None
    ocs_name = _resolve_ocs_name(prof)
    buckets: dict[str, dict[str, dict]] = {"K": {}, "S": {}, "O": {}, "P": {}}
    for p in _task_points(client, collection, ocs_code):
        for blk in (p.get("competency_blocks") or []):
            src = {"ocu_code": p.get("ocu_code"), "ocu_name": p.get("ocu_name"),
                   "task_code": p.get("task_code"), "task_name": p.get("task_name"),
                   "competency_level": blk.get("competency_level")}
            for type_, field, val_key in (("K", "knowledge", "name"), ("S", "skills", "name"),
                                          ("O", "outputs", "name"), ("P", "indicators", "text")):
                for it in (blk.get(field) or []):
                    code = it.get("code")
                    if not code:
                        continue
                    key = urn.item_urn(ocs_code, type_, code)
                    item = buckets[type_].get(key)
                    if item is None:
                        item = {"id": key, "type": type_, "code": code,
                                "name": it.get("name"), "text": it.get("text"),
                                "ocs_code": ocs_code, "ocs_name": ocs_name, "sources": []}
                        buckets[type_][key] = item
                    item["sources"].append(src)
    attitudes = [{"id": urn.item_urn(ocs_code, "A", a.get("code", "")), "type": "A",
                  "code": a.get("code", ""), "name": a.get("name"), "text": None,
                  "ocs_code": ocs_code, "ocs_name": ocs_name, "sources": []}
                 for a in (prof.get("attitudes") or []) if a.get("code")]
    return {
        "ocs_code": ocs_code,
        "knowledge": list(buckets["K"].values()), "skills": list(buckets["S"].values()),
        "outputs": list(buckets["O"].values()), "indicators": list(buckets["P"].values()),
        "attitudes": attitudes,
    }
```

Add schema (`schemas.py`):

```python
class CompetencyPool(BaseModel):
    ocs_code: str
    knowledge: list[CitableItem] = Field(default_factory=list)
    skills: list[CitableItem] = Field(default_factory=list)
    outputs: list[CitableItem] = Field(default_factory=list)
    indicators: list[CitableItem] = Field(default_factory=list)
    attitudes: list[CitableItem] = Field(default_factory=list)
```

Add route (`routes.py`, import `CompetencyPool`):

```python
@router.get("/occupations/{ocs_code}/competencies", response_model=CompetencyPool)
async def get_competencies(ocs_code: str, request: Request):
    app = request.app
    result = await run_in_threadpool(
        service.get_competencies, app.state.client,
        app.state.settings.qdrant_collection, ocs_code=ocs_code)
    if result is None:
        raise HTTPException(status_code=404, detail="ocs_code not found")
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /s/jd-ocs-indexer && uv run pytest tests/test_competencies.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /s/jd-ocs-indexer && git add src/jd_ocs_indexer/api/service.py src/jd_ocs_indexer/api/schemas.py src/jd_ocs_indexer/api/routes.py tests/test_competencies.py
git commit -m "feat(api): GET /occupations/{ocs_code}/competencies — CitableItems w/ provenance"
```

---

### Task 4: `GET /occupations/{ocs_code}/tasks` — tasks grouped by unit

**Files:**
- Modify: `service.py` (add `get_occupation_tasks`), `schemas.py` (add `OccupationTasks`/`UnitTasks`/`TaskRef`), `routes.py`
- Test: `tests/test_occupation_tasks.py`

**Interfaces:**
- Consumes: `service._task_points`, `service._profile_point`, `service._resolve_ocs_name`, `urn.task_urn`/`unit_urn`.
- Produces: `service.get_occupation_tasks(client, collection, *, ocs_code) -> dict | None`. Response `OccupationTasks{ocs_code, ocs_name, units:[{ocu_code, ocu_name, urn, tasks:[{task_code, task_name, urn}]}]}`. Units ordered by ocu_code, tasks by task_code.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_occupation_tasks.py
from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint

_PROFILE = {"chunk_level": "profile", "ocs_code": "OC1", "ocs_name": {"occupation_name": "JT"}}
def _task(tc, tn):
    return {"chunk_level": "task", "ocs_code": "OC1", "ocs_name": "JT",
            "ocu_code": "U1", "ocu_name": "單元一", "task_code": tc, "task_name": tn,
            "competency_blocks": []}

def test_occupation_tasks_grouped_by_unit():
    fake = FakeQdrant(scroll_pages=[([FakePoint(payload=_PROFILE)], None),
                                    ([FakePoint(payload=_task("T1.2", "二")), FakePoint(payload=_task("T1.1", "一"))], None)])
    out = service.get_occupation_tasks(fake, "ocs_v3", ocs_code="OC1")
    assert out["ocs_code"] == "OC1" and out["ocs_name"] == "JT"
    unit = out["units"][0]
    assert unit["ocu_code"] == "U1" and unit["urn"] == "ocs:OC1:U:U1"
    assert [t["task_code"] for t in unit["tasks"]] == ["T1.1", "T1.2"]   # sorted
    assert unit["tasks"][0]["urn"] == "ocs:OC1:T:T1.1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /s/jd-ocs-indexer && uv run pytest tests/test_occupation_tasks.py -q`
Expected: FAIL — `... has no attribute 'get_occupation_tasks'`

- [ ] **Step 3: Write minimal implementation**

Add to `service.py`:

```python
def get_occupation_tasks(client, collection: str, *, ocs_code: str) -> dict | None:
    prof = _profile_point(client, collection, ocs_code)
    if prof is None:
        return None
    units: dict[str, dict] = {}
    for p in _task_points(client, collection, ocs_code):
        uc = p.get("ocu_code")
        u = units.setdefault(uc, {"ocu_code": uc, "ocu_name": p.get("ocu_name"),
                                  "urn": urn.unit_urn(ocs_code, uc or ""), "tasks": []})
        u["tasks"].append({"task_code": p.get("task_code"), "task_name": p.get("task_name"),
                           "urn": urn.task_urn(ocs_code, p.get("task_code") or "")})
    for u in units.values():
        u["tasks"].sort(key=lambda t: (t["task_code"] is None, t["task_code"] or ""))
    units_sorted = sorted(units.values(), key=lambda u: (u["ocu_code"] is None, u["ocu_code"] or ""))
    return {"ocs_code": ocs_code, "ocs_name": _resolve_ocs_name(prof), "units": units_sorted}
```

Add schema (`schemas.py`):

```python
class TaskRef(BaseModel):
    task_code: str
    task_name: str
    urn: str

class UnitTasks(BaseModel):
    ocu_code: Optional[str] = None
    ocu_name: Optional[str] = None
    urn: str
    tasks: list[TaskRef] = Field(default_factory=list)

class OccupationTasks(BaseModel):
    ocs_code: str
    ocs_name: str
    units: list[UnitTasks] = Field(default_factory=list)
```

Add route (`routes.py`, import `OccupationTasks`):

```python
@router.get("/occupations/{ocs_code}/tasks", response_model=OccupationTasks)
async def get_occupation_tasks(ocs_code: str, request: Request):
    app = request.app
    result = await run_in_threadpool(
        service.get_occupation_tasks, app.state.client,
        app.state.settings.qdrant_collection, ocs_code=ocs_code)
    if result is None:
        raise HTTPException(status_code=404, detail="ocs_code not found")
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /s/jd-ocs-indexer && uv run pytest tests/test_occupation_tasks.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /s/jd-ocs-indexer && git add src/jd_ocs_indexer/api/service.py src/jd_ocs_indexer/api/schemas.py src/jd_ocs_indexer/api/routes.py tests/test_occupation_tasks.py
git commit -m "feat(api): GET /occupations/{ocs_code}/tasks — tasks grouped by unit"
```

---

### Task 5: `POST /tasks/batchGet` — task details (competency_blocks) by point id

**Files:**
- Modify: `service.py` (add `batch_get_tasks`), `schemas.py` (add `TaskBatchGetRequest`, `TaskDetail`, `TasksResponse`), `routes.py`
- Test: `tests/test_task_batch_get.py`

**Interfaces:**
- Consumes: `urn.task_urn`.
- Produces: `service.batch_get_tasks(client, collection, *, ids) -> dict`. Response `TasksResponse{tasks:list[TaskDetail]}` where `TaskDetail{id, urn, ocs_code, ocs_name, ocu_code, ocu_name, task_code, task_name, competency_blocks:list[dict]}`. Missing ids silently dropped.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_task_batch_get.py
from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint

_T = {"chunk_level": "task", "ocs_code": "OC1", "ocs_name": "JT", "ocu_code": "U1", "ocu_name": "單元一",
      "task_code": "T1.1", "task_name": "任務一", "competency_blocks": [
          {"competency_level": 3, "indicators": [{"code": "P01", "text": "pt"}],
           "outputs": [], "knowledge": [{"code": "K01", "name": "k1"}], "skills": [{"code": "S01", "name": "s1"}]}]}

def test_batch_get_returns_blocks_and_urn():
    fake = FakeQdrant(retrieve_points=[FakePoint(payload=_T, id="pid1")])
    out = service.batch_get_tasks(fake, "ocs_v3", ids=["pid1"])
    t = out["tasks"][0]
    assert t["id"] == "pid1" and t["urn"] == "ocs:OC1:T:T1.1"
    assert t["ocu_code"] == "U1" and t["task_code"] == "T1.1" and t["ocs_name"] == "JT"
    assert t["competency_blocks"][0]["knowledge"] == [{"code": "K01", "name": "k1"}]
    assert t["competency_blocks"][0]["indicators"] == [{"code": "P01", "text": "pt"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /s/jd-ocs-indexer && uv run pytest tests/test_task_batch_get.py -q`
Expected: FAIL — `... has no attribute 'batch_get_tasks'`

- [ ] **Step 3: Write minimal implementation**

Add to `service.py`:

```python
def _project_task(rec) -> dict:
    p = rec.payload or {}
    return {
        "id": str(getattr(rec, "id", "")),
        "urn": urn.task_urn(p.get("ocs_code", ""), p.get("task_code") or ""),
        "ocs_code": p.get("ocs_code", ""), "ocs_name": p.get("ocs_name") or "",
        "ocu_code": p.get("ocu_code"), "ocu_name": p.get("ocu_name"),
        "task_code": p.get("task_code"), "task_name": p.get("task_name"),
        "competency_blocks": p.get("competency_blocks") or [],
    }


def batch_get_tasks(client, collection: str, *, ids: list[str]) -> dict:
    records = client.retrieve(collection_name=collection, ids=list(ids),
                              with_payload=True, with_vectors=False)
    return {"tasks": [_project_task(r) for r in records]}
```

Add schemas (`schemas.py`):

```python
class TaskBatchGetRequest(BaseModel):
    ids: list[str] = Field(min_length=1)

class TaskDetail(BaseModel):
    id: str
    urn: str
    ocs_code: str
    ocs_name: str = ""
    ocu_code: Optional[str] = None
    ocu_name: Optional[str] = None
    task_code: Optional[str] = None
    task_name: Optional[str] = None
    competency_blocks: list[dict] = Field(default_factory=list)

class TasksResponse(BaseModel):
    tasks: list[TaskDetail]
```

Add route (`routes.py`, import `TaskBatchGetRequest`, `TasksResponse`):

```python
@router.post("/tasks/batchGet", response_model=TasksResponse)
async def batch_get_tasks(req: TaskBatchGetRequest, request: Request):
    app = request.app
    return await run_in_threadpool(
        service.batch_get_tasks, app.state.client,
        app.state.settings.qdrant_collection, ids=req.ids)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /s/jd-ocs-indexer && uv run pytest tests/test_task_batch_get.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /s/jd-ocs-indexer && git add src/jd_ocs_indexer/api/service.py src/jd_ocs_indexer/api/schemas.py src/jd_ocs_indexer/api/routes.py tests/test_task_batch_get.py
git commit -m "feat(api): POST /tasks/batchGet — task details with competency_blocks"
```

---

### Task 6: `POST /occupations/search` — occupation search (raw score)

**Files:**
- Modify: `service.py` (add `search_occupations`), `schemas.py` (add `SearchRequest` if removed, `OccupationHit`, `OccupationSearchResponse`), `routes.py`
- Test: `tests/test_occupation_search.py`

**Interfaces:**
- Consumes: `search_mod.hybrid_search` (existing), `embedder.embed_query`, `urn.occupation_urn`, `_resolve_ocs_name`.
- Produces: `service.search_occupations(client, embedder, collection, *, query, top_k=10) -> dict`. Response `OccupationSearchResponse{hits:list[OccupationHit]}` where `OccupationHit{ocs_code, urn, ocs_name, job_description, ocs_level, score}`. **raw score only**.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_occupation_search.py
from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint, StubEmbedder

def test_search_occupations_projects_hits_with_raw_score():
    hit = FakePoint(payload={"chunk_level": "profile", "ocs_code": "OC1",
                             "ocs_name": {"occupation_name": "資料分析師"},
                             "job_description": "負責資料分析", "ocs_level": 4}, score=0.83)
    fake = FakeQdrant(query_points=[hit])
    out = service.search_occupations(fake, StubEmbedder(), "ocs_v3", query="資料", top_k=5)
    h = out["hits"][0]
    assert h["ocs_code"] == "OC1" and h["urn"] == "ocs:OC1"
    assert h["ocs_name"] == "資料分析師" and h["job_description"] == "負責資料分析"
    assert h["ocs_level"] == 4 and h["score"] == 0.83
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /s/jd-ocs-indexer && uv run pytest tests/test_occupation_search.py -q`
Expected: FAIL — `... has no attribute 'search_occupations'`

- [ ] **Step 3: Write minimal implementation**

Add to `service.py`:

```python
def search_occupations(client, embedder, collection: str, *, query: str, top_k: int = 10) -> dict:
    vec = embedder.embed_query(query)
    hits = search_mod.hybrid_search(
        client, collection, vec.dense,
        vec.sparse.indices if vec.sparse else [],
        vec.sparse.values if vec.sparse else [],
        level="profile", ocs_code=None, is_current=None, limit=top_k)
    out = []
    for h in hits:
        p = h.payload or {}
        oc = p.get("ocs_code", "")
        out.append({"ocs_code": oc, "urn": urn.occupation_urn(oc),
                    "ocs_name": _resolve_ocs_name(p),
                    "job_description": p.get("job_description") or "",
                    "ocs_level": p.get("ocs_level"), "score": h.score})
    return {"hits": out}
```

Add schemas (`schemas.py`):

```python
class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(10, ge=1, le=50)

class OccupationHit(BaseModel):
    ocs_code: str
    urn: str
    ocs_name: str = ""
    job_description: str = ""
    ocs_level: Optional[int] = None
    score: Optional[float] = None

class OccupationSearchResponse(BaseModel):
    hits: list[OccupationHit]
```

Add route (`routes.py`, import `SearchRequest`, `OccupationSearchResponse`; mirror old `/search` threadpool+embed_lock pattern):

```python
@router.post("/occupations/search", response_model=OccupationSearchResponse)
async def search_occupations(req: SearchRequest, request: Request):
    app = request.app
    def _run():
        with app.state.embed_lock:
            return service.search_occupations(
                app.state.client, app.state.embedder,
                app.state.settings.qdrant_collection, query=req.query, top_k=req.top_k)
    return await run_in_threadpool(_run)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /s/jd-ocs-indexer && uv run pytest tests/test_occupation_search.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /s/jd-ocs-indexer && git add src/jd_ocs_indexer/api/service.py src/jd_ocs_indexer/api/schemas.py src/jd_ocs_indexer/api/routes.py tests/test_occupation_search.py
git commit -m "feat(api): POST /occupations/search — occupation hits with raw score"
```

---

### Task 7: `POST /tasks/search` — task search (identity only)

**Files:**
- Modify: `service.py` (add `search_tasks`), `schemas.py` (add `TaskHit`, `TaskSearchResponse`), `routes.py`
- Test: `tests/test_task_search.py`

**Interfaces:**
- Consumes: `search_mod.hybrid_search`, `urn.task_urn`. Reuses `SearchRequest`.
- Produces: `service.search_tasks(client, embedder, collection, *, query, top_k=10) -> dict`. Response `TaskSearchResponse{hits:list[TaskHit]}` where `TaskHit{ocs_code, ocs_name, ocu_code, ocu_name, task_code, task_name, urn, score}`. **identity only — no competency_blocks**.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_task_search.py
from jd_ocs_indexer.api import service
from tests.conftest import FakeQdrant, FakePoint, StubEmbedder

def test_search_tasks_returns_identity_only():
    hit = FakePoint(payload={"chunk_level": "task", "ocs_code": "OC1", "ocs_name": "JT",
                             "ocu_code": "U1", "ocu_name": "單元一",
                             "task_code": "T1.1", "task_name": "任務一",
                             "competency_blocks": [{"knowledge": [{"code": "K01", "name": "k"}]}]}, score=0.7)
    out = service.search_tasks(FakeQdrant(query_points=[hit]), StubEmbedder(), "c", query="任務")
    h = out["hits"][0]
    assert h["task_code"] == "T1.1" and h["urn"] == "ocs:OC1:T:T1.1" and h["score"] == 0.7
    assert h["ocu_code"] == "U1" and h["ocs_name"] == "JT"
    assert "competency_blocks" not in h   # identity only
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /s/jd-ocs-indexer && uv run pytest tests/test_task_search.py -q`
Expected: FAIL — `... has no attribute 'search_tasks'`

- [ ] **Step 3: Write minimal implementation**

Add to `service.py`:

```python
def search_tasks(client, embedder, collection: str, *, query: str, top_k: int = 10) -> dict:
    vec = embedder.embed_query(query)
    hits = search_mod.hybrid_search(
        client, collection, vec.dense,
        vec.sparse.indices if vec.sparse else [],
        vec.sparse.values if vec.sparse else [],
        level="task", ocs_code=None, is_current=None, limit=top_k)
    out = []
    for h in hits:
        p = h.payload or {}
        oc = p.get("ocs_code", "")
        out.append({"ocs_code": oc, "ocs_name": p.get("ocs_name") or "",
                    "ocu_code": p.get("ocu_code"), "ocu_name": p.get("ocu_name"),
                    "task_code": p.get("task_code"), "task_name": p.get("task_name"),
                    "urn": urn.task_urn(oc, p.get("task_code") or ""), "score": h.score})
    return {"hits": out}
```

Add schemas (`schemas.py`):

```python
class TaskHit(BaseModel):
    ocs_code: str
    ocs_name: str = ""
    ocu_code: Optional[str] = None
    ocu_name: Optional[str] = None
    task_code: Optional[str] = None
    task_name: Optional[str] = None
    urn: str
    score: Optional[float] = None

class TaskSearchResponse(BaseModel):
    hits: list[TaskHit]
```

Add route (`routes.py`, import `TaskSearchResponse`):

```python
@router.post("/tasks/search", response_model=TaskSearchResponse)
async def search_tasks(req: SearchRequest, request: Request):
    app = request.app
    def _run():
        with app.state.embed_lock:
            return service.search_tasks(
                app.state.client, app.state.embedder,
                app.state.settings.qdrant_collection, query=req.query, top_k=req.top_k)
    return await run_in_threadpool(_run)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /s/jd-ocs-indexer && uv run pytest tests/test_task_search.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /s/jd-ocs-indexer && git add src/jd_ocs_indexer/api/service.py src/jd_ocs_indexer/api/schemas.py src/jd_ocs_indexer/api/routes.py tests/test_task_search.py
git commit -m "feat(api): POST /tasks/search — task hits (identity only)"
```

---

### Task 8: `POST /tasks/findSimilar` — dedup candidate pairs (dense, auto-tier)

**Files:**
- Modify: `service.py` (add `_pairwise_candidates` pure fn + `find_similar_tasks`), `schemas.py` (add `FindSimilarRequest`, `SimilarPair`, `FindSimilarResponse`), `routes.py`
- Test: `tests/test_find_similar.py`

**Interfaces:**
- Consumes: `urn.task_urn`, numpy.
- Produces: `service._pairwise_candidates(tasks, threshold) -> list[dict]` (pure; `tasks` = list of `{id,ocs_code,task_code,task_name,vector}`; returns undirected pairs `{a,b,score}` with `a/b={urn,ocs_code,task_code,task_name}`, `score>=threshold`, `a` index < `b` index, self excluded). `service.find_similar_tasks(client, collection, *, ocs_codes, score_threshold=0.85) -> dict` scrolls task points **with vectors** for the ocs_codes, calls the pure fn. Response `FindSimilarResponse{candidates:list[SimilarPair]}`.

**Note:** dense vectors only (not hybrid) — semantic dup detection. Brute-force pairwise cosine is fine for the small selected-OCS set (tens–hundreds of tasks).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_find_similar.py
from jd_ocs_indexer.api import service

def _t(i, code, name, vec):
    return {"id": i, "ocs_code": "OC%s" % i[-1], "task_code": code, "task_name": name, "vector": vec}

def test_pairwise_candidates_above_threshold_only():
    a = _t("idA", "T1.1", "撰寫測試報告", [1.0, 0.0])
    b = _t("idB", "T2.2", "編寫測試報告書", [0.99, 0.14])   # ~cos 0.99 with a
    c = _t("idC", "T3.3", "完全不同", [0.0, 1.0])           # ~cos 0.0 with a
    pairs = service._pairwise_candidates([a, b, c], threshold=0.85)
    assert len(pairs) == 1
    p = pairs[0]
    assert {p["a"]["task_code"], p["b"]["task_code"]} == {"T1.1", "T2.2"}
    assert p["a"]["urn"].startswith("ocs:") and p["score"] >= 0.85

def test_pairwise_excludes_self_and_dedups_direction():
    a = _t("idA", "T1.1", "x", [1.0, 0.0])
    b = _t("idB", "T2.2", "y", [1.0, 0.0])   # identical -> cos 1.0
    pairs = service._pairwise_candidates([a, b], threshold=0.85)
    assert len(pairs) == 1   # one undirected pair, no self-pairs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /s/jd-ocs-indexer && uv run pytest tests/test_find_similar.py -q`
Expected: FAIL — `... has no attribute '_pairwise_candidates'`

- [ ] **Step 3: Write minimal implementation**

Add to `service.py` (top: `import numpy as np`):

```python
def _pairwise_candidates(tasks: list[dict], threshold: float) -> list[dict]:
    """Brute-force cosine over task vectors → undirected candidate pairs >= threshold.
    `tasks`: [{id, ocs_code, task_code, task_name, vector}]. Small set (selected OCS)."""
    if len(tasks) < 2:
        return []
    mat = np.asarray([t["vector"] for t in tasks], dtype=float)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit = mat / norms
    sim = unit @ unit.T
    out: list[dict] = []
    n = len(tasks)
    for i in range(n):
        for j in range(i + 1, n):
            score = float(sim[i, j])
            if score >= threshold:
                out.append({
                    "a": {"urn": urn.task_urn(tasks[i]["ocs_code"], tasks[i]["task_code"]),
                          "ocs_code": tasks[i]["ocs_code"], "task_code": tasks[i]["task_code"],
                          "task_name": tasks[i]["task_name"]},
                    "b": {"urn": urn.task_urn(tasks[j]["ocs_code"], tasks[j]["task_code"]),
                          "ocs_code": tasks[j]["ocs_code"], "task_code": tasks[j]["task_code"],
                          "task_name": tasks[j]["task_name"]},
                    "score": round(score, 4)})
    return out


def find_similar_tasks(client, collection: str, *, ocs_codes: list[str],
                       score_threshold: float = 0.85) -> dict:
    flt = models.Filter(must=[
        models.FieldCondition(key="chunk_level", match=models.MatchValue(value="task")),
        models.FieldCondition(key="ocs_code", match=models.MatchAny(any=list(ocs_codes))),
    ])
    tasks: list[dict] = []
    offset = None
    while True:
        records, offset = client.scroll(
            collection_name=collection, scroll_filter=flt,
            with_payload=True, with_vectors=True, limit=256, offset=offset)
        for r in records:
            p = r.payload or {}
            vec = r.vector
            if isinstance(vec, dict):           # named vectors → take dense
                vec = vec.get("dense") or next(iter(vec.values()), None)
            if vec is None:
                continue
            tasks.append({"id": str(getattr(r, "id", "")), "ocs_code": p.get("ocs_code", ""),
                          "task_code": p.get("task_code") or "", "task_name": p.get("task_name") or "",
                          "vector": vec})
        if offset is None:
            break
    return {"candidates": _pairwise_candidates(tasks, score_threshold)}
```

Add schemas (`schemas.py`):

```python
class FindSimilarRequest(BaseModel):
    ocs_codes: list[str] = Field(min_length=1)
    score_threshold: float = Field(0.85, ge=0.0, le=1.0)

class SimilarTaskRef(BaseModel):
    urn: str
    ocs_code: str
    task_code: str
    task_name: str

class SimilarPair(BaseModel):
    a: SimilarTaskRef
    b: SimilarTaskRef
    score: float

class FindSimilarResponse(BaseModel):
    candidates: list[SimilarPair]
```

Add route (`routes.py`, import `FindSimilarRequest`, `FindSimilarResponse`):

```python
@router.post("/tasks/findSimilar", response_model=FindSimilarResponse)
async def find_similar_tasks(req: FindSimilarRequest, request: Request):
    app = request.app
    return await run_in_threadpool(
        service.find_similar_tasks, app.state.client,
        app.state.settings.qdrant_collection,
        ocs_codes=req.ocs_codes, score_threshold=req.score_threshold)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /s/jd-ocs-indexer && uv run pytest tests/test_find_similar.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /s/jd-ocs-indexer && git add src/jd_ocs_indexer/api/service.py src/jd_ocs_indexer/api/schemas.py src/jd_ocs_indexer/api/routes.py tests/test_find_similar.py
git commit -m "feat(api): POST /tasks/findSimilar — dense dedup candidate pairs"
```

---

### Task 9: Remove old API (functions, schemas, routes, tests) + full green

**Files:**
- Modify: `service.py` (delete old `search`, `build_task_pool`, `get_pairs`, `get_profile`, `retrieve_tasks`, `_project_hit`, `_project_task_detail`, `_zip_pairs`, and the old `Pair`-pool helpers no longer referenced — keep `get_stats`, `healthcheck`, `_scroll_all`, `_scroll_records`), `schemas.py` (delete old `Hit`, `SearchResponse`, `SearchFilters`, `TaskPoolRequest/Task/Unit/OcsGroup/TaskPoolResponse`, `PairsResponse`, `Pair`, `ProfileMetaResponse`, `TaskByIdRequest`, `TaskDetail`(old)/`TasksResponse`(old) — replace with the new ones from Tasks 1–8), `routes.py` (delete old routes: `/search`, `/task-pool`, `/tasks/by-id`, `/profile/{ocs_code}/pairs`, `/profile/{ocs_code}`)
- Delete: `tests/test_service_search.py`, `tests/test_service_task_pool.py`, `tests/test_service_pairs.py`, `tests/test_service_profile.py`, `tests/test_service_retrieve.py`, `tests/test_routes.py`, `tests/test_schemas.py`

**Interfaces:** none new — this task only removes superseded code so the suite reflects the new surface.

- [ ] **Step 1: Delete superseded test files**

```bash
cd /s/jd-ocs-indexer && git rm tests/test_service_search.py tests/test_service_task_pool.py tests/test_service_pairs.py tests/test_service_profile.py tests/test_service_retrieve.py tests/test_routes.py tests/test_schemas.py
```

- [ ] **Step 2: Run the suite to surface old-symbol references**

Run: `cd /s/jd-ocs-indexer && uv run pytest -q`
Expected: PASS for all NEW tests; if any import error references a deleted schema/function, it points at leftover old code to remove in Step 3. (`tests/test_service_stats_health.py` and the ingestion tests must still pass.)

- [ ] **Step 3: Remove old functions/schemas/routes**

In `service.py` delete: `search`, `_project_hit`, `build_task_pool`, `get_pairs`, `_zip_pairs`, `get_profile`, `retrieve_tasks`, `_project_task_detail`. Keep: `get_stats`, `healthcheck`, `_scroll_all`, `_scroll_records`, and all new functions from Tasks 2–8.

In `schemas.py` delete the old models listed under **Files** above; keep `HealthResponse`, `StatsResponse`, `CodeName`, and all new models.

In `routes.py` delete the old route handlers (`post_search`, `post_task_pool`, `post_tasks_by_id`, `get_profile_pairs`, `get_profile_meta`) and their imports. Keep `/stats`, `/healthz`, and the new routes.

- [ ] **Step 4: Run full suite — confirm green**

Run: `cd /s/jd-ocs-indexer && uv run pytest -q`
Expected: PASS, no errors/warnings beyond the pre-existing Starlette deprecation warning.

- [ ] **Step 5: Commit**

```bash
cd /s/jd-ocs-indexer && git add -A src/jd_ocs_indexer/api tests/
git commit -m "refactor(api): remove old endpoints/schemas; resource-oriented surface only"
```

---

## Out of Scope (later, cross-repo — do NOT do in this session)

- **Re-ingest** (`uv run jd-ocs-indexer index data/jd-json`) — destructive, shared Qdrant, **requires explicit user authorization**, and must come AFTER the v3 consumer is updated.
- **v3 backend consumers** (`jobintel-ai` repo: `http_client.py`/`models.py`/`header_meta.py`) — must switch to the new endpoints + `CitableItem`/URN shapes.
- **Dedup merge** (v3 `task_dedup.py`: Union-Find clustering + golden-record `MergedTask` with `pref_name` by OCS priority + union competencies). `findSimilar` here only returns candidate pairs.
- **reranker** for occupation search relevance (optional, separate increment).

## Self-Review Notes

- Spec coverage: occupations/{search,detail,competencies,tasks}, tasks/{search,batchGet,findSimilar} all have tasks; provenance URN composed in service from payload (Task 1 helper used in Tasks 2–8); category auto-fill via Task 2; P surfaced in Tasks 3 & 5; raw score in Task 6; identity-only task search in Task 7; dedup candidates in Task 8.
- Type consistency: `urn.*` signatures fixed in Task 1 and reused verbatim; `_profile_point`/`_task_points`/`_resolve_ocs_name` defined in Tasks 2–3 and reused in 4/6/7; `CitableItem`/`SourceRef` shapes consistent across Tasks 1/3.
- No placeholders: every step has runnable test + impl code + exact commands.
