# v3 Consumer → Indexer API v4 Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Switch the v3 consumer (backend `services/knowledge` + graph/REST call sites, and the Next.js frontend) from the old indexer query API to the resource-oriented v4 surface, propagating v4 naming end-to-end and surfacing K/S/O provenance in the UI.

**Architecture:** Re-model the typed `KnowledgeClient` to the v4 endpoints; per-task K/S/O/indicators are derived from an occupation's `/competencies` pool filtered by `source.task_code` (v4 surfaces no Qdrant point ids to feed `batchGet`). Backend tasks (B1–B6) land first, keeping the pytest suite green at every task boundary (new surface added additively, old removed last). Frontend tasks (F1–F2) follow, gated by `tsc --noEmit` + eslint.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, httpx, respx, pytest (asyncio auto); Next.js (non-standard — see `frontend/AGENTS.md`), TypeScript, React, CopilotKit v2.

**Spec:** `docs/superpowers/specs/2026-06-26-api-v4-consumer-migration-design.md`

## Global Constraints

- Backend tests: `cd backend && .venv/Scripts/python -m pytest -q` (single file: append `tests/test_x.py`). pytest.ini sets `asyncio_mode=auto`, `pythonpath=.`, `testpaths=tests`.
- Frontend typecheck: `cd frontend && npx tsc --noEmit` (tsconfig has `noEmit:true`). Lint: `cd frontend && npm run lint`. No unit-test runner exists — `tsc` is the red/green gate.
- Frontend: this is NOT standard Next.js — read the relevant guide under `frontend/node_modules/next/dist/docs/` before writing component code (per `frontend/AGENTS.md`).
- Pydantic models inherit `_Base` (`extra="ignore", populate_by_name=True`) to tolerate API evolution.
- URN scheme (composed by indexer, consumed here): occupation `ocs:{ocs_code}`, unit `ocs:{ocs_code}:U:{ocu_code}`, task `ocs:{ocs_code}:T:{task_code}`, item `ocs:{ocs_code}:{K|S|O|P|A}:{code}`.
- Task identity is `(ocs_code, task_code)` — never a Qdrant point id. Per-task K/S/O comes from `/competencies` filtered on `source.task_code`.
- Out of scope (do NOT build): `/tasks/findSimilar` wiring, dedup clustering/merge, re-ingest, reranker.
- Commits: no `Co-Authored-By` trailer. Branch: `feat/v3`.

## File Structure

**Backend (`backend/app/services/knowledge/`)**
- `models.py` — v4 response models (replaces old). One responsibility: typed indexer responses.
- `base.py` — `KnowledgeClient` Protocol (v4 method set).
- `http_client.py` — `HttpIndexerClient` (v4 endpoints).
- `task_detail.py` — **new** pure helper `task_competencies(pool, task_code)`.

**Backend call sites**
- `app/graph_v3/nodes.py`, `curate_nodes.py`, `deep_nodes.py`, `stubs.py`
- `app/api/routes/ai.py`, `documents.py`
- `app/services/ai/tasks.py`, `app/services/header_meta.py`, `app/services/ocs_doc.py`

**Backend tests** — `tests/conftest_graph.py` (shared `FakeKnowledge`), `test_http_indexer_client.py`, `test_knowledge_models.py`, `test_task_competencies.py` (new), `test_node_task_pool.py`, `test_curate_nodes.py`, `test_deep_five_w2h.py`, `test_ai_extract_tasks.py`, `test_ai_recommend_ks.py`, `test_ai_draft_op.py`, `test_documents_api.py`, `test_ocs_doc.py`.

**Frontend (`frontend/src/`)** — `types/index.ts`, `lib/api.ts`, `lib/ocsDoc.ts`, `components/interview/v3/{TaskCuratePanel,InterruptHandlers,CellFillerPanel,HeaderMetaPanel}.tsx`.

---

### Task B1: v4 knowledge models + client + Protocol + `task_competencies` (additive)

Adds the entire v4 surface alongside the old one. Old models/methods stay until B6, so the suite stays green. `FakeKnowledge` gains v4 methods (keeps old too).

**Files:**
- Modify: `backend/app/services/knowledge/models.py` (append v4 models)
- Modify: `backend/app/services/knowledge/base.py` (append v4 Protocol methods)
- Modify: `backend/app/services/knowledge/http_client.py` (append v4 methods)
- Create: `backend/app/services/knowledge/task_detail.py`
- Modify: `backend/tests/conftest_graph.py` (`FakeKnowledge` gains v4 methods + fields)
- Test: `backend/tests/test_http_indexer_client.py` (append), `backend/tests/test_knowledge_models.py` (append), `backend/tests/test_task_competencies.py` (new)

**Interfaces:**
- Produces (models, all inherit `_Base`): `CodeName{code,name}`, `OcsName{job_category_name?,occupation_name?}`, `SourceRef{ocu_code?,ocu_name?,task_code?,task_name?,competency_level?}`, `CitableItem{id,type,code,name?,text?,ocs_code,ocs_name,sources:list[SourceRef]}`, `OccupationDetail`, `CompetencyPool{ocs_code,knowledge,skills,outputs,indicators,attitudes:list[CitableItem]}`, `TaskRef{task_code,task_name,urn}`, `UnitTasks{ocu_code?,ocu_name?,urn,tasks}`, `OccupationTasks{ocs_code,ocs_name,units}`, `OccupationHit{ocs_code,urn,ocs_name,job_description,ocs_level?,score?}`, `OccupationSearchResponse{hits}`, `TaskHit{ocs_code,ocs_name,ocu_code?,ocu_name?,task_code?,task_name?,urn,score?}`, `TaskSearchResponse{hits}`.
- Produces (client + Protocol): `search_occupations(query,*,top_k=10)->OccupationSearchResponse`, `search_tasks(query,*,top_k=10)->TaskSearchResponse`, `occupation(ocs_code)->OccupationDetail`, `competencies(ocs_code)->CompetencyPool`, `occupation_tasks(ocs_code)->OccupationTasks`.
- Produces (helper): `task_competencies(pool:CompetencyPool, task_code:str)->dict` with keys `knowledge`/`skills`/`outputs` = `list[{code,name}]`, `indicators` = `list[{code,text}]`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_task_competencies.py`:
```python
from app.services.knowledge.models import CitableItem, CompetencyPool, SourceRef
from app.services.knowledge.task_detail import task_competencies


def _item(type_, code, *, name=None, text=None, task_codes=()):
    return CitableItem(id=f"ocs:OC1:{type_}:{code}", type=type_, code=code, name=name,
                       text=text, ocs_code="OC1", ocs_name="JT",
                       sources=[SourceRef(task_code=tc) for tc in task_codes])


def test_task_competencies_filters_by_task_code():
    pool = CompetencyPool(
        ocs_code="OC1",
        knowledge=[_item("K", "K01", name="k1", task_codes=["T1.1", "T1.2"]),
                   _item("K", "K02", name="k2", task_codes=["T1.2"])],
        skills=[_item("S", "S01", name="s1", task_codes=["T1.1"])],
        outputs=[_item("O", "O01", name="o1", task_codes=["T1.1"])],
        indicators=[_item("P", "P01", text="p text", task_codes=["T1.1"])])
    out = task_competencies(pool, "T1.1")
    assert out["knowledge"] == [{"code": "K01", "name": "k1"}]
    assert out["skills"] == [{"code": "S01", "name": "s1"}]
    assert out["outputs"] == [{"code": "O01", "name": "o1"}]
    assert out["indicators"] == [{"code": "P01", "text": "p text"}]


