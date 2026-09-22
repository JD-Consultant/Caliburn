# DB 文件導向重作 Implementation Plan（D25）

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development（建議）執行；步驟用 `- [ ]` 追蹤。

**Goal:** 把 of-record 從「業務表 write-through」改成「文件導向」：業務表精簡到 `users`/`job_profiles`/`document_versions`，任務/KSA/深問細節全在 checkpointer + 最終文件 JSONB；導入 Alembic 管 schema。

**Architecture:** D25（`2026-06-18-db-document-centric-design.md`）。persistence 縮成 `set_selected_ocs(codes)` + `save_document`；drop `TaskRepo/KsaRepo/flush_tasks/flush_ksa` 與 `company_tasks/ksa_items/icap_*` 表/models；導入 Alembic（async env，初始 revision = 乾淨目標 schema）。

**Tech Stack:** Postgres + SQLAlchemy 2.0 async + Alembic 1.13.3；LangGraph AsyncPostgresSaver（checkpointer 自管，勿納入 Alembic）；FastAPI。

## Global Constraints

- 分支 `feat/v3`。後端測試 `backend/.venv/Scripts/python -m pytest`（**不要** `uv run`）。
- 後端啟動 `backend/.venv/Scripts/python run_live.py`（Windows SelectorEventLoop）。
- **未上線、無正式資料** → 可破壞性 migration；dev DB 視為可重建（D25/expand-contract contract 前提已滿足，舊 code 已移除）。
- of-record = `document_versions.content` JSONB（整份 OCS 文件）。任務/KSA/深問細節**只**在 checkpointer + 文件。
- KSA item / task 形狀沿用現況；`selected_ocs_code`(單) → `selected_ocs_codes TEXT[]`(有序複選)。
- **不要動** LangGraph checkpointer 表（`checkpoints/checkpoint_writes/checkpoint_blobs`，由 AsyncPostgresSaver.setup() 管）。Alembic 只管業務表。
- live 入口 = `copilotkit_live_app`（已只掛 users+job_profiles CRUD + /copilotkit）。`main.py` 為舊 demo。

---

### Task 1：安裝 Alembic + async 腳手架（不含 cleanup）

**Files:** Create `backend/alembic.ini`、`backend/alembic/env.py`、`backend/alembic/script.py.mako`、`backend/alembic/versions/.gitkeep`

**Interfaces:**
- Produces: 可跑 `alembic revision --autogenerate` / `alembic upgrade head`；`env.py` 用 `settings.database_url`（async）+ `Base.metadata` 當 target_metadata。

- [ ] **Step 1: 裝 alembic 進 venv**

Run: `backend/.venv/Scripts/python -m pip install alembic==1.13.3`
Expected: 安裝成功（requirements 已 pin）。

- [ ] **Step 2: 初始化 alembic 目錄**

Run（在 backend/）：`backend/.venv/Scripts/python -m alembic init -t async alembic`
（`-t async` 產 async env 範本。）

- [ ] **Step 3: 改 `alembic.ini`** — 把 `sqlalchemy.url` 留空（改由 env.py 從 settings 取），其餘預設。

- [ ] **Step 4: 改 `backend/alembic/env.py`** 接 settings + metadata：

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

from app.config import settings
from app.models.base import Base
import app.models  # noqa: F401  確保所有 model 被 import 進 metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=settings.database_url, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(settings.database_url, future=True)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

> Windows 註記：`asyncio.run` 在此 CLI 情境用 psycopg async 需 SelectorEventLoop。若 `alembic upgrade` 報 ProactorEventLoop，於 env.py 頂部加：
> `import sys, asyncio` + `if sys.platform == "win32": asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())`

- [ ] **Step 5: 加進 requirements 確認** — `alembic==1.13.3` 已在 `backend/requirements.txt`（確認；無則補）。

- [ ] **Step 6: Commit**

```bash
git add backend/alembic.ini backend/alembic/ backend/requirements.txt
git commit -m "build(db): scaffold Alembic (async env wired to settings + Base.metadata)"
```

---

### Task 2：Models 精簡（drop 4 類別 + 瘦 2 類別）

**Files:** Modify `backend/app/models/job_profile.py`、`backend/app/models/__init__.py`

