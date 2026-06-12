# Retrieval and Future JD Authoring Service

本文件描述未來 JD Authoring RAG service 如何使用本 repo 建好的 Qdrant collection，以及 v1 indexer 只保留的 CLI smoke query。

v1 的正式範圍是索引與儲存：

- 不開 HTTP API。
- 不開 MCP server。
- 不提供穩定 Python retrieval SDK。
- 不組裝 LLM answer。
- 不產生職務說明書。
- 不承諾 `smoke-query` 輸出格式。

---

## 1. v1 Smoke Query

v1 smoke query 的目的只有驗證 Qdrant collection 寫入是否正確。

### 1.1 Count

```bash
uv run python -m jd_ocs_indexer.cli stats --collection ocs_bgem3_v2
```

預期：

- total points 約等於 profile + unit + block。
- `profile` 約 908。
- `unit` 約 3,272。
- `block` 約 8,689。

### 1.2 Retrieve by `ocs_code`

```bash
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v2 --ocs-code INM3513-009v1
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
- 驗證 `source_file`、hash、parent ids 存在。

### 1.3 Filter by K/S code

```bash
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v2 --knowledge K01 --skill S01
```

底層用 payload filter，不做 vector search：

```python
models.Filter(
    must=[
        models.FieldCondition(key="chunk_level", match=models.MatchValue(value="block")),
        models.FieldCondition(key="k_codes", match=models.MatchAny(any=["K01"])),
        models.FieldCondition(key="s_codes", match=models.MatchAny(any=["S01"])),
    ]
)
```

用途：

- 驗證 K/S code arrays 寫入正確。
- 驗證 payload indexes 正常。
- 驗證未來「能力/技能找職務」的資料基礎可行。

### 1.4 Dev-only vector probe

```bash
uv run python -m jd_ocs_indexer.cli smoke-query --collection ocs_bgem3_v2 --probe-vector "資料清理 報表 需求確認"
```

用途是確認 dense/sparse vectors 有正確寫入與可查，不是正式 retrieval API。

---

## 2. Future Service Boundary

正式查詢與 RAG 不在本 repo。建議另開 service repo，例如：

```text
jd-ocs-rag-service
jd-ocs-mcp
jd-ocs-query-api
```

該 repo 的責任：

- 接收使用者職務名稱與長段工作描述。
- 抽取工作活動候選項。
- 對 Qdrant 做 vector search / payload filter。
- 聚合候選 `ocs_code`、unit、block、K/S codes。
- 回讀完整 source JSON 組 JD context。
- 產生「你是否也會...」確認問題。
- 產生專屬職務說明書。

---

## 3. JD Authoring Retrieval Flow

### 3.0 重要：所有 query 預設加 `is_current=true` filter

908 份 OCS 含舊版本（v1/v2/v3/v4 並存於同一 collection）。Consumer 端寫 query 時建議**預設加**：

```python
models.FieldCondition(key="is_current", match=models.MatchValue(value=True))
```

避免推薦到已被取代的舊版本。只有審計、版本比對等特殊需求才查 `is_current=false`。

v2 indexer 保留此欄位但不強制 filter — 留給 consumer 決定政策。

### 3.1 使用者只給職務名稱

```text
query = user_job_title
search chunk_level = profile
top_k = 5
```

目的：

- 找候選 OCS 職務。
- 讓使用者確認哪個比較接近。
- 或與工作描述一起做 weighted ranking。

### 3.2 使用者給一大段工作內容

不要只搜尋整段一次。建議：

```text
whole description -> search profile/unit
activity extraction -> per-activity search unit/block
hits -> group by ocs_code, unit_id, k_codes, s_codes
```

例如使用者說：

```text
我會跟業務確認需求，整理 Excel 和資料庫資料，用 SQL 做清理，
建立 Power BI 報表，每週追蹤營運指標，也會跟主管說明異常原因。
```

future service 先拆成：

```text
1. 與業務確認資料或報表需求
2. 整理 Excel 與資料庫來源資料
3. 使用 SQL 清理資料
4. 建立 Power BI 報表
5. 每週追蹤營運指標
6. 向主管說明異常原因
```

每一項再搜尋 `unit` / `block`，避免長段 embedding 被平均後漏掉次要活動。

### 3.3 已知或已確認 `ocs_code`

拿標準任務不需要 vector search：

```python
models.Filter(
    must=[
        models.FieldCondition(key="ocs_code", match=models.MatchValue(value=ocs_code)),
        models.FieldCondition(
            key="chunk_level",
            match=models.MatchAny(any=["unit", "block"]),
        ),
        models.FieldCondition(key="is_current", match=models.MatchValue(value=True)),
    ]
)
```

用途：

- 列出該職務的標準 unit/block。
- 與使用者已描述活動做 coverage/gap comparison。
- 產生確認型提示。

---

## 4. Parent Expansion

block 命中很精準，但常常太碎。future service 可用 parent chunk id 補上下文：

```text
block hit
  -> unit_chunk_id
  -> retrieve unit Markdown

many block hits with same ocs_code
  -> profile_chunk_id
  -> retrieve profile Markdown
```

使用情境：

- block 命中「資料品質檢查」，用 parent unit 取得同組任務。
- 多個 block 命中同一職務，用 parent profile 取得職務定位。
- 組 small-to-big RAG context，不必馬上讀完整 JSON。

完整 JD draft 前仍建議用 `source_file` 回讀完整 JSON。

---

## 5. Full JSON Context

完整 JSON 不塞進 Qdrant。future service 需要完整背景時：

```text
hits
  -> group by source_file / ocs_code
  -> load source JSON from configured source root
  -> verify source_json_hash
  -> assemble JD context package
```

建議規則：

- 精準問答 / evidence retrieval：可只用 chunks + parent context。
- 撰寫完整職務說明書：應讀完整 JSON，整理後再給 LLM。
- 不把 raw JSON 原封不動塞給 LLM；應組成精簡 Markdown context。

---

## 6. Suggested Future Tools

未來 MCP/API 可設計成：

```python
def suggest_candidate_jobs(
    job_title: str | None,
    work_description: str,
    limit: int = 5,
) -> list[CandidateJob]: ...

def match_user_activities(
    work_description: str,
    candidate_ocs_codes: list[str] | None = None,
) -> list[ActivityMatch]: ...

def suggest_missing_work_tasks(
    confirmed_ocs_codes: list[str],
    confirmed_activities: list[str],
) -> list[Question]: ...

def suggest_knowledge_skills(
    matched_chunk_ids: list[str],
) -> KnowledgeSkillSummary: ...

def assemble_jd_context(
    confirmed_ocs_codes: list[str],
    confirmed_activities: list[str],
    include_full_json: bool = True,
) -> str: ...
```

這些工具都屬 future service，不在 indexer repo 實作。

---

## 7. Evaluation Direction

未來 service 評估建議：

- 職務候選 top-k：使用者職務名稱 + 工作描述能否找對相關 OCS。
- 活動 coverage：長段描述拆項後，每個活動是否命中合理 unit/block。
- gap suggestion quality：提示是否像「可能需要確認」而不是硬說使用者漏了。
- K/S 聚合品質：是否能合理歸納知識與技能。
- full JSON context：產生 JD 是否比只用 top-k chunks 更完整。
- latency：embedding + Qdrant query + parent retrieve + JSON load。

---

## 8. References

- Qdrant hybrid queries: https://qdrant.tech/documentation/search/hybrid-queries/
- Qdrant overview: https://qdrant.tech/documentation/overview/
