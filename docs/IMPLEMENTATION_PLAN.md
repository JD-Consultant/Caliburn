# Implementation Plan

本文件是 `jd-ocs-indexer` 的實作決策版。目標是讓實作者可直接建立 v1 程式骨架，並產出可供未來 JD Authoring RAG service 使用的 Qdrant collection。

---

## 1. Summary

v1 只負責索引與儲存：

```text
S:\jd-pdf-to-json\output\0518\*.json
    -> OCSJSONReader
    -> OCSNormalizer
    -> ChunkBuilder
    -> MarkdownRenderer
    -> EmbeddingService
    -> QdrantWriter
    -> Qdrant collection ocs_bgem3_v1
```

本 repo 不提供正式查詢服務、不開 HTTP API、不開 MCP server、不在 indexer 內產生 LLM 回答。CLI 只提供 smoke query，用來驗證寫入後的資料能被 count、retrieve、filter、dev-only vector probe。

未來 JD Authoring RAG 應另開 service repo，讀取本 repo 建好的 Qdrant collection，負責長工作描述拆項、候選職務聚合、遺漏工作提示、完整 JSON context assembly、LLM JD draft。

---

## 2. Product Context

未來產品流程：

```text
使用者描述自己的工作內容
  -> RAG 找出可能相關的 OCS 職務 / unit / block / K/S
  -> 系統提示使用者可能遺漏的工作任務
  -> 使用者確認、刪除、補充
  -> 產生專屬職務說明書
```

這代表 indexer 的 v1 設計重點不是一般文件問答，而是：

- 能用自然語言工作活動命中 OCS unit/block。
- 能聚合 `ocs_code`、unit、K/S codes。
- 能用 parent chunk 補小到大的上下文。
- 能用 `source_file` 讀回完整 JSON，支援 JD 生成背景資料。

---

## 3. Scope

### v1 要做

- 讀取 `jd-pdf-to-json` 的既有 JSON。
- 驗證與 normalize JSON schema，容忍已知缺漏欄位。
- 產生三層 chunks：
  - `profile`: 每份 OCS 一個。
  - `unit`: 每個 `ocu_unit` 一個。
  - `block`: 每個 `competency_block` 一個。
- Render Markdown 作為 embedding text 與未來 LLM context。
- 產生 deterministic point id 與完整 payload。
- 建立 Qdrant collection 與 payload indexes。
- Upsert dense/sparse vectors 與 payload。
- 支援增量索引：source hash 未變則跳過。
- 提供 CLI：`render`、`index`、`stats`、`doctor`、`smoke-query`。

### v1 不做

- 不從 PDF 重抽資料。
- 不提供正式 retrieval API。
- 不提供 HTTP server。
- 不提供 MCP server。
- 不實作長工作描述拆項。
- 不實作遺漏任務提示。
- 不實作 LLM answer / JD generation。
- 不用 LlamaIndex `IngestionPipeline` 作主線。

---

## 4. Architecture

### 4.1 模組結構

```text
src/jd_ocs_indexer/
  cli.py
  config.py
  models/
    ocs.py
    chunk.py
  ingestion/
    reader.py
    normalizer.py
    builder.py
    renderer.py
    manifest.py
  embeddings/
    base.py
    bge_m3.py
    openai_adapter.py
    fastembed_adapter.py
  store/
    schema.py
    ids.py
    qdrant_client.py
    writer.py
  validation/
    stats.py
    smoke_query.py
```

不在本 repo 建立 `serving/`、`api/`、`mcp/`、`rag/` 模組。

### 4.2 Data flow

```text
JSON file
  -> OCSDocument
  -> NormalizedOCSDocument
  -> ChunkRecord[]
  -> Markdown text + payload
  -> EmbeddedChunk[]
  -> Qdrant PointStruct
```

概念命名：

```text
ChunkRecord:
  chunk_key
  chunk_level
  text
  payload

EmbeddedChunk:
  ChunkRecord + dense_vector + sparse_vector?

Qdrant point:
  id + vectors + payload
```

