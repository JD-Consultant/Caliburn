# Caliburn

**透過訪談理解工作，逐步寫成有依據的職務說明書。**

Caliburn 是給員工使用的本機 Web AI 職務分析與職務說明書（JD）應用程式。目標是讓不熟悉 JD 寫作的員工，只需說明工作、回答釐清問題，也能由 AI 逐步產出精簡、完整、符合實際工作的 JD；人仍可編輯同一份工作稿。

## 閱讀入口

| 想了解什麼 | 文件 |
|---|---|
| 產品解決的問題與使用流程 | [產品介紹](docs/product-introduction.md) |
| 專題的動機、方法、實驗與成果 | [專題報告](docs/reports/project-report/report.md) |
| 程式內部如何分工、管理資料與延續分析 | [系統架構報告](docs/reports/system-architecture/README.md)，含流程圖與設計取捨 |
| 維護程式、查找契約與操作方法 | [開發文件導覽](docs/README.md)、[現行架構](docs/target-architecture-map.md) |
| 查閱研究與開發過程 | [研究與實驗材料](docs/reports/README.md)、[歷史查閱](docs/history.md) |

## 正式產品

唯一正式 App 是 `apps/api`（後端）與 `apps/web`（介面）；正式權責與切換見 [ADR 0079](docs/adr/0079-target-rebuild-production-cutover.md)。

- FastAPI 單程序後端、PostgreSQL 18.6 關聯式 JD／訪談／Memory，LangGraph 官方 PostgreSQL saver 保存原生模型接續；
- OpenAI 直連 Responses API，模型固定 `gpt-6-luna`／high，`store=false`，完整原生 items 與 compaction；
- A 主顧問訪談並逐步改稿、B1／B2 背景整理工作情境與理解（Memory），員工只需回答；
- React／MUI 同頁訪談與 JD 編輯，查看本輪 JD 變更與來源原話、撤回本輪 JD，人工與 AI 編輯同一份稿；
- 正式 JD 的中文 PDF 匯出；後端同源提供建置後的 Web，單一程序即可使用。

舊的 `experiments/jd-relational-app` 與 `packages/consultant-memory` 程式已退役，只保留研究與沿革文件；精確退役清單與取回方式見 [ADR 0079](docs/adr/0079-target-rebuild-production-cutover.md#退役範圍與取回)。不提供舊資料搬移或相容層。

## 驗證範圍

品質、容量與使用旅程的實際結果見[驗證範圍](docs/architecture/verification.md)、[實驗發現](docs/reports/experiment-findings.md)與[原始資料](docs/experiments/product-validation/README.md)。跨輪綜合的 JD 項目仍有來源漏引反例；來源可回查不等於依據完整。PDF 部分字型的文字複製／搜尋會出現部首字元。速度受 OpenAI 帳戶的每分鐘 token 上限（TPM）影響：限流時按政策等待；既有 200K TPM 帳戶的合成實驗中，12 輪訪談約 6–25 分鐘，長訪談需數小時，不當成所有環境的效能承諾。

## 執行環境

- Node.js `>=24.19.0 <25`、pnpm `12.5.1`
- Python `3.14`，由 uv `0.12.20` 管理
- 本機 PostgreSQL `18.6`（獨立程序，容器或本機安裝皆可）
- OpenAI API key（沒有 key 時人工 JD 編輯仍可用，AI 訪談停用）
- PDF 匯出：授權的中文字型與 Playwright Chromium（見 [後端 README](apps/api/README.md#pdf-執行依賴)）

Node／TypeScript workspace 使用根目錄 `pnpm-lock.yaml`；Python 使用 `apps/api/uv.lock`。根目錄 Compose 只保留明示啟用的隔離 RAG 服務，不會建立 JD App 資料庫。

## 第一次設定

先建立一個**空的**專用 PostgreSQL database，然後在根目錄執行（PowerShell）：

```powershell
pnpm install --frozen-lockfile
uv sync --project apps/api --locked

$env:CALIBURN_DATABASE_URL = 'postgresql://帳號:密碼@127.0.0.1:5432/caliburn'   # 密碼由本機秘密管理注入，勿提交
$env:CALIBURN_DATABASE_SCHEMA = 'caliburn'                                       # 預設即此值
pnpm app:migrate        # 建立／升級到最新 schema；啟動時只核對，不自動升級
pnpm app:status         # 只診斷，不啟動、不改資料；不印出密碼或 key
pnpm build              # 建置 Web，供後端同源提供
```

OpenAI key 二擇一：設定環境變數 `OPENAI_API_KEY`，或在 `apps/api/.env`（已被 Git 忽略）放**唯一一行** `OPENAI_API_KEY=...`；後端只讀這一項，不讀其他舊設定。

## 日常啟動

```powershell
pnpm start    # 單一後端程序，同源提供建置後的 Web；開啟 http://127.0.0.1:8100/
pnpm dev      # 開發：後端與 Vite 同時啟動；開啟 http://127.0.0.1:5173/
```

按 Ctrl+C 正常停止；暫停、取消與重開後的接續依 [共用執行說明](docs/implementation/agent-execution.md)。完整啟停、備份與故障排除見 [`docs/runbook.md`](docs/runbook.md)。

## 驗證

```powershell
pnpm check    # lint、型別、單元／契約測試（不需資料庫）、前端測試與 production build
```

真 PostgreSQL 整合測試、真瀏覽器與真模型結果分開記錄；PostgreSQL 測試需明確指定隔離的 `_test` 資料庫，見 [後端 README](apps/api/README.md#測試與檢查)。

## 文件與 RAG

- 文件地圖與迭代順序：[`docs/README.md`](docs/README.md)
- 目前有效決策：[`docs/current-decisions.md`](docs/current-decisions.md)
- 正式架構決策：[ADR 0079](docs/adr/0079-target-rebuild-production-cutover.md)（歷史：[ADR 0077](docs/adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)）
- 實驗原件與核對命令：[產品驗證資料](docs/experiments/product-validation/README.md)
- 舊設計與已結案工作：[歷史查閱方式](docs/history.md)；本機封存不隨 Git 發布

`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder` 與 `packages/ocs-contract` 是保留但隔離的 RAG bounded context，不是 JD App runtime 依賴。只有明確執行 `pnpm rag:up`／`pnpm rag:dev` 才會啟動；細節見 [`docs/design/rag-pipeline.md`](docs/design/rag-pipeline.md)。
