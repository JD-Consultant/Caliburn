# v3 重設計 決策紀錄（工作紀錄）

> 記錄 2026-06-13~14 jd-ocs-indexer schema v3 + jobintel-ai 流程/架構重設計過程中的每個決策：**選了什麼、棄用什麼、為什麼**。供專題報告引用。
> 格式：每條 = 決定 / 理由 / 棄用的替代方案。含過程中的**反轉**（設計是逐步逼近的）。

---

## A. 後端整合 / 角色分工

### A1. 兩套平行 iCAP RAG → 統一（方案 A）
- **決定**：jobintel-ai 退役自己的 pgvector iCAP RAG，改用 jd-ocs-indexer 查詢 API。
- **理由**：原本兩套（jobintel-ai OpenAI+pgvector、jd-ocs-indexer BGE-M3+Qdrant）索引同一份 iCAP、重複維護；USER_FLOW §4-5 早就把 jd-ocs-indexer 設計成知識服務、jobintel-ai 當消費端。
- **棄用**：
  - 方案 B「兩套各留、只接前段」→ 重複永遠存在、檢索品質不一致。
  - 方案 C「反向把 indexer 折進 jobintel-ai」→ 失去可重用知識服務、大重構。

### A2. jd-ocs-indexer = 知識服務（向量搜 + 結構化查 + by-id 取）、無狀態
- **決定**：indexer 只回資料、不管使用者狀態；jobintel-ai 管流程/狀態/LLM/產出。
- **理由**：2026 主流「把檢索解耦成 context engine / 服務層」；職責清楚、各自可演進。

---

## B. Schema / chunk / payload

### B1. K/S/A/output → pair 為 canonical，砍 flat codes + terms
- **決定**：只存 `{code,name}` pair；砍 `k_codes`/`s_codes`/`attitude_codes`（flat）+ `knowledge_terms`/`skill_terms`（names）+ 其索引。
- **理由**：iCAP 代碼是 **OCS-local**（同碼不同名），有意義的單位是 `(OCS,名稱)`；pair 把綁定明確存著、不會漂。
- **棄用**：
  - 「用 terms+codes 兩條平行陣列 zip 回 pair」→ 兩條過濾條件不同會錯位（v1/v2 的真實 bug），靜默把碼配錯名。
  - 「保留 flat codes 當索引」→ 代碼 OCS-local，全域 `k_codes=K05` 過濾語意上是錯的；查證後產品流程**沒人用裸碼過濾**（只有 dev smoke-query + 空殼 API + 死 fallback）。

### B2. 結構化查詢（任務樹/池）→ 不走向量
- **決定**：已知 ocs_code 的查詢（列任務、取 K/S/A 池）走結構化 filter/retrieve，不在 Qdrant 上做向量。
- **理由**：known-key lookup 不是語意搜尋。
- **棄用**：「從 block scroll 重組任務樹」→ 會漏 block-less task、平行陣列錯位。

### B3. 砍掉一批 write-only / 冗餘欄位
- **決定**：砍 `block_id`/`block_title`（永遠 None）、`indicator_codes`/`output_codes`（在 evidence/output_pairs）、`source_path`/`source_labels`（write-only、脆弱、結構化 id 可回溯）、`schema_version`/`embedding_provider`（常數、manifest 已有）、`text_format`（常數）、`source_root_alias`（弱 provenance）、`chunk_content_hash`（未用）、`unit_order`/`task_order`（陣列本身有序）。
- **理由**：逐欄 grep 查證「誰讀 payload」，這些都是寫進去沒人讀、或可衍生/常數。
- **方法論**：審 metadata 用「access pattern 驅動」——看每欄被哪個操作讀，而非憑印象。

