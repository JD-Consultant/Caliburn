# Phase ④ 收尾：assemble_ksa + build_doc Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **本地記錄（untracked，不 commit 進 git）。** 日期：2026-06-17。依據 spec `2026-06-16-jobintel-ai-v3-architecture.md` §2/§9.4/§9.5/§12、決策 `2026-06-16-refactor-decision-log.md` D6/D8/D9/**D13/D14**。

**Goal:** 深問迴圈結束後，接上 `assemble_ksa`（從 catalog 取 K/S/A + 公司補充 → 人編輯 → flush `ksa_items`）與 `build_doc`（**deterministic** 組裝 OCS 文件 → 寫 `document_versions` → preview），完成 `finish_deep → assemble_ksa → build_doc → done` 的端到端骨幹。

**Architecture:** 沿用 graph_v3 既有模式——節點透過 `config["configurable"]["deps"]` 取 `KnowledgeClient`/`PersistPort`/`LlmPort`，HITL 用 `interrupt()`+`Command(resume)`。assemble_ksa/build_doc **幾乎全 deterministic**（D13）：K/S/A 來自 indexer `pairs()`、OCU 分組直接用 catalog `task_pool` 的 unit 結構、編碼與注入全程式化、LLM 不用。豐欄位**不落** `company_tasks`（D14）；of-record = `ksa_items` + `document_versions.content`(JSONB)。

**Tech Stack:** langgraph 1.2.5 + SQLAlchemy 2.0 async + Pydantic v2 + pytest/pytest-asyncio。沿用 `KnowledgeClient`、`Deps`、`backend/.venv`（python 3.13）、docker Postgres、`TEST_DATABASE_URL`。

## Global Constraints

- 分支 `feat/v3`；`master` 不動。
- **不 import 舊鏈**：`app.graph.nodes.ocs_builder`、`app.services.icap_retriever`、`app.graph.llm_gateway` 一律不 import（綁死 pgvector/被移除鏈）。重用 = 於 graph_v3 重寫其輸出結構/編碼邏輯。
- **無新 migration**（D14）：`ksa_items`、`document_versions` 表已存在；本階段不加欄、不改 schema。
- KsaRepo/DocRepo 比照 `app/services/persistence.py:TaskRepo` 的 hydrate/flush 風格（D9，row-level upsert）。
- TDD：每節點/repo 先寫失敗測試→watch fail→最小實作→pass→commit。repo 測試需 `TEST_DATABASE_URL`。
- 純資料模組可重用（`app.graph.constants`），但**不得**觸發舊 retrieval/gateway import。

---

### Task 1：build_task_pool 保留 catalog unit 資訊（deterministic OCU 分組的前置）

**Files:**
- Modify: `backend/app/graph_v3/nodes.py`（`_pool_to_tasks`）
- Test: `backend/tests/test_node_task_pool.py`（新增一個斷言）

**Interfaces:**
- Produces: 每個 task dict 額外帶 `unit_id: str`、`unit_title: str`（additive）。build_doc（Task 5）依此分組。

- [ ] **Step 1: 失敗測試（task 帶 unit_id/unit_title）**

在 `backend/tests/test_node_task_pool.py` 末尾新增：
```python
@pytest.mark.asyncio
async def test_pool_tasks_carry_unit_info():
    from app.services.knowledge.models import TaskPool, PoolGroup, PoolUnit, PoolTask
    from app.graph_v3.nodes import _pool_to_tasks
    pool = TaskPool(groups=[PoolGroup(ocs_code="OC1", units=[
        PoolUnit(unit_id="U1", unit_title="預防保養", tasks=[
            PoolTask(id="x", task_id="T1.1", task_title="巡檢")])])])
    tasks = _pool_to_tasks(pool)
    assert tasks[0]["unit_id"] == "U1"
    assert tasks[0]["unit_title"] == "預防保養"
```
Run: `cd backend && .venv/Scripts/python -m pytest tests/test_node_task_pool.py::test_pool_tasks_carry_unit_info -v`
Expected: FAIL（`KeyError: 'unit_id'`）。

- [ ] **Step 2: 加 unit 欄位到 `_pool_to_tasks`**

`backend/app/graph_v3/nodes.py` 的 `_pool_to_tasks`，把 append 的 dict 改成：
```python
                out.append({
                    "task_name": t.task_title,
                    "source": "catalog",
                    "indexer_ref": {"ocs_code": g.ocs_code, "task_id": t.task_id},
                    "unit_id": u.unit_id,
                    "unit_title": u.unit_title,
                    "activity_examples": t.activity_examples,
                })
```

- [ ] **Step 3: 通過測試 + 既有 task_pool 測試不破**

Run: `.venv/Scripts/python -m pytest tests/test_node_task_pool.py -v`
Expected: 全 pass。

- [ ] **Step 4: Commit**
```bash
git add backend/app/graph_v3/nodes.py backend/tests/test_node_task_pool.py
git commit -m "feat(graph_v3): carry catalog unit_id/unit_title on pool tasks (for deterministic OCU grouping)"
```

---

### Task 2：KsaRepo（hydrate/flush `ksa_items`，doc-level，row-level upsert）

**Files:**
- Modify: `backend/app/services/persistence.py`（新增 `KsaRepo`）
- Test: `backend/tests/test_persistence_ksarepo.py`（需 `TEST_DATABASE_URL`）

