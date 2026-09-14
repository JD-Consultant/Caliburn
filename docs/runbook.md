# Runbook — Caliburn 本機開發

Current 產品只有 PostgreSQL、FastAPI 與 Next.js；OpenRouter 是外部 LLM gateway。RAG 供應鏈保留但尚未接入 current 產品，必須明確 opt-in。

## 埠位

| 埠 | 服務 | 起法 |
|---|---|---|
| 5432 | PostgreSQL | `npm run infra` |
| 8001 | API | `cd apps/api && uv run python run_live.py` 或 `npm run dev` |
| 3000 | Web | `npm run dev` |
| 6333／6334 | Qdrant（隔離 RAG） | `npm run rag:up` |
| 8082 | embedder（隔離 RAG） | `npm run rag:up` |
| 8000 | ocs-indexer（隔離 RAG） | `npm run rag:dev` |

## Fresh DB 與首次啟動

若 Docker Desktop 在啟動時報 Windows socket／`The file cannot be accessed by the system`，先讀[2026-09-06 維運紀錄](specs/2026-09-06-docker-desktop-startup-repair.md)。不要直接重設／刪除 volumes，也不要把一次成功啟動當成重啟已穩定；該次自動啟動問題仍未證明根治。

```bash
npm install
npm run infra
npm run db:migrate
npm run consultant-storage:setup
npm run dev
```

執行順序有意分開：Alembic root `0018_consultant_runtime_root` 先建立 `consultant_documents` catalog；接著 LangGraph 官方 `.setup()` 建立 Saver／Store tables；最後才啟動 API／Web。已初始化的日常環境可直接 `npm run up`。

健康檢查：`http://127.0.0.1:8001/healthz`；工作台：`http://localhost:3000/workspace`。API reload 已關閉，改 Python 後要重啟。`npm run down` 會停止 compose 並清理 `3000`／`8001` 的孤兒程序。

## 資料庫邊界

空 DB 完成 migration＋setup 後，public schema 應只有：

- `alembic_version`、`consultant_documents`；
- LangGraph 官方 `checkpoints`、`checkpoint_blobs`、`checkpoint_writes`、`checkpoint_migrations`、`store`、`store_migrations`。

不得出現 `job_analysis_*` 舊表，也沒有資料搬移、雙寫或 compatibility converter。若本機 volume 仍是舊 schema，且確定資料可丟棄，重建：

```bash
docker compose down -v
docker compose up -d db
npm run db:migrate
npm run consultant-storage:setup
```

## OpenRouter

複製 `apps/api/.env.example` 為 `.env`，填入 `OPENROUTER_API_KEY`。`CONSULTANT_MODEL`／`CONSULTANT_PROVIDER` 指定一條 exact route，profile／policy revision 與參數會在每輪解析成 immutable execution snapshot；第一版禁止 silent fallback。沒有 key 時，catalog／snapshot 等不需模型的功能仍可使用，AI 回合回 typed unavailable response。

Git worktree 不會自動帶入被 ignore 的 `apps/api/.env`。在隔離 worktree 做 live model smoke 時，應由啟動程序安全注入 key與明確的 `CONSULTANT_MODEL`／`CONSULTANT_PROVIDER` override；不要把 secret 複製、commit 或印到 log。判定實際路由時讀 durable attempt receipt 的 `actual_model`／`actual_provider`，不能只相信 shell 目標值；若 attempt receipt 為空，代表尚未呼叫 provider。

## RAG（保留、隔離、非 current runtime）

`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder`、`packages/ocs-contract` 與 `packages/indexer-contract` 不在 current API/Web dependency graph，也不由預設指令啟動：

```bash
npm run rag:up
npm run rag:down
npm run rag:dev
```

目前產品沒有 Reference／RAG route、tool、contract 或 UI；不要把上述服務接進 current composition root。詳見 [`design/rag-pipeline.md`](design/rag-pipeline.md)。

## 驗證與故障排除

```bash
npx turbo test
cd apps/api && uv run pytest -q
cd apps/web && npm run test && npx tsc --noEmit && npm run lint
npm run check-codegen -w @caliburn/job-analysis-contract
```

`apps/api/tests/test_consultant_hard_cut.py` 會阻止舊 writer／route／migration／contract 復活；`test_consultant_foundation_boundaries.py` 會阻止 RAG 或 provider adapter 滲入核心顧問邏輯。若 import 行為與 code 不符，先確認 `pwd`、branch 與殘留 `__pycache__`，不要恢復已刪模組。
