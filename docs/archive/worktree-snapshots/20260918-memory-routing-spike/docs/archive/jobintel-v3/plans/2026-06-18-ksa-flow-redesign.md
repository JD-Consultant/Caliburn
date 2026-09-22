# KSA 流程重設計 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 v3 收尾段從單步 `assemble_ksa`（職類層 K/S/A 一次編完）改成「逐任務 K/S 審閱（task 層）+ 全域 A 審閱 + 唯讀 REVIEW」，對齊 OCS 職能基準結構。

**Architecture:** deep loop 全部訪談完 → `fetch_ksa_pool`（打一次 `pairs()` 快取職類池）→ `curate_ks`（單一 node 內 deterministic for-loop，逐任務一個 interrupt 審閱面）→ `curate_attitudes`（一個 interrupt）→ `build_doc`（組裝、REVIEW 唯讀預覽、flush ksa_items + 存 document_versions）→ done。前端用 v2 `useInterrupt(renderInChat:false)` 渲染兩個新審閱面。

**Tech Stack:** LangGraph（interrupt/Command HITL、AsyncPostgresSaver）、ag-ui-langgraph、CopilotKit v2、FastAPI、SQLAlchemy 2.0 async、Next.js 16 + React 19。

## Global Constraints

- 分支 `feat/v3`。後端測試用 `backend/.venv/Scripts/python -m pytest`（**不要** `uv run`）。
- 後端啟動 `backend/.venv/Scripts/python run_live.py`（Windows SelectorEventLoop；改後端碼必重啟，無 --reload）。
- 設計依據：`docs/superpowers/specs/2026-06-18-ksa-flow-redesign-design.md`（D24）。
- **舊架構可丟、不需向後相容**：直接刪 `assemble_ksa`、舊 `edit_ksa` interrupt、前端現有 `KsaEditor`。
- **LangGraph 鐵律**：一個 node 內多個 `interrupt()` 用 resume-list 的 index 嚴格配對 → `curate_ks` 的 for-loop 必須 deterministic（任務固定、順序固定、不可條件式跳過 interrupt）。
- **idempotency-on-resume**：node 從 interrupt resume 會整個重跑 → `pairs()` 只在 `fetch_ksa_pool`（無 interrupt 的獨立 node）打一次、存進 state；`curate_ks`/`curate_attitudes` 只讀 state 的池、不重打。
- KSA item 統一形狀：`{"content": str, "source": "catalog"|"company", "icap_ref": str|None}`。
- task 穩定鍵：`task_key(task) = (task.get("indexer_ref") or {}).get("task_id") or task["task_name"]`。
- of-record 用既有 `ksa_items.task_id`（**無 migration**）：K/S 帶 `task_id`、A `task_id=NULL`。flush 集中在 `build_doc`（REVIEW 確認後）一次做。

---

### Task 1：State schema 改成 per-task KSA

**Files:**
- Modify: `backend/app/graph_v3/state.py`
- Test: `backend/tests/test_state_v3.py`

**Interfaces:**
- Produces: `KsaState` TypedDict `{pool: KsaDraft, by_task: dict[str,dict], attitudes: list[dict], ks_index: int}`；`InterviewState["ksa"]: KsaState`；`new_state()` 初始化；`task_key(task: dict) -> str` helper。

- [ ] **Step 1: 改測試 `test_state_v3.py`（RED）**

把現有對 `ksa` 的斷言改成新結構，並加 `task_key`：

```python
from app.graph_v3.state import new_state, task_key


def test_new_state_has_per_task_ksa():
    s = new_state(job_profile_id="p1", job_title="工程師")
    assert s["ksa"] == {"pool": {"knowledge": [], "skills": [], "attitudes": []},
                        "by_task": {}, "attitudes": [], "ks_index": 0}
    assert s["profile"]["selected_ocs_code"] is None


def test_task_key_prefers_indexer_task_id():
    assert task_key({"task_name": "巡檢", "indexer_ref": {"task_id": "T1"}}) == "T1"
    assert task_key({"task_name": "巡檢"}) == "巡檢"
```

- [ ] **Step 2: 跑測試確認 RED**

Run: `backend/.venv/Scripts/python -m pytest tests/test_state_v3.py -q`
Expected: FAIL（`task_key` ImportError / ksa 結構不符）。

- [ ] **Step 3: 改 `state.py`**

替換 `KsaDraft` 用法處，新增 `KsaState` 與 `task_key`：

```python
class KsaDraft(TypedDict):
    knowledge: list[dict]
    skills: list[dict]
    attitudes: list[dict]


class KsaState(TypedDict):
    pool: KsaDraft                 # fetch_ksa_pool 填的職類池候選
    by_task: dict[str, dict]       # task_key -> {"knowledge": list[dict], "skills": list[dict]}
    attitudes: list[dict]          # 全域 A（curate_attitudes 填）
    ks_index: int                  # 觀測用進度
```

`InterviewState` 的 `ksa` 欄型別改 `KsaState`。`new_state()` 的 `ksa` 初始化改：

```python
        "ksa": {"pool": {"knowledge": [], "skills": [], "attitudes": []},
                "by_task": {}, "attitudes": [], "ks_index": 0},
```

檔尾新增 helper：

```python
def task_key(task: dict) -> str:
    """逐任務穩定鍵：優先 indexer task_id，否則 task_name。"""
    return (task.get("indexer_ref") or {}).get("task_id") or task["task_name"]
```

