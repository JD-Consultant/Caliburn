# jobintel-ai v3 重構 — 決策日誌（Decision Log）

> 本地記錄（untracked，不 commit）。起始 2026-06-16。
> 用途：依使用者要求，記錄**討論過的問題、引用的權威文章、選定的方案與理由**。
> 方法論（使用者定）：後續每個決策 → 先以**權威來源**深挖「別人怎麼做、效果好」→ 列**優劣** → 分析**我們適合什麼** → 再由使用者**選擇**。不急著拍板。
> 資料總表見 `2026-06-15-architecture-research.md`；流程目標見 `2026-06-14-jd-authoring-flow.md`。

---

## 背景

把 jobintel-ai（FastAPI + LangGraph 的 JD 撰寫顧問）重構為**消費 jd-ocs-indexer v3 知識服務**的產品：
- 流程反轉：任務「清單」改從 indexer catalog 取出 + 使用者 curate（取代 LLM 從對話硬萃）；**每個 curate 後的任務仍跑完整 STAR/5W2H/行為指標**（深度為核心價值，不稀釋）。
- 原代碼只當參考，可重新設計（greenfield 允許）。
- 取向：用最主流/最新/效果好、且**權威來源**佐證的做法。

---

## 已定決策

| # | 決策 | 選擇 | 理由 / 來源 |
|---|---|---|---|
| **D1** | 部署規模 | **未定 → 按「可成長到 SaaS」設計** | `PostgresSaver` + 保留 user/tenant 抽象（現 User→JobProfile 已是雛形），但**不現在**上多租戶隔離/RBAC。骨幹預留、不過度。 |
| **D2** | 深度訪談份量 | **每任務都深問（維持現況深度）** | 深度訪談是產品核心價值。任務來源改 catalog，但 STAR→5W2H→indicator 對每個確認任務照跑；catalog 的 k/s/output/活動範例變「just-in-time」prefill/參考。 |
| **D3** | 控制流脊椎 | **方案 A：單一 LangGraph + `interrupt()` HITL** | 一條連貫狀態機；選單節點 emit 可編輯清單→`interrupt`→`Command(resume)`；逐任務深問迴圈。砍掉現況脆弱的中文關鍵字路由。 |
| **D4** | 編排框架 | **LangGraph（用框架）** | 經前沿評估確認：OpenAI 自家指引也是 stateful+HITL+可稽核→LangGraph；LangGraph 1.0 已是 durable execution engine + 一級 HITL。**排除**「純手寫 while-loop + DBOS」純框架派——要自己重造 checkpoint/interrupt-resume/loop/streaming，得不償失。但採 **12-factor 紀律**建（own prompts、own control flow、deterministic 骨幹 + LLM 只在關鍵節點）。 |
| **D5** | 資料庫 | **Postgres（留）；砍 pgvector + `icap_embeddings`** | Postgres 是 2026 agentic app 預設真相（DBOS / LangGraph / 「just use Postgres」共識）。檢索已外包給 indexer 的 Qdrant → jobintel-ai 不再需要 in-DB 向量。durability：`PostgresSaver` 起步，DBOS（Postgres-native）留作 SaaS 抗基礎設施崩潰的後話（selective durability）。 |
| **D6** | JD 產物狀態真相 | **分層 + write-through（策略 A）** | 權威重框：checkpointer 非業務 DB（LangGraph 官方 persistence），CopilotKit 鏡像 graph state → 可編輯清單會話期間必在 graph state。故**兩層並存**：graph state（會話工作態，checkpointer 持久化）+ Postgres 業務表（of-record，可查/匯出）。同步=**進場 hydrate、確認編輯即 flush（write-through）**，集中成一個 persistence 層。排除 B（表 stale）、C（衝 CopilotKit 同步模型）。來源：LangGraph Persistence、CopilotKit shared-state read/write、DBOS、12-factor F5。 |
| **D7** | 知識存取機制 | **typed HTTP client + `KnowledgeClient` 介面（MCP 後話加裝）** | HTTP→MCP 是 additive 非 migration：indexer 側 `FastMCP.from_fastapi(app)` 一行生成 MCP 與 REST 並存（REST 不動）；consumer 側呼叫走 `KnowledgeClient` Protocol，換 transport=換 adapter、節點不改。未來多客戶由 indexer 加裝 MCP surface 服務，jobintel-ai 內部路徑永遠留 HTTP（避免主路徑永久背 4–32× token/RTT）。來源：FastMCP×FastAPI、tadata fastapi_mcp。 |
| **D8** | 控制流形狀 | **多步精靈骨幹 + 深問 sequential subgraph，全程 interrupt（approve/edit/reject）** | 骨幹5步：①pick_profile(search)②build_task_pool(task_pool)③逐任務迴圈→deep_interview 子圖(star→5w2h→indicator，每問 interrupt，catalog 當 prefill)④assemble_ksa(pairs+by-id)⑤build_doc→preview。深問做成 **subgraph**（模組化/可單測/可演進）。迴圈 **sequential**（互動深問不能平行，不用 Send）。HITL 用 `interrupt()`+`Command(resume)`+CopilotKit `useHumanInTheLoop`，**砍掉 route_after_\* 關鍵字路由**。來源：CopilotKit Interrupt Flow、LangGraph use-graph-api、v0.4 HITL。 |
| **D9** | state/schema | **巢狀 graph state + additive 業務表（hybrid 不動）** | graph state 改巢狀有 owner（profile/tasks/deep/ksa/document）；可編輯切片（tasks/ksa）為可定址 key 供 CopilotKit setState。業務表**保留**（現有即權威 hybrid：relational company_tasks/ksa_items + JSONB document_versions）；**additive**：加 company_tasks `source`+`indexer_ref`、job_profiles `selected_ocs_code`，棄 `graph_state` 欄（PostgresSaver 接手）。persistence：Repo + hydrate/flush（row-level upsert 保 task_id 穩定免斷 FK）。排除 restructure（現有已最佳實踐，純增 migration 風險）。來源：Postgres JSONB-vs-relational hybrid（Citus/Architecture Weekly/Neon）。 |
| **D10** | 模型策略 | **成本優先 + per-node 分層 + OpenRouter 單一窗口** | 不用全域單一模型；按任務複雜度分層（強/中/cheap），路由可省 40–70% 成本 <2% 品質損失。供應商：**OpenRouter**（一 OpenAI-相容 API/帳單，每節點挑當下 CP值最高模型、改字串即換、零 lock-in、設 data-policy 控落地→SaaS 安全）。預設：深問 Kimi K2.6 / DeepSeek V4 Pro；indicator/build_doc 中階（DeepSeek V4 / GLM-5.1）；措辭層 DeepSeek Flash / Gemini Flash 或不用 LLM。gateway：擴 `get_chat_llm(role)` + base_url→OpenRouter；砍 dead `get_embeddings()`。**Caveat**：zh-TW + 嚴格 JSON 可靠度無公開 benchmark → 鎖定前用小 eval 驗。來源：LLM routing（TrueFoundry/Morph）、BenchLM 中文榜、AWS Bedrock 託管（data residency）。 |
| **D11** | 前端範圍 | **漸進 wrap（CopilotKit 接現有 Next.js，保留自製展示元件）** | CopilotKit 官方支援漸進採用（layout.tsx 加 provider、custom 元件共存）。自製展示元件（TaskPanel/LiveDocPanel/ProgressTracker/StageGuide/ChatBubble）→ 變 render 目標（`renderAndWaitForResponse`/`useCoAgentStateRender`）被**重用**；只換 plumbing：`useInterview` 手刻 SSE → `useCoAgent` + CopilotKit hooks + provider/runtime。**更好維護**（刪掉最脆弱的手刻 SSE plumbing、保留單純展示元件、混搭是官方正解）。排除全面重寫（元件不糾纏，重寫只換風格一致卻丟可用 UI + 風險）。來源：CopilotKit React Integration、useCopilotAction、Generative UI 2026。 |
| **D12** | 觀測/評估 | **OTel + 小 eval 先行；Langfuse 自建當後續 dashboard** | 現在只做必要+便宜：① 程式用 **OpenTelemetry** 吐 trace（廠商中立、可隨時接平台）② 小 **eval** 集（zh-TW + 嚴格 JSON〔D10 caveat 落地〕、深問品質、文件正確性）當 OpenRouter 換模型的閘門。漂亮 dashboard 等需逐節點 debug 時接 **Langfuse 自建**（OSS/MIT、資料自留、含 eval，合 cost+隱私）；LangSmith 僅在要零設定/不介意付費上雲時。後話、不擋開發。來源：LLM 觀測 2026（Firecrawl/digitalapplied/Laminar）。 |

