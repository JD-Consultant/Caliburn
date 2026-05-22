# 開發 Roadmap

> 基於 2026-05-19 系統架構 Review 整理；2026-05-20 重排優先序。  
> **P0 已於 2026-05-20 全部完成。** **第一〜四階段已於 2026-05-20 全部完成。** 系統現況：工作者完整 Demo Flow 骨架已打通，8 個關鍵 Bug 已修復（含 STAR 無限迴圈、AI phase 持久化、task_id 流程鍵），Schema 已穩定，可進入測試。  
> **現階段主線**：讓單一工作者可從建立職務 → AI 訪談 → 任務確認 → STAR/5W2H → OCS 預覽 → 匯出，完整跑通。JWT / 企業權限不是現在重點。

## 系統定位

此系統的本質是「**企業崗位知識萃取系統**」，不是 JD 產生器或 iCAP 套版工具。

| 不應是 | 應該是 |
|--------|--------|
| 對外招募 JD 生成器 | 企業內部職務說明書與崗位知識萃取工具 |
| iCAP 內容改寫工具 | 以 iCAP 為框架、以工作者訪談為主資料來源的系統 |
| 單次輸入、單次生成 | 逐步訪談、萃取、補洞、生成、驗證、匯出的流程系統 |
| 只產出文件 | 沉澱任務、流程、工具、產出、行為指標、K/S/A 的知識庫 |

**產品核心鏈條**：工作者原話 → 任務萃取 → STAR 證據 → 5W2H 完整度 → 行為指標 → iCAP 對應 → OCS 文件 → 可追溯匯出

---

## P0 — 立即修正，影響 MVP 產出品質

| # | 項目 | 相關文件 |
|---|------|---------|
| ✅ 1 | `interview → task_extraction` 改 `interview_readiness_score`，不再用訊息數判斷 | [graph-pipeline.md](./graph-pipeline.md) |
| ✅ 2 | STAR 改 slot filling（S/T/A/R 四槽結構化判斷） | [graph-pipeline.md](./graph-pipeline.md) |
| ✅ 3 | 5W2H 加 `workflow_steps`、`time_standards`、`collaborators` | [graph-pipeline.md](./graph-pipeline.md) |
| ✅ 4 | `preview` 設為 terminal state，不再 route 到 `ksa` | [graph-pipeline.md](./graph-pipeline.md) |
| ✅ 5 | iCAP confidence 改三段式（high / medium / low → reference / hybrid / company_defined mode） | [graph-pipeline.md](./graph-pipeline.md) |
| ✅ 6 | task / output / indicator chunk 接入訪談流程（多粒度 RAG） | [icap-pipeline.md](./icap-pipeline.md) |
| ✅ 7 | OCS schema 加 `evidence_refs`（指標/任務可追溯到原始訪談） | [ocs-schema.md](./ocs-schema.md) |
| ✅ 8 | 行為指標加 `indicator_quality_score`，低於門檻退回補問 | [ocs-schema.md](./ocs-schema.md) |
| ✅ 9 | 匯出文件標示來源類型（[訪談確認] / [iCAP參考] / [AI整理] / [待確認]） | [export.md](./export.md) |
| ✅ 10 | 修正 PDF 字型跨平台問題（改 Noto Sans TC + `FONT_PATH` 環境變數） | [export.md](./export.md) |

---

## 第一階段 — 工作者完整 UI 流程 ✅ 全部完成

> 排序依據：「能不能讓工作者完整展示產生職務說明書」，而非企業安全考量。

| # | 項目 | 說明 |
|---|------|------|
| ✅ 1 | 工作者首頁 / 職務說明書列表 | 草稿 / 訪談中 / 已預覽 / 已匯出 四種狀態；可先用 demo user |
| ✅ 2 | 建立新職務說明書表單 | 職稱、部門、工作摘要、主要工作對象；建立後自動觸發 icap_rag |
| ✅ 3 | AI 訪談聊天介面 + readiness 顯示 | 右側顯示目前階段、readiness_score、缺漏欄位、下一步提示 |
| ✅ 4 | 任務萃取確認畫面 | 確認按鈕列 + 後端純確認跳過 LLM 重新萃取 |
| ✅ 5 | **逐任務流程改造**（STAR → 5W2H → indicator per task） | 每個任務完整跑完（STAR→5W2H→indicator）再進下一個；改 `route_after_indicator`、`entry_router` 與 conditional edges；修復兩個 bug（T-slot 迴圈 + 訪談提前跳轉） |
| ✅ 6 | STAR / 5W2H 任務卡片與完整度 UI | TaskPanel：`StagePill`（STAR/5W2H/指標三階段）、活躍藍框、完成綠色、待處理 50% opacity |

