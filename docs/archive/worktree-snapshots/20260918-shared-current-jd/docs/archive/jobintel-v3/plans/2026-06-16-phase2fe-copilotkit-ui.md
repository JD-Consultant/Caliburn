# Phase ②-FE 第一條真 UI 端到端（CopilotKit）— Implementation Plan

> **For agentic workers:** 這是**整合 phase**，非純 pytest。後端可 smoke-test；前端要跑起來、**最終點擊驗證由使用者在瀏覽器做**（agent 開不了瀏覽器）。標 `[runtime-verify]` 的步驟＝執行時實測，非單元測試。

**Goal:** 把 Phase ② 的 `graph_v3`（`pick_profile` / `build_task_pool` 兩個 interrupt 節點）透過 **CopilotKit serving** 接到**現有 Next.js 前端**，用 **stub KnowledgeClient**（不需真 indexer/Qdrant）證明「**瀏覽器 ↔ CopilotKit ↔ graph_v3 ↔ interrupt/resume**」整條 plumbing 通：使用者描述職務 → 選 OCS → 編輯任務清單 → 流程推進。

**架構對齊（守住）：** D6 分層（graph state 工作態 + checkpointer；業務表 of-record——本 demo 用 stub persist，真 DB session 留 live-persistence phase）、D7 `KnowledgeClient` 介面（stub 實作，真 HTTP 後接）、D8 interrupt 驅動 HITL、D11 **漸進接現有前端**（復用 `TaskPanel`，不重建）。

**Tech Stack（probe 已實測）：** copilotkit 0.1.94（`CopilotKitRemoteEndpoint` + `LangGraphAGUIAgent` + `add_fastapi_endpoint`）、langgraph 1.2.5、langchain 1.3.9、fastapi 0.137.1（已在 venv）。前端：`@copilotkit/react-core`（v2）+ `@copilotkit/react-ui`，Node v22 / npm 10.9（frontend `node_modules` 需 `npm install`）。

**前置：** 在 `feat/v3`；Phase ①② 已合入（13 commits，19 tests）；venv 已裝 copilotkit。

> ⚠️ **evolving surface**：v2 self-hosted FastAPI+AG-UI 仍在演進。`LangGraphAGUIAgent(config=...)` 是否把 deps 透到 node（`config["configurable"]["deps"]`）→ **Task 1 smoke 驗**；若不透，fallback：`app/graph_v3/runtime.py` 用 `contextvar` 提供 deps，node 改 `get_deps()`（同時更新 Phase ② node 測試）。

---

### Task 1：stub deps + serving SDK + 後端 smoke

**Files:** Create `backend/app/graph_v3/stubs.py`、`backend/app/graph_v3/serving.py`；Test `backend/tests/test_serving_smoke.py`；Modify `backend/requirements.txt`

- [ ] **Step 1: stub 實作（stub-first 的資料來源 + persist）**

Create `backend/app/graph_v3/stubs.py`:
```python
from uuid import UUID

from app.services.knowledge.models import (
    SearchResult, Hit, TaskPool, PoolGroup, PoolUnit, PoolTask, Pairs, TasksByIdResult,
)


class StubKnowledge:
    """Demo 用假 KnowledgeClient（無需真 indexer/Qdrant）。"""
    async def search(self, query, **kw) -> SearchResult:
        return SearchResult(mode="dense", hits=[
            Hit(id="OC1", ocs_code="KRM2421-001v4", chunk_level="profile", job_title="設備維護工程師"),
            Hit(id="OC2", ocs_code="KRM2422-001v4", chunk_level="profile", job_title="生產線技術員"),
        ])

    async def task_pool(self, ocs_codes, **kw) -> TaskPool:
        return TaskPool(groups=[PoolGroup(ocs_code=(ocs_codes or ["OC1"])[0], job_title="設備維護工程師",
            units=[PoolUnit(unit_id="U1", unit_title="預防保養", tasks=[
                PoolTask(id="T1.1", task_id="T1.1", task_title="例行設備巡檢", activity_examples=["每日點檢", "異常記錄"]),
                PoolTask(id="T1.2", task_id="T1.2", task_title="保養排程管理", activity_examples=["排定週期保養"])])])])

    async def pairs(self, ocs_code) -> Pairs: return Pairs(ocs_code=ocs_code)
    async def tasks_by_id(self, ids) -> TasksByIdResult: return TasksByIdResult(tasks=[])
    async def healthz(self) -> bool: return True


class InMemoryPersist:
    """Demo 用 PersistPort：只記在記憶體，不寫 DB（真 DbPersist 留 live-persistence phase）。"""
    def __init__(self): self.selected: dict = {}; self.tasks: dict = {}
    async def set_selected_ocs(self, job_profile_id: UUID, ocs_code: str) -> None:
        self.selected[str(job_profile_id)] = ocs_code
    async def flush_tasks(self, job_profile_id: UUID, tasks: list[dict]) -> None:
        self.tasks[str(job_profile_id)] = tasks
```

