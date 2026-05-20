# Architecture

`jd-ocs-indexer` v1 是索引與儲存工具，不是查詢服務。它讀取 `jd-pdf-to-json` 產出的 OCS JSON，依 schema 產生 Markdown chunks，產生 embeddings，並寫入 Qdrant。

```text
JSON -> Markdown chunks -> embeddings -> Qdrant storage
```

正式 retrieval service、HTTP API、RAG answer engine 都不在 v1 範圍內。v1 只保留 CLI smoke query，用來驗證索引結果。

---

## 1. 分期

| 階段 | 目標 | 狀態 |
|---|---|---|
| v1 | JSON 轉 chunks，embedding，Qdrant upsert，CLI 驗證 | 本期 |
| v2 | 正式 retrieval service、hybrid search、相似職務、RAG context | 未來 |
| v3 | HTTP API、UI、LLM answer engine、評測平台 | 未來 |

v1 的成功標準不是「能回答使用者問題」，而是「能穩定把 908 份 OCS JSON 轉成可被後續查詢系統使用的 Qdrant collection」。

---

## 2. 技術選型總覽

| 層 | v1 選擇 | 備註 |
|---|---|---|
| Source | `jd-pdf-to-json` 既有 JSON | `S:\jd-pdf-to-json\output\0518\*.json` |
| Pipeline | 自訂 pipeline | Reader -> Builder -> Renderer -> Embedder -> Writer |
| Vector DB | Qdrant | named dense/sparse vectors + payload indexes |
| Collection | `ocs_bgem3_v1` | provider/維度變更時建立新 collection |
| Embedding 主線 | BGE-M3 local | dense 1024 + sparse lexical weights |
| Embedding 備案 | OpenAI dense-only、FastEmbed/BM25 | adapter；不混同一 collection |
| Chunk | profile / unit / block | 邊界由 JSON schema 決定 |
| 查詢 | CLI smoke query only | 正式 retrieval 放 v2 |
| 套件管理 | uv | 與上游 Python 專案一致 |

### 為什麼 v1 不用 LlamaIndex IngestionPipeline

本案 v1 重點是資料轉換、payload schema、deterministic ids、source hash、Qdrant named vectors。直接用 `qdrant-client` 更容易控制：

- dense/sparse vector names 與 collection schema。
- nullable / empty-array payload。
- point id 與 chunk key。
- source hash 增量更新。
- 寫入失敗與重試策略。

LlamaIndex 可在 v2 retrieval 或 future ingestion adapter 重新評估，不作 v1 主線。

---

## 3. 系統資料流

```text
┌─────────────────────────────────────────┐
│ jd-pdf-to-json output/0518/*.json        │
│ source of truth                          │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ OCSJSONReader                            │
│ read file, validate Pydantic model, hash │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ OCSNodeBuilder                           │
│ emit profile/unit/block ChunkSpec        │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ MarkdownRenderer                         │
│ ChunkSpec -> human-readable MD text      │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ EmbeddingService                         │
│ BGE-M3 dense/sparse or adapter           │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ QdrantWriter                             │
│ create collection/indexes, upsert points │
└─────────────────────────────────────────┘

Validation only:
┌─────────────────────────────────────────┐
│ CLI smoke-query                          │
│ count / retrieve / payload filter        │
└─────────────────────────────────────────┘
```

Markdown 是 embedding text 的投影，不是切分依據。chunk 邊界一律由 `OCSNodeBuilder` 根據 JSON schema 產生。

---

## 4. 模組結構

```text
jd-ocs-indexer/
├── src/jd_ocs_indexer/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── models/
│   │   ├── ocs.py
│   │   └── chunk.py
│   ├── ingestion/
│   │   ├── reader.py
│   │   ├── builder.py
│   │   ├── renderer.py
│   │   └── manifest.py
│   ├── embeddings/
│   │   ├── base.py
│   │   ├── bge_m3.py
│   │   ├── openai_adapter.py
│   │   └── fastembed_adapter.py
│   ├── store/
│   │   ├── ids.py
│   │   ├── schema.py
│   │   ├── qdrant_client.py
│   │   └── writer.py
│   └── validation/
│       ├── stats.py
│       └── smoke_query.py
├── docs/
├── tests/
│   └── fixtures/
├── docker/
│   └── docker-compose.yml
├── pyproject.toml
└── README.md
```