## ✅ D1–D12 全數定案 → 進入架構 spec（`2026-06-16-jobintel-ai-v3-architecture.md`）→ 實作計畫

---

## 討論過程紀要（取捨與 Q&A）

> 依使用者要求保留討論過程：每個決策的選項取捨、使用者關鍵提問與解法。

- **方法論（貫穿全程，使用者定）**：先研究**權威來源**「別人怎麼做、效果好」→ 列**優劣** → **適配**分析 → 使用者**選**。原代碼當參考、可 greenfield 重設計。要最主流/最新/效果好（前沿大廠 Codex/Claude/OpenAI 等），但**不為「主流」標籤硬套**（看形狀適配）。
- **D1 部署**：SaaS多租戶／內部多用戶／單機／未定 → **未定按可成長到 SaaS**。
- **D2 深問**：分層／全選擇性／每任務 → **每任務都深問**（深度=核心價值不稀釋；任務改 catalog 取出但深度不變）。
- **D3 脊椎**：A 單一 LangGraph+interrupt／B 選單走REST·graph只管深問／C 最小改動沿用舊圖 → **A**。使用者補：可 greenfield、要前沿主流。
- **D4 框架**：誠實評估「不用框架純手寫 while-loop+DBOS」替代 → **排除**（要重造 checkpoint/interrupt/loop/stream；且 LangGraph explicit graph 本就是『擁有控制流』，非 12-factor 批評的 opaque loop）→ **LangGraph + 12-factor 紀律**。
- **D5 DB**：**Postgres**（2026 預設）+ **砍 pgvector**（檢索外包 indexer/Qdrant）。
- **D6 狀態真相**：權威重框（checkpointer≠業務DB，LangGraph 官方）→ **非 table-vs-graph 二選一，是分層 + 同步策略** → 選 **A hydrate/flush write-through**（排除 B stale、C 衝 CopilotKit）。
- **D7 知識存取**：使用者提問「**HTTP 以後改 MCP 難嗎?多客戶要不要一次到位?**」→ 解法:**additive 非 migration**（indexer 側 FastMCP `from_fastapi` 一行；consumer 走 `KnowledgeClient` 介面換 adapter；多客戶由 indexer 加裝 MCP surface、內部路徑永留 HTTP 避免背 4–32× token）→ 規則「好改就先 HTTP」→ **HTTP client**。
- **D8 控制流**：深問 subgraph／內聯 → **subgraph**。確認 `Send`=平行不適合互動深問 → **sequential**；`interrupt(approve/edit/reject)` 取代關鍵字路由。
- **D9 schema**：使用者規則「**改動大才重設計**」→ 量化:**additive**（現有 company_tasks/ksa_items relational + document_versions JSONB 已是權威 hybrid，深問輸出沒變）→ 排除 restructure（純增 migration 風險）。
- **D10 模型**：成本優先+中文開源 → 帶出**資料落地風險**（中文官方 API 走中國伺服器，SaaS 多客戶有合規風險）→ 解法**西方託管 OpenAI-相容**；使用者要「同家公司、CP值最高」→ 提問「**鎖 google 什麼意思?**」→ 釋疑**軟鎖**（gateway OpenAI-相容日後可搬；OpenRouter 一窗口可挑當下最便宜、改字串即換、可設 data-policy）→ 選 **OpenRouter**。
- **D11 前端**：使用者提問「**哪個好、會難維護嗎?**」→ 解法:**漸進更好維護**（刪手刻 SSE plumbing、保留展示元件、混搭是官方正解；全面重寫只換風格一致卻丟可用 UI+風險）→ **漸進 wrap**。

---

## 引用來源（權威優先）

