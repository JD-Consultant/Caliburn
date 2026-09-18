# jobintel-ai v3 — 架構設計（Architecture Spec）

> 本地記錄（untracked，不 commit）。日期：2026-06-16（原版 D1–D12）。
> 決策依據與討論過程：`2026-06-16-refactor-decision-log.md`（**D1–D26**）。
> 研究資料：`2026-06-15-architecture-research.md`。流程目標：`2026-06-14-jd-authoring-flow.md`。
> 本文件 = 把 D1–D12 組成一套**可實作的目標架構**。

> ⚠️ **已實作並有後續修訂（2026-06-18）**：本 spec 為原始目標架構。實作後幾項已被新決策取代——
> - **D22**：CopilotKit remote-endpoint → **AG-UI（ag-ui-langgraph）** + 前端 CopilotKit **v2 headless**（`useAgent`/`useInterrupt`）。
> - **D24**：收尾段（§2 ④⑤、§4.2 ksa、§9 step3-5）→ **逐任務 K/S + 全域 A + REVIEW**（`2026-06-18-ksa-flow-redesign-design.md`）。
> - **D25**：persistence/DB（§4.2 state、§4.4、§6、§8、§9 的 flush/業務表）→ **文件導向**：業務表只剩 `users`/`job_profiles`/`document_versions`，of-record = document_versions JSONB，任務/KSA 在 checkpointer；導入 Alembic（`2026-06-18-db-document-centric-design.md`）。
> 最新整體現況見 `PROJECT-STATUS.md`。以下各節若與 D22/D24/D25 衝突，以後者為準（關鍵節已內嵌註記）。

---

## 1. 目標與範圍

把 jobintel-ai 從「**從對話推論**」的 JD 顧問，重構為「**catalog 取出 + 人 curate + 每任務深問**」的 JD 撰寫 agent，消費 **jd-ocs-indexer v3** 知識服務。

- **棧**：LangGraph（控制流 + HITL）+ CopilotKit/AG-UI（前端共享狀態）+ Postgres（業務 + checkpointer）+ OpenRouter（成本優先分層模型）。
- **方式**：`feat/v3` 分支，`master` 既有 demo 不動；垂直切片漸進、每階段可跑。
- **原則**：12-factor 紀律（own prompts/control flow、deterministic 骨幹 + LLM 只在關鍵節點）、不過度（selective durability）、零 lock-in。

**範圍內**：控制流重構、retrieval 換 indexer、CopilotKit 漸進接入、state/schema additive、per-node 模型、OTel+eval。
**範圍外（未來）**：indexer 的 MCP surface、DBOS、多租戶隔離/RBAC、reranker、前端全面重寫、5W2H→JSONB 微重構。

## 2. 產品流程（flow）

8 步撰寫流程 → 落成 **5 步骨幹 + 深問子圖**：

```
START → entry（由 thread/checkpointer 還原到正確步驟）
 ① pick_profile    : KnowledgeClient.search()    → interrupt(選/改 OCS)        approve→②
 ② build_task_pool : KnowledgeClient.task_pool()  → interrupt(增/刪/改 任務清單) approve→③
 ③ 逐任務迴圈（sequential, task_index 前進）：
       ┌─ deep_interview 子圖（每任務一份）──────────────────┐
       │   star → five_w2h → indicator                        │
       │   每個提問 = interrupt(ask_human)                     │
       │   catalog 的 k/s/output/活動 當 just-in-time prefill  │
       └──────────────────────────────────────────────────────┘
       └ 還有任務→回③；全部完成→④
 ④ curate_ks       : 逐任務 K/S 審閱面（單層迴圈，ks_index）→ interrupt(改K/S)  全任務完→⑤
 ⑤ curate_attitudes: 全域 A 審閱面 → interrupt(改A)                            approve→⑥
 ⑥ build_doc       : 組裝 → REVIEW(唯讀預覽) → 存 document_versions（terminal）
所有人機接觸點 = interrupt(approve/edit/reject)；**關鍵字路由全砍**。
```

> **④⑤ 收尾段已重設計（2026-06-18，D24）**：原單步 `assemble_ksa` 拆成「逐任務 K/S（task 層）+ 全域 A（職類層）」，對齊 OCS 職能基準結構（K/S 在 task 的 competency_blocks、A 在頂層 ocs_attitude）。KS 來源 interim 用 `pairs()` 職類池（待 `tasks_by_id` 502 修好升級 per-task）。細節見 `2026-06-18-ksa-flow-redesign-design.md`。

## 3. 系統架構總覽

```
┌─ Frontend (Next.js + CopilotKit) ─┐        ┌─ Backend (FastAPI + LangGraph) ─────────────┐
│  CopilotKit provider/runtime      │  AG-UI │  graph：5 骨幹節點 + deep_interview 子圖     │
│  useCoAgent（shared state）       │◀──────▶│  interrupt()/Command(resume) = HITL          │
│  renderAndWaitForResponse → 重用  │ (SSE/  │  ┌─ KnowledgeClient (HTTP) → jd-ocs-indexer  │
│  TaskPanel/LiveDocPanel/...       │  events)│  ├─ Persistence: PostgresSaver + Repos       │
└───────────────────────────────────┘        │  ├─ LLM gateway: per-node tier → OpenRouter │
                                              │  └─ OTel traces + eval gate                  │
                                              └──────────┬───────────────────────────────────┘
                                                         ▼
                                        Postgres（業務表 + checkpointer；無 pgvector）
```