**Interfaces:**
- Consumes: `app.models.KsaItem`（欄位 `ksa_type` K|S|A、`content`、`source_type`、`icap_ref`、`job_profile_id`；`task_id` 本階段留 NULL）。
- Produces:
  - `KsaRepo(session).flush(job_profile_id: UUID, ksa: dict) -> None`，`ksa = {"knowledge": [item], "skills": [item], "attitudes": [item]}`，`item = {"content": str, "source": "catalog"|"company", "icap_ref": str|None}`。
  - `KsaRepo(session).hydrate(job_profile_id: UUID) -> dict`，回 `{"knowledge": [...], "skills": [...], "attitudes": [...]}`（item 形狀同上 + `id`）。

- [ ] **Step 1: 失敗測試（flush→hydrate roundtrip + 冪等保 row id）**

Create `backend/tests/test_persistence_ksarepo.py`:
```python
import uuid
import pytest
from app.models import JobProfile, User
from app.services.persistence import KsaRepo


async def _profile(db_session):
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@t.co", name="t")
    prof = JobProfile(id=uuid.uuid4(), user_id=user.id, job_title="工程師")
    db_session.add_all([user, prof])
    await db_session.flush()
    return prof


@pytest.mark.asyncio
async def test_ksa_flush_then_hydrate(db_session):
    prof = await _profile(db_session)
    repo = KsaRepo(db_session)
    ksa = {
        "knowledge": [{"content": "設備原理", "source": "catalog", "icap_ref": "K01"}],
        "skills": [{"content": "點檢操作", "source": "company", "icap_ref": None}],
        "attitudes": [{"content": "細心", "source": "company", "icap_ref": None}],
    }
    await repo.flush(prof.id, ksa)
    got = await repo.hydrate(prof.id)
    assert [k["content"] for k in got["knowledge"]] == ["設備原理"]
    assert got["knowledge"][0]["source"] == "catalog" and got["knowledge"][0]["icap_ref"] == "K01"
    assert got["skills"][0]["content"] == "點檢操作"
    assert got["attitudes"][0]["content"] == "細心"


@pytest.mark.asyncio
async def test_ksa_flush_idempotent_keeps_row_id(db_session):
    prof = await _profile(db_session)
    repo = KsaRepo(db_session)
    await repo.flush(prof.id, {"knowledge": [{"content": "設備原理", "source": "catalog", "icap_ref": "K01"}],
                               "skills": [], "attitudes": []})
    first = (await repo.hydrate(prof.id))["knowledge"][0]["id"]
    # 再 flush 同 content（K 類）→ update 同 row，不新建
    await repo.flush(prof.id, {"knowledge": [{"content": "設備原理", "source": "company", "icap_ref": None}],
                               "skills": [], "attitudes": []})
    rows = await repo.hydrate(prof.id)
    assert len(rows["knowledge"]) == 1 and rows["knowledge"][0]["id"] == first
    assert rows["knowledge"][0]["source"] == "company"   # 已更新
```
Run: `TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/jobintel .venv/Scripts/python -m pytest tests/test_persistence_ksarepo.py -v`
Expected: FAIL（`KsaRepo` 不存在）。

- [ ] **Step 2: 實作 KsaRepo（append 到 persistence.py）**

在 `backend/app/services/persistence.py` 頂部 import 補 `KsaItem`：
```python
from app.models import CompanyTask, KsaItem
```
檔末 append：
```python
_KSA_TYPES = (("knowledge", "K"), ("skills", "S"), ("attitudes", "A"))
_SRC_TO_DB = {"catalog": "icap_official", "company": "company_defined"}
_DB_TO_SRC = {v: k for k, v in _SRC_TO_DB.items()}


class KsaRepo:
    """ksa_items 的 doc-level hydrate/flush。以 (job_profile_id, ksa_type, content)
    為穩定鍵 row-level upsert：保 row id 穩定。task_id 本階段留 NULL（per-task 連結為未來）。"""

    def __init__(self, session: AsyncSession):
        self.s = session

    async def hydrate(self, job_profile_id: UUID) -> dict:
        rows = (await self.s.execute(
            select(KsaItem).where(KsaItem.job_profile_id == job_profile_id)
        )).scalars().all()
        out: dict[str, list[dict]] = {"knowledge": [], "skills": [], "attitudes": []}
        bucket = {"K": "knowledge", "S": "skills", "A": "attitudes"}
        for r in rows:
            key = bucket.get(r.ksa_type)
            if key:
                out[key].append({"id": str(r.id), "content": r.content,
                                 "source": _DB_TO_SRC.get(r.source_type, "company"),
                                 "icap_ref": r.icap_ref})
        return out

    async def flush(self, job_profile_id: UUID, ksa: dict) -> None:
        existing = {(r.ksa_type, r.content): r for r in (await self.s.execute(
            select(KsaItem).where(KsaItem.job_profile_id == job_profile_id)
        )).scalars().all()}
        seen: set[tuple[str, str]] = set()
        for field, code in _KSA_TYPES:
            for item in ksa.get(field, []):
                content = (item.get("content") or "").strip()
                if not content:
                    continue
                key = (code, content)
                seen.add(key)
                row = existing.get(key) or KsaItem(
                    job_profile_id=job_profile_id, ksa_type=code, content=content)
                row.source_type = _SRC_TO_DB.get(item.get("source", "company"), "company_defined")
                row.icap_ref = item.get("icap_ref")
                if key not in existing:
                    self.s.add(row)
        for key, row in existing.items():
            if key not in seen:
                await self.s.delete(row)
        await self.s.flush()
```

- [ ] **Step 3: 通過測試**