- [ ] **Step 4: 跑測試確認 GREEN**

Run: `backend/.venv/Scripts/python -m pytest tests/test_state_v3.py -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/graph_v3/state.py backend/tests/test_state_v3.py
git commit -m "feat(graph_v3): per-task KSA state (KsaState + task_key)"
```

---

### Task 2：persistence — KsaRepo 改 per-task flush（task_id 連結）

**Files:**
- Modify: `backend/app/services/persistence.py`
- Test: `backend/tests/test_persistence_ksa.py` (Create)

**Interfaces:**
- Produces: `KsaRepo.flush(job_profile_id, *, by_task: dict[str,dict], attitudes: list[dict]) -> None`。以 `(ksa_type, content, task_id)` 為穩定鍵 upsert；K/S 帶 `task_id`（由 company_tasks 對應 `task_key`），A `task_id=None`。`KsaRepo.hydrate` 回 `{"by_task": {...}, "attitudes": [...]}`。

- [ ] **Step 1: 寫失敗測試 `test_persistence_ksa.py`（RED）**

```python
import pytest
from uuid import uuid4
from app.models import JobProfile, User, CompanyTask, KsaItem
from app.services.persistence import KsaRepo
from sqlalchemy import select


@pytest.mark.asyncio
async def test_flush_ksa_links_ks_to_task_and_a_global(db_session):
    user = User(email=f"{uuid4()}@x.com", name="n"); db_session.add(user); await db_session.flush()
    prof = JobProfile(user_id=user.id, job_title="工程師"); db_session.add(prof); await db_session.flush()
    t = CompanyTask(job_profile_id=prof.id, task_name="巡檢", indexer_ref={"task_id": "T1"})
    db_session.add(t); await db_session.flush()

    await KsaRepo(db_session).flush(
        prof.id,
        by_task={"T1": {"knowledge": [{"content": "PLC 原理", "source": "catalog", "icap_ref": "K01"}],
                        "skills": [{"content": "故障排除", "source": "company", "icap_ref": None}]}},
        attitudes=[{"content": "細心", "source": "catalog", "icap_ref": "A01"}],
    )
    rows = (await db_session.execute(select(KsaItem).where(KsaItem.job_profile_id == prof.id))).scalars().all()
    by_type = {(r.ksa_type, r.content): r for r in rows}
    assert by_type[("K", "PLC 原理")].task_id == t.id
    assert by_type[("S", "故障排除")].task_id == t.id
    assert by_type[("A", "細心")].task_id is None
```

- [ ] **Step 2: 跑測試確認 RED**

Run: `backend/.venv/Scripts/python -m pytest tests/test_persistence_ksa.py -q`
Expected: FAIL（`flush` 簽章不符 / task_id 為 None）。
> 註：此測試需 DB（`db_session` fixture）。若無測試 DB，標記 `@pytest.mark.skipif` 沿用既有 DB 測試的 skip 慣例（見 `test_live_db_persist.py`）。

- [ ] **Step 3: 改 `KsaRepo`**

替換 `KsaRepo.hydrate` / `flush`：

```python
class KsaRepo:
    """ksa_items：K/S 帶 task_id（per task）、A task_id=NULL（全域）。
    穩定鍵 (ksa_type, content, task_id) row-level upsert。"""

    def __init__(self, session: AsyncSession):
        self.s = session

    async def _task_id_map(self, job_profile_id: UUID) -> dict[str, "UUID"]:
        rows = (await self.s.execute(
            select(CompanyTask).where(CompanyTask.job_profile_id == job_profile_id)
        )).scalars().all()
        out = {}
        for r in rows:
            key = (r.indexer_ref or {}).get("task_id") or r.task_name
            out[key] = r.id
        return out

    async def hydrate(self, job_profile_id: UUID) -> dict:
        rows = (await self.s.execute(
            select(KsaItem).where(KsaItem.job_profile_id == job_profile_id)
            .order_by(KsaItem.created_at, KsaItem.id)
        )).scalars().all()
        id_to_key = {v: k for k, v in (await self._task_id_map(job_profile_id)).items()}
        by_task: dict[str, dict] = {}
        attitudes: list[dict] = []
        bucket = {"K": "knowledge", "S": "skills"}
        for r in rows:
            item = {"id": str(r.id), "content": r.content,
                    "source": _DB_TO_SRC.get(r.source_type, "company"), "icap_ref": r.icap_ref}
            if r.ksa_type == "A":
                attitudes.append(item)
            elif r.ksa_type in bucket and r.task_id is not None:
                key = id_to_key.get(r.task_id)
                if key:
                    by_task.setdefault(key, {"knowledge": [], "skills": []})[bucket[r.ksa_type]].append(item)
        return {"by_task": by_task, "attitudes": attitudes}

    async def flush(self, job_profile_id: UUID, *, by_task: dict, attitudes: list) -> None:
        existing = {(r.ksa_type, r.content, r.task_id): r for r in (await self.s.execute(
            select(KsaItem).where(KsaItem.job_profile_id == job_profile_id)
        )).scalars().all()}
        tmap = await self._task_id_map(job_profile_id)
        seen: set = set()

        def _upsert(code: str, item: dict, task_id):
            content = (item.get("content") or "").strip()
            if not content:
                return
            key = (code, content, task_id)
            seen.add(key)
            row = existing.get(key) or KsaItem(
                job_profile_id=job_profile_id, ksa_type=code, content=content, task_id=task_id)
            row.source_type = _SRC_TO_DB.get(item.get("source", "company"), "company_defined")
            row.icap_ref = item.get("icap_ref")
            if key not in existing:
                self.s.add(row)

        for tkey, ks in (by_task or {}).items():
            tid = tmap.get(tkey)
            for item in ks.get("knowledge", []):
                _upsert("K", item, tid)
            for item in ks.get("skills", []):
                _upsert("S", item, tid)
        for item in (attitudes or []):
            _upsert("A", item, None)

        for key, row in existing.items():
            if key not in seen:
                await self.s.delete(row)
        await self.s.flush()
```

