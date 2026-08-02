# Architecture

> 跨 app 鳥瞰，只寫現行產品邊界、真實 runtime 與已決定的 target。產品範圍見
> [`docs/product-notes.md`](docs/product-notes.md)；顧問核心與切換決策見 ADR
> [0040](docs/adr/0040-professional-consultant-engine-and-r1-validation-contract.md)／
> [0041](docs/adr/0041-document-boundary-single-writer-cutover.md)。

## 產品邊界

Caliburn 是給員工使用的**本機 Web AI 職務分析與職務說明書應用程式**。Web UI、API、PostgreSQL、Qdrant 與必要服務
在員工電腦本機組合運行；LLM 可由本機 API 呼叫 OpenRouter。員工不註冊、不登入、不選 tenant，不接觸 host／port。
一名本機操作者可保存多份彼此隔離的 JD，但一次只開啟一份。

repo 留有早期 user/profile/tenant 欄位與程式，僅屬歷史／FK 相容細節。SaaS、organization/member/ACL、計費、
雲端部署與多人協作不在現行 roadmap。

## 現行 runtime（ACTIVE／TRANSITIONAL）

```text
PDF -> pdf-to-json -> OCS JSON -> ocs-indexer -> Qdrant
                                      |
                                      +-> embedder（BGE-M3 GPU）

員工 -> Next.js Web -> FastAPI API -> PostgreSQL
                         |    |
                         |    +-> OpenRouter
                         +------> ocs-indexer HTTP
```

現行 Web/API 寫入仍是過渡路徑：

```text
/documents/[id]/interview
  -> /api/v1/job-profiles/{profile_id}/interview:turn
  -> app/interview v3
  -> op -> verify -> DocumentVersion.content._pending
  -> Web accept/reject
  -> PATCH /api/v1/job-profiles/{profile_id}/document
```

這是目前唯一使用者可達的 AI 路徑，但已進入 maintenance-only；不得再用它承接新顧問或 current-row Authoring 功能。

## 生命周期地圖

| 區域 | 狀態 | 權威與限制 |
|---|---|---|
| `app/interview` + OCS editor | ACTIVE／TRANSITIONAL | 現行流量；只修阻斷、安全、資料損毀，不擴充 `_pending` |
| `app/interview_vnext` | ISOLATED PROTOTYPE／DONOR | 有 durable persistence、provider/Capture 與舊 operation；production router 不 import；不得直接 promotion |
| `app/job_authoring` v1 | ISOLATED PROTOTYPE | migration 0011 三表 revision core；不是 current-row v2 target，不得擴張 revision entities |
| 專業顧問引擎 | PLANNED／NOT IMPLEMENTED | ADR 0040 greenfield；先跑 R1 Task Discovery，舊 v3/vNext 不作前提 |
| current-row Authoring v2 | PLANNED／NOT IMPLEMENTED | Current Work Model／Current JD 唯一真相；AI 只提 proposal；Current State + Journal 同交易 |
| `local_workspace` Web/API seam | PLANNED／NOT IMPLEMENTED | R1–R5 gate 後才建第一條 production vertical；目前沒有 route/package |

切換按整份 `document_id` 單寫者執行，不做同文件 dual-write。完整 gate、rollback 與退役順序見
[`docs/design/professional-consultant-engine.md`](docs/design/professional-consultant-engine.md)。

## Code map

| 路徑 | 是什麼 | 內部風格 |
|---|---|---|
| [`apps/pdf-to-json/`](apps/pdf-to-json/README.md) | PDF→OCS JSON 離線 ETL | Pipes-and-Filters：parser→transformer→writer |
| [`apps/ocs-indexer/`](apps/ocs-indexer/README.md) | Qdrant 知識／查詢服務（:8000） | ingest pipeline + 無狀態查詢 API；嵌入走 embedder |
| [`apps/embedder/`](apps/embedder/README.md) | BGE-M3 GPU 嵌入容器（:8082） | FastAPI + FlagEmbedding；torch 只住容器 |
| [`apps/api/`](apps/api/README.md) | FastAPI 著作後端（:8001） | Hexagonal：core/ports、adapters、services、API；PostgreSQL owner |
| [`apps/web/`](apps/web/README.md) | Next.js 16 前端（:3000） | 現行 OCS 工作台；新 workspace 尚未實作 |
| `packages/` | 共用契約 | `ocs-contract`（JSON Schema→Pydantic/TS）、`indexer-contract`（共用 Pydantic） |
| [`docs/`](docs/README.md) | ADR、研究、plan、living design、runbook | 文檔分類與 living 規則見 `docs/README.md` |

## 不常變的不變量

- **Bounded contexts**：PDF 解析、OCS 知識檢索、JD 著作；各 context 是模組化單體，不為本機產品拆 SaaS 微服務。
- **依賴方向**：API 採 Hexagonal/Clean + DDD，domain 不 import FastAPI、ORM、provider SDK 或 Web DTO。
- **資料主權**：PostgreSQL 屬 API；Qdrant 屬 indexer；跨 owner 只走 typed API，不直接讀對方 datastore。
- **嵌入隔離**：BGE-M3 dense+sparse 只在 `apps/embedder` Linux GPU 容器；禁止把 torch 放回 indexer/API 進程。
- **契約機制**：跨 Python/TypeScript 用 JSON Schema SSOT + codegen；全 Python 少量 consumer 用共用 typed package。
- **文件權威**：新產品的 Current Work Model／Current JD 是唯一真相；OCS 是 ingest/export shape，不是 live workspace store。
- **AI 權限**：LLM 只能提出有 support/Evidence 的 proposal；員工 accept/edit-accept 後 deterministic application code 才能更新 Current JD。
- **狀態與歷史**：Current State 直接讀；Consultation Journal 與狀態同 transaction 追加，但不作 Event Sourcing replay。
- **依賴降級**：critical dependency fail-fast；reference enrichment 可回部分結果 + `meta.partial`。見 [ADR 0018](docs/adr/0018-indexer-dependency-degradation-policy.md)。

維運見 [`docs/runbook.md`](docs/runbook.md)，上手見 [`CONTRIBUTING.md`](CONTRIBUTING.md)，決策索引見
[`docs/adr/README.md`](docs/adr/README.md)。
