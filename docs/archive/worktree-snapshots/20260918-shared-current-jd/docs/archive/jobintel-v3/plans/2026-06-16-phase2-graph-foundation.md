# Phase ② 圖骨幹 + 前兩節點 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development（建議）或 superpowers:executing-plans。步驟用 `- [ ]` 追蹤。

**Goal:** 在 `feat/v3` 建立 v3 LangGraph 骨幹：升級 langgraph、新巢狀 `InterviewState`、interrupt 驅動的 `pick_profile` / `build_task_pool` 兩節點、checkpointer。**新 graph_v3 與舊 graph 並存、尚不接上 live orchestrator** → 舊流程仍可跑；新圖以 pytest（invoke→interrupt→resume）證明 pattern。

**Architecture:**
- 兩節點**確定性、無 LLM**（只呼叫 `KnowledgeClient` + persist）→ 不需 langchain，minimal venv + langgraph 即可測。
- HITL = `interrupt(payload)` 暫停 → `Command(resume=value)` 接續（取代關鍵字路由）。
- 依賴注入：node 從 `config["configurable"]["deps"]` 取 `Deps(knowledge, persist)`。測試用 `MemorySaver` + fake knowledge + spy persist（無 DB / 無序列化問題）。`AsyncPostgresSaver` 單獨整合測。
- write-through：edit 確認（resume）後才 `persist.flush_tasks`（在 `interrupt()` 之後 → 只跑一次）。

**Tech Stack:** langgraph（升級到最新 1.x）+ langgraph-checkpoint-postgres / pydantic / sqlalchemy / pytest。沿用 Phase ① 的 `KnowledgeClient`、`TaskRepo`、venv（`backend/.venv`，python 3.13）、docker Postgres、`TEST_DATABASE_URL`。

**前置：** 在 `feat/v3`；Phase ① 已合入（6 commits）。依據 spec §4.1/§4.2/§4.4。

> ⚠️ **已知取捨**：單節點 interrupt 語意下，`interrupt()` **之前**的唯讀呼叫（search/task_pool）在 resume 時會**再跑一次**（read-only、idempotent，可接受；日後要省再加快取）。`interrupt()` **之後**的副作用（flush）只跑一次。

---

### Task 1：升級 langgraph + 驗證 HITL/checkpointer API

**Files:** Modify `backend/requirements.txt`；Create `backend/tests/test_langgraph_api.py`

- [ ] **Step 1: venv 安裝最新 langgraph + postgres checkpointer**

Run（venv）：
```
backend/.venv/Scripts/python -m pip install -U "langgraph>=1.0" "langgraph-checkpoint-postgres>=2.0" psycopg[binary]
backend/.venv/Scripts/python -c "import langgraph; print('langgraph', langgraph.__version__)"
```

- [ ] **Step 2: 失敗測試（鎖定 API 表面）**

Create `backend/tests/test_langgraph_api.py`:
```python
def test_hitl_and_checkpointer_api_present():
    from langgraph.graph import StateGraph, START, END          # noqa
    from langgraph.types import interrupt, Command               # noqa
    from langgraph.checkpoint.memory import MemorySaver          # noqa
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # noqa
    assert callable(interrupt)
```
Run：`cd backend && .venv/Scripts/python -m pytest tests/test_langgraph_api.py -q`
Expected：若 import path 與此不符 → 失敗 → 依實際 path 修正本測試與後續節點的 import（這步就是為了把真實 API 釘死）。

- [ ] **Step 3: 通過 + 更新 requirements 版本**

更新 `requirements.txt`：把 `langgraph==0.2.28` 改成實測版本（如 `langgraph==1.0.x`），新增 `langgraph-checkpoint-postgres==<實測>` 與 `psycopg[binary]==<實測>`。
Run：`pytest tests/test_langgraph_api.py -q` → Expected：1 passed。

- [ ] **Step 4: Commit**
```bash
git add backend/requirements.txt backend/tests/test_langgraph_api.py
git commit -m "build: upgrade langgraph to 1.x + postgres checkpointer; pin HITL api"
```

---