（`_KSA_TYPES` 常數已不需要，可留著不影響。）

- [ ] **Step 4: 跑測試確認 GREEN**

Run: `backend/.venv/Scripts/python -m pytest tests/test_persistence_ksa.py -q`
Expected: PASS（或 skip 若無 DB）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/persistence.py backend/tests/test_persistence_ksa.py
git commit -m "feat(persistence): per-task KsaRepo.flush (K/S task_id, A global)"
```

---

### Task 3：PersistPort + 三個實作改 flush_ksa 簽章

**Files:**
- Modify: `backend/app/graph_v3/deps.py`（`PersistPort`、`DbPersist`、`LiveDbPersist`）
- Modify: `backend/app/graph_v3/stubs.py`（`InMemoryPersist`）
- Modify: `backend/tests/conftest_graph.py`（`SpyPersist`）

**Interfaces:**
- Consumes: `KsaRepo.flush(pid, *, by_task, attitudes)`（Task 2）。
- Produces: `PersistPort.flush_ksa(self, job_profile_id, *, by_task: dict, attitudes: list) -> None`（取代舊 `flush_ksa(job_profile_id, ksa)`）。

- [ ] **Step 1: 改 `deps.py` 的 Protocol 與兩個實作**

`PersistPort`：

```python
    async def flush_ksa(self, job_profile_id: UUID, *, by_task: dict, attitudes: list) -> None: ...
```

`DbPersist.flush_ksa`：

```python
    async def flush_ksa(self, job_profile_id: UUID, *, by_task: dict, attitudes: list) -> None:
        await KsaRepo(self.s).flush(job_profile_id, by_task=by_task, attitudes=attitudes)
        await self.s.flush()
```

`LiveDbPersist.flush_ksa`：

```python
    async def flush_ksa(self, job_profile_id: UUID, *, by_task: dict, attitudes: list) -> None:
        async with self._sf() as s:
            await KsaRepo(s).flush(job_profile_id, by_task=by_task, attitudes=attitudes)
            await s.commit()
```

- [ ] **Step 2: 改 `stubs.py` 的 `InMemoryPersist.flush_ksa`**

```python
    async def flush_ksa(self, job_profile_id, *, by_task, attitudes) -> None:
        self.ksa[str(job_profile_id)] = {"by_task": by_task, "attitudes": attitudes}
```

- [ ] **Step 3: 改 `conftest_graph.py` 的 `SpyPersist`**

```python
    async def flush_ksa(self, pid, *, by_task, attitudes):
        self.ksa_flushed = (str(pid), by_task, attitudes)
```

- [ ] **Step 4: 跑既有套件確認沒爆 import**

Run: `backend/.venv/Scripts/python -m pytest -q`
Expected: 可能有 assemble 相關紅燈（Task 6 移除），其餘 import 正常。記錄紅燈集合，Task 4–6 處理。

- [ ] **Step 5: Commit**

```bash
git add backend/app/graph_v3/deps.py backend/app/graph_v3/stubs.py backend/tests/conftest_graph.py
git commit -m "refactor(persist): flush_ksa(by_task, attitudes) signature across ports"
```

---

### Task 4：新節點 fetch_ksa_pool + curate_ks + curate_attitudes

**Files:**
- Create: `backend/app/graph_v3/curate_nodes.py`
- Test: `backend/tests/test_curate_nodes.py`

**Interfaces:**
- Consumes: `task_key`（Task 1）、`Deps`、`KnowledgeClient.pairs()`。
- Produces: `fetch_ksa_pool(state, config) -> dict`、`curate_ks(state, config) -> dict`、`curate_attitudes(state, config) -> dict`。interrupt 形狀：
  - `curate_ks`：`{"kind":"curate_ks","task_index":int,"task_total":int,"task_name":str,"candidates":{"knowledge":[...],"skills":[...]},"selected":{"knowledge":[...],"skills":[...]}}`；resume `{"ks":{"knowledge":[...],"skills":[...]}}`。
  - `curate_attitudes`：`{"kind":"curate_attitudes","candidates":[...],"selected":[...]}`；resume `{"attitudes":[...]}`。

- [ ] **Step 1: 寫失敗測試 `test_curate_nodes.py`（RED）**

```python
import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.curate_nodes import fetch_ksa_pool, curate_ks, curate_attitudes
from app.graph_v3.deps import Deps
from app.services.knowledge.models import Pairs, Pair
from tests.conftest_graph import FakeKnowledge, SpyPersist


def _one(node):
    g = StateGraph(InterviewState)
    g.add_node("n", node)
    g.add_edge(START, "n"); g.add_edge("n", END)
    return g.compile(checkpointer=MemorySaver())