- [ ] **Step 2: serving SDK（probe-grounded API）**

Create `backend/app/graph_v3/serving.py`:
```python
from copilotkit import CopilotKitRemoteEndpoint, LangGraphAGUIAgent
from langgraph.checkpoint.memory import MemorySaver

from app.graph_v3.graph import build_graph_v3
from app.graph_v3.deps import Deps
from app.graph_v3.stubs import StubKnowledge, InMemoryPersist

AGENT_NAME = "jd_authoring"


def build_demo_sdk() -> CopilotKitRemoteEndpoint:
    """stub-first：graph_v3 + 假 deps，記憶體 checkpointer。"""
    deps = Deps(knowledge=StubKnowledge(), persist=InMemoryPersist())
    graph = build_graph_v3(checkpointer=MemorySaver())
    agent = LangGraphAGUIAgent(
        name=AGENT_NAME,
        description="JD 撰寫顧問（v3 stub demo）",
        graph=graph,
        config={"configurable": {"deps": deps}},
    )
    return CopilotKitRemoteEndpoint(agents=[agent])
```

- [ ] **Step 3: 失敗測試 `backend/tests/test_serving_smoke.py`** [部分 runtime-verify]
```python
from app.graph_v3.serving import build_demo_sdk, AGENT_NAME


def test_demo_sdk_registers_agent():
    sdk = build_demo_sdk()
    names = [a.name for a in sdk.agents]
    assert AGENT_NAME in names
```
Run: `cd /s/jobintel-ai/backend && .venv/Scripts/python -m pytest tests/test_serving_smoke.py -q`
Expected: 先 RED（模組未建）→ 建好後 GREEN（1 passed）。
> **[runtime-verify]** 額外手動確認 `LangGraphAGUIAgent(config=...)` 的 deps 真的透到 node：暫時在 `pick_profile` 開頭 `print` deps 或寫一個 driver 跑一次 `build_demo_sdk()` 的 agent。若 deps 為 None → 採 contextvar fallback（見頂部警告）。

- [ ] **Step 4: 更新 requirements（反映 venv 實況）**

`requirements.txt`：移除/取代衝突的 langchain 舊 pin → `langchain==1.3.9`、`langchain-core==1.4.7`；新增 `copilotkit==0.1.94`。移除先前 Phase③ TODO 註解（已解）。

- [ ] **Step 5: Commit**
```bash
git -C /s/jobintel-ai add backend/app/graph_v3/stubs.py backend/app/graph_v3/serving.py backend/tests/test_serving_smoke.py backend/requirements.txt
git -C /s/jobintel-ai commit -m "feat(graph_v3): CopilotKit serving (stub deps) + agent registration smoke"
```

---

### Task 2：把 CopilotKit endpoint 掛上 FastAPI app

**Files:** Create `backend/app/copilotkit_app.py`（獨立 demo app，不動既有 `main.py`）；Test `backend/tests/test_copilotkit_endpoint.py`

- [ ] **Step 1: 獨立 demo app（避免動到舊 main.py / 舊 graph）**

Create `backend/app/copilotkit_app.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from copilotkit.integrations.fastapi import add_fastapi_endpoint
from app.graph_v3.serving import build_demo_sdk

app = FastAPI(title="jobintel v3 CopilotKit demo")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"],
                   allow_methods=["*"], allow_headers=["*"])
add_fastapi_endpoint(app, build_demo_sdk(), "/copilotkit")


@app.get("/healthz")
def healthz(): return {"status": "ok"}
```

- [ ] **Step 2: 端點 smoke 測試** [runtime-verify]
```python
from fastapi.testclient import TestClient
from app.copilotkit_app import app


def test_healthz():
    with TestClient(app) as c:
        assert c.get("/healthz").json()["status"] == "ok"


def test_copilotkit_route_mounted():
    with TestClient(app) as c:
        # info/discovery endpoint 應存在（非 404）。實際路徑/方法以 add_fastapi_endpoint 為準，
        # 執行時若 404 → 用 app.routes 印出實際掛載路徑後修正本斷言。
        paths = [getattr(r, "path", "") for r in app.routes]
        assert any("/copilotkit" in p for p in paths)
```
Run pytest → GREEN（route 已掛）。
> **[runtime-verify]** 啟動 `uvicorn app.copilotkit_app:app --port 8000` 並確認啟動無誤、`/healthz` 回 ok。

- [ ] **Step 3: Commit**
```bash
git -C /s/jobintel-ai add backend/app/copilotkit_app.py backend/tests/test_copilotkit_endpoint.py
git -C /s/jobintel-ai commit -m "feat(graph_v3): mount CopilotKit /copilotkit endpoint on demo FastAPI app"
```

---

### Task 3：前端 — CopilotKit provider + runtime（漸進，不重建）

**Files:** Modify `frontend/src/app/layout.tsx`（或新增 demo route）；Create Next runtime route；`frontend` npm 安裝。 [全 runtime-verify]