Run: `TEST_DATABASE_URL=... .venv/Scripts/python -m pytest tests/test_persistence_ksarepo.py -v`
Expected: 2 passed.

- [ ] **Step 4: Commit**
```bash
git add backend/app/services/persistence.py backend/tests/test_persistence_ksarepo.py
git commit -m "feat(persistence): KsaRepo doc-level hydrate/flush with stable-id upsert"
```

---

### Task 3：DocRepo（寫/讀 `document_versions`，版本遞增）

**Files:**
- Modify: `backend/app/services/persistence.py`（新增 `DocRepo`）
- Test: `backend/tests/test_persistence_docrepo.py`（需 `TEST_DATABASE_URL`）

**Interfaces:**
- Consumes: `app.models.DocumentVersion`（`version` int、`format` text、`content` JSONB、`status` text、`job_profile_id`）。
- Produces:
  - `DocRepo(session).save(job_profile_id: UUID, content: dict, fmt: str = "json") -> dict`，回 `{"id", "version", "format", "content", "status"}`，version = 現有 max+1（無則 1）。
  - `DocRepo(session).latest(job_profile_id: UUID) -> dict | None`。

- [ ] **Step 1: 失敗測試（save 遞增版本 + latest 取最新）**

Create `backend/tests/test_persistence_docrepo.py`:
```python
import uuid
import pytest
from app.models import JobProfile, User
from app.services.persistence import DocRepo


async def _profile(db_session):
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@t.co", name="t")
    prof = JobProfile(id=uuid.uuid4(), user_id=user.id, job_title="工程師")
    db_session.add_all([user, prof])
    await db_session.flush()
    return prof


@pytest.mark.asyncio
async def test_save_increments_version_and_latest(db_session):
    prof = await _profile(db_session)
    repo = DocRepo(db_session)
    v1 = await repo.save(prof.id, {"ocs_profile": {"ocs_code": "ENT-001"}})
    assert v1["version"] == 1 and v1["format"] == "json"
    v2 = await repo.save(prof.id, {"ocs_profile": {"ocs_code": "ENT-002"}})
    assert v2["version"] == 2
    latest = await repo.latest(prof.id)
    assert latest["version"] == 2 and latest["content"]["ocs_profile"]["ocs_code"] == "ENT-002"
```
Run: `TEST_DATABASE_URL=... .venv/Scripts/python -m pytest tests/test_persistence_docrepo.py -v`
Expected: FAIL（`DocRepo` 不存在）。

- [ ] **Step 2: 實作 DocRepo（append 到 persistence.py）**

頂部 import 補 `DocumentVersion`、`func`：
```python
from sqlalchemy import func, select
from app.models import CompanyTask, DocumentVersion, KsaItem
```
檔末 append：
```python
class DocRepo:
    """document_versions：每次 save 版本遞增；content 為 OCS 文件 JSONB。"""

    def __init__(self, session: AsyncSession):
        self.s = session

    async def save(self, job_profile_id: UUID, content: dict, fmt: str = "json") -> dict:
        cur_max = (await self.s.execute(
            select(func.max(DocumentVersion.version))
            .where(DocumentVersion.job_profile_id == job_profile_id)
        )).scalar()
        row = DocumentVersion(job_profile_id=job_profile_id,
                              version=(cur_max or 0) + 1, format=fmt,
                              content=content, status="draft")
        self.s.add(row)
        await self.s.flush()
        return self._to_dict(row)

    async def latest(self, job_profile_id: UUID) -> dict | None:
        row = (await self.s.execute(
            select(DocumentVersion)
            .where(DocumentVersion.job_profile_id == job_profile_id)
            .order_by(DocumentVersion.version.desc())
        )).scalars().first()
        return self._to_dict(row) if row else None

    @staticmethod
    def _to_dict(r: DocumentVersion) -> dict:
        return {"id": str(r.id), "version": r.version, "format": r.format,
                "content": r.content, "status": r.status}
```

- [ ] **Step 3: 通過測試**

Run: `TEST_DATABASE_URL=... .venv/Scripts/python -m pytest tests/test_persistence_docrepo.py -v`
Expected: 1 passed.

- [ ] **Step 4: Commit**
```bash
git add backend/app/services/persistence.py backend/tests/test_persistence_docrepo.py
git commit -m "feat(persistence): DocRepo save/latest for document_versions"
```

---

### Task 4：PersistPort 擴充 + DbPersist/InMemoryPersist 實作 ksa/doc

**Files:**
- Modify: `backend/app/graph_v3/deps.py`（`PersistPort` + `DbPersist`）
- Modify: `backend/app/graph_v3/stubs.py`（`InMemoryPersist`）
- Test: `backend/tests/test_deps_dbpersist.py`（新增斷言）

**Interfaces:**
- Produces（PersistPort additive 方法，節點呼叫）：
  - `async def flush_ksa(self, job_profile_id: UUID, ksa: dict) -> None`
  - `async def save_document(self, job_profile_id: UUID, content: dict) -> dict`

- [ ] **Step 1: 失敗測試（DbPersist 轉呼 KsaRepo/DocRepo）**

