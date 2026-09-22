# Live-wire A：graph_v3 接真依賴 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development（建議）或 superpowers:executing-plans。步驟用 `- [ ]`。
> **本地記錄（untracked，不 commit）。** 日期：2026-06-17。依據 spec §3/§4.4、決策 D5/D6/D7/D10/**D15/D16/D17**。

**Goal:** 把 graph_v3 從 stub demo 接成真服務：真 indexer（HttpIndexerClient）、真業務表（session-factory 的 LiveDbPersist）、真 checkpointer（AsyncPostgresSaver 由 FastAPI lifespan 持有），用獨立的 production 入口 `copilotkit_live_app.py`。**不**移除舊代碼（concern B 延後）。

**Architecture:** deps 在 app 啟動時一次性烤進 CopilotKit agent → 無 per-request scope，故 `LiveDbPersist` 持 session-factory、每操作開短命 session 並各自 commit（write-through，D16）。checkpointer 與 httpx client 由 lifespan 以 `AsyncExitStack` 持有、shutdown 關閉（D17）。既有 `copilotkit_app.py`（demo, MemorySaver+stubs）與 `build_demo_sdk` 保留給測試。

**Tech Stack:** FastAPI lifespan + langgraph-checkpoint-postgres 3.1.0（AsyncPostgresSaver）+ psycopg 3.3.4 + SQLAlchemy 2.0 async + httpx + CopilotKit。沿用 `backend/.venv`、docker Postgres、`TEST_DATABASE_URL`。

## Global Constraints

- 分支 `feat/v3`；**只做 concern A**，不刪舊代碼、不動 `main.py`/`copilotkit_app.py`(demo)/`build_demo_sdk`。
- 既有測試（`test_copilotkit_endpoint.py`、`test_serving_smoke.py`）必須維持綠。
- 不 import 被移除鏈（icap_retriever / app.graph.llm_gateway / ocs_builder）。
- 重用既有：`HttpIndexerClient`(`app/services/knowledge/http_client.py`)、`open_pg_checkpointer`(`app/graph_v3/checkpointer.py`)、`OpenRouterLlm`(`app/graph_v3/llm.py`)、repos(`app/services/persistence.py`)、`AsyncSessionLocal`(`app/database.py`)、`DbPersist`(`app/graph_v3/deps.py`)。
- TDD：每單元先寫失敗測試。DB 測試用 `TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/jobintel uv run pytest ...`（已驗證可連）。
- 提交只 stage 明確檔案路徑；**絕不** `git add -A`（repo 有 untracked `docs/superpowers/` 不可 commit）。

---

### Task 1：LiveDbPersist（session-factory，每操作短命 session + commit）

**Files:**
- Modify: `backend/app/graph_v3/deps.py`（新增 `LiveDbPersist`）
- Test: `backend/tests/test_live_db_persist.py`（需 `TEST_DATABASE_URL`）

**Interfaces:**
- Consumes: `AsyncSessionLocal`（`app.database`）；既有 `DbPersist`（同檔，takes 一個 live `AsyncSession`）。
- Produces: `LiveDbPersist(session_factory)` 實作 `PersistPort` 四方法，每個方法 `async with session_factory() as s: 委派 DbPersist(s) → await s.commit()`。

- [ ] **Step 1: 失敗測試（真 DB：每操作各自 commit、跨 session 可讀回）**

Create `backend/tests/test_live_db_persist.py`:
```python
import os
import uuid
import pytest
from app.database import AsyncSessionLocal
from app.models import JobProfile, User
from app.graph_v3.deps import LiveDbPersist
from app.services.persistence import KsaRepo, DocRepo

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"),
                                reason="TEST_DATABASE_URL not set")


@pytest.mark.asyncio
async def test_live_persist_commits_each_op_visible_in_new_session():
    pid = uuid.uuid4()
    uid = uuid.uuid4()
    # 建 user+profile（獨立 session，commit 讓其他 session 看得到）
    async with AsyncSessionLocal() as s:
        s.add_all([User(id=uid, email=f"{uid}@t.co", name="t"),
                   JobProfile(id=pid, user_id=uid, job_title="工程師")])
        await s.commit()
    try:
        live = LiveDbPersist(AsyncSessionLocal)
        await live.set_selected_ocs(pid, "OC1")
        await live.flush_ksa(pid, {"knowledge": [{"content": "設備原理", "source": "catalog", "icap_ref": "K01"}],
                                   "skills": [], "attitudes": []})
        doc = await live.save_document(pid, {"ocs_profile": {"ocs_code": "ENT-001"}})
        assert doc["version"] == 1

        # 用全新 session 讀回 → 證明各操作確實 commit
        async with AsyncSessionLocal() as s:
            prof = await s.get(JobProfile, pid)
            assert prof.selected_ocs_code == "OC1"
            ksa = await KsaRepo(s).hydrate(pid)
            assert ksa["knowledge"][0]["content"] == "設備原理"
            latest = await DocRepo(s).latest(pid)
            assert latest["content"]["ocs_profile"]["ocs_code"] == "ENT-001"
    finally:
        async with AsyncSessionLocal() as s:
            prof = await s.get(JobProfile, pid)
            if prof:
                await s.delete(prof)            # cascade 刪 ksa_items/document_versions
            user = await s.get(User, uid)
            if user:
                await s.delete(user)
            await s.commit()
```
Run: `TEST_DATABASE_URL=... uv run pytest tests/test_live_db_persist.py -v`
Expected: FAIL（`LiveDbPersist` 不存在）。

- [ ] **Step 2: 實作 LiveDbPersist（append 到 deps.py）**

在 `backend/app/graph_v3/deps.py` 頂部確認有 import（多半已有 `AsyncSession`）；檔末 append：
```python
class LiveDbPersist:
    """Live serving 的 PersistPort：每操作開一短命 session、委派 DbPersist、各自 commit
    （write-through，D16）。deps 在 app 啟動一次性注入、無 per-request scope，故用 factory。"""

    def __init__(self, session_factory):
        self._sf = session_factory

    async def set_selected_ocs(self, job_profile_id, ocs_code) -> None:
        async with self._sf() as s:
            await DbPersist(s).set_selected_ocs(job_profile_id, ocs_code)
            await s.commit()

    async def flush_tasks(self, job_profile_id, tasks) -> None:
        async with self._sf() as s:
            await DbPersist(s).flush_tasks(job_profile_id, tasks)
            await s.commit()

    async def flush_ksa(self, job_profile_id, ksa) -> None:
        async with self._sf() as s:
            await DbPersist(s).flush_ksa(job_profile_id, ksa)
            await s.commit()

    async def save_document(self, job_profile_id, content) -> dict:
        async with self._sf() as s:
            doc = await DbPersist(s).save_document(job_profile_id, content)
            await s.commit()
            return doc
```

- [ ] **Step 3: 通過測試**

Run: `TEST_DATABASE_URL=... uv run pytest tests/test_live_db_persist.py -v`
Expected: 1 passed.

- [ ] **Step 4: Commit**
```bash
git add backend/app/graph_v3/deps.py backend/tests/test_live_db_persist.py
git commit -m "feat(graph_v3): LiveDbPersist (session-factory, commit per op) for live serving"
```

---

### Task 2：build_live_deps + build_live_sdk（真依賴組裝）

**Files:**
- Modify: `backend/app/graph_v3/serving.py`（新增 `build_live_deps`、`build_live_sdk`；保留 `build_demo_sdk`/`AGENT_NAME`）
- Test: `backend/tests/test_serving_live.py`

**Interfaces:**
- Consumes: `HttpIndexerClient`、`OpenRouterLlm`、`LiveDbPersist`、`AsyncSessionLocal`、`build_graph_v3`、`settings`。
- Produces:
  - `build_live_deps() -> Deps`（knowledge=HttpIndexerClient(設定值)、persist=LiveDbPersist(AsyncSessionLocal)、llm=OpenRouterLlm()）。
  - `build_live_sdk(checkpointer, deps) -> CopilotKitRemoteEndpoint`（用傳入 checkpointer 建 graph、deps 注入 agent config）。

- [ ] **Step 1: 失敗測試（型別正確、不打網路）**

Create `backend/tests/test_serving_live.py`:
```python
from langgraph.checkpoint.memory import MemorySaver

from app.graph_v3.serving import AGENT_NAME, build_live_deps, build_live_sdk
from app.graph_v3.deps import LiveDbPersist
from app.services.knowledge.http_client import HttpIndexerClient
from app.graph_v3.llm import OpenRouterLlm


def test_build_live_deps_types():
    deps = build_live_deps()
    assert isinstance(deps.knowledge, HttpIndexerClient)
    assert isinstance(deps.persist, LiveDbPersist)
    assert isinstance(deps.llm, OpenRouterLlm)


def test_build_live_sdk_registers_agent():
    # 用 MemorySaver 當 checkpointer 佔位（不需真 PG；只驗組裝）
    sdk = build_live_sdk(MemorySaver(), build_live_deps())
    assert AGENT_NAME in [a.name for a in sdk.agents]
```
Run: `uv run pytest tests/test_serving_live.py -v`
Expected: FAIL（`build_live_deps`/`build_live_sdk` 不存在）。

- [ ] **Step 2: 實作（append 到 serving.py）**

在 `backend/app/graph_v3/serving.py` 頂部 import 區加：
```python
from app.config import settings
from app.database import AsyncSessionLocal
from app.graph_v3.deps import Deps, LiveDbPersist
from app.graph_v3.llm import OpenRouterLlm
from app.services.knowledge.http_client import HttpIndexerClient
```
檔末 append：
```python
def build_live_deps() -> Deps:
    return Deps(
        knowledge=HttpIndexerClient(settings.indexer_base_url,
                                    settings.indexer_api_key,
                                    settings.indexer_timeout_s),
        persist=LiveDbPersist(AsyncSessionLocal),
        llm=OpenRouterLlm(),
    )


def build_live_sdk(checkpointer, deps) -> CopilotKitRemoteEndpoint:
    graph = build_graph_v3(checkpointer=checkpointer)
    agent = LangGraphAGUIAgent(
        name=AGENT_NAME,
        description="JD 撰寫顧問（v3 live）",
        graph=graph,
        config={"configurable": {"deps": deps}},
    )
    return CopilotKitRemoteEndpoint(agents=[agent])
```
（`CopilotKitRemoteEndpoint`/`LangGraphAGUIAgent`/`build_graph_v3`/`AGENT_NAME` 已在檔內 import/定義。）

- [ ] **Step 3: 通過測試 + 既有 serving 測試不破**

Run: `uv run pytest tests/test_serving_live.py tests/test_serving_smoke.py -v`
Expected: 全 pass。

- [ ] **Step 4: Commit**
```bash
git add backend/app/graph_v3/serving.py backend/tests/test_serving_live.py
git commit -m "feat(graph_v3): build_live_deps + build_live_sdk (real indexer/persist/llm)"
```

---

### Task 3：copilotkit_live_app（lifespan 持有 AsyncPostgresSaver + httpx，註冊端點）

**Files:**
- Create: `backend/app/copilotkit_live_app.py`
- Test: `backend/tests/test_copilotkit_live_app.py`

**Interfaces:**
- Consumes: `open_pg_checkpointer`（`app/graph_v3/checkpointer.py`）、`build_live_deps`/`build_live_sdk`（Task 2）、`settings`。
- Produces: `app`（FastAPI，production 入口）：lifespan 內 `AsyncExitStack` 進 checkpointer → 建 deps+sdk → `add_fastapi_endpoint(app, sdk, "/copilotkit")`；shutdown 關 `deps.knowledge`。`/healthz` 回 ok。

- [ ] **Step 1: 失敗測試（TestClient 觸發 lifespan：healthz + /copilotkit 掛載；無 DB 則 skip）**

Create `backend/tests/test_copilotkit_live_app.py`:
```python
import os
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"),
                                reason="live app lifespan needs Postgres for AsyncPostgresSaver")


def test_live_app_lifespan_mounts_endpoint():
    # 讓 live app 的 PG checkpointer 指向測試 DB
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    from app.copilotkit_live_app import app
    with TestClient(app) as c:
        assert c.get("/healthz").json()["status"] == "ok"
        paths = [getattr(r, "path", "") for r in app.routes]
        assert any("/copilotkit" in p for p in paths), f"no /copilotkit route in {paths}"
```
> 註：`settings` 在 import 時讀環境；測試在 import `copilotkit_live_app` 前設 `DATABASE_URL=$TEST_DATABASE_URL`，確保 checkpointer 連到測試 DB。若 `settings.database_url` 已是測試 DB 則此行無害。
Run: `TEST_DATABASE_URL=... uv run pytest tests/test_copilotkit_live_app.py -v`
Expected: FAIL（`app.copilotkit_live_app` 不存在）。

- [ ] **Step 2: 實作 copilotkit_live_app.py**

Create `backend/app/copilotkit_live_app.py`:
```python
"""Production v3 CopilotKit app：live deps + AsyncPostgresSaver（D15/D17）。
跑：uvicorn app.copilotkit_live_app:app --port 8000
demo（無依賴）仍在 app.copilotkit_app。"""
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from copilotkit.integrations.fastapi import add_fastapi_endpoint

from app.config import settings
from app.graph_v3.checkpointer import open_pg_checkpointer
from app.graph_v3.serving import build_live_deps, build_live_sdk


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        saver = await stack.enter_async_context(open_pg_checkpointer(settings.database_url))
        deps = build_live_deps()
        add_fastapi_endpoint(app, build_live_sdk(saver, deps), "/copilotkit")
        try:
            yield
        finally:
            await deps.knowledge.aclose()   # 關 httpx client


app = FastAPI(title="jobintel v3 (live)", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
```

- [ ] **Step 3: 通過測試**

Run: `TEST_DATABASE_URL=... uv run pytest tests/test_copilotkit_live_app.py -v`
Expected: 1 passed。
> 若 `add_fastapi_endpoint` 在 lifespan 內註冊的路由 TestClient 看不到：改為在 module 載入時先 `add_fastapi_endpoint(app, build_live_sdk(<lazy>), ...)` 不可行（需 saver）→ 改用 app.router.routes 在 lifespan append 後仍生效的驗證；若實測 CopilotKit 對此有特殊行為，回報 BLOCKED 由 controller 決定（可能改為 startup event 或把 graph 放 app.state 由固定端點引用）。

- [ ] **Step 4: 全套件 + Commit**

Run: `TEST_DATABASE_URL=... uv run pytest -q`
Expected: 全綠（既有 + 本期新測；無 DB 時新 DB/live 測試 skip）。
```bash
git add backend/app/copilotkit_live_app.py backend/tests/test_copilotkit_live_app.py
git commit -m "feat(serving): live CopilotKit app with lifespan-owned AsyncPostgresSaver + httpx cleanup"
```

- [ ] **Step 5: 更新專案記憶**

更新 `C:\Users\chenb\.claude\projects\s--jobintel-ai\memory\`：記 live-wire A DONE（LiveDbPersist + build_live_sdk + copilotkit_live_app）；下一步 = concern B（移除舊代碼，保留 constants/prompts，動 main.py 路由）。

---

## 完成後
- **產出**：production 入口 `copilotkit_live_app`（真 indexer/persist/checkpointer）；demo 與舊路徑不動。
- **手動驗證（非自動測試）**：啟 indexer（`S:\jd-ocs-indexer` → `uv run jd-ocs-indexer serve --port 8000`）；設 `INDEXER_BASE_URL`/`OPENROUTER_API_KEY`/`DATABASE_URL`；`uvicorn app.copilotkit_live_app:app --port 8001` 跑一條真流程。
- **下一步**：
  - **concern B**：移除 `app/graph/`(留 constants/prompts)、`icap_*`、`llm_gateway`、`ocs_builder`、舊 orchestrator；連帶處理/移除 `main.py` 的 `tasks`/`interviews` 路由。
  - **Phase ⑤**：OTel + eval 閘門。
  - **前端**：CopilotKit 接 interrupt（select_profile/edit_tasks/ask_human/edit_ksa/preview）。

## Self-Review
- **Spec/決策覆蓋**：D15（只做 A）✓；D16（LiveDbPersist session-factory + commit per op）✓ Task 1；D17（lifespan 持 checkpointer + 獨立 live app + 保留 demo）✓ Task 3；真 indexer/llm 注入 ✓ Task 2。
- **不破壞**：`build_demo_sdk`/`copilotkit_app.py`/`main.py`/`DbPersist(session)` 皆不動；既有 serving 測試在 Task 2 Step 3 一併跑。
- **無 placeholder**：每 task 有完整 test + 實作碼 + 指令；唯一不確定點（CopilotKit 在 lifespan 註冊端點）已在 Task 3 Step 3 標明 BLOCKED 路徑。
- **型別一致**：`LiveDbPersist(session_factory)`、`build_live_deps()->Deps`、`build_live_sdk(checkpointer, deps)->CopilotKitRemoteEndpoint`、`deps.knowledge.aclose()`（HttpIndexerClient 有此法）跨 task 對齊。
- **測試隔離**：LiveDbPersist 真 DB 測試自建自清（cascade delete + finally），不依賴 rollback fixture（因它自管 commit）。
