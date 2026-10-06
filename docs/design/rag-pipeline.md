# RAG pipeline — PDF → OCS → indexer → embedder/Qdrant（保留、隔離的 bounded context）

> **現行狀態** ：RAG 是獨立檢索範圍。正式 JD App（`apps/api`、`apps/web`）已依 [ADR0080](../adr/0080-opt-in-public-reference-agent-tools.md)完成可選 HTTP consumer 接線，須明示設定才啟用；不是預設啟動依賴。
> `apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder`、`packages/ocs-contract`、`packages/indexer-contract`
> 保持獨立安裝、測試與執行；正式 App 不 import 這些 Python 套件，也不代為啟動 GPU 或 Qdrant。
> App 的 composition root 只在有設定時建立 HTTP client，公版選用及排除範圍由 App 保存。
>
> **沿革** ：[ADR 0057](../adr/0057-current-only-runtime-and-data-boundary.md) Decision 5（Proposed，2026-08-11 修正為保留＋隔離）與
> [`docs/specs/2026-08-11-rag-bounded-context-retention-design.md`](../specs/2026-08-11-rag-bounded-context-retention-design.md)。
> 這些文件保留當時未接消費端的取捨；現行接入權責依 ADR0080，查詢契約依[公版參考 API 設計](../specs/2026-10-05-occupation-reference-api-design.md)。

## 1. 端到端資料流

現行公版參考流程分為三段：

1. **解析來源：** `pdf-to-json` 將 PDF 轉成 OCS JSON，正常輸出與拒絕診斷分開保存。
2. **建索引與查詢：** 操作者明示選定來源版本，以 `index-references` 建立獨立 document／task 索引。查詢經兩路廣蒐、完整聯集重排序及公版去重，回傳最多五份參考；模型計算由獨立 `embedder` 提供。
3. **按需使用：** 設定後的 JD App 經 HTTP 查詢公版，顧問再選主要參考、讀取任務及記錄員工明確否認的工作範圍。公版提供查漏線索，工作事實仍由員工訪談支持。

<details>
<summary>歷史：公版消費端接入前的 profile／task 管線</summary>

下圖保留當時的 908 檔 corpus。圖中的「沒有任何 consumer」描述當時狀態，不適用於 ADR0080 接線後的職位整體參考 API。

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

</details>

`pdf-to-json` 只負責解析與轉換，不寫 JD App PostgreSQL；`ocs-indexer` 負責 ingest、模型 HTTP 呼叫與
Qdrant index/query，不 import 已退役的 `jd_relational`。`embedder` 提供 BGE-M3 embedding 與
BGE-reranker-v2-m3 配對評分，模型權重留在 GPU 容器，不進正式 App process。

## 2. Package 與 app 責任

| 路徑 | 職責 | pnpm workspace 成員 | 語言／管理 |
|---|---|---|---|
| [`apps/pdf-to-json/`](../../apps/pdf-to-json/README.md) | PDF → OCS JSON 解析／轉換（`jd-convert` CLI），純離線批次、無狀態 | 是（`@caliburn/pdf-to-json`） | Python，per-app `uv` |
| [`apps/ocs-indexer/`](../../apps/ocs-indexer/README.md) | OCS JSON → Qdrant 索引：`index-references` 建新公版參考索引，`jd-ocs-indexer index` 保留既有索引；無狀態 API 由 `jd-ocs-indexer serve` 提供（:8000） | 是（`@caliburn/ocs-indexer`） | Python，per-app `uv` |
| [`apps/embedder/`](../../apps/embedder/README.md) | BGE-M3 dense+sparse embedding 與 BGE-reranker-v2-m3 配對評分（`POST /embed`、`POST /rerank`、`GET /health`），GPU container | 否——沒有 `package.json`，只有 Dockerfile | Docker only |
| [`packages/ocs-contract/`](../../packages/ocs-contract/) | OCS JSON schema／生成的 Pydantic model／TypeScript type；`pdf-to-json` 與 `ocs-indexer` 共用 | 是（`@caliburn/ocs-contract`） | Python + codegen，per-app `uv`／pnpm scripts |
| [`packages/indexer-contract/`](../../packages/indexer-contract/) | indexer 查詢 API 的 Pydantic wire model，供 producer 驗證 request／response，包含新公版參考 API 的格式 | 否——沒有 `package.json`，Python-only | Python，per-app `uv` |