### B4. 點類型：profile/unit/block 三層 → **profile + task 兩種**（反轉過兩次）
- **決定（最終）**：只建 **profile point** 和 **task point**；unit/block 不建 point，block 只在 index 時聚合 K/S 與活動句。
- **過程（重要）**：
  1. 先想「砍 unit」（它是 block 的 roll-up、流程沒讀）。
  2. 使用者指出「列任務清單要完整、含 block-less task」→ **反轉**回「unit 是完整任務清單的家、補 task_pairs」。
  3. 使用者再指出「embedding 單位錯了、K/S 沒被 embed、chunk 太大」→ **再反轉**成 task-centric：task 才是被搜尋與被選的單位。
- **理由（最終）**：全流程只有 2 個動作需要向量（描述→職務、改過的任務→K/S），所以只 embed profile + task；block 是 iCAP 內部結構、user 不感知。
- **棄用**：
  - block points → 過細、K/S 散在 chunk、user 不以 block 思考。
  - 大 tree 當 profile payload → chunk 太大、雜。
  - 獨立結構化 DB（SQLite/Postgres）→ 不需要，Qdrant 本來就能 by-key retrieve / filter scroll（使用者點出「Qdrant 不一定要向量搜」）。

### B5. 索引精簡 18 → ~9
- **決定**：只索引「全域有意義 + 真會過濾」的欄位（chunk_level/ocs_code/ocs_code_base/job_title/is_current/version/ocs_level/industry_codes/occupation_codes）。
- **棄用**：OCS-local 的 id/碼索引（k/s/attitude/task/unit）全砍——全域過濾沒意義。

### B6. 補回 `prerequisites` / `supplements`
- **決定**：profile 加這兩欄（建議學歷/經驗/能力條件、其他補充說明）。
- **理由**：流程 Step 7 需要；**來源 `notes.prerequisites/supplements` 早就 parse 了、只是 v2 builder 沒寫入**。
- **棄用**：supplements 做硬選單 → 結構鬆、當參考就好。

---

## C. Embedding 策略

### C1. 只 embed profile + task
- **決定**：只有這兩種有向量。
- **理由**：見 B4——只 2 個動作需要語意搜尋。
- **棄用**：embed 全部（太多）、不 embed K/S（改過的任務搜不到）。

### C2. embed 是「動作」不是「欄位」、砍通用 `text`
- **決定**：embed 字串在 index 時組好餵模型、**不回存**；顯示用已存的結構化欄位（job_description / activity_examples）拼。
- **理由**：通用 `text` = task_title+活動 = 跟已存欄位重複。

### C3. profile embed 要大（職務+工作內容+技能）、task embed 適中（任務+活動）
- **決定**：profile 為了匹配職位要全（含 tool-level 技能詞）；task 聚焦活動以接住 drift。
- **棄用**：profile 只 embed 描述 → tool 詞（Python/SQL）配不到。

---

## D. 流程

### D1. bottom-up 核心保留 + menu-first scoping（混合）
- **決定**：核心 bottom-up 深訪不變；前面加可選的 menu-first 快速 scoping。
- **理由**：研究——對話式 completion 高但 7-8 分鐘疲勞懸崖；menu 砍冷啟動、bottom-up 保深度。
- **棄用**：純 literal menu-first（anchor 風險、跟 jobintel-ai 哲學衝突）、純對話（冷啟動慢）。

### D2. gap detection → 前置（選職務→選任務）
- **決定**：廣度補漏前置成「選職位→任務選單勾選」。
- **理由**：最省時 + 廣度一開始就保證不漏；anchoring 被「深度仍 bottom-up」擋住。

### D3. by-id 取 vs 向量找 = jobintel-ai 依狀態決定
- **決定**：有來源且內容沒改 → by-id（捷徑）；自訂或改過 → 向量（保底，永遠對）。
- **理由**：只有 jobintel-ai 知道任務身世；向量涵蓋 by-id 所有情況（沒改的任務向量搜會找到自己）。

### D4. task_id = OCS 來源參考，非使用者任務身分
- **決定**：使用者的排序/編號/改名是 jobintel-ai state；OCS task_id 只當引用 + by-id key。
- **理由**：JD 用自己的編號（USER_FLOW 論點）；排序/改名不影響檢索。

