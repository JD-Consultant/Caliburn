# Runbook — Caliburn JD App 本機操作

正式 App 是 `apps/api` 與 `apps/web`，日常操作統一從 repository 根目錄進入；正式邊界見
[ADR 0079](adr/0079-target-rebuild-production-cutover.md)。舊 `experiments/jd-relational-app`
（含舊 `app:init`／`app:set-key`、OpenRouter、Windows 認證管理員）已退役，不再有對應命令。

## 服務與版本

| 項目 | 要求 |
|---|---|
| Node.js | `>=24.19.0 <25` |
| package manager | pnpm `12.5.1`，根目錄單一 lockfile |
| Python | `3.14`，由 uv `0.12.20` 管理（`apps/api/uv.lock`） |
| PostgreSQL | 本機 **18.6**，獨立程序；容器或本機安裝皆可 |
| API | `127.0.0.1:8100`，單程序、無 reload、無 proxy headers |
| Web | 正式：由 API 同源提供 `http://127.0.0.1:8100/`；開發：Vite `http://127.0.0.1:5173/` |
| 模型 | OpenAI Responses 直連，`gpt-6-luna`／high；key 只在後端使用 |
| PDF | 授權的中文字型＋Playwright Chromium（選用；缺少時匯出回 503） |
| RAG | 隔離且非預設依賴 |

不要按端口終止身分不明的程序；程式變更後在原前景終端正常停止再重啟。

## 安裝依賴

```powershell
pnpm install --frozen-lockfile
uv sync --project apps/api --locked
```

Node／TypeScript 只使用 `pnpm-lock.yaml`；Python 只使用 `apps/api/uv.lock`。不要產生 npm lockfile，也不要用根目錄 Compose 建立 JD App 的資料庫。

## 第一次初始化

1. 建立一個**空的**專用 PostgreSQL database（不要沿用舊產品的資料庫；本版不搬移舊資料）。
2. 以環境變數明示連線，密碼由本機秘密管理注入，不貼在命令列歷史、文件或 Git：

```powershell
$env:CALIBURN_DATABASE_URL = 'postgresql://帳號:密碼@127.0.0.1:5432/caliburn'
$env:CALIBURN_DATABASE_SCHEMA = 'caliburn'      # 預設值；可省略
pnpm app:migrate                                 # 建立 namespace 並升級到最新 schema，可重跑
pnpm app:status                                  # 診斷；不印出密碼或 key
pnpm build                                       # 建置 Web，供 `pnpm start` 同源提供
```

`app:migrate` 是**唯一**會改 schema 的命令。啟動只核對 migration head：未初始化或版本不符會啟動失敗，並提示執行 `pnpm app:migrate`；它不自動升級、清資料或重建 volume。LangGraph 的 checkpoint 表由官方 saver 在啟動時安全建立。

## AI credential

二擇一，後端只讀 `OPENAI_API_KEY` 這一項：

- 環境變數 `OPENAI_API_KEY`；
- 或 `apps/api/.env`（已被 Git 忽略）內**唯一一行** `OPENAI_API_KEY=...`，`pnpm start`／`pnpm dev` 會自動以 `--key-file` 載入。

key 不進 prompt、模型工具、Web bundle、URL、資料庫、checkpoint、一般 log 或 Git。`pnpm app:status` 只顯示「已設定」，不證明 key 有效；確認有效性需要真 provider 請求。沒有 key 時人工 JD 仍可使用，AI 訪談明示停用，且不會自動 fallback。更換 key 後須重啟後端。

注意：後端啟動時會續跑已接受但未完成的訪談與背景整理，這可能消耗模型額度；只想操作人工 JD 時不要提供 key。

## 日常啟動與停止

先啟動已初始化的 PostgreSQL，再於根目錄執行：

```powershell
pnpm start    # 單一後端程序同源提供建置後的 Web：http://127.0.0.1:8100/
pnpm dev      # 開發：後端 :8100 與 Vite :5173 同時前景啟動：http://127.0.0.1:5173/
```

`pnpm start` 需要先 `pnpm build`；沒有建置會明確報錯，不自動建置或猜目錄。在原終端按 Ctrl+C 正常停止：後端先停止新准入、保存已取得的結果並停在可恢復邊界，再釋放資源；強制關閉仍依最後可靠位置恢復。重開後，進行中或暫停的訪談可由介面找回並續作；背景整理由系統依持久狀態自動承接。

隔離驗證時若前端使用第二個埠，可在**後端啟動前**設定 `CALIBURN_DEV_ORIGIN=http://127.0.0.1:5174`（只接受一個帶明確埠的 loopback HTTP origin），見[後端 README](../apps/api/README.md)。

## PDF 匯出

匯出正式 JD 的中文 PDF 需要兩項，缺少時 `GET /api/job-files/{id}/jd/export.pdf` 回 503，不下載空檔：

