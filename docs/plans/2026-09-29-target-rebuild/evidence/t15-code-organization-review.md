# T15 補遺：程式組織審查——高內聚、低耦合（2026-10-01）

- 範圍：後端 `apps/api/src/caliburn`（204 個模組，約 2.19 萬行，不含生成碼與 migration 版本檔）與前端 `apps/web/src`（65 個正式檔，約 5,640 行）。依 Owner 要求「審核代碼規範、寫法，要高內聚、低耦合」，以[程式組織](../../../implementation/code-organization.md)與[程式撰寫規範](../../../implementation/coding-standard.md)為判準。基準提交 `d98c0daf`。
- 不改產品行為；只修有具體反例的結構問題，每項先有失敗的檢查或測試（Red），再修到通過（Green）。T15 本身已於 [T15 條件對照](t15-capacity-measurements.md#6-t15-完成對照2026-10-01-有界收尾)勾選；本頁是維護性的補充證據，不重開、也不改變 T14／T16／T17／T18 的狀態。

## 判準與方法

規範自己說「不強迫每函式最多若干行／參數」「模組超大先找職責混合，不用固定行數硬拆」，所以不以行數為罰則。判準取其可檢查的部分：

1. 層方向（程式組織 §2）：依賴只向下；`models` 純淨；角色之間不互相 import；前端 `shared` 不 import feature、feature 不 import 別的 feature。
2. 內聚：一個模組／類別的內容是否為同一責任一起變動；是否有重複的同一段邏輯（兩處要同步修改的證據）；有無「過渡」殘留。
3. 耦合：模組與套件層級的 import 圖有無環；上行 import；扇出過大的非組裝根。
4. 工具鏈：Ruff（E／F／I／UP／B／ASYNC／N／A／RUF006／RUF100）、mypy strict、TypeScript strict、ESLint、Prettier。

方法是工具鏈全跑一次，再用一支唯讀的標準庫 AST 腳本量測：import 圖（模組、套件兩級，含 `TYPE_CHECKING` 與函式內 import）、檔案／函式長度與分支數、同一模組內定義的連通分量（內聚代理）、類別方法的共用屬性（LCOM4）、常見壞味道的計數；前端以 regex 抓相對 import 並分區。這些是**描述性量測**，能執行的規則才進入測試或 lint；沒有新增架構分析平台，腳本不納入產品。

## 結果總覽（修改前，基準 `d98c0daf`）

| 面向 | 結果 |
|---|---|
| 工具鏈 | Ruff check／format、mypy strict（278 檔）、`tsc`、ESLint、Prettier **全部乾淨** |
| 模組級 import 環 | **0**（含 `TYPE_CHECKING`）；沒有動態 import；函式內 import 僅 5 處 |
| 套件級環 | **2**：`adapters` ↔ `settings`、`transport` ↔ `workflows` |
| 壞味道 | 無 `type: ignore`／`noqa`／TODO／`print`／`global`／`time.sleep`／`**kwargs`／模組級可變狀態／位置布林旗標；`except Exception` 22 處皆在隔離／恢復邊界；`Any` 16 處在 provider 邊界；`cast` 2 處 |
| 內聚 | 中位數模組 86 行、無缺 docstring 的大模組；`models.py` 內的簇是領域值＋其錯誤，屬正常；僅 3 個類別 LCOM4 ≥ 2 |
| 測試碼 | 949 個測試函式名稱最短 29 字元、中位數 62，皆表達情境與保證，沒有 `test_01` 類名稱；沒有超過 40 KB 的測試檔 |
| 前端 | 無 feature→feature、shared→feature 的 import；無 `any`／非空斷言／`ts-ignore`／`eslint-disable`／`dangerouslySetInnerHTML`；`useEffect` 只有 5 處 |
| 長函式 | 34 個 > 60 行、17 個分支數 > 20、11 個參數 > 7；集中在共用執行與組裝根（見「保留的已知債」） |

整體品質好：層次大致被遵守，債務集中在少數可指名的位置。以下是有具體反例的發現。

**修改後（同一腳本）：**套件級環 **2 → 0**、模組級仍為 0；> 60 行的函式 34 → 33（組裝根的兩個大函式縮為約 15–40 行）；模組 204 個不變、總行數 21,881 → 21,868（重複開頭移除，新增共用模組與測試不計）；mypy 仍 278 檔、Ruff 乾淨。長函式主體（共用執行的三個恢復狀態機）依下文刻意保留。

## 發現與處置

| # | 發現（證據） | 處置 | Red → Green |
|---|---|---|---|
| F1 | **B1／B2 共用組裝放在 `workflows/memory_analysis`，卻 import `transport.model_tools`**（9 個 import，造成 `transport` ↔ `workflows` 套件環）；`agents/memory_analysis` 另有兩個標明「Transitional」的 re-export 殼（`results.py`、`tools.py`），只被 2 個測試檔使用 | `runner.py`、`context.py` 移到 `agents/memory_analysis/`（它們就是角色層組裝）；`tools.py` 移到 `transport/model_tools/memory_analysis.py`（與讀寫工具同層）；`AnalysisRecovery` 與其他交接值同放 `workflows/memory_analysis/results.py`；刪兩個殼並改正 2 個測試的 import | 新增的層規則在真實樹上 **1 failed**（正好 9 個上行 import）；搬移後 **115 passed**（含真 PG 的 runner、parent、batch、handoff 測試） |
| F2 | **`settings` ↔ `adapters` 套件環**：`settings` 為驗證模型而 import `adapters.openai_models`，而 `adapters.database`、`process_lock` 又 import `settings.DatabaseSettings` | `DatabaseSettings` 由使用它的 adapter 擁有（`adapters/database_settings.py`），`Settings` 只負責組合；adapter 不再 import `settings` | 測例 `adapters.database` import `settings` 被偵測；真實樹 0 違規；設定／migration／leader lock 相關 **101 passed** |
| F3 | **兩個角色 runner 重複同一段開頭**：`_fix_budget`（逐字相同，只差例外訊息）、`ModelRequestExecutor`＋預留常數 `0.0001`／`0.50`、`CompactionRuntime`、`compact_window` 閉包。先前換 provider profile 時必須在兩份同步修改，正是重複的成本 | 新增 `workflows/model_runtime.py`（`fix_execution_policy`、`bind_model_runtime`、預留常數）與 `agent_execution.bind_window_compaction`；兩個 runner 各少約 40 行，仍各自擁有 prompt、工具、歷史與完成，**不是 BaseAgent** | 3 個新的真 PG 測例（首次依設定固定額度、重啟保留原額度、計價基準不同即衝突）；runner／壓縮／恢復相關 **66 passed**，`test_role_prompt_contracts` 的補丁目標改為共用函式 |
| F4 | **組裝根單一巨大 lifespan**（`create_app` 162 行、`lifespan` 129 行、深度 4） | 拆成 `_reset_runtime_state`、`_start_database_runtime`、`_start_model_runtime`，路由改成有序常數 `ROUTERS`；AsyncExitStack 的推入順序（renderer → saver → SDK → consultant supervisor → Memory supervisor）與 LIFO 關閉順序不變 | bootstrap、web delivery、HTTP 執行／控制／supervisor／commentary／憑證隔離等 **43 passed** |
| F5 | **前端 feature 互不 import 只靠慣例**：ESLint 只擋 `shared` → feature／app，沒有擋 feature → feature 或 feature → app | `eslint.config.js` 依 feature 清單產生限制規則（相對路徑 regex） | 探針檔 import 兄弟 feature 與 app 時原先**無報告**；加規則後**兩項皆報錯**，探針移除後整個專案 ESLint 乾淨、Prettier 通過 |
| F6 | **「沒有 production 呼叫者」的 API**：`release_block` 只在測試中被呼叫，最終失敗後背景整理永遠停止（T11 已知限制） | 以訪談進度解除（見[T11 更新](t11-memory-batch.md#任務完成對照2026-09-30-恢復後)）；dead hook 與其操作種類移除 | 改寫的政策測例無實作時 `assert 'quota_exhausted' is None` 失敗，有實作 6 passed；舊資料列不自動解除另有測例 |

層方向規則現在以表格鎖在 `tests/unit/test_import_boundaries.py`：`adapters` 不 import 任何上層與 `settings`；`features` 不 import `workflows`／`transport`／`agents`；`agent_execution` 不 import `workflows`／`transport`；`workflows` 不 import `transport`／`agents`；`transport` 不 import `agents`；沒有人 import `bootstrap`；兩個 Memory 角色之間不互相 import（共用組裝 `agents/memory_analysis` 是明列的例外）。新增的 10 個反例都會被偵測，真實樹 0 違規。

## 保留的已知債與觸發條件（不在本輪處理）

以下是量測找到、但**刻意不改**的位置，原因都是「會動到已有 Red→Green 恢復保證的核心，卻沒有行為需求」：

| 位置 | 現況 | 為何不動 | 之後怎麼拆（觸發：下一次需要改該函式時） |
|---|---|---|---|
| `agent_execution/tool_steps.py::_run_response_flow_once`（245 行、分支 74） | 一個函式依序做：前置驗證、讀已存狀態、暫停對帳、HeldInputCount／HeldModelResponse 對帳、非作用中寫入者結算、控制再進入、invoke | 每個分支對應一個曾經失敗的恢復反例，註解即規格；拆分會動到整個恢復狀態機 | 以 `_HeldHandoff` 小物件取代 `nonlocal held`，再依階段抽成 `_reconcile_pause`／`_reconcile_held`／`_settle_inactive_writer`／`_reenter_control` 純搬移 |
| `tool_steps.py::_build_response_step`（363 行）與 `context_compaction.py::_run_context_boundary_once`（242 行） | LangGraph 以閉包定義全部節點 | 節點彼此共用 builder 層的限制與回呼；成圖後行為由 PG 測試固定 | 以持有限制與回呼的小類別，節點改為方法，`add_node` 用綁定方法 |
| `agents/memory_analysis/runner.py::run`（約 170 行）、`ConsultantRunner.run`（約 100 行） | 角色啟動序列 | 兩者的歷史／交接差異是真的，只有開頭已抽出共用 | 可再抽「恢復邊界核對」，目前差異大於相似 |
| `ConsultantRecovery` 與 `AnalysisRecovery` | 兩個相同的 union alias | 只是型別別名，合併收益小 | 放進 `agent_execution` 的單一 `HeldHandoff` |
| `transport/model_tools/jd_item_revision_wire.py::parse_item_revision` | 以 `isinstance` if／elif 梯處理 union（量測的「深度 12」是 elif 巢狀的假象） | 平坦易讀，改 `match` 純屬風格 | 下次新增 change 型別時改 `match` |
| 前端 `InterviewComposer.tsx`（345 行） | 同一個送出協定：草稿、待確認識別、恢復、完成後刷新、狀態顯示 | 這些共用同一組互鎖狀態，拆成多個 hook 反而把狀態機分散；現有三個測試檔固定行為 | 只把純顯示的狀態面板抽成元件；不抽狀態 |

## 驗證

後端（`apps/api`）：

```powershell
./.venv-target/Scripts/python.exe -m ruff check .
./.venv-target/Scripts/python.exe -m ruff format --check .
./.venv-target/Scripts/python.exe -m mypy
$env:CALIBURN_TEST_DATABASE_URL = 'postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
./.venv-target/Scripts/python.exe -B -m pytest tests -p no:cacheprovider -q
```

前端（`apps/web`，使用 Node 24 執行檔直接呼叫 `node_modules`）：`tsc --noEmit`、`eslint .`、`prettier --check` 全部乾淨。結果摘要見提交訊息及本頁末段。

## 限制

- 量測是靜態、描述性的；沒有證明所有動態呼叫路徑都遵守層方向，也不證明責任切分「剛好」。
- 單元／真 PG 測試是行為回歸，不是新的真模型品質證據；本頁沒有任何 OpenAI 外送或付費請求。
- 保留的已知債是判斷，不是遺漏：若 Owner 要求在最終驗收前處理，建議先處理 `_run_response_flow_once`，並以既有恢復測試與一次有界真模型旅程作回歸。