def test_task_competencies_unknown_task_code_is_empty():
    pool = CompetencyPool(ocs_code="OC1",
                          knowledge=[_item("K", "K01", name="k1", task_codes=["T1.1"])])
    assert task_competencies(pool, "T9.9") == {
        "knowledge": [], "skills": [], "outputs": [], "indicators": []}
```

Append to `backend/tests/test_knowledge_models.py`:
```python
def test_competency_pool_parses_citable_items():
    from app.services.knowledge.models import CompetencyPool
    p = CompetencyPool.model_validate({
        "ocs_code": "OC1",
        "knowledge": [{"id": "ocs:OC1:K:K01", "type": "K", "code": "K01", "name": "k1",
                       "ocs_code": "OC1", "ocs_name": "JT",
                       "sources": [{"task_code": "T1.1", "competency_level": 3}]}],
        "skills": [], "outputs": [], "indicators": [], "attitudes": [], "extra": "ok"})
    assert p.knowledge[0].code == "K01"
    assert p.knowledge[0].sources[0].task_code == "T1.1"


def test_occupation_detail_parses_nested_ocs_name():
    from app.services.knowledge.models import OccupationDetail
    d = OccupationDetail.model_validate({
        "ocs_code": "OC1", "urn": "ocs:OC1",
        "ocs_name": {"job_category_name": None, "occupation_name": "資料分析師"},
        "job_categories": [{"code": "JC1", "name": "資訊類"}],
        "occupations": [], "industries": [], "attitudes": [],
        "job_description": "x", "ocs_level": 4, "prerequisites": ["a"], "supplements": []})
    assert d.ocs_name.occupation_name == "資料分析師" and d.ocs_level == 4
    assert d.job_categories[0].code == "JC1" and d.prerequisites == ["a"]
```

Append to `backend/tests/test_http_indexer_client.py`:
```python
@respx.mock
async def test_search_occupations_calls_endpoint(client):
    route = respx.post(f"{BASE}/occupations/search").mock(return_value=httpx.Response(
        200, json={"hits": [{"ocs_code": "OC1", "urn": "ocs:OC1", "ocs_name": "JT",
                             "job_description": "d", "ocs_level": 4, "score": 0.8}]}))
    r = await client.search_occupations("hello", top_k=5)
    assert route.called and r.hits[0].ocs_code == "OC1" and r.hits[0].score == 0.8


@respx.mock
async def test_occupation_uses_path_param(client):
    respx.get(f"{BASE}/occupations/OC1").mock(return_value=httpx.Response(
        200, json={"ocs_code": "OC1", "urn": "ocs:OC1",
                   "ocs_name": {"occupation_name": "JT"}, "job_categories": [],
                   "occupations": [], "industries": [], "attitudes": [],
                   "job_description": "", "prerequisites": [], "supplements": []}))
    r = await client.occupation("OC1")
    assert r.ocs_name.occupation_name == "JT"


@respx.mock
async def test_competencies_uses_path(client):
    respx.get(f"{BASE}/occupations/OC1/competencies").mock(return_value=httpx.Response(
        200, json={"ocs_code": "OC1", "knowledge": [], "skills": [], "outputs": [],
                   "indicators": [], "attitudes": []}))
    r = await client.competencies("OC1")
    assert r.ocs_code == "OC1"


@respx.mock
async def test_occupation_tasks_uses_path(client):
    respx.get(f"{BASE}/occupations/OC1/tasks").mock(return_value=httpx.Response(
        200, json={"ocs_code": "OC1", "ocs_name": "JT", "units": [
            {"ocu_code": "U1", "ocu_name": "單元一", "urn": "ocs:OC1:U:U1",
             "tasks": [{"task_code": "T1.1", "task_name": "任務一", "urn": "ocs:OC1:T:T1.1"}]}]}))
    r = await client.occupation_tasks("OC1")
    assert r.units[0].tasks[0].task_code == "T1.1"
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest -q tests/test_task_competencies.py tests/test_knowledge_models.py tests/test_http_indexer_client.py`
Expected: FAIL — `ModuleNotFoundError: ... task_detail` and `ImportError: cannot import name 'CompetencyPool'`.

- [ ] **Step 3: Add the v4 models**

Append to `backend/app/services/knowledge/models.py`:
```python
class CodeName(_Base):
    code: str = ""
    name: str = ""


class OcsName(_Base):
    job_category_name: str | None = None
    occupation_name: str | None = None


class SourceRef(_Base):
    ocu_code: str | None = None
    ocu_name: str | None = None
    task_code: str | None = None
    task_name: str | None = None
    competency_level: int | None = None


class CitableItem(_Base):
    id: str = ""
    type: str = ""
    code: str = ""
    name: str | None = None
    text: str | None = None
    ocs_code: str = ""
    ocs_name: str = ""
    sources: list[SourceRef] = Field(default_factory=list)


class OccupationDetail(_Base):
    ocs_code: str = ""
    urn: str = ""
    ocs_name: OcsName = Field(default_factory=OcsName)
    job_categories: list[CodeName] = Field(default_factory=list)
    occupations: list[CodeName] = Field(default_factory=list)
    industries: list[CodeName] = Field(default_factory=list)
    job_description: str = ""
    ocs_level: int | None = None
    attitudes: list[CodeName] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)


class CompetencyPool(_Base):
    ocs_code: str = ""
    knowledge: list[CitableItem] = Field(default_factory=list)
    skills: list[CitableItem] = Field(default_factory=list)
    outputs: list[CitableItem] = Field(default_factory=list)
    indicators: list[CitableItem] = Field(default_factory=list)
    attitudes: list[CitableItem] = Field(default_factory=list)


class TaskRef(_Base):
    task_code: str = ""
    task_name: str = ""
    urn: str = ""


class UnitTasks(_Base):
    ocu_code: str | None = None
    ocu_name: str | None = None
    urn: str = ""
    tasks: list[TaskRef] = Field(default_factory=list)


class OccupationTasks(_Base):
    ocs_code: str = ""
    ocs_name: str = ""
    units: list[UnitTasks] = Field(default_factory=list)


class OccupationHit(_Base):
    ocs_code: str = ""
    urn: str = ""
    ocs_name: str = ""
    job_description: str = ""
    ocs_level: int | None = None
    score: float | None = None


class OccupationSearchResponse(_Base):
    hits: list[OccupationHit] = Field(default_factory=list)


class TaskHit(_Base):
    ocs_code: str = ""
    ocs_name: str = ""
    ocu_code: str | None = None
    ocu_name: str | None = None
    task_code: str | None = None
    task_name: str | None = None
    urn: str = ""
    score: float | None = None


class TaskSearchResponse(_Base):
    hits: list[TaskHit] = Field(default_factory=list)
```

Create `backend/app/services/knowledge/task_detail.py`:
```python
"""Derive a single task's K/S/O/indicators from an occupation CompetencyPool by
filtering CitableItems on their source task_code. Replaces the old per-point
tasks_by_id path — the v4 surface exposes no Qdrant point ids to feed batchGet."""
from __future__ import annotations

from app.services.knowledge.models import CompetencyPool


def _matches(item, task_code: str) -> bool:
    return any(s.task_code == task_code for s in item.sources)


