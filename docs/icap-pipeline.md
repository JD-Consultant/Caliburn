# iCAP Parser + pgvector 向量嵌入流程

## 資料表結構

```sql
CREATE TABLE icap_embeddings (
    id          UUID PRIMARY KEY,
    ocs_code    TEXT NOT NULL,
    chunk_type  TEXT NOT NULL,
    chunk_text  TEXT NOT NULL,
    metadata    JSONB,
    embedding   vector(1536)
);
```

索引建議：
```sql
CREATE INDEX ON icap_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX ON icap_embeddings (chunk_type);
CREATE INDEX ON icap_embeddings (ocs_code);
```

---

## Chunk Types（9 種）

| chunk_type | 內容 | 查詢用途 |
|------------|------|---------|
| `competency` | 整體職能基準摘要 | `icap_matcher`：職種候選與三段式信心判斷 |
| `unit` | 職能單元描述 | ✅ **已接入候選排序**：與 competency 一起作 profile-level matching；訪談 prompt 注入仍為 P2 |
| `task` | 工作任務描述 | ✅ **已接入**：候選排序與 `task_extraction` 任務參考 |
| `indicator` | 行為指標文字 | ✅ **已接入**：`indicator` 節點注入官方指標語氣與格式範本 |
| `output` | 工作產出列表 | ✅ **已接入**：候選排序與 `five_w2h` 節點參考提示 |
| `knowledge` | 知識項目 | ✅ **已接入**：`ocs_builder` 節點 K 項 iCAP 代碼對應 |
| `skill` | 技能項目 | ✅ **已接入**：`ocs_builder` 節點 S 項 iCAP 代碼對應 |
| `attitude` | 態度項目 | ✅ **已接入**：`ocs_builder` 節點 A 項 iCAP 代碼對應 |
| `notes` | 說明與補充事項 | P2 backlog：訪談開始時注入學歷/年資要求 |

**已接入 RAG 查詢：8 種**（`competency`, `unit`, `task`, `indicator`, `output`, `knowledge`, `skill`, `attitude`）
**尚未接入：** `notes`；`unit` 已用於候選排序，但尚未注入一般訪談 prompt。

---

## RAG / iCAP 參考檢索點

| # | 觸發節點 | chunk_type | 函式 | 用途 |
|---|---------|-----------|------|------|
| 1 | `icap_rag_node` / `task_extraction_node` | `competency`, `unit`, `task`, `output`, `indicator` | `match_icap_candidates()` | 以 profile 與已萃取任務重新排名候選職種，決定三段式信心（`icap_mode`） |
| 2 | `task_extraction_node` | `task` | `search_tasks()` | 任務萃取後為每個任務附上 `icap_task_ref`，供使用者確認時參考 |
| 3 | `five_w2h_node` | `task`, `output`, `indicator`, `knowledge`, `skill` | `search_tasks()` / `search_outputs()` / `search_indicators()` / `search_knowledge()` / `search_skills()` | 追問 `workflow_steps`, `tools`, `outputs`, `quality_standards` 時產生 iCAP 參考提示泡泡 |
| 4 | `indicator_node` | `indicator` | `search_indicators()` | 行為指標生成前注入官方指標範本，統一語氣與 P/O code 格式 |
| 5 | `ocs_builder_node` | `knowledge` | `search_knowledge()` | 每個 K 項對應 iCAP 知識代碼 |
| 6 | `ocs_builder_node` | `skill` / `attitude` | `search_skills()` / `search_attitudes()` | 每個 S/A 項對應 iCAP 代碼 |

> RAG 觸發條件：`icap_mode` 為 `reference` 或 `hybrid` 時 (checkpoint 2~6 視節點條件啟用)；`company_defined` 時部分節點跳過 iCAP 注入。
> iCAP 是「信心與參考」來源，不是硬性準確率或套版依據；行為指標仍以企業訪談內容為主。

---

## iCAP Parser（`scripts/icap_parser.py`）

輸入：單一 iCAP 官方 JSON 檔案  
輸出：`list[TextNode]`（llama-index `TextNode`，僅作為資料容器，帶 `text`, `metadata`, `id_` 欄位）

> **llama-index 的使用範圍**：`requirements.txt` 安裝了 `llama-index==0.11.14`，但只在此處借用 `TextNode` 資料結構。實際 embedding 呼叫為 OpenAI SDK，向量寫入為 psycopg2 直接 INSERT，未使用 LlamaIndex pipeline / RAG / vector store 功能。

