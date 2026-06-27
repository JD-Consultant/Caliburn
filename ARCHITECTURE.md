# Architecture

> 高層地圖,**刻意簡短**(只寫不常變的)。完整設計見 [`docs/specs/2026-06-27-system-architecture-design.md`](docs/specs/2026-06-27-system-architecture-design.md);決策見 [`docs/adr/`](docs/adr/)。

## 鳥瞰

Caliburn 是給顧問用的**多租戶 B2B SaaS**:把官方 OCS 職能基準 → 客製職務說明書。一個 monorepo,三個 bounded context + 一個前端:

```
PDF ──▶ pdf-to-json ──(OCS JSON)──▶ ocs-indexer ──(HTTP 查詢)──▶ api ──▶ web ──▶ 使用者
        解析(ETL)                  檢索(Qdrant+ML)            著作(FastAPI+LangGraph)  (Next.js)
```

## Code map

| 路徑 | 是什麼 | 內部風格 |
|---|---|---|
| `apps/pdf-to-json/` | PDF→OCS JSON 的 ETL(CLI) | Pipes-and-Filters(parser→transformer→writer) |
| `apps/ocs-indexer/` | Qdrant+BGE-M3 知識/查詢服務(:8000) | ingest 管線 + 查詢 API;embeddings port/adapter |
| `apps/api/` | FastAPI + LangGraph 後端(:8001) | 領域模組 + agent;目標 Hexagonal(core/ports + adapters,見 spec Phase 3) |
| `apps/web/` | Next.js 16 前端(:3000) | feature 化、server/client 邊界 |
| `packages/` | 共用套件 | Phase 2:`ocs-contract`(契約優先) |
| `docs/` | 系統文檔 / ADR / runbook | 見 `docs/README.md` |

## 跨切原則(不常變的)

- **Hexagonal/Clean + DDD,每 context 一個模組化單體**(非微服務)。依賴往內指向 domain core。
- **資料主權**:Postgres 屬 api、Qdrant 屬 indexer;別的服務只經其 API 取資料,不直接碰倉庫。
- **契約優先**(Phase 2):OCS 結構由 `packages/ocs-contract` 的 JSON-Schema 單一定義。
- **多租戶**:租戶隔離只在 api(Pool + Postgres RLS);知識服務全域共享。
- **Agent**:LangGraph + 12-factor;indexer 縫 MCP-ready。

決策史與取捨:[`docs/adr/`](docs/adr/)。維運:[`docs/runbook.md`](docs/runbook.md)。上手:[`CONTRIBUTING.md`](CONTRIBUTING.md)。