**Interfaces:**
- Produces: 只剩 `User`、`JobProfile`(瘦身)、`DocumentVersion`(瘦身) 三個 model；`Base.metadata` 只含 `users/job_profiles/document_versions`。
- `JobProfile` 欄位：`id, user_id, job_title, department, job_summary, selected_ocs_codes(ARRAY(Text)), created_at, updated_at`。
- `DocumentVersion` 欄位：`id, job_profile_id, version, content(JSONB), status, created_at`。

- [ ] **Step 1: 改 `job_profile.py`**

- 刪整個 class：`IcapReference`、`InterviewSession`、`CompanyTask`、`KsaItem`。
- `JobProfile`：刪欄 `tenure_months, primary_stakeholders, stage, completion_pct, icap_source_type, document_draft, graph_state`；`selected_ocs_code = Column(Text)` → `selected_ocs_codes = Column(ARRAY(Text))`；刪對應 relationship（`icap_references`/`interview_sessions`/`company_tasks`/`ksa_items`/`document_versions` 中除 document_versions 外全刪；`document_versions` relationship 保留）。
- `DocumentVersion`：刪欄 `file_path, format`。
- 確認 import 還需要的：`ARRAY, Column, DateTime, ForeignKey, Integer, Text, JSONB, UUID, func, relationship, uuid`；移除只被刪 model 用到的（如 `Boolean, Float`）。

- [ ] **Step 2: 改 `app/models/__init__.py`** — 移除 `CompanyTask/KsaItem/IcapReference/InterviewSession` 的 export，只留 `User/JobProfile/DocumentVersion`（+ Base）。

- [ ] **Step 3: 驗證 import**

Run: `backend/.venv/Scripts/python -c "import app.models; from app.models import User, JobProfile, DocumentVersion; print(sorted(app.models.Base.metadata.tables))"`
Expected: `['document_versions', 'job_profiles', 'users']`（無 company_tasks/ksa_items/icap_*）。

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/job_profile.py backend/app/models/__init__.py
git commit -m "refactor(models): document-centric — drop CompanyTask/KsaItem/IcapReference/InterviewSession; slim JobProfile/DocumentVersion (D25)"
```

---

### Task 3：Alembic 初始 revision = 乾淨目標 schema

**Files:** Create `backend/alembic/versions/0001_document_centric_baseline.py`

**Interfaces:**
- Consumes: Task 2 的 models（metadata 只剩 3 表）。
- Produces: `alembic upgrade head` 在空 DB 建出 `users/job_profiles/document_versions`（含 `selected_ocs_codes ARRAY`）。

- [ ] **Step 1: autogenerate 初始 revision**（針對空/新 DB）

前提：對著一個**乾淨測試 DB**（或先手動 `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` 於 dev DB——pre-prod 可重建）。
Run（backend/）：`backend/.venv/Scripts/python -m alembic revision --autogenerate -m "document centric baseline"`
產出 versions/xxxx_*.py（含 create_table users/job_profiles/document_versions）。

- [ ] **Step 2: 人工核對 revision** — 確認：3 表齊、`job_profiles.selected_ocs_codes` 為 `ARRAY(Text)`、無 company_tasks/ksa_items/icap_*；`document_versions` 無 file_path/format；updated_at trigger（autogenerate 不會產 trigger，手動在 upgrade() 末尾加 `op.execute(...)` 建 `update_updated_at` function + job_profiles trigger，比照舊 init.sql）。

- [ ] **Step 3: 套用到 dev DB**

Run: `backend/.venv/Scripts/python -m alembic upgrade head`
Expected: 建表成功。`\d job_profiles` 確認欄位。

- [ ] **Step 4: 刪舊 SQL migrations**（被 Alembic 取代）

```bash
git rm backend/migrations/init.sql backend/migrations/002_v3_additive.sql
```
（若 migrations/ 空了則一併移除目錄。）

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/ ; git rm backend/migrations/*.sql
git commit -m "feat(db): Alembic baseline = document-centric schema (3 tables); drop raw SQL migrations"
```

---

### Task 4：Pydantic schemas 精簡

**Files:** Modify `backend/app/schemas/job_profile.py`、`backend/app/schemas/__init__.py`

**Interfaces:**
- Produces: `JobProfileCreate{job_title, department?, job_summary?}`、`JobProfileUpdate{job_title?, department?, job_summary?}`、`JobProfileOut{id, user_id, job_title, department, job_summary, selected_ocs_codes:list[str], created_at, updated_at}`、`User*` 不變。刪 `CompanyTask*`、`InterviewMessage*` 等。