@pytest.mark.asyncio
async def test_fetch_ksa_pool_caches_pairs():
    pairs = Pairs(ocs_code="OC1", knowledge=[Pair(code="K01", name="PLC")],
                  skills=[Pair(code="S01", name="排障")], attitudes=[Pair(code="A01", name="細心")])
    fake = FakeKnowledge(); fake._pairs = pairs  # see conftest patch below
    s = new_state(job_profile_id="p1", job_title="工程師")
    s["profile"]["selected_ocs_code"] = "OC1"
    cfg = {"configurable": {"thread_id": "t", "deps": Deps(knowledge=fake, persist=SpyPersist())}}
    out = await _one(fetch_ksa_pool).ainvoke(s, cfg)
    assert out["ksa"]["pool"]["knowledge"][0]["content"] == "PLC"
    assert out["ksa"]["pool"]["attitudes"][0]["content"] == "細心"
    assert out["current_step"] == "curate_ks"


@pytest.mark.asyncio
async def test_curate_ks_loops_per_task_then_routes_attitudes():
    s = new_state(job_profile_id="p1", job_title="工程師")
    s["tasks"] = [{"task_name": "巡檢", "indexer_ref": {"task_id": "T1"}},
                  {"task_name": "保養", "indexer_ref": {"task_id": "T2"}}]
    s["ksa"]["pool"] = {"knowledge": [{"content": "PLC", "source": "catalog", "icap_ref": "K01"}],
                        "skills": [], "attitudes": []}
    cfg = {"configurable": {"thread_id": "t", "deps": Deps(knowledge=FakeKnowledge(), persist=SpyPersist())}}
    graph = _one(curate_ks)
    out = await graph.ainvoke(s, cfg)
    assert out["__interrupt__"][0].value["kind"] == "curate_ks"
    assert out["__interrupt__"][0].value["task_name"] == "巡檢"
    out = await graph.ainvoke(Command(resume={"ks": {"knowledge": [{"content": "PLC", "source": "catalog", "icap_ref": "K01"}], "skills": []}}), cfg)
    assert out["__interrupt__"][0].value["task_name"] == "保養"   # 第二任務
    out = await graph.ainvoke(Command(resume={"ks": {"knowledge": [], "skills": []}}), cfg)
    assert out["ksa"]["by_task"]["T1"]["knowledge"][0]["content"] == "PLC"
    assert out["ksa"]["by_task"]["T2"] == {"knowledge": [], "skills": []}
    assert out["current_step"] == "curate_attitudes"


@pytest.mark.asyncio
async def test_curate_attitudes_interrupt_then_store():
    s = new_state(job_profile_id="p1", job_title="工程師")
    s["ksa"]["pool"] = {"knowledge": [], "skills": [],
                        "attitudes": [{"content": "細心", "source": "catalog", "icap_ref": "A01"}]}
    cfg = {"configurable": {"thread_id": "t", "deps": Deps(knowledge=FakeKnowledge(), persist=SpyPersist())}}
    graph = _one(curate_attitudes)
    out = await graph.ainvoke(s, cfg)
    assert out["__interrupt__"][0].value["kind"] == "curate_attitudes"
    out = await graph.ainvoke(Command(resume={"attitudes": [{"content": "細心", "source": "catalog", "icap_ref": "A01"}]}), cfg)
    assert out["ksa"]["attitudes"][0]["content"] == "細心"
    assert out["current_step"] == "build_doc"
```

加 `FakeKnowledge.pairs` 支援可配 `_pairs`（在 conftest_graph 已有 `pairs` 回 `Pairs(ocs_code=...)`；改成回 `self._pairs` 若有設）：在 `conftest_graph.py` 的 `FakeKnowledge.__init__` 加 `self._pairs = None`，`pairs` 改 `return self._pairs or Pairs(ocs_code=ocs_code)`。

- [ ] **Step 2: 跑測試確認 RED**

Run: `backend/.venv/Scripts/python -m pytest tests/test_curate_nodes.py -q`
Expected: FAIL（`curate_nodes` 模組不存在）。

- [ ] **Step 3: 建 `curate_nodes.py`**

```python
"""v3 收尾 curate 節點：fetch_ksa_pool / curate_ks（逐任務）/ curate_attitudes（全域）。
deterministic、單一 node 內 interrupt for-loop（index-based resume）。pairs() 只在
fetch_ksa_pool 打一次並快取進 state，curate_* 只讀池不重打（idempotency-on-resume）。"""
import logging

from langgraph.types import interrupt

from app.graph_v3.state import InterviewState, task_key
from app.graph_v3.tracing import traced_node

logger = logging.getLogger("jobintel")


def _pairs_to_items(pairs_list) -> list[dict]:
    return [{"content": p.name, "source": "catalog", "icap_ref": p.code or None}
            for p in pairs_list if p.name]


