# Qdrant Schema

本文定義 Qdrant collection 的結構：vectors 配置、payload 欄位、索引、命名規範。

> 對應 chunk 結構見 [CHUNKING.md](./CHUNKING.md)；對應 ingestion 流程見 [INGESTION.md](./INGESTION.md)。

---

## 1. Collection 命名

- v1 default：`ocs_bgem3_v1`
- 升 embedding 模型或大幅改 schema 時：`ocs_v2`、`ocs_v3`...
- 多模型並存 PoC 期間：`ocs_bgem3_v1`、`ocs_openai_v1`、`ocs_fastembed_v1`

理由：vector 維度不同的 collection 無法互通；版本化 collection 比 alias 切換更安全。

---

## 2. Vectors 配置（named vectors）

```python
from qdrant_client.http import models

vectors_config = {
    "dense": models.VectorParams(
        size=1024,
        distance=models.Distance.COSINE,
        on_disk=False,
    ),
}
sparse_vectors_config = {
    "sparse": models.SparseVectorParams(
        index=models.SparseIndexParams(on_disk=False),
        # v1 預設不加 modifier，避免與 BGE-M3 lexical_weights 重複加權。
        # 若未來評測證明 IDF 較佳，再以新 collection 升版。
    ),
}
```

| Vector | 模型 | 維度 | distance | 來源 |
|---|---|---|---|---|
| `dense` | BGE-M3 dense | 1024 | Cosine | `BGEM3FlagModel.encode(...)["dense_vecs"]` |
| `sparse` | BGE-M3 lexical_weights | 不定 | Dot | `encode(..., return_sparse=True)["lexical_weights"]` |

**為什麼不啟用 ColBERT 多向量？**
- BGE-M3 第三種輸出 `colbert_vecs` 是 token-level 多向量，Qdrant 支援為 `MultiVectorConfig`
- 對 13K chunks 用 ColBERT，儲存 +5x、index 速度 -3x，POC 不值得
- 留作未來「retrieval 精度不足」時的補救手段；schema 升版 → 新 collection

**OpenAI adapter 切換時**：
- 改為 `dense_openai: VectorParams(size=3072, distance=COSINE)`
- 不可與 BGE-M3 同 collection 混用（維度不同 + 語意空間不同 + sparse 不存在）
- Adapter 切換 = 新 collection

---

## 3. Payload schema

所有 chunk 共用同一 payload schema。v1 規則：

- Required：識別、OCS 基本欄位、來源追蹤欄位必須存在。
- Nullable：版本、parent、OCU/task/block 層級欄位可為 null。
- Empty array：分類、代碼集合、聚合欄位缺失時一律寫空陣列。

```python
{
    # 識別與分層 ----
    "chunk_key": str,              # 例：FSI3311-001v3::block::T1::T1.1::0
    "chunk_type": Literal["profile", "unit", "block"],
    "parent_id": Optional[str],    # block→unit::T1 / unit→profile / profile→None

    # OCS 層級 ----
    "ocs_code": str,               # 例：FSI3311-001v3
    "ocs_code_base": str,          # 例：FSI3311-001（去版本，跨版本聚合用）
    "ocs_name": str,               # 例：證券業-受託買賣業務人員
    "version": Optional[str],      # 例：V3；缺 version history 時從 ocs_code 解析
    "version_seq": Optional[int],  # 1=V1, 2=V2, 3=V3...（數字比較用）
    "is_current": bool,            # status == "最新版本"
    "update_date": Optional[str],  # YYYY/MM/DD（字串比 ISO 對齊上游格式）
    "ocs_level": int,              # 2–5

    # 類別陣列 ----
    "job_category_codes": list[str],   # 例：["FSI"]
    "job_category_names": list[str],
    "occupation_codes": list[str],     # 例：["3311"]
    "occupation_names": list[str],
    "industry_codes": list[str],       # 例：["K6611"]
    "industry_names": list[str],

    # OCU / Task ----（unit 與 block 才有）
    "ocu_code": Optional[str],         # 例：T1
    "ocu_name": Optional[str],
    "task_codes": list[str],       # 例：["T1.1"] 或 ["T1.1","T1.2"]；非 task 層為 []
    "task_names": list[str],

    # Block 內容 ----（block 才有）
    "competency_level": Optional[int],    # 2–5 或 null
    "indicator_codes": list[str],  # ["P1.1.1","P1.1.2"]；非 block 為 []
    "output_codes": list[str],     # ["O1.1.1"]
    "knowledge_codes": list[str],  # ["K05","K12"]
    "skill_codes": list[str],      # ["S01","S09"]

    # Unit 聚合 ----（unit 才有，block-level 去重後集合）
    "unit_knowledge_codes": list[str],
    "unit_skill_codes": list[str],

    # Profile 限定 ----（profile 才有）
    "attitude_codes": list[str],   # ["A01","A02",...]；非 profile 為 []
    "has_prerequisites": Optional[bool],
    "has_supplements": Optional[bool],

    # 來源追蹤 ----
    "source_file": str,            # 例：證券業-受託買賣業務人員-職能基準.json
    "source_hash": str,            # sha256 of source JSON，增量更新觸發條件
    "indexed_at": str,             # ISO 8601 timestamp
}
```