### Base metadata（所有 chunk 共享）
```python
{
    "ocs_code":        "DAT-001",
    "occupation_name": "資料庫管理師",
    "job_categories":  [{"name": "資訊服務業", "code": "J"}],
    "occupations":     [{"name": "資料庫管理師", "code": "2522"}],
    "industries":      [{"name": "電腦及電子產品製造業"}],
    "notes":           "學歷要求：大學以上...",
}
```

> `job_categories`/`occupations`/`industries` 儲存完整 `{name, code}` dict，支援 `icap_rag_node` 讀取職業代碼（`occ_code`）。

### Breadcrumb 欄位

每個 chunk 的 metadata 包含 `breadcrumb` 字串，表示該 chunk 在 iCAP 階層中的完整路徑，供 LLM 引用來源、debug 與 UI 顯示使用：

| chunk_type | breadcrumb 格式 | 範例 |
|---|---|---|
| `competency` | `{occupation_name} ({ocs_code})` | `資料庫管理師 (DAT-001)` |
| `notes` | `{occupation_name} ({ocs_code}) > 說明補充` | `資料庫管理師 (DAT-001) > 說明補充` |
| `unit` | `{occupation_name} ({ocs_code}) > {ocu_name} ({ocu_code})` | `資料庫管理師 (DAT-001) > 系統維運 (DAT-001-03)` |
| `task` | `... > {ocu_name} ({ocu_code}) > {task_name} ({task_code})` | `... > 系統維運 (DAT-001-03) > 資料庫維護 (T3.1)` |
| `indicator` | `... > {task_name} ({task_code}) > {indicator_code}` | `... > 資料庫維護 (T3.1) > P1.1.1` |
| `output` | `... > {task_name} ({task_code}) > {output_code}` | `... > 資料庫維護 (T3.1) > O1.1` |
| `knowledge` | `... > {task_name} ({task_code}) > {knowledge_code}` | `... > 資料庫維護 (T3.1) > K-INF-001` |
| `skill` | `... > {task_name} ({task_code}) > {skill_code}` | `... > 資料庫維護 (T3.1) > S-INF-001` |
| `attitude` | `{occupation_name} ({ocs_code}) > {attitude_code}` | `資料庫管理師 (DAT-001) > A-GEN-001` |

> `breadcrumb` 存於 metadata JSONB，需重新執行 `icap_ingest.py` 後才會寫入資料庫（已有資料不會自動更新）。

### Chunk 生成邏輯

1. **competency chunk**：`職能基準摘要：{occupation_name}\n{competency_level}\n{ocu_unit_names…}`
2. **unit chunks**：每個 OCU 一個 chunk，含 unit 名稱與所有任務名稱
3. **task chunks**：每個任務一個 chunk，含任務名稱、說明、task_codes
4. **indicator chunks**：每個行為指標一個 chunk，帶 `indicator_code`
5. **output chunks**：每個工作產出一個 chunk，帶 `output_code`
6. **knowledge chunks**：每個知識項目一個 chunk，含 `knowledge_code`
7. **skill chunks**：每個技能項目一個 chunk，含 `skill_code`
8. **attitude chunks**：每個態度項目一個 chunk，含 `attitude_code`
9. **notes chunk**：若有 `notes_and_appendix.requirements` 內容，產生一個 chunk

### task_codes 多值處理
```python
task_codes_raw = task_obj.get("task_codes", [])
all_codes_str  = " / ".join(f"{tc['code']} {tc['name']}" for tc in task_codes_raw)
```
metadata 儲存完整 `task_codes` list，顯示用 `all_codes_str`。

---

## Ingest Script（`scripts/icap_ingest.py`）

```bash
cd backend
python -m scripts.icap_ingest \
    --json-dir /path/to/icap-json \
    --batch-size 50
```

| 參數 | 說明 |
|------|------|
| `--json-dir` | iCAP JSON 檔案根目錄（會遞迴搜尋） |
| `--batch-size` | 每批 embed 節點數（default 50，避免 token limit） |
| `--dry-run` | 僅 parse + 印出，不寫 DB |
| `--resume` | 跳過 DB 已存在的 ocs_code |

### 執行流程
1. `_dedup_files()`：同一 `ocs_code` 只取第一個（去除官方重複版本）
2. `clear_ocs_code(conn, ocs_code)`：刪除舊資料後重新 upsert（idempotent）
3. 批次呼叫 `embed_texts()` → OpenAI embeddings API，帶 exponential backoff rate-limit retry
4. `upsert_nodes()` 使用 `ON CONFLICT (id) DO UPDATE`

---

## icap_retriever（`app/services/icap_retriever.py`）

提供 6 個非同步查詢函式，供各 LangGraph 節點呼叫；職種候選排序則由 `app/services/icap_matcher.py` 統一處理：