@traced_node("fetch_ksa_pool")
async def fetch_ksa_pool(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    ocs = state["profile"]["selected_ocs_code"]
    pool = {"knowledge": [], "skills": [], "attitudes": []}
    if ocs:
        try:
            pairs = await deps.knowledge.pairs(ocs)
            pool = {"knowledge": _pairs_to_items(pairs.knowledge),
                    "skills": _pairs_to_items(pairs.skills),
                    "attitudes": _pairs_to_items(pairs.attitudes)}
        except Exception as exc:  # noqa: BLE001
            logger.warning("fetch_ksa_pool: pairs() failed, empty pool: %s", exc)
    return {"ksa": {**state["ksa"], "pool": pool}, "current_step": "curate_ks"}


@traced_node("curate_ks")
async def curate_ks(state: InterviewState, config) -> dict:
    pool = state["ksa"]["pool"]
    cand = {"knowledge": pool.get("knowledge", []), "skills": pool.get("skills", [])}
    by_task = dict(state["ksa"].get("by_task") or {})
    tasks = state["tasks"]
    for idx, task in enumerate(tasks):
        key = task_key(task)
        edited = interrupt({
            "kind": "curate_ks",
            "task_index": idx, "task_total": len(tasks),
            "task_name": task["task_name"],
            "candidates": cand,
            "selected": by_task.get(key, {"knowledge": [], "skills": []}),
        })
        ks = edited.get("ks") if isinstance(edited, dict) else None
        by_task[key] = ks or {"knowledge": [], "skills": []}
    logger.info("curate_ks: %d tasks done", len(tasks))
    return {"ksa": {**state["ksa"], "by_task": by_task},
            "current_step": "curate_attitudes"}


@traced_node("curate_attitudes")
async def curate_attitudes(state: InterviewState, config) -> dict:
    pool = state["ksa"]["pool"]
    edited = interrupt({
        "kind": "curate_attitudes",
        "candidates": pool.get("attitudes", []),
        "selected": state["ksa"].get("attitudes", []),
    })
    attitudes = edited.get("attitudes") if isinstance(edited, dict) else None
    return {"ksa": {**state["ksa"], "attitudes": attitudes or []},
            "current_step": "build_doc"}
```

- [ ] **Step 4: 跑測試確認 GREEN**

Run: `backend/.venv/Scripts/python -m pytest tests/test_curate_nodes.py -q`
Expected: PASS（3 passed）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/graph_v3/curate_nodes.py backend/tests/test_curate_nodes.py backend/tests/conftest_graph.py
git commit -m "feat(graph_v3): fetch_ksa_pool + curate_ks(per-task) + curate_attitudes nodes"
```

---

### Task 5：build_doc — K/S 巢狀進每任務、A 全域、REVIEW 後 flush

**Files:**
- Modify: `backend/app/graph_v3/build_doc.py`
- Test: `backend/tests/test_node_build_doc.py`（若不存在則 Create）

**Interfaces:**
- Consumes: `state["ksa"]["by_task"]`（task_key→{knowledge,skills}）、`state["ksa"]["attitudes"]`、`task_key`、`PersistPort.flush_ksa(pid, by_task=, attitudes=)`、`save_document`。
- Produces: 文件 `ocs_content.ocu_units[].tasks[]` 各含 `knowledge`/`skills`（coded）；`ocs_ksa` 只剩 `attitudes`。`build_doc` 先 `interrupt(preview)` → flush_ksa → save_document。

- [ ] **Step 1: 改 `_assemble` 與 `build_doc`**

在 `build_doc.py` 頂部 import `task_key`：

```python
from app.graph_v3.state import InterviewState, task_key
```

`_assemble` 內，task 迴圈組 `tasks_out` 時，加入該任務的 K/S（從 `by_task`）：

```python
    by_task = (state.get("ksa") or {}).get("by_task") or {}

    def _coded_ks(items, prefix):
        out, i = [], 0
        for it in items:
            content = (it.get("content") or "").strip()
            if not content:
                continue
            i += 1
            out.append({"code": it.get("icap_ref") or f"{prefix}{i:02d}", "name": content,
                        "source": it.get("source", "company"), "icap_ref": it.get("icap_ref")})
        return out
```

在 `tasks_out.append({...})` 內加 `knowledge`/`skills`（用該 task 的 key）：

```python
            ks = by_task.get(task_key(task), {})
            tasks_out.append({"task_code": f"T{u_idx}.{t_idx}",
                              "task_name": task.get("task_name", ""),
                              "indicators": indicators, "outputs": outputs,
                              "knowledge": _coded_ks(ks.get("knowledge", []), f"K{u_idx}.{t_idx}"),
                              "skills": _coded_ks(ks.get("skills", []), f"S{u_idx}.{t_idx}")})
```

`ocs_ksa` 區塊改成只含 attitudes（K/S 已下放任務）：

```python
    attitudes = (state.get("ksa") or {}).get("attitudes", [])
    return {
        "ocs_profile": {...},                      # 不變
        "ocs_content": {"ocu_units": ocu_units},
        "ocs_ksa": {"attitudes": _coded(attitudes, "A")},
    }
```

（保留既有 `_coded` helper 給 attitudes 用。）

`build_doc` 收尾改成 REVIEW 確認後 flush KSA 再存檔：

```python
@traced_node("build_doc")
async def build_doc(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    doc = _assemble(state)
    interrupt({"kind": "preview", "document": doc})   # REVIEW（唯讀）
    ksa = state.get("ksa") or {}
    await deps.persist.flush_ksa(state["job_profile_id"],
                                 by_task=ksa.get("by_task") or {},
                                 attitudes=ksa.get("attitudes") or [])
    await deps.persist.save_document(state["job_profile_id"], doc)
    logger.info("build_doc: %d OCU units, flushed KSA", len(doc["ocs_content"]["ocu_units"]))
    return {"document": doc, "current_step": "done"}
```

- [ ] **Step 2: 寫/改測試（RED→GREEN）**

`test_node_build_doc.py`：建單節點 graph，state 帶 1 任務 + by_task + attitudes，invoke → preview interrupt → resume → 斷言 doc 結構 + SpyPersist 收到 flush_ksa 與 save_document：

```python
import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.build_doc import build_doc
from app.graph_v3.deps import Deps
from tests.conftest_graph import FakeKnowledge, SpyPersist


def _one():
    g = StateGraph(InterviewState); g.add_node("n", build_doc)
    g.add_edge(START, "n"); g.add_edge("n", END)
    return g.compile(checkpointer=MemorySaver())


@pytest.mark.asyncio
async def test_build_doc_nests_ks_per_task_and_flushes():
    s = new_state(job_profile_id="p1", job_title="工程師")
    s["tasks"] = [{"task_name": "巡檢", "indexer_ref": {"task_id": "T1"}, "unit_id": "U1", "unit_title": "保養"}]
    s["ksa"]["by_task"] = {"T1": {"knowledge": [{"content": "PLC", "source": "catalog", "icap_ref": "K01"}],
                                  "skills": [{"content": "排障", "source": "company", "icap_ref": None}]}}
    s["ksa"]["attitudes"] = [{"content": "細心", "source": "catalog", "icap_ref": "A01"}]
    spy = SpyPersist()
    cfg = {"configurable": {"thread_id": "t", "deps": Deps(knowledge=FakeKnowledge(), persist=spy)}}
    graph = _one()
    out = await graph.ainvoke(s, cfg)
    assert out["__interrupt__"][0].value["kind"] == "preview"
    out = await graph.ainvoke(Command(resume=True), cfg)
    task0 = out["document"]["ocs_content"]["ocu_units"][0]["tasks"][0]
    assert task0["knowledge"][0]["name"] == "PLC"
    assert task0["skills"][0]["name"] == "排障"
    assert out["document"]["ocs_ksa"]["attitudes"][0]["name"] == "細心"
    assert spy.ksa_flushed[1]["T1"]["knowledge"][0]["content"] == "PLC"   # by_task
    assert spy.ksa_flushed[2][0]["content"] == "細心"                      # attitudes
    assert spy.doc_saved is not None
    assert out["current_step"] == "done"
```

Run RED: `backend/.venv/Scripts/python -m pytest tests/test_node_build_doc.py -q` → FAIL；改完 → PASS。

- [ ] **Step 3: Commit**

```bash
git add backend/app/graph_v3/build_doc.py backend/tests/test_node_build_doc.py
git commit -m "feat(build_doc): nest K/S per task, A global, flush KSA after REVIEW"
```

---

### Task 6：graph 重接線 + 移除 assemble_ksa

**Files:**
- Modify: `backend/app/graph_v3/graph.py`
- Delete: `backend/app/graph_v3/assemble_nodes.py`、`backend/tests/test_node_assemble_ksa.py`
- Test: `backend/tests/test_graph_v3_full_e2e.py`（更新 resume 序列）

**Interfaces:**
- Consumes: `fetch_ksa_pool`/`curate_ks`/`curate_attitudes`（Task 4）、`build_doc`（Task 5）。
- Produces: 路由 `finish_deep → fetch_ksa_pool → curate_ks → curate_attitudes → build_doc → END`。

- [ ] **Step 1: 改 `graph.py`**

import 改：移除 `from app.graph_v3.assemble_nodes import assemble_ksa`，加 `from app.graph_v3.curate_nodes import fetch_ksa_pool, curate_ks, curate_attitudes`。

`finish_deep` 的 current_step 改 `"fetch_ksa_pool"`：

```python
def finish_deep(state: InterviewState) -> dict:
    return {"current_step": "fetch_ksa_pool"}
```

`build_graph_v3` 內：移除 `g.add_node("assemble_ksa", ...)` 與其 edge；新增節點與線：

```python
    g.add_node("fetch_ksa_pool", fetch_ksa_pool)
    g.add_node("curate_ks", curate_ks)
    g.add_node("curate_attitudes", curate_attitudes)
    ...
    g.add_edge("finish_deep", "fetch_ksa_pool")
    g.add_edge("fetch_ksa_pool", "curate_ks")
    g.add_edge("curate_ks", "curate_attitudes")
    g.add_edge("curate_attitudes", "build_doc")
    g.add_edge("build_doc", END)
```

- [ ] **Step 2: 刪舊檔**

```bash
git rm backend/app/graph_v3/assemble_nodes.py backend/tests/test_node_assemble_ksa.py
```

- [ ] **Step 3: 更新 full e2e 測試**

`test_graph_v3_full_e2e.py`：在 deep loop 完成後，新增 resume 序列：每任務一個 `curate_ks` resume（`Command(resume={"ks":{"knowledge":[],"skills":[]}})`），再一個 `curate_attitudes` resume（`Command(resume={"attitudes":[]})`），再 `preview` resume（`Command(resume=True)`）。並把 FakeKnowledge 設可回 `pairs`（fetch_ksa_pool 會打）。斷言最終 `current_step == "done"` 且 `document` 存在。
（依現有檔的既有 resume 寫法續寫；參考 Task 4/5 的 resume 形狀。）

- [ ] **Step 4: 跑全套件確認 GREEN**

Run: `backend/.venv/Scripts/python -m pytest -q`
Expected: 全 PASS（assemble 相關紅燈已隨刪檔消失）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/graph_v3/graph.py backend/tests/test_graph_v3_full_e2e.py
git commit -m "feat(graph_v3): wire fetch_ksa_pool->curate_ks->curate_attitudes->build_doc; drop assemble_ksa"
```

---

### Task 7：前端 — 砍 KsaEditor、加 CurateKsPanel + CurateAttitudesPanel

**Files:**
- Modify: `frontend/src/components/interview/v3/InterruptHandlers.tsx`
- Modify: `frontend/src/app/v3/[id]/page.tsx`（seed 的 `ksa` 改新結構）

**Interfaces:**
- Consumes: interrupt payload（Task 4）：`curate_ks`/`curate_attitudes`。
- Produces: `resolve({ks:{knowledge,skills}})`（curate_ks）、`resolve({attitudes})`（curate_attitudes）。

- [ ] **Step 1: 改 v3 page seed 的 `ksa`**

`frontend/src/app/v3/[id]/page.tsx` 的 `agent.setState({...})` 把 `ksa` 改成：

```ts
      ksa: { pool: { knowledge: [], skills: [], attitudes: [] }, by_task: {}, attitudes: [], ks_index: 0 },
```

- [ ] **Step 2: 改 `InterruptHandlers.tsx`**

移除舊 `KsaEditor` component 與 `edit_ksa` 分支。新增共用的可編輯清單 `CurateList`（候選 checkbox 預設不勾 + 增/改/刪）、`CurateKsPanel`（K 段 + S 段）、`CurateAttitudesPanel`。型別與元件：

```tsx
type KsaItem = { content: string; source?: string; icap_ref?: string | null };

function CurateList({
  title, candidates, value, onChange, done,
}: {
  title: string;
  candidates: KsaItem[];
  value: KsaItem[];                       // 已選/已編輯
  onChange: (items: KsaItem[]) => void;
  done: boolean;
}) {
  // 候選預設不勾：以 content 判斷是否已在 value
  const has = (c: string) => value.some((v) => v.content === c);
  const toggle = (it: KsaItem) =>
    onChange(has(it.content) ? value.filter((v) => v.content !== it.content) : [...value, it]);
  const edit = (i: number, content: string) =>
    onChange(value.map((v, j) => (j === i ? { ...v, content } : v)));
  const remove = (i: number) => onChange(value.filter((_, j) => j !== i));
  const add = () => onChange([...value, { content: "", source: "company", icap_ref: null }]);
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium text-muted-foreground">{title}（已選 {value.length}）</p>
      {candidates.map((c) => (
        <label key={c.content} className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={has(c.content)} disabled={done} onChange={() => toggle(c)} />
          <span className={has(c.content) ? "" : "text-muted-foreground"}>{c.content}</span>
          {c.icap_ref ? <span className="font-mono text-[10px] text-muted-foreground">{c.icap_ref}</span> : null}
        </label>
      ))}
      {value.filter((v) => !candidates.some((c) => c.content === v.content)).map((v, i) => (
        <div key={`extra-${i}`} className="flex items-center gap-2">
          <input className="flex-1 rounded border px-2 py-1 text-sm" value={v.content} disabled={done}
                 onChange={(e) => edit(value.indexOf(v), e.target.value)} />
          <button type="button" className="text-red-500" disabled={done} onClick={() => remove(value.indexOf(v))}>✕</button>
        </div>
      ))}
      <button type="button" className="text-xs text-blue-600 hover:underline" disabled={done} onClick={add}>＋ 新增自訂</button>
    </div>
  );
}