def task_competencies(pool: CompetencyPool, task_code: str) -> dict:
    """Per-task slice of the pool. K/S/O → [{code,name}], indicators(P) → [{code,text}]."""
    return {
        "knowledge": [{"code": it.code, "name": it.name or ""}
                      for it in pool.knowledge if _matches(it, task_code)],
        "skills": [{"code": it.code, "name": it.name or ""}
                   for it in pool.skills if _matches(it, task_code)],
        "outputs": [{"code": it.code, "name": it.name or ""}
                    for it in pool.outputs if _matches(it, task_code)],
        "indicators": [{"code": it.code, "text": it.text or ""}
                       for it in pool.indicators if _matches(it, task_code)],
    }
```

- [ ] **Step 4: Add the v4 client methods + Protocol entries**

Append to `backend/app/services/knowledge/http_client.py` (inside `HttpIndexerClient`, and extend the import from `.models`):
```python
    async def search_occupations(self, query: str, *, top_k: int = 10) -> OccupationSearchResponse:
        resp = await self._client.post("/occupations/search", json={"query": query, "top_k": top_k})
        resp.raise_for_status()
        return OccupationSearchResponse.model_validate(resp.json())

    async def search_tasks(self, query: str, *, top_k: int = 10) -> TaskSearchResponse:
        resp = await self._client.post("/tasks/search", json={"query": query, "top_k": top_k})
        resp.raise_for_status()
        return TaskSearchResponse.model_validate(resp.json())

    async def occupation(self, ocs_code: str) -> OccupationDetail:
        resp = await self._client.get(f"/occupations/{ocs_code}")
        resp.raise_for_status()
        return OccupationDetail.model_validate(resp.json())

    async def competencies(self, ocs_code: str) -> CompetencyPool:
        resp = await self._client.get(f"/occupations/{ocs_code}/competencies")
        resp.raise_for_status()
        return CompetencyPool.model_validate(resp.json())

    async def occupation_tasks(self, ocs_code: str) -> OccupationTasks:
        resp = await self._client.get(f"/occupations/{ocs_code}/tasks")
        resp.raise_for_status()
        return OccupationTasks.model_validate(resp.json())
```
Update the `from app.services.knowledge.models import (...)` block in `http_client.py` to also import `CompetencyPool, OccupationDetail, OccupationSearchResponse, OccupationTasks, TaskSearchResponse`.

Append to `backend/app/services/knowledge/base.py` (inside the `KnowledgeClient` Protocol, and extend its import block likewise):
```python
    async def search_occupations(self, query: str, *, top_k: int = 10) -> OccupationSearchResponse: ...

    async def search_tasks(self, query: str, *, top_k: int = 10) -> TaskSearchResponse: ...

    async def occupation(self, ocs_code: str) -> OccupationDetail: ...

    async def competencies(self, ocs_code: str) -> CompetencyPool: ...

    async def occupation_tasks(self, ocs_code: str) -> OccupationTasks: ...
```

- [ ] **Step 5: Give `FakeKnowledge` the v4 methods (keep old)**

In `backend/tests/conftest_graph.py`, extend the top import to include
`CompetencyPool, OccupationSearchResponse, OccupationTasks`, then add fields in `__init__`
(`self._competencies=None; self._occ_tasks=None; self._occ_search=None`) and these methods to `FakeKnowledge`:
```python
    async def search_occupations(self, query, *, top_k=10):
        self.calls.append(("search_occupations", query))
        return self._occ_search or OccupationSearchResponse(hits=[])

    async def occupation_tasks(self, ocs_code):
        self.calls.append(("occupation_tasks", ocs_code))
        return self._occ_tasks or OccupationTasks(ocs_code=ocs_code)

    async def competencies(self, ocs_code):
        self.calls.append(("competencies", ocs_code))
        return self._competencies or CompetencyPool(ocs_code=ocs_code)
```

- [ ] **Step 6: Run the new tests + full suite — confirm green**

Run: `cd backend && .venv/Scripts/python -m pytest -q`
Expected: PASS (new v4 tests pass; old tests still pass — old surface untouched).

- [ ] **Step 7: Commit**

```bash
cd backend && git add app/services/knowledge tests/test_task_competencies.py tests/test_knowledge_models.py tests/test_http_indexer_client.py tests/conftest_graph.py
git commit -m "feat(be): add v4 indexer client surface (models/client/protocol + task_competencies)"
```

---

### Task B2: Switch `nodes.py` (pick_profile, build_task_pool) to v4

`pick_profile` → `search_occupations`; `build_task_pool` calls `occupation_tasks` per code and merges. Drop `activity_examples`. `indexer_ref` becomes `{ocs_code, task_code}`.

**Files:**
- Modify: `backend/app/graph_v3/nodes.py`
- Modify: `backend/app/graph_v3/stubs.py` (`StubKnowledge.search_occupations`/`occupation_tasks`)
- Test: `backend/tests/test_node_task_pool.py`

**Interfaces:**
- Consumes: `knowledge.search_occupations`, `knowledge.occupation_tasks`, models `OccupationTasks`/`OccupationSearchResponse`.
- Produces: `_pool_to_tasks(occ_tasks_list: list[OccupationTasks]) -> list[dict]` where each dict is `{task_name, source:"catalog", indexer_ref:{ocs_code,task_code}, ocu_code, ocu_name}` (was `unit_id/unit_title/task_id/activity_examples`).

- [ ] **Step 1: Rewrite the tests**

Replace `backend/tests/test_node_task_pool.py` body with (imports + three tests):
```python
import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.nodes import build_task_pool, _pool_to_tasks
from app.graph_v3.deps import Deps
from app.services.knowledge.models import OccupationTasks, UnitTasks, TaskRef
from tests.conftest_graph import FakeKnowledge, SpyPersist


def _graph():
    g = StateGraph(InterviewState)
    g.add_node("build_task_pool", build_task_pool)
    g.add_edge(START, "build_task_pool")
    g.add_edge("build_task_pool", END)
    return g.compile(checkpointer=MemorySaver())


def _occ(ocs, *tasks):
    return OccupationTasks(ocs_code=ocs, ocs_name="工程師", units=[
        UnitTasks(ocu_code="U1", ocu_name="巡檢類", urn=f"ocs:{ocs}:U:U1",
                  tasks=[TaskRef(task_code=tc, task_name=tn, urn=f"ocs:{ocs}:T:{tc}")
                         for tc, tn in tasks])])


@pytest.mark.asyncio
async def test_task_pool_interrupt_then_flush_edited():
    fake = FakeKnowledge()
    fake._occ_tasks = _occ("OC1", ("T1.1", "例行巡檢"))
    spy = SpyPersist()
    graph = _graph()
    s = new_state(job_profile_id="p1", job_title="工程師")
    s["profile"]["selected_ocs_code"] = "OC1"
    s["profile"]["selected_ocs_codes"] = ["OC1"]
    cfg = {"configurable": {"thread_id": "t1", "deps": Deps(knowledge=fake, persist=spy)}}

    out = await graph.ainvoke(s, cfg)
    intr = out["__interrupt__"][0].value
    assert intr["kind"] == "edit_tasks"
    assert intr["tasks"][0]["task_name"] == "例行巡檢" and intr["tasks"][0]["source"] == "catalog"
    assert intr["tasks"][0]["indexer_ref"] == {"ocs_code": "OC1", "task_code": "T1.1"}

    edited = [{"task_name": "例行巡檢", "source": "catalog",
               "indexer_ref": {"ocs_code": "OC1", "task_code": "T1.1"}},
              {"task_name": "公司自訂任務", "source": "company"}]
    out2 = await graph.ainvoke(Command(resume={"tasks": edited}), cfg)
    assert [t["task_name"] for t in out2["tasks"]] == ["例行巡檢", "公司自訂任務"]
    assert out2["current_step"] == "deep"


