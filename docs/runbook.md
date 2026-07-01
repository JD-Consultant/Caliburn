# Runbook — Caliburn(本地開發 / 維運操作)

開發環境=四個服務 + 一個 DB。本檔記錄起停、重啟紀律、與踩過的故障排除。
首次安裝/測試見 [`../CONTRIBUTING.md`](../CONTRIBUTING.md)。

## 埠位圖

| 埠 | 服務 | 起法 | 依賴 |
|---|---|---|---|
| 5432 | Postgres(`caliburn-db-1`,docker) | `docker compose up -d db` | — |
| 8000 | ocs-indexer(知識/查詢) | `cd apps/ocs-indexer && uv run jd-ocs-indexer serve --port 8000` | Qdrant |
| 8001 | api(FastAPI+LangGraph,`run_live.py`) | `npx turbo dev`(或 `cd apps/api && uv run python run_live.py`) | Postgres(+indexer 供知識) |
| 3000 | web(Next.js) | `npx turbo dev` | api |

## 起整套(順序)

```bash
docker compose up -d db                       # 1. DB(等 healthy)
cd apps/ocs-indexer && uv run jd-ocs-indexer serve --port 8000 &   # 2. indexer(冷啟載 BGE-M3 ~3s;要知識查詢才需要)
cd /s/caliburn && npx turbo dev               # 3. api(:8001) + web(:3000)
```
驗:`curl 127.0.0.1:8001/healthz`(api 統一 `/healthz`,含 DB readiness;ADR 0017)、瀏覽器開 `localhost:3000`。

## 停 / 重啟

**api 的 `reload` 已關閉(單一進程)。** 日常停止:在跑 `turbo dev` / `run_live.py` 的終端機按 **Ctrl-C** 即乾淨關閉(turbo 把訊號往下傳,uvicorn 單進程直接收掉)。

> ⚠️ **改了後端碼要自己重啟**(無自動 reload) —— Ctrl-C 後重跑即可。

只有進程被**孤兒化**時(終端機沒 Ctrl-C 就關掉、或背景 detached 跑)才需手動清:

```powershell
# 殺掉佔住 8001/3000 的進程(reload 已關,沒有 reloader+worker 雙進程,不需 /T 殺整棵樹)
Get-NetTCPConnection -State Listen -LocalPort 8001,3000 | % { taskkill /F /PID $_.OwningProcess }
Get-NetTCPConnection -State Listen -LocalPort 8001,3000   # 驗證已空
```

## 故障排除

| 症狀 | 多半原因 | 處置 |
|---|---|---|
| 改了後端碼「沒效」 | reload 已關,忘了手動重啟 | Ctrl-C 後重跑 `run_live`(改碼需手動重啟) |
| 前端 **Failed to fetch** | api 掛了 / 回 500 / CORS | `curl 127.0.0.1:8001/healthz`;看 turbo dev log;檢查 api 例外 |
| api 某端點 500「No module named 'greenlet'」類 | 執行期缺依賴(測試 skip DB 沒測到) | 比對真實環境補進 `pyproject.toml` + `uv lock`;async DB 要 `sqlalchemy[asyncio]` |
| `uv run pytest` 說 pytest not found | 該 app 的測試依賴在 extra 裡 | 用對的指令:`--all-extras`(indexer)/`--extra dev`(pdf-to-json) |
| 埠被占 | 舊服務(或別 repo)還在跑 | 用埠位圖查 PID,`taskkill /F /T` |
| db 一直噴 `collation version mismatch`(2.36 vs 2.41) | 換過 Postgres image 基底 OS(如舊 `pgvector/pgvector:pg16` → 官方 `postgres:16`,glibc 不同),既有 `caliburn_pgdata` volume 的 collation 元資料對不上;嚴重時 `CREATE DATABASE`(template1)直接 ERROR(ADR 0014 換 image 後遇到) | dev 無重要資料 → **重建 pgdata**:`docker compose -p caliburn down` → `docker volume rm caliburn_pgdata`(**勿動** `caliburn_qdrant_storage`/`caliburn_hf_cache`)→ `up -d db` → `npm run db:migrate`。要保資料則 `ALTER DATABASE <db> REFRESH COLLATION VERSION;`(template1/postgres/該庫)+ 必要時 `REINDEX` |

## 跑後端 DB 整合測試（pytest）

`apps/api` 的 DB 測試靠 `TEST_DATABASE_URL`;**沒設就整批 skip**(見 `tests/conftest.py`)。逐測試開交易、結束 rollback,故測試庫只需**有 schema**:

```bash
docker exec caliburn-db-1 psql -U postgres -c "CREATE DATABASE caliburn_test;"
cd apps/api && DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/caliburn_test" uv run alembic upgrade head
TEST_DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/caliburn_test" uv run pytest
```

## 部署(SaaS,後端我方託管)

交付 = 客戶連網址,不交程式碼。各 app 獨立部署(monorepo affected-only):
- `web` → Vercel 或容器;`api` → 容器;`ocs-indexer` → 容器(+持久卷,內部不對外);`pdf-to-json` → 離線 job(非服務)。
- Postgres / Qdrant:**先自架**(見 [ADR 0006](adr/0006-multitenancy-pool-rls.md));有真實客戶資料後再評估託管。
- 新客戶 = 建一個 Organization(租戶),**零額外部署**(多租戶 Pool + RLS)。
> 詳細部署拓撲見 spec §部署章節;正式 CI/CD 與 silo 升級為後續工作。
