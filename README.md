# jd-ocs-indexer

`jd-ocs-indexer` 是 **JD Authoring RAG 的 OCS 索引建置器**。

它把 [jd-pdf-to-json](../jd-pdf-to-json/) 已產出的 OCS（職能基準）JSON 轉成 schema-aware Markdown chunks，產生 embeddings，並寫入 Qdrant。未來的 MCP server / HTTP API / JD 產生器會讀取這個 collection，但不放在本 repo。

```text
OCS JSON -> profile/unit/block Markdown chunks -> embeddings -> Qdrant storage
```

v1 **不提供正式查詢 API / MCP server tool / RAG answer engine**。本 repo 只保留 CLI smoke query，用來驗證 Qdrant 寫入、payload filter、point retrieve 正常。

> **目前狀態：設計與文件落地階段**。本 repo 尚未建立程式碼骨架，下一步依 [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) 實作。

---

## 產品定位

未來 RAG 的目標不是單純查詢 OCS，而是幫使用者撰寫自己的職務說明書：

```text
使用者描述自己的工作內容
  -> 找相似 OCS 職務 / 工作任務 / K/S
  -> 提示可能遺漏的工作內容
  -> 讓使用者確認或補充
  -> 產生專屬職務說明書
```

因此本 repo 要產出的不是一般文件索引，而是可以支援下列能力的 OCS knowledge index：

- 使用自然語言工作描述找候選職務。
- 從長段工作描述拆出多個活動後，分別命中相關 unit/block。
- 聚合 `ocs_code`、unit、K/S codes，供未來服務產生提示。
- 透過 `source_file` 回到完整 JSON，補足 JD 生成需要的背景資料。

---

## v1 目標

1. 讀取 `S:\jd-pdf-to-json\output\0518\*.json` 作為 source of truth。
2. 將每份 JSON 轉成三層 chunk：`profile`、`unit`、`block`。
3. 將每個 chunk render 成 Markdown，作為 embedding/text 投影；Markdown 不作切分來源。
4. 使用 embedding adapter 產生向量，預設 BGE-M3 dense + sparse。
5. 使用 direct Qdrant writer upsert points 與 payload indexes。
6. 提供 CLI smoke query 驗證：count、依 `ocs_code` retrieve、依 K/S code filter、dev-only vector probe。

---

## 非 v1 範圍

- 不開 HTTP API。
- 不開 MCP server。
- 不提供正式 Python 查詢 SDK。
- 不在 indexer 內產生 LLM 答案。
- 不處理使用者互動、遺漏提示、JD 草稿生成。
- 不處理 PDF 解析；PDF -> JSON 完全由 `jd-pdf-to-json` 負責。
- 不把 LlamaIndex `IngestionPipeline` 當 v1 主線。

正式 serving layer 建議另開 repo，例如 `jd-ocs-rag-service` 或 `jd-ocs-mcp`。該 repo 使用 `qdrant-client` 讀取本 repo 建好的 collection，並負責 query orchestration、完整 JSON context assembly、LLM prompt、MCP/API contract。

LlamaIndex 不列為必要依賴。若未來服務只是 deterministic tool/API，`qdrant-client` + 自訂 context assembler 會更可控；只有需要內建 chat engine、agent workflow、RAG evaluation 時才重新評估。

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
| 查詢 | v1 僅 CLI smoke query；正式 MCP/API/JD RAG 另 repo |
| 套件管理 | uv |

不同 embedding provider 不混用同一個 collection；換 provider 或向量維度時建立新 collection。

---

## 設計文件

| 文件 | 內容 |
|---|---|
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | v1 決策總報告、模組架構、CLI、驗收標準 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 系統資料流、repo 邊界、未來 JD Authoring RAG 契約 |
| [docs/CHUNKING.md](docs/CHUNKING.md) | 三層 chunk 策略、Markdown 模板、邊界情況 |
| [docs/SCHEMA.md](docs/SCHEMA.md) | Qdrant collection、named vectors、payload 欄位與索引 |
| [docs/INGESTION.md](docs/INGESTION.md) | 自訂 ingestion pipeline、增量更新、CLI 規劃 |
| [docs/RETRIEVAL.md](docs/RETRIEVAL.md) | 未來 JD Authoring RAG service 的查詢契約與 v1 smoke query |

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

- Qdrant overview: https://qdrant.tech/documentation/overview/
- Qdrant hybrid queries: https://qdrant.tech/documentation/search/hybrid-queries/
