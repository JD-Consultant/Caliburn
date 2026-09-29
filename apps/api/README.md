# Caliburn backend（新目標施工中）

本目錄是新架構，不沿用同路徑的舊 venv、DB 或配置。目前提供 health、職務檔案建立／清單／改名／回讀、App 開場正式訪談及生成契約；AI 訪談、JD 和 Memory 產品功能尚未交付。現行正式產品入口不變，進度見[任務表](../../docs/plans/2026-09-29-target-rebuild/tasks.md)。目前僅供隔離開發／合成測試，完整瀏覽器入口安全與正式交付 gate 尚未完成，不對外開放。

## 安裝與執行

從 repo root 執行。使用 Python 3.14、uv 0.12.20；先安裝根 `package.json` 指定的 Node 24／pnpm，前端生成器也需要該環境。精確依賴由 `uv.lock` 保存。

```powershell
$env:UV_PROJECT_ENVIRONMENT = Join-Path $PWD 'apps/api/.venv-target'
uv sync --project apps/api --locked
pnpm install --filter @caliburn/frontend --frozen-lockfile --strict-peer-dependencies
uv run --project apps/api --locked uvicorn caliburn.bootstrap:create_app --factory --host 127.0.0.1 --port 8100 --loop asyncio:SelectorEventLoop
```

`GET /api/health` 回傳 `{"status":"ok"}`，只表示程序存活，不表示 DB／模型可用。Ctrl+C 停止前景開發程序。新應用不在 import 時讀取 `.env`，這組命令不需模型金鑰，也不使用現行產品資料。

Windows 的 psycopg async 不支援預設 Proactor loop，因此明確使用 Python／Uvicorn 支援的 Selector factory，而非已棄用的全域 event-loop policy。這尚不代表 PDF 的 Windows 子程序接線已驗證；後續 T13 必須處理其不同 loop 需求，見[介面交付](../../docs/implementation/interface-and-delivery.md#4-pdf-與程序)。

## 驗證

### 目標資料庫初始化

先建立**專用的新空白 PostgreSQL database**，不填舊產品連線。以下從 repo root 執行；密碼由本機秘密管理注入，勿提交。僅使用新的配置名稱，不自動載入 `.env`。

```powershell
$env:CALIBURN_DATABASE_URL = 'postgresql://帳號:密碼@127.0.0.1:5432/caliburn_target'
$env:CALIBURN_DATABASE_SCHEMA = 'caliburn'
uv run --project apps/api --locked alembic -c apps/api/alembic.ini upgrade head
uv run --project apps/api --locked alembic -c apps/api/alembic.ini check
```

migration 會在已存在的目標 DB 建立指定 namespace；重跑 `upgrade head` 不重建原資料。應用啟動只檢查 migration head，不默默升級。未配置新 DB 時 health 仍可用、檔案 API 回 503；已配置但結構未初始化／不相符則啟動失敗。初始 schema 包含不可變原文，不提供破壞性 downgrade；需要資料處置應另行核對精確範圍。

目前資料入口（具體 DTO 由 `/openapi.json` 與 `contracts/http/` 生成）：

- `POST /api/job-files`：`command_id`、`display_name`、`employee_name`；新建立回 201，同一命令重送回原結果／200，不同輸入重用命令回 409。
- `GET /api/job-files`、`GET /api/job-files/{job_file_id}`：清單／目前檔案 metadata。
- `POST /api/job-files/{job_file_id}/rename`：`command_id`、`expected_name_revision`、`display_name`；只改檔案標籤。同命令回原結果／200，過期修訂或改 payload 重用命令回 409。GET 的 `name_revision` 作下次改名基準，不能在重送時偷換。成功後再 GET 目前名稱；員工姓名與訪談不變。
- `GET /api/job-files/{job_file_id}/interviews`：只有已正式化的訪談；目前建立後只有來源為 App 的開場第 1 則。未完成原文不在這裡出現。
- `POST /api/job-files/{job_file_id}/inputs`：`command_id`、`text`；原文與 A 准入同次保存回 202，重送原命令回原接受結果／200，改內容重用命令或已有其他 A 回 409。重新提交已取消原文須用新命令，不是重送舊命令。**目前只做持久接受，尚無模型 runner／控制 UI，不會生成答覆**；不提供任意正式化 API。接線及未完邊界見[訪談保存](../../docs/implementation/interview-storage.md#6-輸入接受重送與新提交)。

### 測試與檢查

保持前述 `UV_PROJECT_ENVIRONMENT`；不要意外使用舊 `apps/api/.venv`。

```powershell
uv run --project apps/api --locked pytest apps/api/tests/unit apps/api/tests/contracts -q
uv run --project apps/api --locked ruff check apps/api
uv run --project apps/api --locked ruff format --check apps/api
uv run --project apps/api --locked mypy --config-file apps/api/pyproject.toml apps/api/src/caliburn
uv run --project apps/api --locked python apps/api/scripts/generate_contracts.py --check
```

修改 `contracts/http/*.schema.json` 後，執行相同生成命令但不帶 `--check`。標準生成器產 Python／TS，禁止手改 `generated/`。App schema 與模型原生輸出是不同邊界：前者拒絕額外欄位，後者保留 SDK 原生項目及未知 metadata。

真 PostgreSQL 測試只接受**明確指定、loopback、名稱以 `_test` 結尾的隔離資料庫**；缺環境變數會 skip，不代表通過。測試建立隨機 schema，完成後只清理自己新建的 schema，不刪 DB。

```powershell
# 使用自行建立的空白測試 DB，不填既有產品 DB 或真實員工資料。
$env:CALIBURN_TEST_DATABASE_URL = 'postgresql://測試帳號:測試密碼@127.0.0.1:5432/caliburn_test'
uv run --project apps/api --locked pytest apps/api/tests/integration -m postgres -q
```

SDK 測試以 `MockTransport` 攔截所有請求，不連 OpenAI；跨程序 PG probe 只驗框架原生字典及既存 node 接續，不能替代 T06／T12 的業務副作用、取消與故障驗收。真 API 測試必須另外依[有界授權](../../docs/plans/2026-09-29-target-rebuild/README.md#3-狀態與施工順序)執行。
