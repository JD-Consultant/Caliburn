# 主流 agent 系統:組件命名與回合管線 — 研究 + 對照健檢

研究日期:2026-07-12 · 方法:A 段先用業界通用詞彙查官方 SDK 文件與署名實務文章,完全不帶 B 段自創術語;B 段最後才做。

---

## A 段:主流命名與回合管線

### A-1. 組件命名對照表(概念 × 各家名稱)

| 概念 | Anthropic Claude Agent SDK | OpenAI Agents SDK | Google ADK | LangGraph | Pydantic AI | 通用語 |
|---|---|---|---|---|---|---|
| **對話主體** | *agent* / *subagent*(`query`, `AgentDefinition`) | **Agent**(LLM + instructions + tools) | **LlmAgent**(`Agent`) | node(graph 節點) | **Agent**(泛型於 output type) | agent / assistant |
| **規劃/調度者** | 主 agent 委派 subagent;無獨立 planner 物件 | 用 **handoffs** 或 agent-as-tool 委派;無獨立 planner | **workflow agents**(Sequential/Parallel/Loop)+ **Planner**(ReAct planner 可插拔) | **supervisor** / **orchestrator-worker** 模式 | 主 agent 呼叫 output/tool functions | orchestrator / supervisor / planner |
| **執行/寫入角色** | 內建 tools(Read/**Write**/Edit/Bash)由 agent loop 執行 | tool 執行在 **Runner** 迴圈內 | **Runner** 協調 tool 呼叫;tools/AgentTools | node + tool | **function tools** / **output functions** | tool executor |
| **驗證/守門** | **hooks**(`PreToolUse`/`PostToolUse`…)做確定性檢查+阻擋;**permissions** | **guardrails**(input/output)+ **tripwire**;tool guardrails | **callbacks**(before/after model/tool/agent) | **middleware**(v1.1:retry、content-moderation) | **output validators** + `ModelRetry`;Pydantic schema 驗證 | guardrail / validator / hook |
| **進度/狀態追蹤** | **sessions**(JSONL,可 resume/fork)+ **memory**(CLAUDE.md) | **Sessions**(持久記憶,可 Redis)+ server `conversation_id` | **Session** / **State** / **Events**(事件序)/ **Memory**(跨 session) | **StateGraph** + state object(TypedDict) | `RunContext` / message history | session / state / memory / ledger |
| **評分/守門判官** | (SDK 外)LLM-as-judge 慣例 | (Evals 產品線)judge | (Eval 服務) | (LangSmith 評測) | 用 output validator | grader / judge / evaluator / verifier |
| **兜底機制** | hooks `Stop`/`SessionEnd`;`max` 迴圈上限 | `max_turns` 上限;output guardrail | LoopAgent 終止條件;callback | 條件邊 / recursion limit | retry 預算上限 | max-turns / fallback / retry budget |

要點:各家**沒有統一詞彙**,但收斂在少數 primitive:**agent**(對話主體)、**tool**(執行)、**guardrail/hook/callback/validator**(守門)、**session/state/memory**(狀態)、**judge/verifier**(評分)。OpenAI 官方明言「刻意保持極少抽象、極少 primitive」;Anthropic 也是「同一個 agent loop + tools + context management」。B 段那種**單層 loop** 因此與主流一致,不是異數。

### A-2. 一回合的標準生命週期

各家 turn 收斂成同一骨架(以 OpenAI Runner 最白話,ADK/Claude 同構):

1. **輸入 + input guardrail**(OpenAI:input guardrail 可 *parallel*(預設,低延遲)或 *blocking*(省 token/避免副作用);只在鏈上第一個 agent 跑)。
2. **context 組裝**:載入 session/state 歷史(ADK `SessionService` append events + state;Claude sessions resume;LangGraph state object)。
3. **模型呼叫**:Runner/agent loop 呼叫當前 agent 的 LLM。
4. **輸出判定三岔**:最終答案(結束)/ tool 呼叫(執行)/ handoff(換 agent)。
5. **tool 執行**(可暫停等 human approval)。
6. **output guardrail**(OpenAI:一律 *blocking*,只在最後一個 agent 跑;tripwire 觸發即 raise)。
7. **狀態/session 更新**:新訊息落 session/state(ADK 用 `EventActions.state_delta` 增量更新 State;LangGraph reducer 合併 state)。
8. 迴圈直到最終輸出或 `max_turns`。

**「對話角色 vs 寫入角色分離」有沒有官方先例?** 有,但多是**框架模式**而非單一 SDK 的內建 primitive:

