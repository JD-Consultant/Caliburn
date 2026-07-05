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
| [0015](0015-document-save-optimistic-concurrency.md) | 文件存檔採樂觀並發（version 守衛）；回合制協作不上 CRDT/OT；minimal 先、逐操作 full 延後 | Accepted（2a-minimal 已實作：雙 token version+revision、409 + ConflictDialog；full 延後） |
| [0016](0016-batch-task-catalog-endpoint.md) | 後端批次 task-catalog 端點（每 ocs_code 撈一次池）；前端 setQueryData 灌快取 | Accepted（模式由 0021 一般化；task-catalogs 端點與前端 seeding 已於 P3 退役） |
| [0017](0017-app-entry-single-composition-root.md) | 後端 app 入口收斂:單一組裝點 + `/healthz` 統一 + 移除 demo app（livez/readyz 待容器化） | Accepted |
| [0018](0018-indexer-dependency-degradation-policy.md) | indexer 依賴降級政策:critical fail-fast vs enrichment 降級 + `meta.partial`（circuit breaker 延後） | Accepted |
| [0019](0019-api-naming-alignment.md) | API 命名對齊:自訂方法 `:verb`、根層 `GET /occupations?q=`、`PUT occupations`（monorepo 原子改名、偏離 AIP-231/132 白紙黑字） | Accepted |
| [0020](0020-interview-authoring-interaction-model.md) | 訪談式撰寫互動模式:混合載體（文件常駐 + 精靈化訪談面板）；實作可重新設計、不受既有資產約束 | Accepted |
| [0021](0021-knowledge-pack-single-sync-point.md) | 知識包：選職類=唯一 knowledge 同步點；indexer 給資料/api 處理/web 讀寫；來源必標的資料基座 | Accepted（P1–P3 已實作：`/knowledge` 端點＋web 全選單切換＋舊四端點退役） |
| [0022](0022-similarity-matching-items-match.md) | 相似比對 `items:match`：indexer 確定性能力、FS 三區分帶、星型非遞移、非破壞呈現；survivorship 在 web；api 純搬運 | Accepted（v1 已實作：端點＋校準＋pack 掛載＋態度收合/任務徽章） |
| [0023](0023-interview-engine-stateless-turns.md) | 訪談引擎骨幹：無狀態回合服務＋軟階段＋指令詞彙表；quote 溯源；停止三重保險；既有 graph 走 Strangler Fig（接受後部分翻案 0007） | Proposed（草案待核） |
| [0024](0024-llm-wiring-select-schema.md) | LLM 接線：`LlmPort.select_schema`＋受限解碼路徑判準（OpenRouter strict 起步、對抗性驗收、escalation 槽） | Proposed（草案待核） |
| [0025](0025-coedit-authority-dual-channel.md) | 人機共編權限：雙通道＋風險分流＋節點批審（分流寫入目的地，取代「人改過只能提議」） | Proposed（草案待核） |

完整脈絡見 [`../specs/2026-06-27-system-architecture-design.md`](../specs/2026-06-27-system-architecture-design.md)。
契約怎麼選/怎麼交付的規範見 [`../contract-strategy.md`](../contract-strategy.md)（ADR 0004/0010 的一般化、預答契約 #3）。
