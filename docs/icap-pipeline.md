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
| `competency` | 整體職能基準摘要 | `icap_rag` 節點：職稱命中判斷（三段式信心） |
| `unit` | 職能單元描述 | P2 backlog：訪談節點注入任務參考 |
| `task` | 工作任務描述 | ✅ **已接入**：`task_extraction` 節點任務萃取時注入 iCAP 官方任務參考 |
| `indicator` | 行為指標文字 | ✅ **已接入**：`indicator` 節點注入官方指標語氣與格式範本 |
| `output` | 工作產出列表 | ✅ **已接入**：`five_w2h` 節點注入 iCAP 官方產出清單 |
| `knowledge` | 知識項目 | ✅ **已接入**：`ocs_builder` 節點 K 項 iCAP 代碼對應 |
| `skill` | 技能項目 | ✅ **已接入**：`ocs_builder` 節點 S 項 iCAP 代碼對應 |
| `attitude` | 態度項目 | ✅ **已接入**：`ocs_builder` 節點 A 項 iCAP 代碼對應 |
| `notes` | 說明與補充事項 | P2 backlog：訪談開始時注入學歷/年資要求 |

**已接入 RAG 查詢：7 種**（`competency`, `task`, `indicator`, `output`, `knowledge`, `skill`, `attitude`）  
**尚未接入：** `unit`, `notes`（P2 backlog）

---

## 6 個 RAG 檢索點

| # | 觸發節點 | chunk_type | 函式 | 用途 |
|---|---------|-----------|------|------|
| 1 | `icap_rag_node` | `competency` | `pgvector cosine` 直接查 | 職稱對應 iCAP 代碼，決定三段式信心（`icap_mode`） |
| 2 | `task_extraction_node` | `task` | `search_tasks()` | 任務萃取時注入 iCAP 官方任務描述，引導 LLM 對齊標準名稱 |
| 3 | `five_w2h_node` | `output` | `search_outputs()` | 5W2H 填洞時注入官方產出清單，提示 LLM 補齊 output 欄位 |
| 4 | `indicator_node` | `indicator` | `search_indicators()` | 行為指標生成前注入官方指標範本，統一語氣與 P/O code 格式 |
| 5 | `ocs_builder_node` | `knowledge` | `search_knowledge()` | 每個 K 項對應 iCAP 知識代碼 |
| 6 | `ocs_builder_node` | `skill` / `attitude` | `search_skills()` / `search_attitudes()` | 每個 S/A 項對應 iCAP 代碼 |

> RAG 觸發條件：`icap_mode` 為 `reference` 或 `hybrid` 時 (checkpoint 2~6 視節點條件啟用)；`company_defined` 時部分節點跳過 iCAP 注入。

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

## icap_ksa_rag（`app/services/icap_ksa_rag.py`）

提供 6 個非同步查詢函式，供各 LangGraph 節點呼叫：

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

## 三段式信心判斷（`icap_rag_node`）

`icap_rag_node` 執行 competency chunk 向量搜尋後，依以下邏輯設定 `icap_mode`：

| 信心層級 | 條件 | `icap_mode` |
|---------|------|------------|
| 高信心 | profile similarity ≥ `ICAP_HIGH_THRESHOLD`（0.70）且 task_match_rate 高 | `"reference"` |
| 中信心 | similarity ≥ `ICAP_MEDIUM_THRESHOLD`（0.55）（職稱或任務部分符合） | `"hybrid"` |
| 低信心 | similarity < 0.55 或任務幾乎不匹配 | `"company_defined"` |

`icap_mode` 存入 `InterviewState` 並持久化至 `job_profiles.graph_state`，後續所有節點依此決定是否注入 iCAP 官方內容。

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

`unit` chunk 可在訪談節點注入職能單元參考，`notes` chunk 可在訪談開始時注入學歷/年資要求，目前列為第七階段 P2 backlog。
