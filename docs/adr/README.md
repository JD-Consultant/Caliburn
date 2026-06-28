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

完整脈絡見 [`../specs/2026-06-27-system-architecture-design.md`](../specs/2026-06-27-system-architecture-design.md)。