---

## 第二階段 — 文件預覽與匯出體驗 ✅ 全部完成

| # | 項目 | 說明 |
|---|------|------|
| ✅ 7 | OCS Preview 頁面 | 完整 OCS JSON 轉人類可讀版（職責/任務/指標/K/S/A/態度）；`BehaviorIndicatorCard`、`KsaSection`、`EvidenceRefs`、`QualityBadge` |
| ✅ 8 | display_label 顯示 | `SourceBadge` 元件：`[訪談確認]`藍 / `[AI整理]`紫 / `[iCAP參考]`琥珀 / `[待確認]`灰 |
| ✅ 9 | Evidence 展開功能 | `EvidenceRefs` 可展開顯示來源：工作者原話 / STAR slot / 5W2H 欄位 |
| ✅ 10 | 匯出 DOCX / PDF / XLSX / JSON 按鈕與下載流程 | [export.md](./export.md)；Preview 頁面含凍結（freeze）按鈕 |

---

## 第三階段 — 支撐前端的 API ✅ 主要端點完成

| # | 端點 | 說明 | 相關文件 |
|---|------|------|---------|
| ✅ 11 | `GET /job-profiles/{id}/state` | 頁面重整後恢復階段、readiness score、document_ready | [api.md](./api.md) |
| ✅ 12 | `GET /documents/{profile_id}/preview` | 取得預覽版 OCS JSON（含 quality_scores） | [api.md](./api.md) |
| ⏸ 13 | `POST /tasks/{id}/confirm` | 任務萃取確認，推進至 STAR（延後；目前由前端按鈕 + chat 流程處理） | [api.md](./api.md) |
| ⏸ 14 | `POST /tasks/{id}/regenerate-indicator` | 修改 5W2H 後重生單一任務行為指標（延後） | [api.md](./api.md) |
| ✅ 15 | `POST /documents/{id}/freeze` | Preview 後鎖定文件版本；設 stage="preview"（terminal state） | [api.md](./api.md) |

---

## 第四階段 — Schema 穩定與資料防呆 ✅ 全部完成

| # | 項目 | 說明 | 相關文件 |
|---|------|------|---------|
| ✅ 16 | Pydantic schema 補齊 | 補 `notes`、`occ_code`、`evidence_refs`、`quality_score`、`display_label`、`quality_status`；新增 `EvidenceRef`、`EnrichedExportJson`、`IcapReferencePack`、`TaskQualityScore` | [ocs-schema.md](./ocs-schema.md) |
| ✅ 17 | JSON 匯出補充 | `get_enriched_export_json()` 除 `ocs_document` 外加入 `evidence_refs`（展開）、`icap_reference_pack`（mode/hit/candidates）、`quality_scores`（任務品質摘要） | [export.md](./export.md) |
| ✅ 18 | **per-output 行為指標** | `indicator_node` 改為 per-output 生成：每個 `outputs` 條目生成獨立指標，1-to-1 對應 P/O 代碼；無 outputs 時 fallback 為整任務單一指標；`behavior_indicators` 每筆加入 `task_id`、`output_name`；`ocs_builder` 從 `behavior_indicators` 注入（不再由 LLM 自行生成） | [ocs-schema.md](./ocs-schema.md) |

另修復 8 個關鍵 Bug（2026-05-20）：

