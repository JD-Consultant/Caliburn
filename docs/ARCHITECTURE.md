# Architecture

`jd-ocs-indexer` 是 JD Authoring RAG 的索引建置器。它讀取 [jd-pdf-to-json](../../jd-pdf-to-json/) 輸出的 OCS JSON，產生 profile / unit / block 三層 Markdown chunks，建立 embeddings，並寫入 Qdrant。

本 repo 不做 MCP server、HTTP API、使用者互動，也不產生職務說明書。它的交付物是穩定的 Qdrant collection、payload schema、source trace 與 smoke query。

相關文件：

- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) - v1 實作計畫、模組、CLI、驗收標準
- [CHUNKING.md](./CHUNKING.md) - 三層 chunk 策略與 Markdown 投影
- [SCHEMA.md](./SCHEMA.md) - Qdrant collection、payload、payload indexes
- [INGESTION.md](./INGESTION.md) - ingestion pipeline、增量更新、CLI
- [RETRIEVAL.md](./RETRIEVAL.md) - 未來 JD Authoring RAG service 查詢契約

---

## 1. Repository Boundary

### This repo: `jd-ocs-indexer`

```text
S:\jd-pdf-to-json\output\0518\*.json
  -> validate / normalize
  -> build profile / unit / block chunks
  -> render Markdown text
  -> embed
  -> upsert Qdrant
  -> smoke query validation
```

責任：

- 保留 OCS JSON 的結構邊界，不做通用 token splitter。
- 產生適合自然語言工作描述搜尋的 Markdown chunk text。
- 產生可 filter、group、trace、parent expand 的 metadata。
- 確保每個 chunk 都能透過 `source_file` 回到完整 JSON。
- 建立 payload indexes，支援未來服務快速 filter。

### Future repo: JD Authoring RAG service

建議另開 repo，例如 `jd-ocs-rag-service` 或 `jd-ocs-mcp`：

```text
user work description
  -> activity extraction
  -> Qdrant search / filter
  -> group by ocs_code / unit / K/S
  -> load full source JSON when needed
  -> assemble JD authoring context
  -> ask confirmation questions
  -> draft custom job description
```

該服務應以 read-only Qdrant client 使用本 repo 建好的 collection。它可以暴露 MCP tools、HTTP API 或 LLM workflow，但不應反過來改寫 indexer 的資料。

---

## 2. v1 Scope

| 範疇 | v1 indexer | future service |
|---|---:|---:|
| OCS JSON -> chunks | yes | no |
| chunk -> Markdown | yes | no |
| Markdown -> embedding | yes | no |
| 寫入 Qdrant + payload index | yes | no |
| 增量更新 manifest | yes | no |
| Smoke query CLI | yes | no |
| 正式 retrieval API / SDK | no | yes |
| MCP server / HTTP API | no | yes |
| 長工作描述拆項 | no | yes |
| 遺漏工作任務提示 | no | yes |
| 完整 JSON context assembly | no | yes |
| LLM JD draft generation | no | yes |

---

## 3. Architecture Decisions

| 層 | 決策 |
|---|---|
| Source of truth | `jd-pdf-to-json` 既有 JSON |
| Pipeline | 自訂 Reader -> Builder -> Renderer -> Embedder -> Writer |
| Vector DB | Qdrant |
| Collection | `ocs_bgem3_v1` |
| Embedding default | BGE-M3 dense 1024 + sparse lexical weights |
| Chunk boundary | JSON schema 決定，不由 Markdown 或 token splitter 決定 |
| Text projection | Markdown，直接可作 LLM context |
| Qdrant client | direct `qdrant-client` |
| Full JSON | 不塞入 Qdrant payload，透過 `source_file` 回讀 |
| Parent context | 用 `profile_chunk_id` / `unit_chunk_id` 快速補上下文 |
| LlamaIndex | v1 不使用；future service 也先以自訂 service + `qdrant-client` 為主 |

### 為什麼 direct Qdrant

本案需要精準控制：

- named vectors：`dense` / `sparse`
- deterministic point id
- payload required / nullable / empty array 規則
- relative source path + source hash
- payload indexes
- parent chunk id 與 source trace

這些都是 indexer 的核心契約，用 direct `qdrant-client` 最清楚。

---

## 4. Data Flow

```text
   jd-pdf-to-json output/0518/*.json
                |
                v
   OCSJSONReader
     - parse JSON
     - canonical sha256
     - relative source_file
                |
                v
   OCSNormalizer
     - nullable / empty array rules
     - version fallback from ocs_code
     - stable order fields
                |
                v
   ChunkBuilder
     - profile chunk x 1
     - unit chunks x N
     - block chunks x N
     - chunk_key, parent ids, source path
                |
                v
   MarkdownRenderer
     - LLM-friendly text
     - work activity / knowledge / skill language
                |
                v
   EmbeddingService
     - dense vector
     - sparse vector when provider supports it
                |
                v
   QdrantWriter
     - ensure collection
     - ensure payload indexes
     - batch upsert points
                |
                v
   Qdrant collection: ocs_bgem3_v1
```

