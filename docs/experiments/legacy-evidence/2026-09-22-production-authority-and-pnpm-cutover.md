# 正式權責、pnpm 根入口與舊架構退役證據

**日期：**2026-09-22

**決策：**[ADR0077](../../adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)

**範圍：**只切換 repository 正式 authority、依賴與操作入口；不改 A／B1／B2／C、Memory、compaction、JD 業務語意或 provider。

## 交付結果

- `experiments/jd-relational-app`、其 Web 與 `packages/consultant-memory` 是唯一正式 JD App。
- 根目錄採 Node.js `>=24.19.0 <25`、pnpm `12.5.1`、TypeScript、uv 與單一 active `pnpm-lock.yaml`。
- `apps/api`、`apps/web`、`packages/job-analysis-contract` 的可執行程式、生成物、舊 npm locks、Turbo 與 PostgreSQL 16 Compose 已退出。研究、設計、實驗、結果、歷史 README 與 Git 沿革保留。
- 不搬舊資料、不雙讀、不雙寫、不加舊 schema adapter；正式 App 使用其明示初始化的 PostgreSQL 18.6。
- `pnpm dev`／`pnpm start` 從既有受保護設定只讀一個公開 loopback API origin，再以前景方式啟動兩個既有 workspace scripts。沒有第二份設定或 process manager。

## 首敗與最小修正

1. 第一版 PowerShell 協調器在正式 package script 中發生 parser error，且包住 pnpm 後的程序生命週期不可靠。沒有改 API、Web、資料庫或產品語意；依 Node 24 官方穩定 `child_process.spawn` 改成薄 Node 協調器。
2. 第一版 Node 協調器把 pnpm 12 在 Windows 提供的 `npm_execpath=pnpm.exe` 當 JavaScript 交給 Node，得到 `ERR_UNKNOWN_FILE_EXTENSION .exe`。修正為 `.js／.cjs／.mjs` 才透過目前 Node 執行，其餘可執行檔直接 spawn；5 個 launcher contract tests 固定 mode、loopback origin、fail-closed filters 與 executable 分流。
3. 啟動測試遇到 3002 已占用時，先查 PID、命令列、父程序與建立時間；確認是同一新 App 後才停止精確程序。沒有按 port 終止未知程序。

這些修正只處理操作入口。pnpm 仍以官方多 `--filter` 選取兩個套件，`--parallel --stream` 執行長程序；Runtime 的關閉與排空仍由既有 App 負責。

## 實際驗證

| Gate | 結果 |
|---|---|
| `pnpm install --frozen-lockfile` | PASS；6 個 workspace projects，固定 package manager 與 lockfile 完整性檢查通過 |
| 根目錄 `pnpm check` | PASS／exit 0 |
| Launcher tests | 5 passed |
| 新 App Python | 3,115 passed／322 skipped；既有 Pydantic／Starlette warnings 保留 |
| Web | 310 passed |
| TypeScript／codegen | PASS |
| Next.js 16.3.5 production build | PASS |
| `pnpm app:status` | PASS；設定 ready，OpenRouter credential 已設定但未顯示秘密 |
| `pnpm start` Web | `GET http://127.0.0.1:3002/` → HTTP 200 |
| `pnpm start` API | `GET http://127.0.0.1:8772/openapi.json` → HTTP 200，title `Caliburn JD workspace`，17 paths |
| 正常停止 | Ctrl+C 後 3002／8772 均無 listener |

本切換沒有 provider request、沒有付費、沒有修改或搬移舊資料。先前同日的真 Luna、真 PostgreSQL與瀏覽器旅程證據直接沿用，不為 authority 切換重做。

## 官方依據

- [pnpm 12 filtering](https://pnpm.io/filtering)：多個 `--filter` 取聯集並限定命令作用範圍。
- [pnpm 12 run](https://pnpm.io/cli/run)：`--parallel` 是多套件長程序的正式模式，`--stream` 保留各套件即時輸出。
- [Node.js 24 child process](https://nodejs.org/download/release/latest-v24.x/docs/api/child_process.html)：`spawn()` 是穩定的非同步子程序 API；Windows 的可執行檔與 command script 行為須分開處理。
- [uv build backend](https://docs.astral.sh/uv/concepts/build-backend/)：正式 Python package 使用 uv build backend 與鎖定環境。
- [Next.js Turbopack root](https://nextjs.org/docs/app/api-reference/config/next-config-js/turbopack)：monorepo root 必須涵蓋解析依賴所需的共同父層。

## 未被本 gate 宣稱完成的事項

- 真人員工品質試用與更多異質職位，不由工程切換代替。
- OpenRouter cache hit、provider-native compaction 等既有未驗項，不因根入口通過而改判。
- GitHub PR／checks／merge 在本證據寫入時尚待執行，完成後由 PR 與 Git 歷史提供外部交付證據。
- pnpm 12 的 lockfile 是官方多文件 YAML 格式；GitHub dependency graph 是否完整解析須在 push 後另行觀察，不以本地 frozen install 代替。
