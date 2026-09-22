# Caliburn

Caliburn 是給員工使用的本機 Web AI 職務分析與職務說明書（JD）應用程式。員工與 LLM 在同一份 JD 上工作，共用相同的關聯式資料與業務規則；訪談、工作案例、穩定工作理解與 JD 之間可按需回查來源。

## 正式產品

唯一正式 App 位於 [`experiments/jd-relational-app`](experiments/jd-relational-app/README.md)：

- FastAPI／PostgreSQL 18.6 關聯式 JD 後端；
- Next.js／React／TypeScript 同頁訪談與六章 JD 編輯畫面；
- A 主顧問、B1 案例整理、B2 工作理解、C 即時修補與分層 Memory；
- OpenRouter 的 OpenAI-only Luna 路徑與 App-side continuation compaction；
- 查看本輪 JD 改動、來源原話，以及只撤回本輪 JD。

目錄名稱 `experiments` 是專案迭代沿革，不表示這套程式是範例。正式權責與硬切換見 [ADR 0077](docs/adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)。舊 `apps/api`、`apps/web` 與 `packages/job-analysis-contract` 的可執行程式已移除，只留下醒目標記的歷史文件；不提供舊資料搬移或相容層。

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