- [ ] **Step 1: 安裝套件**

Run（在 `s:\jobintel-ai\frontend`）：`npm install` 然後 `npm install @copilotkit/react-core @copilotkit/react-ui`
（版本以 CopilotKit v2 為準；`useInterrupt` 來自 `@copilotkit/react-core/v2`。）

- [ ] **Step 2: Next.js CopilotKit runtime route** — 依 CopilotKit v2 官方 Next 設定建 `frontend/src/app/api/copilotkit/route.ts`，`runtimeUrl` 指向後端 `http://localhost:8000/copilotkit`（self-hosted AG-UI）。實際樣板以 `npx copilotkit@latest` 或官方 docs 為準（evolving）。

- [ ] **Step 3: Provider 包住 demo 頁** — 在一個新 demo 頁（例如 `frontend/src/app/v3-demo/page.tsx`）外層包 `<CopilotKit runtimeUrl="/api/copilotkit" agent="jd_authoring">`，避免動到既有主流程頁。

- [ ] **Step 4 [runtime-verify]:** `npm run dev`，頁面能載入、provider 無 console error、能連上後端（network 看到 /api/copilotkit 請求）。

- [ ] **Step 5: Commit**（前端檔 + package.json/lock）
```bash
git -C /s/jobintel-ai add frontend/src/app/api/copilotkit frontend/src/app/v3-demo frontend/src/app/layout.tsx frontend/package.json frontend/package-lock.json
git -C /s/jobintel-ai commit -m "feat(fe): CopilotKit provider + runtime route (v3 demo page)"
```

---

### Task 4：前端 — 兩個 interrupt 的 UI（select_profile / edit_tasks）

**Files:** demo 頁元件；復用 `frontend/src/components/interview/TaskPanel.tsx`。 [全 runtime-verify]

- [ ] **Step 1: `useInterrupt` 接 `select_profile`** — `useInterrupt({ render: ({event, resolve}) => ... })`：`event.value.kind === "select_profile"` 時，把 `event.value.candidates` 渲染成可選清單，選一個 → `resolve({ ocs_code })`（→ graph resume）。

- [ ] **Step 2: `useInterrupt` 接 `edit_tasks`** — `event.value.kind === "edit_tasks"` 時，把 `event.value.tasks` 餵給**復用的 `TaskPanel`**（可增/刪/改），確認 → `resolve({ tasks: edited })`。

- [ ] **Step 3: `useCoAgent`** 讀 agent 共享 state（顯示 current_step / 已選 OCS / 任務清單），讓 UI 反映流程。

- [ ] **Step 4: Commit**（demo 頁元件）

---

### Task 5：跑起來 + 使用者瀏覽器驗收 [runtime-verify，協作]

- [ ] **Step 1:** 後端 `uvicorn app.copilotkit_app:app --port 8000`；前端 `npm run dev`（:3000）。
- [ ] **Step 2（使用者做）:** 開 `http://localhost:3000/v3-demo`，輸入職務描述 → **選 OCS**（select_profile interrupt）→ **編輯任務清單**（edit_tasks interrupt，TaskPanel）→ 確認 → 流程 `current_step` 推進到 `deep`。
- [ ] **Step 3:** 驗收標準：兩個 interrupt 都能在 UI 顯示 + 編輯 + resume；stub 任務清單正確顯示；無 console/server error。
- [ ] 通過 → Phase ②-FE 完成；記錄到 memory + decision log（live-wire 真 indexer/真 DbPersist + 深問子圖排後續 phase）。

---

## 完成後
- **產出**：第一條「瀏覽器 ↔ CopilotKit ↔ graph_v3 interrupt/resume」端到端通（stub 資料）。證明 D8 HITL + D11 漸進前端真的成立。
- **明確未做（對齊用，避免 scope 漂移）**：真 indexer 接線（換掉 StubKnowledge → HttpIndexerClient）、真 DbPersist 每請求 session、PostgresSaver 取代 MemorySaver、深問子圖（Phase ③）、live-wire 舊 orchestrator 退場。
- **風險點**：v2 self-hosted AG-UI 演進中——Task 1 的 deps-via-config、Task 2 的端點路徑、Task 3 的 Next runtime 樣板，三處標 [runtime-verify]，執行時以實測為準微調，**不偏離架構**。

## Self-Review
- 對齊 D6/D7/D8/D11 ✓（stub 仍走 Deps/PersistPort/KnowledgeClient 抽象、interrupt 驅動、復用 TaskPanel、不動既有 main/graph）。
- probe-grounded：serving API（LangGraphAGUIAgent/CopilotKitRemoteEndpoint/add_fastapi_endpoint）已實測存在；deps-via-config 有 fallback。
- 誠實：前端 + 端到端為 [runtime-verify]/協作，非 pytest；scope 嚴格限在「stub plumbing」，真資料/持久化/深問明列為未做。