- [ ] **Step 1: 改 `schemas/job_profile.py`**
- `JobProfileCreate`：刪 `tenure_months, primary_stakeholders`（只留 job_title/department/job_summary）。
- `JobProfileUpdate`：刪 `tenure_months, primary_stakeholders, stage, completion_pct`。
- `JobProfileOut`：刪 `tenure_months, primary_stakeholders, stage, completion_pct, icap_source_type, graph_state`；加 `selected_ocs_codes: list[str] = []`。
- 刪 class：`CompanyTaskCreate/Update/Out`、`InterviewMessageIn/Out`。
- `UserCreate/Out` 不動。

- [ ] **Step 2: 改 `schemas/__init__.py`** — 移除被刪 schema 的 export。

- [ ] **Step 3: 驗證 import**

Run: `backend/.venv/Scripts/python -c "from app.schemas import JobProfileOut, JobProfileCreate, UserOut; print('ok')"`

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/
git commit -m "refactor(schemas): document-centric — slim JobProfile schemas + selected_ocs_codes; drop CompanyTask/InterviewMessage"
```

---

### Task 5：Persistence 簡化

**Files:** Modify `backend/app/services/persistence.py`、`backend/app/graph_v3/deps.py`、`backend/app/graph_v3/stubs.py`、`backend/tests/conftest_graph.py`
**Test:** `backend/tests/test_persistence_doc.py`（Create；取代舊 persistence 測試）

**Interfaces:**
- Produces:
  - `persistence.py`：只剩 `DocRepo`（不變）+ 新 `ProfileRepo.set_selected_ocs(job_profile_id, codes: list[str])`（UPDATE job_profiles.selected_ocs_codes）。刪 `TaskRepo`、`KsaRepo`、`_TASK_FIELDS`、`_KSA_TYPES`、`_SRC_TO_DB`。
  - `PersistPort`：`set_selected_ocs(job_profile_id, codes: list[str])` + `save_document(job_profile_id, content) -> dict`。刪 `flush_tasks`/`flush_ksa`。
  - `DbPersist`/`LiveDbPersist`/`InMemoryPersist`/`SpyPersist` 同步。

- [ ] **Step 1: 寫失敗測試 `test_persistence_doc.py`（RED）**

```python
import pytest
from uuid import uuid4
from sqlalchemy import select
from app.models import JobProfile, User
from app.services.persistence import ProfileRepo, DocRepo


@pytest.mark.asyncio
async def test_set_selected_ocs_writes_array(db_session):
    u = User(email=f"{uuid4()}@x.com", name="n"); db_session.add(u); await db_session.flush()
    p = JobProfile(user_id=u.id, job_title="工程師"); db_session.add(p); await db_session.flush()
    await ProfileRepo(db_session).set_selected_ocs(p.id, ["OC2", "OC1"])
    row = (await db_session.execute(select(JobProfile).where(JobProfile.id == p.id))).scalar_one()
    assert row.selected_ocs_codes == ["OC2", "OC1"]


@pytest.mark.asyncio
async def test_doc_repo_save_increments_version(db_session):
    u = User(email=f"{uuid4()}@x.com", name="n"); db_session.add(u); await db_session.flush()
    p = JobProfile(user_id=u.id, job_title="工程師"); db_session.add(p); await db_session.flush()
    r1 = await DocRepo(db_session).save(p.id, {"ocs_profile": {}})
    r2 = await DocRepo(db_session).save(p.id, {"ocs_profile": {}})
    assert r1["version"] == 1 and r2["version"] == 2
```
（沿用既有 DB-skip 慣例；無 TEST_DATABASE_URL 則 skip。）

- [ ] **Step 2: RED** — `backend/.venv/Scripts/python -m pytest tests/test_persistence_doc.py -q`（FAIL：ProfileRepo 不存在）。

- [ ] **Step 3: 改 `persistence.py`** — 刪 `TaskRepo`/`KsaRepo` + 相關常數；新增：

```python
class ProfileRepo:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def set_selected_ocs(self, job_profile_id: UUID, codes: list[str]) -> None:
        prof = await self.s.get(JobProfile, job_profile_id)
        if prof:
            prof.selected_ocs_codes = list(codes or [])
        await self.s.flush()
```
（`DocRepo` 不動；`DocRepo.save` 的 `status` 仍 'draft'。）

- [ ] **Step 4: 改 `deps.py`** — `PersistPort`：

```python
class PersistPort(Protocol):
    async def set_selected_ocs(self, job_profile_id: UUID, codes: list[str]) -> None: ...
    async def save_document(self, job_profile_id: UUID, content: dict) -> dict: ...