function CurateKsPanel({ value, onConfirm }: {
  value: { task_index: number; task_total: number; task_name: string;
           candidates: { knowledge: KsaItem[]; skills: KsaItem[] };
           selected: { knowledge: KsaItem[]; skills: KsaItem[] } };
  onConfirm: (ks: { knowledge: KsaItem[]; skills: KsaItem[] }) => void;
}) {
  const [k, setK] = useState<KsaItem[]>(value.selected?.knowledge ?? []);
  const [s, setS] = useState<KsaItem[]>(value.selected?.skills ?? []);
  const [done, setDone] = useState(false);
  return (
    <div className="space-y-3 rounded-xl border p-3">
      <p className="text-sm font-medium">
        任務 {value.task_index + 1}/{value.task_total}：{value.task_name} — 選知識(K) / 技能(S)
      </p>
      <CurateList title="知識 K" candidates={value.candidates.knowledge} value={k} onChange={setK} done={done} />
      <CurateList title="技能 S" candidates={value.candidates.skills} value={s} onChange={setS} done={done} />
      <button type="button" className="w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              disabled={done}
              onClick={() => { setDone(true);
                onConfirm({ knowledge: k.filter((x) => x.content.trim()), skills: s.filter((x) => x.content.trim()) }); }}>
        確認此任務，下一個
      </button>
    </div>
  );
}