### Task 2：v3 巢狀 InterviewState

**Files:** Create `backend/app/graph_v3/__init__.py`、`backend/app/graph_v3/state.py`；Test `backend/tests/test_state_v3.py`

- [ ] **Step 1: 失敗測試**

Create `backend/tests/test_state_v3.py`:
```python
from app.graph_v3.state import InterviewState, new_state


def test_new_state_has_v3_shape():
    s = new_state(job_profile_id="p1", job_title="工程師", job_summary="做事")
    assert s["current_step"] == "pick_profile"
    assert s["profile"]["selected_ocs_code"] is None
    assert s["tasks"] == [] and s["ksa"] == {"knowledge": [], "skills": [], "attitudes": []}
```
Run → Expected：FAIL（模組不存在）。

- [ ] **Step 2: 實作 state**

Create `backend/app/graph_v3/__init__.py`（空）。Create `backend/app/graph_v3/state.py`:
```python
from typing import Any, TypedDict


class ProfilePick(TypedDict):
    candidates: list[dict]
    selected_ocs_code: str | None


class DeepState(TypedDict):
    current_task_index: int
    slots_by_task: dict[str, dict]
    missing_fields: list[str]
    completed_task_ids: list[str]
    retry: dict[str, int]


class KsaDraft(TypedDict):
    knowledge: list[dict]
    skills: list[dict]
    attitudes: list[dict]


class InterviewState(TypedDict):
    job_profile_id: str
    job_title: str
    job_summary: str
    current_step: str            # pick_profile|task_pool|deep|assemble_ksa|build_doc|done
    profile: ProfilePick
    tasks: list[dict]            # 〔可編輯〕每筆含 provenance
    deep: DeepState
    ksa: KsaDraft
    document: dict | None


def new_state(*, job_profile_id: str, job_title: str, job_summary: str = "") -> InterviewState:
    return {
        "job_profile_id": job_profile_id,
        "job_title": job_title,
        "job_summary": job_summary,
        "current_step": "pick_profile",
        "profile": {"candidates": [], "selected_ocs_code": None},
        "tasks": [],
        "deep": {"current_task_index": 0, "slots_by_task": {}, "missing_fields": [],
                 "completed_task_ids": [], "retry": {}},
        "ksa": {"knowledge": [], "skills": [], "attitudes": []},
        "document": None,
    }
```
Run → Expected：1 passed。

- [ ] **Step 3: Commit**
```bash
git add backend/app/graph_v3/__init__.py backend/app/graph_v3/state.py backend/tests/test_state_v3.py
git commit -m "feat(graph_v3): nested InterviewState v3 + new_state factory"
```

---

### Task 3：節點依賴埠（Deps / PersistPort / DbPersist）

**Files:** Create `backend/app/graph_v3/deps.py`；Test `backend/tests/test_deps_dbpersist.py`（需 `TEST_DATABASE_URL`）

- [ ] **Step 1: 失敗測試（DbPersist.flush_tasks 真寫入 + set_selected_ocs）**

Create `backend/tests/test_deps_dbpersist.py`:
```python
import uuid
import pytest
from app.models import JobProfile, User
from app.graph_v3.deps import DbPersist
from app.services.persistence import TaskRepo


@pytest.mark.asyncio
async def test_dbpersist_flush_and_select(db_session):
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@t.co", name="t")
    prof = JobProfile(id=uuid.uuid4(), user_id=user.id, job_title="工程師")
    db_session.add_all([user, prof])
    await db_session.flush()

    persist = DbPersist(session=db_session)
    await persist.set_selected_ocs(prof.id, "OC1")
    await persist.flush_tasks(prof.id, [{"task_name": "巡檢", "source": "catalog"}])

    assert (await db_session.get(JobProfile, prof.id)).selected_ocs_code == "OC1"
    assert (await TaskRepo(db_session).hydrate(prof.id))[0]["task_name"] == "巡檢"
```
Run → Expected：FAIL（模組不存在）。

- [ ] **Step 2: 實作 deps**

