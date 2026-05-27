# 資料庫 Schema

## 總覽

```
users
  └── job_profiles
        ├── icap_references
        ├── interview_sessions
        ├── company_tasks
        │     └── ksa_items
        ├── ksa_items（profile 層級）
        └── document_versions

icap_embeddings（獨立向量表，與上方無 FK 關聯）
```

---

## 應用資料表

### `users`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | UUID PK | |
| `email` | TEXT UNIQUE | |
| `name` | TEXT | |
| `company` | TEXT | |
| `created_at` | TIMESTAMPTZ | |

---

### `job_profiles`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK → users | CASCADE DELETE |
| `job_title` | TEXT | 職稱 |
| `department` | TEXT | 部門 |
| `tenure_months` | INTEGER | 年資（月） |
| `primary_stakeholders` | TEXT[] | 主要利害關係人 |
| `job_summary` | TEXT | 工作摘要 |
| `stage` | TEXT | 流程階段（見下方 stage 值） |
| `completion_pct` | INTEGER | 完成百分比 0–100 |
| `icap_source_type` | TEXT | `icap_official` / `company_defined` |
| `document_draft` | JSONB | 草稿 OCS JSON |
| `graph_state` | JSONB | LangGraph 跨 call 持久化狀態（18 個 key） |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

**stage 值流轉**：
```
basic_info → icap_ref → interview → task_extraction
→ responsibility_grouping → star → five_w2h → indicator → ksa → preview（terminal）
```

---

### `icap_references`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | UUID PK | |
| `job_profile_id` | UUID FK → job_profiles | CASCADE DELETE |
| `icap_id` | TEXT | iCAP embedding 的 UUID（字串） |
| `icap_title` | TEXT | iCAP 職稱 |
| `similarity` | FLOAT | cosine similarity（0–1） |
| `match_reason` | TEXT | chunk_text 前 120 字 |
| `mismatch_notes` | TEXT | 不符說明 |
| `recommendation` | TEXT | `建議參考` / `部分參考` / `低信心` |
| `is_selected` | BOOLEAN | 是否被選用 |
| `created_at` | TIMESTAMPTZ | |

---

### `interview_sessions`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | UUID PK | |
| `job_profile_id` | UUID FK → job_profiles | CASCADE DELETE |
| `role` | TEXT | `ai` / `user` |
| `phase` | TEXT | `general` / `star_<task_id>` / `five_w2h_<task_id>` |
| `content` | TEXT | 訊息內容 |
| `extra_data` | JSONB | 預留擴充欄位 |
| `created_at` | TIMESTAMPTZ | |

> `phase` 由後端節點輸出決定（`accumulated.get("phase", message.phase)`），前端傳入的 phase 僅作 fallback。

---

### `company_tasks`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | UUID PK | |
| `job_profile_id` | UUID FK → job_profiles | CASCADE DELETE |
| `task_name` | TEXT | 任務名稱 |
| `description` | TEXT | 簡短描述 |
| `category` | TEXT | `核心職責` / `例行工作` / `協作任務` / `待確認` |
| `frequency` | TEXT | `每日` / `每週` / `每月` / `專案性` / `臨時性` |
| `importance` | TEXT | 預設 `中` |
| `responsibility_type` | TEXT | `主責` / `協作` / `支援` |
| `sort_order` | INTEGER | 顯示排序 |
| `situation` | TEXT | 5W2H — 情境 |
| `purpose` | TEXT | 5W2H — 目的 |
| `stakeholders` | TEXT[] | 5W2H — 利害關係人 |
| `workflow_steps` | TEXT[] | 5W2H — 執行步驟 |
| `inputs` | TEXT[] | 5W2H — 輸入 |
| `outputs` | TEXT[] | 5W2H — 產出 |
| `tools` | TEXT[] | 5W2H — 工具/系統 |
| `collaborators` | TEXT[] | 5W2H — 協作對象 |
| `quality_standards` | TEXT[] | 5W2H — 品質標準 |
| `time_standards` | TEXT[] | 5W2H — 時效標準 |
| `quantity_standards` | TEXT[] | 5W2H — 數量標準 |
| `risks_or_common_errors` | TEXT[] | 5W2H — 風險/常見錯誤 |
| `evidence_from_user` | TEXT | 工作者原話摘錄 |
| `star_case` | JSONB | `{S, T, A, R}` 四槽 |
| `behavior_indicator_5w2h` | TEXT | 行為指標 5W2H 版 |
| `behavior_indicator_abcd` | TEXT | 行為指標 ABCD 版 |
| `icap_mapping` | JSONB | iCAP 代碼對照 |
| `completeness_pct` | INTEGER | 完成度 0–100 |
| `missing_fields` | TEXT[] | 待補欄位清單 |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