function CurateAttitudesPanel({ value, onConfirm }: {
  value: { candidates: KsaItem[]; selected: KsaItem[] };
  onConfirm: (attitudes: KsaItem[]) => void;
}) {
  const [a, setA] = useState<KsaItem[]>(value.selected ?? []);
  const [done, setDone] = useState(false);
  return (
    <div className="space-y-3 rounded-xl border p-3">
      <p className="text-sm font-medium">選態度（A，全職類共用）</p>
      <CurateList title="態度 A" candidates={value.candidates} value={a} onChange={setA} done={done} />
      <button type="button" className="w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              disabled={done}
              onClick={() => { setDone(true); onConfirm(a.filter((x) => x.content.trim())); }}>
        確認態度，產生文件
      </button>
    </div>
  );
}
```

`render` switch 內：移除 `edit_ksa` 分支，加：

```tsx
      if (value.kind === "curate_ks") {
        return <CurateKsPanel value={value as never} onConfirm={(ks) => resolve({ ks })} />;
      }
      if (value.kind === "curate_attitudes") {
        return <CurateAttitudesPanel value={value as never} onConfirm={(attitudes) => resolve({ attitudes })} />;
      }
```

（`InterruptValue` 型別補上 `task_index?/task_total?/candidates?/selected?` 等欄；`preview` 分支沿用既有 `DocPreviewPanel`。）

- [ ] **Step 3: typecheck**

Run: `cd frontend && npx tsc --noEmit -p tsconfig.json`
Expected: 無輸出（PASS）。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/interview/v3/InterruptHandlers.tsx frontend/src/app/v3/[id]/page.tsx
git commit -m "feat(fe): curate_ks (per-task K/S) + curate_attitudes panels; drop KsaEditor"
```

