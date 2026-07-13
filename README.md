# Caliburn

給顧問用的多租戶 B2B SaaS(職能基準 OCS → 職務說明書)。Monorepo:Turborepo + per-app uv。
架構見 [`ARCHITECTURE.md`](ARCHITECTURE.md);決策見 [`docs/adr/`](docs/adr/);維運見 [`docs/runbook.md`](docs/runbook.md)。

---

## 快速開始

### 先備工具
- **Node 22 + npm 10**、**[uv](https://docs.astral.sh/uv/)**(Astral)、**Docker Desktop**(WSL2 backend)。
- 嵌入服務 `embedder` 需 **NVIDIA GPU**(Docker Desktop + WSL2 nvidia runtime;本機已驗證 RTX 4060)。

### 首次安裝
```bash
npm install                                   # JS（根:web + turbo）
cd apps/api          && uv sync               # 後端
cd apps/ocs-indexer  && uv sync --all-extras  # 知識/查詢
cd apps/pdf-to-json  && uv sync --extra dev   # PDF→JSON ETL（非常駐）
docker compose up -d --build embedder         # 首次 build 嵌入容器（~15GB，含 CUDA torch）
```

### 一鍵啟動 / 關閉
```bash
npm run up      # = docker compose up -d（db + qdrant + embedder）&& turbo dev（api + web + indexer）
# Ctrl-C 收掉 dev server；若視窗被硬關留下孤兒進程，改用下面的 down 全清
npm run down    # = docker compose down + kill-port 3000/8000/8001（停 infra + 收掉 dev server；named volume 資料保留）
```

| 服務 | 埠 | 說明 |
|---|---|---|
| **web** | http://localhost:3000 | Next.js 前端（著作工作台,入口 `/dashboard` → `/documents/[id]`) |
| **api** | http://localhost:8001 | FastAPI + 訪談引擎後端（健康檢查 `/healthz`） |
| **ocs-indexer** | http://localhost:8000 | Qdrant 知識/查詢服務 |
| **db** | localhost:5432 | Postgres（業務表;無 in-DB 向量,檢索走 Qdrant;容器 `caliburn-db-1`） |
| **qdrant** | localhost:6333 | 向量庫（容器 `caliburn-qdrant-1`） |
| **embedder** | http://localhost:8082 | BGE-M3 GPU 容器（dense+sparse;`caliburn-embedder-1`） |

### 首次資料初始化
```bash
npm run db:migrate                                          # Postgres schema（alembic upgrade head）
cd apps/ocs-indexer && uv run jd-ocs-indexer index ./data/jd-json   # 建 Qdrant 索引（經 embedder,不需本機 torch）
```
開瀏覽器 **http://localhost:3000** → 新增職務 → 進入 `/documents/[id]` 著作。

### 測試 / Lint(提交前)
```bash
npx turbo test                  # api / ocs-indexer / pdf-to-json（pytest）+ web（vitest）
cd apps/web && npx tsc --noEmit && npm run lint
```

---

## 進一步
- [`CONTRIBUTING.md`](CONTRIBUTING.md) —— 安裝細節、專案結構、提交規範、平台踩雷。
- [`docs/runbook.md`](docs/runbook.md) —— 埠位圖、起停 / 重啟紀律、故障排除。
- [`docs/README.md`](docs/README.md) —— 文件索引(ADR / 研究紀錄 / 契約策略 / 命名規範)。
- [`ARCHITECTURE.md`](ARCHITECTURE.md) —— 系統大框架(3 bounded context、六邊形 api、契約、嵌入服務)。
