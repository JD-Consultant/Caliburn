# Retrieval 設計

本文件描述未來 v2 retrieval 方向，以及 v1 僅保留的 CLI smoke query。

v1 的正式範圍是索引與儲存，不提供正式查詢服務：

- 不開 HTTP API。
- 不提供穩定 Python retrieval SDK。
- 不組裝 LLM answer。
- 不承諾 `smoke-query` 輸出格式。

---

## 1. v1 Smoke Query

v1 smoke query 的目的只有驗證 Qdrant collection 寫入是否正確。

### 1.1 Count

檢查 collection 存在、point 數合理、chunk_type 分布合理。

```bash
uv run python -m jd_ocs_indexer.cli stats --collection ocs_bgem3_v1
```

預期：

- total points 約等於 profile + unit + block。
- `profile` 約 908。
- `unit` 約 3,272。
- `block` 約 8,689。

### 1.2 Retrieve by `ocs_code`

```bash
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v1 --ocs-code INM3513-009v1
```

底層用 payload filter：

```python
models.Filter(
    must=[
        models.FieldCondition(
            key="ocs_code",
            match=models.MatchValue(value="INM3513-009v1"),
        )
    ]
)
```

用途：

- 驗證 profile/unit/block 都有寫入。
- 驗證 `ocs_code` payload index 可用。
- 驗證 source metadata 存在。

### 1.3 Filter by K/S code

```bash
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v1 --knowledge K01 --skill S01
```

底層用 payload filter，不做 vector search：

```python
models.Filter(
    must=[
        models.FieldCondition(key="chunk_type", match=models.MatchValue(value="block")),
        models.FieldCondition(key="knowledge_codes", match=models.MatchAny(any=["K01"])),
        models.FieldCondition(key="skill_codes", match=models.MatchAny(any=["S01"])),
    ]
)
```

用途：

- 驗證 K/S code arrays 寫入正確。
- 驗證 payload indexes 正常。
- 驗證未來「能力找職務」的資料基礎可行。

---

## 2. v2 Retrieval Scenarios

v2 才會把下列能力整理成正式 service。

| 情境 | 入口 chunk_type | 主要機制 | 是否需要 LLM |
|---|---|---|---|
| 依職能/技能查職位 | block | payload filter | 否 |
| 依職位查職能內涵 | profile -> unit -> block | filter + 結構展開 | 否 |
| 跨基準比對 / 相似度 | profile / unit | hybrid vector search | 否 |
| RAG context retrieval | block + parent unit/profile | hybrid + small-to-big | 不一定 |
| RAG answer engine | context chunks | LLM + citations | 是 |

---

## 3. Future Service API

以下 API 是 v2 方向，不在 v1 實作。

```python
class RetrievalService:
    def find_jobs_by_competencies(
        self,
        knowledge_codes: list[str] | None = None,
        skill_codes: list[str] | None = None,
        attitude_codes: list[str] | None = None,
        match: Literal["any", "all"] = "any",
        industry_codes: list[str] | None = None,
        ocs_level: tuple[int, int] | None = None,
        only_current: bool = True,
        limit: int = 50,
    ) -> list[JobMatch]: ...

    def get_job_profile(
        self,
        ocs_code: str | None = None,
        ocs_name_query: str | None = None,
    ) -> JobProfileFull: ...

    def find_similar_jobs(
        self,
        reference_ocs_code: str,
        granularity: Literal["profile", "unit"] = "profile",
        only_current: bool = True,
        limit: int = 10,
    ) -> list[SimilarJobMatch]: ...

    def search(
        self,
        query: str,
        chunk_types: list[Literal["profile", "unit", "block"]] | None = None,
        filters: SearchFilters | None = None,
        limit: int = 20,
    ) -> list[Hit]: ...

    def retrieve_for_rag(
        self,
        query: str,
        merge_strategy: Literal["small_to_big", "auto_merge", "none"] = "small_to_big",
        top_k_fine: int = 10,
        filters: SearchFilters | None = None,
    ) -> list[RAGContext]: ...
```