### D5. 完整度 = 深度（每任務 T/O/P/K/S 齊）+ 廣度（對標準覆蓋）；Step 8 LLM 白話覆述確認
- **決定**：OCS 當完整度標尺；完整度儀表給滿分動力 + 分段心理錨。

---

## E. 實現架構

### E1. 三分架構：確定性選單元件 / interrupt 提案編輯 / LangGraph 深度
- **決定**：純選單走「後端撈+前端可編輯清單元件」（無 LLM）；agent 提案走 LangGraph interrupt+edit；唯一真 agentic 的 Step 4 深度訪談用 LangGraph 子流程。
- **理由**：2026 共識「agent 只用在需要推理處」；LangChain 自己說 interrupt 別做即時點選。
- **棄用**：全塞一個 LangGraph（選單變一堆 interrupt 節點、graph 變胖）。

### E2. 採 generative-UI「模式」、不採 CopilotKit「框架」
- **決定**：自實作輕量 `list-spec` 事件 + 可重用 `SelectableEditableList` 元件在現有 SSE 上。
- **理由**：jobintel-ai 已有自訂 Next.js+SSE+bespoke 元件；硬上 CopilotKit/AG-UI 框架=大遷移、跟現有打架。拿模式好處、不扛框架。
- **棄用**：CopilotKit/AG-UI 全套框架（greenfield 才直接上）。

### E3. Step 4 深度引擎：簡化、不換
- **決定**：留現有 STAR/5W2H 引擎（5W2H 九欄已涵蓋 T/O/P）；STAR+5W2H 重疊可收成一段降負擔；UI 重新框成 T/O/P。
- **棄用**：整個換掉（它是 work 的 agentic 核心）。

### E4. reranker：加 bge-reranker-v2-m3
- **決定**：/search hybrid 後加 cross-encoder rerank。
- **理由**：2026 主流預設 hybrid+rerank（+26/28% recall/precision）；BGE 家族、self-host 零摩擦。
- **棄用**：GraphRAG / agentic RAG（對 lookup 是浪費、貴 3-10×）。

### E5. 上 CopilotKit/AG-UI 框架；同 repo 開 `feat/v3` branch 重構，不新 repo
- **決定**：採 CopilotKit/AG-UI（不只是模式）。jobintel-ai **同一 repo 開 `feat/v3` branch**；後端**留**深度引擎+服務+匯出+DB、**重構** graph 前段、**換** `icap_retriever`→jd-ocs-indexer、**加** CopilotKit runtime + `company_tasks` 表；前端用 CopilotKit 重寫。
- **理由**：CopilotKit 的 shared state（agent↔前端雙向 live 同步）特別貼合 Step 3「LLM 與使用者編輯同一份任務清單」；前端反正要為新流程重寫、順便換；後端 5-6 成可複用。
- **棄用**：
  - 新 repo → 後端要全搬、丟 git 歷史、純浪費。
  - 直接動 main → 破壞現有可運作 demo（故開 branch）。
  - 純自訂不上框架 → 雙向同步要手刻 SSE+/submit。
- **對 state 的影響**：CopilotKit 下，任務清單**留 graph state**（框架同步）、checkpoint **落表**做 audit（vs 純自訂版「拆 company_tasks 表當真相」）。

---

## 方法論註記（給報告）

1. **access-pattern 驅動**：審欄位看「誰讀」，不憑印象。
2. **逐欄 grep 查證**：每個「砍除」前先 grep consumer。
3. **設計是逼近的**：unit/block、tree、R1/R2 都反轉過——使用者的 challenge（「不該搜 block？」「Qdrant 不一定要向量？」「embedding 單位錯了」）逐步逼出更乾淨的設計。
4. **以最新權威資料佐證**：RAG 架構、HITL、generative UI 都查 2025-26 來源。