### 4.3 Direct Qdrant writer

v1 直接使用 `qdrant-client` 建 collection、建 payload indexes、upsert points。這比先接 LlamaIndex 更符合本案需求，原因是：

- 需要精準控制 named vectors：`dense` / `sparse`。
- 需要精準控制 payload 欄位、nullable、empty arrays。
- 需要 deterministic point id。
- 需要 relative source path、source hash、chunk content hash。
- v1 是 storage/indexer，不是 retriever framework。

---

## 5. Source Data

正式輸入：

```text
S:\jd-pdf-to-json\output\0518\*.json
```

payload 不寫絕對路徑，改寫相對於 source root 的路徑：

```json
{
  "source_root_alias": "jd-pdf-to-json",
  "source_file": "output/0518/example.json"
}
```

實際 root 由 config/env 管理：

```text
OCS_SOURCE_ROOT=S:/jd-pdf-to-json
```

實測資料：

- 908 files
- 3,272 units
- 8,347 tasks
- 8,689 blocks
- 129 files missing version history
- 903 files missing job category
- 53 multi-task groups

---

## 6. Chunk Keys

```text
profile: ocs:{ocs_code}:profile
unit:    ocs:{ocs_code}:unit:{unit_key}
block:   ocs:{ocs_code}:unit:{unit_key}:task:{primary_task_key}:block:{block_key}
```

規則：

- 若 JSON 有穩定代碼，沿用原代碼作 `unit_key` / `task_key`。
- 若缺穩定代碼，用 zero-padded index fallback，例如 `0001`。
- 多 task group 時，`primary_task_key = sorted(task_keys)[0]`，完整 `task_keys` 仍寫入 payload。
- Qdrant point id 用 `uuid5(namespace, chunk_key)`，`chunk_key` 本身存 payload。

Markdown dump 檔名將 `:` 替換為 `_` 或使用 URL-safe sanitizer，避免 Windows 檔名限制。

---

## 7. Payload Contract

完整欄位定義見 [SCHEMA.md](./SCHEMA.md)。v1 payload 的核心規則：

Required：

- `chunk_key`
- `chunk_level`
- `ocs_code`
- `job_title`
- `text`
- `source_root_alias`
- `source_file`
- `source_json_hash`
- `chunk_content_hash`
- `schema_version`
- `embedding_provider`
- `indexed_at`

Nullable：

- `job_category`
- `version`
- `version_seq`
- `update_date`
- `unit_id`
- `unit_title`
- `block_id`
- `block_title`
- `competency_level`
- `profile_chunk_id`
- `unit_chunk_id`

Empty array default：

- `task_ids`
- `task_titles`
- `k_codes`
- `s_codes`
- `attitude_codes`
- `industry_codes`
- `occupation_codes`
- `knowledge_terms`
- `skill_terms`
- `work_activity_terms`

Trace fields：

- `source_path`
- `source_labels`
- `unit_order`
- `task_orders`
- `block_order`

`T1`、`T1.1`、`P1.1.1`、`O1.1.1` 這類代碼不作主要搜尋入口，但應保留在 `source_labels` 或 code arrays 中，供 citation、排序、debug、回溯原始 JSON 使用。

---

## 8. Embedding and Qdrant

### 8.1 v1 default

- Collection: `ocs_bgem3_v1`
- Dense vector:
  - name: `dense`
  - size: 1024
  - distance: cosine
- Sparse vector:
  - name: `sparse`
  - source: BGE-M3 lexical_weights
  - distance: dot product
  - 不加 Qdrant `Modifier.IDF`

預設不啟用 ColBERT multi-vector。若後續 retrieval 品質不足，再以新 collection 重新評估。

### 8.2 Provider options