Create `backend/app/graph_v3/deps.py`:
```python
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobProfile
from app.services.knowledge.base import KnowledgeClient
from app.services.persistence import TaskRepo


class PersistPort(Protocol):
    async def set_selected_ocs(self, job_profile_id: UUID, ocs_code: str) -> None: ...
    async def flush_tasks(self, job_profile_id: UUID, tasks: list[dict]) -> None: ...


class DbPersist:
    """正式環境的 PersistPort：用一個 AsyncSession 寫業務表。"""
    def __init__(self, session: AsyncSession):
        self.s = session

    async def set_selected_ocs(self, job_profile_id: UUID, ocs_code: str) -> None:
        prof = await self.s.get(JobProfile, job_profile_id)
        if prof:
            prof.selected_ocs_code = ocs_code
        await self.s.flush()

    async def flush_tasks(self, job_profile_id: UUID, tasks: list[dict]) -> None:
        await TaskRepo(self.s).flush(job_profile_id, tasks)


@dataclass
class Deps:
    knowledge: KnowledgeClient
    persist: PersistPort
```
Run（含 DB）→ Expected：1 passed。

- [ ] **Step 3: Commit**
```bash
git add backend/app/graph_v3/deps.py backend/tests/test_deps_dbpersist.py
git commit -m "feat(graph_v3): Deps + PersistPort + DbPersist adapter"
```

---

### Task 4：pick_profile 節點

**Files:** Create `backend/app/graph_v3/nodes.py`；Test `backend/tests/test_node_pick_profile.py`

- [ ] **Step 1: 失敗測試（用單節點圖 + MemorySaver 驗 interrupt→resume）**

Create `backend/tests/conftest_graph.py`（共用 fakes）:
```python
import uuid
from app.services.knowledge.models import SearchResult, TaskPool


class FakeKnowledge:
    def __init__(self, search=None, pool=None):
        self._search = search or SearchResult(mode="dense", hits=[])
        self._pool = pool or TaskPool(groups=[])
        self.calls = []

    async def search(self, query, **kw):
        self.calls.append(("search", query)); return self._search

    async def task_pool(self, ocs_codes, **kw):
        self.calls.append(("task_pool", ocs_codes)); return self._pool

    async def pairs(self, ocs_code): ...
    async def tasks_by_id(self, ids): ...
    async def healthz(self): return True


class SpyPersist:
    def __init__(self): self.selected = None; self.flushed = None
    async def set_selected_ocs(self, pid, ocs): self.selected = (str(pid), ocs)
    async def flush_tasks(self, pid, tasks): self.flushed = (str(pid), tasks)
```

Create `backend/tests/test_node_pick_profile.py`:
```python
import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.state import new_state
from app.graph_v3.nodes import pick_profile
from app.graph_v3.deps import Deps
from app.graph_v3.state import InterviewState
from app.services.knowledge.models import SearchResult, Hit
from tests.conftest_graph import FakeKnowledge, SpyPersist


def _one_node_graph():
    g = StateGraph(InterviewState)
    g.add_node("pick_profile", pick_profile)
    g.add_edge(START, "pick_profile")
    g.add_edge("pick_profile", END)
    return g.compile(checkpointer=MemorySaver())


@pytest.mark.asyncio
async def test_pick_profile_interrupts_then_persists_selection():
    fake = FakeKnowledge(search=SearchResult(mode="dense", hits=[
        Hit(id="p1", ocs_code="OC1", chunk_level="profile", job_title="工程師")]))
    spy = SpyPersist()
    graph = _one_node_graph()
    cfg = {"configurable": {"thread_id": "t1", "deps": Deps(knowledge=fake, persist=spy)}}

    out = await graph.ainvoke(new_state(job_profile_id="p1", job_title="工程師"), cfg)
    intr = out["__interrupt__"][0].value
    assert intr["kind"] == "select_profile" and intr["candidates"][0]["ocs_code"] == "OC1"

    out2 = await graph.ainvoke(Command(resume={"ocs_code": "OC1"}), cfg)
    assert out2["profile"]["selected_ocs_code"] == "OC1"
    assert out2["current_step"] == "task_pool"
    assert spy.selected == ("p1", "OC1")
```
Run → Expected：FAIL（`pick_profile` 不存在）。

