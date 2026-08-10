# Runbook — Caliburn 本機開發

現行系統只有 PostgreSQL、FastAPI 與 Next.js。舊 OCS／indexer／embedder 服務已移除，不要再啟動或設定它們。

## 埠位

| 埠 | 服務 | 起法 |
|---|---|---|
| 5432 | PostgreSQL | `docker compose up -d db` |
| 8001 | API | `cd apps/api && uv run python run_live.py` 或 `npx turbo dev` |
| 3000 | Web | `npx turbo dev` |

## 啟動與停止

```bash
npm run up
npm run db:migrate
npm run down
```

`npm run up` 只起 PostgreSQL，接著在 host 啟動 API 與 Web。健康檢查：`curl http://127.0.0.1:8001/healthz`；工作台在 `http://localhost:3000/workspace`。

API reload 已關閉；改 Python 後停止並重新啟動 API。`npm run down` 會停 compose 並收 `3000`／`8001` 的孤兒程序。

## 資料庫

Current-only schema 的 root 是 migration `0012_job_analysis_current_state`，目前 head 為 `0017`。它只建立 `job_analysis_*` 七張表與 `alembic_version`，不建立舊 users、documents、interview 或 job_authoring 表。

本次硬切不搬舊資料。若既有 volume 是舊 schema，使用可丟棄的本機資料庫重建：

```bash
docker compose down -v
docker compose up -d db
npm run db:migrate
```

## 測試與故障排除

```bash
npx turbo test
cd apps/api && uv run pytest -q
cd apps/web && npm run test && npx tsc --noEmit && npm run lint
```

若 migration 或 API import 出現已刪除的 OCS／interview 模組，先確認目前 branch、工作目錄與 `uv sync`；不要把舊模組加回來。詳細現行邊界見 [`ARCHITECTURE.md`](../ARCHITECTURE.md) 與 [ADR 0057](adr/0057-current-only-runtime-and-data-boundary.md)。
