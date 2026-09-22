# Runbook — Caliburn JD App 本機操作

正式 App 位於 [`experiments/jd-relational-app`](../experiments/jd-relational-app/README.md)，但日常操作統一從 repository 根目錄進入。舊 `apps/api`、`apps/web`、npm／Turbo 與 PostgreSQL 16 Compose 已退役；正式邊界見 [ADR 0077](adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)。

## 服務與版本

| 項目 | 正式要求 |
|---|---|
| Node.js | `>=24.19.0 <25` |
| package manager | pnpm `12.5.1`，根目錄單一 lockfile |
| Python | `>=3.12 <3.13`，由 uv 管理 |
| PostgreSQL | 本機 **18.6**；由首次初始化記錄 host／port／database／user |
| API | `127.0.0.1`；port 由首次初始化保存 |
| Web | `http://127.0.0.1:3002/` |
| OpenRouter | 外部 LLM gateway；key 只存 Windows 認證管理員 |
| RAG | 隔離且非預設依賴 |

API 固定單程序、loopback、無 reload、無 proxy headers。不要按端口終止身分不明的程序；程式變更後在原前景終端正常停止再重啟。

## 安裝依賴

在 repository 根目錄執行：

```powershell
pnpm install --frozen-lockfile
uv sync --project experiments/jd-relational-app --frozen
```

Node／TypeScript 只使用 `pnpm-lock.yaml`；Python 只使用 `experiments/jd-relational-app/uv.lock`。不要產生 npm lockfile，也不要用根目錄 Compose 建立 JD App 的資料庫。

## 第一次初始化

先建立空的 PostgreSQL 18.6 資料庫，再執行：

```powershell
pnpm app:status
pnpm app:init
pnpm app:set-key
```

`app:init` 會互動詢問 PostgreSQL 連線、API port 及允許的 Web origin；管理畫面 origin 應為 `http://127.0.0.1:3002`。資料庫密碼不顯示，也不從命令參數或環境變數傳入。

初始化會執行固定 JD migration 與官方 LangGraph Saver／Store setup。普通啟動只核對既有結構，不自動 migration、清資料或重建 volume。初始化中斷時使用：

```powershell
pnpm app:resume-init
```

不要對已有內容、未知物件或版本不符的資料庫再次執行 `app:init`。本版不搬移舊資料，也不讀取舊 schema。

## AI credential

```powershell
pnpm app:set-key
pnpm app:status
pnpm app:remove-key
```

OpenRouter key 只存同一 Windows 使用者的 Windows 認證管理員，不放 `.env`、DPAPI App 設定、資料庫、prompt、checkpoint、前端、log 或 Git。`app:status` 只證明 credential 已設定；確認有效性需要真 provider 請求。沒有 key 時人工 JD 仍可使用，AI 明示未啟用，且不會自動 fallback。

## 日常啟動與停止

先啟動已初始化的 PostgreSQL，再於 repository 根目錄執行：

```powershell
pnpm dev
```

正式 production build／serve：

```powershell
pnpm build
pnpm start
```

開啟 <http://127.0.0.1:3002/>。根啟動器透過 App 的 `api-origin` 讀取已核准的 loopback API 位址；不讀出秘密、不猜 port，也不保存第二份設定。API 與 Web 共用前景程序群組；在原終端按 Ctrl+C 後，App 會先排空已登記工作再關閉資源。

需要診斷時，才直接在 `experiments/jd-relational-app` 使用 `uv run --frozen python -m jd_relational ...`；這不是另一條日常產品入口。

## 資料庫與備份

`public` schema 保存關聯式 JD 與背景准入；`jd_runtime` 保存 LangGraph checkpoint／store／Memory publication。兩者屬同一 App、同一資料範圍，但責任分層。一份完整備份包含：

1. 整個資料庫的 `pg_dump`，不要用 `-n` 只挑單一 schema；
2. App 的 `host.v1.dpapi` 設定檔。

OpenRouter key 不在備份內；換電腦或還原後須重新執行 `pnpm app:set-key`。瀏覽器 IndexedDB 不是正式資料庫備份。精確證據與限制見 [`specs/2026-09-14-jd-backup-and-restore-slice.md`](specs/2026-09-14-jd-backup-and-restore-slice.md)。

## 驗證

```powershell
pnpm check
```

也可使用窄命令：

```powershell
pnpm test
pnpm typecheck
pnpm build
```

真 PostgreSQL、真瀏覽器與真模型結果分開記錄；離線測試不能代替 provider 或 UI 證據。Windows 受限 token 可能讓真 ACL 模組因暫存目錄權限出現 `WinError 5`，不得為測試變綠而放寬正式 App 的 ACL 或忽略錯誤。

## RAG（隔離、非 JD App 依賴）

`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder` 與 `packages/ocs-contract` 不在 JD App dependency graph。只有明確執行下列命令才啟動：

```powershell
pnpm rag:up
pnpm rag:dev
pnpm rag:down
```

不要把 RAG 接進 JD App composition root。詳見 [`design/rag-pipeline.md`](design/rag-pipeline.md)。
