# RAG pipeline — PDF → OCS → indexer → embedder/Qdrant（保留、隔離的 bounded context）

> **狀態**：retained future bounded context。**不是** current 產品（`apps/api`／`apps/web`）的一部分，也**不是**已退役的歷史設計。
> `apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder`、`packages/ocs-contract`、`packages/indexer-contract`
> 都是可獨立安裝、測試、執行的 monorepo 成員，但**不被** current API/Web import、呼叫，也不掛在 current 的
> production composition root 上。決策依據：[ADR 0057](../adr/0057-current-only-runtime-and-data-boundary.md)
> Decision 5（Proposed，2026-08-11 修正為保留＋隔離）；設計脈絡與 owner 裁決見
> [`docs/specs/2026-08-11-rag-bounded-context-retention-design.md`](../specs/2026-08-11-rag-bounded-context-retention-design.md)。
> 若要讓 current API/Web 開始消費檢索結果，必須另開 ADR 定義 query contract、index freshness、embedding
> identity、failure fallback 與 provenance／evidence linkage；本檔不是那個授權。

## 1. 端到端資料流

```text
PDF corpus（apps/pdf-to-json/data/pdfs，908 檔）
  │  jd-convert CLI
  ▼
apps/pdf-to-json ──uses──> packages/ocs-contract ──writes──> OCS JSON corpus
                                                              （apps/ocs-indexer/data/jd-json，908 檔）
                                                                  │  jd-ocs-indexer index
                                                                  ▼
                                                            apps/ocs-indexer
                                                                  │
                                    HTTP embed（POST /embed）    │  upsert
                                    ┌─────────────────────┐      ▼
                                    │ apps/embedder（GPU） │ →  Qdrant（docker compose --profile rag）
                                    └─────────────────────┘
                                                                  │
                                                    jd-ocs-indexer serve（:8000，本機 HTTP 語意查詢 API，
                                                    目前沒有任何 consumer）
```

`pdf-to-json` 只負責解析與轉換，不寫 current PostgreSQL；`ocs-indexer` 只負責 ingest、embedding wiring、
Qdrant index/query，不 import `app.*` 或 current API；`embedder` 只提供 BGE-M3 HTTP embedding service，不進
API process。

## 2. Package 與 app 責任

| 路徑 | 職責 | npm workspace 成員 | 語言／管理 |
|---|---|---|---|
| [`apps/pdf-to-json/`](../../apps/pdf-to-json/README.md) | PDF → OCS JSON 解析／轉換（`jd-convert` CLI），純離線批次、無狀態 | 是（`@caliburn/pdf-to-json`） | Python，per-app `uv` |
| [`apps/ocs-indexer/`](../../apps/ocs-indexer/README.md) | OCS JSON → Qdrant 索引（`jd-ocs-indexer index`）＋無狀態語意查詢 API（`jd-ocs-indexer serve`，:8000） | 是（`@caliburn/ocs-indexer`） | Python，per-app `uv` |
| [`apps/embedder/`](../../apps/embedder/README.md) | BGE-M3 dense+sparse embedding HTTP service（`POST /embed`、`GET /health`），GPU container | 否——沒有 `package.json`，只有 Dockerfile | Docker only |
| [`packages/ocs-contract/`](../../packages/ocs-contract/) | OCS JSON schema／生成的 Pydantic model／TypeScript type；`pdf-to-json` 與 `ocs-indexer` 共用 | 是（`@caliburn/ocs-contract`） | Python + codegen，per-app `uv`／npm scripts |
| [`packages/indexer-contract/`](../../packages/indexer-contract/) | indexer 查詢 API 的共用 pydantic wire model，為未來 `ocs-indexer ⇄` API consumer 保留的 seam | 否——沒有 `package.json`，Python-only | Python，per-app `uv` |

`ocs-contract`／`indexer-contract` 都以 `tool.uv.sources` path dependency（相對路徑、editable）供
`pdf-to-json`／`ocs-indexer` 使用，不是發佈到 registry 的套件。current 的 `apps/api`、`apps/web`、
`packages/job-analysis-contract` 完全不宣告對它們的依賴。

## 3. 本機指令

RAG 服務**不在** `npm run up`／`npm run dev` 的預設啟動範圍——那兩個指令只 filter `@caliburn/api`／
`@caliburn/web`。RAG 是明確 opt-in：

```bash
npm run rag:up      # docker compose --profile rag up -d（qdrant + embedder，GPU）
npm run rag:down    # docker compose --profile rag down
npm run rag:dev     # turbo dev --filter=@caliburn/ocs-indexer（查詢 API :8000）
```

各 app 也可獨立以自己的 uv project 執行測試，不需要 Compose／GPU：