在 `backend/tests/test_deps_dbpersist.py` 末尾新增：
```python
@pytest.mark.asyncio
async def test_dbpersist_flush_ksa_and_save_document(db_session):
    import uuid
    from app.models import JobProfile, User
    from app.graph_v3.deps import DbPersist
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@t.co", name="t")
    prof = JobProfile(id=uuid.uuid4(), user_id=user.id, job_title="工程師")
    db_session.add_all([user, prof])
    await db_session.flush()

    p = DbPersist(db_session)
    await p.flush_ksa(prof.id, {"knowledge": [{"content": "A", "source": "catalog", "icap_ref": "K01"}],
                                "skills": [], "attitudes": []})
    doc = await p.save_document(prof.id, {"ocs_profile": {"ocs_code": "ENT-001"}})
    assert doc["version"] == 1
```
Run: `TEST_DATABASE_URL=... .venv/Scripts/python -m pytest tests/test_deps_dbpersist.py::test_dbpersist_flush_ksa_and_save_document -v`
Expected: FAIL（`flush_ksa` 不存在）。

- [ ] **Step 2: 擴 PersistPort + DbPersist（deps.py）**

`PersistPort` Protocol 內補兩個方法簽章：
```python
    async def flush_ksa(self, job_profile_id: UUID, ksa: dict) -> None: ...
    async def save_document(self, job_profile_id: UUID, content: dict) -> dict: ...
```
import 補 repos：
```python
from app.services.persistence import TaskRepo, KsaRepo, DocRepo
```
`DbPersist` 內補：
```python
    async def flush_ksa(self, job_profile_id: UUID, ksa: dict) -> None:
        await KsaRepo(self.s).flush(job_profile_id, ksa)

    async def save_document(self, job_profile_id: UUID, content: dict) -> dict:
        return await DocRepo(self.s).save(job_profile_id, content)
```

- [ ] **Step 3: 擴 InMemoryPersist（stubs.py，demo 用）**

`backend/app/graph_v3/stubs.py` 的 `InMemoryPersist`，`__init__` 加 `self.ksa = {}; self.docs = {}`，並補：
```python
    async def flush_ksa(self, job_profile_id, ksa) -> None:
        self.ksa[str(job_profile_id)] = ksa

    async def save_document(self, job_profile_id, content) -> dict:
        v = len(self.docs.get(str(job_profile_id), [])) + 1
        self.docs.setdefault(str(job_profile_id), []).append(content)
        return {"id": f"mem-{v}", "version": v, "format": "json",
                "content": content, "status": "draft"}
```

- [ ] **Step 4: 通過測試（含既有 dbpersist 測試）**

Run: `TEST_DATABASE_URL=... .venv/Scripts/python -m pytest tests/test_deps_dbpersist.py -v`
Expected: 全 pass。

- [ ] **Step 5: Commit**
```bash
git add backend/app/graph_v3/deps.py backend/app/graph_v3/stubs.py backend/tests/test_deps_dbpersist.py
git commit -m "feat(graph_v3): PersistPort flush_ksa/save_document (DbPersist + InMemoryPersist)"
```

---

### Task 5：assemble_ksa 節點（catalog pairs + 公司補充 + interrupt 編輯 + flush）

**Files:**
- Create: `backend/app/graph_v3/assemble_nodes.py`（`assemble_ksa`）
- Test: `backend/tests/test_node_assemble_ksa.py`

**Interfaces:**
- Consumes: `state["profile"]["selected_ocs_code"]`、`deps.knowledge.pairs(ocs_code) -> Pairs`（`Pairs.knowledge/skills/attitudes: list[Pair{code,name}]`）、`deps.persist.flush_ksa`。
- Produces: `assemble_ksa(state, config) -> {"ksa": {...}, "current_step": "build_doc"}`；interrupt kind `"edit_ksa"`，payload `{"kind": "edit_ksa", "ksa": draft}`，resume 值 `{"ksa": {...}}` 或直接 `{...}`。

- [ ] **Step 1: 失敗測試（catalog pairs → draft → interrupt → 編輯後 flush）**

Create `backend/tests/test_node_assemble_ksa.py`:
```python
import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.assemble_nodes import assemble_ksa
from app.graph_v3.deps import Deps
from app.services.knowledge.models import Pairs, Pair
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm


def _graph():
    g = StateGraph(InterviewState)
    g.add_node("assemble_ksa", assemble_ksa)
    g.add_edge(START, "assemble_ksa")
    g.add_edge("assemble_ksa", END)
    return g.compile(checkpointer=MemorySaver())


def _state():
    s = new_state(job_profile_id="p1", job_title="設備維護工程師")
    s["profile"] = {"candidates": [], "selected_ocs_code": "OC1"}
    return s


@pytest.mark.asyncio
async def test_assemble_ksa_from_catalog_then_edit_and_flush(monkeypatch):
    pairs = Pairs(ocs_code="OC1",
                  knowledge=[Pair(code="K01", name="設備原理")],
                  skills=[Pair(code="S01", name="點檢操作")],
                  attitudes=[Pair(code="A01", name="細心")])
    fake = FakeKnowledge()
    async def _pairs(ocs_code): return pairs
    monkeypatch.setattr(fake, "pairs", _pairs)
    spy = SpyPersist()
    graph = _graph()
    cfg = {"configurable": {"thread_id": "t1",
                            "deps": Deps(knowledge=fake, persist=spy, llm=FakeLlm())}}

    out = await graph.ainvoke(_state(), cfg)
    payload = out["__interrupt__"][0].value
    assert payload["kind"] == "edit_ksa"
    # draft 帶 catalog 來源 + icap_ref
    assert payload["ksa"]["knowledge"][0] == {"content": "設備原理", "source": "catalog", "icap_ref": "K01"}

    # 人編輯：加一條公司補充
    edited = {"knowledge": payload["ksa"]["knowledge"] + [{"content": "公司SOP", "source": "company", "icap_ref": None}],
              "skills": payload["ksa"]["skills"], "attitudes": payload["ksa"]["attitudes"]}
    out = await graph.ainvoke(Command(resume={"ksa": edited}), cfg)

    assert out["current_step"] == "build_doc"
    assert len(out["ksa"]["knowledge"]) == 2
    assert spy.ksa_flushed[0] == "p1"
    assert len(spy.ksa_flushed[1]["knowledge"]) == 2
```
並在 `backend/tests/conftest_graph.py` 的 `SpyPersist` 加 ksa/doc 記錄：
```python
class SpyPersist:
    def __init__(self):
        self.selected = None; self.flushed = None
        self.ksa_flushed = None; self.doc_saved = None
    async def set_selected_ocs(self, pid, ocs): self.selected = (str(pid), ocs)
    async def flush_tasks(self, pid, tasks): self.flushed = (str(pid), tasks)
    async def flush_ksa(self, pid, ksa): self.ksa_flushed = (str(pid), ksa)
    async def save_document(self, pid, content):
        self.doc_saved = (str(pid), content)
        return {"id": "spy-1", "version": 1, "format": "json", "content": content, "status": "draft"}
```
Run: `.venv/Scripts/python -m pytest tests/test_node_assemble_ksa.py -v`
Expected: FAIL（`assemble_nodes` 不存在）。

