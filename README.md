# Caliburn

**透過訪談理解工作，逐步寫成有依據的職務說明書。**

Caliburn 是本機 Web AI 職務分析工具。員工說明實際工作，AI 顧問依回答追問、釐清責任範圍，逐步寫成職務說明書（JD），不要求員工先學會 JD 的寫法。

**說明工作 → 顧問釐清 → 編輯 JD → 回查依據 → 匯出 PDF**

- **邊訪談、邊改稿**：同頁查看訪談與 JD；AI 處理中可預覽改動，完成後人可繼續編輯。
- **長訪談延續分析**：背景 Memory 將有效訪談整理成工作情境與工作理解，供顧問按需讀取。
- **有依據的內容**：JD 可引用訪談原話、工作情境或工作理解；來源更新與人工改稿後，可查看差異及待核對項目。
- **可接續的工作**：支援訪談暫停、繼續、取消，以及已保存處理紀錄的回看。

## 正式產品

正式 App 位於 `apps/api`（FastAPI／PostgreSQL／LangGraph）與 `apps/web`（React／MUI）。模型使用 OpenAI 直連 Responses API 的 `gpt-6-luna`／high，App 自行管理原生接續項目與壓縮；不使用遠端對話保存。後端可同源提供建置後的畫面，不必另外啟動前端伺服器。正式權責與切換見 [ADR 0079](docs/adr/0079-target-rebuild-production-cutover.md)。

