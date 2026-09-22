# Concern B：移除舊代碼 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development。步驟用 `- [ ]`。
> **本地記錄（untracked，不 commit）。** 日期：2026-06-17。依據決策 **D18**（見 decision-log）、D5/D8。

**Goal:** 搬遷 graph_v3 仍需的 pure-data（`constants` + `prompts.indicator`）進 graph_v3，然後**全刪舊鏈**：`app/graph/`、`icap_*`、`interview_orchestrator`、`state_service`、舊 `interviews` REST 路由。`master` demo 不受影響（不同分支）。

**Architecture:** 兩步——(1) 重構搬遷 + 改 3 處 import（既有測試套件為安全網）；(2) 刪除 dead 模組 + 解除 main.py 對舊路由的接線，以「全套件綠 + `import app.main` 成功」為驗證。

**Tech Stack:** Python 3.13 / pytest。沿用 `backend/.venv`、`TEST_DATABASE_URL`。

## Global Constraints

- 分支 `feat/v3`；`master` 不動。
- **零測試依賴舊鏈**（已確認）→ 刪除不得破壞任何現有測試；全套件須維持綠（46 passed 基線）。
- **保留**：`app/graph_v3/*`、`app/services/document_service.py`、`app/api/routes/{users,job_profiles,tasks,documents}.py`、`document_service`。
- **不搬 dead prompts**：只搬 `prompts/indicator.py`（graph_v3 唯一用到的）；`prompts/star.py`、`prompts/interview.py` 隨 `app/graph/` 一起刪。
- 提交只 stage 明確路徑；**絕不** `git add -A`（untracked `docs/superpowers/` 不可 commit）。`git rm` 用明確路徑。

---

### Task 1：搬遷 constants + prompts.indicator 進 graph_v3，改 3 處 import

**Files:**
- Create: `backend/app/graph_v3/constants.py`（= 舊 `app/graph/constants.py` 內容，原樣）
- Create: `backend/app/graph_v3/prompts/__init__.py`（空）、`backend/app/graph_v3/prompts/indicator.py`（= 舊 `app/graph/prompts/indicator.py` 內容，原樣）
- Modify: `backend/app/graph_v3/deep_nodes.py`、`backend/app/api/routes/tasks.py`、`backend/tests/test_deep_five_w2h.py`

**Interfaces:**
- Produces: `app.graph_v3.constants`（含 `FIVE_W2H_REQUIRED`、`FIVE_W2H_LIST_FIELDS`、`INDICATOR_REQUIRED_FIELDS`、`TASK_COMPLETENESS_FIELDS` 等，與舊 constants 同名同值）；`app.graph_v3.prompts.indicator`（含 `PER_OUTPUT`、`SINGLE`）。
- 舊 `app.graph.constants` / `app.graph.prompts.indicator` 在 Task 2 才刪；本 task 結束時新舊並存、import 已全部指向新位置。

- [ ] **Step 1: 複製檔案到 graph_v3（內容原樣，不改一字）**

```bash
cd backend
cp app/graph/constants.py app/graph_v3/constants.py
mkdir -p app/graph_v3/prompts
: > app/graph_v3/prompts/__init__.py
cp app/graph/prompts/indicator.py app/graph_v3/prompts/indicator.py
```
（`app/graph_v3/prompts/__init__.py` 必須存在且為空，使其成為 package。）

- [ ] **Step 2: 改 3 處 import 指向 graph_v3**

1. `backend/app/graph_v3/deep_nodes.py`：
   - line 9 `from app.graph.constants import FIVE_W2H_REQUIRED, FIVE_W2H_LIST_FIELDS, INDICATOR_REQUIRED_FIELDS` → `from app.graph_v3.constants import FIVE_W2H_REQUIRED, FIVE_W2H_LIST_FIELDS, INDICATOR_REQUIRED_FIELDS`
   - line 10 `import app.graph.prompts.indicator as ind_prompts` → `import app.graph_v3.prompts.indicator as ind_prompts`
   - docstring（line 2）把「重用 app.graph.prompts.* 與 app.graph.constants」改為「重用 app.graph_v3.prompts.* 與 app.graph_v3.constants」。
2. `backend/app/api/routes/tasks.py` line 8：`from app.graph.constants import TASK_COMPLETENESS_FIELDS` → `from app.graph_v3.constants import TASK_COMPLETENESS_FIELDS`
3. `backend/tests/test_deep_five_w2h.py` line 11：`from app.graph.constants import FIVE_W2H_REQUIRED` → `from app.graph_v3.constants import FIVE_W2H_REQUIRED`

- [ ] **Step 3: 驗證（既有套件為安全網）**

確認新模組可 import 且值一致、相關測試綠：
```bash
uv run python -c "from app.graph_v3.constants import FIVE_W2H_REQUIRED, INDICATOR_REQUIRED_FIELDS, TASK_COMPLETENESS_FIELDS; import app.graph_v3.prompts.indicator as p; print(bool(p.PER_OUTPUT and p.SINGLE))"
TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/jobintel uv run pytest tests/test_deep_five_w2h.py tests/test_deep_indicator.py tests/test_deep_subgraph.py tests/test_node_task_pool.py tests/test_graph_v3_full_e2e.py -q
```
Expected：印出 `True`；測試全綠。

