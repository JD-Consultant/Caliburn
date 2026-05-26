# Ingestion Pipeline

v1 ingestion 採自訂 pipeline，不使用 LlamaIndex `IngestionPipeline` 作主線。

```text
OCSJSONReader -> OCSNormalizer -> ChunkBuilder -> MarkdownRenderer -> EmbeddingService -> QdrantWriter
```

這個選擇讓 v1 可以精準控制 chunk 邊界、Markdown text、payload schema、source hash、deterministic point id、Qdrant named vectors。

---

## 1. Reader

`OCSJSONReader` 負責：

- 掃描 `S:\jd-pdf-to-json\output\0518\*.json`。
- 以 Pydantic model 驗證 JSON。
- 產生 canonical JSON bytes。
- 計算 `source_json_hash`。
- 產生相對路徑 `source_file`，例如 `output/0518/example.json`。
- 寫入 `source_root_alias = "jd-pdf-to-json"`。

Reader 不處理 PDF，不嘗試修補上游資料，只做解析與健康狀態紀錄。

---

## 2. Normalizer

`OCSNormalizer` 負責把已知缺漏轉成穩定欄位：

- 缺 version history：從 `ocs_code` 尾端 `vN` 推導，失敗則 nullable。
- 缺 `job_category`：`job_category = null`，`job_category_codes = []`。
- 缺 task / K/S / attitude arrays：寫 `[]`。
- 多 task group：排序後選 `primary_task_key`，完整 task ids 仍保留。
- 建立 order 欄位：`unit_order`、`task_orders`、`block_order`。

Normalizer 的目標是讓後續 Builder 不需要到處處理缺欄位。

---

## 3. Chunk Builder

`ChunkBuilder` 依 JSON 結構產生三層 chunk：

- 每份 JSON 產生一個 `profile` chunk。
- 每個 `ocu_unit` 產生一個 `unit` chunk。
- 每個 `competency_block` 產生一個 `block` chunk。

每個 chunk 都包含：

```text
chunk_key
chunk_level
base payload
profile_chunk_id / unit_chunk_id
source_path
source_labels
```

chunk key 範例：

```text
profile: ocs:INM3513-009v1:profile
unit:    ocs:INM3513-009v1:unit:T1
block:   ocs:INM3513-009v1:unit:T1:task:T1.1:block:0001
```

如果原始 JSON 沒有穩定代碼，使用 zero-padded index fallback：

```text
unit:0001
task:0002
block:0003
```

---

## 4. Markdown Renderer

`MarkdownRenderer` 負責把 chunk 轉成可 embedding、可給 LLM 當 context 的 Markdown。

原則：

- Markdown 不是切分來源，chunk 邊界由 Builder 決定。
- 每個 chunk text 都要自我完備，包含職務、unit/task/block 上下文。
- block chunk 要放使用者會說得出口的工作活動、知識、技能文字，不只放代碼。
- unit chunk 可放任務摘要與 K/S 去重集合。
- profile chunk 放職務摘要、類別、主要 unit 列表、態度與 notes。

Renderer 產出後計算 `chunk_content_hash`。

---

## 5. Embedding

`EmbeddingService` 介面：

```python
class EmbeddingService(Protocol):
    provider: str

    def embed_texts(self, texts: list[str]) -> list[EmbeddedVector]:
        ...
```

v1 預設 BGE-M3：

- `dense`: 1024d
- `sparse`: lexical_weights

備案：

- OpenAI dense-only adapter。
- FastEmbed/BM25 adapter。

不同 provider 或維度使用不同 collection。

---

## 6. Qdrant Writer

`QdrantWriter` 負責：

- 建立 collection `ocs_bgem3_v1`。
- 建立 payload indexes。
- 將 `EmbeddedChunk` 轉成 `PointStruct`。
- 使用 `uuid5(namespace, chunk_key)` 產生 deterministic point id。
- batch upsert。
- 失敗重試與 failed report。

Point 結構：

```text
id      = uuid5(chunk_key)
vectors = {"dense": ..., "sparse": ...}
payload = chunk payload + text
```

---

## 7. Manifest and Incremental Indexing

v1 使用 local manifest 控制增量，不依賴 LlamaIndex docstore。

範例：

```json
{
  "collection": "ocs_bgem3_v1",
  "embedding_provider": "bge-m3",
  "source_root_alias": "jd-pdf-to-json",
  "files": {
    "output/0518/example.json": {
      "source_json_hash": "sha256:...",
      "chunk_keys": [
        "ocs:INM3513-009v1:profile"
      ],
      "indexed_at": "2026-05-26T00:00:00+08:00"
    }
  }
}
```

順序：

1. 掃描 source files。
2. 計算 `source_json_hash`。
3. hash 未變：skip。
4. hash 新增或變更：重建該檔 chunks。
5. upsert 該檔 points 到 Qdrant。
6. Qdrant upsert 確認回應後，才更新 manifest。

若 manifest 寫入失敗，CLI exit non-zero，避免 Qdrant 與 manifest 狀態靜默分歧。

---

## 8. CLI

### render

```bash
uv run python -m jd_ocs_indexer.cli render S:\jd-pdf-to-json\output\0518 -o output\md
```

驗證 JSON -> chunks -> Markdown，不連 Qdrant。

### index

```bash
uv run python -m jd_ocs_indexer.cli index S:\jd-pdf-to-json\output\0518
```

跑完整 pipeline。

### stats

```bash
uv run python -m jd_ocs_indexer.cli stats S:\jd-pdf-to-json\output\0518
uv run python -m jd_ocs_indexer.cli stats --collection ocs_bgem3_v1
```

### doctor

```bash
uv run python -m jd_ocs_indexer.cli doctor S:\jd-pdf-to-json\output\0518
```

檢查缺 version、缺 job_category、zero block、multi-task group 等。

### smoke-query

```bash
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v1 --ocs-code INM3513-009v1
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v1 --knowledge K01 --skill S01
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v1 --probe-vector "資料清理 報表 需求確認"
```

`smoke-query` 只驗證索引，不是正式 API。

---

## 9. LlamaIndex Decision

LlamaIndex 不在 v1 使用，原因：

- 已有乾淨 JSON，不需要 parser。
- v1 是 deterministic ingestion + storage。
- Qdrant payload schema、source trace、point id 都需要精準控制。
- 未來 MCP/API 若只是工具層，也以 `qdrant-client` + custom context assembler 更可控。

只有未來需要 chat engine、agent workflow、RAG evaluation framework 時，才另外評估。

---

## 10. Failure Handling

| Failure | Handling |
|---|---|
| JSON parse failed | 記入 `failed_files.jsonl`，繼續下一檔 |
| Required field missing | 若無 fallback，記入 failed；已知缺漏由 normalizer 處理 |
| Embedding failed | batch retry；仍失敗記入 `failed_chunks.jsonl` |
| Qdrant upsert failed | retry；仍失敗則 CLI exit non-zero |
| Manifest write failed | CLI exit non-zero |

---

## 11. Output Reports

`index` 完成後輸出：

- source file count
- skipped / indexed / failed count
- chunks by `chunk_level`
- payload index ensure status
- embedding provider / collection
- elapsed time

報告不作正式 API，僅供操作與 debug。