```bash
cd apps/pdf-to-json && uv sync && uv run --extra dev pytest -q   # parser／transformer 測試
cd apps/ocs-indexer && uv sync --all-extras && uv run --all-extras pytest -q  # unit／contract 測試
```

要跑完整流程（PDF → 索引 → 查詢）才需要 `rag:up`（Qdrant + GPU embedder）：

```bash
npm run rag:up
cd apps/ocs-indexer && uv run jd-ocs-indexer index ./data/jd-json
cd apps/ocs-indexer && uv run jd-ocs-indexer serve --port 8000
```

`db`（current 產品用的 PostgreSQL）沒有 Compose profile，`docker compose up -d db` 或 `npm run up` 都會啟動
它；`qdrant`／`embedder` 都標記 `profiles: [rag]`，只有 `--profile rag`（或 `npm run rag:up`）會啟動它們。

## 4. 資料落地位置

| 資料 | 路徑 | 數量 |
|---|---|---|
| PDF corpus（來源） | `apps/pdf-to-json/data/pdfs/` | 908 |
| OCS JSON corpus（`pdf-to-json` 產出、`ocs-indexer` 消費） | `apps/ocs-indexer/data/jd-json/` | 908 |
| 向量索引 | Qdrant collection（預設 `ocs_v4`，見 `apps/ocs-indexer` 的 `QDRANT_COLLECTION`），落在 named volume `qdrant_storage`（`rag` profile 啟動時建立） | — |
| Embedding 模型快取 | named volume `hf_cache`（BAAI/bge-m3 權重，避免每次重抓） | — |

PDF 不只是測試 fixture，也是未來重新產生 OCS JSON 的來源材料。PostgreSQL（`pgdata` volume）只服務 current
`job_analysis` schema（migration 0012–0017）；RAG 資料流完全不寫入它。

## 5. 邊界不變量

- **current API/Web 不 import、不呼叫、不部署 RAG 程式碼**：`apps/api` 的 composition surfaces（`app/api`、
  `app/adapters`）與 `apps/web/src` 不得出現 `jd_ocs_indexer`、`jd_pdf_to_json`、`ocs_contract`、
  `indexer_contract` 或 `embedder` 的 import／依賴。API 側由
  `apps/api/tests/test_job_analysis_dependencies.py` 的 AST guard
  （`test_current_composition_does_not_import_removed_paths`）強制；Web 側目前沒有任何程式碼會 import
  它們（只吃 `@caliburn/job-analysis-contract`），以 `rg` 靜態掃描驗證。
- **RAG app 之間可以互相 import 對方的 contract**：`pdf-to-json`／`ocs-indexer` import `ocs-contract`，
  `ocs-indexer` 也 import `indexer-contract`，這是預期內的 bounded-context 內部依賴；guard 只掃 current API
  的 composition surfaces，不禁止這個方向，也不阻止 RAG app 之間或 RAG app 對自己 contract 的依賴。
- **`ocs-indexer` 的查詢 API（:8000）目前沒有任何 consumer**：它的 README 描述「供 apps/api 使用」是歷史／
  未來設計意圖，不是目前已接通的事實；`indexer-contract` 是為了那條未來 seam 保留的 wire model，在 current
  API 真的開始消費它之前，不會有任何 current 程式碼 import 它。
- **不做資料遷移或雙寫**：`job_analysis` 的 PostgreSQL Current State 與 RAG 的 PDF／OCS JSON／Qdrant 是兩套
  互不相通的資料世界。
- 若要讓 current API/Web 開始消費檢索結果，必須另開 ADR，明確定義 query contract、index freshness、
  embedding identity、failure fallback、API transaction 外的 provider 呼叫，以及 current JD
  provenance／evidence linkage；這份文件與 [ADR 0057](../adr/0057-current-only-runtime-and-data-boundary.md)
  都不是那個授權。

## 6. 相關文件

- [ADR 0057](../adr/0057-current-only-runtime-and-data-boundary.md) — current-only hard cut，Decision 5
  記錄 RAG 保留＋隔離。
- [`docs/specs/2026-08-11-rag-bounded-context-retention-design.md`](../specs/2026-08-11-rag-bounded-context-retention-design.md)
  — 恢復範圍、owner 裁決與研究來源。
- [`docs/plans/2026-08-11-rag-bounded-context-retention-plan.md`](../plans/2026-08-11-rag-bounded-context-retention-plan.md)
  — 逐 task 執行計畫與驗收條件。
- [`apps/pdf-to-json/README.md`](../../apps/pdf-to-json/README.md)、
  [`apps/ocs-indexer/README.md`](../../apps/ocs-indexer/README.md)、
  [`apps/embedder/README.md`](../../apps/embedder/README.md) — 各 app 內部指南。