| # | Bug | 修復說明 |
|---|-----|---------|
| ✅ B1 | `interview_ready` 狀態每 call 重置 | `initial_state` 從 `saved_state` 恢復 `interview_ready` 與 `interview_ready_confirmed` |
| ✅ B2 | iCAP threshold 衝突（無 hybrid mode） | `config.py` 拆為 `icap_high_threshold=0.70`、`icap_medium_threshold=0.55`；`.env.example` 同步更新 |
| ✅ B3 | `freeze_document()` 要求先 export | 改為直接從 `graph_state["ocs_document"]` 建立 `DocumentVersion`，不依賴 export |
| ✅ B4 | Graph SSE error 繼續送 `[DONE]` | `try/except` 加 `return` 提前結束 stream；前端可感知錯誤 |
| ✅ B5 | `task_name` 作為流程 key（LLM 可能改名） | `task_extraction` 在萃取後立即分配穩定 `task_id=task_001…`；`star_slots_by_task`、`star_completed_task_ids`、`indicator_retry_counts`、`behavior_indicators`、phase key 全部改用 `task_id` |
| ✅ B6 | STAR 節點無限重問同一問題（S slot 永遠無法填入） | 根本原因：AI 回應存 DB 用的是使用者輸入的 `phase`（通常 "general"），而非節點輸出的 `"star_task_001"`；guard 過濾不到任何 user 訊息 → `user_input` 永遠被清空。修法：(1) `interviews.py` 儲存 AI 訊息改用 `accumulated.get("phase", message.phase)`；(2) `star.py` guard 改為檢查 AI 訊息（後端控制 phase，可靠） |
| ✅ B7 | `star.py` 全部任務完成 fallback 路由到 `five_w2h` 且重置 `current_task_index=0` | 舊版遺留碼（per-task loop 前的設計）。觸發時會導致重跑所有任務 5W2H。改為路由 `"ksa"`，保留當前 `current_task_index` |
| ✅ B8 | `route_after_task_extraction` 確認關鍵字缺少 "yes"/"Yes" | `graph.py` 的 `_CONFIRM_KEYWORDS` 補齊，與 `task_extraction.py` 的 `_PURE_CONFIRM_KEYWORDS` 保持一致 |

> **待決議**（輸入驗證）：偏題/亂答防護，三個選項：  
> (A) 最低門檻保護：要求 ≥ 4 輪回覆 + 平均 >15 字才允許 ready=True（零 LLM cost）  
> (B) LLM 相關性評分：interview_node 加輕量 LLM call 驗證回答是否與工作相關  
> (C) 任務萃取 Guardrail：萃取後若任務數<1 或名稱無意義則退回 interview（最重要）  
> 建議先做 (A)+(C)，等用戶決定。

---

## 第五階段 — 開發期穩定性

| # | 項目 | 說明 | 相關文件 |
|---|------|------|---------|
| 19 | Graph execution lock | 防止前端連點或 SSE 重連觸發兩次 AI 流程 | [api.md](./api.md) |
| 20 | `graph_runs` 執行紀錄表 | 記錄每次 graph 執行的 stage / node / 錯誤，供 debug | [architecture.md](./architecture.md) |

---

## 第六階段 — iCAP 資料治理

| # | 項目 | 說明 | 相關文件 |
|---|------|------|---------|
| 21 | iCAP Parser 修正 | 職類別代碼多值解析（LPS/5404/N8000）、task_codes 多值支援、notes_and_appendix 欄位 | [icap-pipeline.md](./icap-pipeline.md) |
| 22 | 說明與補充事項（Excel/PDF）補完 | 依賴 #21 iCAP Parser，目前為 placeholder | [export.md](./export.md) |
| 23 | `icap_standards` 主資料表 + 版本狀態正規化 | iCAP 版本管理與資料品質警告 | [icap-pipeline.md](./icap-pipeline.md) |
| 24 | `embedding_model` 版本記錄於 `icap_embeddings` | 防止模型更新後舊新向量不可比 | [architecture.md](./architecture.md) |
| 25 | `task_icap_mappings` 正規表 | task-level mapping + confidence（目前留 OCS JSON 已足夠） | [architecture.md](./architecture.md) |
| 26 | `task_evidence_refs` 正規表 | 長期查詢與稽核（目前 OCS JSON 已有 evidence_refs） | [architecture.md](./architecture.md) |
| 27 | 低信心 iCAP → `company_defined mode` 資產化完整流程 | 企業自建職能基準庫 | [icap-pipeline.md](./icap-pipeline.md) |
| 28 | 建立 RAG 命中率、任務萃取、行為指標品質的測試集 | 流程穩定後系統化驗證 | — |

---

## 第七階段 — 企業內測前（暫緩）

> 目前只做 Demo / 單機測試，不需要多使用者隔離。可先用固定 demo user。  
> 資料表保留 `company_id`、`owner_user_id` 欄位設計，但不做登入與權限。

