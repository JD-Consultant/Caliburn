# 原生開發初始化

原生模式執行 `apps/backend` 與 `apps/frontend`，正式同源模式由同一 FastAPI 程序提供建置後的 Web。PostgreSQL 與 Qdrant 仍須先啟動，可共用本專案的 Compose 資料服務。

## 安裝

工具版本依根 [package.json](../../package.json)、[後端 pyproject](../../apps/backend/pyproject.toml)及 lock：Node 24、pnpm 12、Python 3.14 與 uv。根目錄執行：

```powershell
pnpm install --frozen-lockfile
uv sync --project apps/backend --locked --extra local-models
```

Node 使用根唯一的 `pnpm-lock.yaml`；Python 使用 `apps/backend/uv.lock`。公版權重不隨安裝下載，事先備妥固定版本。後端使用自己的 `.venv`。

## 環境與資料服務

尚無設定檔時，將 `apps/backend/.env.example` 複製為同目錄 `.env`，依真實環境填入：

- `CALIBURN_REBUILD_DATABASE_URL`：獨立新 PostgreSQL 的 SQLAlchemy URL。
- `CALIBURN_REBUILD_REFERENCE_CONFIG`：公版 JSON 設定，包含 Qdrant、collection 及既有權重 cache；相對路徑以後端工作目錄解析。
- PDF 的字型及相容 Chromium 路徑。
- 需要 AI 時的 Agent JSON、Checkpoint 連線與 OpenAI SDK 環境；設定見[後端 README](../../apps/backend/README.md#啟動)。

使用根 Compose 資料服務時，先完成[快速開始](getting-started.md#1-準備環境與設定)的根 `.env`，再執行 `pnpm docker:deps`。原生後端連 host 的 `127.0.0.1:55441`（PG）與 `http://127.0.0.1:6335`（Qdrant），不能照抄容器內的 `postgres`／`qdrant` 主機名。

## 遷移與啟動

```powershell
pnpm app:migrate
pnpm app:status
pnpm dev
```

`app:migrate` 明示升級業務 Schema。Checkpoint 連線若使用專用 schema，先由資料庫管理入口建立該 schema；官方 Saver setup 只建立自己的表。需要初始化 Saver 時，在根目錄另執行：

```powershell
pnpm app:migrate --with-checkpoints
```

開發 UI 位於 [127.0.0.1:5174](http://127.0.0.1:5174)，後端位於 `127.0.0.1:8101`。Vite 將 `/api` 轉送並重寫至後端；後端未設 Web dist 時 API 文件為 `/docs`。

正式同源模式：

```powershell
pnpm build
pnpm start
```

此時開啟 [127.0.0.1:8101](http://127.0.0.1:8101)，API 文件為 `/api/docs`。不要同時在同一埠啟動開發與正式後端。關閉自己啟動的終端程序，不按埠號猜測並終止其他程序。

## 檢查

```powershell
pnpm check
```

根檢查涵蓋文件、靜態檢查、單元／前端測試與 build。真 PostgreSQL、Qdrant 及瀏覽器旅程見[驗證責任](../implementation/verification-plan.md)。未配置專用測試依賴的 skip 不算整合通過；此命令不授權付費模型外送。