`ocs-contract`／`indexer-contract` 都以 `tool.uv.sources` path dependency（相對路徑、editable）供
`pdf-to-json`／`ocs-indexer` 使用，不是發佈到 registry 的套件。正式 App 不直接依賴這些 Python 套件，
由自己的 adapter 驗證公版 HTTP 邊界。舊 `jd-relational-app` 與 `packages/consultant-memory` 已退役，
現行產品邊界見 [ADR0079](../adr/0079-target-rebuild-production-cutover.md)。

## 3. 本機指令

RAG 服務**不在** `pnpm dev`／`pnpm start` 的預設啟動範圍；它是明確 opt-in：

```bash
pnpm rag:up      # docker compose --profile rag up -d（qdrant + embedder，GPU）
pnpm rag:down    # docker compose stop qdrant embedder
pnpm rag:dev     # 啟動 ocs-indexer 查詢 API（:8000）
```

各 app 也可獨立以自己的 uv project 執行測試，不需要 Compose／GPU：

```bash
cd apps/pdf-to-json && uv sync && uv run --extra dev pytest -q   # parser／transformer 測試
cd apps/ocs-indexer && uv sync --all-extras && uv run --all-extras pytest -q  # unit／contract 測試
```

實際建索引與查詢需要 `rag:up`（Qdrant + GPU embedder）。以下命令沿用既有 profile／task 索引；
新公版參考索引的選版與 `REFERENCE_COLLECTION` 設定見 [indexer README](../../apps/ocs-indexer/README.md#職位整體參考-api)：

```bash
pnpm rag:up
cd apps/ocs-indexer && uv run jd-ocs-indexer index ./data/jd-json
cd apps/ocs-indexer && uv run jd-ocs-indexer serve --port 8000
```

根目錄 Compose 不提供 JD App PostgreSQL。`qdrant`／`embedder` 都標記 `profiles: [rag]`，只有
`--profile rag`（或 `pnpm rag:up`）會啟動它們。

啟動 RAG 不會自動替 JD App 開啟工具。App 端須另設定 URL 與 timeout，步驟見[後端可選啟用](../../apps/api/README.md#公版參考工具的可選啟用)；使用前須讓欲啟用的 App 程序載入設定。

Docker 公版模式使用 `compose.jd-app.rag.yaml`，以 `pnpm docker:rag:up` 一併啟動既有 App／PostgreSQL 與三個獨立 RAG 服務。延伸配置會設定 App 的內網 URL，但 App 程序不管理 RAG 容器；預設基本模式也不啟動 RAG。模型與 Qdrant 設定重用根 `docker-compose.yml`，查詢 API 依自己的 lockfile 獨立建置。來源選版、建索引、停止、volume 與驗證範圍見[公版 Docker 操作](../runbook.md#含公版參考的-docker-模式)。

## 4. 資料落地位置

下表保留原 corpus 與既有 profile／task 索引的位置及數量，不能當作本次已選版或已通過解析的統計。
後續補齊結果見[JSON 補齊紀錄](../experiments/2026-10-04-ocs-json-repair/README.md)。

| 資料 | 路徑 | 數量 |
|---|---|---|
| PDF corpus（來源） | `apps/pdf-to-json/data/pdfs/` | 908 |
| OCS JSON corpus（`pdf-to-json` 產出、`ocs-indexer` 消費） | `apps/ocs-indexer/data/jd-json/` | 908 |
| 向量索引 | Qdrant collection（預設 `ocs_v4`，見 `apps/ocs-indexer` 的 `QDRANT_COLLECTION`），落在 named volume `qdrant_storage`（`rag` profile 啟動時建立） | — |
| Embedding 模型快取 | named volume `hf_cache`（BAAI/bge-m3 權重，避免每次重抓） | — |

PDF 不只是測試 fixture，也是未來重新產生 OCS JSON 的來源材料。RAG 資料流完全不寫入正式 JD App 的
PostgreSQL；JD App 的資料庫也不由本 Compose 建立。

新公版參考索引使用操作者選定的 JSON 目錄及獨立 collection，由 `REFERENCE_COLLECTION` 指定。
來源 hash 綁定公版身分，完整寫入後才發布 ready manifest；更新來源須建立新 collection，不能覆寫既有索引或在讀取時代換新版。

## 5. 邊界不變量

- **正式 JD App 不 import 或部署 RAG 程式碼：** `apps/api/src/caliburn` 與 `apps/web/src`
  不直接依賴 `jd_ocs_indexer`、`jd_pdf_to_json`、`ocs_contract`、`indexer_contract` 或 `embedder` 套件。
  以 dependency metadata 與靜態掃描驗證；明示啟用的公版 HTTP client 依 ADR0080 管理。
- **RAG app 之間可以互相 import 對方的 contract** ：`pdf-to-json`／`ocs-indexer` import `ocs-contract`，
  `ocs-indexer` 也 import `indexer-contract`，這是預期內的 bounded-context 內部依賴；guard 只掃 current API
  的 composition surfaces，不禁止這個方向，也不阻止 RAG app 之間或 RAG app 對自己 contract 的依賴。
- **API 與進度各有 owner：** `ocs-indexer` 的職位整體參考 API（:8000）提供來源與搜尋結果，
  `indexer-contract` 定義 producer 的 wire model；App 保存選用公版與明確否認範圍，不交給 RAG 保存。
  既有 profile／task API 的退役消費端不因新接線而復活。
- **不做資料遷移或雙寫：** 正式 App 的 PostgreSQL 與 RAG 的 PDF／OCS JSON／Qdrant 各自保存資料。
  公版正文不複製成 Memory／JD 工作事實；查詢正文只使用員工確認的實際工作，排除範圍另行保存與讀取。
- **故障不能當查無資料：** 索引未 ready、模型身分不相容或連線失敗皆回明確錯誤，不以空結果代替，
  也不清除 App 的選用 state。
- 現行 consumer 權責依 ADR0080。新增其他消費用途仍循決策流程；本檔與歷史的 [ADR 0057](../adr/0057-current-only-runtime-and-data-boundary.md)
  不提供額外施工授權。

## 6. 相關文件

- [ADR0080](../adr/0080-opt-in-public-reference-agent-tools.md) — 現行可選 HTTP consumer、工具生命週期與啟用權責。
- [公版參考 API 設計](../specs/2026-10-05-occupation-reference-api-design.md)與[公版工具契約](../specs/2026-10-04-public-reference-completion-design.md) — 查詢、來源讀取、App state 與角色工具。
- [ADR 0057](../adr/0057-current-only-runtime-and-data-boundary.md) — 歷史 Proposed 討論稿；Decision 5 記錄當時 RAG 保留＋隔離的取捨。
- [`docs/specs/2026-08-11-rag-bounded-context-retention-design.md`](../specs/2026-08-11-rag-bounded-context-retention-design.md)
  — 恢復範圍、隔離原則與研究來源。
- [`docs/plans/2026-08-11-rag-bounded-context-retention-plan.md`](../history.md#source-0f1ee13f53bc33d4050e)
  — 逐 task 執行計畫與驗收條件。
- [`apps/pdf-to-json/README.md`](../../apps/pdf-to-json/README.md)、
  [`apps/ocs-indexer/README.md`](../../apps/ocs-indexer/README.md)、
  [`apps/embedder/README.md`](../../apps/embedder/README.md) — 各 app 內部指南。