```
`DbPersist`/`LiveDbPersist`：`set_selected_ocs` 委派 `ProfileRepo`；`save_document` 委派 `DocRepo`；**刪** `flush_tasks`/`flush_ksa`。`LiveDbPersist.set_selected_ocs` 用短命 session + commit。

- [ ] **Step 5: 改 `stubs.py` `InMemoryPersist`** — 只留 `set_selected_ocs(self, pid, codes)`（存 list）+ `save_document`；刪 flush_tasks/flush_ksa。

- [ ] **Step 6: 改 `conftest_graph.py` `SpyPersist`** — `set_selected_ocs(self, pid, codes)` 記 `(str(pid), codes)`；`save_document` 不變；刪 flush_tasks/flush_ksa。

- [ ] **Step 7: GREEN + 全套件**

Run: `backend/.venv/Scripts/python -m pytest tests/test_persistence_doc.py -q`（PASS/skip）；再 `pytest -q`（會有 graph 節點/舊測試紅燈 → Task 6/8 處理；記錄）。

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/persistence.py backend/app/graph_v3/deps.py backend/app/graph_v3/stubs.py backend/tests/conftest_graph.py backend/tests/test_persistence_doc.py
git rm backend/tests/test_persistence_ksa.py backend/tests/test_deps_dbpersist.py backend/tests/test_live_db_persist.py
git commit -m "refactor(persist): document-centric — ProfileRepo.set_selected_ocs + DocRepo only; drop Task/KsaRepo + flush_* (D25)"
```
（刪舊 persistence 測試：test_persistence_ksa/test_deps_dbpersist/test_live_db_persist 都測已刪的 flush_tasks/flush_ksa/KsaRepo。）

---

### Task 6：Graph 節點調整（pick_profile 寫 codes、移除 flush）

**Files:** Modify `backend/app/graph_v3/nodes.py`、`backend/app/graph_v3/curate_nodes.py`、`backend/app/graph_v3/build_doc.py`
**Test:** Modify `backend/tests/test_node_pick_profile.py`、`test_node_task_pool.py`、`test_node_build_doc.py`、`test_graph_v3_full_e2e.py`

**Interfaces:**
- `pick_profile`：`await deps.persist.set_selected_ocs(job_profile_id, codes)`（codes = 有序清單；取代舊 `set_selected_ocs(primary)`）。
- `build_task_pool`：**移除** `await deps.persist.flush_tasks(...)`（任務只進 state/checkpointer）。
- `build_doc`：**移除** `flush_ksa(...)`，只留 `await deps.persist.save_document(...)`。

- [ ] **Step 1: 改 nodes**
- `nodes.py pick_profile`：把 `set_selected_ocs(state["job_profile_id"], primary)` 改成 `set_selected_ocs(state["job_profile_id"], codes)`。
- `nodes.py build_task_pool`：刪 `await deps.persist.flush_tasks(...)` 那行（其餘不變，仍回 `{"tasks": tasks, ...}`）。
- `build_doc.py`：刪 `flush_ksa(...)` 呼叫，保留 `save_document` + interrupt(preview)。

- [ ] **Step 2: 更新測試**
- `test_node_pick_profile.py`：斷言 `spy.selected == ("p1", ["OC1"])`（list；複選測試 `["OC2","OC1"]`）。
- `test_node_task_pool.py`：移除對 `spy.flushed` 的斷言（不再 flush）；保留 interrupt/排序斷言。
- `test_node_build_doc.py`：移除 `spy.ksa_flushed` 斷言；保留 doc 結構 + `spy.doc_saved`。
- `test_graph_v3_full_e2e.py`：移除 flush_tasks/flush_ksa 相關斷言；end state document + done 保留。

- [ ] **Step 3: 全套件 GREEN**

Run: `backend/.venv/Scripts/python -m pytest -q`（目標全綠，除 Task 7 待清的舊路由測試）。

- [ ] **Step 4: Commit**

```bash
git add backend/app/graph_v3/nodes.py backend/app/graph_v3/curate_nodes.py backend/app/graph_v3/build_doc.py backend/tests/test_node_pick_profile.py backend/tests/test_node_task_pool.py backend/tests/test_node_build_doc.py backend/tests/test_graph_v3_full_e2e.py
git commit -m "refactor(graph_v3): pick_profile writes selected_ocs_codes; drop flush_tasks/flush_ksa (document-centric, D25)"
```

