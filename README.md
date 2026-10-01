# Caliburn

**透過訪談理解工作，逐步寫成有依據的職務說明書。**

Caliburn 是給員工使用的本機 Web AI 職務分析與職務說明書（JD）應用程式。目標是讓不熟悉 JD 寫作的員工，只需說明工作、回答釐清問題，也能由 AI 逐步產出精簡、完整、符合實際工作的 JD；人仍可編輯同一份工作稿。

- **第一次認識產品：**[產品專題介紹](docs/product-introduction.md)——問題、使用流程、核心設計與待驗證的價值。
- **準備理解或開發新架構：**[目標架構地圖](docs/target-architecture-map.md)——由全貌逐層深入責任、生命週期、工具與保存。
- **找檔案或接手工作：**[Repo／文件分類](docs/README.md)、[收尾任務](docs/plans/2026-09-29-target-rebuild/tasks.md#收尾分類與下一步)、[驗收與實驗資料](docs/plans/2026-09-29-target-rebuild/evidence/README.md)。
- **教授與技術評閱者：**[系統架構報告](docs/reports/system-architecture/README.md)——含流程圖、內部分工與設計取捨；有固定基準，不代替最新開發契約。

介紹與目標文件描述重構方向，**不代表已全部實作**。下面是現行正式程式及使用方式；兩者不混為同一個完成狀態。

## 正式產品

唯一正式 App 位於 [`experiments/jd-relational-app`](experiments/jd-relational-app/README.md)：

- FastAPI／PostgreSQL 18.6 關聯式 JD 後端；
- Next.js／React／TypeScript 同頁訪談與六章 JD 編輯畫面；
- A 主顧問、B1 案例整理、B2 工作理解、C 即時修補與分層 Memory；
- OpenRouter 的 OpenAI-only Luna 路徑與 App-side continuation compaction；
- 查看本輪 JD 改動、來源原話，以及只撤回本輪 JD。

目錄名稱 `experiments` 是專案迭代沿革，不表示這套程式是範例。正式權責與硬切換見 [ADR 0077](docs/adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)。原 `apps/api`、`apps/web` 與 `packages/job-analysis-contract` 的舊接線已退役；現在的 [`apps/api`](apps/api/README.md)／[`apps/web`](apps/web/README.md) 是另行重建的新目標程式，並非只剩歷史 README，也不整合舊資料。其進度依[任務表](docs/plans/2026-09-29-target-rebuild/tasks.md)，正式入口待 T18 通過才切換。以下環境與命令仍屬現行正式產品。

## 執行環境

- Node.js `>=24.19.0 <25`
- pnpm `12.5.1`
- Python `>=3.12 <3.13` 與 uv
- 本機 PostgreSQL `18.6`

Node／TypeScript workspace 使用根目錄 `pnpm-lock.yaml`；Python 使用 App 自己的 `uv.lock`。根目錄 Compose 只保留明示啟用的隔離 RAG 服務，不會建立 JD App 資料庫。

## 第一次設定

先準備空的 PostgreSQL 18.6 資料庫，再於根目錄執行：

```powershell
pnpm install --frozen-lockfile
uv sync --project experiments/jd-relational-app --frozen
pnpm app:status
pnpm app:init
pnpm app:set-key
```

`app:init` 只用於空資料庫，會互動詢問連線資料、API port 與 Web origin。OpenRouter key 只存 Windows 認證管理員，不進 `.env`、資料庫或 Git。初始化中斷時使用 `pnpm app:resume-init`，不要重新初始化已有內容的資料庫。

## 日常啟動

先啟動已設定的 PostgreSQL，再於根目錄執行：

```powershell
pnpm dev
```

開啟 <http://127.0.0.1:3002/>。啟動器會從受保護的 App 設定取得正確 API origin，同時以前景程序啟動 API 與 Web；按 Ctrl+C 正常停止與排空。Production build 使用：

```powershell
pnpm build
pnpm start
```

完整初始化、credential、備份與故障排除見 [`docs/runbook.md`](docs/runbook.md)。

## 驗證

```powershell
pnpm check
```

這會執行正式 Python 測試、Web 測試、TypeScript typecheck、契約生成核對與 production build。真 PostgreSQL、真瀏覽器及真模型的證據仍分開記錄，見 [`docs/current-decisions.md`](docs/current-decisions.md) 與 [`docs/specs/evidence`](docs/specs/evidence)。

## 文件與 RAG

- 文件地圖與迭代順序：[`docs/README.md`](docs/README.md)
- 目前有效決策：[`docs/current-decisions.md`](docs/current-decisions.md)
- 正式架構決策：[`docs/adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md`](docs/adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)
- 最新完整 App 證據：[`docs/specs/evidence/2026-09-22-jd-component-first-acceptance.md`](docs/specs/evidence/2026-09-22-jd-component-first-acceptance.md)
- 舊 worktree 與文件沿革：[`docs/archive/worktree-history-index.md`](docs/archive/worktree-history-index.md)

`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder` 與 `packages/ocs-contract` 是保留但隔離的 RAG bounded context，不是 JD App runtime 依賴。只有明確執行 `pnpm rag:up`／`pnpm rag:dev` 才會啟動；細節見 [`docs/design/rag-pipeline.md`](docs/design/rag-pipeline.md)。