## 4. 後端

### 4.1 控制流（D3/D8）
- 單一 LangGraph：5 骨幹節點 + `deep_interview` **subgraph**（star→five_w2h→indicator，保留現有深問引擎，改 interrupt 驅動）。
- HITL：節點內 `interrupt(payload)` → AG-UI → CopilotKit `renderAndWaitForResponse` 渲染（用重用元件）→ `Command(resume=編輯結果)`。**取代 `route_after_*` 中文關鍵字路由**。
- 迴圈 **sequential**（互動深問不能平行，故不用 `Send`）。
- `entry_router` 保留概念（由 `current_step` + checkpointer 還原），但推進改 interrupt/resume。

### 4.2 State schema（D6/D9）
巢狀、各有 owner（取代扁平 30 欄）：
```python
class InterviewState(TypedDict):
    job_profile_id: str
    current_step: str                 # pick_profile|task_pool|deep|assemble_ksa|build_doc|done
    messages: Annotated[list, add_messages]   # 對話（暫態，checkpointer）
    profile: ProfilePick              # {candidates, selected_ocs_code}
    tasks: list[TaskItem]             # 〔可編輯·CopilotKit 共享〕含 provenance
    deep: DeepState                   # 〔暫態〕{current_task_index, slots_by_task, missing_fields, completed_ids, retry}
    ksa: KsaDraft                     # 〔可編輯·CopilotKit 共享〕{knowledge, skills, attitudes}
    document: dict | None
```
- `TaskItem`：`source:"catalog"|"company"` + `indexer_ref:{ocs_code,task_id}` + 深問產出欄位。
- **可編輯切片**（`tasks`/`ksa`）為頂層可定址 key → CopilotKit `setState` 可改。
- **工作態 vs of-record**：編輯中/補洞中在 graph state（checkpointer）；**確認某步**才 flush 到業務表；深問 slots 在 state，任務**深問完成**才把定稿 flush 進 `company_tasks`。

### 4.3 KnowledgeClient（D7）
- `KnowledgeClient` Protocol（6 方法：search / task_pool / pairs / tasks_by_id / stats / healthz）+ `HttpIndexerClient` 實作（typed + Pydantic）。
- 節點呼叫**介面**不是 raw HTTP → 日後換 transport = 換 adapter。
- 未來多客戶：indexer 側 `FastMCP.from_fastapi(app)` 加裝 MCP surface（與 REST 並存）；jobintel-ai 內部路徑永留 HTTP。

### 4.4 Persistence（D6/D9 → **已被 D25 取代，見下方註記**）
> ⚠️ **D25（2026-06-18）翻轉本節**：改文件導向，**移除 `TaskRepo`/`KsaRepo`/`flush_tasks`/`flush_ksa`**；persistence 只剩 `set_selected_ocs` + `DocRepo.save_document`；of-record = `document_versions` JSONB。詳見 `2026-06-18-db-document-centric-design.md`。以下為原 D6/D9 設計（保留供脈絡）。
- **LangGraph `PostgresSaver`** checkpointer（thread=profile_id）= thread 工作態。**棄用** `job_profiles.graph_state` 欄。
- `TaskRepo / KsaRepo / DocRepo` + `hydrate()`（進場從表載入）/ `flush()`（確認編輯→**row-level upsert**，保 `task_id` 穩定免斷 `ksa_items` FK）。
- 集中一個 persistence 模組，節點只呼叫 hydrate/flush。

### 4.5 LLM gateway（D10）
- per-node 分層：deep_interview=強階、indicator/build_doc=中階、措辭=cheap/無 LLM。
- 擴 `get_chat_llm(role)`（role→model 映射，settings 可配）+ OpenAI-相容 `base_url` → **OpenRouter**（一窗口挑 CP值最高、改字串即換、設 data-policy）。
- 預設：深問 Kimi K2.6 / DeepSeek V4 Pro；中階 DeepSeek V4 / GLM-5.1；cheap DeepSeek Flash / Gemini Flash。
- **砍** dead `get_embeddings()`（D5 後無 in-DB 向量）。
- 換模型前過 **eval 閘門**（見 §7）。

## 5. 前端（D11）

**漸進 wrap**，非重寫：
- 加 CopilotKit provider（layout.tsx）+ runtime 端點。
- 換 plumbing：`useInterview`（手刻 SSE）→ `useCoAgent`（shared state）+ `renderAndWaitForResponse`（interrupt）；`lib/api.ts` chat SSE → CopilotKit runtime。
- **重用展示元件當 render 目標**：`TaskPanel`（編輯任務清單）、`LiveDocPanel`（預覽）、`ProgressTracker`、`StageGuide`、`ChatBubble`。
- 調整：`IcapBadges`/`SourceBadge` 的「iCAP 信心模式」顯示因 catalog-first 改內容（元件殼留）。

