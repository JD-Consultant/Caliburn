# RAG 完整流程報告

## 一、全局架構

```
職稱 + 工作摘要
      │
      ▼
① icap_rag_node          ← RAG #1：competency 向量搜尋，決定 icap_mode
      │
      ▼
② interview_node         ← 無 RAG：AI 訪談，收集工作描述
      │
      ▼
③ task_extraction_node   ← LLM 萃取任務 + RAG #2：task 向量搜尋注入 icap_task_ref
      │
      ▼
④ five_w2h_node          ← 逐欄追問 5W2H + RAG #3：output 向量搜尋提示產出
      │
      ▼
⑤ star_node              ← 無 RAG：收集 STAR 案例
      │
      ▼
⑥ indicator_node         ← RAG #4：indicator 向量搜尋提供指標範本
      │
      ▼
⑦ ocs_builder_node       ← LLM 建 OCS 文件 + RAG #5/#6/#7：K/S/A 代碼對照
```

---

## 二、RAG 觸發點逐一說明

### RAG #1 — `icap_rag_node`：職稱命中判斷

**觸發**：流程起點，使用者輸入職稱 + 部門 + 工作摘要後立即執行。

**查詢**：
```
query      = "{job_title} {department} {job_summary}"
chunk_type = "competency"
```

**結果**：依 cosine similarity 決定 `icap_mode`，影響後續**所有** RAG 是否啟動：

| similarity | icap_mode | 後續行為 |
|---|---|---|
| ≥ 0.70 | `reference` | K/S 以 icap_official 為主 |
| ≥ 0.55 | `hybrid` | icap_official 與 company_defined 均衡 |
| < 0.55 | `company_defined` | 跳過所有 iCAP 注入 |

**輸出至 state**：`icap_candidates`（含 ocs_code）、`icap_mode`、`icap_hit`

---

### RAG #2 — `task_extraction_node`：任務對應 iCAP 官方代碼

**觸發**：LLM 從訪談對話萃取結構化任務列表後，`icap_mode != company_defined` 時執行。

**查詢**（每個任務並行執行）：
```
query           = "{task_name} {description}"
chunk_type      = "task"
top_k           = 1
ocs_code_filter = top_ocs_code   ← 縮窄到命中職種
```

**結果**：每個任務注入 `icap_task_ref`：
```json
{
  "code": "T2.3",
  "name": "資料庫效能監控",
  "ocs_code": "DAT-001",
  "similarity": 0.81
}
```

**用途**：任務清單呈現給使用者時顯示 `iCAP T2.3` 標籤，供確認參考。

---

### RAG #3 — `five_w2h_node`：產出欄位填寫建議

**觸發**：追問 `outputs` 欄位時，且 `icap_mode != company_defined`。

**查詢**：
```
query           = "{task_name} 工作產出"
chunk_type      = "output"
top_k           = 3
ocs_code_filter = top_ocs_code
```

**結果**：拼成提示文字附在問題後方：
```
（iCAP 參考：此類職務常見產出包含 維護報告、效能基準文件、備份日誌，可參考或自行描述）
```

**用途**：引導使用者填出符合 iCAP 規格的產出項，降低空白率。

---

### RAG #4 — `indicator_node`：行為指標語氣範本

**觸發**：`icap_mode != company_defined` 時，每個任務生成指標前執行。

**查詢**：
```
query           = "{task_name} {purpose} 行為指標"
chunk_type      = "indicator"
top_k           = 2
ocs_code_filter = top_ocs_code
```

**結果**：作為 prompt 的一個 section 注入給 LLM：
```
iCAP 參考指標範例（措辭參考，勿直接複製）：
  - 定期執行完整備份並驗證還原成功率達標
  - 監控資料庫效能指標並於閾值異常時回報
```

**用途**：統一 5W2H / ABCD 指標的措辭風格與 P/O code 格式，LLM 參考語氣但不直接複製。

---

### RAG #5/#6/#7 — `ocs_builder_node`：K/S/A 代碼對照

**觸發**：OCS 文件建立後，逐條 K/S/A 項目執行，僅 `source_type == "icap_official"` 的條目才查詢。

**三支獨立查詢**：

| RAG | query | chunk_type | top_k | 寫入欄位 |
|---|---|---|---|---|
| #5 | `"{k_name} {task_query}"` | `knowledge` | 1 | `icap_ref` |
| #6 | `"{s_name} {task_query}"` | `skill` | 1 | `icap_ref` |
| #7 | `"{a_name}"` | `attitude` | 1 | `icap_ref` |

**結果**：每條官方項目對應到 iCAP 代碼：
```json
{ "name": "資料庫查詢語言", "source_type": "icap_official", "icap_ref": "K-INF-001" }
```

---

## 三、RAG 共用底層：`_search_ksa()`（`app/services/icap_retriever.py`）

所有 RAG #2～#7 共用同一個 pgvector 查詢邏輯：

```sql
WITH deduped AS (
    SELECT DISTINCT ON (metadata->>:code_key)   -- 每個官方代碼只出現一次
        chunk_text, metadata,
        1 - (embedding <=> CAST(:vec AS vector)) AS similarity
    FROM icap_embeddings
    WHERE chunk_type = :chunk_type
      AND metadata->>:code_key IS NOT NULL
      [AND ocs_code = :ocs_code]               -- 可選：縮窄到特定職種
    ORDER BY metadata->>:code_key, embedding <=> CAST(:vec AS vector)
)
SELECT * FROM deduped
WHERE similarity >= 0.58                        -- 低信心直接過濾
ORDER BY similarity DESC
LIMIT :k
```

- `DISTINCT ON (code_key)`：每個官方代碼只出現一次，避免重複
- `similarity >= 0.58`：低信心結果不返回，避免錯誤注入
- `ocs_code_filter`（可選）：指定職種縮窄搜尋範圍，減少跨職種干擾

---

## 四、icap_mode 對各 RAG 的影響

| icap_mode | RAG #2 task | RAG #3 output | RAG #4 indicator | RAG #5/#6/#7 K/S/A |
|---|---|---|---|---|
| `reference` | ✅ 執行 | ✅ 執行 | ✅ 執行 | ✅ icap_official 為主 |
| `hybrid` | ✅ 執行 | ✅ 執行 | ✅ 執行 | ✅ icap_official + company_defined 混合 |
| `company_defined` | ❌ 跳過 | ❌ 跳過 | ❌ 跳過 | ❌ 全部 company_defined |

---

## 五、目前架構的已知限制

| 問題 | 影響 | 位置 |
|---|---|---|
| 單段式檢索，`top_k=1` 直接信任第一名 | K/S/A 代碼可能對錯 | `ocs_builder_node` |
| 無 reranker | `task_extraction` 的 `icap_task_ref` 精準度依賴 cosine | `task_extraction_node` |
| `unit` / `notes` chunk 尚未接入 | 訪談無法注入職能單元參考與學歷要求 | P2 backlog |
| `icap_standards` 主資料表缺失 | 無法做版本管理與資料品質警告 | 第六階段規劃 |
| embedding model 版本未記錄 | 模型升版後舊向量不可比較 | 第六階段規劃 |
