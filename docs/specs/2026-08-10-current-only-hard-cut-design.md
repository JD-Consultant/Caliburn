# Current-only hard cut 設計研究

日期：2026-08-10  
狀態：owner 已決定只保留新 `job_analysis` 系統；本稿供 ADR 0057 與施工計畫使用。

## 1. 裁決與前提

本 repo 不再維持 legacy／vNext 並存。第一版只保留本機 Web 的 `app/job_analysis`：員工可保存多份彼此隔離的職務說明書，經 `/api/v1/job-analysis` 與 `/workspace` 完成直接編輯、顧問回合、提案決策、Current JD 與 XLSX 匯出。

owner 已確認現有本機資料庫可以重建，舊資料不需要保留或遷移。因此本次是 source、runtime、schema history 的 hard cut，不做 dual write、資料搬遷或相容 API。

## 2. 研究證據

權威文件與實際 source 的交叉結果如下：

| 證據 | 結果 | 對裁決的意義 |
| --- | --- | --- |
| `AGENTS.md`、`docs/product-notes.md`、`docs/adr/0043`–`0056` | `job_analysis` 是目前產品權威；Current JD 與 Work Model 不接舊 `job_authoring`／vNext | current boundary 已存在，不需從舊模型抽取資料 |
| `apps/api/app/api/router.py`、`app/api/routes/job_analysis.py`、`app/api/job_analysis_deps.py` | 新 API 只需要 `job_analysis` route、PostgreSQL adapter、OpenRouter adapter | 舊 route／adapter 可以從 composition root 移除 |
| `apps/web/src/app/workspace/**`、`components/workspace/**`、`lib/jobAnalysis*` | workspace 只吃 `job-analysis-contract` 與 current API；不引用 OCS contract、舊 hooks 或舊頁面 | 舊 Web editor 可整棵移除 |
| Alembic `0012_job_analysis_current_state.py` | 內容是 greenfield current tables，唯一依賴是 `0011` 的 migration chain，不讀舊表 | 可將 `0012.down_revision` 改為 `None`，保留 `0012–0017` 的 current 演進與測試形狀 |
| `apps/api/app/job_analysis` 與 current tests | 新引擎只依賴 Pydantic、SQLAlchemy、HTTPX、OpenPyXL、job-analysis contract | 舊 LangGraph／LangChain／vNext provider 與測試可刪，依賴可瘦身 |
| root workspace、Compose、各 app manifest | `ocs-indexer`、`pdf-to-json`、`embedder`、Qdrant、OCS/indexer contracts 都服務舊 OCS／知識檢索路徑，current workspace 無 consumer | monorepo deployable 收斂為 `apps/api`、`apps/web` 與 `packages/job-analysis-contract`；Compose 只留 Postgres |

## 3. 保留與移除閉包

### 保留

- `apps/api/app/job_analysis/**`、current API route／mapper／problem response、PostgreSQL adapter、設定／資料庫／健康檢查。
- `apps/web/src/app/workspace/**`、workspace components、current `jobAnalysis*` helpers、必要 UI primitives、`job-analysis-contract`。
- `apps/api/alembic/versions/0012–0017`，但把 `0012` 變成 current-only root；最終資料表只有 `job_analysis_*` 七表。
- PostgreSQL 與必要的 OpenRouter HTTP provider；不保留 Qdrant、embedder 或 PDF→OCS pipeline。
- 歷史 ADR/spec/design 文件作為追溯材料，不把已移除的架構重新列為現行入口。

### 移除

- API 舊 users／job profiles／documents／occupations／AI／interview routes 與其 adapters、models、schemas、services。
- `app/interview/**`、`app/interview_vnext/**`、`app/job_authoring/**` 及其 migration、provider、schema writer、tests。
- Web `/dashboard`、`/documents/**`、`components/interview/**`、舊 hooks、OCS client/types、使用者 store。
- `packages/ocs-contract`、`packages/indexer-contract`、`apps/ocs-indexer`、`apps/pdf-to-json`、`apps/embedder`。
- 舊 migration `0001–0011` 與只驗證舊 schema／引擎的 tests；保留 current migration contract test 並改驗「只存在 current tables」。

不刪歷史 ADR；Accepted ADR 不改寫。新增 ADR 0057 記錄本次翻轉，避免未來 agent 依舊 ADR 把已退役 runtime 救回。

## 4. 選項比較

| 選項 | 優點 | 缺點 | 裁決 |
| --- | --- | --- | --- |
| 保留所有舊 runtime，只標 legacy | 風險最低、既有測試少改 | 仍有雙產品邊界、舊表與大量依賴；與 owner「只留新系統」矛盾 | 不採用 |
| 只移除 route，保留引擎／migration／app | API 表面簡潔 | dead code、舊表與 uv/npm workspace 仍會被維護；不能稱 current-only | 不採用 |
| **current-only hard cut + 可重建 DB** | 邊界最清楚、依賴與啟動流程最小、舊資料不再成為相容負擔 | 既有本機舊資料與舊 API 全失效；需要一次重建 DB 與完整 suite | **採用** |

## 5. 安全網與回復

施工順序是先固定 current route／table／import 護欄，再移除 source 與 workspace members，最後重建 migration chain、更新 Compose／文件並跑完整 monorepo gates。每個 task 獨立 commit；不 push。

回復不是 runtime 雙軌：若驗證失敗，以 Git commit 邊界回復 source；若要回復舊本機資料，需使用 owner 自行保留的 Postgres volume／backup。施工前不會自動把舊 volume 當成可相容資料庫繼續使用；current-only 啟動要求新 DB 跑 `alembic upgrade head`。