```python
# K/S/A（ocs_builder_node）
await search_knowledge("SQL 查詢語法 設計 ETL", top_k=1)
# → [{"code": "K-INF-001", "name": "資料庫查詢語言", "ocs_code": "DAT-001", "similarity": 0.82}]

await search_skills("Python 資料處理", top_k=1)
await search_attitudes("主動積極", top_k=1)

# Task / Output / Indicator（multi-granularity RAG）
await search_tasks("資料庫維護 效能監控", top_k=3, ocs_code_filter="DAT-001")
await search_outputs("維護報告 效能基準", top_k=3, ocs_code_filter="DAT-001")
await search_indicators("定期備份 還原測試", top_k=3, ocs_code_filter="DAT-001")
```

### 共用底層：`_search_ksa()`

所有 6 個函式共用同一 pgvector 查詢邏輯：

```sql
WITH deduped AS (
    SELECT DISTINCT ON (metadata->>:code_key)
        chunk_text, metadata,
        1 - (embedding <=> CAST(:vec AS vector)) AS similarity
    FROM icap_embeddings
    WHERE chunk_type = :chunk_type
      AND metadata->>:code_key IS NOT NULL
      [AND ocs_code = :ocs_code]   -- 可選 filter
    ORDER BY metadata->>:code_key, embedding <=> CAST(:vec AS vector)
)
SELECT * FROM deduped
WHERE similarity >= 0.58
ORDER BY similarity DESC
LIMIT :k
```

- `DISTINCT ON (code_key)`：每個官方代碼只出現一次，避免重複
- `similarity >= 0.58`：低信心結果不返回，避免錯誤注入
- `ocs_code_filter`（可選）：指定 OCS 代碼縮窄搜尋範圍，減少跨職種干擾

---

## 三段式信心判斷（`icap_matcher.py`）

`icap_matcher.py` 會依 profile-level query（職稱/部門/摘要/readiness 訊號）與 task-level query（已萃取任務）組合多個 chunk_type 的證據，計算候選職種的檢索信心。此分數是 retrieval confidence，不是使用者可解讀的百分比準確率。

| 信心層級 | 條件 | `icap_mode` |
|---------|------|------------|
| 高信心 | weighted similarity ≥ `ICAP_HIGH_THRESHOLD`（0.70）且證據覆蓋合理 | `"reference"` |
| 中信心 | weighted similarity ≥ `ICAP_MEDIUM_THRESHOLD`（0.55） | `"hybrid"` |
| 低信心 | weighted similarity < 0.55 | `"company_defined"` |

`icap_mode` 存入 `InterviewState` 並持久化至 `job_profiles.graph_state`，後續所有節點依此決定是否注入 iCAP 官方內容。

> 目前未採用職稱關鍵字硬性降權，也尚未實作 reranker / judge。百工百業的準確提升應靠任務證據、候選職種語意覆蓋與後續 reranker，而不是用職稱字面規則硬切。

---

## 已知問題與改善方向

> **P0 問題已於 2026-05-20 全部解決。**

### icap_standards 主資料表（第六階段 #23）

**現況**：只有 `icap_embeddings` 向量表，無法做版本管理與資料品質警告。

**目標**：新增 `icap_standards` 主表，`icap_embeddings` 以 `standard_id` 連回：

```sql
CREATE TABLE icap_standards (
    id                    UUID PRIMARY KEY,
    ocs_code              TEXT NOT NULL,
    ocs_name              TEXT NOT NULL,
    version               TEXT,
    normalized_status     TEXT,   -- active | historical | deprecated
    is_replaced           BOOLEAN DEFAULT FALSE,
    replaced_by           TEXT,
    raw_json              JSONB,
    data_quality_warnings JSONB,
    ingested_at           TIMESTAMPTZ DEFAULT now()
);
```

iCAP 原始資料可能出現版本狀態矛盾（`raw_status = "最新版本"` 但更新說明寫已被取代），需在 ingest 時正規化並記錄警告。

### embedding model 版本記錄（第六階段 #24）

**現況**：`text-embedding-3-small` 版本未記錄於 DB，若 OpenAI 更新模型，舊向量與新向量不可比較。

**目標**：`icap_embeddings` 加入 `embedding_model` 欄位，re-ingest 時記錄模型版本。

### unit / notes chunk 接入（第七階段 P2）

`unit` chunk 已用於候選排序；後續仍可在訪談節點注入職能單元參考。`notes` chunk 可在訪談開始時注入學歷/年資要求，目前列為第七階段 P2 backlog。
