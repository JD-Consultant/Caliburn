# RAG pipeline — PDF → OCS → indexer → embedder/Qdrant（保留、隔離的 bounded context）

> **現行狀態** ：RAG 是獨立檢索範圍。正式 JD App（`apps/api`、`apps/web`）已完成可選 HTTP consumer 接線，須明示設定才啟用；不是預設啟動依賴。
> `apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder`、`packages/ocs-contract`、`packages/indexer-contract`
> 保持獨立安裝、測試與執行；正式 App 不 import 這些 Python 套件，也不代為啟動 GPU 或 Qdrant。
> App 的 composition root 只在有設定時建立 HTTP client，公版選用及排除範圍由 App 保存。

## 1. 端到端資料流

現行公版參考流程分為三段：

1. **解析來源：** `pdf-to-json` 將 PDF 轉成 OCS JSON，正常輸出與拒絕診斷分開保存。
2. **建索引與查詢：** 操作者明示選定來源版本，以 `index-references` 建立獨立 document／task 索引。查詢經兩路廣蒐、完整聯集重排序及公版去重，回傳最多五份參考；模型計算由獨立 `embedder` 提供。
3. **按需使用：** 設定後的 JD App 經 HTTP 查詢公版，顧問再選主要參考、讀取任務及記錄員工明確否認的工作範圍。公版提供查漏線索，工作事實仍由員工訪談支持。

<details>
<summary>歷史：公版消費端接入前的 profile／task 管線</summary>

下圖保留當時的 908 檔 corpus。圖中的「沒有任何 consumer」描述當時狀態，不適用於已接線的職位整體參考 API。

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
現行產品邊界見 [正式產品與選型](../architecture/design-decisions.md)。

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
資料完整度須沿來源檢核，不能由檔案數推定。

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
  以 dependency metadata 與靜態掃描驗證；明示啟用的公版 HTTP client 由 App composition root 管理。
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
- 新增其他消費用途須核對資料責任、契約與驗收，不因 RAG 服務存在而自動啟用。

### 公版選用與明確否認的保存資格

App 分開保存選用公版及員工明確否認的工作範圍。選用值 `null` 表示尚未選擇，`[]` 表示已評估而無合適參考；選用工具替換整個集合，但保留排除範圍。搜尋故障不能當成空選擇。只有明確不做／不負責才可列入排除，未知、部分適用、未答或拒答不等於否認；員工更正時可解除原範圍。

候選只在 execution completed 且有匹配正式員工 exchange 後，才取得後輪採用資格；查詢固定上界 F 內、員工序號最新的合格 state。空集合仍可覆蓋舊選擇；未用工具的中間輪次不清空 state。B1／B2 沿持久批次的 F 讀排除範圍，後輪新增或解除不回流舊批次。

工具能力、格式與指引依原 captured request 接續；新設定不追補舊訪談或舊批次，已啟用的原請求缺少 client 時明確拒絕。原命令與結果沿既有 prepared／execute 及操作查回，不能因恢復而重選公版。

保存接線見[公版 workflow](../../apps/api/src/caliburn/workflows/occupation_references.py)與[固定 state 讀取](../../apps/api/src/caliburn/workflows/occupation_reference_reads.py)，wire 由[工具 Schema](../../apps/api/contracts/tools/)維護。

## 6. 相關文件

- [公版 API](../../apps/ocs-indexer/README.md)：查詢與固定來源讀取。
- [App 可選啟用](../../apps/api/README.md#公版參考工具的可選啟用)：設定與角色接線。
- [PDF 轉換](../../apps/pdf-to-json/README.md)、[模型服務](../../apps/embedder/README.md)：各 App 的操作與限制。
