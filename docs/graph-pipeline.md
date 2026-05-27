# LangGraph 訪談狀態機

## 流程總覽

```
START
  │ entry_router（依 current_stage 跳入）
  ▼
icap_rag ──────────────────────────────────► interview
                                               │
                      [readiness_score < 0.70] │ [readiness_score >= 0.70 + 用戶已回應過渡訊息]
                                   ↓ END        ▼
                               task_extraction
                                   │
                    [round <= 1 or 未確認] │ [用戶確認]
                              ↓ END        ▼
                         responsibility_grouping
                                  │
                 [round <= 1 or 未確認] │ [用戶確認]
                             ↓ END        ▼
                              ┌──────────────────────────────────────┐
                              │     逐任務迴圈（per-task loop）        │
                              │                                       │
                              │  star ──► [四槽未全填] ──► END        │
                              │   │                                   │
                              │  [S/T/A/R 四槽完成（當前任務）]        │
                              │   ▼                                   │
                              │  five_w2h ──► [仍有缺欄] ──► END      │
                              │   │                                   │
                              │  [當前任務所有欄位齊全]                 │
                              │   ▼                                   │
                              │  indicator ──► [品質不足] ──► five_w2h│
                              │   │                                   │
                              │  [還有下一個任務] ─────────────► star  │
                              └──────────────────────────────────────┘
                                   │
                              [全部任務完成]
                                   ▼
                                  ksa (ocs_builder)  ← 注入 display_labels
                                   │
                                  END  （preview 為 terminal state）
```

## 節點說明

### 1. `icap_rag` — iCAP RAG 檢索
**檔案**: `app/graph/nodes/icap_rag.py`

- 透過 `app/services/icap_matcher.py` 以職稱、部門、工作摘要先找出 iCAP 候選職種
- 目前主軸仍是向量相似度 + 三段式信心，不用職稱關鍵字硬性過濾百工百業
- 回傳 `icap_candidates`（含 `ocs_code`, `icap_title`, `similarity`, `confidence_label`, `recommendation` 等）
- 依信心設定 `icap_mode`：`reference` / `hybrid` / `company_defined`

### 2. `interview` — 自然訪談
**檔案**: `app/graph/nodes/interview.py`

- System Prompt 帶入職稱/部門/工作摘要
- 保留最近 20 則對話歷史（避免 token 過長）
- 每次只問一個追問問題；引導工作者描述工具、產出、品質標準

**轉換條件**（`route_after_interview`）：需同時滿足：
1. `interview_readiness_score >= 0.70`（READY_THRESHOLD）
2. `interview_ready_confirmed == True`（用戶已回應過「接下來整理清單」的過渡訊息）

**兩段式 readiness 確認**（防止同 call 內提前跳轉）：
- 第一次達標：interview_node 顯示「接下來整理任務清單」過渡訊息，`interview_ready=True, interview_ready_confirmed=False`
- 用戶回應後第二次進入：interview_node 回傳空 ai_response，設 `interview_ready_confirmed=True`，route 才放行到 task_extraction

分數由 `compute_readiness()` 計算，6 個信號加權（總權重 7）：
- `tasks`（權重 2）：含任務動詞的句子 ≥ 2 句，或有序列舉 ≥ 2 項
- `outputs`（權重 1）：報告/文件/清單等 24 個產出關鍵詞
- `tools`（權重 1）：ERP/Excel/SAP 等 30+ 個工具/系統名
- `stakeholders`（權重 1）：客戶/廠商/部門等 30+ 個關係人詞
- `quality`（權重 1）：時效/KPI/幾天內等品質標準詞
- `context`（權重 1）：每天/定期/月初等頻率詞

分數 < 0.45 繼續訪談；0.45–0.70 補問最高優先的缺漏信號；>= 0.70 進入兩段式確認。

### 3. `task_extraction` — 任務萃取
**檔案**: `app/graph/nodes/task_extraction.py`