- [ ] **Step 2: 實作 pick_profile**

Create `backend/app/graph_v3/nodes.py`:
```python
from langgraph.types import interrupt

from app.graph_v3.state import InterviewState


async def pick_profile(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    query = state.get("job_summary") or state["job_title"]
    res = await deps.knowledge.search(query, level="profile", top_k=8)
    candidates = [h.model_dump() for h in res.hits]

    selected = interrupt({"kind": "select_profile", "candidates": candidates})
    ocs = selected.get("ocs_code") if isinstance(selected, dict) else str(selected)

    await deps.persist.set_selected_ocs(state["job_profile_id"], ocs)
    return {
        "profile": {"candidates": candidates, "selected_ocs_code": ocs},
        "current_step": "task_pool",
    }
```
Run → Expected：1 passed。

- [ ] **Step 3: Commit**
```bash
git add backend/app/graph_v3/nodes.py backend/tests/conftest_graph.py backend/tests/test_node_pick_profile.py
git commit -m "feat(graph_v3): pick_profile node (search -> interrupt -> persist selection)"
```

---

### Task 5：build_task_pool 節點

**Files:** Modify `backend/app/graph_v3/nodes.py`；Test `backend/tests/test_node_task_pool.py`

- [ ] **Step 1: 失敗測試（task_pool → interrupt(edit) → resume 寫回 tasks + flush）**

Create `backend/tests/test_node_task_pool.py`:
```python
import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.nodes import build_task_pool
from app.graph_v3.deps import Deps
from app.services.knowledge.models import TaskPool, PoolGroup, PoolUnit, PoolTask
from tests.conftest_graph import FakeKnowledge, SpyPersist


def _graph():
    g = StateGraph(InterviewState)
    g.add_node("build_task_pool", build_task_pool)
    g.add_edge(START, "build_task_pool")
    g.add_edge("build_task_pool", END)
    return g.compile(checkpointer=MemorySaver())


@pytest.mark.asyncio
async def test_task_pool_interrupt_then_flush_edited():
    pool = TaskPool(groups=[PoolGroup(ocs_code="OC1", job_title="工程師", units=[
        PoolUnit(unit_id="U1", unit_title="巡檢類", tasks=[
            PoolTask(id="OC1-T1.1", task_id="T1.1", task_title="例行巡檢")])])])
    fake = FakeKnowledge(pool=pool)
    spy = SpyPersist()
    graph = _graph()
    s = new_state(job_profile_id="p1", job_title="工程師")
    s["profile"]["selected_ocs_code"] = "OC1"
    cfg = {"configurable": {"thread_id": "t1", "deps": Deps(knowledge=fake, persist=spy)}}

    out = await graph.ainvoke(s, cfg)
    intr = out["__interrupt__"][0].value
    assert intr["kind"] == "edit_tasks"
    assert intr["tasks"][0]["task_name"] == "例行巡檢" and intr["tasks"][0]["source"] == "catalog"

    edited = [{"task_name": "例行巡檢", "source": "catalog",
               "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"}},
              {"task_name": "公司自訂任務", "source": "company"}]
    out2 = await graph.ainvoke(Command(resume={"tasks": edited}), cfg)
    assert [t["task_name"] for t in out2["tasks"]] == ["例行巡檢", "公司自訂任務"]
    assert out2["current_step"] == "deep"
    assert spy.flushed[0] == "p1" and len(spy.flushed[1]) == 2
```
Run → Expected：FAIL（`build_task_pool` 不存在）。

