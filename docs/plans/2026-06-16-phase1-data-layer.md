# Phase ① 資料層 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 在 `feat/v3` 上建立新的「資料基礎」——對 indexer 的 `KnowledgeClient`、additive schema、persistence repos、pytest 測試框架——**完全不動正在跑的 graph**，分支保持可跑（舊流程不壞）。

**Architecture:** 純 additive 後端基礎建設。新模組與舊 `icap_*` 並存；舊節點繼續用舊 retrieval（之後 Phase 才換掉）。本階段交付物都可單測，且互不依賴執行順序。

**Tech Stack:** FastAPI / SQLAlchemy 2.0 async / asyncpg / httpx / Pydantic v2 / Postgres（raw SQL migrations）/ pytest + pytest-asyncio + respx（新增）。

**前置：** 在 `feat/v3` 分支上工作（`git switch -c feat/v3` 若尚未建立）。架構依據 `docs/superpowers/specs/2026-06-16-jobintel-ai-v3-architecture.md` §4.3/§4.4/§6。

---

### Task 0：pytest 測試框架

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/tests/__init__.py`、`backend/tests/conftest.py`
- Create: `backend/pytest.ini`

- [ ] **Step 1: 加測試依賴**

`backend/requirements.txt` 末尾新增：
```
# Testing
pytest==8.3.3
pytest-asyncio==0.24.0
respx==0.21.1
```
安裝：`pip install -r backend/requirements.txt`

- [ ] **Step 2: pytest 設定**

Create `backend/pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
pythonpath = .
```

- [ ] **Step 3: conftest（client 測試不需 DB；repo 測試用 TEST_DATABASE_URL 交易回滾）**

Create `backend/tests/__init__.py`（空檔）。Create `backend/tests/conftest.py`:
```python
import os
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")


@pytest_asyncio.fixture
async def db_session():
    """每測試一條交易，結束 rollback；需設 TEST_DATABASE_URL 指向測試 Postgres。"""
    if not TEST_DATABASE_URL:
        import pytest
        pytest.skip("TEST_DATABASE_URL not set")
    engine = create_async_engine(TEST_DATABASE_URL)
    conn = await engine.connect()
    trans = await conn.begin()
    Session = async_sessionmaker(bind=conn, expire_on_commit=False, class_=AsyncSession)
    session = Session()
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await conn.close()
        await engine.dispose()
```

- [ ] **Step 4: 冒煙測試確認框架可跑**

Create `backend/tests/test_smoke.py`:
```python
def test_harness_works():
    assert True
```
Run: `cd backend && pytest tests/test_smoke.py -v` → Expected: 1 passed.

- [ ] **Step 5: Commit**
```bash
git add backend/requirements.txt backend/pytest.ini backend/tests/
git commit -m "test: add pytest harness (pytest-asyncio, respx, conftest)"
```

---

### Task 1：KnowledgeClient Protocol + 回應模型

**Files:**
- Create: `backend/app/services/knowledge/__init__.py`、`backend/app/services/knowledge/models.py`、`backend/app/services/knowledge/base.py`
- Test: `backend/tests/test_knowledge_models.py`

- [ ] **Step 1: 失敗測試（模型解析 indexer 回應）**

Create `backend/tests/test_knowledge_models.py`:
```python
from app.services.knowledge.models import SearchResult, TaskPool, Pairs, TaskDetail


def test_search_result_parses_and_ignores_extra():
    r = SearchResult.model_validate({
        "mode": "hybrid",
        "hits": [{"id": "p1", "score": 0.9, "chunk_level": "task",
                  "ocs_code": "OC1", "task_id": "T1", "task_title": "做事",
                  "job_title": "工程師", "unexpected": "ok"}],
    })
    assert r.mode == "hybrid"
    assert r.hits[0].id == "p1" and r.hits[0].task_title == "做事"


def test_pairs_parses_code_name_dicts():
    p = Pairs.model_validate({
        "ocs_code": "OC1",
        "knowledge": [{"code": "K01", "name": "知識一"}],
        "skills": [], "attitudes": [], "outputs": [],
        "prerequisites": ["需先具備X"], "supplements": [],
    })
    assert p.knowledge[0].code == "K01" and p.prerequisites == ["需先具備X"]