- **AG-UI 協定**(Agent-User Interaction)明確把「LLM 看得到的 `result` 欄位」與「送給 UI 的 state 事件(`StateDelta`,JSON-Patch)」分成**兩條通道**——`_handle_function_result_content()` 檢查 `state_delta`/`state_snapshot` 鍵後發 UI 事件,LLM 只看到 result。這正是「一個通道說話、另一個通道結構化寫入」。
- **多 agent assembly-line / extraction 模式**:summarizer/assessor/**verifier** 角色分工;生產級做法是維護一個**結構化 profile 物件**(current goals / entities / recent tool outputs),而非原始訊息記錄——對話由對話 agent 產、結構由 extraction agent 抽。
- **不同模型配不同角色**是明列的好處:planner 用結構化模板、writer 用創意措辭、fact-checker 用嚴格邏輯——「便宜模型專責結構化寫入、強模型專責對話」屬同一光譜。

### A-3. UI 事件(按鈕點擊等非文字輸入)如何進 agent

主流答案:**event log + state injection**,不是塞成自由文字。

- **AG-UI 協定**是這條線目前最成型的標準:agent/tool/UI 之間是**事件驅動契約**。使用者在 agent 渲染的 calendar/確認表單上的互動,以**結構化 response** 回流,而非要 agent 重新 parse 的 free text。狀態變動用 `StateDelta`(JSON-Patch)增量注入。支援 **interrupt**:agent 暫停請求輸入,前端渲染控件,回應走事件通道。
- **Google ADK**:**Events** 是 session 內「訊息與動作」的時間序記錄,**非 LLM 動作**一樣 append 進 event log,由 `SessionService` 統一 append events + 改 state。
- **Claude / 終端 coding agent 實務**(arXiv 2603.05344):多入口(CLI/TUI/WebSocket)匯流到同一 agent 核心;lifecycle 事件明列 `SessionStart`/`UserPromptSubmit`/`PreToolUse`/`PostToolUse`/`SubagentStop`/`Stop` 等;**thread-safe injection queue** 讓使用者中途插話,在**迭代邊界**排空。

共識:非對話動作 = **一等公民事件**,寫進 event log / 用 state-delta 注入,在迴圈邊界被消費;不偽裝成使用者說的話。

### A-4. 2026 新出現的管線模式

- **Plan-then-Execute(含安全論證)**:先產完整計畫再吃外部不可信資料,把控制流「鎖死」在暴露於 prompt injection 之前(arXiv 2605.14290、2509.08646)。回報 92% 完成率、3.6× 加速。
- **Write-ahead / 驗收準則先行(Agent Levers, PDCA loop, 2026-05)**:plan 階段先寫**一組 acceptance criteria**,每條配一個 **typed verifier**(shell 指令 / 截圖 / 人工 rubric)並設**迭代預算**;鐵律是「verifier 測**行為**,不是測 agent 過去的動作」。
- **分層/成本感知驗證(cost-aware eval, 2026)**:**確定性檢查(schema、tool-call 格式)對 100% 輸出跑、成本近零、先攔最常見幻覺**;必要時才上便宜的 fine-tuned judge(如 Galileo Luna, <200ms)。是「先確定性、後 LLM」的明確主流化。
- **LLM-as-verifier vs LLM-as-judge**:judge 在**完整輸出後**評分;**verifier 檢查每一中間步是否有證據支撐、在錯誤擴散前給回饋**(SAFE 框架,evidence-grounded)。
- **多角色判官**(CourtEval, 2025):**Grader(判)/ Critic(檢方)/ Defender(辯方)**,Grader 聽兩造後改分。
- **Middleware 標準化**(LangGraph v1.1, 2025-12):retry(指數退避)、content-moderation 成為可插拔 middleware。

---

## B 段:對照健檢

被檢架構(繁中職務說明書訪談引擎):**consultant**(對話,強模型,唯讀工具,決定回話+標記本回合有無素材)→ **scribe**(便宜模型+strict schema,按需喚醒,把素材轉寫入 op)→ **verify**(寫入前純程式六查,退回重試×2 後丟棄)→ **ledger**(確定性覆蓋帳本,追欄位收齊、放行、含拒絕事件)→ **backstop**(每 N 回合確定性掃逐字稿撿漏)。寫入落 pending,使用者 accept/reject 為無聲 UI 事件記入 ledger。狀態全在 DB(無狀態回合),context 分層快取,skill 檔按欄位確定性載入。

### B-1. 與主流形態的偏差(缺件/多件/順序)

**大體同構,無重大偏差。** 逐項對:

- consultant→scribe→verify→ledger 正好落在 A-2 標準骨架的 **模型 → 工具/輸出 → output guardrail → 狀態更新**。順序正確。
- **speak/write 分離**有官方先例(AG-UI 雙通道、extraction-agent 模式、不同模型配不同角色),**不是異類設計**。用便宜模型+strict schema 專責寫入 = A-4「確定性/結構化通道」+ Pydantic「structured output 用 schema 驗證」的正解。
- **verify 純程式六查** = A-4「成本感知驗證」的教科書執行:確定性檢查對 100% 輸出跑、近零成本、先攔幻覺。刻意**不放 LLM 進 verify**,與主流「先確定性後 judge」完全一致——是優點不是缺點。其中「出處存在性 / 來源一致」= LLM-as-verifier 的 **grounding/faithfulness** 檢查(SAFE),很到位。
- **accept/reject 無聲 UI 事件記入 ledger** = A-3 的 event-log / state-injection 主流做法(AG-UI、ADK Events)。正確,別改成塞文字。
- **無狀態回合 + 狀態全在 DB** = OpenAI Sessions / ADK SessionService「狀態外置、逐回合重建 context」的主流姿態。

**可議的小缺件(非硬傷):**

1. **缺 input 側 guardrail**:目前只有**寫入前** verify,沒有**輸入前**的確定性檢查。OpenAI 明確把 guardrail 分 input/output 兩端;若使用者輸入會被 scribe 當素材寫入,考慮補一道輕量 input guardrail(或明確記錄「刻意不做,因唯讀 consultant 不執行副作用」)。屬**可選優化**,非缺陷。
2. **retry×2 是否回饋錯誤**:Pydantic AI 的 `ModelRetry` 精神是**把驗證錯誤訊息回灌給模型**再試,不是盲重試。確認 scribe 的重試有把 verify 的具體失敗原因喂回去(faithfulness/schema 哪條掛了),否則兩次重試價值打折。
3. **planner 缺席是刻意且合規**:主流也不強制獨立 planner(OpenAI/Claude 都靠單 loop + 委派);與本 repo ADR 0008「刻意單層 loop」一致,無需補。

### B-2. 命名對映與改名建議

| 本架構名 | 業界慣用對映 | 建議 |
|---|---|---|
| **consultant** | conversational **agent** / assistant / (ADK)LlmAgent;唯讀=read-only/analyst agent | **保留**。領域語義精確(顧問訪談),對維護者比泛稱「agent」更達意。可在文檔一句話標註「= 主對話 agent」降低新進者成本。 |
| **scribe** | **structured-output / extraction / writer agent**;「便宜模型+strict schema」= structured output pipeline | **保留可,但要掛鉤**。scribe 很傳神,但新進者不會直接聯想到「extraction/structured-writer」。文檔標註「scribe = structured-write channel(extraction agent)」。 |
| **verify** | **guardrail**(OpenAI output guardrail)/ **validator**(Pydantic)/ **verifier step**(2026);純程式=deterministic check | **建議靠攏主流**:內部可稱其為 **output guardrail / verifier**。「六查退回重試×2」= tripwire + retry budget + `ModelRetry`。名字 `verify` 已夠標準,只需在文檔點名它就是 output guardrail,並用「tripwire」描述觸發。 |
| **ledger** | **state / session state**;**且有直接先例**:Microsoft **Magentic-One 的 Task Ledger / Progress Ledger** | **保留,名字選得好**。「ledger」在大廠多 agent 文獻(Magentic-One)就是確定性進度帳本的正式用語,對映精準,勝過泛稱「state」。 |
| **backstop** | **reconciliation sweep / safety-net / fallback**;定期掃逐字稿撿漏 | **保留但加註**。backstop 是清楚的英文比喻但非固定術語;文檔標「= periodic deterministic reconciliation sweep / safety net」。若要更主流可考慮 `reconciler` 或 `sweep`。 |
| **pending(待審寫入)** | human-in-the-loop **approval** / pending state;AG-UI interrupt | **保留**,與 OpenAI「tool 執行前暫停等 approval」、AG-UI interrupt 同構。 |

原則:**consultant / scribe / ledger** 領域語義強、且 ledger 有大廠先例 → **保留更精確**;**verify / backstop** 是通用機制 → 名字不必改,但**文檔要明點對映**(output guardrail / verifier、reconciliation sweep),把新進者的理解成本降在文檔而非改碼。

### B-3. 值得抄的優化(A 段看到、此架構可採)

1. **重試回灌錯誤(Pydantic `ModelRetry`)**:scribe retry×2 時,把 verify 六查的**具體失敗條目**當回饋喂回,而非盲試。低成本、直接提高第二次成功率。
2. **write-ahead / 驗收準則先行(Agent Levers)**:讓 ledger 的「欄位收齊判定」升級成**每欄位一條 typed verifier**(本架構已有 skill 檔按欄位確定性載入——正好掛驗收準則),使「放行」是對**行為/證據**的檢查而非對「scribe 說寫了」的信任。
3. **雙帳本拆分(Magentic-One Task vs Progress Ledger)**:目前 ledger 同時管「該收哪些欄位(計畫)」與「收齊沒(進度)」。Magentic-One 把 **Task Ledger(要什麼)** 與 **Progress Ledger(進度/是否卡住)** 分開,利於 backstop 判斷「卡住了嗎、要不要換策略」。可選。
4. **input guardrail 端(OpenAI 雙端 guardrail)**:如 B-1(1),補一道輸入側確定性檢查或明確記錄不做的理由。
5. **採 AG-UI 事件詞彙**描述 accept/reject/pending 這條 UI-事件線(`StateDelta`/interrupt/JSON-Patch),讓「無聲 UI 事件記入 ledger」對接一個**既有標準協定**的命名,降低跨系統溝通成本。純命名/文檔層,不必改架構。
6. **guardrail 執行模式(blocking vs parallel)**:verify 目前是寫入前 blocking(正確,因有副作用)。可借 OpenAI 的框架語言在文檔說明「verify 必須 blocking(有寫入副作用),不可 parallel」,把設計理由固化。
7. **backstop 保持確定性、抗拒 LLM 化**:主流「先確定性、近零成本」明確支持現狀;若未來要加 LLM,走 **verifier(逐步、證據支撐)** 而非 **judge(事後整體評分)**,並只在確定性掃描漏接時才升級——維持成本感知分層。

---

## 來源(標日期,優先 2025H2–2026)

**Anthropic**
- Agent SDK overview(agent loop / hooks 生命週期 / subagents / sessions / skills)— code.claude.com/docs/en/agent-sdk/overview(2025–2026)
- Building agents with the Claude Agent SDK — anthropic.com/engineering/building-agents-with-the-claude-agent-sdk(2025)

**OpenAI**
- Running agents(Runner / turn lifecycle / sessions)— openai.github.io/openai-agents-python/running_agents/(2025–2026)
- Guardrails(input/output guardrail、tripwire、blocking vs parallel)— openai.github.io/openai-agents-python/guardrails/
- Handoffs / Agents — openai.github.io/openai-agents-python/handoffs/、/agents/

**Google ADK**
- Agents(LlmAgent / workflow agents / Planner)— google.github.io/adk-docs/agents/、/agents/workflow-agents/
- Sessions/State/Events/Memory — adk.dev/sessions/
- Developer's guide to multi-agent patterns in ADK — developers.googleblog.com(2025)

**LangChain / LangGraph**
- Plan-and-Execute Agents — langchain.com/blog/planning-agents
- LangGraph 架構 / supervisor / StateGraph / v1.1 middleware(2025-12)— latenode.com 架構指南(2025)

**Pydantic AI**
- Output / output validators / `ModelRetry` / structured output — pydantic.dev/docs/ai/core-concepts/output/、/api/pydantic-ai/output/

**協定 / 模式 / 署名實務**
- AG-UI Protocol(events / StateDelta / state injection / interrupt)— docs.ag-ui.com/concepts/events;Microsoft agent-framework AG-UI state management — learn.microsoft.com(2025–2026)
- Agent Levers: PDCA / write-ahead / typed verifier — fmind.medium.com(2026-05)
- Web Agents Should Adopt Plan-Then-Execute — arXiv 2605.14290;Secure Plan-then-Execute — arXiv 2509.08646
- LLM-as-Judge 實務指南(2026)— sureprompts.com;Agent Evaluation(trajectory / LLM-as-judge)— medium/@vinodkrane(2026-05)
- CourtEval(Grader/Critic/Defender)、SAFE(LLM-as-verifier, evidence-grounded)— arXiv 2508.02994 / 2604.01993
- Building AI Coding Agents for the Terminal(lifecycle events / injection queue)— arXiv 2603.05344
- Magentic-One Task Ledger / Progress Ledger(ledger 先例)— Microsoft Research(2024–2025)