增量索引：

```text
source_json_hash unchanged -> skip file
source_json_hash changed -> rebuild chunks for file
chunk_content_hash unchanged -> may skip re-embedding in later optimization
upsert OK -> update local manifest
```

---

## 5. Chunk Strategy for JD Authoring

三層不是三選一，而是同一份 JSON 產生三種搜尋粒度：

| chunk_level | 用途 | future service 常見用法 |
|---|---|---|
| `profile` | 找候選職務、職務總覽、相似職務 | 使用者說職務名稱或長描述時，先找可能的 `ocs_code` |
| `unit` | 找主要工作任務 / 職能單元 | 提示「你是否也會做這些同組任務」 |
| `block` | 找具體能力、K/S、行為證據 | 從使用者活動命中具體工作內容與 K/S |

長工作描述不應只搜尋一次。future service 應：

```text
whole description -> search profile/unit for candidate jobs
extracted activities -> search unit/block per activity
hits -> group by ocs_code, unit, K/S
top ocs_code -> load full JSON when drafting JD
```

---

## 6. Metadata Strategy

每個 chunk 寫成一個 Qdrant point：

```text
Qdrant point = id + vectors + payload
chunk = logical unit = text + metadata + source trace
```

payload 欄位分三類：

| 類別 | 用途 | 例子 |
|---|---|---|
| query metadata | filter / group / ranking | `chunk_level`, `ocs_code`, `job_title`, `k_codes`, `s_codes` |
| context metadata | 搜尋結果顯示與 parent expansion | `unit_title`, `task_titles`, `profile_chunk_id`, `unit_chunk_id` |
| trace metadata | 回溯完整 JSON、debug、增量更新 | `source_file`, `source_json_hash`, `chunk_content_hash`, `source_path`, `source_labels` |

`source_file` 和 parent chunk id 不是重複欄位：

- `source_file`：回到完整 JSON，適合 JD 生成前組完整 context。
- `profile_chunk_id` / `unit_chunk_id`：在 Qdrant 內快速拿已 render 好的 parent Markdown，適合 small-to-big context。

---

## 7. Planned Module Structure

```text
jd-ocs-indexer/
├── src/jd_ocs_indexer/
│   ├── cli.py
│   ├── config.py
│   ├── models/
│   │   ├── ocs.py
│   │   └── chunk.py
│   ├── ingestion/
│   │   ├── reader.py
│   │   ├── normalizer.py
│   │   ├── builder.py
│   │   ├── renderer.py
│   │   └── manifest.py
│   ├── embeddings/
│   │   ├── base.py
│   │   ├── bge_m3.py
│   │   ├── openai_adapter.py
│   │   └── fastembed_adapter.py
│   ├── store/
│   │   ├── qdrant_client.py
│   │   ├── schema.py
│   │   ├── ids.py
│   │   └── writer.py
│   └── validation/
│       ├── stats.py
│       └── smoke_query.py
├── docs/
├── tests/
│   └── fixtures/
├── docker/
│   └── docker-compose.yml
├── .data/
├── pyproject.toml
└── README.md
```

本 repo 不新增 `serving/`、`api/`、`mcp/`、`rag/` 模組。

---

## 8. Deployment Shape

### Qdrant

- 開發 / POC：本機 Docker，`6333` / `6334`
- Collection：`ocs_bgem3_v1`
- Payload indexes：只建常用 filter 欄位
- Snapshot：正式化後再加備份流程

### Embedding

- 預設：BGE-M3 local
- 備案：OpenAI dense-only、FastEmbed/BM25 adapter
- 不同 provider / 維度不可混同一 collection

### Source root

payload 只存相對路徑：

```json
{
  "source_root_alias": "jd-pdf-to-json",
  "source_file": "output/0518/example.json"
}
```

實際 root 由 config/env 管理，例如：

```text
OCS_SOURCE_ROOT=S:/jd-pdf-to-json
```

---

## 9. Out of Scope

- PDF parsing
- MCP server
- HTTP API
- Web UI
- LLM prompt orchestration
- JD draft generation
- 使用者確認流程
- 多租戶權限模型

---

## 10. Risks

| 風險 | 嚴重度 | 緩解 |
|---|---|---|
| BGE-M3 sparse lexical weights 與 Qdrant sparse vector 寫入細節 | 中 | `smoke-query --probe-vector` 驗證；必要時先 dense-only |
| `job_category` 大量缺失 | 低 | empty array，不作 fatal |
| version history 缺失 | 低 | 從 `ocs_code` 尾端 `vN` 推導，失敗則 nullable |
| multi-task group 導致 chunk key 漂移 | 低 | `primary_task_key = sorted(task_keys)[0]` |
| future service 需要完整 JSON | 中 | 每個 chunk 必存 relative `source_file` + `source_json_hash` |
| metadata 欄位太多造成 index 過重 | 低 | payload 可多存，但只對常用 filter 欄位建 index |
