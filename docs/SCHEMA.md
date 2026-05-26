# Qdrant Schema

本文定義 `jd-ocs-indexer` v1 的 Qdrant collection、vectors、payload、payload indexes 與 point id 規則。

> 對應 chunk 邊界見 [CHUNKING.md](./CHUNKING.md)；對應 pipeline 見 [INGESTION.md](./INGESTION.md)。

---

## 1. Collection

命名格式：

```text
ocs_{provider}_v{n}
```

v1 預設：

```text
ocs_bgem3_v1
```

規則：

- 不同 embedding provider 不混同一 collection。
- 不同 vector 維度不混同一 collection。
- payload schema 大改時升 collection version。
- Manifest 中保存 collection name 與 embedding provider，避免誤寫。

---

## 2. Vectors

v1 預設使用 BGE-M3：

```python
from qdrant_client.http import models

vectors_config = {
    "dense": models.VectorParams(
        size=1024,
        distance=models.Distance.COSINE,
    ),
}

sparse_vectors_config = {
    "sparse": models.SparseVectorParams(
        index=models.SparseIndexParams(on_disk=False),
    ),
}
```

| Vector | 來源 | 維度 | distance |
|---|---|---:|---|
| `dense` | BGE-M3 dense vector | 1024 | Cosine |
| `sparse` | BGE-M3 lexical_weights | sparse | Dot |

不啟用 Qdrant `Modifier.IDF` 作為 v1 預設。BGE-M3 lexical_weights 已是模型產生的 token 權重，先避免二次加權。

OpenAI adapter 只寫 `dense` vector，需使用獨立 collection，例如 `ocs_openai_v1`。

---

## 3. Payload Design

一個 chunk 寫成一個 Qdrant point：

```text
logical chunk = text + metadata + source trace
qdrant point = id + vector(s) + payload
```

payload 分成三類：

| 類別 | 用途 | 是否通常建 index |
|---|---|---:|
| query metadata | filter / group / ranking | yes |
| context metadata | 搜尋結果顯示、parent expansion | partly |
| trace metadata | 回溯 JSON、debug、增量更新 | no |

### 3.1 Complete payload

```python
{
    # Identification
    "chunk_key": str,                 # ocs:{ocs_code}:unit:{unit_key}:...
    "chunk_level": Literal["profile", "unit", "block"],
    "schema_version": str,            # "ocs-index-v1"
    "embedding_provider": str,        # "bge-m3"
    "text_format": Literal["markdown"],
    "text": str,                      # Markdown text used for embedding and context

    # OCS profile
    "ocs_code": str,
    "ocs_code_base": str,             # 去版本，用於跨版本聚合
    "job_title": str,
    "job_category": Optional[str],
    "version": Optional[str],
    "version_seq": Optional[int],
    "is_current": bool,
    "update_date": Optional[str],
    "ocs_level": Optional[int],

    # Category arrays
    "job_category_codes": list[str],
    "industry_codes": list[str],
    "industry_names": list[str],
    "occupation_codes": list[str],
    "occupation_names": list[str],

    # Unit context
    "unit_id": Optional[str],
    "unit_title": Optional[str],
    "unit_order": Optional[int],

    # Task context
    "task_ids": list[str],
    "task_titles": list[str],
    "task_orders": list[int],

    # Block context
    "block_id": Optional[str],
    "block_title": Optional[str],
    "block_order": Optional[int],
    "competency_level": Optional[int],

    # Parent chunk ids for small-to-big context
    "profile_chunk_id": Optional[str],
    "unit_chunk_id": Optional[str],

    # OCS codes for filter / evidence
    "indicator_codes": list[str],     # P codes
    "output_codes": list[str],        # O codes
    "k_codes": list[str],
    "s_codes": list[str],
    "attitude_codes": list[str],

    # Human-readable terms for JD authoring service
    "knowledge_terms": list[str],
    "skill_terms": list[str],
    "work_activity_terms": list[str],

    # Source trace
    "source_root_alias": str,         # "jd-pdf-to-json"
    "source_file": str,               # "output/0518/example.json"
    "source_json_hash": str,          # sha256 canonical source JSON
    "chunk_content_hash": str,        # sha256 rendered Markdown text
    "source_path": Optional[str],     # JSON pointer-ish path
    "source_labels": dict[str, list[str] | str],
    "indexed_at": str,                # ISO 8601
}
```

### 3.2 Required fields

必填：

- `chunk_key`
- `chunk_level`
- `schema_version`
- `embedding_provider`
- `text_format`
- `text`
- `ocs_code`
- `ocs_code_base`
- `job_title`
- `is_current`
- `source_root_alias`
- `source_file`
- `source_json_hash`
- `chunk_content_hash`
- `indexed_at`

### 3.3 Nullable fields

可為 `null`：

- `job_category`
- `version`
- `version_seq`
- `update_date`
- `ocs_level`
- `unit_id`
- `unit_title`
- `unit_order`
- `block_id`
- `block_title`
- `block_order`
- `competency_level`
- `profile_chunk_id`
- `unit_chunk_id`
- `source_path`

### 3.4 Empty array fields

缺資料時寫 `[]`，不寫 `null`：

- `job_category_codes`
- `industry_codes`
- `industry_names`
- `occupation_codes`
- `occupation_names`
- `task_ids`
- `task_titles`
- `task_orders`
- `indicator_codes`
- `output_codes`
- `k_codes`
- `s_codes`
- `attitude_codes`
- `knowledge_terms`
- `skill_terms`
- `work_activity_terms`

---

## 4. Field Semantics

### `source_file`

`source_file` 是相對於 configured source root 的路徑：