**官方 / 一手**
- Anthropic Engineering：[Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)、[Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)、[Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- LangChain/LangGraph docs：[Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)、[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)；[HITL with interrupt（blog）](https://www.langchain.com/blog/making-it-easier-to-build-human-in-the-loop-agents-with-interrupt)
- AG-UI / CopilotKit docs：[AG-UI State](https://docs.ag-ui.com/concepts/state)、[AG-UI Intro](https://docs.ag-ui.com/introduction)、[CopilotKit docs](https://docs.copilotkit.ai/)
- 12-factor agents（humanlayer）：[The 12 Factors](https://deepwiki.com/humanlayer/12-factor-agents/3-the-12-factors)
- DBOS：[Durable Execution for Crashproof AI Agents](https://www.dbos.dev/blog/durable-execution-crashproof-ai-agents)

**對照 / 評析**
- [OpenAI Agents SDK vs LangGraph（particula.tech）](https://particula.tech/blog/langgraph-vs-crewai-vs-openai-agents-sdk-2026)
- [Durable execution: Temporal/LangGraph/DBOS（agentmarketcap）](https://agentmarketcap.ai/blog/2026/04/10/durable-agent-execution-production-temporal-modal-event-sourced)
- [Best Database for AI Agents（pingcap）](https://www.pingcap.com/compare/best-database-for-ai-agents/)
- [pgvector vs Qdrant（encore.dev）](https://encore.dev/articles/pgvector-vs-qdrant)

---

## D8 釐清（2026-06-17）：深問「subgraph」= 單層 node loop，**不**在主圖掛真子圖

> 觸發：審視「骨幹③做到一半?」時，誤把 spec §4.1 字面「deep_interview subgraph」當缺口，把 star/five_w2h/indicator 重構成「主圖掛編譯子圖 + 迴圈回到子圖節點」（commit `8040d5a`）。測試全綠 → 以為成功。後讀 `plans/2026-06-16-phase3-deep-interview.md` 發現該寫法**牴觸已定設計**，深查後 revert，回到單層 loop。

**決策：維持 phase3 計畫的「單層 node loop」**——star/five_w2h/indicator 平鋪在主圖，逐任務以 `deep.current_task_index` 重新進入 `star`（每任務＝全新 interrupt 計數器）。D8「subgraph 可獨立測」由 `test_deep_subgraph.py` 的**獨立測試用小圖**滿足，**不在 app code 出貨子圖殼**。

**理由（權威 + 實證）：**
1. **上游已知 bug，正中我們的形狀**：`langchain-ai/langgraph#6792`（**OPEN**，影響 1.0.8／含我們的 **1.2.5**）：interrupt 在 subgraph 內時，resume 會**重跑前面節點 + 重複 interrupt**，且「**頂層圖不會發生**」。深問每任務有 4 STAR + 多個 5W2H interrupt，放子圖即暴露於此。相關群集：#4796（子圖 restart 非 resume）、#30518（resume 停在 interrupt 前→無限迴圈）、#4028（單次 invoke 無法 resume 多 interrupt）。#2870（多 interrupt resume 值複用）已於 0.2.x／PR#3054 修，我們版本無此支。
2. **我的綠燈是假信心**：2-task loop 測試每次都用**同一句答案** resume → 連「resume 值被複用」這類 bug 都驗不出；e2e 也沒斷言「無重複 LLM 呼叫／無節點重跑」。通過 ≠ 正確。
3. **YAGNI / Anthropic「只在明顯改善時才加複雜度」**：單層 loop 已達同樣模組化與可測性；真子圖只增風險面，無可證的好處。

**來源**：[langgraph#6792](https://github.com/langchain-ai/langgraph/issues/6792)、[#4796](https://github.com/langchain-ai/langgraph/issues/4796)、[#2870](https://github.com/langchain-ai/langgraph/issues/2870)（已修參照）、[LangGraph Subgraphs 官方](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)、[Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)。

**後續注意**：若哪天升級 LangGraph 後 #6792 類問題確認修復、且真有跨任務模組化需求，再評估子圖；屆時測試必須以**不同答案**逐 interrupt 驗證、並斷言節點不重跑。spec §4.1 字面「subgraph」應讀作本條釐清。

---

## Phase ④ 設計決策（2026-06-17）：assemble_ksa + build_doc

> 規劃 Phase ④（深問之後的收尾：K/S/A 組裝 + OCS 文件生成）時的設計選擇。依據 spec §2/§9.4/§9.5/§12、D6/D8/D9。

**D13 — build_doc 用 deterministic 組裝為主、LLM 近乎不用。**
- 選擇：OCU 分組**直接用 catalog `task_pool` 的 unit 結構**（catalog 本就分好 unit）；編碼（T/P/O/K/S/A）、indicators/outputs 注入、display label/evidence_refs 全**程式化**；K/S/A 來自 assemble_ksa（catalog+公司）；LLM 不用或僅選配潤飾。
- 理由：資料進到 build_doc 時**已是結構化**（catalog K/S/A + 深問 indicators）。對已結構化資料組裝合規文件，業界共識是「separate reasoning from execution」：deterministic 組裝可稽核/可測/零成本/低延遲、忠於 catalog；LLM 只該用在非結構推理。呼應 D4（12-factor：deterministic 骨幹 + LLM 只在關鍵節點）。
- **ocs_builder 不 import**：舊 `app/graph/nodes/ocs_builder.py` 綁死 `icap_retriever`(已移除 pgvector RAG) + 舊 `llm_gateway` + 舊扁平 state。D8 表「保留 ocs_builder」實為**重用其輸出結構/編碼邏輯**（OCS JSON 形狀、T/P/O/K/S/A 編碼、display label、evidence_refs），於 graph_v3 **重寫（port）成 deterministic build_doc**。
- 來源：[hybrid doc automation（Parseur）](https://parseur.com/blog/llms-document-automation-capabilities-limitations)、[Compiled AI（arXiv 2604.05150）](https://arxiv.org/pdf/2604.05150)、[Anthropic Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)。

**D14 — 深問豐欄位（star_case/5W2H/behavior_indicators）暫不落 `company_tasks`，延後。**
- 選擇：build_doc 直接讀 graph state（checkpointer 持久化）；of-record 輸出 = `document_versions.content`(JSONB，內嵌 evidence_refs) + `ksa_items`（關聯式 K/S/A）。`company_tasks` 維持只存任務 metadata。
- 理由：豐欄位已內嵌於最終文件與 evidence_refs，在 `company_tasks` 再存一份**冗餘**；spec §12 本就把「5W2H 欄→JSONB details 微重構」列為未來。**推翻**先前（在誤判 #3 為 Phase ③ 缺口時）暫定的「加 behavior_indicators JSONB 欄」——context 已變。
- 來源：D6（checkpointer=工作態 of-record）、spec §12。

**Phase ④ 範圍**：`finish_deep→assemble_ksa→build_doc→preview` 接線；`assemble_ksa`（catalog pairs+by-id + 公司補充 + interrupt 編輯 + flush `ksa_items`）+ `KsaRepo`；`build_doc`（deterministic port + 寫 `document_versions`）+ `DocRepo`。`KsaRepo/DocRepo` 比照 `TaskRepo`（D9）。

✅ Phase ④ 已完成（2026-06-17，commits bbec82a..01e7951，42 passed）。

---

## Live-wire 設計決策（2026-06-17）

> 把 graph_v3 從 stub demo 接成真服務。依據 spec §3/§4.4、D5/D6/D7/D10。

**D15 — Live-wire 這期只做「A：讓 v3 變真」，不做「B：移除舊代碼」。**
- A：HttpIndexerClient（真 indexer HTTP）+ DbPersist（真業務表）+ AsyncPostgresSaver（真 checkpointer）接進 serving。
- B（延後）：刪 `app/graph/`（**保留** `app.graph.constants` + `app.graph.prompts.*`——graph_v3 的 deep_nodes/build_doc 仍 import 這些 pure-data 模組）、`icap_*`、`llm_gateway`、`ocs_builder`、舊 orchestrator。爆炸半徑大（動到 `main.py` 的 `api/routes/tasks.py`+`interviews.py`），值得單獨小心做。
- 理由：A 低風險（`copilotkit_app.py` 與 `main.py` 分離，舊路徑不動），可獨立驗證。

**D16 — DbPersist 在 live serving 用 session-factory、每操作一短命 session、各自 commit（write-through）。**
- 因 deps 在 app 啟動時一次性烤進 CopilotKit agent（`config={"configurable":{"deps":...}}`），無 per-request scope。新增 `LiveDbPersist(session_factory=AsyncSessionLocal)`：每個 persist 操作 `async with sf() as s` 開短命 session、委派現有 repos、`commit`。保留 `DbPersist(session)` 給測試/直接用。
- 理由：SQLAlchemy 2.x 共識「短命 session/unit-of-work、不跨請求共用」；session-per-op 正合 write-through（確認某步即落 + commit）。來源：[SQLAlchemy Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)。

**D17 — checkpointer（AsyncPostgresSaver）+ httpx client 由 FastAPI lifespan 持有；live app 為獨立入口。**
- lifespan 內：用 `AsyncExitStack` 進 `open_pg_checkpointer`（已存在的 @asynccontextmanager）→ `setup()`；以該 saver 建 graph_v3 + 建 live deps + `add_fastapi_endpoint`；shutdown 關閉。**不**在會關閉的暫時 `async with` 裡建圖（否則抓到已關連線）。
- 新 `app/copilotkit_live_app.py`（production 入口，`uvicorn app.copilotkit_live_app:app`）；**保留** `copilotkit_app.py`（demo，MemorySaver+stubs）給測試/無依賴本地跑。
- 來源：[LangGraph+FastAPI lifespan](https://medium.com/@termtrix/i-built-a-langgraph-fastapi-agent-and-spent-days-fighting-postgres-8913f84c296d)、[langgraph-checkpoint-postgres](https://pypi.org/project/langgraph-checkpoint-postgres)（已裝 3.1.0 + psycopg 3.3.4）。

✅ Live-wire A 已完成（2026-06-17，commits 6e27ad8..dbad55d，46 passed）。

---

## Concern B 決策（2026-06-17）：移除舊代碼

**D18 — 現在就移除舊代碼；constants/prompts.indicator 搬進 graph_v3 後全刪 `app/graph/`。**
- 時機：選「現在刪」而非 strangler-fig 正統的「等 live 端到端驗證後」。理由：舊碼在 feat/v3 已是 dead path、**零測試依賴**、`master` demo 為 fallback、git 可 revert。**Caveat（誠實記錄）**：v3 live app 尚未對真 indexer/OpenRouter 跑過端到端 → 嚴格 strangler-fig 下略早；風險由 master fallback + git history 緩解。來源：[Shopify strangler-fig](https://shopify.engineering/refactoring-legacy-code-strangler-fig-pattern)、[techdebt.best](https://techdebt.best/playbooks/strangler-fig/)。
- **搬遷**：`app/graph/constants.py`→`app/graph_v3/constants.py`；`app/graph/prompts/indicator.py`→`app/graph_v3/prompts/indicator.py`（+空 `__init__`）。star/interview prompts 為 dead（graph_v3 未用，star_node 用 deep_nodes 內聯 `_STAR_REFINE`）→ 不搬、隨 app/graph/ 一起刪。
- **改 import（3 處）**：`app/graph_v3/deep_nodes.py`、`app/api/routes/tasks.py`、`tests/test_deep_five_w2h.py`。`build_doc.py` 不涉及。
- **刪**：整個 `app/graph/`、`app/services/{icap_matcher,icap_retriever,interview_orchestrator,state_service}.py`、`app/api/routes/interviews.py`（舊 `GET history`+`POST chat`）+ `main.py` 的 import/include。
- **保留**：`document_service.py`、路由 users/job_profiles/tasks/documents。config 的 `icap_*` settings 變 dead 但無害（暫留）。

✅ Concern B 已完成（2026-06-17，commits 8033cc3..f9ad0a6，55 passed；app/graph/ 全消失）。

---

## Phase ⑤ 決策（2026-06-17）：OTel + eval 閘門

**D19 — OTel 用手動 SDK span，不用 auto-instrumentation 庫。**
- 關鍵洞察：逐節點（業務）span 兩種做法都得手動；auto-instrumentation 只自動產生 LLM 呼叫層 span+token。我們**只有一個 LLM gateway**（`OpenRouterLlm`），自抓 token（langchain `AIMessage.usage_metadata`，已驗 langchain-core 1.4.7 可用）僅 ~15 行 → auto 省的不划算，卻多背全域包 langchain 的依賴。
- 做法：`opentelemetry-sdk` + OTLP exporter（endpoint 由 env 配，預設不掛 processor＝近 no-op）；`gen_ai.*` 實驗性語義慣例（system/request.model/usage.input_tokens/output_tokens、operation.name）；node 用 decorator 包 span，LLM 在 gateway 包 span（model/tokens/latency）。可用 `InMemorySpanExporter` 單測。cost 暫以選配 price map 估（無則略）。
- 理由：12-factor own-it、廠商中立（OTLP→日後接 Langfuse 自建只改 endpoint，D12）、慣例仍 experimental 不想被庫綁。來源：[OTel GenAI 慣例](https://opentelemetry.io/blog/2026/genai-observability/)、[Uptrace](https://uptrace.dev/blog/opentelemetry-ai-systems)。

**D20 — Eval：輕量自製 harness、deterministic-first；LLM-judge/框架延後。**
- 3 類 eval（spec §7）大多可 deterministic：① zh-TW+嚴格 JSON（parse 成功+必填 key+CJK/無英文洩漏）② 深問品質（用既有 `quality_score`+結構完整度）③ 文件正確性（build_doc 本就 deterministic：編碼/分組/K-S-A 注入/無缺欄）。
- 結構：`backend/evals/checks.py`（純函式，用 fixtures **單測**）+ `datasets/` + `run_eval.py`（CLI，跑時打**真** OpenRouter 套 checks，當換模型閘門，**不進**一般 pytest）。
- 理由：鐵律「能 deterministic 就必須 deterministic」；judge 非確定、**zh-TW judging 不可靠**、「絕不可當唯一閘門」、要錢。合我們 deterministic-backbone（D4/D13）。等遇到「deterministic 抓不到的品質退化」再加 judge（YAGNI）。來源：[DeepEval LLM-as-judge](https://deepeval.com/guides/guides-llm-as-a-judge)、[Evidently](https://www.evidentlyai.com/llm-guide/llm-as-a-judge)。
- **範圍外**：Langfuse 自建 dashboard（D12，後話）；LLM-as-judge 品質評分。

✅ Phase ⑤ 已完成（2026-06-17，commits f9ad0a6..5cdb186，67 passed）。

---

## 前端決策（2026-06-17）：CopilotKit 接 interrupt（D11 落地）

**D21 — 薄切片先行 + 「我寫、使用者瀏覽器驗」。**
- 背景：前端（`frontend/`，Next 16 + React 19）**零測試框架**，CopilotKit interrupt UI 難自動測，且 `frontend/AGENTS.md` 警告 Next 16 有 breaking changes（寫前讀 node_modules 文件）。後端的「pytest 全綠＝完成」在前端行不通——驗證只能瀏覽器手動（需 live 後端 + indexer + 金鑰 + `next dev`），我代跑不了。
- 方向：**薄切片**——Slice 1＝裝 CopilotKit + `/api/copilotkit` runtime route（→ 後端 `/copilotkit` CopilotKitRemoteEndpoint）+ `<CopilotKit>` provider（Providers.tsx）+ 接 1 個 interrupt（`select_profile`，重用展示元件），使用者瀏覽器驗通後再迭代其餘 4 interrupt + `useCoAgent` 共享 state + 退役 `useInterview`。
- 執行：**我寫碼**（對齊 Next16/CopilotKit 文件 + `tsc/next build` 靜態檢查），**使用者在瀏覽器驗** round-trip。subagent+pytest-gate 模型不適用（無測試閘門）。
- 技術模式（研究）：`copilotRuntimeNextJSAppRouterEndpoint` + `CopilotRuntime`（remoteEndpoints 指後端，因後端用 copilotkit `CopilotKitRemoteEndpoint`）；`useCoAgent`；`useLangGraphInterrupt`。來源：[CopilotKit Interrupt Flow](https://docs.showcase.copilotkit.ai/langgraph-python/human-in-the-loop/interrupt-flow)、[LangChain×CopilotKit](https://docs.langchain.com/oss/python/langchain/frontend/integrations/copilotkit)、D11。

**D22 — Slice 1 瀏覽器驗證踩到版本不相容 → 改走 AG-UI 直連（`ag-ui-langgraph`）。**
- 症狀：`useAgent: Agent 'jd_authoring' not found ... No agents registered`。後端 `/copilotkit/info` 正確列出 agent（`type: langgraph_agui`, `sdkVersion: 0.1.94`）但 JS 1.60 runtime 不註冊。
- 根因（研究）：python `copilotkit` PyPI 最新即 **0.1.94（legacy 線）**，其 `CopilotKitRemoteEndpoint` 與新 JS `useAgent` **已知不相容**（CopilotKit issue **#2898**：「CopilotKitRemoteEndpoint not compatible to useAgent in v1.50.1」；#1907 handshake bug）。2026 主流已轉向 **AG-UI 協定**（CopilotKit = frontend+runtime+agent over AG-UI）。
- 決策：**改 Option B（AG-UI 直連）**——翻轉先前「先 A 降版」的暫定建議，因 A 會鎖進 legacy+已知 bug 線。後端改用 **`ag-ui-langgraph`（PyPI，2026-06 發布，0.0.41）** 的 `LangGraphAgent(graph, config={"configurable":{"deps":...}})` + `add_langgraph_fastapi_endpoint`（已驗證 API 支援傳 config/deps + 用我們的 compiled graph + AsyncPostgresSaver）；前端 `CopilotRuntime({agents:{jd_authoring: HttpAgent/@ag-ui/langgraph}})` 直連，JS 維持 1.60。
- 來源：[AG-UI Protocol](https://www.copilotkit.ai/blog/ag-ui-protocol-bridging-agents-to-any-front-end)、[CopilotKit×LangGraph 架構](https://docs.copilotkit.ai/langgraph-python/concepts/architecture)、[ag-ui-langgraph PyPI](https://pypi.org/project/ag-ui-langgraph/)、[CopilotKit #2898](https://github.com/CopilotKit/CopilotKit/issues/2898)。
- 連帶：`copilotkit` python 套件改用 ag-ui-langgraph 後變 dead dep（可後續移除）；demo serving 一併遷移、更新 serving 測試。

### Slice 1 整合踩雷紀錄（bugs / 根因 / 修法）—— 2026-06-18 瀏覽器驗證過程

1. **`uv run uvicorn` 抓到全域 Python 3.14（無 copilotkit）** → `ModuleNotFoundError: copilotkit`。根因：專案無 `pyproject.toml`，`uv run` 不認 `backend/.venv`，退回全域直譯器。**修**：用 venv 直跑（`.venv\Scripts\python ...`），不要 `uv run`。順帶：venv 原本沒裝 `uvicorn`（requirements 有 pin 但沒裝），已補裝 0.30.6。
2. **psycopg async 在 Windows ProactorEventLoop 掛** → `Psycopg cannot use the 'ProactorEventLoop'`。根因：uvicorn 在 Windows 預設 Proactor，AsyncPostgresSaver(psycopg) 需 SelectorEventLoop，且 policy 要在 loop 建立前設。**修**：新增 `backend/run_live.py` 啟動器，於 import uvicorn 前 `asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())`。
3. **CopilotKit JS 1.60 `useAgent` 不認 python `copilotkit` 0.1.94 `CopilotKitRemoteEndpoint`** → "Agent 'jd_authoring' not found / No agents registered"。根因：版本/協定 skew（CopilotKit #2898）。**修**：見 D22，改 AG-UI（ag-ui-langgraph）。
4. **Next runtime fetch 後端 "fetch failed"（後端零 log）**。根因：Node/undici 在 Windows 把 `localhost`→IPv6 `::1`，uvicorn 只聽 IPv4 `127.0.0.1`。**修**：route 的 `COPILOTKIT_REMOTE_URL` 預設改 `http://127.0.0.1:8001/copilotkit`。
5. **v1 `useCoAgent().run()` headless 崩** → `Cannot set properties of undefined (setting 'abortController')`。根因：v1 run() 非 headless-safe。**修**：改用 v2 `useAgent().runAgent()`。
6. **interrupt 選單不顯示（無錯）**。根因：v1 `useLangGraphInterrupt` 只在 `<CopilotChat>` 內渲染；我們是自製無聊天 UI。**修**：改用 v2 `useInterrupt({renderInChat:false})`（回傳 ReactElement 自己擺）。`event.value` 為 payload（容錯：若為 JSON 字串則 parse）。
7. **resume 報 "terminated"**。根因：URL 的 `job_profile_id` 非合法 UUID（如 "test1"）→ pick_profile resume 時 `set_selected_ocs` 查 `JobProfile.id` 觸發 asyncpg `invalid UUID` DataError → SSE 串流中斷。**修**：URL 用真 JobProfile UUID（測試用 `0e2df66b-e0eb-4bbd-971a-ad0e816425eb`）。
8. **（已知，未修）indexer 冷啟動首次 search 超過 30s `indexer_timeout_s`**（暖機後 0.4s）。建議調高預設或 indexer 啟動自我暖機。

### Slice 2（2026-06-18）：edit_tasks 接線 + select_profile 改複選（有序＝優先度）

**D23 — `select_profile` 由單選改複選，點選順序＝優先度。** 使用者明確要求「職位要可複選、用選擇順序排序優先度」。
- 後端（純 indexer、無 LLM，現可瀏覽器驗）：
  - `state.ProfilePick` 加 `selected_ocs_codes: list[str]`（有序）；保留 `selected_ocs_code`=primary（=第一個），相容既有 `JobProfile.selected_ocs_code` 欄位 → **免 migration**。
  - `pick_profile`：resume 經 `_resume_to_codes` 容錯解析 `{"ocs_codes":[...]}`｜舊 `{"ocs_code":"x"}`｜純字串；primary 寫進既有欄位，完整有序清單留 checkpoint state。
  - `build_task_pool`：讀 `selected_ocs_codes` 餵 `task_pool(codes)`（indexer 本就吃 list），再 `_sort_by_priority` 依 codes 順序穩定排序任務後 flush（任務帶 `indexer_ref.ocs_code` provenance，list 順序即優先度）。
  - TDD：新增 `test_pick_profile_multi_select_keeps_order_as_priority`、`test_task_pool_orders_tasks_by_ocs_priority`；全套件 58 passed / 11 skipped。
- 前端：`ProfilePicker` 改複選（點選顯示順序徽章 1/2/3…、可取消、確認鍵），`resolve({ ocs_codes })`（物件，非字串）。
- `edit_tasks` 一併接線：`TaskCurator`（依 unit 分組、預設全保留、可勾掉、確認）→ `resolve({ tasks })`（物件契約，後端讀 `edited["tasks"]`）。
- **待瀏覽器驗**：(a) 物件 resume（`{ocs_codes}` / `{tasks}`）序列化是否如預期（Slice 1 只驗過字串 resume）；(b) 多 OCS task_pool 任務排序；(c) 後端需重啟（`run_live.py` 無 --reload）才吃到 nodes/state 變更。
- 深問（ask_human）/edit_ksa/preview 仍擱置（需 LLM API）。

### Slice 3 踩雷（2026-06-18）：前端 seed 漏 `deep` → route_deep KeyError

- 症狀：選完職類、整理任務後**進深問**時前端報 "terminated"；後端 `graph.py:13 route_deep` `KeyError: 'deep'`（`state["deep"]["current_task_index"]`）。
- 根因：v3 頁用 `agent.setState({...})` seed 整個 InterviewState，但**漏了 `deep` key**（後端 `new_state()` 有，前端手寫 seed 沒同步）。Slice 1 只走到 edit_tasks 邊界、沒進 route_deep 所以沒爆；深問接上後流程繼續才觸發。
- 修：前端 seed 補完整 `deep: {current_task_index:0, slots_by_task:{}, missing_fields:[], completed_task_ids:[], retry:{}}`，對齊 `new_state()`。
- 教訓：**前端 `agent.setState` 必須提供完整 InterviewState**（deep 節點直接讀 `state["deep"]`，非 `.get`）。日後加 state 欄位要同步前端 seed；或改由後端 new_state 初始化、前端只送 inputs（較大重構，暫不做）。

### Slice 3 踩雷②（2026-06-18）：catalog 預填未容錯 → indexer 502 炸節點

- 症狀：深問跑完一個任務的 STAR、進 `five_w2h` 時前端 "terminated"；後端 `five_w2h_node` → `_prefill_from_catalog` → `tasks_by_id` → `httpx.HTTPStatusError: 502 Bad Gateway for /tasks/by-id`。
- 根因：indexer 的 `/tasks/by-id` 回 502（indexer 端問題，另一 repo；search/task-pool/pairs 都正常）；而 `_prefill_from_catalog` 的呼叫**未容錯**，例外直接冒泡炸掉節點 → 串流中斷。
- 架構定位：catalog k/s/output 是 **just-in-time prefill**（架構 §line33/135），是便利層、非 of-record（人答才定稿）。依「deterministic 骨幹 + 容錯降級」哲學該優雅降級。
- 修：`_prefill_from_catalog`（tasks_by_id）+ `assemble_ksa`（pairs）都包 try/except → 失敗就跳過/空 draft，由 5W2H/edit_ksa 問人。58 passed。
- **待辦（indexer 端，非本 repo）**：`S:\jd-ocs-indexer` 的 `/tasks/by-id` 502 要查；修好後 outputs 才會自動預填（現在會問人）。相關 [[jd-ocs-indexer-service]]。

## D24 — 收尾段重設計：逐任務 K/S + 全域 A + REVIEW（2026-06-18，brainstorming）

> 緣由：使用者發現使用者流程與設想有出入。經 brainstorming + 權威資料佐證重設計。完整 design：`2026-06-18-ksa-flow-redesign-design.md`。

- **權威依據**：OCS 職能基準結構（indexer `models/ocs.py`）——K/S 在每個任務的 `competency_blocks`（task 層）、A 在頂層 `ocs_attitude`（職類層）。indexer 供應：`tasks_by_id→k_pairs/s_pairs`（task 層）、`pairs→attitudes`（職類層）。→ 現況 `assemble_ksa` 全從 `pairs()` 撈 K/S/A 一步做完，**結構錯**。
- **HITL 主流**（LangGraph 官方 approve/edit/reject + idempotency-on-resume；CopilotKit controlled gen-UI）：單一可編輯審閱面把選+改合一；node 從 interrupt resume 會整個重跑 → fetch 要 idempotent。
- **決策**：
  - 拆 `assemble_ksa` → `curate_ks`（**全部訪談完後**逐任務審閱面，單層迴圈鏡像 deep loop）+ `curate_attitudes`（全域一次）。
  - 每個 curate 步（任務/KS/A）= **單一可編輯審閱面**（勾/改/增/刪→確認），標 provenance。
  - **KS 來源 interim = `pairs()` 職類池**（因 `tasks_by_id` 502）：每任務候選同一份池、人逐任務挑；`tasks_by_id` 修好後升級 per-task。
  - A 全域，從 `pairs().attitudes`。
  - REVIEW = 唯讀預覽 + 確認存 `document_versions`（跳回編輯屬範圍外）。
  - idempotency：`pairs()` 整段只打一次、快取進 state，迴圈共用、resume 不重打。
  - **(2026-06-18 細節定案)** KS 審閱面**預設全不勾**（人逐任務挑）；flush **集中最後一次**；of-record 用既有 **`ksa_items.task_id`**（K/S 帶 task_id、A=NULL，**無 migration**）。
- **留給 writing-plans**：state 欄位/reducer、interrupt payload 形狀、任務→`company_tasks.id` 對應、`ksa_items` 重寫策略（見 design doc §7）。

### D24 實作完成（2026-06-18，subagent-driven TDD）

commits `896b377..91908f1`（feat/v3）。後端 Tasks 1–6 + 前端 7–8 + 最終 review fix。全套件 62 passed/10 skipped、前端 tsc+eslint clean。
- 新節點 `fetch_ksa_pool`/`curate_ks`（逐任務單層迴圈）/`curate_attitudes`；`assemble_ksa` 已刪。
- `KsaRepo.flush(by_task=, attitudes=)`、of-record 用 `ksa_items.task_id`（K/S 帶 task_id、A=NULL，無 migration）。
- 前端 `CurateKsPanel`/`CurateAttitudesPanel`（單一可編輯審閱面、預設全不勾）取代 `KsaEditor`；`DocPreviewPanel` 顯示每任務 K/S。
- 最終 review 抓到 Critical：兩個 DB 測試漏改新簽章（被 DB-skip 遮住），已修。
- **待**：瀏覽器 e2e 驗收（流程走到逐任務 KS → A → REVIEW → 存檔）。tasks_by_id 502 修好後把 KS 來源升級 per-task（D24-c）。

## D25 — DB 改文件導向（修訂 D6/D9）（2026-06-18，討論 + 權威佐證）

> 完整 design：`2026-06-18-db-document-centric-design.md`。緣由：討論「何時存 DB/什麼欄/哪些表」時發現 v3 實際只用關聯表一小部分。

- **翻轉 D6/D9**（業務表 of-record + write-through）→ **文件導向**：of-record = 有版本的 `document_versions.content` JSONB（整份 OCS 文件）。延續 D14（深問細節不落業務表）。
- **業務表精簡到 3 張**：`users`、`job_profiles`（砍 graph_state/stage/completion_pct/icap_source_type/document_draft/tenure_months/primary_stakeholders；`selected_ocs_code`→`selected_ocs_codes TEXT[]`）、`document_versions`（砍 file_path/format）。
- **全 drop**：`company_tasks`、`ksa_items`、`icap_references`、`interview_sessions`、`icap_embeddings`(+vector ext) + 對應 models。
- 工作態（任務/深問/KS/A）全在 LangGraph checkpointer。寫 DB 點：建檔(users/job_profiles)、pick_profile(selected_ocs_codes)、build_doc 確認(document_versions)。
- **權威依據**：JSONB「無查詢需求即可、長成 mini-schema 再正規化」；LangGraph 三層分離（checkpointer/store/業務 DB）；Alembic 為 SQLAlchemy migration 主流；expand-contract 的 contract 前提（舊 code 已移除）已滿足 → 可直接破壞性清理（未上線）。
- **取捨**：任務/KSA 失去 SQL 查詢/單欄編輯（目前無需求）；未來有需求再正規化（JSONB→欄，容易）。
- **範圍**（persistence 層重作）：Alembic 導入 + drop 表/欄 + 砍 4 個 model + PersistPort 縮成 set_selected_ocs/save_document（刪 TaskRepo/KsaRepo/flush_tasks/flush_ksa）+ 節點調整 + 連帶清舊 documents.py/main.py demo + 更新測試。
- **使用者已核准方向（2026-06-18）**；下一步 writing-plans。

## D26 — MVP 範圍（2026-06-18，scope 討論）

> 使用者察覺 scope creep，定 MVP 先行、再迭代（YAGNI）。

- **MVP IN**：已建的完整流程（建檔→選職類→任務 curate→深問→KSA→REVIEW→存檔）＋ **D25 文件導向乾淨地基（現在做）**＋ **resume（重開 profile 接續既有 checkpointer thread；目前 persistence 已免費，只缺前端接續）**＋ 瀏覽器 e2e 驗收。
- **MVP DEFER**：① 完成後可隨時編輯 JD（需單獨設計：thread time-travel / 文件編輯器 / 關聯化單欄改——文件導向皆接得住，不卡死）；② 匯出 docx/pdf；③ indexer 搜尋品質 + tasks_by_id 502（別的 repo）；④ 多租戶/RBAC；⑤ 進階觀測 dashboard。
- **順序**：先 D25 地基 → 再 resume + e2e → MVP 完成。
- resume 釐清：LangGraph checkpointer 已持久化 thread（隨時退出/續做免費）；前端需從「每次重 seed」改成「偵測既有 thread 則接續」。

### D25 實作完成（2026-06-18，subagent-driven + DB 實地重建 + e2e）

commits `ff4355e..c816f86`（feat/v3）。後端 8 task（Alembic/models/baseline/schemas/persistence/nodes/routes/sweep）+ opus 終審 + DB 重建 + 瀏覽器 e2e（使用者確認「可以」）。
- 業務表 = `users`/`job_profiles`/`document_versions`；`company_tasks`/`ksa_items`/`icap_*`/`interview_sessions` + 4 models 全刪；Alembic 管 schema（raw SQL migrations 移除）；persistence = `ProfileRepo.set_selected_ocs` + `DocRepo`。
- e2e 抓到並修：① `selected_ocs_codes` nullable 無 default → NULL → JobProfileOut 500 → 設 NOT NULL default `'{}'`（3cb4aa0）；② 前端 `ensureUser` 不驗證快取 user → DB 重置後 404 卡死 → 改成驗證+404 重建（c816f86）。
- 後端 suite 61 passed/4 skipped。of-record = document_versions JSONB；任務/KSA/深問細節在 checkpointer。

### Resume 調查（2026-06-18，未完成 → 擱置）

目標：重開 profile 接續既有 checkpointer thread（D26 MVP 項）。調查發現 CopilotKit v2 **headless** 設 thread 不直觀：
- `useAgent({agentId})` 只回 `{agent}`、**不收 threadId**；直接 `agent.threadId = id` 被 `react-hooks/immutability` lint 擋（且 fragile）。
- threadId 的正規入口是 `<CopilotChat threadId>` prop（但我們 headless、不用 chat），或 v1 風格 `CopilotContext.setThreadId`（line 458）/ `CopilotChatConfigurationProvider`——**哪個被 v2 `useAgent` 真正讀取，未從型別確認**。
- 後端機制已清楚：`AbstractAgent` 的 `AgentConfig` 收 `threadId`/`initialState`；thread 釘好後，resume = `runAgent()` 不 setState → LangGraph 從 checkpoint 的待答 interrupt 重新冒出（ag-ui-langgraph 轉 `__interrupt__` → useInterrupt 重渲染）。
- **下一步（未做）**：研究 CopilotKit v2 headless thread API（`CopilotChatConfigurationProvider` / `setThreadId` / `useThreads`）+ 瀏覽器反覆驗證。需獨立 focused session，不宜在超長 session 尾端硬幹。已還原半成品改動、tree 乾淨。

## D27 — 前端「文件即工作台」UX 重設計（2026-06-21，討論 + 權威佐證）

> 完整 design：`2026-06-21-frontend-canvas-ux-design.md`。緣由：原 v3 前端是線性 wizard 煙霧殼；使用者提出「**文件（職務說明書）才是主角，流程只是把空格填起來的工具**」，要能隨時看、隨時改、走完也能回來改。

- **權威依據（2026）**：ShapeofAI《Auto-fill》（按需逐格填、先示範再套用）；Agent UX 2026 / builder.io（一個高價值 artifact + 漸進信任）；Google Cloud agentic patterns（結構化骨架 + 局部 bounded agent 的混合式最可靠）；CopilotKit Generative UI / CoAgents Research Canvas。→ 結論：採 **document-as-interface**。
- **決策（使用者 AskUserQuestion 三選）**：
  - **Model 2 文件即工作台**（非線性 wizard、非純空白表）：先 seed 骨架（pick_profile+task_pool+fetch_ksa_pool），之後攤開可互動表格、**自由點空格填**。
  - **同一張表編輯**：無獨立編輯模式；建立=編輯=續做同一畫面；點已填格就地改/重填。
  - **自由順序**：seed 後不強制逐任務走完。
  - 樣式：先乾淨設計系統（Tailwind + `components/ui/*`）。
- **後端拆解**：線性 `build_graph_v3` → **seed graph**（pick_profile→build_task_pool→fetch_ksa_pool→END）+ **單格 filler**（`fill_task_interview` 重用 deep_nodes 單任務、`fill_task_ks` 把 curate_ks 去 for-loop 單任務化、`fill_attitudes`≈curate_attitudes）。filler 傾向各一 AG-UI 端點、新鮮短命 thread。舊大圖可選留作 autopilot（非 MVP）。
- **Persistence 精修 D25**：新增**連續儲存的 draft**——seed 後建 `document_versions(status='draft')`，每格 filler 完成 PATCH 更新 JSONB；checkpointer 角色縮小到「進行中那一格」。新端點 `GET/PATCH /job-profiles/{id}/document` + `POST .../finalize`（snapshot final，reuse `_assemble`）。
- **resume 連帶解套**：工作態落在 draft 文件而非長 thread → **CopilotKit v2 headless threadId SPIKE 風險大降**；跨 session 續做＝載入 draft JSONB；進行中未完成的格採「回來重跑該格」（不需精準續答暫停 interrupt）。
- **Dashboard**：用 draft/final 判定 未開始/進行中(完成度%)/完成；list 端點補 `doc_status`/`completion`。
- **範圍**：IN＝工作台+可互動表格+單格 filler+draft 連續存+同表編輯+續做+finalize+dashboard 狀態+錯誤 banner；OUT＝匯出、拖拉排序、多 agent、indexer 修正、進行中 interrupt 跨 session 精準續答。
- **使用者已核准方向（2026-06-21）**。下一步：§C 兩個 [驗證] 小 spike（AG-UI run 中 state 推送 + 短命 filler thread + useInterrupt）→ writing-plans → subagent-driven 實作。

### D27 定稿（2026-06-21，多輪討論後；修訂前述 D27 的「per-cell LangGraph filler」段）

> 完整 design 已更新：`2026-06-21-frontend-canvas-ux-design.md`。下列定案**取代**前述 D27 中「每格一次性 LangGraph filler（α）」的構想。

- **catalog 定義入檔**：catalog = `jd-ocs-indexer` 的 OCS 職能基準知識庫（檢索、非 LLM）。OCS schema 契約由 `S:\jd-pdf-to-json` README 定義、indexer 供應、我們產出（三方同契約）。我們的職務說明書 = 一份合法 OCS JSON。
- **填格手段（β REST-first）**：LLM 延後後，curate 本質是 CRUD → K/S/A/O/P 全走 `GET 候選池 + 表單 + PATCH document`，**MVP 完全不跑 LangGraph/AG-UI**；既有 interrupt 面板「UI 元件」重用（resolve→POST）。**連帶：CopilotKit v2 headless threadId SPIKE 在 MVP 消失**。
- **手打優先原則**：每格基準＝使用者自己打；catalog 候選 / LLM 為疊加加速器。**O/P = 手打兩清單（產出 + 績效/行為指標）**；K/S/A = catalog 候選選單。
- **LLM 是核心、但延後，且形態＝全域 CoAgent**（非每格小 graph）：一個看得到整份 document + 全對話的大 session，over document shared state，對話中提議填任一格、人核准（HITL）。CopilotKit/AG-UI/LangGraph 在此回歸（正用途）。現有 `deep_nodes` 逐任務 STAR 大概率被此 CoAgent 重塑，先留不動。
- **文件 of-record = OCS 契約**（5 區塊 version_info/ocs_profile/ocs_content/ocs_attitude/notes）；draft 連續寫（`document_versions status='draft'`，每格 PATCH）；finalize 產合法 OCS JSON（可套 jd-pdf-to-json `validate`）。`version_info` 用我們自己的版本管理。
- **每任務一個 competency_block**（schema 仍支援多 block、不鎖死）：
  - `competency_level` = block 可空屬性（每任務一個）；**K/S 才是 block 真正分界訊號**（依 jd-pdf-to-json §6.3.2/§6.3.6）；MVP 多半 `null`、catalog/LLM 帶才有、**不做輸入控制**。
  - **K/S 每任務寫一次（不 denormalize 到每個 P）**：避免重複維護、對齊官方 PDF 排版、匯出即一個 block。底下列多個 O + 多個 P。
- **unit（主要職責 `ocu_units`）保留**為分區（對齊契約）。`task_codes` 為陣列（同格多 T code 時 >1，通常 1）。codes 與 names 並存。
- **使用者永遠看不到「block」字眼**；畫面只有「任務 + 其 O/P/K/S/級別」，unit 分區。
- **使用者已定案（2026-06-21）**。下一步：writing-plans → subagent-driven 實作（順序見 design §實作分塊；§C 無 LangGraph spike，MVP 風險低）。

### D27 e2e bug log（2026-06-21，瀏覽器驗收逐一修復，均已 commit）

1. **live app 沒掛 documents router**（T3 疏漏）：新 `documents.py` 只在 `main.py` include，沒在 `copilotkit_live_app.py`（前端實連的 :8001）→ 工作台端點全 404。修：live app 補 `include_router(documents.router)`（commit 23a054a）。
2. **重複 task_code React key crash**（多職類撞號）：`skeleton` 只用 `unit_id` 分組，不同職類都從 T1/T1.1 編號 → 同 unit_id 被合併 → 同一 unit 出現兩個 T1.1 → React duplicate key。修：分組鍵改 `(ocs_code, unit_id)` + 整份遞進重編 T{u}/T{u}.{t} + 每項 provenance/source；React key 改 index（commit e9c97dc）。
3. **〔選任務〕一直反灰**：使用者在選職類前先在空表動過手 → 產生一張 `ocs_code` 空的 draft；`GET document` 一有 draft 就回該 draft，而 FE 用 `doc.ocs_profile.ocs_code` 判斷有無職類 → 永遠空。修：`set_occupations` 改成會**刷新文件表頭**（就地更新既有 draft，或建只有表頭的 draft），`build-tasks` 亦刷表頭（commit a5fcb04，+回歸測試）。
4. **拖拉不能改順序 / 目標判斷錯**：碰撞偵測把 over 算成巢狀的「任務」而非「職責」→ 職責重排的判斷式不符 → 沒反應；同層任務拖到職責容器 → 變成接到尾端。修：onDragEnd 把 over 正規化（拖職責→換算成 over 所屬職責來重排；拖任務→over 是任務則精準插入、是職責則接尾端）（commit f3067af）。
5. **拖拉後畫面不同步、重整才正確**（根因級）：用「位置」當 dnd sortable id（`unit:0`/`task:0:1`），重排後 id 永遠 0,1,2… 沒跟著項目移動 → dnd-kit 判定沒換位、不重繪。修：每個職責/任務帶**穩定 id `_uid`/`_tid`**（隨項目移動、存進 draft 以跨存檔 round-trip 保持穩定），`ensureIds` 在載入時補；sortable id 改 `u:<uid>`/`t:<tid>`，onDragEnd 以 id 查現索引（commit 4a4ece9）。**使用者確認全部正確。**

> 通則教訓：(a) 新端點要同時掛 demo(main) 與 live app；(b) 文件 of-record 一旦有 draft，header/狀態要主動刷新（不可只更新 profile 欄）；(c) **dnd-kit 的 sortable id 必須是「隨項目移動的穩定 id」，不可用位置索引**，否則重排不重繪。

## D28 — LLM Agent（員工 AI 訪談 + 工作台副駕）（2026-06-22，多輪 UX-first 討論 + 權威佐證）

> 完整 design：`2026-06-22-llm-agent-design.md`。把延後的「核心 LLM」加入。緣由：D27 文件工作台已完成，回頭做 AI。

- **使用者/工作流定位**（關鍵）：顧問+員工；**員工先用系統產 80 分 → 顧問與員工精修到 100 分**。LLM ≈ 顧問初始訪談的自動化版（員工口語 → catalog-grounded 結構化草稿）。工作台(D27)＝精修工具。
- **權威依據**：工作分析（Task Inventory / CIT / 5W2H / 結構化訪談效度 .55–.70）；辨識>回憶；漸進揭露；CopilotKit「UI 層非 agent 框架」+ frontend/backend action 分離 + Direct-to-LLM（可不用 LangGraph、AG-UI 保證未來可換）；微軟 Copilot Autofill（建議/來源透明/不自動存）；Anthropic 多 agent 準則（單 agent+好 prompt 通常夠、先流程後自主）。
- **決策原則**：AI 提議-人定奪；catalog 優先(`tasks_by_id` 取官方 O/P/K/S)、AI 補(個人化/自訂)；辨識>回憶(catalog 勾選清單+CIT 補漏)；漸進揭露(核心任務才 5W2H+CIT 深問)；重要度分流深度；**解耦**(AI=自家無狀態專職端點、可測可換模型；document JSONB=單一真相源；CopilotKit=UI/HITL 層)；透明+安全(來源標記+理由+警語)。
- **架構**：`/ai/*` 5 端點（extract-tasks/structure-task/draft-op/recommend-ks/clarify）+ Claude(OpenRouter/Anthropic)；**CopilotKit 聊天+✨ 兩入口共用這些端點**，用 chat（非 headless useAgent，避開 v2 threadId 雷）+ useCopilotReadable + useCopilotAction(renderAndWaitForResponse HITL)→ 套用走現有 PATCH。**不用 LangGraph**（未來可換、前端不變）。K/S 升級 per-task tasks_by_id（補 D24-c）。
- **延後**：一鍵自動草擬整份（→未來多 agent 編排）、多帳號權限、PDF/docx、語音。
- **待 review（§F）**：重要度自動 vs 手動、5W2H 欄位精簡、intake 形式、工作筆記落點(export 剝除)、多帳號(先同檔)、LLM 模型/通道。
- **狀態：草稿待 review**；定案後 writing-plans → subagent-driven（後端端點先、各自可測）。

### D28 review 定案（2026-06-22）
- **MVP＝甲（結構化）**：核心全 UI 觸發（intake 表單 + 勾任務 + ✨ 面板）**直接 fetch `/ai/*`**，**不上 CopilotKit/聊天**；自由聊天副駕列 **Phase 2**（開放式問整份、顧問精修用）。
- §F 定案：① 砍重要度欄位（深淺由員工動作：✨深填/一鍵 catalog 輕量）；② 5W2H 卡片精簡+漸進（必填1格做什麼/產出、選填 CIT+收合細節）；③ intake＝一頁3格表單；④ 工作筆記存 `_notes`、export 剝除；⑤ 多帳號/權限**延後（很後面）**、MVP 同一份檔同工作區；⑥ LLM＝OpenRouter、預設便宜高CP模型、**可 per-function 換模型**。
- **§I 未來自主深度訪談（現在不做、架構預留）**：員工可選「深度訪談模式」→ AI 多輪對話→直接產出完整文件。設計約束：`/ai/*` 寫成無狀態純函式（顯式輸入→結構化輸出、不綁 UI/觸發者），未來訪談 agent＝獨立編排層疊在函式上、不重寫；document JSONB+PATCH 唯一 of-record。

### D28 實作完成（2026-06-22，subagent-driven TDD）
plan `2026-06-22-llm-agent-plan.md` T0–T12 全做完（T13 真模型 e2e+eval gate＝需 `OPENROUTER_API_KEY` 人工驗收，未進 CI）。後端 134 passed（FakeLlm、免 key）；前端 tsc+eslint 乾淨。commits 5101960→630e538。
- **後端 T0–T7**：T0 catalog 任務 UUID 串接（task-candidates 回 id、build-tasks picked 帶 id、ocs_doc provenance `{ocs_code,task_id,id}`）。T1 AI 基礎（`get_llm` dep＝有 key 才建 OpenRouterLlm；`/ai` router 掛 main+live app；`app/services/ai/` 純函式包）。T2–T6 五端點全寫成**薄 adapter + 純函式**（§I 未來訪談 agent 可重用）：recommend-ks（provenance.id→tasks_by_id→官方 K/S；note+LLM 篩選+理由 source=catalog，否則全 catalog；indexer 掛→空不爆）、draft-op（官方 outputs/activity_examples；note+LLM 個人化 source=ai，否則 catalog；太薄回空）、extract-tasks（task_pool→suggested UUID(grounded)+custom_candidates）、structure-task（描述→{task_name,unit_suggestion}，無 LLM→描述當名）、clarify（一個追問或 null）。T7 `_notes` 工作筆記欄＋`assemble_final` 連同 `_pool/_uid/_tid` 一併剝除。**無 key→catalog-only 全程可用**。
- **前端 T8–T12**：T8 `lib/api` 5 端點 + 型別（AiSource/各 result、`provenance.id?`/`_notes?`/`CandidateTask.id`）。T9 ✨「AI 填寫」面板（每任務一顆）＝核心入口：5W2H 卡（必填做什麼/產出＋選填 CIT＋收合細節）→ draft-op+recommend-ks → 暫存（O/P 可改、K/S 勾選＋來源徽章 目錄/AI＋理由）→ 套用走現有 setOp/setKS+PATCH；全部採用/捨棄；警語；clarify 一輪；`_notes` 隨套用存（`get/setTaskNotes`）。T12 次要任務「帶 catalog」＝同面板 `autoCatalog` 模式（開啟即空 note 自動帶官方、跳 5W2H/clarify）。T11 〔選任務〕面板加 extract-tasks「AI 預勾」（suggested UUID→prov 比對預勾）＋ CIT 補漏（描述→structure-task→加自訂任務，走 build-tasks `task_id=custom:<uuid>` 避 dedup 撞）。T10 `/v3/[id]/intake` 一頁 3 格小訪談→組 job_summary 存 profile→進工作台（status=none 時表格頂端有邀請 banner）；職類推薦/extract 預勾沿用既有 OccupationPicker/TaskCuratePanel。
- **MVP 守則落實**：AI 只提議不寫 DB；catalog 優先、來源+理由透明；`/ai/*` 無狀態純函式（§I 預留）；**不碰 CopilotKit**（聊天 Phase 2）。
- **待辦**：T13 給 key 跑真模型人工 e2e（員工小訪談→盤點→✨深填→次要一鍵→A→80分→顧問精修）＋ eval grounding/schema gate；FE 無自動測試→瀏覽器驗收（4 服務：DB/run_live.py:8001/indexer:8000/frontend:3000）。

### D28 T13 eval-gate ✅（2026-06-23，真模型 DeepSeek V3）
`OPENROUTER_API_KEY` 設於 gitignored `backend/.env`；模型＝使用者選 `deepseek/deepseek-chat`（cheap 三層共用）。smoke `docs/superpowers/_t13_smoke.py`（untracked）建真情境(profile→職類→任務含 provenance UUID)打 5 端點 **12/12 綠**：catalog 優先＋AI 個人化(source=ai)＋grounding(catalog 項有 code)＋source 標記皆如設計。**瀏覽器全流程驗收仍待人工**。

## D29 — indexer profile 端點 + 表頭自動填（2026-06-23，查證 indexer 原始碼後設計）
spec＝`2026-06-23-indexer-profile-endpoint.md`。
- **動機**：選職類後表頭（所屬類別/行業別/工作描述/基準級別/notes/態度）目前要人手打；查證 jd-ocs-indexer 後發現**資料全在 profile chunk payload**（`builder.py:97`），只差乾淨取用端點。`/search` 雖回部分但無 code、`/pairs` 只有 K/S/A+notes。
- **決定**：(1) indexer 加 `GET /profile/{ocs_code}` flat 投影端點（job_title/job_category{code,name}/occupations[]/industries[]（帶 code）/job_description/ocs_level/attitudes/prerequisites/supplements；A+B 合一），純 `scroll(limit=1)` 投影、零新資料。(2) builder `_profile_record` payload 補 `job_category_codes`（normalizer 已抽、payload 漏存）→ 重灌（其餘欄位免重灌）。
- **多選職務（防雷）**：文件含多 OCS＝表頭 `category` 為各 OCS 官方分類**聯集**；做成**多值勾選清單**（職類/職業/行業，含代碼），預設全勾、AI 可預選。聯集**依 code 去重、保序**，取消某 OCS 只移除「僅它帶入」者、不洗他人（D27 duplicate-key 教訓）。
- **職能基準代碼/名稱**＝一組綁定對、**單值**：預設第一順位 `codes[0]`，可從已選 OCS 切換主基準（code+name 同步換）。category 才多值，代碼/名稱不是。
- **實作順序**：I1 indexer 端點+builder 補欄+重灌（TDD）→ V1 v3 `ProfileMeta`+client+`set_occupations`/`_refresh_header` 多 OCS 聯集自動填 → V2 DocHeader category 多選清單+主基準切換 → V3（選配）AI 預選 category。

### D29 I1 ✅（2026-06-23，jd-ocs-indexer `dev`，commit 9bf52ac，50 passed）
`GET /profile/{ocs_code}` flat 投影端點（service.get_profile：profile point 一次 scroll，`_zip_pairs` 容錯 code/name 長度不一、404 when absent）+ `ProfileMetaResponse/CodeName` schema + route。builder `_profile_record` payload 補 `job_category_codes`。**`job_category.code` 需 re-ingest 才生效，其餘欄位對現有資料即時可用**。

### D29 V1 ✅（2026-06-23，jobintel-ai `feat/v3`，commit df99247，141 passed）
採**唯讀候選池**模式避「重選洗掉編輯」雷：`GET /job-profiles/{id}/header-meta` 逐 selected code 呼 `knowledge.profile()`，聚合（`app/services/header_meta.py` 純函式：依 code 去重、code 空退 name、每候選記 `sources` 供「最後一個來源 OCS 移除才下架」、主基準單值預設 codes[0] + `primary_options` 切換清單）回職類/職業/行業/態度/notes 候選 + primary。`ProfileMeta` model + `KnowledgeClient.profile()`（http_client + 兩處 stub）。**文件只由前端 PATCH 寫入，端點永不寫**。per-code 容錯（indexer 掛/缺 code→略過不爆）。⚠️ 教訓：誤用 `git add -A` 把 untracked `docs/superpowers/` 一起 commit，已 `reset --soft`+`restore --staged` 修正後只提交 backend。

### D29 V2 ✅（2026-06-23，jobintel-ai `feat/v3`，commit 1d6d629，tsc+eslint 乾淨）
`HeaderMetaPanel`（〔表頭分類〕按鈕，已選職類才啟用）讀 `/header-meta`：勾選所屬職類別/職業別/行業別（多值聯集）、態度 A、應備資格/補充說明，並單選切換主基準（代碼↔名稱綁定，預設 codes[0]）。候選＝indexer 聯集 ∪ 文件現有列（手動列保留、不被洗），預設全勾（官方事實）。套用走現有 PATCH（`setCategory`/`setPrimaryBasis`/`setNotes`/`setAttitudes`）。be 小補：`primary_options` 帶 `job_category_name`/`job_description`/`ocs_level`，切主基準時綁定欄一起正確帶入（可選帶官方工作描述/級別）。**待**：V3 AI 預選（選配）、re-ingest+重啟 indexer、瀏覽器驗收。

### D29 修正 ✅（2026-06-23，使用者比對原始 JSON 抓到）commits cb17573(indexer)/2210e4e(v3)
**bug**：`category.job_categories` 是**多值** `[{code,name}]`（同 occupations/industries，如 AIoT＝MPM/INM/ISD/SET），但 indexer normalizer 只抓 job_categories 的 **code、丟 name**；而 `job_category`（單數）抓的是 `ocs_name.job_category_name`（常 null＝**另一欄**，標題用單一職類名）。I1/V1 誤把兩者混成單值 `{code: codes[0], name: job_category_name}`。**修**：normalizer 補抓 `job_category_names`（與 code 鎖步去重）；builder payload 存之；`get_profile` 回 `job_categories:[{code,name}]`（多值）+ `job_category_name`（單值）分開；schemas/`ProfileMeta`/`aggregate` 同步。前端本來就把 job_categories 設計成清單→無需改。**re-ingest 因此是必要的**（job_category code+name 整組原本沒存，非「補一格」）。**教訓**：實作前要比對**真實原始 JSON**（`data/jd-json/*.json`）確認欄位基數（多值 vs 單值），別憑欄名臆測。