- [ ] **Step 2: 實作 build_task_pool（append 到 nodes.py）**
```python
def _pool_to_tasks(pool) -> list[dict]:
    out = []
    for g in pool.groups:
        for u in g.units:
            for t in u.tasks:
                out.append({
                    "task_name": t.task_title,
                    "source": "catalog",
                    "indexer_ref": {"ocs_code": g.ocs_code, "task_id": t.task_id},
                    "activity_examples": t.activity_examples,
                })
    return out


async def build_task_pool(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    ocs = state["profile"]["selected_ocs_code"]
    pool = await deps.knowledge.task_pool([ocs] if ocs else [])
    proposed = _pool_to_tasks(pool)

    edited = interrupt({"kind": "edit_tasks", "tasks": proposed})
    tasks = edited.get("tasks", proposed) if isinstance(edited, dict) else proposed

    await deps.persist.flush_tasks(state["job_profile_id"], tasks)
    return {"tasks": tasks, "current_step": "deep"}
```
Run → Expected：1 passed。

- [ ] **Step 3: Commit**
```bash
git add backend/app/graph_v3/nodes.py backend/tests/test_node_task_pool.py
git commit -m "feat(graph_v3): build_task_pool node (task_pool -> interrupt edit -> flush)"
```

---

### Task 6：graph_v3 組裝 + 端到端 interrupt/resume

**Files:** Create `backend/app/graph_v3/graph.py`；Test `backend/tests/test_graph_v3_e2e.py`

- [ ] **Step 1: 失敗測試（兩節點端到端：select → edit → done）**

Create `backend/tests/test_graph_v3_e2e.py`:
```python
import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.graph import build_graph_v3
from app.graph_v3.state import new_state
from app.graph_v3.deps import Deps
from app.services.knowledge.models import SearchResult, Hit, TaskPool, PoolGroup, PoolUnit, PoolTask
from tests.conftest_graph import FakeKnowledge, SpyPersist


@pytest.mark.asyncio
async def test_full_two_node_slice():
    fake = FakeKnowledge(
        search=SearchResult(mode="dense", hits=[Hit(id="p1", ocs_code="OC1", chunk_level="profile")]),
        pool=TaskPool(groups=[PoolGroup(ocs_code="OC1", units=[
            PoolUnit(tasks=[PoolTask(id="x", task_id="T1.1", task_title="巡檢")])])]))
    spy = SpyPersist()
    graph = build_graph_v3(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "t1", "deps": Deps(knowledge=fake, persist=spy)}}

    out = await graph.ainvoke(new_state(job_profile_id="p1", job_title="工程師"), cfg)
    assert out["__interrupt__"][0].value["kind"] == "select_profile"

    out = await graph.ainvoke(Command(resume={"ocs_code": "OC1"}), cfg)
    assert out["__interrupt__"][0].value["kind"] == "edit_tasks"

    out = await graph.ainvoke(Command(resume={"tasks": [{"task_name": "巡檢", "source": "catalog"}]}), cfg)
    assert out["current_step"] == "deep"
    assert spy.selected == ("p1", "OC1") and spy.flushed[0] == "p1"
```
Run → Expected：FAIL（`build_graph_v3` 不存在）。

- [ ] **Step 2: 實作 graph_v3**

Create `backend/app/graph_v3/graph.py`:
```python
from langgraph.graph import StateGraph, START, END

from app.graph_v3.state import InterviewState
from app.graph_v3.nodes import pick_profile, build_task_pool


def build_graph_v3(checkpointer=None):
    """v3 骨幹（Phase ②：前兩節點；深問子圖等後續 phase 接上）。"""
    g = StateGraph(InterviewState)
    g.add_node("pick_profile", pick_profile)
    g.add_node("build_task_pool", build_task_pool)
    g.add_edge(START, "pick_profile")
    g.add_edge("pick_profile", "build_task_pool")
    g.add_edge("build_task_pool", END)
    return g.compile(checkpointer=checkpointer)
```
Run → Expected：1 passed。

- [ ] **Step 3: Commit**
```bash
git add backend/app/graph_v3/graph.py backend/tests/test_graph_v3_e2e.py
git commit -m "feat(graph_v3): assemble pick_profile -> build_task_pool graph + e2e interrupt/resume"
```

---

### Task 7：AsyncPostgresSaver factory + checkpointer 持久化整合測

**Files:** Create `backend/app/graph_v3/checkpointer.py`；Test `backend/tests/test_checkpointer_pg.py`（需 `TEST_DATABASE_URL`）