@pytest.mark.asyncio
async def test_task_pool_orders_tasks_by_ocs_priority():
    # FakeKnowledge returns the same _occ_tasks per call; use a per-code dict instead.
    by_code = {"OC1": _occ("OC1", ("T1", "巡檢A")), "OC2": _occ("OC2", ("T1", "保養B"))}

    class MultiFake(FakeKnowledge):
        async def occupation_tasks(self, ocs_code):
            self.calls.append(("occupation_tasks", ocs_code))
            return by_code[ocs_code]

    fake = MultiFake()
    graph = _graph()
    s = new_state(job_profile_id="p1", job_title="工程師")
    s["profile"]["selected_ocs_codes"] = ["OC2", "OC1"]
    cfg = {"configurable": {"thread_id": "tp", "deps": Deps(knowledge=fake, persist=SpyPersist())}}

    out = await graph.ainvoke(s, cfg)
    intr = out["__interrupt__"][0].value
    assert ("occupation_tasks", "OC2") in fake.calls and ("occupation_tasks", "OC1") in fake.calls
    assert [t["task_name"] for t in intr["tasks"]] == ["保養B", "巡檢A"]


def test_pool_tasks_carry_unit_info():
    tasks = _pool_to_tasks([_occ("OC1", ("T1.1", "巡檢"))])
    assert tasks[0]["ocu_code"] == "U1"
    assert tasks[0]["ocu_name"] == "巡檢類"
    assert tasks[0]["indexer_ref"] == {"ocs_code": "OC1", "task_code": "T1.1"}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/Scripts/python -m pytest -q tests/test_node_task_pool.py`
Expected: FAIL — `ImportError: cannot import name 'OccupationTasks'`-style mismatch / `_pool_to_tasks` signature error.

- [ ] **Step 3: Rewrite the production code**

In `backend/app/graph_v3/nodes.py` replace `pick_profile`'s search line and the `_pool_to_tasks`/`build_task_pool` functions:
```python
    res = await deps.knowledge.search_occupations(query, top_k=8)
    candidates = [h.model_dump() for h in res.hits]
```
```python
def _pool_to_tasks(occ_tasks_list) -> list[dict]:
    out = []
    for occ in occ_tasks_list:
        for u in occ.units:
            for t in u.tasks:
                out.append({
                    "task_name": t.task_name,
                    "source": "catalog",
                    "indexer_ref": {"ocs_code": occ.ocs_code, "task_code": t.task_code},
                    "ocu_code": u.ocu_code,
                    "ocu_name": u.ocu_name,
                })
    return out


def _sort_by_priority(tasks: list[dict], codes: list[str]) -> list[dict]:
    """依使用者勾選的 OCS 優先度（codes 順序）穩定排序任務；未知 OCS 排最後。"""
    rank = {c: i for i, c in enumerate(codes)}
    return sorted(
        tasks,
        key=lambda t: rank.get((t.get("indexer_ref") or {}).get("ocs_code"), len(codes)),
    )