| Provider | 優點 | 缺點 | v1 建議 |
|---|---|---|---|
| BGE-M3 local | 中文與代碼/術語混合友善，可 dense+sparse 離線 | 依賴較重，CPU 較慢 | 預設 |
| OpenAI dense-only | 部署簡單，品質穩，支援降維 | 成本、API key、無 sparse | adapter |
| FastEmbed/BM25 | Qdrant 生態整合順 | 語意與中文效果需實測 | adapter/PoC |

不同 provider 或不同維度都不混同一 collection；換 provider 或調維度即建立新 collection。

### 8.3 Payload indexes

只對常用 filter 欄位建立 payload index：

- `chunk_level`
- `ocs_code`
- `ocs_code_base`
- `job_title`
- `job_category`
- `version`
- `is_current`
- `unit_id`
- `task_ids`
- `k_codes`
- `s_codes`
- `attitude_codes`
- `industry_codes`
- `occupation_codes`
- `schema_version`
- `embedding_provider`

不建 index 但保留：`source_file`、`source_json_hash`、`chunk_content_hash`、`source_path`、`source_labels`、各種 title/name、order 欄位。

---

## 9. CLI

### `render`

```bash
uv run python -m jd_ocs_indexer.cli render S:\jd-pdf-to-json\output\0518 -o output\md
```

只讀 JSON 並輸出 Markdown，不連 Qdrant。

### `index`

```bash
uv run python -m jd_ocs_indexer.cli index S:\jd-pdf-to-json\output\0518
```

執行完整 pipeline，依 `source_json_hash` 跳過未變檔案。

### `stats`

```bash
uv run python -m jd_ocs_indexer.cli stats S:\jd-pdf-to-json\output\0518
uv run python -m jd_ocs_indexer.cli stats --collection ocs_bgem3_v1
```

統計來源資料或 Qdrant collection。

### `doctor`

```bash
uv run python -m jd_ocs_indexer.cli doctor S:\jd-pdf-to-json\output\0518
```

檢查缺 version、缺 category、zero block、multi-task group、空 attitudes 等。

### `smoke-query`

```bash
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v1 --ocs-code INM3513-009v1
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v1 --knowledge K01 --skill S01
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v1 --probe-vector "資料清理 報表 需求確認"
```

僅用於驗證索引，不視為正式查詢接口。輸出格式不作穩定 API 承諾。

---

## 10. Future Service Contract

未來 service repo 應使用本 repo 產出的 payload contract 做：

```text
match_user_work_description()
suggest_candidate_jobs()
match_user_activities()
suggest_missing_work_tasks()
suggest_knowledge_skills()
assemble_jd_context()
draft_job_description()
```

典型查詢策略：

```text
whole user description -> search profile/unit
extracted activities -> search unit/block per activity
hits -> group by ocs_code and unit_id
high confidence ocs_code -> load full JSON via source_file
block hits -> retrieve unit/profile chunks via parent ids when small context is enough
```

---

## 11. Acceptance Criteria

- `README.md` 清楚描述本 repo 做什麼與不做什麼。
- `ARCHITECTURE.md` 清楚切分 indexer repo 與 future JD Authoring RAG service。
- `SCHEMA.md` 足以直接實作 Qdrant payload 與 indexes。
- 文件不再把正式查詢服務 / MCP / API 寫成本 repo v1 目標。
- `render` 能對 fixture JSON 產出 profile/unit/block Markdown。
- `doctor` 能回報已知資料缺漏，不把缺 version/job_category 視為 fatal。
- `index` 對 fixture 可建立 Qdrant collection 並 upsert points。
- 重跑 `index` 對未變檔案會 skip。
- `smoke-query` 可驗證 count、retrieve by `ocs_code`、filter by K/S code。
- `smoke-query --probe-vector` 可驗證 dense/sparse 寫入路徑。

---

## 12. References

- Qdrant overview: https://qdrant.tech/documentation/overview/
- Qdrant hybrid queries: https://qdrant.tech/documentation/search/hybrid-queries/
