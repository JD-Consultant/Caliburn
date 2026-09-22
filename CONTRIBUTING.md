# Caliburn 開發指南

Caliburn 的正式產品是本機 Web AI 職務分析與職務說明書 App。現行權責由
[ADR0077](docs/adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)決定；
開始修改前先讀[目前決策](docs/current-decisions.md)與相關設計文件，不從歷史目錄猜現況。

## 正式結構

```text
experiments/jd-relational-app/      Python 3.12／FastAPI／LangGraph／PostgreSQL JD App
experiments/jd-relational-app/web/ Next.js／TypeScript 管理畫面
packages/consultant-memory/        A／B1／B2 共用的分層 Memory runtime
docs/                              ADR、研究、設計、計畫、證據與 runbook
```

`apps/api`、`apps/web` 與 `packages/job-analysis-contract` 只保留歷史 README，不能接回正式程式。
RAG bounded context 仍保留，但與 JD App 隔離且只能明示啟用。

## 工具與安裝

- Node.js `>=24.19.0 <25`
- pnpm `12.5.1`
- Python `>=3.12 <3.13` 與 uv
- PostgreSQL `18.6`

在 repository 根目錄執行：

```powershell
pnpm install --frozen-lockfile
uv sync --project experiments/jd-relational-app --frozen
```

Node／TypeScript 使用根目錄唯一的 `pnpm-lock.yaml`；不要新增 npm lockfile。Python 使用 App 自己的
`uv.lock`。正式資料庫由 `pnpm app:init` 明示初始化，不由安裝或一般啟動偷偷建立、清除或搬移。

## 日常開發

```powershell
pnpm app:status
pnpm dev
```

production build／serve：

```powershell
pnpm build
pnpm start
```

更完整的 credential、初始化、備份與停止方式見[runbook](docs/runbook.md)。OpenRouter key 只存
Windows 認證管理員，不放 `.env`、資料庫、命令列、log 或 Git。

## 驗證與提交

正式根閘門：

```powershell
pnpm check
```

它重用各 workspace 的既有 Python、Web、型別、codegen 與 production build 檢查。真 PostgreSQL、
真瀏覽器及真模型驗收仍依各計畫明示執行；離線綠燈不能冒充 provider 或 UI 證據。

使用 Conventional Commits，一個可審工作單位一個 commit。保留他人未提交內容；不要把研究、設計、
實驗或結果文件當成舊程式刪除。未經 Owner 明確要求，不 push、merge、發布或執行付費模型驗證。

## 隔離 RAG

```powershell
pnpm rag:up
pnpm rag:dev
pnpm rag:down
```

RAG 不在正式 JD App dependency graph。變更前讀
[RAG 設計](docs/design/rag-pipeline.md)，不要把它接進 JD App composition root。