### 設計筆記

- **`ocs_code_base`**：把 `FSI3311-001v3` 切成 base `FSI3311-001` + version `V3`。跨版本聚合查詢用 base。
- **version 缺失**：目前 908 份中有 129 份缺 version history。v1 從 `ocs_profile.ocs_code` 尾端 `vN` 推導 `version` / `version_seq`；不可推導時填 null，`is_current` 預設 true。
- **category 缺失**：目前多數 JSON 缺 `job_category`。`job_category_codes` / `job_category_names` 寫空陣列，不視為 fatal。
- **多 T-code**：53 個 task group 含多個 T-code。`chunk_key` 使用第一個 T-code，payload `task_codes` 保留完整陣列供 filter。
- **代碼陣列存代碼，非 name**：name 較長、會變動、且 dense vector 已能語意比對 name 相似度；代碼負責 filter，name 在 vector 端。
- **`source_hash`**：對來源 JSON `sha256(canonical_json_bytes)`，內容變動才重新處理；v1 由 local manifest 控制增量。
- **`indexed_at`**：除錯與 stale data 排查；不參與檢索。

---

## 4. Payload 索引

不是所有欄位都需要 indexed payload field（Qdrant 對未索引 payload 的 filter 走全表掃描）。實際會被 filter 的欄位才建索引：

```python
from qdrant_client.http import models

PAYLOAD_INDEXES = [
    ("chunk_type", models.PayloadSchemaType.KEYWORD),
    ("ocs_code", models.PayloadSchemaType.KEYWORD),
    ("ocs_code_base", models.PayloadSchemaType.KEYWORD),
    ("version", models.PayloadSchemaType.KEYWORD),
    ("is_current", models.PayloadSchemaType.BOOL),
    ("ocs_level", models.PayloadSchemaType.INTEGER),
    ("competency_level", models.PayloadSchemaType.INTEGER),

    # 陣列：indexed keyword 即可走 match.any
    ("job_category_codes", models.PayloadSchemaType.KEYWORD),
    ("occupation_codes", models.PayloadSchemaType.KEYWORD),
    ("industry_codes", models.PayloadSchemaType.KEYWORD),
    ("task_codes", models.PayloadSchemaType.KEYWORD),
    ("knowledge_codes", models.PayloadSchemaType.KEYWORD),
    ("skill_codes", models.PayloadSchemaType.KEYWORD),
    ("attitude_codes", models.PayloadSchemaType.KEYWORD),
    ("unit_knowledge_codes", models.PayloadSchemaType.KEYWORD),
    ("unit_skill_codes", models.PayloadSchemaType.KEYWORD),

    # 文字模糊搜尋（可選；用於「職業名稱包含 X」之類）
    ("ocs_name", models.PayloadSchemaType.TEXT),
]
```