| # | 項目 | 相關文件 |
|---|------|---------|
| 29 | JWT / session token 取代 query param `user_id` | [api.md](./api.md) |
| 30 | `company_id` tenant isolation + profile owner check + export 權限 | [api.md](./api.md) |
| 31 | API rate limit | [api.md](./api.md) |

---

## Backend 架構改善 ✅ 全部完成（2026-05-20）

| # | 項目 | 新增檔案 | 修改檔案 |
|---|------|---------|---------|
| ✅ 1 | **StateService** — 統一三方狀態同步 | `services/state_service.py` | `interviews.py`（移除手動 state 建構） |
| ✅ 2 | **TaskLoopManager** — 集中任務推進邏輯 | `graph/task_loop.py` | `nodes/star.py`、`five_w2h.py`、`indicator.py` |
| ✅ 3 | **Phase 強型別** — 消滅字串拼接 | `graph/phase.py` | `nodes/star.py`、`five_w2h.py`（`f"star_{task_id}"` → `Phase.star(id).to_str()`） |
| ✅ 4 | **LLMGateway** — retry + JSON parse retry | `graph/llm_gateway.py` | `nodes/star.py`、`indicator.py`、`interview.py` |
| ✅ 5 | **InterviewOrchestrator** — 拆分 interviews.py 職責 | `services/interview_orchestrator.py` | `interviews.py`（從 169 行縮至 52 行，只剩 HTTP 層） |
| ✅ 6 | **PromptTemplate 模組** — 集中管理 system prompt | `graph/prompts/interview.py`、`star.py`、`indicator.py` | `nodes/interview.py`、`star.py`、`indicator.py` |

---

## 第八階段 — 訪談體驗優化（2026-05-23 完成）

| # | 項目 | 說明 |
|---|------|------|
| ✅ 32 | **iCAP Live Preview 版面** | 訪談頁改為左右分割：聊天室（36%）+ iCAP 職能基準表格即時預覽（64%）；格式完全對齊官方 iCAP 表格（主要職責 / 工作任務 / 產出 / 行為指標 / 職能級別 / K/S）；未填欄位顯示 skeleton 動畫，隨訪談逐步填入；OCS 文件完成後自動切換為完整資料。元件：`LiveDocPanel`。 |

---

## P2 — 產品成熟期

- **RAG 輔助訪談問題**：`interview_node` 在 RAG #1 命中後，將 iCAP unit chunk（職能單元）注入 system prompt，讓 LLM 知道此職種官方認定應有哪些工作面向，訪談時主動問出工作者未提及的任務，而非完全靠工作者自述；`company_defined` 模式亦可注入相似度最高的 top-N 候選作為軟參考。目前 `interview_node` 完全無 RAG，`five_w2h_node` 僅 `outputs` 欄位有 RAG #3 注入，其餘欄位（`situation`、`purpose`、`workflow_steps`、`quality_standards`、`time_standards`）皆無。
- iCAP 多粒度 RAG 完整接入（unit / notes chunk）
- Reranker（提升 iCAP RAG 精準度）
- 任務自動合併與去重 UI
- 企業自建職能基準庫（讓系統越用越準）
- 多職務比較（同部門不同職等）
- 部門職責地圖
- 新人交接版輸出
- 訓練需求分析
- 職務異動版本比較
- 多租戶企業管理後台
- 匯出模板客製化

---

## MVP 驗收標準

| 面向 | 標準 |
|------|------|
| 完成時間 | 工作者能在 30–45 分鐘內完成一份草稿 |
| 任務萃取準確率 | 使用者認為 80% 以上任務正確 |
| 行為指標完整度 | 核心任務皆包含情境、目的、協作對象、工具、步驟、產出、品質/時效標準 |
| iCAP 對齊可信度 | 高信心命中合理；低信心時不硬套，能進 company_defined mode |
| 來源可追溯 | 任務與指標可回溯到原始訪談或 iCAP 參考 |
| 文件可用性 | 工作者覺得像自己的工作，新人可用於理解崗位 |

---

## 一句話總結

> 這套系統真正的價值不是用 AI 寫職務說明書，而是用 AI 萃取企業崗位知識，並以 iCAP 為框架生成可追溯、可交接、可管理的企業內部職務說明書。