- 以全部對話 + 固定 prompt 呼叫 LLM（temperature=0）
- 輸出 JSON 陣列，每個任務包含：`task_name`, `description`, `category`, `frequency`, `responsibility_type`, `evidence_from_user`, `collaborators`, `stakeholders`, `tools`, `outputs`, `workflow_steps`, `uncertainty_fields`
- 若 `icap_mode != company_defined`，會以任務名稱/描述重新查 iCAP task chunk，附上 `icap_task_ref` 作為參考；這不是硬性準確率判定
- 每呼叫一次 `task_extraction_round += 1`
- 第一次呼叫後停在 END 等用戶確認；用戶說純「確認/好/OK/繼續…」後 → `responsibility_grouping`
- 若使用者提出修正，會保留既有 `task_id` 並重新整理任務清單

### 4. `responsibility_grouping` — 主要職責分組
**檔案**: `app/graph/nodes/responsibility_grouping.py`

- 將已確認的 `extracted_tasks` 整理成 1–5 個主要職責分組
- 每個分組包含：`responsibility_id`, `title`, `description`, `task_ids`
- 規則：不新增任務；每個任務必須且只能出現在一個主要職責
- 若 iCAP 有參考基準，只作命名風格與架構參考，不硬套官方職類
- 第一次產生後停在 END 等使用者確認；確認後才進入 STAR
- 使用者可用自然語言修正，例如「把 API 測試移到後端服務開發」

### 5. `star` — STAR 深度追問
**檔案**: `app/graph/nodes/star.py`

- 針對 `extracted_tasks[current_task_index]` 進行 STAR 框架追問
- **新任務判斷**：若 DB 中尚無以 `phase == "star_<task_id>" and role == "ai"` 的訊息，視為首次進入此任務，`user_input` 清空（防止前一輪確認語誤填槽位）。用 **AI 訊息** 判斷而非 user 訊息（前端 phase 可能為 "general"，不可靠）
- **Slot filling**：LLM 從 user_input 萃取 S/T/A/R 槽位，允許一次填多槽；`_MIN_SLOT_LEN = 4`（支援中文短答）
- **Synthesis fallback**：若已重問同一槽位且用戶仍無法填入，LLM 從已知 S/A/R 上下文推斷合理內容，避免無限迴圈
- **完成條件**：四槽皆非 null → `current_stage = "five_w2h"`，進入同任務的 5W2H 補洞
- **安全 fallback**：若 `idx >= len(tasks)`（例如狀態異常），路由到 `"ksa"` 而非 `"five_w2h"`

> AI 訊息 phase 由 `interviews.py` 以 `accumulated.get("phase", message.phase)` 寫入 DB，確保節點輸出的 phase（`"star_task_001"`）正確持久化。

`star_slots_by_task` 格式（以 `task_id` 為 key，非 `task_name`）：
```python
{
  "task_001": {
    "S": "每月月底彙整業績報表時",
    "T": "負責合併各區資料並產出摘要",
    "A": "從 ERP 匯出原始資料，用 Python 清洗合併",
    "R": "準時提交月報，誤差率降低 30%"
  }
}
```

> `task_id` 由 `task_extraction_node` 於萃取後立即分配（`task_001`, `task_002`…），穩定不受 LLM 重新命名影響。`phase` 也以 `task_id` 構建：`star_task_001`、`five_w2h_task_001`。

### 6. `five_w2h` — 5W2H 補洞
**檔案**: `app/graph/nodes/five_w2h.py`

必填欄位（`FIVE_W2H_REQUIRED`，共 9 欄）：

| 欄位 | 問題 |
|------|------|
| `situation` | 這項工作在什麼時候、什麼場景下發生？ |
| `purpose` | 做這項工作的目的是什麼？ |
| `collaborators` | 需要跟誰協作？跨部門合作情況？（list）✦ |
| `stakeholders` | 需要面對誰、服務誰、或影響誰？（list） |
| `tools` | 使用哪些系統、工具、表單？（list） |
| `workflow_steps` | 具體怎麼做？步驟是什麼？（list）✦ |
| `outputs` | 最後產出什麼？（list） |
| `quality_standards` | 怎樣才算做好？（list） |
| `time_standards` | 有時效要求嗎？多久要完成？✦ |