- [ ] **Step 2: 實作 assemble_ksa（assemble_nodes.py）**

Create `backend/app/graph_v3/assemble_nodes.py`:
```python
"""v3 收尾節點：assemble_ksa（catalog K/S/A + 公司補充，interrupt 編輯）。
deterministic：K/S/A 來自 indexer pairs()，不用 LLM/不用 pgvector RAG（D13）。"""
import logging

from langgraph.types import interrupt

from app.graph_v3.state import InterviewState

logger = logging.getLogger("jobintel")


def _pairs_to_items(pairs_list) -> list[dict]:
    """Pair{code,name} → draft item（catalog 來源，icap_ref=code）。"""
    return [{"content": p.name, "source": "catalog", "icap_ref": p.code or None}
            for p in pairs_list if p.name]


async def assemble_ksa(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    ocs = state["profile"]["selected_ocs_code"]
    pairs = await deps.knowledge.pairs(ocs) if ocs else None

    draft = {
        "knowledge": _pairs_to_items(pairs.knowledge) if pairs else [],
        "skills": _pairs_to_items(pairs.skills) if pairs else [],
        "attitudes": _pairs_to_items(pairs.attitudes) if pairs else [],
    }

    edited = interrupt({"kind": "edit_ksa", "ksa": draft})
    ksa = edited.get("ksa", draft) if isinstance(edited, dict) else draft

    await deps.persist.flush_ksa(state["job_profile_id"], ksa)
    logger.info("assemble_ksa: flushed K=%d S=%d A=%d",
                len(ksa["knowledge"]), len(ksa["skills"]), len(ksa["attitudes"]))
    return {"ksa": ksa, "current_step": "build_doc"}
```

- [ ] **Step 3: 通過測試**

Run: `.venv/Scripts/python -m pytest tests/test_node_assemble_ksa.py -v`
Expected: 1 passed.

- [ ] **Step 4: Commit**
```bash
git add backend/app/graph_v3/assemble_nodes.py backend/tests/test_node_assemble_ksa.py backend/tests/conftest_graph.py
git commit -m "feat(graph_v3): assemble_ksa node (catalog pairs + company supplements, interrupt edit, flush)"
```

---

### Task 6：build_doc 節點（deterministic OCS 組裝 + preview + save_document）

**Files:**
- Create: `backend/app/graph_v3/build_doc.py`（`build_doc` + 純 helper）
- Test: `backend/tests/test_node_build_doc.py`

**Interfaces:**
- Consumes: `state["tasks"]`（含 `unit_id/unit_title`、`outputs`、`behavior_indicators: [{output_name, indicator_5w2h, ...}]`、`star_case`、5W2H 欄）、`state["ksa"]`、`state["job_title"]/["job_summary"]`、`deps.persist.save_document`。
- Produces: `build_doc(state, config) -> {"document": doc, "current_step": "done"}`；interrupt kind `"preview"`，payload `{"kind": "preview", "document": doc}`，resume 任意值（確認）即結束。
- OCS doc 形狀（v3，deterministic）：
```python
{
  "ocs_profile": {"ocs_code": str, "occupation_name": str, "job_description": str},
  "ocs_content": {"ocu_units": [
     {"ocu_code": "T1", "ocu_name": str, "tasks": [
        {"task_code": "T1.1", "task_name": str,
         "indicators": [{"code": "P1.1.1", "text": str}],
         "outputs": [{"code": "O1.1.1", "name": str}]}]}]},
  "ocs_ksa": {"knowledge": [{"code": "K01", "name": str, "source": str, "icap_ref": str|None}],
              "skills": [...], "attitudes": [...]},
}
```

- [ ] **Step 1: 失敗測試（兩 unit/兩 task → 編碼正確、indicators/outputs/ksa 注入、preview→save）**