舊的 `experiments/jd-relational-app` 與 `packages/consultant-memory` 程式已退役，只保留研究與沿革文件；精確退役清單與取回方式見 [ADR 0079](docs/adr/0079-target-rebuild-production-cutover.md#退役範圍與取回)。不提供舊資料搬移或相容層。

## 執行環境

| 項目 | 使用版本或條件 |
|---|---|
| Node.js／pnpm | Node.js `>=24.19.0 <25`；pnpm `12.5.1` |
| Python／uv | Python `3.14`；uv `0.12.20` |
| PostgreSQL | 本機 `18.6`，由容器或本機安裝獨立啟動 |
| AI 訪談 | OpenAI API key；沒有 key 時仍可人工編輯 JD |
| PDF 匯出 | 授權的中文字型與 Playwright Chromium，見 [PDF 設定](docs/runbook.md#pdf-匯出) |

Node／TypeScript workspace 使用根目錄 `pnpm-lock.yaml`；Python 使用 `apps/api/uv.lock`。

## 第一次設定

以下命令都在專案根目錄執行，範例使用 PowerShell。首次安裝先建立一個空的專用 PostgreSQL database；更新已有的 Caliburn 時，沿用原資料庫，不另建空庫。

### 1. 安裝依賴

```powershell
pnpm install --frozen-lockfile
uv sync --project apps/api --locked
```

### 2. 設定資料庫與 AI

```powershell
# 連線字串僅示意格式；實際帳密由本機秘密管理提供，勿提交。
$env:CALIBURN_DATABASE_URL = 'postgresql://帳號:密碼@127.0.0.1:5432/caliburn'
$env:CALIBURN_DATABASE_SCHEMA = 'caliburn'  # 預設值，可省略
```

OpenAI key 二擇一：由環境變數 `OPENAI_API_KEY` 提供，或在 `apps/api/.env` 放唯一一行 `OPENAI_API_KEY=你的金鑰`。該檔案已被 Git 忽略；`pnpm start`／`pnpm dev` 會自動讀取它，**但不從中載入資料庫、PDF 或其他設定**。

PowerShell 的 `$env:…` 只對目前視窗及其啟動的程序有效。換新視窗後，須重新提供資料庫與 PDF 設定；以環境變數提供的 key 也一樣。

### 3. 初始化並建置

```powershell
pnpm app:migrate   # 建立／升級 App schema；不清除既有資料
pnpm build         # 建置畫面，供 pnpm start 使用
pnpm start
```

開啟 [http://127.0.0.1:8100/](http://127.0.0.1:8100/)，建立職務檔案即可開始。需要匯出 PDF 時，先完成 [PDF 設定](docs/runbook.md#pdf-匯出)。啟動不會自動執行 migration。

## 日常啟動

先啟動 PostgreSQL，在同一個 PowerShell 視窗提供所需設定，再選一種方式：

| 用途 | 命令 | 開啟位置 |
|---|---|---|
| 使用或錄影展示 | `pnpm start` | [http://127.0.0.1:8100/](http://127.0.0.1:8100/)；需已有建置 |
| 開發前端 | `pnpm dev` | [http://127.0.0.1:5173/](http://127.0.0.1:5173/)；同時啟動後端與 Vite |

兩種方式都使用後端 `8100`，不要同時執行。按 Ctrl+C 正常停止；重開會依已保存狀態承接工作，已接受的 AI 工作可能繼續消耗模型額度。暫停、取消與接續規則見 [共用執行說明](docs/implementation/agent-execution.md)。

`pnpm app:status` 可診斷目前終端的環境設定與資料庫連線，不啟動服務或模型。它不自動讀取 `apps/api/.env`，也不套用 `pnpm start` 的 Web 建置目錄，不能當成正在執行的服務狀態。判讀方式、DataGrip 與故障排除見 [操作手冊](docs/runbook.md#診斷)。

## 更新已有安裝

先讓工作停在安全點，正常停止自己啟動的 App，並備份原資料庫。沒有本機程式修改時，在專案根目錄執行：

```powershell
git pull --ff-only
pnpm install --frozen-lockfile
uv sync --project apps/api --locked
# 在此視窗提供原資料庫／schema 與所需 PDF 設定。
pnpm app:migrate
pnpm build
pnpm start
```

沿用原資料庫、schema 及 key，不重建 volume 或清空資料。若 `git pull` 因分支分歧或本機修改而拒絕，先核對差異，不用強制覆蓋；Git 歷史修正的舊提交對照見 [歷史查閱](docs/history.md)。備份與停止方式見 [操作手冊](docs/runbook.md#資料庫與備份)。

## 驗證

```powershell
pnpm check    # lint、型別、單元／契約測試（不需資料庫）、前端測試與 production build
```

真 PostgreSQL 整合測試、真瀏覽器與真模型結果分開記錄；PostgreSQL 測試需明確指定隔離的 `_test` 資料庫，見 [後端 README](apps/api/README.md#測試與檢查)。

## 驗證範圍

實際結果見 [驗證範圍](docs/architecture/verification.md)、[實驗發現](docs/reports/experiment-findings.md)與[原始資料](docs/experiments/product-validation/README.md)。跨輪綜合的 JD 項目仍有來源漏引反例；PDF 部分字型的文字複製／搜尋會出現部首字元。速度受 OpenAI 帳戶的每分鐘 token 上限（TPM）影響：既有 200K TPM 帳戶的合成實驗中，12 輪訪談約 6–25 分鐘，長訪談需數小時，不作為其他環境的效能承諾。

## 閱讀入口

| 想了解什麼 | 文件 |
|---|---|
| 產品解決的問題與使用流程 | [產品介紹](docs/product-introduction.md) |
| 專題的動機、方法、實驗與成果 | [專題報告](docs/reports/project-report/report.md) |
| 程式內部如何分工、管理資料與延續分析 | [系統架構報告](docs/reports/system-architecture/README.md)，含流程圖與設計取捨 |
| 維護程式、查找契約與操作方法 | [文件導覽](docs/README.md)、[現行架構](docs/target-architecture-map.md) |
| 查閱研究與開發過程 | [研究與實驗材料](docs/reports/README.md)、[歷史查閱](docs/history.md) |

## 文件與 RAG

有效決策見 [`docs/current-decisions.md`](docs/current-decisions.md)，實驗原件見[產品驗證資料](docs/experiments/product-validation/README.md)。舊設計與已結案工作依[歷史查閱方式](docs/history.md)取回；本機封存不隨 Git 發布。

目前未提供 JD App 的 Docker 交付配置；根目錄 Compose 只提供隔離的 RAG 服務，不會建立 JD App 資料庫。`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder` 與 `packages/ocs-contract` 不是 JD App 的執行依賴，只有明確執行 `pnpm rag:up`／`pnpm rag:dev` 才會啟動；細節見 [RAG 說明](docs/design/rag-pipeline.md)。