## 6. 資料庫（D5/D9 → **已被 D25 取代**）
> ⚠️ **D25（2026-06-18）重設計本節**：業務表精簡到 **`users` / `job_profiles` / `document_versions`**；**drop `company_tasks`、`ksa_items`**（+ 舊 `icap_references`/`interview_sessions`/`icap_embeddings`）；任務/KSA/深問細節全在 checkpointer + 最終文件 JSONB；導入 Alembic。詳見 `2026-06-18-db-document-centric-design.md`。以下為原 D5/D9 設計（保留供脈絡）。
- **Postgres 保留**；**移除 pgvector + `icap_embeddings` 表**（檢索外包 indexer/Qdrant）。
- **Additive schema 變更**：
  - `company_tasks`：+ `source TEXT`（catalog|company）、+ `indexer_ref JSONB`
  - `job_profiles`：+ `selected_ocs_code TEXT`；**棄用** `graph_state`
  - `ksa_items` / `document_versions`：不變（已足夠）
- 現有即權威 hybrid：relational（company_tasks/ksa_items）+ JSONB（document_versions.content）。

## 7. 觀測 / 評估（D12）

- **OTel** 儀器（廠商中立）從一開始就埋；逐節點 trace + token/cost/latency。
- **小 eval 集**：① zh-TW + 嚴格 JSON 可靠度（驗便宜模型）② 深問品質 ③ 文件組裝正確性。**換 OpenRouter 模型前須過 eval**。
- Dashboard：需逐節點 debug 時接 **Langfuse 自建**（OSS、資料自留、含 eval）。

## 8. 移除 / 保留

| 移除 | 保留（重用） |
|---|---|
| `icap_matcher` + `icap_retriever` + `icap_embeddings`/pgvector | 深問引擎 `star`/`five_w2h`/`indicator` → 包成 subgraph |
| `route_after_*` 關鍵字路由 | `ocs_builder`（組裝；輸入改 catalog K/S/A + 公司補充） |
| `job_profiles.graph_state` blob | `document_service`/匯出、業務表 |
| `get_embeddings()` | LLM gateway（擴成 per-node）、前端展示元件 |
| 從對話 LLM 萃任務（`task_extraction` 舊角色） | （task_extraction → 改成 catalog 取出 + 編輯） |

## 9. 資料流走查

1. 使用者描述職務 → `pick_profile`：`search()` 得候選 → `interrupt` 選 OCS（Sonnet/cheap 措辭）。
2. `build_task_pool`：`task_pool(ocs_code)` 得任務選單 → emit `tasks`（CopilotKit 編輯）→ `interrupt` 增刪改 → flush `company_tasks`（source/indexer_ref）。
3. 逐任務 `deep_interview` 子圖：catalog k/s/output 當 prefill → STAR 四槽（強階模型，每問 interrupt）→ 5W2H 補洞 → indicator 生成+品質（中階）→ 完成 flush 定稿到 `company_tasks`。下一任務循環。
4. `assemble_ksa`：`pairs()`+`tasks_by_id()` 取 catalog K/S/A + 公司補充 → emit `ksa`（編輯）→ `interrupt` → flush `ksa_items`。
5. `build_doc`：`ocs_builder` 組裝 OCS 文件 → 寫 `document_versions`（JSONB）→ `preview`（terminal）→ 匯出。
- 全程：checkpointer 持久化 thread；每節點 OTel trace；模型按 role 經 OpenRouter。

## 10. 測試策略
- **TDD**（subagent-driven，沿用 indexer 的節奏：RED→GREEN→commit）。
- 單測：每節點（mock KnowledgeClient + LLM）、persistence hydrate/flush（FK 穩定）、interrupt/resume、state reducers。
- **eval harness**：§7 三項，當模型切換閘門。
- 子圖可獨立測（D8 選 subgraph 的好處）。

## 11. 分支 / 遷移策略
- `feat/v3` 分支；`master` demo 不動（D1 保留可運作 demo）。
- 垂直切片漸進（建議 phase 序）：① 資料層（KnowledgeClient + 砍 pgvector + schema additive + persistence）② 骨幹節點 ①②（pick_profile/task_pool + interrupt + CopilotKit shared-state 第一條端到端）③ deep_interview 子圖 ④ assemble_ksa + build_doc ⑤ OTel+eval ⑥ 前端元件接齊。每階段 branch 可跑。

## 12. 範圍外 / 未來
indexer MCP surface、DBOS durability、多租戶隔離/RBAC、reranker、前端全面 CopilotKit-native、5W2H 欄→JSONB `details` 微重構。

## 13. 決策索引
完整 D1–D12 選項取捨、權威來源、討論過程 → 見 `2026-06-16-refactor-decision-log.md`。