@traced_node("build_task_pool")
async def build_task_pool(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    prof = state["profile"]
    codes = prof.get("selected_ocs_codes") or (
        [prof["selected_ocs_code"]] if prof.get("selected_ocs_code") else [])
    occ_list = [await deps.knowledge.occupation_tasks(c) for c in codes]
    proposed = _sort_by_priority(_pool_to_tasks(occ_list), codes)

    edited = interrupt({"kind": "edit_tasks", "tasks": proposed})
    tasks = edited.get("tasks", proposed) if isinstance(edited, dict) else proposed

    return {"tasks": tasks, "current_step": "deep"}
```

In `backend/app/graph_v3/stubs.py` add v4 methods to `StubKnowledge` (keep old for now); extend its model import to include `OccupationHit, OccupationSearchResponse, OccupationTasks, UnitTasks, TaskRef`:
```python
    async def search_occupations(self, query, *, top_k=10) -> OccupationSearchResponse:
        return OccupationSearchResponse(hits=[
            OccupationHit(ocs_code="KRM2421-001v4", urn="ocs:KRM2421-001v4", ocs_name="設備維護工程師"),
            OccupationHit(ocs_code="KRM2422-001v4", urn="ocs:KRM2422-001v4", ocs_name="生產線技術員"),
        ])

    async def occupation_tasks(self, ocs_code) -> OccupationTasks:
        return OccupationTasks(ocs_code=ocs_code, ocs_name="設備維護工程師", units=[
            UnitTasks(ocu_code="U1", ocu_name="預防保養", urn=f"ocs:{ocs_code}:U:U1", tasks=[
                TaskRef(task_code="T1.1", task_name="例行設備巡檢", urn=f"ocs:{ocs_code}:T:T1.1"),
                TaskRef(task_code="T1.2", task_name="保養排程管理", urn=f"ocs:{ocs_code}:T:T1.2"),
            ])])
```

- [ ] **Step 4: Run to verify pass + full suite**

Run: `cd backend && .venv/Scripts/python -m pytest -q tests/test_node_task_pool.py && .venv/Scripts/python -m pytest -q`
Expected: PASS (whole suite still green; other call sites still use old methods, which remain).

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/graph_v3/nodes.py app/graph_v3/stubs.py tests/test_node_task_pool.py
git commit -m "feat(be): nodes pick_profile/build_task_pool → v4 (search_occupations + occupation_tasks)"
```

---

### Task B3: Switch `curate_nodes.py` + `deep_nodes.py` to v4

`fetch_ksa_pool` → `competencies`; K/S/A items gain `sources` (task_codes). `deep_nodes._prefill_from_catalog` → `competencies` + `task_competencies` for outputs.

**Files:**
- Modify: `backend/app/graph_v3/curate_nodes.py`, `backend/app/graph_v3/deep_nodes.py`
- Modify: `backend/app/graph_v3/stubs.py` (`StubKnowledge.competencies`)
- Test: `backend/tests/test_curate_nodes.py`, `backend/tests/test_deep_five_w2h.py`

**Interfaces:**
- Consumes: `knowledge.competencies(ocs)->CompetencyPool`, `task_competencies(pool, task_code)`.
- Produces: `_citables_to_items(items: list[CitableItem]) -> list[dict]` → `[{content, source:"catalog", icap_ref, sources:[task_code…]}]`.

- [ ] **Step 1: Rewrite the curate test for v4 competencies**

In `backend/tests/test_curate_nodes.py`, replace the model import and `test_fetch_ksa_pool_caches_pairs`:
```python
from app.services.knowledge.models import CompetencyPool, CitableItem, SourceRef
```
```python
@pytest.mark.asyncio
async def test_fetch_ksa_pool_from_competencies():
    pool = CompetencyPool(ocs_code="OC1",
        knowledge=[CitableItem(id="ocs:OC1:K:K01", type="K", code="K01", name="PLC",
                               ocs_code="OC1", ocs_name="工程師",
                               sources=[SourceRef(task_code="T1.1")])],
        skills=[CitableItem(id="ocs:OC1:S:S01", type="S", code="S01", name="排障",
                            ocs_code="OC1", ocs_name="工程師", sources=[SourceRef(task_code="T1.1")])],
        attitudes=[CitableItem(id="ocs:OC1:A:A01", type="A", code="A01", name="細心",
                               ocs_code="OC1", ocs_name="工程師", sources=[])])
    fake = FakeKnowledge(); fake._competencies = pool
    s = new_state(job_profile_id="p1", job_title="工程師")
    s["profile"]["selected_ocs_code"] = "OC1"
    cfg = {"configurable": {"thread_id": "t", "deps": Deps(knowledge=fake, persist=SpyPersist())}}
    out = await _one(fetch_ksa_pool).ainvoke(s, cfg)
    assert out["ksa"]["pool"]["knowledge"][0]["content"] == "PLC"
    assert out["ksa"]["pool"]["knowledge"][0]["sources"] == ["T1.1"]
    assert out["ksa"]["pool"]["attitudes"][0]["content"] == "細心"
    assert out["current_step"] == "curate_ks"
```
(The other two curate tests use literal pool dicts and need no change.)

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/Scripts/python -m pytest -q tests/test_curate_nodes.py::test_fetch_ksa_pool_from_competencies`
Expected: FAIL — `AttributeError: 'FakeKnowledge' object has no attribute ...` is satisfied (B1 added it) but `fetch_ksa_pool` still calls `pairs` → returns empty pool, assertion on `sources` fails.

- [ ] **Step 3: Rewrite `fetch_ksa_pool` + deep prefill**

In `backend/app/graph_v3/curate_nodes.py`, replace `_pairs_to_items` and the `fetch_ksa_pool` body:
```python
def _citables_to_items(items) -> list[dict]:
    return [{"content": it.name, "source": "catalog", "icap_ref": it.code or None,
             "sources": [s.task_code for s in it.sources if s.task_code]}
            for it in items if it.name]


@traced_node("fetch_ksa_pool")
async def fetch_ksa_pool(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    ocs = state["profile"]["selected_ocs_code"]
    pool = {"knowledge": [], "skills": [], "attitudes": []}
    if ocs:
        try:
            comp = await deps.knowledge.competencies(ocs)
            pool = {"knowledge": _citables_to_items(comp.knowledge),
                    "skills": _citables_to_items(comp.skills),
                    "attitudes": _citables_to_items(comp.attitudes)}
        except Exception as exc:  # noqa: BLE001
            logger.warning("fetch_ksa_pool: competencies() failed, empty pool: %s", exc)
    return {"ksa": {**state["ksa"], "pool": pool}, "current_step": "curate_ks"}
```

In `backend/app/graph_v3/deep_nodes.py`, replace `_prefill_from_catalog`:
```python
async def _prefill_from_catalog(task: dict, deps) -> dict:
    """catalog outputs 當 just-in-time prefill（best-effort）。v4：以 (ocs_code, task_code)
    從 competencies pool 過濾該任務的 outputs。indexer 失敗就跳過，由 5W2H 問人。"""
    ref = task.get("indexer_ref") or {}
    ocs_code, task_code = ref.get("ocs_code"), ref.get("task_code")
    if not ocs_code or not task_code or deps.knowledge is None or task.get("outputs"):
        return task
    try:
        pool = await deps.knowledge.competencies(ocs_code)
    except Exception as exc:  # noqa: BLE001
        logger.warning("five_w2h prefill skipped (competencies failed): %s", exc)
        return task
    from app.services.knowledge.task_detail import task_competencies
    detail = task_competencies(pool, task_code)
    if not task.get("outputs") and detail["outputs"]:
        task["outputs"] = [o["name"] for o in detail["outputs"] if o["name"]]
    return task
```

In `backend/app/graph_v3/stubs.py`, add `StubKnowledge.competencies` (extend its import with `CitableItem, CompetencyPool, SourceRef`):
```python
    async def competencies(self, ocs_code) -> CompetencyPool:
        return CompetencyPool(ocs_code=ocs_code,
            knowledge=[CitableItem(id=f"ocs:{ocs_code}:K:K01", type="K", code="K01",
                                   name="設備保養原理", ocs_code=ocs_code, ocs_name="設備維護工程師",
                                   sources=[SourceRef(task_code="T1.1")])],
            skills=[CitableItem(id=f"ocs:{ocs_code}:S:S01", type="S", code="S01", name="點檢操作",
                                ocs_code=ocs_code, ocs_name="設備維護工程師", sources=[SourceRef(task_code="T1.1")])],
            attitudes=[CitableItem(id=f"ocs:{ocs_code}:A:A01", type="A", code="A01", name="細心負責",
                                   ocs_code=ocs_code, ocs_name="設備維護工程師", sources=[])])
```

- [ ] **Step 4: Run to verify pass + full suite**

Run: `cd backend && .venv/Scripts/python -m pytest -q tests/test_curate_nodes.py tests/test_deep_five_w2h.py && .venv/Scripts/python -m pytest -q`
Expected: PASS. (If `test_deep_five_w2h.py` stubs `tasks_by_id`/uses `indexer_ref.task_id`, update its stub to set `_competencies` and its task `indexer_ref` to `{ocs_code, task_code}` — read the file first; assertions on prefilled `outputs` stay.)

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/graph_v3/curate_nodes.py app/graph_v3/deep_nodes.py app/graph_v3/stubs.py tests/test_curate_nodes.py tests/test_deep_five_w2h.py
git commit -m "feat(be): curate/deep nodes → v4 competencies (K/S/A sources + per-task outputs)"
```

---

### Task B4: Switch `ai.py` + `services/ai/tasks.py` + `extract_tasks` to v4

Per-task K/S/O via `competencies` + `task_competencies` keyed on `(ocs_code, task_code)` from provenance. extract-tasks candidate id = `task_code`.

**Files:**
- Modify: `backend/app/services/ai/tasks.py` (add `catalog_ref`), `backend/app/api/routes/ai.py`, `backend/app/services/ai/extract_tasks.py` (only if it inspects candidate `id` shape — verify)
- Test: `backend/tests/test_ai_recommend_ks.py`, `backend/tests/test_ai_draft_op.py`, `backend/tests/test_ai_extract_tasks.py`

**Interfaces:**
- Consumes: `knowledge.competencies`, `task_competencies`, `knowledge.occupation_tasks`.
- Produces: `tasks.catalog_ref(task)->{ocs_code,task_code}` (reads `provenance`); `_catalog_ks(knowledge, ref)->(k,s)`; `_catalog_op(knowledge, ref)->(outputs, indicators)`; `_task_candidates(knowledge, ocs_codes)->[{id:task_code, title}]`.

- [ ] **Step 1: Rewrite the extract-tasks test stub + ids (and recommend/draft stubs)**

In `backend/tests/test_ai_extract_tasks.py`, replace the `StubKnowledge`, `_pool()` and id literals so candidates come from `occupation_tasks` and ids are task_codes:
```python
from app.services.knowledge.models import OccupationTasks, UnitTasks, TaskRef


class StubKnowledge:
    """Minimal KnowledgeClient for /ai/extract-tasks: only occupation_tasks is exercised."""
    def __init__(self, occ=None, fail=False):
        self.occ = occ
        self.fail = fail
        self.calls = []

    async def occupation_tasks(self, ocs_code):
        self.calls.append(ocs_code)
        if self.fail:
            raise RuntimeError("indexer down")
        return self.occ or OccupationTasks(ocs_code=ocs_code)


def _occ():
    return OccupationTasks(ocs_code="OC1", ocs_name="JT", units=[
        UnitTasks(ocu_code="U1", ocu_name="U", urn="ocs:OC1:U:U1", tasks=[
            TaskRef(task_code="T1.1", task_name="蒐集標準", urn="ocs:OC1:T:T1.1"),
            TaskRef(task_code="T1.2", task_name="撰寫報告", urn="ocs:OC1:T:T1.2")])])
```
Update each test: `StubKnowledge(_occ())`; `suggested_task_ids`/expected use `"T1.1"`/`"T1.2"` (was `cat-1`/`cat-2`) and an unknown `"T9.9"` is dropped. `test_extract_tasks_indexer_down_returns_empty` uses `StubKnowledge(fail=True)`.

For `test_ai_recommend_ks.py` and `test_ai_draft_op.py`: replace their per-file `StubKnowledge.tasks_by_id` with `competencies(ocs_code)` returning a `CompetencyPool` whose items carry `sources=[SourceRef(task_code=...)]`, and ensure the document fixture task's `provenance` is `{ocs_code, task_code}`. (Read each file first; keep the existing assertions on returned K/S and outputs/indicators.) Example competencies stub:
```python
from app.services.knowledge.models import CitableItem, CompetencyPool, SourceRef

class StubKnowledge:
    def __init__(self, pool=None, fail=False):
        self.pool = pool
        self.fail = fail
    async def competencies(self, ocs_code):
        if self.fail:
            raise RuntimeError("down")
        return self.pool or CompetencyPool(ocs_code=ocs_code)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/Scripts/python -m pytest -q tests/test_ai_extract_tasks.py tests/test_ai_recommend_ks.py tests/test_ai_draft_op.py`
Expected: FAIL — production still calls `task_pool`/`tasks_by_id`.

- [ ] **Step 3: Rewrite the ai adapters**

In `backend/app/services/ai/tasks.py` add (keep `catalog_id` if other code still needs it; B6 removes if unused):
```python
def catalog_ref(task: dict) -> dict:
    """provenance (ocs_code, task_code) for catalog tasks; empty strings for custom."""
    p = task.get("provenance") or {}
    return {"ocs_code": p.get("ocs_code") or "", "task_code": p.get("task_code") or ""}
```

In `backend/app/api/routes/ai.py` replace `_catalog_ks`, `_catalog_op`, `_task_candidates` and their call sites:
```python
from app.services.knowledge.task_detail import task_competencies


async def _catalog_ks(knowledge: KnowledgeClient, ref: dict) -> tuple[list[dict], list[dict]]:
    if not ref.get("ocs_code") or not ref.get("task_code"):
        return [], []
    try:
        pool = await knowledge.competencies(ref["ocs_code"])
    except Exception:
        logger.warning("ai: competencies failed", exc_info=True)
        return [], []
    detail = task_competencies(pool, ref["task_code"])
    return detail["knowledge"], detail["skills"]


async def _catalog_op(knowledge: KnowledgeClient, ref: dict) -> tuple[list[str], list[str]]:
    if not ref.get("ocs_code") or not ref.get("task_code"):
        return [], []
    try:
        pool = await knowledge.competencies(ref["ocs_code"])
    except Exception:
        logger.warning("ai: competencies failed", exc_info=True)
        return [], []
    detail = task_competencies(pool, ref["task_code"])
    return [o["name"] for o in detail["outputs"]], [p["text"] for p in detail["indicators"]]


async def _task_candidates(knowledge: KnowledgeClient, ocs_codes: list[str]) -> list[dict]:
    if not ocs_codes:
        return []
    out = []
    for code in ocs_codes:
        try:
            occ = await knowledge.occupation_tasks(code)
        except Exception:
            logger.warning("ai: occupation_tasks failed", exc_info=True)
            continue
        out += [{"id": t.task_code, "title": t.task_name} for u in occ.units for t in u.tasks]
    return out
```
Update the two call sites: `await _catalog_ks(knowledge, _tasks.catalog_ref(task))` and `await _catalog_op(knowledge, _tasks.catalog_ref(task))`.

Verify `backend/app/services/ai/extract_tasks.py` only echoes candidate `id`s through (it does — it filters LLM-suggested ids against candidate ids); no change needed unless it parses id format.

- [ ] **Step 4: Run to verify pass + full suite**

Run: `cd backend && .venv/Scripts/python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/api/routes/ai.py app/services/ai/tasks.py tests/test_ai_extract_tasks.py tests/test_ai_recommend_ks.py tests/test_ai_draft_op.py
git commit -m "feat(be): /ai/* → v4 (competencies-derived K/S/O, task_code candidate ids)"
```

---

### Task B5: Switch `documents.py` + `header_meta.py` + `ocs_doc.py` to v4

REST routes emit v4 field names; provenance becomes `{ocs_code, task_code, urn}`.

**Files:**
- Modify: `backend/app/api/routes/documents.py`, `backend/app/services/header_meta.py`, `backend/app/services/ocs_doc.py`
- Test: `backend/tests/test_documents_api.py`, `backend/tests/test_ocs_doc.py`

**Interfaces:**
- Consumes: `knowledge.occupation_tasks`, `knowledge.search_occupations`, `knowledge.occupation`, `knowledge.competencies`; `OccupationDetail` (header_meta input).
- Produces REST shapes: task-candidates `{groups:[{ocs_code, ocs_name, units:[{ocu_code, ocu_name, tasks:[{task_code, task_name, urn}]}]}]}`; ocs-search `{hits:[{ocs_code, ocs_name}]}`; ksa-pool items `{code, name, sources:[task_code…]}`; document `provenance:{ocs_code, task_code, urn}`.

- [ ] **Step 1: Update tests for v4 shapes**

In `backend/tests/test_ocs_doc.py`: update any literal `provenance` to `{"ocs_code","task_code","urn"}` and any `indexer_ref`/picked `task_id` → `task_code`; the merge-on-recurate dedup test keys on `(ocs_code, task_code)`. (Read the file; adjust literals + assertions.)

In `backend/tests/test_documents_api.py`: update the indexer stub to implement `occupation_tasks`/`search_occupations`/`occupation`/`competencies`; assert task-candidates groups use `ocs_name`/`ocu_code`/`ocu_name`/`task_code`/`urn`, ocs-search hits use `ocs_name`, ksa-pool items carry `sources`, header-meta `primary.occupation_name` is filled from `ocs_name.occupation_name`. (Read the file; mirror existing assertions with new field names.)

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/Scripts/python -m pytest -q tests/test_documents_api.py tests/test_ocs_doc.py`
Expected: FAIL.

- [ ] **Step 3: Rewrite the routes/services**

`backend/app/api/routes/documents.py`:
- `task_candidates`: build groups from per-code `occupation_tasks`:
```python
    groups = []
    for code in codes:
        try:
            occ = await knowledge.occupation_tasks(code)
        except Exception:
            logger.warning("task-candidates: occupation_tasks(%s) failed", code, exc_info=True)
            raise HTTPException(status_code=502, detail="indexer unavailable")
        groups.append({
            "ocs_code": occ.ocs_code, "ocs_name": occ.ocs_name,
            "units": [{"ocu_code": u.ocu_code, "ocu_name": u.ocu_name,
                       "tasks": [{"task_code": t.task_code, "task_name": t.task_name, "urn": t.urn}
                                 for t in u.tasks]} for u in occ.units]})
    return {"groups": groups}
```
- `build_tasks`: read `task_code` from each picked row; set `indexer_ref={"ocs_code":..., "task_code":...}` (drop `id`/`task_id`).
- `ocs_search`: `res = await knowledge.search_occupations(q, top_k=8)`; build hits `{"ocs_code": h.ocs_code, "ocs_name": h.ocs_name or h.ocs_code}`.
- `header_meta`: `metas.append(await knowledge.occupation(code))`.
- `ksa_pool`: `comp = await knowledge.competencies(code)`; iterate `comp.knowledge/skills/attitudes`; entry `{"code": it.code, "name": it.name or "", "sources": [s.task_code for s in it.sources if s.task_code]}`.

`backend/app/services/header_meta.py` `aggregate`: input is `list[OccupationDetail]`; read `m.ocs_name.occupation_name` and `m.ocs_name.job_category_name` (were `m.job_title`/`m.job_category_name`); attitudes/categories already `CodeName` (`.code/.name`) so `_merge_pairs` is unchanged. Output keys unchanged (`occupation_name`/`job_category_name`).

`backend/app/services/ocs_doc.py`: `_task_prov` and the custom-task provenance writer become `{ocs_code, task_code, urn}`:
```python
def _task_prov(task: dict) -> dict:
    ref = task.get("indexer_ref") or {}
    return {"ocs_code": ref.get("ocs_code") or "", "task_code": ref.get("task_code") or "",
            "urn": ref.get("urn") or ""}
```
and update `build_from_picked` to read `task_code` from refs and key the existing-task set on `(p.get("ocs_code"), p.get("task_code"))`.

- [ ] **Step 4: Run to verify pass + full suite**

Run: `cd backend && .venv/Scripts/python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/api/routes/documents.py app/services/header_meta.py app/services/ocs_doc.py tests/test_documents_api.py tests/test_ocs_doc.py
git commit -m "feat(be): documents/header-meta/ocs-doc → v4 field names + provenance task_code"
```

---

### Task B6: Remove old indexer surface (models, methods, Protocol, stubs, tests)

**Files:**
- Modify: `backend/app/services/knowledge/{models.py,base.py,http_client.py}`, `backend/app/graph_v3/stubs.py`, `backend/tests/conftest_graph.py`, `backend/app/services/ai/tasks.py`
- Modify/trim: `backend/tests/test_http_indexer_client.py`, `backend/tests/test_knowledge_models.py`

**Interfaces:** none new — removal only, so the suite reflects the v4 surface.

- [ ] **Step 1: Delete old symbols**

- `models.py`: delete `Hit, SearchResult, Pair, Pairs, PoolTask, PoolUnit, PoolGroup, TaskPool, ProfileMeta, TaskDetail, TasksByIdResult`.
- `base.py`: delete old Protocol methods `search, task_pool, pairs, profile, tasks_by_id` and their now-unused imports.
- `http_client.py`: delete old methods `search, task_pool, pairs, profile, tasks_by_id` and unused imports.
- `stubs.py` `StubKnowledge`: delete `search, task_pool, pairs, profile, tasks_by_id` and old imports (keep `search_occupations, occupation_tasks, competencies, healthz`).
- `conftest_graph.py` `FakeKnowledge`: delete `search, task_pool, pairs, tasks_by_id` and old imports.
- `ai/tasks.py`: delete `catalog_id` if no remaining caller (grep first).
- `test_http_indexer_client.py` / `test_knowledge_models.py`: delete the old-surface tests (`test_search_calls_endpoint_and_parses`, `test_pairs_uses_path_param`, `test_tasks_by_id_posts_ids`, `test_search_result_parses_and_ignores_extra`, `test_pairs_parses_*`, `test_task_detail_parses`).

- [ ] **Step 2: Grep for stragglers**

Run: `cd backend && git grep -nE "task_pool|tasks_by_id|\.pairs\(|\.profile\(|SearchResult|TaskPool|ProfileMeta|TasksByIdResult|PoolGroup|catalog_id" -- app tests`
Expected: no matches in `app/` or `tests/` (docs may match — ignore). Fix any straggler.

- [ ] **Step 3: Run full suite — confirm green**

Run: `cd backend && .venv/Scripts/python -m pytest -q`
Expected: PASS, no import errors.

- [ ] **Step 4: Commit**

```bash
cd backend && git add app/services/knowledge app/graph_v3/stubs.py app/services/ai/tasks.py tests/conftest_graph.py tests/test_http_indexer_client.py tests/test_knowledge_models.py
git commit -m "refactor(be): remove old indexer surface; v4-only KnowledgeClient"
```

---

### Task F1: Frontend field renames (types + api + ocsDoc + task/profile panels)

Rename task-candidates/search/profile/provenance fields to v4 across types and their consumers so `tsc` is green at the task boundary. Drop `activity_examples` from the task curator.

**Files:**
- Modify: `frontend/src/types/index.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/ocsDoc.ts`, `frontend/src/components/interview/v3/TaskCuratePanel.tsx`, `frontend/src/components/interview/v3/InterruptHandlers.tsx`

**Interfaces:**
- Produces (types): `OcsSearchHit{ocs_code, ocs_name}`; `CandidateTask{task_code, task_name, urn}`; `CandidateUnit{ocu_code, ocu_name, tasks}`; `CandidateGroup{ocs_code, ocs_name, units}`; `PickedTask{ocs_code, ocu_code, ocu_name, ocs_name, task_code, task_name}`; `OcsTask.provenance{ocs_code, task_code, urn?}`; `ProfileCandidate{ocs_code, ocs_name?}`; `PoolTask.indexer_ref{ocs_code?, task_code?}` (no `activity_examples`).

- [ ] **Step 1: Read the platform guide**

Read `frontend/node_modules/next/dist/docs/` index for any component/typing constraints (per `frontend/AGENTS.md`). No code yet.

- [ ] **Step 2: Update `types/index.ts`**

Replace the relevant interfaces:
```ts
export interface OcsSearchHit {
  ocs_code: string;
  ocs_name: string;
}

export interface CandidateTask {
  task_code: string;
  task_name: string;
  urn: string;
}
export interface CandidateUnit {
  ocu_code: string;
  ocu_name: string;
  tasks: CandidateTask[];
}
export interface CandidateGroup {
  ocs_code: string;
  ocs_name: string;
  units: CandidateUnit[];
}
export interface TaskCandidates {
  groups: CandidateGroup[];
}

export interface PickedTask {
  ocs_code: string;
  ocu_code: string;
  ocu_name: string;
  ocs_name: string;
  task_code: string;
  task_name: string;
}
```
In `OcsTask`, change `provenance?: { ocs_code: string; task_code: string; urn?: string }`.

- [ ] **Step 3: Update `lib/api.ts` + `lib/ocsDoc.ts`**

`api.ts`: `ocsSearch` return type unchanged (`OcsSearchHit[]`) — only the field shape changed. In `ocsDoc.ts`, update any helper that reads `provenance.task_id`/`unit_id`/`unit_title`/`occupation_name` from picked rows or tasks to the new names (`task_code`/`ocu_code`/`ocu_name`/`ocs_name`). (Read `ocsDoc.ts` first; rename references.)

- [ ] **Step 4: Update `TaskCuratePanel.tsx`**

Replace `t.id`/`t.task_id`/`t.task_title` with `t.task_code`/`t.task_name`; `g.occupation_name`→`g.ocs_name`; `u.unit_id`/`u.unit_title`→`u.ocu_code`/`u.ocu_name`; `tkey`/`alreadyIn`/`adopted` key on `(ocs_code, task_code)`; provenance read `p?.ocs_code && p?.task_code`. extract-tasks `byId` maps `task_code` (suggested ids are task_codes): replace the `byId` build + lookup:
```tsx
      const byCode = new Map<string, { oc: string; tc: string }>();
      for (const g of groups) for (const u of g.units) for (const t of u.tasks)
        byCode.set(`${g.ocs_code}__${t.task_code}`, { oc: g.ocs_code, tc: t.task_code });
      // suggested_task_ids are task_codes scoped per OCS: try each group
      for (const id of res.suggested_task_ids) {
        for (const g of groups) {
          const m = byCode.get(`${g.ocs_code}__${id}`);
          if (m && !alreadyIn.has(tkey(m.oc, m.tc))) next.add(tkey(m.oc, m.tc));
        }
      }
```
`confirm()` emits `PickedTask` with `ocu_code`/`ocu_name`/`ocs_name`/`task_code`/`task_name`. Custom rows: drop `id`, use `task_code: \`custom:${newUid()}\``.

- [ ] **Step 5: Update `InterruptHandlers.tsx`**

`ProfileCandidate` → `{ ocs_code: string; ocs_name?: string | null }`; in `ProfilePicker` render `c.ocs_name` (was `c.job_title`). `PoolTask` → `indexer_ref?: { ocs_code?: string; task_code?: string }`, remove `activity_examples`; in `TaskCurator` remove the `r.activity_examples` preview block and drop it from the emitted object.

- [ ] **Step 6: Typecheck + lint — confirm green**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: PASS (no type errors; eslint clean).

- [ ] **Step 7: Commit**

```bash
cd frontend && git add src/types/index.ts src/lib/api.ts src/lib/ocsDoc.ts src/components/interview/v3/TaskCuratePanel.tsx src/components/interview/v3/InterruptHandlers.tsx
git commit -m "feat(fe): v4 field renames (task_code/ocu_*/ocs_name) + drop activity_examples"
```

---

### Task F2: Frontend provenance surfacing (K/S/O source badges)

Add display-only `sources` to pool/candidate items and render a "共 N／來自：…" badge on K/S/O candidate rows in `CellFillerPanel` and the `curate_ks` interrupt list. The of-record `CodeName` stays `{code,name}`.

**Files:**
- Modify: `frontend/src/types/index.ts` (add `KsaPoolItem`), `frontend/src/components/interview/v3/CellFillerPanel.tsx`, `frontend/src/components/interview/v3/InterruptHandlers.tsx`, `frontend/src/components/interview/v3/HeaderMetaPanel.tsx` (only if field names shifted)

**Interfaces:**
- Consumes: backend ksa-pool items `{code, name, sources:string[]}` (B5) and `curate_ks` candidate `KsaItem.sources?:string[]` (B3 → interrupt payload).
- Produces (types): `KsaPoolItem extends CodeName { sources?: string[] }`; `KsaPool{knowledge,skills,attitudes:KsaPoolItem[]}`. `KsaItem` gains `sources?: string[]`.

- [ ] **Step 1: Add display types**

In `types/index.ts`:
```ts
export interface KsaPoolItem extends CodeName {
  sources?: string[];
}
export interface KsaPool {
  knowledge: KsaPoolItem[];
  skills: KsaPoolItem[];
  attitudes: KsaPoolItem[];
}
```
In `InterruptHandlers.tsx`, extend `KsaItem` with `sources?: string[]`.

- [ ] **Step 2: Render the badge in `CellFillerPanel.tsx`**

In the `Picker` candidate row, after the name span, add (reusing the HeaderMetaPanel pattern):
```tsx
              {(c as KsaPoolItem).sources && (c as KsaPoolItem).sources!.length > 0 ? (
                <span className="ml-auto shrink-0 rounded bg-sky-100 px-1 py-0.5 text-[10px] text-sky-700"
                      title={"來自：" + (c as KsaPoolItem).sources!.join("、")}>
                  共 {(c as KsaPoolItem).sources!.length}
                </span>
              ) : null}
```
(Widen the `Picker` `catalog`/candidate types from `CodeName[]` to `KsaPoolItem[]`, and `CellFillerPanel`'s `pool` prop to `KsaPool` with `KsaPoolItem`.)

- [ ] **Step 3: Render the badge in the `curate_ks` list (`InterruptHandlers.tsx`)**

In `CurateList`, after the candidate label content:
```tsx
          {c.sources?.length ? (
            <span className="shrink-0 rounded bg-sky-100 px-1 py-0.5 text-[10px] text-sky-700"
                  title={"來自：" + c.sources.join("、")}>
              共 {c.sources.length}
            </span>
          ) : null}
```

- [ ] **Step 4: Typecheck + lint — confirm green**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/types/index.ts src/components/interview/v3/CellFillerPanel.tsx src/components/interview/v3/InterruptHandlers.tsx
git commit -m "feat(fe): surface K/S/O provenance (source task_code badges)"
```

---

## Self-Review

**Spec coverage:**
- Section 1 (knowledge layer) → B1, removed in B6. ✓
- Section 2 (call sites: nodes/curate/deep/ai/documents/header_meta/ocs_doc) → B2–B5. ✓
- Section 3 (outward REST v4 naming) → B5 + frontend F1. ✓
- Section 4 (frontend types/panels/provenance) → F1, F2. ✓
- Section 5 (testing) → each task is TDD; out-of-scope (findSimilar/dedup) never added. ✓
- Core forced change (point id → task_code; competencies-by-task_code; provenance drop `id`) → B1 helper, B3 deep, B4 ai, B5 ocs_doc. ✓

**Placeholder scan:** New modules/tests have full code. Edits to already-read tests (B1/B2/B3 curate) show full code; edits to not-yet-read tests (B3 deep_five_w2h, B4 recommend/draft, B5 documents/ocs_doc) give exact new stub code + the precise field/assertion changes with a "read the file first" instruction — concrete, not "TBD".

**Type consistency:** `task_competencies` returns `knowledge/skills/outputs:[{code,name}]`, `indicators:[{code,text}]` — consumed identically in B3 (`detail["outputs"]`) and B4 (`detail["knowledge"/"skills"/"outputs"/"indicators"]`). `indexer_ref`/`provenance` = `{ocs_code, task_code(, urn)}` consistent across B2 (nodes), B3 (deep), B4 (`catalog_ref`), B5 (ocs_doc), F1 (types). Client/Protocol method names (`search_occupations/search_tasks/occupation/competencies/occupation_tasks`) identical in B1 definitions and B2–B5 call sites. Frontend `CandidateGroup.ocs_name`/`CandidateUnit.ocu_code`/`CandidateTask.task_code` consistent between F1 types and TaskCuratePanel usage.

## Out of Scope (later increments)
- `/tasks/findSimilar` wiring + cross-repo dedup clustering/merge.
- Re-ingest of live Qdrant (destructive; explicit authorization; after consumer).
- Reranker for occupation search relevance.