---

### `ksa_items`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | UUID PK | |
| `job_profile_id` | UUID FK → job_profiles | CASCADE DELETE |
| `task_id` | UUID FK → company_tasks | SET NULL（允許 profile 層級的 K/S/A） |
| `ksa_type` | TEXT | `K` / `S` / `A` |
| `content` | TEXT | 項目內容 |
| `source_type` | TEXT | `icap_official` / `company_defined` |
| `icap_ref` | TEXT | iCAP 代碼（如 `K-INF-001`） |
| `confirmed` | BOOLEAN | 是否已人工確認 |
| `created_at` | TIMESTAMPTZ | |

---

### `document_versions`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | UUID PK | |
| `job_profile_id` | UUID FK → job_profiles | CASCADE DELETE |
| `version` | INTEGER | 版本號，從 1 開始 |
| `format` | TEXT | `pdf` / `docx` / `xlsx` / `json` |
| `file_path` | TEXT | 檔案路徑（匯出檔） |
| `content` | JSONB | 凍結的 OCS JSON 內容 |
| `status` | TEXT | `draft` / `frozen` |
| `created_at` | TIMESTAMPTZ | |

---

## 向量資料表

### `icap_embeddings`

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | UUID PK | 由 `icap_parser.py` 產生 |
| `ocs_code` | TEXT | 職種代碼（如 `DAT-001`） |
| `chunk_type` | TEXT | 9 種 chunk type（見 icap-pipeline.md） |
| `chunk_text` | TEXT | 嵌入的文字內容 |
| `metadata` | JSONB | 包含 breadcrumb、階層代碼等（見 icap-pipeline.md） |
| `embedding` | vector(1536) | OpenAI text-embedding-3-small 產生 |

**建議索引**：
```sql
CREATE INDEX ON icap_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX ON icap_embeddings (chunk_type);
CREATE INDEX ON icap_embeddings (ocs_code);
```

> 詳細 chunk 結構與 metadata 欄位說明見 [icap-pipeline.md](./icap-pipeline.md)。

---

## graph_state 持久化欄位（`job_profiles.graph_state`）

`graph_state` JSONB 由 `StateService` 統一管理，儲存以下 18 個 LangGraph 狀態欄位：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `extracted_tasks` | list | 結構化任務列表（含 5W2H、icap_task_ref） |
| `responsibility_groups` | list | 已確認或待確認的主要職責分組（`responsibility_id`, `title`, `task_ids`） |
| `responsibility_grouping_round` | int | 主要職責分組輪次（0=未分組，1+=已展示） |
| `current_task_index` | int | 當前處理的任務索引 |
| `task_extraction_round` | int | 萃取輪次（0=未萃取，1+=已展示） |
| `missing_fields` | list | 5W2H 待補欄位 |
| `star_slots_by_task` | dict | `{task_id: {S, T, A, R}}` |
| `star_completed_task_ids` | list | 已完成 STAR 的 task_id 列表 |
| `behavior_indicators` | list | 每個 output 的行為指標 |
| `indicator_retry_counts` | dict | `{task_id: int}` 品質重試計數 |
| `ksa_items` | list | flat KSA 列表（backward compat） |
| `ocs_document` | dict | 完整 OCS JSON（含 evidence_refs / display_labels） |
| `icap_candidates` | list | iCAP 候選職種（含 ocs_code、similarity） |
| `icap_hit` | bool | 是否命中 iCAP |
| `icap_mode` | str | `reference` / `hybrid` / `company_defined` |
| `interview_readiness_detail` | dict | 6 信號評分明細 |
| `interview_ready` | bool | readiness score >= 0.70 |
| `interview_ready_confirmed` | bool | 用戶已回應過渡訊息 |