> ✦ = P0 新增欄位，用於讓行為指標包含協作邊界、執行步驟與時效標準。

每輪只問一個欄位；前一輪的用戶回答存回 `extracted_tasks[idx]`。
當補問 `workflow_steps`, `tools`, `outputs`, `quality_standards` 且 `icap_mode != company_defined` 時，節點會先送出 `kind="reference"` 的 iCAP 參考提示，再送出 `kind="question"` 的正式問題。前端會顯示成兩個泡泡，避免「參考資料 + 提問」黏在同一段。
所有欄位補齊 → `current_stage = "indicator"`（同任務），進入指標生成。

### 7. `indicator` — 行為指標生成（含品質評分與 Guardrail）
**檔案**: `app/graph/nodes/indicator.py`

- 逐任務處理（以 `task_id` 追蹤已完成任務，防止重入）
- **Per-output 模式**（Stage 4 #18）：若任務有 `outputs` list，每個 output 生成獨立指標；無 outputs 時 fallback 為整任務單一指標
- iCAP indicator 僅作措辭與格式參考；行為指標仍要呈現企業內部知識體系，不限制成基準式短句
- 每筆指標包含：
  - `indicator_5w2h`：「在【情境】下，為了【目的】，…，產出【此具體產出物】，達到【標準】。」
  - `indicator_abcd`：「面對【對象】，能…達到…標準。」
  - `output_name`：對應的產出物名稱（單一指標模式為空字串）
- **Guardrail**：若任務缺少必填欄位 → 退回 `five_w2h`
- **品質評分**：LLM 同 call 自評 7 維度，score = hits/7（per-output 模式取平均）

| 維度 | 對應欄位 |
|------|---------|
| `has_situation` | situation |
| `has_purpose` | purpose |
| `has_collaborators` | collaborators |
| `has_tools` | tools |
| `has_action` | workflow_steps |
| `has_output` | outputs |
| `has_standard` | quality_standards / time_standards |

- `quality_score >= 0.60` → 通過，存入 `behavior_indicators`（`quality_status: "ok"`），`current_stage = "star"`（下一個任務）或 `"ksa"`（全部完成）
- `quality_score < 0.60`，首次失敗 → 清除弱欄位，退回 `five_w2h` 補問（同任務），`indicator_retry_counts[task_id] += 1`
- 第二次仍不足 → 強制接受（`quality_status: "force_accepted"`），`display_label` 標為 `[待確認]`

`behavior_indicators` 每筆格式：
```python
{
  "task_id":        "task_001",
  "task_name":      "設計 ETL Pipeline",
  "output_name":    "ETL 排程腳本",    # per-output；單一指標模式為 ""
  "indicator_5w2h": "在每月月底…",
  "indicator_abcd": "面對 PM，能…",
  "quality_score":  0.86,
  "quality_status": "ok"              # "ok" | "force_accepted"
}
```

**逐任務路由（`route_after_indicator`）**：
- `current_stage == "five_w2h"` → 退回 five_w2h（Guardrail 或品質不足）
- `current_stage == "star"` → 前往 star（下一任務）
- 其他 → 前往 ksa（全部完成）

### 8. `ksa` / `ocs_builder` — OCS 文件生成
**檔案**: `app/graph/nodes/ocs_builder.py`

（節點名稱是 `ksa`，函式是 `ocs_builder_node`）