**不建索引**：`indicator_codes`、`output_codes`、各種 name 陣列、`source_file`、`source_hash`、`indexed_at`。這些 payload 仍儲存但不參與常用 filter（或極少用到，全表掃描可接受）。

---

## 5. Point ID 規則

```python
import uuid
NAMESPACE = uuid.UUID("6f1c8a3e-3e0b-4f0f-9c2e-0c5000000001")  # 固定

def point_id(chunk_key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, chunk_key))
```

- 確定性映射：同 `chunk_key` 永遠對應同一 UUID
- 增量更新時 upsert（`PointStruct` 帶同 id）= 覆寫，符合預期
- 避免用 hash int（Qdrant 也支援），UUID 跨工具更通用

---

## 6. 常用 Filter 範本

### 「依技能查職位」（反向查詢，純 filter，無向量）

```python
filter = models.Filter(
    must=[
        models.FieldCondition(
            key="skill_codes",
            match=models.MatchAny(any=["S01", "S09"]),  # 任一技能
        ),
        models.FieldCondition(key="is_current", match=models.MatchValue(value=True)),
        models.FieldCondition(key="chunk_type", match=models.MatchValue(value="block")),
    ]
)
# 用 scroll API 而非 search（不需要向量距離）
client.scroll(collection_name="ocs_bgem3_v1", scroll_filter=filter, limit=100, with_payload=True)
```

### 「金融業 + L3 以上」混合檢索（v2）

```python
filter = models.Filter(
    must=[
        models.FieldCondition(
            key="industry_codes",
            match=models.MatchAny(any=["K6611", "K6612", "K65"]),
        ),
        models.FieldCondition(
            key="ocs_level",
            range=models.Range(gte=3),
        ),
        models.FieldCondition(key="is_current", match=models.MatchValue(value=True)),
    ]
)
client.query_points(
    collection_name="ocs_bgem3_v1",
    query=models.FusionQuery(fusion=models.Fusion.RRF),
    prefetch=[
        models.Prefetch(query=dense_vec, using="dense", limit=50, filter=filter),
        models.Prefetch(query=sparse_vec, using="sparse", limit=50, filter=filter),
    ],
    limit=10,
    with_payload=True,
)
```

### 「跨版本比對最新版」

```python
filter = models.Filter(
    must=[
        models.FieldCondition(key="ocs_code_base", match=models.MatchValue(value="FSI3311-001")),
        models.FieldCondition(key="is_current", match=models.MatchValue(value=True)),
    ]
)
```

---

## 7. Collection 建立流程（pseudocode）

```python
def ensure_collection(client, name="ocs_bgem3_v1"):
    if client.collection_exists(name):
        return
    client.create_collection(
        collection_name=name,
        vectors_config={"dense": models.VectorParams(size=1024, distance=models.Distance.COSINE)},
        sparse_vectors_config={"sparse": models.SparseVectorParams()},
        hnsw_config=models.HnswConfigDiff(m=16, ef_construct=200),
        optimizers_config=models.OptimizersConfigDiff(default_segment_number=2),
    )
    for field, ftype in PAYLOAD_INDEXES:
        client.create_payload_index(
            collection_name=name,
            field_name=field,
            field_schema=ftype,
        )
```

HNSW 參數的 `m=16` + `ef_construct=200` 對 12,869 points 是寬鬆但安全的設定；future tuning 留給 RETRIEVAL.md 的評估環節。

---

## 8. 預估儲存

- Dense 1024d × float32 = 4 KB / vector × 12,869 = **約 51.5 MB**
- Sparse 平均 ~50 個非零項 × (4 byte idx + 4 byte val) = ~400 byte × 12,869 = **約 5.1 MB**
- Payload 平均 ~2 KB × 12,869 = **約 25.7 MB**
- HNSW 圖、索引開銷：粗估 2× 向量大小
- **總計 < 200 MB**，現代 SSD 隨手可放
