# REST API 端點參考

Base URL: `http://localhost:8000/api/v1`

---

## Users

### `POST /users`
建立使用者。

**Body**
```json
{ "email": "user@example.com", "name": "王小明", "company": "XX 企業" }
```

**Response 201**
```json
{ "id": "uuid", "email": "...", "name": "...", "company": "...", "created_at": "..." }
```

### `GET /users/{user_id}`
取得使用者資料。

---

## Job Profiles

> 目前以 `?user_id=<uuid>` query param 傳遞身份，正式版改 JWT。

### `POST /job-profiles?user_id={uuid}`
新增職務檔案。

**Body**
```json
{
  "job_title": "資料工程師",
  "department": "資訊部",
  "tenure_months": 24,
  "primary_stakeholders": ["PM", "DS"],
  "job_summary": "負責 ETL pipeline 開發與維護"
}
```

**Response 201** → `JobProfileOut`（包含 `id`, `stage: "basic_info"`, `completion_pct: 0`）

### `GET /job-profiles?user_id={uuid}`
列出所有職務（`limit`, `offset` 分頁）。

### `GET /job-profiles/{profile_id}`
取得單一職務（含 `graph_state`）。

### `PATCH /job-profiles/{profile_id}`
更新基本資料或 `stage`/`completion_pct`。

### `DELETE /job-profiles/{profile_id}`
刪除職務（CASCADE 刪除所有子資料）。

---

## Interviews

### `GET /interviews/{profile_id}/history`
取得對話歷史。

Query params: `limit` (default 200), `offset` (default 0)

**Response**
```json
[
  { "role": "ai",   "content": "...", "phase": "general",         "created_at": "..." },
  { "role": "user", "content": "...", "phase": "star_task_001",   "created_at": "..." }
]
```

### `POST /interviews/{profile_id}/chat`
送出訊息，觸發 LangGraph，回傳 SSE 串流。

**Body**
```json
{ "content": "我主要負責每日的 ETL 排程監控", "phase": "general" }
```

**Response** `text/event-stream`
```
data: {"type":"message","kind":"summary","stage":"task_extraction","phase":"general","node":"task_extraction","content":"我整理出 4 項任務..."}
data: {"type":"message","kind":"reference","stage":"five_w2h","phase":"five_w2h_task_001","node":"five_w2h","content":"iCAP 參考提示：這類任務常見產出包含..."}
data: {"type":"message","kind":"question","stage":"five_w2h","phase":"five_w2h_task_001","node":"five_w2h","content":"關於「資料清理」，我還需要了解一個細節..."}
data: "[DONE]"
```

每個 `data:` 是一個 JSON event。`kind` 目前包含 `summary` / `question` / `reference` / `status` / `error`；前端會把每個 message event 顯示成獨立 AI 泡泡，因此 iCAP 參考提示和正式提問不會黏在同一泡泡。

**phase 值**
| 值 | 說明 |
|----|------|
| `general` | 訪談初期、任務萃取階段 |
| `star_<task_id>` | STAR 深度追問特定任務（例如 `star_task_001`） |
| `five_w2h_<task_id>` | 5W2H 補洞特定任務（例如 `five_w2h_task_001`） |

> `task_id` 由系統分配（`task_001`, `task_002`…），穩定不受 LLM 重新命名影響。前端讀取 `GET /job-profiles/{id}/state` 中的 `graph_state.extracted_tasks[].task_id` 即可取得對應值。

---

## Tasks

### `GET /tasks/{profile_id}`
取得職務下所有 CompanyTask 列表（含完整度百分比）。

### `PATCH /tasks/{task_id}`
手動更新任務欄位（供前端補充資料）。

---

## Job Profiles（補充端點）

### `GET /job-profiles/{profile_id}/state` ✅ 已實作
取得目前 graph state 摘要（輕量輪詢，頁面重整後恢復）。

**Response**
```json
{
  "stage": "responsibility_grouping",
  "graph_state": {
    "extracted_tasks": [...],
    "responsibility_groups": [...],
    "responsibility_grouping_round": 1,
    "current_task_index": 1,
    "star_slots_by_task": {...},
    "behavior_indicators": [...],
    "interview_readiness_detail": {...},
    "interview_ready": true,
    "interview_ready_confirmed": true
  }
}
```

---

## Documents

### `GET /documents/{profile_id}/preview` ✅ 已實作
取得預覽版 OCS JSON（含 behavior_indicators、ksa_items）。

**前提條件**：`JobProfile.stage` 為 `ksa` 或 `preview`。

**Response**
```json
{
  "ocs_document": { ... },
  "behavior_indicators": [...],
  "ksa_items": [...]
}
```

### `POST /documents/{profile_id}/freeze` ✅ 已實作
鎖定文件版本，設 `stage = "preview"`（terminal state，不再觸發 graph 節點）。

**Response 200**
```json
{ "status": "frozen", "version_id": "uuid" }
```

錯誤：`404` profile 不存在；`400` 無 ocs_document 可凍結。

### `POST /documents/{profile_id}/export?format={format}`
匯出職能文件。

**格式** `docx` | `pdf` | `xlsx` | `json`

**前提條件**：`JobProfile.stage` 必須為 `ksa` 或 `preview`，否則回傳 422。

**Response**
- `json` → `application/json`（`Content-Disposition: attachment; filename=<ocs_code>.json`）
- 其他 → 對應 MIME，`FileResponse`

**filename 規則**：`<ocs_code>.<format>`，例如 `DAT-001.xlsx`

### `GET /documents/{profile_id}/versions`
列出此職務的匯出版本紀錄（`id`, `format`, `status`, `created_at`）。

---

## Health Check

### `GET /health`
```json
{ "status": "ok", "db": true, "app": "JobIntel AI" }
```
`db: false` 表示資料庫連線失敗（`status: "degraded"`）。

---

## 已知問題與改善方向（Review 結論）

### 身份驗證（P1）

**現況**：`user_id` 以 query param 傳入，僅適合原型。

**目標**：改為 JWT / session token，加入 `company_id` tenant isolation，並補：
- profile owner check
- export file permission check
- API rate limit
- Graph execution lock（避免同一 profile 同時觸發兩次 AI 流程）

### 建議新增端點（待實作）

```
✅ GET  /job-profiles/{id}/state              # 已實作（2026-05-20）
⏸  POST /job-profiles/{id}/resume             # SSE 中斷後恢復（P1，延後）
⏸  POST /tasks/{task_id}/confirm              # 工作者確認任務內容（延後；目前由前端按鈕+chat處理）
⏸  POST /tasks/{task_id}/regenerate-indicator # 重新生成單一任務行為指標（延後）
⏸  GET  /icap/candidates/{profile_id}         # 取得目前 iCAP 候選清單（P1，延後）
⏸  POST /icap/retrieve                        # 手動觸發多粒度 iCAP 檢索（P1，延後）
✅ GET  /documents/{profile_id}/preview       # 已實作（2026-05-20）
✅ POST /documents/{profile_id}/freeze        # 已實作（2026-05-20）
```

### SSE 中斷恢復（P1）

**現況**：SSE 連線中斷後無法續接，使用者需重新送出訊息。

**目標**：前端保存 `Last-Event-ID`，後端支援從上次中斷點續串流。
