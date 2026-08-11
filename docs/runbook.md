# Runbook — Caliburn 本機開發

Current 產品只有 PostgreSQL、FastAPI 與 Next.js；`npm run up`／`npm run dev` 只啟動這三者。舊 `app.interview`／`app.interview_vnext`／`app.job_authoring` 服務已移除，不要再啟動或設定它們。repo 另外保留一組與 current 完全隔離、選用（opt-in）的 RAG 供應鏈（Qdrant／embedder／ocs-indexer），見下方「RAG（選用、隔離）」與 [`design/rag-pipeline.md`](design/rag-pipeline.md)。

## 埠位

| 埠 | 服務 | 起法 |
|---|---|---|
| 5432 | PostgreSQL | `docker compose up -d db` |
| 8001 | API | `cd apps/api && uv run python run_live.py` 或 `npx turbo dev` |
| 3000 | Web | `npx turbo dev` |
| 6333／6334 | Qdrant（選用，RAG） | `npm run rag:up` |
| 8082 | embedder（選用，RAG，GPU） | `npm run rag:up` |
| 8000 | ocs-indexer 查詢 API（選用，RAG） | `npm run rag:dev` |

## 啟動與停止

```bash
npm run up
npm run db:migrate
npm run down
```

`npm run up` 只起 PostgreSQL，接著在 host 啟動 API 與 Web；不會啟動 Qdrant 或 embedder。健康檢查：`curl http://127.0.0.1:8001/healthz`；工作台在 `http://localhost:3000/workspace`。

API reload 已關閉；改 Python 後停止並重新啟動 API。`npm run down` 會停 compose 並收 `3000`／`8001` 的孤兒程序。

## RAG（選用、隔離）

RAG 供應鏈（`apps/pdf-to-json`／`apps/ocs-indexer`／`apps/embedder`／`packages/ocs-contract`／`packages/indexer-contract`）不是 current API/Web 的 runtime dependency，預設不啟動；完整資料流、package 責任與資料落地見 [`design/rag-pipeline.md`](design/rag-pipeline.md)。

```bash
npm run rag:up      # docker compose --profile rag up -d（Qdrant + GPU embedder）
npm run rag:down    # docker compose --profile rag down
npm run rag:dev     # turbo dev --filter=@caliburn/ocs-indexer（查詢 API :8000）
```

`db`（PostgreSQL）沒有 Compose profile，`npm run up`／`docker compose up -d db` 都會啟動它；`qdrant`／`embedder` 標記 `profiles: [rag]`，只有 `npm run rag:up`（或 `docker compose --profile rag up -d`）會啟動。

## 資料庫

Current-only schema 的 root 是 migration `0012_job_analysis_current_state`，目前 head 為 `0017`。它只建立 `job_analysis_*` 七張表與 `alembic_version`，不建立舊 users、documents、interview 或 job_authoring 表；RAG 供應鏈不寫入這個 PostgreSQL（PDF／OCS JSON／Qdrant 是另一套資料世界，見 `design/rag-pipeline.md`）。

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

若 current API import 出現 `app.interview`／`app.interview_vnext`／`app.job_authoring`（已刪除）或 `ocs_contract`／`indexer_contract`／`jd_ocs_indexer`／`jd_pdf_to_json`／`embedder`（RAG 專屬、與 current 隔離）之類的模組，先確認目前 branch、工作目錄與 `uv sync`；不要把舊模組加回來，也不要把 RAG 模組接進 current composition root——`apps/api/tests/test_job_analysis_dependencies.py` 的 AST guard 會擋下這兩種情況。詳細現行邊界見 [`ARCHITECTURE.md`](../ARCHITECTURE.md) 與 [ADR 0057](adr/0057-current-only-runtime-and-data-boundary.md)。
