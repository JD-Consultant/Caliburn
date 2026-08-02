# Architecture

> 高層地圖,**刻意簡短**(只寫不常變的)。完整設計見 [`docs/specs/2026-06-27-system-architecture-design.md`](docs/specs/2026-06-27-system-architecture-design.md);決策見 [`docs/adr/`](docs/adr/)。

## 鳥瞰

Caliburn 是給員工使用的**本機 Web AI 職務分析與職務說明書應用程式**。第一版是一名本機操作者、
無登入／帳密／多租戶 SaaS；OCS／iCAP 等公版資料只作參考與匯出格式，不取代員工訪談所得的
客製工作分析。一個 monorepo,三個 bounded context + 一個前端:

```
PDF ──▶ pdf-to-json ──(OCS JSON)──▶ ocs-indexer ──(HTTP 查詢)──▶ api ──▶ web ──▶ 使用者
        解析(ETL)                  檢索(Qdrant+ML)            著作(FastAPI+訪談引擎)   (Next.js)
```

## Code map

| 路徑 | 是什麼 | 內部風格 |
|---|---|---|
| [`apps/pdf-to-json/`](apps/pdf-to-json/README.md) | PDF→OCS JSON 的 ETL(CLI) | Pipes-and-Filters(parser→transformer→writer) |
| [`apps/ocs-indexer/`](apps/ocs-indexer/README.md) | Qdrant 知識/查詢服務(:8000) | ingest 管線 + 無狀態查詢 API;嵌入走 embedder 服務 |
| [`apps/embedder/`](apps/embedder/README.md) | BGE-M3 GPU 嵌入容器(:8082) | FastAPI + FlagEmbedding(torch 只住這裡,ADR 0012) |
| [`apps/api/`](apps/api/README.md) | FastAPI 後端+訪談引擎(:8001) | Hexagonal(core/ports + adapters + services + interview,ADR 0008/0030) |
| [`apps/web/`](apps/web/README.md) | Next.js 16 前端(:3000) | React Query cache-as-state + 選擇性持久化;文件工作台 |
| `packages/` | 共用契約套件 | `ocs-contract`(#1/#3)、`indexer-contract`(#2) |
| `docs/` | 系統文檔 / ADR / runbook | 見 `docs/README.md`(文檔分層原則也在那) |

**文檔分層(monorepo)**:本檔管**跨 app** 鳥瞰;各 app 內部地圖/流程/不變量在
**該 app 的 `README.md`**(colocation);「為什麼」在 `docs/adr/`。互連不互抄。

## 跨切原則(不常變的)

- **Hexagonal/Clean + DDD,每 context 一個模組化單體**(非微服務)。依賴往內指向 domain core。
- **資料主權**:Postgres 屬 api、Qdrant 屬 indexer;別的服務只經其 API 取資料,不直接碰倉庫。
- **契約優先**(Phase 2):OCS 結構由 `packages/ocs-contract` 的 JSON-Schema 單一定義。
- **產品資料**:第一版是單機、單操作者、一次開啟一份 JD；repo 早期 RLS／tenant 程式不是新工作的
  架構前提，不新增登入、ACL、計費或多人協作。
- **AI 工作面**:`apps/api/app/interview/` 是淘汰但暫留的舊訪談路徑；
  `apps/api/app/job_analysis/` 是 ADR 0040／0042 下的現行 greenfield Task Analysis 引擎，
  已接 PostgreSQL、`/api/v1/job-analysis` 與 `/workspace` 本機 Web。兩者不得互相 import、搬資料或雙寫；舊 LangGraph／CopilotKit
  已退場勿救回。
- **依賴降級**:對 indexer 等外部依賴**逐端點分類**——critical(掛→快錯 5xx)vs enrichment(掛→回部分資料 + `meta.partial`,不擋主流程)。見 [ADR 0018](docs/adr/0018-indexer-dependency-degradation-policy.md)。

決策史與取捨:[`docs/adr/`](docs/adr/)。維運:[`docs/runbook.md`](docs/runbook.md)。上手:[`CONTRIBUTING.md`](CONTRIBUTING.md)。
