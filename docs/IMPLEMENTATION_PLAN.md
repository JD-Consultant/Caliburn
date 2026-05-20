# Implementation Plan

本文件是 `jd-ocs-indexer` 的實作決策版。目標是讓實作者不需要再重新判斷架構邊界，就能直接建立 v1 程式骨架。

---

## 1. Summary

v1 只負責索引與儲存：

```text
S:\jd-pdf-to-json\output\0518\*.json
    -> OCSJSONReader
    -> OCSNodeBuilder
    -> MarkdownRenderer
    -> EmbeddingService
    -> QdrantWriter
    -> Qdrant collection ocs_bgem3_v1
```

v1 不提供正式查詢服務，不開 HTTP API，不在 indexer 內產生 LLM 回答。CLI 只提供 smoke query，用來驗證寫入後的資料能被 count、retrieve、filter。

v2 才處理正式 retrieval service、相似職務、hybrid search、small-to-big context、RAG answer engine。

---

## 2. Scope

### v1 要做

- 讀取 `jd-pdf-to-json` 的既有 JSON。
- 驗證 JSON schema，容忍已知缺漏欄位。
- 產生三層 chunks：
  - `profile`: 每份 OCS 一個。
  - `unit`: 每個 `ocu_unit` 一個。
  - `block`: 每個 `competency_block` 一個。
- Render Markdown 作為 embedding text。
- 產生 deterministic point id 與 payload。
- 建立 Qdrant collection 與 payload indexes。
- Upsert dense/sparse vectors 與 payload。
- 支援增量索引：source hash 未變則跳過。
- 提供 CLI：
  - `render`
  - `index`
  - `stats`
  - `doctor`
  - `smoke-query`

### v1 不做

- 不從 PDF 重抽資料。
- 不用 LlamaParse 當正式來源。
- 不提供正式 retrieval API。
- 不提供 HTTP server。
- 不實作 LLM answer generation。
- 不用 LlamaIndex `IngestionPipeline` 作主線。

---

## 3. Architecture

### 3.1 模組結構

```text
src/jd_ocs_indexer/
  cli.py
  config.py
  models/
    ocs.py
    chunk.py
  ingestion/
    reader.py
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

### 3.2 Data flow

```text
JSON file
  -> OCSDocument
  -> ChunkSpec[]
  -> Markdown text + payload
  -> dense/sparse vectors
  -> Qdrant PointStruct