### 模組責任

| 模組 | 責任 |
|---|---|
| `models/ocs.py` | 鏡像上游 JSON schema |
| `models/chunk.py` | ChunkSpec、payload model、vector-ready point model |
| `ingestion/reader.py` | 讀檔、Pydantic 驗證、canonical hash |
| `ingestion/builder.py` | 依 schema 產生 profile/unit/block chunks |
| `ingestion/renderer.py` | 將 chunks render 成 Markdown |
| `ingestion/manifest.py` | 記錄 source hash、indexed chunks、增量狀態 |
| `embeddings/*` | embedding provider adapters |
| `store/schema.py` | Qdrant collection 與 payload indexes |
| `store/writer.py` | batch upsert、retry、失敗記錄 |
| `validation/*` | stats、doctor、smoke-query |

---

## 5. CLI 邊界

v1 CLI 是操作入口，也是驗證工具：

```bash
uv run python -m jd_ocs_indexer.cli render <json_dir> -o output/md
uv run python -m jd_ocs_indexer.cli index <json_dir>
uv run python -m jd_ocs_indexer.cli stats <json_dir>
uv run python -m jd_ocs_indexer.cli stats --collection ocs_bgem3_v1
uv run python -m jd_ocs_indexer.cli doctor <json_dir>
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v1 --ocs-code INM3513-009v1
```

`smoke-query` 不承諾穩定輸出格式，不視為正式產品接口。

---

## 6. 部署形態

### 6.1 Qdrant

- POC：本機 Docker。
- Port：`6333` HTTP、`6334` gRPC。
- Data path：`./.data/qdrant`。
- Snapshot：未來可加入 `./.data/snapshots`。

### 6.2 Embedding

v1 預設 in-process BGE-M3。若本機資源不足，保留兩種切換方向：

- OpenAI dense-only adapter：簡化部署，但不支援 sparse。
- FastEmbed/BM25 adapter：較輕量，但中文與語意品質需實測。

### 6.3 LlamaParse

LlamaParse 不進 v1 ingestion。未來用途：

- PDF 重新解析。
- 與既有 JSON 比對。
- 用 `markdown` / `items` 驗證表格抽取品質。

---

## 7. 與 jd-pdf-to-json 的契約

- 唯一正式輸入是 JSON，不是 PDF。
- 本專案不要求上游改 schema。
- 上游缺漏欄位由 indexer schema 容忍：
  - 缺 version history：從 `ocs_code` 嘗試解析版本。
  - 缺 job category：寫空陣列。
  - multi-task group：完整保留 `task_codes`。
- 驗證失敗的檔案寫入 `failed_files.jsonl`，不中斷全量處理。

---

## 8. 風險與待解

| 風險 | 影響 | v1 處理 |
|---|---|---|
| BGE-M3 安裝/速度 | 全量索引時間增加 | 先支援小 fixture，再跑全量；保留 adapter |
| sparse 權重與 Qdrant IDF | 分數可能重複加權 | 預設不加 IDF；留評測比較 |
| 上游 JSON 缺漏 | payload 不完整 | nullable/empty array，不阻斷 |
| 沒有正式 query API | 上層無法直接用 | v1 只做 storage；v2 補 retrieval |
| collection schema 變更 | 需要重建 | provider/schema 升版建立新 collection |

---

## 9. 參考

- LlamaParse: https://developers.llamaindex.ai/llamaparse/
- Qdrant overview: https://qdrant.tech/documentation/overview/
- Qdrant hybrid queries: https://qdrant.tech/documentation/search/hybrid-queries/