流程：
1. Idempotency guard：若 `document_ready == True` 且 `ocs_document` 已存在 → 直接返回空 delta（preview terminal state 保護）
2. 以 LLM 生成原始 OCS JSON（`_OCS_BUILD_PROMPT`，temperature=0.2）
3. `_enrich_and_assign_codes()` 賦予階層式代碼 + RAG 對應 K/S/A 至 iCAP code
4. `_attach_evidence_to_ocs_task()` 將 STAR / 5W2H 資料注入 `evidence_refs`
5. `_compute_display_labels()` / `_primary_display_label()` 計算並注入每個 task / indicator / output / KSA 的 `display_label` 與 `display_labels`
6. `_apply_responsibility_groups()` 依已確認的 `responsibility_groups` 決定 OCU 主要職責與任務歸屬
7. `_extract_legacy_ksa()` 產生 flat KSA 列表（backward compat）
8. 設定 `document_ready = True`, `current_stage = "preview"`

---

## InterviewState 欄位

```python
class InterviewState(TypedDict):
    # 基本資料
    job_profile_id: str
    job_title: str
    department: str
    job_summary: str

    # 流程控制
    current_stage: str    # basic_info → icap_ref → interview → task_extraction
                          # → responsibility_grouping → star → five_w2h → indicator
                          # → ksa → preview（terminal）
    phase: str            # general | star_<task_id> | five_w2h_<task_id>

    # 對話
    messages: list[dict]  # [{ role, content, phase }]
    user_input: str
    ai_response: str

    # iCAP RAG
    icap_candidates: list[dict]
    icap_hit: bool
    icap_mode: str        # "reference" | "hybrid" | "company_defined"（三段式信心判斷）

    # 任務萃取
    extracted_tasks: list[dict]
    responsibility_groups: list[dict]
    responsibility_grouping_round: int  # 0=未分組, 1=已展示等確認, 2+=已確認進 STAR
    current_task_index: int
    task_extraction_round: int    # 0=未萃取, 1=已展示等確認, 2+=已確認進主要職責分組

    # STAR slot filling
    star_slots_by_task: dict      # { task_id: { "S": str|None, "T": str|None, "A": str|None, "R": str|None } }
    star_completed_task_ids: list[str]  # task_id 列表

    # 5W2H
    missing_fields: list[str]

    # 訪談成熟度（每 call 重算；detail 持久化供前端顯示）
    interview_readiness_score: float
    interview_readiness_detail: dict   # ReadinessResult dict（6 信號明細）
    interview_ready: bool              # score >= 0.70
    interview_ready_confirmed: bool    # True = 用戶已回應過渡訊息，可進 task_extraction

    # 行為指標品質
    indicator_retry_counts: dict  # { task_id: int }，防止無限補問迴圈

    # 最終輸出
    behavior_indicators: list[dict]   # [{task_id, task_name, output_name, indicator_5w2h, indicator_abcd, quality_score, quality_status}]
    ksa_items: list[dict]             # 舊格式 flat KSA（backward compat）
    ocs_document: dict                # 完整 OCS JSON 結構（含 evidence_refs / display_labels）
    document_ready: bool
```

跨 API call 持久化欄位（存入 `job_profiles.graph_state` JSONB，由 `_PERSISTENT_STATE_KEYS` 管理）：
`extracted_tasks`, `responsibility_groups`, `responsibility_grouping_round`,
`current_task_index`, `task_extraction_round`, `missing_fields`,
`star_slots_by_task`, `star_completed_task_ids`,
`behavior_indicators`, `indicator_retry_counts`,
`ksa_items`, `ocs_document`,
`icap_candidates`, `icap_hit`, `icap_mode`,
`interview_readiness_detail`, `interview_ready`, `interview_ready_confirmed`

---

## entry_router 對應表

```python
_STAGE_TO_NODE = {
    "basic_info":      "icap_rag",
    "icap_ref":        "icap_rag",
    "interview":       "interview",
    "task_extraction": "task_extraction",
    "responsibility_grouping": "responsibility_grouping",
    "star":            "star",
    "five_w2h":        "five_w2h",
    "indicator":       "indicator",
    "ksa":             "ksa",
    "preview":         END,   # terminal state — 不再觸發任何節點
    "completed":       END,
}
```