Create `backend/tests/test_node_build_doc.py`:
```python
import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.state import new_state, InterviewState
from app.graph_v3.build_doc import build_doc
from app.graph_v3.deps import Deps
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm


def _graph():
    g = StateGraph(InterviewState)
    g.add_node("build_doc", build_doc)
    g.add_edge(START, "build_doc")
    g.add_edge("build_doc", END)
    return g.compile(checkpointer=MemorySaver())


def _state():
    s = new_state(job_profile_id="p1", job_title="設備維護工程師", job_summary="維護產線設備")
    s["tasks"] = [
        {"task_name": "巡檢", "unit_id": "U1", "unit_title": "預防保養",
         "outputs": ["點檢表"],
         "behavior_indicators": [{"output_name": "點檢表", "indicator_5w2h": "每日晨班完成點檢表"}]},
        {"task_name": "排程", "unit_id": "U1", "unit_title": "預防保養",
         "outputs": ["保養排程"],
         "behavior_indicators": [{"output_name": "保養排程", "indicator_5w2h": "每週排定保養"}]},
        {"task_name": "通報", "unit_id": "U2", "unit_title": "異常處理",
         "outputs": [],
         "behavior_indicators": [{"output_name": "", "indicator_5w2h": "異常即時通報"}]},
    ]
    s["ksa"] = {
        "knowledge": [{"content": "設備原理", "source": "catalog", "icap_ref": "K01"}],
        "skills": [{"content": "點檢操作", "source": "company", "icap_ref": None}],
        "attitudes": [{"content": "細心", "source": "company", "icap_ref": None}],
    }
    return s


@pytest.mark.asyncio
async def test_build_doc_deterministic_assembly_then_preview():
    spy = SpyPersist()
    graph = _graph()
    cfg = {"configurable": {"thread_id": "t1",
                            "deps": Deps(knowledge=FakeKnowledge(), persist=spy, llm=FakeLlm())}}
    out = await graph.ainvoke(_state(), cfg)

    payload = out["__interrupt__"][0].value
    assert payload["kind"] == "preview"
    doc = payload["document"]
    units = doc["ocs_content"]["ocu_units"]
    # U1 兩任務、U2 一任務，依出現序分組
    assert [u["ocu_code"] for u in units] == ["T1", "T2"]
    assert [t["task_code"] for t in units[0]["tasks"]] == ["T1.1", "T1.2"]
    assert units[0]["tasks"][0]["indicators"][0]["code"] == "P1.1.1"
    assert units[0]["tasks"][0]["indicators"][0]["text"] == "每日晨班完成點檢表"
    assert units[0]["tasks"][0]["outputs"][0]["code"] == "O1.1.1"
    assert units[1]["tasks"][0]["task_code"] == "T2.1"
    # ksa 注入（doc-level）
    assert doc["ocs_ksa"]["knowledge"][0]["code"] == "K01"
    assert doc["ocs_ksa"]["skills"][0]["name"] == "點檢操作"

    # preview 確認 → 結束 + save_document
    out = await graph.ainvoke(Command(resume="confirm"), cfg)
    assert out["current_step"] == "done"
    assert out["document"]["ocs_profile"]["occupation_name"] == "設備維護工程師"
    assert spy.doc_saved[0] == "p1"
```
Run: `.venv/Scripts/python -m pytest tests/test_node_build_doc.py -v`
Expected: FAIL（`build_doc` 不存在）。

- [ ] **Step 2: 實作 build_doc（build_doc.py，全 deterministic）**

Create `backend/app/graph_v3/build_doc.py`:
```python
"""v3 build_doc：deterministic 組裝 OCS 文件（D13）。
OCU 分組用 catalog unit 結構；編碼 T/P/O/K/S/A 全程式化；不用 LLM、不 import 舊 ocs_builder。"""
import logging

from langgraph.types import interrupt

from app.graph_v3.state import InterviewState

logger = logging.getLogger("jobintel")


def _group_units(tasks: list[dict]) -> list[dict]:
    """依 unit_id 保序分組；無 unit_id 者歸入 '_'。"""
    order: list[str] = []
    by_unit: dict[str, dict] = {}
    for t in tasks:
        uid = t.get("unit_id") or "_"
        if uid not in by_unit:
            order.append(uid)
            by_unit[uid] = {"unit_title": t.get("unit_title") or "其他工作任務", "tasks": []}
        by_unit[uid]["tasks"].append(t)
    return [{"unit_id": uid, **by_unit[uid]} for uid in order]


def _assemble(state: InterviewState) -> dict:
    units_grouped = _group_units(state["tasks"])
    ocu_units = []
    for u_idx, unit in enumerate(units_grouped, 1):
        tasks_out = []
        for t_idx, task in enumerate(unit["tasks"], 1):
            inds = task.get("behavior_indicators") or []
            indicators = [{"code": f"P{u_idx}.{t_idx}.{p}", "text": ind.get("indicator_5w2h", "")}
                          for p, ind in enumerate(inds, 1) if ind.get("indicator_5w2h")]
            # outputs：優先用 indicator 的 output_name，否則 task["outputs"]
            out_names = [ind["output_name"] for ind in inds if ind.get("output_name")] \
                or [o for o in (task.get("outputs") or []) if o]
            outputs = [{"code": f"O{u_idx}.{t_idx}.{o}", "name": name}
                       for o, name in enumerate(out_names, 1)]
            tasks_out.append({"task_code": f"T{u_idx}.{t_idx}",
                              "task_name": task.get("task_name", ""),
                              "indicators": indicators, "outputs": outputs})
        ocu_units.append({"ocu_code": f"T{u_idx}", "ocu_name": unit["unit_title"], "tasks": tasks_out})

    ksa = state.get("ksa") or {"knowledge": [], "skills": [], "attitudes": []}
    def _coded(items, prefix):
        return [{"code": it.get("icap_ref") or f"{prefix}{i:02d}", "name": it["content"],
                 "source": it.get("source", "company"), "icap_ref": it.get("icap_ref")}
                for i, it in enumerate(items, 1)]

    return {
        "ocs_profile": {
            "ocs_code": (state["profile"].get("selected_ocs_code") or ""),
            "occupation_name": state.get("job_title", ""),
            "job_description": state.get("job_summary", ""),
        },
        "ocs_content": {"ocu_units": ocu_units},
        "ocs_ksa": {
            "knowledge": _coded(ksa.get("knowledge", []), "K"),
            "skills": _coded(ksa.get("skills", []), "S"),
            "attitudes": _coded(ksa.get("attitudes", []), "A"),
        },
    }


async def build_doc(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    doc = _assemble(state)
    interrupt({"kind": "preview", "document": doc})   # 人確認預覽
    await deps.persist.save_document(state["job_profile_id"], doc)
    logger.info("build_doc: assembled %d OCU units", len(doc["ocs_content"]["ocu_units"]))
    return {"document": doc, "current_step": "done"}
```