def test_task_detail_parses():
    t = TaskDetail.model_validate({
        "id": "OC1-T1.1", "ocs_code": "OC1", "task_id": "T1.1", "task_title": "t",
        "competency_level": 3, "activity_examples": ["a"],
        "k_pairs": [{"code": "K01", "name": "k"}], "s_pairs": [], "output_pairs": [],
    })
    assert t.competency_level == 3 and t.k_pairs[0].name == "k"
```
Run: `pytest tests/test_knowledge_models.py -v` → Expected: FAIL（模組不存在）。

- [ ] **Step 2: 實作模型**

Create `backend/app/services/knowledge/__init__.py`（空檔）。Create `backend/app/services/knowledge/models.py`:
```python
from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Pair(_Base):
    code: str = ""
    name: str = ""


class Hit(_Base):
    id: str
    score: float = 0.0
    chunk_level: str = ""
    ocs_code: str = ""
    job_title: str | None = None
    unit_id: str | None = None
    unit_title: str | None = None
    task_id: str | None = None
    task_title: str | None = None


class SearchResult(_Base):
    mode: str = ""
    hits: list[Hit] = []


class PoolTask(_Base):
    id: str
    task_id: str = ""
    task_title: str = ""
    activity_examples: list[str] = []


class PoolUnit(_Base):
    unit_id: str = ""
    unit_title: str = ""
    tasks: list[PoolTask] = []


class PoolGroup(_Base):
    ocs_code: str = ""
    job_title: str = ""
    units: list[PoolUnit] = []


class TaskPool(_Base):
    groups: list[PoolGroup] = []


class Pairs(_Base):
    ocs_code: str = ""
    knowledge: list[Pair] = []
    skills: list[Pair] = []
    attitudes: list[Pair] = []
    outputs: list[Pair] = []
    prerequisites: list[str] = []
    supplements: list[str] = []


class TaskDetail(_Base):
    id: str
    ocs_code: str = ""
    unit_id: str | None = None
    unit_title: str | None = None
    task_id: str = ""
    task_title: str = ""
    competency_level: int | None = None
    activity_examples: list[str] = []
    k_pairs: list[Pair] = []
    s_pairs: list[Pair] = []
    output_pairs: list[Pair] = []


class TasksByIdResult(_Base):
    tasks: list[TaskDetail] = []
```

- [ ] **Step 3: 通過測試**

Run: `pytest tests/test_knowledge_models.py -v` → Expected: 3 passed.

- [ ] **Step 4: KnowledgeClient Protocol（介面，讓節點依賴它不依賴 HTTP）**

Create `backend/app/services/knowledge/base.py`:
```python
from typing import Protocol

from app.services.knowledge.models import Pairs, SearchResult, TaskPool, TasksByIdResult


class KnowledgeClient(Protocol):
    async def search(self, query: str, *, level: str | None = None,
                     hybrid: bool = True, top_k: int = 10) -> SearchResult: ...
    async def task_pool(self, ocs_codes: list[str], *, activity_examples: int = 3) -> TaskPool: ...
    async def pairs(self, ocs_code: str) -> Pairs: ...
    async def tasks_by_id(self, ids: list[str]) -> TasksByIdResult: ...
    async def healthz(self) -> bool: ...
```

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/knowledge/ backend/tests/test_knowledge_models.py
git commit -m "feat(knowledge): indexer response models + KnowledgeClient Protocol"
```

---

### Task 2：HttpIndexerClient（httpx 實作）+ config

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/app/services/knowledge/http_client.py`
- Test: `backend/tests/test_http_indexer_client.py`

- [ ] **Step 1: config 加 indexer 設定**

`backend/app/config.py` 在 class `Settings` 內新增（接 jd-ocs-indexer 的 query API）：
```python
    # jd-ocs-indexer query API
    indexer_base_url: str = "http://localhost:8000"
    indexer_api_key: str = ""
    indexer_timeout_s: float = 30.0
```

- [ ] **Step 2: 失敗測試（用 respx mock httpx）**

Create `backend/tests/test_http_indexer_client.py`:
```python
import httpx
import pytest
import respx

from app.services.knowledge.http_client import HttpIndexerClient

BASE = "http://idx.test"


@pytest.fixture
def client():
    return HttpIndexerClient(base_url=BASE, api_key="", timeout_s=5.0)


