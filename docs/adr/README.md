# Architecture Decision Records (ADR)

每份 ADR 記錄**一個**重大決策的脈絡、決定、與後果(取捨)。格式採輕量 Nygard 式。
ADR 是「為什麼」層;搭配 `../specs/`(細節設計)與 `../runbook.md`(怎麼操作)。

> 規則:ADR 一旦 Accepted 就**不改內容**;要翻案就新開一份 ADR 標 `Supersedes`/`Superseded by`。

## 索引

| # | 決策 | 狀態 |
|---|---|---|
| [0001](0001-monorepo-with-turborepo.md) | Monorepo（Turborepo + per-app uv），非 polyrepo | Accepted（Phase 1 已實作） |
| [0002](0002-three-bounded-contexts-modular-monolith.md) | 三個 bounded context，各為模組化單體 | Accepted |
| [0003](0003-indexer-stays-separate-service.md) | ocs-indexer 維持獨立服務 | Accepted |
| [0004](0004-contract-first-ocs-contract.md) | 契約優先 `packages/ocs-contract` | Accepted（Phase 2 規劃中） |
| [0005](0005-per-app-uv-defer-workspace.md) | per-app uv 專案;uv workspace 延後 | Accepted（Phase 1） |
| [0006](0006-multitenancy-pool-rls.md) | 多租戶 Pool + Postgres RLS | Accepted（登入時實作） |
| [0007](0007-langgraph-retained-mcp-ready.md) | LangGraph 留用 + 12-factor + MCP-ready | Accepted |
| [0008](0008-api-hexagonal-layering.md) | api 六邊形分層:ports→core、adapters→edge、移除反向邊 | Accepted（Phase 3a 已實作） |
| [0009](0009-embedding-version-manifest.md) | embedding 版本 manifest + 查詢前相容驗證;瘦 CLI | Accepted（Phase 3c 已實作） |
| [0010](0010-indexer-contract-shared-package.md) | 契約 #2 indexer 查詢 API：共用 pydantic 套件（非 codegen/Pact） | Accepted（契約 #2 已實作） |
| [0011](0011-web-ocs-types-generated.md) | 契約 #3 Part A：web 改吃 ocs-contract 生成的 TS 型別 | Accepted（契約 #3 Part A 已實作） |
| [0012](0012-embedding-as-a-service.md) | 嵌入服務化：自建 BGE-M3 容器（保留 dense+sparse、torch 移出 app） | Accepted |
| [0013](0013-naming-cleanup-caliburn.md) | 命名整理：web 改 Caliburn、內部去版號（graph_v3→authoring、/v3→/documents）、容器/DB 去 jobintel | Accepted |
| [0014](0014-db-image-stock-postgres.md) | DB image 降回 stock `postgres:16`（移除未使用的 pgvector；D5 後檢索走 Qdrant） | Accepted |
| [0015](0015-document-save-optimistic-concurrency.md) | 文件存檔採樂觀並發（version 守衛）；回合制協作不上 CRDT/OT；minimal 先、逐操作 full 延後 | Accepted |
| [0016](0016-batch-task-catalog-endpoint.md) | 後端批次 task-catalog 端點（每 ocs_code 撈一次池）；前端 setQueryData 灌快取 | Accepted |
| [0017](0017-app-entry-single-composition-root.md) | 後端 app 入口收斂:單一組裝點 + `/healthz` 統一 + 移除 demo app（livez/readyz 待容器化） | Accepted |
| [0018](0018-indexer-dependency-degradation-policy.md) | indexer 依賴降級政策:critical fail-fast vs enrichment 降級 + `meta.partial`（circuit breaker 延後） | Accepted |
| [0019](0019-api-naming-alignment.md) | API 命名對齊:自訂方法 `:verb`、根層 `GET /occupations?q=`、`PUT occupations`（monorepo 原子改名、偏離 AIP-231/132 白紙黑字） | Accepted |

完整脈絡見 [`../specs/2026-06-27-system-architecture-design.md`](../specs/2026-06-27-system-architecture-design.md)。
契約怎麼選/怎麼交付的規範見 [`../contract-strategy.md`](../contract-strategy.md)（ADR 0004/0010 的一般化、預答契約 #3）。