---

### Task 8：前端 — DocPreviewPanel 顯示每任務 K/S

**Files:**
- Modify: `frontend/src/components/interview/v3/InterruptHandlers.tsx`（`DocPreviewPanel` + `DocPreview` 型別）

**Interfaces:**
- Consumes: 文件 `ocs_content.ocu_units[].tasks[]` 新增 `knowledge`/`skills`（Task 5）；`ocs_ksa` 只剩 `attitudes`。

- [ ] **Step 1: 更新型別與渲染**

`DocPreview` 的 task 型別加 `knowledge?: {code?:string;name?:string}[]; skills?: {...}[]`。`DocPreviewPanel` 在每個 task 下，`outputs`/`indicators` 之後加：

```tsx
                  {t.knowledge?.length ? (
                    <span className="block pl-4 text-xs text-muted-foreground">
                      K：{t.knowledge.map((x) => x.name).join("、")}
                    </span>
                  ) : null}
                  {t.skills?.length ? (
                    <span className="block pl-4 text-xs text-muted-foreground">
                      S：{t.skills.map((x) => x.name).join("、")}
                    </span>
                  ) : null}
```

`ksaRow("知識 K", ...)` / `ksaRow("技能 S", ...)` 兩行移除（K/S 已在任務下顯示），只留 `ksaRow("態度 A", ksa.attitudes)`。

- [ ] **Step 2: typecheck**

Run: `cd frontend && npx tsc --noEmit -p tsconfig.json`
Expected: 無輸出。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/interview/v3/InterruptHandlers.tsx
git commit -m "feat(fe): DocPreview shows per-task K/S, A global"
```

---

### Task 9：端到端瀏覽器驗收 [runtime-verify，協作]

**Files:** 無（人工驗證）

- [ ] **Step 1:** 重啟後端 `backend/.venv/Scripts/python run_live.py`（吃新 nodes/graph）；確認 indexer:8000 暖機、前端:3000。
- [ ] **Step 2（使用者做）:** dashboard 新增職務 → 選職類 → 整理任務 → 深問走完所有任務 → **逐任務 KS 審閱面**（每任務挑 K/S，預設全不勾）→ **態度審閱面** → **REVIEW 唯讀**（每任務下顯示 K/S、底部顯示 A）→ 確認存檔 → done。
- [ ] **Step 3:** 驗收標準：`curate_ks` 每任務一個面、resume 正常推進到下一任務；`curate_attitudes` 一次；REVIEW 結構正確；存檔後 `ksa_items` 有 K/S（帶 task_id）與 A（task_id NULL）、`document_versions` 有新版。盯後端 log 無例外。
- [ ] **Step 4:** 通過 → 在 decision log D24 補「實作完成 + 瀏覽器驗證」一行；更新 memory `phase4-status`。

---

## Self-Review

- **Spec 覆蓋**：§3 流程表（②單面、③深問、④curate_ks、⑤curate_attitudes、⑥REVIEW）→ Task 4/5/6/7/8 ✓；§4 決策（單面 D24-b→Task7；KS=pairs() D24-c→Task4 fetch_ksa_pool；A 全域 D24-d→Task4；REVIEW 唯讀 D24-e→Task5/8；idempotency D24-f→Task4 fetch 分離；assemble 拆除 D24-g→Task6；預設全不勾 D24-h→Task7 CurateList；flush 最後一次 D24-i→Task5；ksa_items.task_id D24-j→Task2）✓。
- **Placeholder 掃描**：各 step 皆含實際程式碼/指令；e2e（Task9）為人工 runtime-verify，非單元測試（已標明）。
- **型別一致**：`task_key`（Task1）→ curate_nodes/build_doc/KsaRepo 一致；`flush_ksa(by_task=, attitudes=)` 簽章 Task2/3/5 一致；interrupt payload `curate_ks`/`curate_attitudes` 形狀 Task4 定義、Task7 消費一致；KSA item `{content,source,icap_ref}` 全程一致。
- **已知後續**：`tasks_by_id` 502 修好後把 `fetch_ksa_pool` 升級成 per-task `k_pairs`/`s_pairs`（D24-c 升級路徑，本計畫範圍外）。