```powershell
$env:CALIBURN_PDF_FONT_PATH = 'D:\fonts\NotoSansTC-VF.ttf'              # 已授權的中文字型
uv run --project apps/api --locked python -m playwright install chromium --only-shell   # 鎖定版本的瀏覽器
# 或指定與已鎖 Playwright 相容的 Chromium：$env:CALIBURN_PDF_CHROMIUM_PATH = '...\chrome.exe'
```

PDF 只匯出正式 JD、不含候選與員工姓名；畫面中文正確，部分字型的文字複製／搜尋會出現部首字元（已知限制，見 [T13](plans/2026-09-29-target-rebuild/evidence/t13-pdf-export.md)）。

## 診斷

| 現象 | 查什麼 |
|---|---|
| 想知道這次啟動會用什麼 | `pnpm app:status`：資料庫（可連線、migration 是否在 head）、模型是否設定、PDF 字型／瀏覽器、Web 建置 |
| 後端啟動失敗並提到 migration | 資料庫尚未初始化或版本不符：`pnpm app:migrate` |
| `POST /inputs` 回 503 `model_not_configured` | 沒有 OpenAI key（或後端啟動前未設定）；人工 JD 不受影響 |
| 瀏覽器或 CLI 收到 403 | 精確 Host／Origin 檢查：只接受 `127.0.0.1`／`localhost`／`[::1]` 的 5173／8100（及明示的一個 dev origin） |
| `GET /api/health` | 只表示程序存活，不表示資料庫或模型可用 |
| 訪談失敗或結果不明 | 介面顯示安全的失敗原因，原輸入保留；技術診斷在後端 log（只含穩定 ID、階段、錯誤類別，不含原話或 payload） |
| 一輪訪談很久沒有回應 | 多半是 OpenAI 帳戶的每分鐘 token 上限（TPM）在限流，後端 log 會出現 `Provider request failed: … failure=rate_limited`。系統會照服務建議的時間自動多等（沒有建議時 10 秒起、60 秒封頂），**不算失敗**，單輪最長等到工作期限（預設 30 分鐘）；可隨時取消該輪。TPM 200K 的帳戶上，一場 12 輪訪談約 6–25 分鐘；要更快請改用更高 TPM 的帳戶 |
| 訪談或背景整理全部立刻失敗，後端 log 為 `failure=access_blocked … provider_code=credit_balance_exhausted` | OpenAI 帳戶儲值額度用完（HTTP 429，但不是限流）。系統不重試、原輸入保留、該次處理標為失敗；補額度後重新送出原輸入 |
| 資料庫剛重啟（或被外力中止）後，讀訪談狀態的端點回 500，`/api/health` 仍是 ok | **重啟後端**。leader 鎖與 checkpoint 連線各只持一條資料庫連線、不會自動重連，這是刻意的單一 leader 設計；重啟時系統會恢復已保存的進行中工作（能續作則續作，否則安全終止、原輸入保留，之後可重送） |

## 資料庫與備份

**首版成品驗收不以備份／空庫還原為前置。**目前優先驗證既有 PostgreSQL／checkpoint 在一般中斷與重開後能查回已確認保存的訪談、JD 與進度；未送出的輸入或未保存草稿不保證意外關閉後找回。備份資訊供後續維護參考，不表示已完成完整還原端到端驗收：

- 備份整個資料庫（`pg_dump` 不要用 `-n` 只挑單一 schema）；關聯式資料與 checkpoint 表在同一 namespace，兩者屬同一資料範圍。
- OpenAI key 不在備份內；在另一台電腦還原後須重新提供 key。瀏覽器 localStorage／sessionStorage 不是正式資料備份。
- 不自動清資料、刪 volume 或重建資料庫；資料處置需先核對精確目標。

## 驗證

```powershell
pnpm check
```

也可使用窄命令：`pnpm lint`、`pnpm typecheck`、`pnpm test`、`pnpm build`。`pnpm test` 不需資料庫；真 PostgreSQL 整合測試需明確指定隔離的 loopback `_test` 資料庫並直接執行 pytest：

```powershell
$env:CALIBURN_TEST_DATABASE_URL = 'postgresql://測試帳號:密碼@127.0.0.1:5432/caliburn_test'
uv run --project apps/api --locked pytest apps/api/tests -m postgres -q
```

測試各自建立並回收隨機 schema，不碰既有資料。真 PostgreSQL、真瀏覽器與真模型結果分開記錄；離線測試不能代替 provider 或 UI 證據。付費驗證腳本須依 manifest 明示的有限預算執行（見各任務證據）。Windows 受限 token 可能讓暫存目錄權限出現 `WinError 5`，不得為測試變綠而放寬安全限制。

## RAG（隔離、非 JD App 依賴）

`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder` 與 `packages/ocs-contract` 不在 JD App dependency graph。只有明確執行下列命令才啟動：

```powershell
pnpm rag:up
pnpm rag:dev
pnpm rag:down
```

不要把 RAG 接進 JD App composition root。詳見 [`design/rag-pipeline.md`](design/rag-pipeline.md)。
