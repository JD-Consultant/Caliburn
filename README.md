# jd-ocs-indexer

`jd-ocs-indexer` 將 [jd-pdf-to-json](../jd-pdf-to-json/) 產出的 OCS（職能基準）JSON 轉成 schema-aware Markdown chunks，產生 embeddings，並寫入 Qdrant 向量資料庫。

目前決策版 v1 的責任邊界很明確：

```text
OCS JSON -> profile/unit/block Markdown chunks -> embeddings -> Qdrant storage
```

v1 **不提供正式查詢 API / RetrievalService / RAG answer engine**。本 repo 只保留 CLI 驗證查詢，用來確認 Qdrant 寫入、payload filter、point retrieve 正常。正式查詢服務與 RAG 組裝列為 v2 或上層應用。

> **目前狀態：設計與文件落地階段**。本 repo 尚未建立程式碼骨架，下一步依 [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) 實作。

---

## v1 目標

1. 讀取 `S:\jd-pdf-to-json\output\0518\*.json` 作為 source of truth。
2. 將每份 JSON 轉成三層 chunk：`profile`、`unit`、`block`。
3. 將每個 chunk render 成 Markdown，作為 embedding/text 投影；Markdown 不作切分來源。
4. 使用 embedding adapter 產生向量，預設 BGE-M3 dense + sparse。
5. 使用 direct Qdrant writer upsert points 與 payload indexes。
6. 提供 CLI smoke query 驗證：count、依 `ocs_code` retrieve、依 K/S code filter。

---

## 非 v1 範圍

- 不開 HTTP API。
- 不提供正式 Python 查詢 SDK。
- 不在 indexer 內產生 LLM 答案。
- 不用 LlamaParse 重抽 PDF 作正式資料來源。
- 不把 LlamaIndex `IngestionPipeline` 當 v1 主線。

LlamaParse 與 LlamaIndex 仍保留為 future adapter / 驗證工具：

- LlamaParse v2 可用於 PDF 重新解析、markdown/items 比對、抽取品質驗證。
- LlamaIndex 可在 v2 查詢層或 ingestion adapter 重新評估。

---

## 技術選型

| 層 | v1 決策 |
|---|---|
| Source of truth | `jd-pdf-to-json` 既有 JSON |
| Pipeline | 自訂 pipeline：Reader -> Builder -> Renderer -> Embedder -> QdrantWriter |
| Vector DB | Qdrant（本機 Docker 或後續 Cloud） |
| Collection | `ocs_bgem3_v1` |
| Embedding（主） | BGE-M3（dense 1024d + sparse lexical weights） |
| Embedding（備） | OpenAI dense-only、FastEmbed/BM25 adapter |
| Chunk 策略 | 三層：profile / unit / block（約 12,869 chunks） |
| 查詢 | v1 僅 CLI smoke query；v2 才規劃正式 retrieval |
| 套件管理 | uv |

不同 embedding provider 不混用同一個 collection；換 provider 或向量維度時建立新 collection。

---

## 設計文件

| 文件 | 內容 |
|---|---|
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | v1 決策總報告、模組架構、CLI、驗收標準 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 系統資料流、模組邊界、v1/v2 分期 |
| [docs/CHUNKING.md](docs/CHUNKING.md) | 三層 chunk 策略、Markdown 模板、邊界情況 |
| [docs/SCHEMA.md](docs/SCHEMA.md) | Qdrant collection、named vectors、payload 欄位與索引 |
| [docs/INGESTION.md](docs/INGESTION.md) | 自訂 ingestion pipeline、增量更新、CLI 規劃 |
| [docs/RETRIEVAL.md](docs/RETRIEVAL.md) | v2 retrieval 設計與 v1 smoke query 範圍 |

---

## 已知資料規模

依 `S:\jd-pdf-to-json\output\0518\` 實測：

- 908 份 JSON
- 3,272 個 `ocu_unit`
- 8,347 個 `task`
- 8,689 個 `competency_block`
- 預估 v1 chunks：908 profile + 3,272 unit + 8,689 block = 12,869 points
- 129 份 JSON 缺 version history
- 903 份 JSON 缺 `job_category`
- 53 個 task group 含多個 T-code

缺漏欄位不阻斷索引；由 schema 層以 nullable 或空陣列處理。

---

## 下一步

1. 建立 Python 專案骨架與 CLI。
2. 實作 OCS JSON Pydantic models 與 reader。
3. 實作三層 chunk builder 與 Markdown renderer。
4. 實作 Qdrant collection schema / payload indexes。
5. 實作 BGE-M3 embedding adapter 與 Qdrant writer。
6. 對 3 份 fixture 跑 end-to-end，再跑全量 908 份。

參考文件：

- LlamaParse: https://developers.llamaindex.ai/llamaparse/
- Qdrant overview: https://qdrant.tech/documentation/overview/
- Qdrant hybrid queries: https://qdrant.tech/documentation/search/hybrid-queries/
