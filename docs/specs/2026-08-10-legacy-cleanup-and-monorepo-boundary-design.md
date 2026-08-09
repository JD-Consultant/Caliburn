# Legacy Cleanup 與 Monorepo 邊界整理設計

- 日期：2026-08-10
- 狀態：Approved for implementation（owner 於 2026-08-10 指示研究後直接執行）
- 範圍：第一階段安全清理與架構規範整理

實作步驟見 [`../plans/2026-08-10-legacy-cleanup-and-monorepo-boundary-plan.md`](../plans/2026-08-10-legacy-cleanup-and-monorepo-boundary-plan.md)。

## 1. 目標與不變量

本階段要讓 repo 清楚回答三件事：現行第一版在哪裡、哪些路徑只是 legacy 相容、哪些路徑仍在建設中。清理只移除已證明沒有 runtime／測試／codegen／migration 消費者的淘汰物；不以「名稱看起來舊」作為刪除理由。

本階段不改產品流程、不切換 AI runtime、不刪仍被 route 使用的舊資料表、不搬資料、不雙寫、不新增 SaaS／登入／多租戶能力。每一個實際刪除仍需 characterization test 或既有測試作為安全網，並以一個 task 一個 commit 收尾。

## 2. 現況診斷

權威來源是根 `AGENTS.md`、`ARCHITECTURE.md`、`docs/README.md`、`docs/design/` 與 ADR；目前程式樹的證據如下：

| 分區 | 現況 | 本階段處理 |
|---|---|---|
| `apps/api/app/job_analysis/` | ADR 0040／0042 的現行 greenfield；已接 PostgreSQL、`/api/v1/job-analysis`、本機 Web workspace 與公版 XLSX | 標為現行產品核心，補明確依賴規則 |
| `apps/web/src/components/workspace/` | 現行文件工作台，消費 `job-analysis-contract` | 標為現行 UI；不與 legacy OCS editor 混用 |
| `packages/job-analysis-contract/` | 現行 job-analysis seam，schema 生成 Python／TypeScript | 標為單一契約來源 |
| `apps/api/app/interview/`、`apps/web/src/components/interview/` | 文件與 `/job-profiles/.../interview:*` route 仍直接使用；雖標為淘汰暫留，仍是可執行 legacy seam | 不刪；加 legacy 禁令與 consumer 清單 |
| `apps/api/app/interview_vnext/` | greenfield 隔離實作；尚無 production route／live LLM，且有自己的測試與 schema | 不刪、不接回舊 runtime；保留為建設中 bounded module |
| `apps/api/app/job_authoring/` | 被 `interview_vnext` 的 contract／persistence 讀取；另有 `job_authoring_*` 表與測試 | 不刪；標為 vNext supporting module |
| 已明確退役的 endpoint／UI 名稱 | 例如 `task-candidates`、`task-catalogs`、`document:buildTasks`、CopilotKit／SuggestionReview 等，部分已由程式移除、部分只剩歷史註記 | 逐項查 zero consumer；只刪確實仍留在 source 的 dead asset，歷史文檔移至 archive 或修正索引 |

## 3. 邊界設計

### 3.1 Monorepo 層

- `apps/*` 是可執行 bounded context；各 Python app 保持自己的 `pyproject.toml`／`uv.lock`，Web 使用 workspace package。
- `packages/*` 只放跨 app 的 typed contract 或生成物，不放 application service、資料庫模型或 UI 邏輯。
- `docs/` 放跨 app 的設計、ADR、研究與計畫；單一 app 的操作與內部不變量放該 app 的 `README.md`／`AGENTS.md`。
- API、indexer、embedder 之間只走已登記的 HTTP／contract seam；API 不直接碰 Qdrant，app 不把 torch 拉回 process。

### 3.2 API bounded context 層

- `app/job_analysis` 只能依賴自己的 `core`／`domain`／`application`／`providers`、PostgreSQL adapter 與 `packages/job-analysis-contract`；AST guard 繼續禁止 import `app.interview`、`app.interview_vnext`、`app.job_authoring`、`evals`。
- `app/interview` 是 legacy bounded path，只由 legacy route／adapter／legacy Web seam 消費；不得被新 `job_analysis` code 包裝或重新抽象成共用 framework。
- `app/interview_vnext` 是隔離中的 future path；不得 import／wrap v3 `consultant`、`scribe`、`harvest`、`select`，也不得由 production route 偷接。
- `app/job_authoring` 只作 vNext supporting module；在 vNext route、資料切換與 rollback 條件未完成前，不得宣告可刪。