@respx.mock
async def test_search_calls_endpoint_and_parses(client):
    route = respx.post(f"{BASE}/search").mock(return_value=httpx.Response(
        200, json={"mode": "hybrid", "hits": [{"id": "p1", "score": 0.8,
                   "chunk_level": "task", "ocs_code": "OC1", "task_title": "t"}]}))
    r = await client.search("hello", top_k=5)
    assert route.called
    assert r.hits[0].id == "p1"


@respx.mock
async def test_pairs_uses_path_param(client):
    respx.get(f"{BASE}/profile/OC1/pairs").mock(return_value=httpx.Response(
        200, json={"ocs_code": "OC1", "knowledge": [{"code": "K01", "name": "k"}],
                   "skills": [], "attitudes": [], "outputs": [],
                   "prerequisites": [], "supplements": []}))
    r = await client.pairs("OC1")
    assert r.knowledge[0].code == "K01"


@respx.mock
async def test_tasks_by_id_posts_ids(client):
    respx.post(f"{BASE}/tasks/by-id").mock(return_value=httpx.Response(
        200, json={"tasks": [{"id": "x", "task_id": "T1.1", "task_title": "t",
                   "competency_level": 3}]}))
    r = await client.tasks_by_id(["x"])
    assert r.tasks[0].competency_level == 3
```
Run: `pytest tests/test_http_indexer_client.py -v` → Expected: FAIL（模組不存在）。

- [ ] **Step 3: 實作 HttpIndexerClient**

Create `backend/app/services/knowledge/http_client.py`:
```python
import httpx

from app.services.knowledge.models import Pairs, SearchResult, TaskPool, TasksByIdResult


class HttpIndexerClient:
    """jd-ocs-indexer query API 的 typed HTTP client（KnowledgeClient 實作）。
    日後要外部多客戶，indexer 端加 MCP surface 即可，本 client 不變。"""

    def __init__(self, base_url: str, api_key: str = "", timeout_s: float = 30.0):
        self._base = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.AsyncClient(base_url=self._base, headers=headers, timeout=timeout_s)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def search(self, query: str, *, level: str | None = None,
                     hybrid: bool = True, top_k: int = 10) -> SearchResult:
        payload = {"query": query, "hybrid": hybrid, "top_k": top_k}
        if level:
            payload["level"] = level
        resp = await self._client.post("/search", json=payload)
        resp.raise_for_status()
        return SearchResult.model_validate(resp.json())

    async def task_pool(self, ocs_codes: list[str], *, activity_examples: int = 3) -> TaskPool:
        resp = await self._client.post("/task-pool", json={
            "ocs_codes": ocs_codes, "activity_examples": activity_examples})
        resp.raise_for_status()
        return TaskPool.model_validate(resp.json())

    async def pairs(self, ocs_code: str) -> Pairs:
        resp = await self._client.get(f"/profile/{ocs_code}/pairs")
        resp.raise_for_status()
        return Pairs.model_validate(resp.json())

    async def tasks_by_id(self, ids: list[str]) -> TasksByIdResult:
        resp = await self._client.post("/tasks/by-id", json={"ids": ids})
        resp.raise_for_status()
        return TasksByIdResult.model_validate(resp.json())

    async def healthz(self) -> bool:
        try:
            resp = await self._client.get("/healthz")
            return resp.status_code == 200 and resp.json().get("status") == "ok"
        except Exception:
            return False