- [ ] **Step 4: 全套件 + Commit**
```bash
TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/jobintel uv run pytest -q   # 期望 46 passed
git add backend/app/graph_v3/constants.py backend/app/graph_v3/prompts/__init__.py backend/app/graph_v3/prompts/indicator.py backend/app/graph_v3/deep_nodes.py backend/app/api/routes/tasks.py backend/tests/test_deep_five_w2h.py
git status   # 確認無 docs/ staged、無 app/graph/ 變動
git commit -m "refactor(graph_v3): relocate constants + prompts.indicator into graph_v3 (concern B prep)"
```

---

### Task 2：刪除舊鏈（app/graph/、icap_*、orchestrator、state_service、interviews 路由）

**Files:**
- Delete: `backend/app/graph/`（整個目錄）、`backend/app/services/icap_matcher.py`、`backend/app/services/icap_retriever.py`、`backend/app/services/interview_orchestrator.py`、`backend/app/services/state_service.py`、`backend/app/api/routes/interviews.py`
- Modify: `backend/app/main.py`（移除 `interviews` import + include）
- Create: `backend/tests/test_old_chain_removed.py`（守衛測試）

**Interfaces:**
- Consumes: Task 1 已把 graph_v3 對 constants/prompts 的依賴改到新位置（故刪 `app/graph/` 安全）。
- Produces: `app.main.app` 仍可 import（移除 interviews 後不破）；舊模組不再存在。

- [ ] **Step 1: 失敗測試（守衛：舊模組已移除、app.main 仍可建）**

Create `backend/tests/test_old_chain_removed.py`:
```python
import importlib
import pytest


@pytest.mark.parametrize("mod", [
    "app.graph.graph",
    "app.graph.nodes.ocs_builder",
    "app.services.icap_retriever",
    "app.services.icap_matcher",
    "app.services.interview_orchestrator",
    "app.services.state_service",
    "app.api.routes.interviews",
])
def test_old_modules_are_gone(mod):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(mod)


def test_main_app_still_imports():
    import app.main
    assert app.main.app is not None


def test_kept_pure_data_lives_in_graph_v3():
    from app.graph_v3.constants import TASK_COMPLETENESS_FIELDS  # noqa: F401
    import app.graph_v3.prompts.indicator  # noqa: F401
```
Run: `uv run pytest tests/test_old_chain_removed.py -q`
Expected: FAIL（舊模組此時仍存在 → `test_old_modules_are_gone` 失敗）。

- [ ] **Step 2: 移除 main.py 對 interviews 的接線**

`backend/app/main.py`：
- import 行 `from app.api.routes import documents, interviews, job_profiles, tasks, users` → 移除 `interviews`（變 `documents, job_profiles, tasks, users`）。
- 刪除 `app.include_router(interviews.router,   prefix="/api/v1")` 該行。

- [ ] **Step 3: git rm 刪除舊鏈（明確路徑）**

```bash
cd backend
git rm -r app/graph
git rm app/services/icap_matcher.py app/services/icap_retriever.py app/services/interview_orchestrator.py app/services/state_service.py
git rm app/api/routes/interviews.py
```
（注意：`app/graph_v3/` 不受影響；只刪 `app/graph/`。）

- [ ] **Step 4: 通過守衛測試 + 全套件**

```bash
uv run pytest tests/test_old_chain_removed.py -q                      # 期望全綠
TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/jobintel uv run pytest -q
```
Expected: 守衛測試綠；全套件綠（46 + 3 守衛 = 49 passed，數字以實際為準；**不得有 import error / collection error**）。
若有殘留 import 舊模組導致 collection error → 找出該檔修正（理論上不應有，已確認零依賴）。

- [ ] **Step 5: Commit**
```bash
git add backend/app/main.py backend/tests/test_old_chain_removed.py
git status   # 確認：刪除的檔在 staged、無 docs/ staged
git commit -m "refactor: remove legacy graph/icap/orchestrator chain + old interviews route (concern B)"
```

- [ ] **Step 6: 更新專案記憶**

更新 `C:\Users\chenb\.claude\projects\s--jobintel-ai\memory\phase4-status.md`：記 concern B DONE（舊鏈移除、constants/prompts 搬入 graph_v3）；下一步改 Phase ⑤（OTel+eval）/ 前端。

---

## 完成後
- **產出**：repo 只剩 v3 路徑（graph_v3 + knowledge + persistence + 保留的 CRUD 路由 + document_service）；舊 graph/icap/orchestrator 與舊 interviews 路由消失。
- **手動驗證**：`uv run python -c "import app.main"` 與啟動 `uvicorn app.main:app` 應正常（少了 /api/v1/interviews）；`uvicorn app.copilotkit_live_app:app` 不受影響。
- **下一步**：Phase ⑤（OTel + eval 閘門）；前端 CopilotKit 接 interrupt；（可選清理）config 的 dead `icap_*` settings、interviews 專用的 dead schemas。

## Self-Review
- **決策覆蓋**：D18 全部 ✓（搬 constants+prompts.indicator、不搬 dead star/interview prompts、刪整個舊鏈 + interviews 路由 + main.py 接線）。
- **安全網**：零測試依賴舊鏈（已 grep 確認）；Task 1 用既有測試驗搬遷；Task 2 用守衛測試（舊模組 ModuleNotFoundError + `import app.main` 成功）驗刪除。
- **無 placeholder**：每 step 有明確檔案/指令/實際測試碼。
- **不破壞**：`master` 不同分支不受影響；`build_doc.py` 不涉 constants/prompts；document_service/CRUD 路由保留；graph_v3 import 已在 Task 1 全部轉新位置才於 Task 2 刪舊。
- **型別/名稱一致**：搬遷為原樣複製（同名同值）；3 處 import 改 `app.graph.*`→`app.graph_v3.*`，符號不變。