- [ ] **Step 3: 通過測試**

Run: `.venv/Scripts/python -m pytest tests/test_node_build_doc.py -v`
Expected: 1 passed.

- [ ] **Step 4: Commit**
```bash
git add backend/app/graph_v3/build_doc.py backend/tests/test_node_build_doc.py
git commit -m "feat(graph_v3): deterministic build_doc (catalog-unit OCU grouping + preview + save)"
```

---

### Task 7：接上主圖 finish_deep → assemble_ksa → build_doc → END + 端到端

**Files:**
- Modify: `backend/app/graph_v3/graph.py`
- Test: `backend/tests/test_graph_v3_full_e2e.py`（新建，全流程）

**Interfaces:**
- Consumes: Task 5 `assemble_ksa`、Task 6 `build_doc`。
- Produces: `build_graph_v3` 新增節點 `assemble_ksa`、`build_doc`；邊 `finish_deep→assemble_ksa→build_doc→END`。

- [ ] **Step 1: 失敗測試（pick→pool→深問→assemble→build→done 全綠）**

Create `backend/tests/test_graph_v3_full_e2e.py`:
```python
import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph_v3.graph import build_graph_v3
from app.graph_v3.state import new_state
from app.graph_v3.deps import Deps
from app.services.knowledge.models import (
    SearchResult, Hit, TaskPool, PoolGroup, PoolUnit, PoolTask, TasksByIdResult, Pairs, Pair)
from tests.conftest_graph import FakeKnowledge, SpyPersist, FakeLlm

_GOOD = {"has_situation": True, "has_purpose": True, "has_collaborators": True,
         "has_tools": True, "has_action": True, "has_output": True, "has_standard": True}


@pytest.mark.asyncio
async def test_full_flow_pick_to_done(monkeypatch):
    star_refine = {"S": "s", "T": "t", "A": "a", "R": "r"}
    indicators = [{"output_name": "點檢表", "indicator_5w2h": "x", "indicator_abcd": "y",
                   "quality_dims": _GOOD}]
    def _json(prompt):
        return star_refine if "STAR 四槽" in prompt else indicators
    fake = FakeKnowledge(
        search=SearchResult(mode="dense", hits=[Hit(id="p1", ocs_code="OC1", chunk_level="profile")]),
        pool=TaskPool(groups=[PoolGroup(ocs_code="OC1", units=[
            PoolUnit(unit_id="U1", unit_title="預防保養", tasks=[
                PoolTask(id="x1", task_id="T1.1", task_title="巡檢")])])]),
        tasks=TasksByIdResult(tasks=[]))
    async def _pairs(ocs_code):
        return Pairs(ocs_code="OC1", knowledge=[Pair(code="K01", name="設備原理")],
                     skills=[], attitudes=[])
    monkeypatch.setattr(fake, "pairs", _pairs)
    spy = SpyPersist()
    graph = build_graph_v3(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "t1",
                            "deps": Deps(knowledge=fake, persist=spy, llm=FakeLlm(json=_json))}}

    out = await graph.ainvoke(new_state(job_profile_id="p1", job_title="工程師"), cfg)
    out = await graph.ainvoke(Command(resume={"ocs_code": "OC1"}), cfg)        # select_profile
    out = await graph.ainvoke(Command(resume={"tasks": [
        {"task_name": "巡檢", "source": "catalog", "unit_id": "U1", "unit_title": "預防保養",
         "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"}}]}), cfg)        # edit_tasks
    # 深問所有 interrupt
    guard = 0
    while "__interrupt__" in out and out["__interrupt__"][0].value["kind"] == "ask_human":
        out = await graph.ainvoke(Command(resume="作業員、ERP、零漏檢、當日完成"), cfg)
        guard += 1; assert guard < 40
    # edit_ksa
    assert out["__interrupt__"][0].value["kind"] == "edit_ksa"
    out = await graph.ainvoke(Command(resume={"ksa": out["__interrupt__"][0].value["ksa"]}), cfg)
    # preview
    assert out["__interrupt__"][0].value["kind"] == "preview"
    out = await graph.ainvoke(Command(resume="confirm"), cfg)

    assert out["current_step"] == "done"
    assert out["document"]["ocs_content"]["ocu_units"][0]["tasks"][0]["task_code"] == "T1.1"
    assert spy.ksa_flushed[0] == "p1" and spy.doc_saved[0] == "p1"
```
Run: `.venv/Scripts/python -m pytest tests/test_graph_v3_full_e2e.py -v`
Expected: FAIL（主圖 finish_deep 後直接 END，不會進 assemble_ksa）。