```

- [ ] **Step 4: 通過測試**

Run: `pytest tests/test_http_indexer_client.py -v` → Expected: 3 passed.

- [ ] **Step 5: Commit**
```bash
git add backend/app/config.py backend/app/services/knowledge/http_client.py backend/tests/test_http_indexer_client.py
git commit -m "feat(knowledge): HttpIndexerClient over the 6 indexer endpoints + config"
```

---

### Task 3：Additive SQL 遷移

**Files:**
- Create: `backend/migrations/002_v3_additive.sql`

- [ ] **Step 1: 寫遷移（additive，與現有 init.sql 同風格的 raw SQL）**

Create `backend/migrations/002_v3_additive.sql`:
```sql
-- v3 additive：provenance + 選定 OCS。不刪任何欄；graph_state 待 PostgresSaver 接手後（Phase ②）再 drop。
ALTER TABLE company_tasks  ADD COLUMN IF NOT EXISTS source      TEXT DEFAULT 'company';
ALTER TABLE company_tasks  ADD COLUMN IF NOT EXISTS indexer_ref JSONB;
ALTER TABLE job_profiles   ADD COLUMN IF NOT EXISTS selected_ocs_code TEXT;
```

- [ ] **Step 2: 套用到測試/開發 DB 並驗證**

Run（對你的 Postgres）：`psql "$DATABASE_URL_SYNC" -f backend/migrations/002_v3_additive.sql`
驗證：`psql "$DATABASE_URL_SYNC" -c "\d company_tasks"` → 應見 `source`、`indexer_ref` 欄。

- [ ] **Step 3: Commit**
```bash
git add backend/migrations/002_v3_additive.sql
git commit -m "feat(db): additive v3 migration (company_tasks provenance, job_profiles.selected_ocs_code)"
```

---

### Task 4：SQLAlchemy 模型補欄

**Files:**
- Modify: `backend/app/models/job_profile.py`
- Test: `backend/tests/test_models_columns.py`

- [ ] **Step 1: 失敗測試（ORM 認得新欄）**

Create `backend/tests/test_models_columns.py`:
```python
from app.models import CompanyTask, JobProfile


def test_company_task_has_provenance_columns():
    cols = set(CompanyTask.__table__.columns.keys())
    assert {"source", "indexer_ref"} <= cols


def test_job_profile_has_selected_ocs_code():
    assert "selected_ocs_code" in JobProfile.__table__.columns.keys()
```
Run: `pytest tests/test_models_columns.py -v` → Expected: FAIL。

- [ ] **Step 2: 加欄位到模型**

`backend/app/models/job_profile.py`：
- `JobProfile` 內（`icap_source_type` 附近）加：`selected_ocs_code = Column(Text)`
- `CompanyTask` 內（`sort_order` 附近）加：
```python
    source = Column(Text, default="company")        # catalog | company
    indexer_ref = Column(JSONB)                      # {ocs_code, task_id}
```
（`JSONB` 已 import。）

- [ ] **Step 3: 通過測試**

Run: `pytest tests/test_models_columns.py -v` → Expected: 2 passed.

- [ ] **Step 4: Commit**
```bash
git add backend/app/models/job_profile.py backend/tests/test_models_columns.py
git commit -m "feat(models): add provenance + selected_ocs_code columns"
```

---

### Task 5：TaskRepo（hydrate / flush，row-level upsert 保 task_id 穩定）

**Files:**
- Create: `backend/app/services/persistence.py`
- Test: `backend/tests/test_persistence_taskrepo.py`（需 `TEST_DATABASE_URL`）

- [ ] **Step 1: 失敗測試（flush 後 hydrate 回來；既有 task 用 indexer_ref/source 識別不重建、保留 row id）**

Create `backend/tests/test_persistence_taskrepo.py`:
```python
import uuid
import pytest
from app.models import JobProfile, User
from app.services.persistence import TaskRepo


@pytest.mark.asyncio
async def test_flush_then_hydrate_roundtrip(db_session):
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@t.co", name="t")
    prof = JobProfile(id=uuid.uuid4(), user_id=user.id, job_title="工程師")
    db_session.add_all([user, prof])
    await db_session.flush()

    repo = TaskRepo(db_session)
    tasks = [{"task_name": "巡檢", "source": "catalog",
              "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"}}]
    await repo.flush(prof.id, tasks)

    got = await repo.hydrate(prof.id)
    assert len(got) == 1 and got[0]["task_name"] == "巡檢"
    assert got[0]["source"] == "catalog"


@pytest.mark.asyncio
async def test_flush_is_idempotent_keeps_row_id(db_session):
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@t.co", name="t")
    prof = JobProfile(id=uuid.uuid4(), user_id=user.id, job_title="工程師")
    db_session.add_all([user, prof])
    await db_session.flush()

    repo = TaskRepo(db_session)
    await repo.flush(prof.id, [{"task_name": "巡檢", "source": "catalog",
                                "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"}}])
    first = (await repo.hydrate(prof.id))[0]["id"]
    # 第二次 flush 同一任務（標題不變）→ 應 update 同 row，不新建
    await repo.flush(prof.id, [{"task_name": "巡檢", "source": "catalog",
                                "indexer_ref": {"ocs_code": "OC1", "task_id": "T1.1"},
                                "frequency": "每日"}])
    rows = await repo.hydrate(prof.id)
    assert len(rows) == 1 and rows[0]["id"] == first and rows[0]["frequency"] == "每日"
