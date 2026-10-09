# Caliburn 開發指南

Caliburn 的正式產品是本機 Web AI 職務分析與職務說明書 App。現行權責由
[正式產品與選型](docs/architecture/design-decisions.md)決定；
開始修改前先讀[架構與現行責任](docs/architecture/README.md)與相關設計文件，不從歷史目錄猜現況。

## 正式結構

```text
apps/api/        Python 3.14／FastAPI／LangGraph／PostgreSQL 後端（A／B1／B2、JD、Memory、PDF）
apps/web/        React／TypeScript／MUI 介面
docs/            現行架構、契約、開發規範與 runbook
```

舊關聯式 App 與獨立 Memory 套件已退役，不能接回 import 或啟動。歷史決策與研究原件只在本機保存；RAG 仍保留，與 JD App 隔離且只能明示啟用。

## 工具與安裝

- Node.js `>=24.19.0 <25`、pnpm `12.5.1`
- Python `3.14`，由 uv `0.12.20` 管理
- PostgreSQL `18.6`

在 repository 根目錄執行：

```powershell
pnpm install --frozen-lockfile
uv sync --project apps/api --locked
```

Node／TypeScript 使用根目錄唯一的 `pnpm-lock.yaml`；不要新增 npm lockfile。Python 使用
`apps/api/uv.lock`。資料庫與 OpenAI key 只經明示的環境變數／`apps/api/.env` 的單一 key 設定，
不由安裝或啟動偷偷建立、清除或搬移；步驟見 [runbook 的首次初始化](docs/runbook.md#第一次初始化)。

## 日常開發

```powershell
pnpm app:status   # 診斷設定，不啟動、不改資料
pnpm dev          # 後端 :8100 與 Vite :5173 同時啟動
```

production 形式（單一後端程序同源提供建置後的 Web）：

```powershell
pnpm build
pnpm start
```

## 程式規範

層次與依賴方向、命名與寫法依[程式組織](docs/implementation/code-organization.md)與
[程式撰寫規範](docs/implementation/coding-standard.md)：依賴只向下，模組以業務責任組織，Service
是用例責任而非必須的 class 後綴，不為想像的未來泛化。層方向與前端 feature 互不 import 由
`apps/api/tests/unit/test_import_boundaries.py` 與 `apps/web/eslint.config.js` 鎖定，違反會直接失敗。
新功能依[開發規範](docs/implementation/development-standard.md)以行為反例先行（Red → Green → Refactor）。

## 驗證與提交

正式根閘門：

```powershell
pnpm check
```

它執行 lint（Ruff、ESLint、Prettier 格式）、型別（mypy strict、TypeScript）、不需資料庫的單元／契約／前端
測試，以及契約生成核對與 production build。真 PostgreSQL、真瀏覽器及真模型驗收仍依各計畫明示執行
（見[後端 README](apps/api/README.md#測試與檢查)）；離線綠燈不能冒充 provider 或 UI 證據。

使用 Conventional Commits，一個可審工作單位一個 commit，不加工具署名。保留他人未提交內容；研究、計畫、實驗原件與報告只留本機；公開提交保留程式、必要測試與架構／開發文件。未經 Owner 明確要求，不 push、merge、發布或執行付費模型驗證。

## 隔離 RAG

```powershell
pnpm rag:up
pnpm rag:dev
pnpm rag:down
```

RAG 不在正式 JD App dependency graph。變更前讀
[RAG 設計](docs/design/rag-pipeline.md)，不要把它接進 JD App composition root。