---

## 已知問題與改善方向（Review 結論）

> **P0 問題已於 2026-05-20 全部解決。** **第一~四階段主要 bug 已於 2026-05-20 修復（含 5 個關鍵 bug，詳見 roadmap.md 第四階段）。** 以下保留原始問題描述與解決方式供參考。

### ✅ interview → task_extraction 轉換條件（P0 已解決）

~~**現況**：用戶訊息達 3 則即進入 `task_extraction`~~

**已實作**：改為 `interview_readiness_score` 六維加權評分（score >= 0.70 → 進入萃取），加兩段式 `interview_ready_confirmed` 防止同 call 內提前跳轉。

### ✅ STAR 完成條件（P0 已解決）

~~**現況**：靠 AI 回覆含「已收集完畢」字串，判斷脆弱~~

**已實作**：改為 slot filling，S/T/A/R 四槽皆有值才切換；`_MIN_SLOT_LEN=4` 支援中文短答；synthesis fallback 避免無限迴圈。

### ✅ STAR T-slot 無限迴圈（Stage 1 bug 已解決）

~~**現況**：`_MIN_SLOT_LEN=10` 拒絕合法中文短答，反覆追問同一槽位~~

**已實作**：`_MIN_SLOT_LEN` 改為 4；加 `_synthesize_slot()` — 若已重問過且用戶仍無法填入，LLM 從已知 S/A/R 上下文推斷合理內容（temperature=0.1，15~60 字）。

### ✅ Interview 提前跳入任務萃取（Stage 1 bug 已解決）

~~**現況**：`interview_node` 設 `interview_ready=True` 後，同 call 的 `route_after_interview` 立即路由到 `task_extraction`~~

**已實作**：兩段式確認模式：
1. 第一次達標 → 顯示過渡訊息，`interview_ready_confirmed=False`
2. 用戶回應後 → 回傳空 ai_response，`interview_ready_confirmed=True`，route 才放行

### ✅ 5W2H 必填欄位補強（P0 已解決）

**已實作**：新增 `workflow_steps`、`time_standards`、`collaborators` 三欄，共 9 個必填欄位。

### ✅ preview 應為 terminal state（P0 已解決）

**已實作**：`_STAGE_TO_NODE["preview"] = END`；`ocs_builder_node` 加 idempotency guard。

### ✅ iCAP confidence gateway（P0 已解決）

**已實作**：三段式模式 `reference / hybrid / company_defined`，存入 state `icap_mode`，ocs_builder 依模式調整生成策略。

### ✅ STAR 節點無限重問同一問題（B6 已解決）

~~**現況**：STAR S slot 永遠無法填入，同一問題無限重複~~

**已實作**：
1. `interviews.py` AI 訊息存 DB 改用 `accumulated.get("phase", message.phase)`（節點輸出 phase），而非 user 輸入 phase
2. `star.py` 新任務判斷改為過濾 **AI 訊息**（後端控制，phase 可靠），不再過濾 user 訊息（前端 phase 可能為 "general"）

### ✅ star.py 全部任務完成 fallback 路由錯誤（B7 已解決）

~~**現況**：全部 STAR 任務完成時的防呆 fallback 路由到 `five_w2h` 並重置 `current_task_index=0`，導致重跑所有任務 5W2H~~

**已實作**：fallback 改為路由 `"ksa"`，保留當前 `current_task_index`（不重置）。此 fallback 在正常流程不應觸發（由 indicator 負責路由 ksa），僅作保護。

### 待處理：偏題/亂答輸入驗證

**現況**：interview_readiness 使用關鍵詞匹配，用戶若亂答但剛好包含關鍵詞，score 會被錯誤拉高。

**待決議方案**（見 roadmap.md 第四階段）：
- (A) 最低門檻保護：≥ 4 輪回覆 + 平均 >15 字
- (B) LLM 相關性評分
- (C) 任務萃取 Guardrail（建議優先）