---

## 4. 情境 1：依職能/技能查職位

這個情境可以純 payload filter 完成，不需要向量。

範例：「找所有需要 K01 且 S01 的職位」：

```python
filter_ = models.Filter(
    must=[
        models.FieldCondition(key="chunk_type", match=models.MatchValue(value="block")),
        models.FieldCondition(key="knowledge_codes", match=models.MatchAny(any=["K01"])),
        models.FieldCondition(key="skill_codes", match=models.MatchAny(any=["S01"])),
        models.FieldCondition(key="is_current", match=models.MatchValue(value=True)),
    ]
)

hits, _ = client.scroll(
    collection_name="ocs_bgem3_v1",
    scroll_filter=filter_,
    limit=10000,
    with_payload=True,
    with_vectors=False,
)
```

應用層再依 `ocs_code` group，回傳每個職務命中的 blocks 與 codes。

---

## 5. 情境 2：依職位查職能內涵

若使用者提供 `ocs_code`：

```python
filter_ = models.Filter(
    must=[
        models.FieldCondition(key="ocs_code", match=models.MatchValue(value=ocs_code)),
        models.FieldCondition(key="is_current", match=models.MatchValue(value=True)),
    ]
)
```

取回該 OCS 的所有 chunks 後，應用層依：

1. `profile`
2. `unit` by `ocu_code`
3. `block` by `ocu_code` / `task_codes` / `competency_level`

排序組裝成完整職能內涵。

若使用者提供職務名稱，v2 可先用 `ocs_name` text index 或 hybrid search resolve `ocs_code`。

---

## 6. 情境 3：相似職務

v2 使用 Qdrant Query API 做 hybrid search。Qdrant 支援在同一個 point 上存 named dense/sparse vectors，再用 prefetch + RRF fusion 合併結果。

範例：

```python
client.query_points(
    collection_name="ocs_bgem3_v1",
    prefetch=[
        models.Prefetch(
            query=dense_vec,
            using="dense",
            limit=30,
            filter=profile_filter,
        ),
        models.Prefetch(
            query=models.SparseVector(indices=sparse_indices, values=sparse_values),
            using="sparse",
            limit=30,
            filter=profile_filter,
        ),
    ],
    query=models.FusionQuery(fusion=models.Fusion.RRF),
    limit=10,
    with_payload=True,
)
```

用途：

- 給一個 OCS 找相似 OCS。
- 給一段自然語描述找相近職務。
- 給 unit/block 找相似職能片段。

---

## 7. 情境 4：RAG Context Retrieval

v2 可先做 retrieval-only，不急著在本 repo 內產生 LLM 答案。

流程：

```text
query
  -> embed query
  -> hybrid search block chunks
  -> expand parent unit/profile
  -> return context + citations
```

### Small-to-big

每個 block hit 都附帶 parent unit context。

優點：

- citation 細。
- context 足夠。
- 實作簡單。

### Auto-merge

若 top-K blocks 多數落在同一個 unit，直接回傳 unit 作為 context。

優點：

- 適合問「某職務的一整段職責」。
- 減少重複 block。

風險：

- context 變大。
- citation 粒度較粗。

---

## 8. RAG Answer Engine

若 v3 要在本 repo 內加入 answer engine，需要額外決策：

- LLM provider。
- prompt template。
- citation 格式。
- hallucination guard。
- evaluation set。
- streaming / non-streaming。

目前不納入 v1，也不作 v2 必做項目。

---

## 9. 評估方向

v2 retrieval 評估建議：

- payload filter 正確率：K/S/T/O/P code 查詢。
- 相似職務 top-k：人工標註 30-50 組 query。
- hybrid vs dense-only：比較中文術語與代碼命中。
- small-to-big context 品質：人工檢查 citations。
- latency：不含 embedding 的 Qdrant query P50/P95。

---

## 10. 參考

- Qdrant hybrid queries: https://qdrant.tech/documentation/search/hybrid-queries/
- Qdrant overview: https://qdrant.tech/documentation/overview/