```

`MarkdownRenderer` 只負責 text projection；chunk 邊界由 JSON schema 決定，不由 Markdown headings 或 token splitter 決定。

### 3.3 Direct Qdrant writer

v1 直接使用 `qdrant-client` 建 collection、建 payload indexes、upsert points。這比先接 LlamaIndex 更符合本案需求，原因是：

- 需要精準控制 named vectors：`dense` / `sparse`。
- 需要精準控制 payload 欄位、nullable、empty arrays。
- 需要 deterministic point id 與 source hash。
- v1 不是 retrieval framework，而是 storage/indexer。

LlamaIndex 可作 future adapter，但不是 v1 dependency。

---

## 4. Data Model

### 4.1 Source of truth

正式輸入是：

```text
S:\jd-pdf-to-json\output\0518\*.json
```

實測資料：

- 908 files
- 3,272 units
- 8,347 tasks
- 8,689 blocks
- 129 files missing version history
- 903 files missing job category
- 53 multi-task groups

### 4.2 Chunk keys

```text
profile: {ocs_code}::profile
unit:    {ocs_code}::unit::{ocu_code}
block:   {ocs_code}::block::{ocu_code}::{primary_task_code}::{block_idx}
```

`primary_task_code` 使用該 task group 的第一個 T-code。完整 `task_codes` 仍寫入 payload，供 filter 與未來 retrieval 使用。

### 4.3 Payload 缺漏規則

- Required：
  - `chunk_key`
  - `chunk_type`
  - `ocs_code`
  - `ocs_name`
  - `ocs_level`
  - `source_file`
  - `source_hash`
  - `indexed_at`
- Nullable：
  - `parent_id`
  - `version`
  - `version_seq`
  - `update_date`
  - `ocu_code`
  - `ocu_name`
  - `competency_level`
- Empty array default：
  - category arrays
  - task arrays
  - indicator/output/knowledge/skill/attitude arrays
  - prerequisites/supplements derived flags

若 version history 缺失，從 `ocs_profile.ocs_code` 解析尾端 `vN`。可解析則寫 `version="VN"`、`version_seq=N`；不可解析則設為 null。`is_current` 預設 true，除非 version history 明確指出不是最新版本。

---

## 5. Embedding and Qdrant

### 5.1 v1 default

- Collection: `ocs_bgem3_v1`
- Dense vector:
  - name: `dense`
  - size: 1024
  - distance: cosine
- Sparse vector:
  - name: `sparse`
  - source: BGE-M3 lexical weights
  - distance: dot product by Qdrant sparse vector behavior

預設不啟用 ColBERT multi-vector。若後續 retrieval 品質不足，再以新 collection 重新評估。

### 5.2 Provider options

| Provider | 優點 | 缺點 | v1 建議 |
|---|---|---|---|
| BGE-M3 local | 中文與代碼/術語混合友善，可 dense+sparse 離線 | 依賴較重，CPU 較慢 | 預設 |
| OpenAI dense-only | 部署簡單，品質穩 | 成本、API key、無 sparse | adapter |
| FastEmbed/BM25 | Qdrant 生態整合順 | 語意與中文效果需實測 | adapter/PoC |

不同 provider 不混同一 collection。換 provider 或向量維度即建立新 collection。

### 5.3 Payload indexes

v1 payload indexes 以未來 filter 為準：

- `chunk_type`
- `ocs_code`
- `ocs_code_base`
- `version`
- `is_current`
- `ocs_level`
- `competency_level`
- `occupation_codes`
- `industry_codes`
- `task_codes`
- `knowledge_codes`
- `skill_codes`
- `attitude_codes`
- `ocs_name` text index

---

## 6. CLI

### `render`

```bash
uv run python -m jd_ocs_indexer.cli render S:\jd-pdf-to-json\output\0518 -o output\md
```

只讀 JSON 並輸出 Markdown，不連 Qdrant。

### `index`

```bash
uv run python -m jd_ocs_indexer.cli index S:\jd-pdf-to-json\output\0518
```

執行完整 pipeline，依 source hash 跳過未變檔案。

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
```

僅用於驗證索引，不視為正式查詢接口。

---

## 7. LlamaParse Notes

LlamaParse v2 不進 v1 主線。保留用途：

- 重新解析 PDF，與既有 JSON 比對。
- 取 `markdown` / `items` 檢查表格抽取品質。
- 作為未來資料補洞或品質稽核工具。

截至本報告撰寫時，LlamaParse v2 的關鍵用法：

- Python SDK: `llama-cloud>=2.1`
- client: `LlamaCloud()`
- required parse fields: `tier`、`version`
- result selection: `expand=["markdown", "items"]`
- v2 request options 分為 `input_options`、`processing_options`、`agentic_options`、`output_options`

參考：https://developers.llamaindex.ai/llamaparse/

---

## 8. Acceptance Criteria

- `README.md` 清楚描述 v1 做什麼與不做什麼。
- `IMPLEMENTATION_PLAN.md` 足以直接建立程式骨架。
- 文件不再把正式 RetrievalService 寫成 v1 目標。
- `render` 能對 fixture JSON 產出 profile/unit/block Markdown。
- `doctor` 能回報已知資料缺漏，不把缺 version/job_category 視為 fatal。
- `index` 對 fixture 可建立 Qdrant collection 並 upsert points。
- `smoke-query` 可驗證 count、retrieve by `ocs_code`、filter by K/S code。

---

## 9. References

- LlamaParse: https://developers.llamaindex.ai/llamaparse/
- Qdrant overview: https://qdrant.tech/documentation/overview/
- Qdrant hybrid queries: https://qdrant.tech/documentation/search/hybrid-queries/
