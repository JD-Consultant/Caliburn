# Caliburn

**透過訪談理解工作，逐步寫成有依據的職務說明書。**

Caliburn 是給員工使用的本機 Web AI 職務分析與職務說明書（JD）應用程式。目標是讓不熟悉 JD 寫作的員工，只需說明工作、回答釐清問題，也能由 AI 逐步產出精簡、完整、符合實際工作的 JD；人仍可編輯同一份工作稿。

- **第一次認識產品：**[產品專題介紹](docs/product-introduction.md)——問題、使用流程、核心設計與待驗證的價值。
- **準備理解或開發：**[目標架構地圖](docs/target-architecture-map.md)——由全貌逐層深入責任、生命週期、工具與保存。
- **找檔案或接手工作：**[Repo／文件分類](docs/README.md)、[收尾任務](docs/plans/2026-09-29-target-rebuild/tasks.md#收尾分類與下一步)、[驗收與實驗資料](docs/plans/2026-09-29-target-rebuild/evidence/README.md)。
- **教授與技術評閱者：**[系統架構報告](docs/reports/system-architecture/README.md)——含流程圖、內部分工與設計取捨；有固定基準，不代替最新開發契約。

## 正式產品

唯一正式 App 是 `apps/api`（後端）與 `apps/web`（介面）；正式權責與切換見 [ADR 0079](docs/adr/0079-target-rebuild-production-cutover.md)。

- FastAPI 單程序後端、PostgreSQL 18.6 關聯式 JD／訪談／Memory，LangGraph 官方 PostgreSQL saver 保存原生模型接續；
- OpenAI 直連 Responses API，模型固定 `gpt-6-luna`／high，`store=false`，完整原生 items 與 compaction；
- A 主顧問訪談並逐步改稿、B1／B2 背景整理工作情境與理解（Memory），員工只需回答；
- React／MUI 同頁訪談與 JD 編輯，查看本輪 JD 變更與來源原話、撤回本輪 JD，人工與 AI 編輯同一份稿；
- 正式 JD 的中文 PDF 匯出；後端同源提供建置後的 Web，單一程序即可使用。

舊的 `experiments/jd-relational-app` 與 `packages/consultant-memory` 程式已退役，只保留研究與沿革文件；精確退役清單與取回方式見 [ADR 0079](docs/adr/0079-target-rebuild-production-cutover.md#退役範圍與取回)。不提供舊資料搬移或相容層。

## 已知限制（請先讀）

品質與容量驗證的**實際結果與未過項目**記在 [T14 品質證據](docs/plans/2026-09-29-target-rebuild/evidence/t14-job-analysis-quality.md)、[T16 容量證據](docs/plans/2026-09-29-target-rebuild/evidence/t16-compaction-continuity.md)與 [T17 旅程證據](docs/plans/2026-09-29-target-rebuild/evidence/t17-course-administrator-journey.md)。最重要的是：JD 項目的來源引用在跨輪綜合內容時偶爾漏引；每次來源都可回查，但不保證涵蓋完整，使用者應在來源檢視中核對。PDF 畫面正確，部分字型的文字複製／搜尋會出現部首字元。速度與穩定受 OpenAI 帳戶的每分鐘 token 上限（TPM）影響：被限流時系統會自動多等、不算失敗；在 200K TPM 的帳戶上，12 輪訪談約 6–25 分鐘、長訪談要數小時。完整的已知不足與成因見 [T14 證據](docs/plans/2026-09-29-target-rebuild/evidence/t14-job-analysis-quality.md#已知不足成因與後續研究方向2026-10-01)。

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
- 施工計畫、任務與驗證證據：[`docs/plans/2026-09-29-target-rebuild/`](docs/plans/2026-09-29-target-rebuild/README.md)
- 舊 worktree 與文件沿革：[`docs/archive/worktree-history-index.md`](docs/archive/worktree-history-index.md)

`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder` 與 `packages/ocs-contract` 是保留但隔離的 RAG bounded context，不是 JD App runtime 依賴。只有明確執行 `pnpm rag:up`／`pnpm rag:dev` 才會啟動；細節見 [`docs/design/rag-pipeline.md`](docs/design/rag-pipeline.md)。