- [ ] **Step 2: 接上主圖（graph.py）**

`backend/app/graph_v3/graph.py`：
1. import 補：
```python
from app.graph_v3.assemble_nodes import assemble_ksa
from app.graph_v3.build_doc import build_doc
```
2. `build_graph_v3` 內，`finish_deep` 節點註冊後加兩節點、改邊：
```python
    g.add_node("assemble_ksa", assemble_ksa)
    g.add_node("build_doc", build_doc)
```
3. 把 `g.add_edge("finish_deep", END)` 改成：
```python
    g.add_edge("finish_deep", "assemble_ksa")
    g.add_edge("assemble_ksa", "build_doc")
    g.add_edge("build_doc", END)
```
（`finish_deep` 仍回傳 `{"current_step": "assemble_ksa"}`，保持不變。）

- [ ] **Step 3: 通過測試 + 全套件**

Run: `.venv/Scripts/python -m pytest tests/test_graph_v3_full_e2e.py -v`
Expected: 1 passed.
Run（全套件）: `TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/jobintel .venv/Scripts/python -m pytest -q`
Expected: 全綠。

- [ ] **Step 4: Commit**
```bash
git add backend/app/graph_v3/graph.py backend/tests/test_graph_v3_full_e2e.py
git commit -m "feat(graph_v3): wire finish_deep -> assemble_ksa -> build_doc -> done (full e2e)"
```

---

### Task 8：demo serving 端到端（stub pairs）+ 全套件

**Files:**
- Modify: `backend/app/graph_v3/stubs.py`（`StubKnowledge.pairs` 回真資料）
- Test: `backend/tests/test_serving_smoke.py`（沿用；確認仍建得起來）

- [ ] **Step 1: StubKnowledge.pairs 回 demo K/S/A**

`backend/app/graph_v3/stubs.py` 的 `StubKnowledge.pairs` 改成：
```python
    async def pairs(self, ocs_code) -> Pairs:
        return Pairs(ocs_code=ocs_code,
                     knowledge=[Pair(code="K01", name="設備保養原理")],
                     skills=[Pair(code="S01", name="點檢操作")],
                     attitudes=[Pair(code="A01", name="細心負責")])
```
（檔頂 import 補 `Pair`。）

- [ ] **Step 2: 全套件 + serving smoke**

Run: `TEST_DATABASE_URL=... .venv/Scripts/python -m pytest -q`
Expected: 全綠。

- [ ] **Step 3: Commit**
```bash
git add backend/app/graph_v3/stubs.py
git commit -m "feat(graph_v3): stub pairs for demo assemble_ksa/build_doc end-to-end"
```

- [ ] **Step 4: 更新專案記憶**

更新 `C:\Users\chenb\.claude\projects\s--jobintel-ai\memory\`：記 Phase ④ DONE（assemble_ksa + build_doc deterministic + KsaRepo/DocRepo + 主圖收尾接齊 + 測試數）；指向 live-wire（HttpIndexerClient/DbPersist/PostgresSaver）為下一步。

---

## 完成後
- **產出**：`finish_deep→assemble_ksa→build_doc→done` 端到端骨幹；`KsaRepo`/`DocRepo`；deterministic OCS 組裝（catalog-unit 分組、零 LLM）。
- **下一步**：
  - **live-wire**：StubKnowledge→HttpIndexerClient、InMemoryPersist→DbPersist（每請求 session）、MemorySaver→AsyncPostgresSaver；orchestrator 改用 graph_v3；移除舊 `app/graph/`+`icap_*`+`llm_gateway`+`ocs_builder`。
  - **Phase ⑤**：OTel + eval 閘門。
  - **前端**（最後）：CopilotKit 接 `edit_ksa`/`preview` interrupt + LiveDocPanel 渲染新 OCS doc 形狀。
  - **未來**（spec §12）：per-task K/S 連結（ksa_items.task_id）、5W2H→JSONB details。

## Self-Review
- **Spec 覆蓋**：§9.4 assemble_ksa（pairs + 公司補充 + interrupt + flush ksa_items）✓（Task 5+2+4）；§9.5 build_doc（組裝→document_versions→preview）✓（Task 6+3+4）；§2 收尾接線 ✓（Task 7）；D13 deterministic ✓（Task 6 零 LLM）；D14 豐欄位不落 ✓（無 company_tasks 寫入）；D9 Repo 模式 ✓（Task 2/3）。
- **無新 migration**：ksa_items/document_versions 已存在（D14）。**執行前驗證**：`psql "$DATABASE_URL_SYNC" -c "\d ksa_items"` 與 `\d document_versions` 確認表在；若缺，先補對應 migration 再開工。
- **Placeholder 掃描**：每 task 皆有完整 test + 實作碼 + 指令，無 TBD/TODO。
- **型別一致**：`PersistPort.flush_ksa(job_profile_id, ksa)`/`save_document(job_profile_id, content)->dict`、`KsaRepo.flush/hydrate`、`DocRepo.save/latest`、interrupt kinds `edit_ksa`/`preview`、ksa item 形狀 `{content,source,icap_ref}`、doc 形狀（ocs_profile/ocs_content/ocs_ksa）跨 task 對齊。
- **不破壞**：assemble/build 為新節點；graph.py 僅改 finish_deep 出邊；PersistPort 新方法 additive（DbPersist+InMemoryPersist+SpyPersist 皆實作）；`build_task_pool` 加 unit 欄為 additive。
```