### 3.3 Web 層

- `/workspace` 與 `components/workspace` 是現行 job-analysis UI；API client 只吃 `job-analysis-contract` 與 job-analysis route。
- `/documents`、`components/interview`、`lib/api.ts` 與 OCS editor 保持 legacy seam；不把它們誤標為第一版 workspace 的共用元件。
- Legacy UI 若要退役，必須先移除 route 入口、client call、hook、測試與文件指路，並以瀏覽器／HTTP smoke 證明沒有現行入口；不能只刪 component 檔案。

## 4. 清理策略與順序

採分層、可回復的順序：

1. **建立 inventory**：以 `git ls-files`、`rg`、AST dependency test、route mount、package exports、migration／codegen 搜尋逐項列出候選；每個候選記錄 producer、consumer、測試、資料表與刪除理由。
2. **先整理規範**：更新 `ARCHITECTURE.md`、`docs/README.md`、相關 app README／AGENTS，補現行／legacy／vNext 三色分區與禁止依賴；新增或擴充 architecture boundary test。
3. **只移除 zero-consumer dead assets**：包含已退役且仍殘留的空 client、未引用 type、已無 route 的 UI／測試輔助；刪除前先建立或確認 characterization coverage。
4. **修正歷史文檔指路**：保留可追溯的 ADR／研究原文；過時施工指示移到 `docs/archive/` 或明確標為 historical，不能讓現行索引把它指成施工依據。
5. **分開規劃 hard cut**：`app/interview`、legacy OCS editor、`job_authoring`／vNext table 不在本階段刪除；待新版 production route、資料切換、rollback、browser smoke 與 owner sign-off 另開 ADR／plan。

## 5. 驗收

- `ARCHITECTURE.md` 與 `docs/README.md` 能指出現行、legacy、vNext 三類邊界，且不再把 legacy route 描述成現行第一版 workspace。
- 新增／擴充 AST boundary tests：`job_analysis` 不得引用 legacy／vNext／evals；vNext 不得包裝舊 consultant／scribe／harvest／select。
- 每個被刪候選在 source、test、package export、route、migration、codegen 搜尋中都有可引用的 zero-consumer 證據。
- `packages/job-analysis-contract`、API job-analysis focused suite、Web tests／TypeScript／lint 通過；若改到 legacy OCS seam，另跑相應 legacy tests。
- 不產生 migration，不改現有資料，不改 production route 行為；worktree clean 後每個 task 各自 commit，最後才由 owner 決定是否 push／合併。

## 6. 未納入本階段

- 不把 monorepo 拆成 polyrepo，也不新增 generic framework。
- 不把現行 `job_analysis` 搬去 `interview_vnext`，不把兩套資料合併。
- 不直接刪 `apps/api/app/interview/`、`apps/web/src/components/interview/`、`apps/api/app/interview_vnext/` 或 `apps/api/app/job_authoring/`。
- 不為了「看起來乾淨」刪除仍被 production route、legacy document persistence、vNext persistence 或 eval fixture 消費的檔案。

## 7. 本地依據

- [`AGENTS.md`](../../AGENTS.md)：產品範圍、bounded context、禁止 import 與工作紀律。
- [`ARCHITECTURE.md`](../../ARCHITECTURE.md)：目前 monorepo 高層地圖與 legacy／現行 AI 分界。
- [`docs/README.md`](../README.md)：文檔 taxonomy、擺放與 living docs 規則。
- [`docs/design/task-analysis-engine.md`](../design/task-analysis-engine.md)：現行 job-analysis durable vertical。
- [`docs/design/interview-engine.md`](../design/interview-engine.md)：legacy interview engine 的退役禁令。
- [`docs/plans/2026-07-16-interview-ai-vnext-implementation-plan.md`](../plans/2026-07-16-interview-ai-vnext-implementation-plan.md)：vNext 的隔離、切換與 v3 刪除順序。
