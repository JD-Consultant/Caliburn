# Caliburn — 文件索引

給顧問用的多租戶 B2B SaaS（職能基準 → 職務說明書）。Monorepo：Turborepo + uv（per-app）。

## 文件擺放原則（hybrid + colocation，業界共識）

- **中央 `docs/`** —— 跨專案 / 系統級 / 活的設計文檔（本資料夾）。
- **各 app 旁邊 `apps/<app>/`** —— 該 app 自己的 README / ARCHITECTURE / 指南（colocation，就近維護）。
- **`docs/archive/`** —— 歷史記錄（不再現行維護，僅供追溯）。

## 中央系統文檔（現行）

- [`specs/2026-06-27-system-architecture-design.md`](specs/2026-06-27-system-architecture-design.md) —— Caliburn 大框架架構設計（monorepo / 契約優先 / 3 bounded context / Hexagonal+DDD / 多租戶）。
- [`plans/2026-06-27-phase1-monorepo-consolidation.md`](plans/2026-06-27-phase1-monorepo-consolidation.md) —— Phase 1（三 repo 併入 monorepo）實作計畫，已執行（tag `phase1-monorepo`）。
- [`ocs-schema.md`](ocs-schema.md) —— OCS JSON 結構與代碼規則（T/P/O/K/S/A）；跨專案共享契約的參考，Phase 2 抽 `packages/ocs-contract` 時的依據。

## 各 app 自帶文檔（colocated）

- `apps/api/` —— FastAPI + LangGraph 後端。
- `apps/web/` —— Next.js 前端（見 `apps/web/README.md` / `AGENTS.md`）。
- `apps/ocs-indexer/` —— Qdrant + BGE-M3 知識/查詢服務（見 `apps/ocs-indexer/README.md`）。
- `apps/pdf-to-json/` —— OCS PDF→JSON ETL（見 `apps/pdf-to-json/README.md`、`ARCHITECTURE.md`、`docs/`）。

## 歷史

- [`archive/jobintel-v3/`](archive/jobintel-v3/) —— 併入 monorepo 前的 jobintel-ai v3 時代設計/決策/計畫文件（2026-06-14～06-27），保留供追溯。