```
Run（需測試 Postgres）：`TEST_DATABASE_URL=... pytest tests/test_persistence_taskrepo.py -v` → Expected: FAIL。

- [ ] **Step 2: 實作 TaskRepo**

Create `backend/app/services/persistence.py`:
```python
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CompanyTask

# 哪些欄位 flush 寫回（深問產出之外的清單欄）
_TASK_FIELDS = ("task_name", "description", "category", "frequency",
                "responsibility_type", "source", "indexer_ref", "sort_order")


class TaskRepo:
    """company_tasks 的 hydrate/flush。flush 以 (job_profile_id, task_name) 為穩定鍵
    做 row-level upsert：既有 row 更新、不存在才新建、清單中消失的刪除 → 保 row id 穩定免斷 ksa FK。"""

    def __init__(self, session: AsyncSession):
        self.s = session

    async def hydrate(self, job_profile_id: UUID) -> list[dict]:
        rows = (await self.s.execute(
            select(CompanyTask)
            .where(CompanyTask.job_profile_id == job_profile_id)
            .order_by(CompanyTask.sort_order)
        )).scalars().all()
        return [self._to_dict(r) for r in rows]

    async def flush(self, job_profile_id: UUID, tasks: list[dict]) -> None:
        existing = {r.task_name: r for r in (await self.s.execute(
            select(CompanyTask).where(CompanyTask.job_profile_id == job_profile_id)
        )).scalars().all()}
        seen: set[str] = set()
        for i, t in enumerate(tasks):
            name = t.get("task_name", "")
            if not name:
                continue
            seen.add(name)
            row = existing.get(name) or CompanyTask(job_profile_id=job_profile_id, task_name=name)
            for f in _TASK_FIELDS:
                if f in t:
                    setattr(row, f, t[f])
            row.sort_order = i
            if name not in existing:
                self.s.add(row)
        for name, row in existing.items():
            if name not in seen:
                await self.s.delete(row)
        await self.s.flush()

    @staticmethod
    def _to_dict(r: CompanyTask) -> dict:
        return {"id": str(r.id), "task_name": r.task_name, "description": r.description,
                "category": r.category, "frequency": r.frequency,
                "responsibility_type": r.responsibility_type, "source": r.source,
                "indexer_ref": r.indexer_ref, "sort_order": r.sort_order}
```

- [ ] **Step 3: 通過測試**

Run: `TEST_DATABASE_URL=... pytest tests/test_persistence_taskrepo.py -v` → Expected: 2 passed.

- [ ] **Step 4: Commit**
```bash
git add backend/app/services/persistence.py backend/tests/test_persistence_taskrepo.py
git commit -m "feat(persistence): TaskRepo hydrate/flush with stable-id row-level upsert"
```

---

## 完成後

- 全測試綠：`cd backend && pytest -v`（repo 測試需 `TEST_DATABASE_URL`）。
- Final review（subagent-driven 的最後一關）。
- **產出**：`KnowledgeClient`+`HttpIndexerClient`、additive schema + 模型、`TaskRepo`、pytest 框架。舊 graph 未動、分支可跑。
- **下一步**：Phase ②（骨幹節點 ①②：升級 langgraph→v0.4+、PostgresSaver、pick_profile/build_task_pool + interrupt + CopilotKit shared-state 第一條端到端；此時開始移除對應 `icap_*` 與 `graph_state` 欄）。`KsaRepo`/`DocRepo` 比照 `TaskRepo` 於用到時補（Phase ④）。

## Self-Review
- Spec 覆蓋：§4.3 KnowledgeClient ✓、§6 additive schema ✓、§4.4 persistence（TaskRepo；KsaRepo/DocRepo 延後到 Phase ④用到時）✓、測試框架 ✓。
- 無 placeholder：各 task 有真實 test + 實作碼 + 指令。
- 型別一致：模型/欄位/方法名跨 task 對齊（`Pair{code,name}`、`source`、`indexer_ref`）。
- 不破壞：本階段純 additive，未 import/呼叫於舊 graph，分支保持可跑。