```json
{
  "source_root_alias": "jd-pdf-to-json",
  "source_file": "output/0518/example.json"
}
```

用途：

- 查詢命中後讀回完整 JSON。
- JD 生成前補完整背景資料。
- debug chunk 來源。
- 搭配 `source_json_hash` 驗證來源版本。

不在 payload 中寫 `S:/...` 絕對路徑，避免綁死本機磁碟與部署環境。

### `source_json_hash`

整份 canonical JSON 的 sha256。用途：

- 判斷來源 JSON 是否變更。
- 控制增量索引。
- 驗證未來 service 讀到的 JSON 是否與索引時一致。

### `chunk_content_hash`

render 後 Markdown text 的 sha256。用途：

- 判斷 chunk text 是否真的變更。
- 未來可做 per-chunk embedding cache。

### `profile_chunk_id` / `unit_chunk_id`

parent chunk id 是 Qdrant 內的快速上下文捷徑：

- block 命中後，用 `unit_chunk_id` 取回所屬 unit Markdown。
- 多個 block 命中同一職務時，用 `profile_chunk_id` 取回職務摘要。
- 不需要每次都讀完整 JSON。

完整 JSON 仍由 `source_file` 回讀；parent id 不負責還原完整 JSON。

### `source_labels`

保留原始 OCS 標籤，例如：

```json
{
  "unit": "T1",
  "tasks": ["T1.1"],
  "indicators": ["P1.1.1", "P1.1.2"],
  "outputs": ["O1.1.1"]
}
```

這些標籤不是主要搜尋入口，不預設建 index。用途是 citation、排序、debug、回原始 JSON 對照。

---

## 5. Payload Indexes

不是所有 payload 欄位都建 index。v1 只對常用 filter / group 欄位建：

```python
from qdrant_client.http import models

PAYLOAD_INDEXES = [
    ("chunk_level", models.PayloadSchemaType.KEYWORD),
    ("ocs_code", models.PayloadSchemaType.KEYWORD),
    ("ocs_code_base", models.PayloadSchemaType.KEYWORD),
    ("job_title", models.PayloadSchemaType.TEXT),
    ("job_category", models.PayloadSchemaType.KEYWORD),
    ("version", models.PayloadSchemaType.KEYWORD),
    ("is_current", models.PayloadSchemaType.BOOL),
    ("ocs_level", models.PayloadSchemaType.INTEGER),
    ("unit_id", models.PayloadSchemaType.KEYWORD),
    ("task_ids", models.PayloadSchemaType.KEYWORD),
    ("competency_level", models.PayloadSchemaType.INTEGER),
    ("k_codes", models.PayloadSchemaType.KEYWORD),
    ("s_codes", models.PayloadSchemaType.KEYWORD),
    ("attitude_codes", models.PayloadSchemaType.KEYWORD),
    ("industry_codes", models.PayloadSchemaType.KEYWORD),
    ("occupation_codes", models.PayloadSchemaType.KEYWORD),
    ("schema_version", models.PayloadSchemaType.KEYWORD),
    ("embedding_provider", models.PayloadSchemaType.KEYWORD),
]
```

暫不建 index：

- `source_file`
- `source_json_hash`
- `chunk_content_hash`
- `source_path`
- `source_labels`
- `indicator_codes`
- `output_codes`
- 各種 title/name arrays
- order 欄位

這些欄位仍會存進 payload，只是不作常用 filter。

---

## 6. Point ID

Qdrant point id 使用 deterministic UUIDv5：

```python
import uuid

NAMESPACE = uuid.UUID("6f1c8a3e-3e0b-4f0f-9c2e-0c5000000001")

def point_id(chunk_key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, chunk_key))
```

優點：

- 同一 chunk 重跑會得到同一 id。
- upsert 可覆寫舊 point，不會重複新增。
- UUID 跨工具與 API 較通用。

---

## 7. Common Filter Examples

### Get all chunks for one OCS

```python
filter_ = models.Filter(
    must=[
        models.FieldCondition(
            key="ocs_code",
            match=models.MatchValue(value="INM3513-009v1"),
        )
    ]
)
```

### Get all blocks with specific K/S codes

```python
filter_ = models.Filter(
    must=[
        models.FieldCondition(key="chunk_level", match=models.MatchValue(value="block")),
        models.FieldCondition(key="k_codes", match=models.MatchAny(any=["K01"])),
        models.FieldCondition(key="s_codes", match=models.MatchAny(any=["S01"])),
    ]
)
```

### Search only unit/block for JD authoring

```python
filter_ = models.Filter(
    must=[
        models.FieldCondition(
            key="chunk_level",
            match=models.MatchAny(any=["unit", "block"]),
        ),
        models.FieldCondition(key="is_current", match=models.MatchValue(value=True)),
    ]
)
```

### Retrieve parent context

Application layer should map `profile_chunk_id` / `unit_chunk_id` to point ids using the same `uuid5(namespace, chunk_key)` function, then call batch retrieve.

---

## 8. Collection Creation Pseudocode

```python
def ensure_collection(client, name="ocs_bgem3_v1"):
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config={
                "dense": models.VectorParams(
                    size=1024,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(
                    index=models.SparseIndexParams(on_disk=False),
                )
            },
        )

    for field, ftype in PAYLOAD_INDEXES:
        client.create_payload_index(
            collection_name=name,
            field_name=field,
            field_schema=ftype,
        )
```

---

## 9. Storage Estimate

- Dense 1024d float32：約 4 KB / point。
- 12,869 points：約 51.5 MB dense vectors。
- Sparse vectors、payload、HNSW index 加總後，POC 預估仍低於數百 MB。

資料量對 Qdrant 很小；設計重點不是容量，而是 metadata contract 與 future service 可用性。
