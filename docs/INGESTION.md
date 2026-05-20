# Ingestion Pipeline

v1 ingestion 採自訂 pipeline，不使用 LlamaIndex `IngestionPipeline` 作主線。

```text
OCSJSONReader -> OCSNodeBuilder -> MarkdownRenderer -> EmbeddingService -> QdrantWriter
```

這個選擇讓 v1 可以精準控制 chunk 邊界、Markdown text、payload schema、source hash、deterministic point id、Qdrant named vectors。

---

## 1. Pipeline Overview

### 1.1 Reader

`OCSJSONReader` 負責：

- 讀取單一 JSON 檔。
- 以 Pydantic model 驗證。
- 計算 canonical `source_hash`。
- 產生 source metadata：`source_file`、mtime、hash。
- 將可容忍缺漏轉成一致內部模型。

輸出：

```python
LoadedOCSDocument(
    path=Path(...),
    source_hash="...",
    document=OCSDocument(...),
)
```

### 1.2 Builder

`OCSNodeBuilder` 負責：

- 每份 JSON 產生一個 `profile` chunk。
- 每個 `ocu_unit` 產生一個 `unit` chunk。
- 每個 `competency_block` 產生一個 `block` chunk。
- 填入 `chunk_key`、`parent_id`、payload base fields。
- 處理缺 version、缺 job category、multi-task group。

輸出：

```python
ChunkSpec(
    chunk_key="INM3513-009v1::block::T1::T1.1::0",
    chunk_type="block",
    parent_key="INM3513-009v1::unit::T1",
    payload={...},
    source={...},
)
```

### 1.3 Renderer

`MarkdownRenderer` 負責：

- 將 `ChunkSpec` render 成 Markdown。
- Markdown 作為 embedding input 與人工檢視輸出。
- 可選擇 dump 到 `output/md/{ocs_code}/`。

Markdown 不作為 split input。chunk 邊界已由 Builder 決定。

### 1.4 Embedder

`EmbeddingService` 負責將 Markdown text 轉成 vector。

```python
class EmbeddingService(Protocol):
    dense_dim: int
    supports_sparse: bool

    def embed_dense(self, texts: list[str]) -> list[list[float]]: ...
    def embed_sparse(self, texts: list[str]) -> list[SparseVector] | None: ...
```

v1 預設 BGE-M3：

- dense: 1024 dim
- sparse: lexical weights
- 不輸出 ColBERT multi-vector

### 1.5 Writer

`QdrantWriter` 負責：

- 確認 collection 存在。
- 建立 named vectors 與 payload indexes。
- 將 chunks 轉成 `PointStruct`。
- batch upsert。
- 記錄失敗 chunks。
- 更新 local manifest。

---

## 2. Incremental Indexing

v1 使用 local manifest 控制增量，不依賴 LlamaIndex docstore。

Manifest 可存在：

```text
.data/index_manifest.json
```

建議格式：

```json
{
  "collection": "ocs_bgem3_v1",
  "embedding_provider": "bgem3",
  "sources": {
    "AIoT應用工程師-職能基準.json": {
      "source_hash": "...",
      "ocs_code": "INM3513-009v1",
      "chunk_keys": [
        "INM3513-009v1::profile",
        "INM3513-009v1::unit::T1"
      ],
      "indexed_at": "2026-05-20T..."
    }
  }
}
```

流程：

1. 掃描 `*.json`。
2. 計算 `source_hash`。
3. hash 未變：skip。
4. hash 新增或變更：重建該檔 chunks。
5. upsert 該檔 points。
6. 更新 manifest。

`--rebuild` 可刪除 collection 後重建。`--prune` 可刪除 manifest 中存在但 source dir 已消失的 OCS。

---

## 3. CLI

### 3.1 render

```bash
uv run python -m jd_ocs_indexer.cli render <json_dir> -o output/md
```

用途：

- 驗證 JSON -> chunks -> Markdown。
- 不載入 embedding model。
- 不連 Qdrant。

驗收：

- 每份 JSON 至少產生一個 profile。
- total chunks = profile + unit + block。
- dump path 保留 `ocs_code` 與 `chunk_key`。

### 3.2 index

```bash
uv run python -m jd_ocs_indexer.cli index <json_dir>
uv run python -m jd_ocs_indexer.cli index <json_dir> --rebuild
uv run python -m jd_ocs_indexer.cli index <json_dir> --prune
```

用途：

- 執行完整 indexing。
- 預設增量。
- `--rebuild` 強制重建 collection。
- `--prune` 清除 source dir 已不存在的舊 points。

### 3.3 stats

```bash
uv run python -m jd_ocs_indexer.cli stats <json_dir>
uv run python -m jd_ocs_indexer.cli stats --collection ocs_bgem3_v1
```

來源統計：

- files
- units
- tasks
- blocks
- missing version history
- missing job category
- multi-task groups

Collection 統計：

- total points
- count by chunk_type
- collection vector config
- payload index list

### 3.4 doctor

```bash
uv run python -m jd_ocs_indexer.cli doctor <json_dir>
```

檢查：

- JSON parse error。
- zero block。
- missing `ocs_code`。
- missing `ocs_name`。
- missing version history。
- missing job category。
- empty attitudes。

缺 version/job category 是 warning，不是 fatal。

### 3.5 smoke-query

```bash
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v1 --ocs-code INM3513-009v1
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v1 --knowledge K01 --skill S01
```

用途只限驗證：

- collection count 正常。
- `ocs_code` retrieve 正常。
- K/S code payload filter 正常。

輸出格式不作穩定 API 承諾。

---

## 4. Embedding Providers

### 4.1 BGE-M3 local（v1 default）

優點：

- 適合中文與代碼/術語混合資料。
- 同時支援 dense 與 sparse。
- 可離線。

缺點：

- dependency 與模型下載較重。
- CPU 全量索引時間可能較長。

### 4.2 OpenAI dense-only adapter

優點：

- 不需本機模型資源。
- 部署簡單。

缺點：

- 需要 API key 與成本控管。
- dense-only，精準代碼查詢要依賴 payload filter。
- collection schema 與 BGE-M3 不相容。

### 4.3 FastEmbed/BM25 adapter

優點：

- Qdrant 生態整合好。
- 較輕量。

缺點：

- 中文語意品質需實測。
- 不一定等價於 BGE-M3 sparse lexical weights。

---

## 5. Error Handling

| 失敗 | 行為 |
|---|---|
| JSON parse failed | 記入 `failed_files.jsonl`，繼續下一檔 |
| Required field missing | fatal for that file |
| Known optional field missing | warning，使用 null 或 empty array |
| Embedding failed | batch retry；仍失敗記入 `failed_chunks.jsonl` |
| Qdrant upsert failed | retry；仍失敗則 CLI exit non-zero |
| Manifest update failed | CLI exit non-zero，避免索引狀態不可信 |

---

## 6. Future Adapters

### LlamaIndex

保留作 future adapter，不是 v1 主線。可能用途：

- v2 query/retriever abstraction。
- 與其他 vector store 串接。
- RAG evaluation pipeline。

### LlamaParse

保留作 PDF 驗證/補洞工具。可能用途：

- 重新解析 PDF。
- 比對 markdown/items 與既有 JSON。
- 發現上游 parser 漏抽欄位。

---

## 7. Acceptance Criteria

- `render` 對 fixture 可產出 profile/unit/block Markdown。
- `doctor` 對 908 JSON 可完成並列出 warning。
- `index` 對 fixture 可建立 collection 與 upsert points。
- 重跑 `index` 對未變檔案會 skip。
- `smoke-query` 可完成 count、retrieve、payload filter。
