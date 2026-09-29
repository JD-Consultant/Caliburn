# Caliburn backend（新目標施工中）

本目錄是新架構，不沿用同路徑的舊 venv、DB 或配置。目前提供最小 health、生成契約及離線／真 PG 基礎測試；訪談、JD 和 Memory 產品功能尚未交付。現行正式產品入口不變，進度見[任務表](../../docs/plans/2026-09-29-target-rebuild/tasks.md)。

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