- [ ] **Step 1: 失敗測試（同 thread 跨兩次 ainvoke 還原 state；用無依賴 trivial 圖避開序列化）**

Create `backend/tests/test_checkpointer_pg.py`:
```python
import os
import uuid
import pytest
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

from app.graph_v3.checkpointer import open_pg_checkpointer

PG = os.getenv("TEST_DATABASE_URL", "")


class _S(TypedDict):
    n: int


async def _inc(state: _S) -> dict:
    return {"n": state["n"] + 1}


@pytest.mark.skipif(not PG, reason="TEST_DATABASE_URL not set")
@pytest.mark.asyncio
async def test_pg_checkpointer_persists_thread_state():
    async with open_pg_checkpointer(PG) as saver:
        g = StateGraph(_S)
        g.add_node("inc", _inc); g.add_edge(START, "inc"); g.add_edge("inc", END)
        graph = g.compile(checkpointer=saver)
        cfg = {"configurable": {"thread_id": f"t-{uuid.uuid4()}"}}
        await graph.ainvoke({"n": 0}, cfg)
        snap = await graph.aget_state(cfg)
        assert snap.values["n"] == 1
```
Run → Expected：FAIL（模組不存在）。

- [ ] **Step 2: 實作 checkpointer factory**

> Task 1 已確認 import path。`AsyncPostgresSaver.from_conn_string` 需 psycopg 連線字串（`postgresql://...`，非 `+asyncpg`）。首次需 `await saver.setup()` 建表。

Create `backend/app/graph_v3/checkpointer.py`:
```python
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


def _to_psycopg_dsn(url: str) -> str:
    # 接受 sqlalchemy 風格 → 轉成 psycopg 可用 dsn
    return url.replace("postgresql+asyncpg://", "postgresql://").replace("+psycopg", "")


@asynccontextmanager
async def open_pg_checkpointer(database_url: str):
    dsn = _to_psycopg_dsn(database_url)
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        await saver.setup()
        yield saver
```
Run（含 DB）→ Expected：1 passed（若 `from_conn_string`/`setup` 簽名與實測不符，依 Task 1 結果微調）。

- [ ] **Step 3: Commit**
```bash
git add backend/app/graph_v3/checkpointer.py backend/tests/test_checkpointer_pg.py
git commit -m "feat(graph_v3): AsyncPostgresSaver factory + thread persistence integration test"
```

---

## 完成後
- 全測試：`cd backend && TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/jobintel .venv/Scripts/python -m pytest -q`
- Final review（subagent-driven 最後一關）。
- **產出**：v3 graph 骨幹（state / deps / pick_profile / build_task_pool / graph_v3 / PostgresSaver），interrupt/resume + checkpointer pattern 經 pytest 證明。**舊 graph 未動、未 live-wire**。
- **下一步**：
  - **Phase ②-FE**：CopilotKit provider/runtime + `useCoAgent` + `renderAndWaitForResponse` 接這兩個 interrupt（select_profile / edit_tasks）→ 第一條真 UI 端到端。
  - **Phase ③**：deep_interview 子圖（star→five_w2h→indicator，需 langchain + LLM gateway per-node）。
  - live-wire（orchestrator 改用 graph_v3、處理 deps 注入與 PostgresSaver 序列化、移除舊 graph/icap_*）排在前兩節點 + FE 驗證後。

## Self-Review
- Spec 覆蓋：§4.1 控制流（interrupt/checkpointer）✓、§4.2 state ✓、§4.4 persist 接點（DbPersist）✓。
- 無 placeholder：每 task 真 test + 實作碼；唯一「實測微調」點在 Task 1（API path）與 Task 7（checkpointer 簽名），且都有驗證步驟兜底。
- 不破壞：graph_v3 為**新模組**，未改舊 graph/orchestrator；節點無 LLM → minimal venv 可測。
- 型別一致：`Deps(knowledge, persist)`、`PersistPort.set_selected_ocs/flush_tasks`、interrupt kinds `select_profile`/`edit_tasks` 跨 task 對齊。
