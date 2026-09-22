# 0043. `job_analysis` 本機 Current State 持久化與編輯權威

- 狀態：Accepted
- 日期：2026-07-29
- 取代：[0039](0039-local-multi-document-canonical-public-form-workspace.md)
- 研究：
  [本機 JD 分層編輯與 `job_analysis` PostgreSQL 持久化研究](../specs/2026-07-29-local-jd-authoring-and-postgresql-persistence-research.md)

## 脈絡

`app/job_analysis` 已以 greenfield 方式完成第一條 Task Analysis scripted vertical，但尚無資料庫、route 或 Web。
產品需要讓單一本機操作者保存、關閉及重開多份 JD，且能直接編輯目前文件。既有 `job_authoring`／vNext tables
沒有使用者資料，也承載已失效的 revision、hash、tenant 與舊契約；整合或搬遷只會把舊架構帶進新引擎。

同時，Current JD、AI 的 Current Work Model、待決 Proposal 與完成回合有不同的權威與修改生命週期，不能再塞成
一份 monolithic snapshot，也不需要拆成完整 Evidence/Event Sourcing 系統。

## 決定

### Greenfield 邊界

- 新 persistence 從空的 `job_analysis_*` tables 開始。
- 不 import、wrap、dual-write、轉換或回填 `app.job_authoring`／`app.interview_vnext` 資料。
- 舊 tables 暫留但不接線；新 durable vertical 驗證後再另案刪除。
- 0039 由本 ADR 完整取代。其本機多文件、Current State、內部模型不受公版限制等觀念，只有本 ADR
  重新寫明者繼續有效。

### 產品權威與編輯

- Current JD 是員工文件權威；AI 的 Current Work Model 是可修正的分析，不得覆寫員工文件。
- 員工直接編輯 Current JD 時立即保存，不在每次 keypress／save 呼叫 LLM；下次 AI 互動前才 reconcile。
- UI 不必顯示內部 `pending_reconciliation`。員工只需看到文件、提案與過時提案的白話結果。
- 第一版 UI 以分層編輯器呈現：公版必要欄位與 Task statement 常駐；purpose、context、frequency、
  responsibility role、enablers 可展開編輯；來源按需唯讀；ID、lineage、generation 等控制欄位隱藏。
- 內部 UI 可比公版更細；未來 export 才要求一模一樣的公版格式。

### PostgreSQL current-state 形狀

第一個 durable vertical 只建四張表：

1. `job_analysis_documents`：文件 metadata、versioned Work Model JSONB、active question、authority generation。
2. `job_analysis_jd_tasks`：員工可編輯的 Current JD Task relational rows。
3. `job_analysis_proposals`：一列一份原子 Proposal；status relational、versioned payload JSONB。
4. `job_analysis_journal`：完成的 employee turn、direct edit、proposal decision；append-only application seam。

Current Work Model 是 document-scoped atomic JSONB；Proposal payload 是 proposal-scoped atomic JSONB。兩者 hydrate
時必須經 versioned Pydantic contract 驗證並 fail closed。Journal 不是 Current State 真相，不要求可 replay，
也不做 Event Sourcing、CQRS、projection、hash chain 或 outbox。

O/P/K/S/A 與完整公版 header 等各自 production contract 成立後才新增 current relational tables；第一版不先建空表。
Task 第一版只新增 `purpose_result`、`context`、`frequency_text`、`responsibility_role`、`enablers` 與
`display_order`。不加入 O*NET 群體統計、`core/supporting`、importance、typicality 或 time share。

### Transaction 與 stale-input 保護

- 每個 mutation 先鎖 document row，再以固定順序處理 Task／Proposal；同一 transaction 寫 current state 與 Journal。
- AI 呼叫一定在 transaction 外；讀 snapshot 與套用結果使用兩段短 transaction。
- 寫入前重驗 authority generation 與 operation read-set；不符即丟棄舊結果並重新分析。
- 完成操作的 stable `entry_id` 提供 idempotency；不另建 generic workflow／operation ledger。
- reload 直接 hydrate Current State，不 replay Journal。
- 每個 concurrent asyncio task 使用自己的 SQLAlchemy `AsyncSession`。

### 程式邊界

- persistence ports 與 records 位於 `app/job_analysis/application`，不得依賴 SQLAlchemy。
- PostgreSQL models、repositories 與 UoW 位於 `app/adapters` 的新 greenfield adapter。
- `app/job_analysis` 持續不得 import `app.job_authoring`、`app.interview_vnext` 或舊 production AI 路徑。
- 第一份 persistence plan 只做到 PostgreSQL durable vertical，不接 Web、不做舊資料 migration。

## 後果

正面：

- 可以用 PostgreSQL 完成保存、重開、直接編輯與 AI/員工決策的原子性，而不繼承舊架構。
- 關聯 Task rows 支援局部編輯與排序；JSONB 只承載真正需要整體驗證、整體替換的 aggregate。
- 員工文件與 AI 分析保持兩層權威，LLM 執行期間的直接編輯不會被舊結果覆蓋。

成本：

- `JdEntry {task_id, content}` 必須先升級為完整 `JdTask`，Proposal before/after 與 Context projection 需同步調整。
- adapter 必須實作 JSONB hydrate validation、generation/read-set stale 檢查與固定 lock 順序。
- O/P/K/S/A 與公版 export 仍需後續逐一研究與實作。

風險：

- 單一 document-scoped Work Model JSONB 日後若出現高頻局部寫入，可能需要重新評估拆分；第一版沒有此需求。
- Journal 不是狀態重建來源，不能把「有 Journal」誤宣稱為完整 audit 或 Event Sourcing。
- 舊 tables 在刪除前會暫時共存；任何新 route 或 adapter 都不得讀寫它們。