---

### Task 7：清舊路由 + main.py（依賴已刪 schema）

**Files:** Delete `backend/app/api/routes/documents.py`、`backend/app/api/routes/tasks.py`；Modify `backend/app/main.py`；Modify/Delete 相關測試 + `backend/app/services/document_service.py`(若僅舊 export 用)

**Interfaces:**
- `main.py`：只掛 `users` + `job_profiles`；移除 `tasks`/`documents` include；移除 `Base.metadata.create_all`（schema 改由 Alembic 管）。

- [ ] **Step 1: 刪舊路由**

```bash
git rm backend/app/api/routes/documents.py backend/app/api/routes/tasks.py
```

- [ ] **Step 2: 改 `main.py`** — 移除 `from app.api.routes import documents, ... tasks`；只 `include_router(users)`, `include_router(job_profiles)`；移除 lifespan 的 `Base.metadata.create_all`（改註解：schema 由 `alembic upgrade head` 管）。

- [ ] **Step 3: document_service.py** — 若只被刪除的 documents.py 用（grep 確認無其他 importer），`git rm backend/app/services/document_service.py`；若仍被引用則保留不動。

- [ ] **Step 4: 守衛/相關測試** — grep `routes.tasks`/`routes.documents`/`document_service`/`app.main` 的測試；刪除測舊端點者（如 test_documents/test_tasks/test_export 若存在）；`import app.main` 守衛測試保留（確認仍可 import）。

- [ ] **Step 5: 全套件 GREEN**

Run: `backend/.venv/Scripts/python -m pytest -q`（全綠）。

- [ ] **Step 6: Commit**

```bash
git add -A backend/app/main.py backend/app/api/routes backend/app/services backend/tests
git commit -m "chore(api): drop legacy documents/tasks routes + create_all (Alembic owns schema); slim main.py (D25)"
```

---

### Task 8：測試 DB fixture + 全綠收尾

**Files:** Modify `backend/tests/conftest.py`（若 db_session fixture 用 create_all → 確認用 `Base.metadata.create_all`（瘦身後 3 表）仍可建）；掃殘留

**Interfaces:** 測試 DB schema 由 models `Base.metadata.create_all` 建（與 Alembic 獨立；models 即真相）。

- [ ] **Step 1: 檢查 conftest db_session** — 確認 fixture 用 `Base.metadata.create_all/drop_all`（瘦身後只建 3 表）；若引用已刪 model 則修。
- [ ] **Step 2: 全域 grep 殘留** — `CompanyTask|KsaItem|IcapReference|InterviewSession|flush_tasks|flush_ksa|company_tasks|ksa_items|graph_state|\.stage` 在 backend/app + tests，逐一清乾淨。
- [ ] **Step 3: 全套件** — `backend/.venv/Scripts/python -m pytest -q` 全綠。
- [ ] **Step 4: Commit** `git commit -am "test: align test DB + sweep dangling refs to dropped tables (D25)"`

---

### Task 9：端到端驗證 [runtime-verify，協作]

- [ ] **Step 1:** dev DB：`backend/.venv/Scripts/python -m alembic upgrade head`（或重建 schema）。重啟 `run_live.py`。
- [ ] **Step 2（使用者）:** 走完整流程，確認存檔後 `document_versions` 有新版（含每任務 K/S + 全域 A + 指標）；`job_profiles.selected_ocs_codes` 為陣列；**無** company_tasks/ksa_items 表。
- [ ] **Step 3:** decision log D25 補「實作完成」；memory 更新。

---

## Self-Review

- **Spec 覆蓋**（design §7）：Alembic→Task1/3；models→Task2；schemas→Task4；persistence→Task5；節點→Task6；舊 code 清理→Task7；測試→Task5/6/8 ✓。
- **Placeholder**：各步有檔/碼/指令；Alembic autogenerate 後需人工核對 trigger（Task3 Step2 已標）。
- **型別一致**：`set_selected_ocs(codes: list[str])` 於 PersistPort/DbPersist/LiveDbPersist/InMemory/Spy/pick_profile 一致；`selected_ocs_codes` 於 model(ARRAY)/schema(list[str])/state 一致。
- **風險**：① Alembic async env 在 Windows 需 SelectorEventLoop（Task1 Step4 已註）；② autogenerate 不產 trigger/extension drop，需人工補（Task3 Step2）；③ dev DB 需重建（pre-prod 可接受，D25）。
