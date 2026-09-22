# 2025–2026 官方 AI 應用參考架構研究紀錄

> 研究員紀錄。純學習,不綁專案。只收模型廠 / 雲廠 / 原廠框架**官方**來源(工程部落格、官方 docs、架構中心);
> 拒絕內容農場、無署名轉述、顧問行銷白皮書。每條標 URL + 日期。優先 2025 下半–2026。
> 撰寫日期:2026-07-12。

---

## 摘要(先讀這段)

2025–2026 官方藍圖已高度收斂。**共同分層**大致是:UI/對話層 → orchestration(agent runtime / 編排)→ 工具層(含 MCP)→ 知識/檢索層(grounding)→ 守門層(guardrails / content safety)→ 觀測層(tracing / evals)。差異在「編排」怎麼做:Anthropic 主張**單一 agent loop + 內建 harness + subagent**,盡量少框架;OpenAI Agents SDK 把 **Agents / Handoffs / Guardrails / Sessions / Tools / Tracing** 做成六個原語;Google ADK 明分 **workflow agents(Sequential/Parallel/Loop)vs LLM-driven agents**,走 hub-and-spoke 多 agent;雲廠(AWS GenAI Lens、Azure Foundry 基線)把它包成**六邊形 / orchestrator-in-the-middle** 的企業級部署藍圖。

七個問題的一句話結論:
1. **分層**已成共識,差別在編排哲學(單 loop vs 多原語 vs graph)。
2. **Agent SDK 假設**:Anthropic = 「把 Claude Code 的 harness 當 library」,agent 直接操作你的檔案/程序;OpenAI = 「runtime 幫你管 turn/tool/handoff/guardrail/session」,原語少而可組合。
3. **chat + 持久工作品**:官方(Canvas / Artifacts / Foundry conversation object)做法是**把對話與工作品分成兩個 state**,工作品是可定址的持久物件,模型透過工具做**定點編輯 / 整篇重寫**。
4. **檢索**:2026 官方定位是 **agentic retrieval / just-in-time**(檢索=工具呼叫),但**混合**(預先 metadata + 執行時探索)是主流建議,「do the simplest thing that works」。
5. **守門/評測**:guardrails 官方建議做成**獨立的分層防禦**(deterministic + LLM-based + moderation,平行執行、fail-fast);tracing **預設開、貫穿全程**,是獨立橫切層。
6. **框架 vs 自建**:所有官方都誠實說「先用 API 直接寫最簡方案,搞不定再上框架;用框架必須讀懂底層」。
7. **多租戶**:官方(AWS 八情境含 multi-tenant、Azure secure multitenant RAG)共識是**用 API/gatekeeper 層封裝租戶資料存取 + security trimming**,store-per-tenant vs 共用 store 依租戶數與資料量選,身分需一路流穿到檢索時強制過濾。

---

## Q1 — 標準分層:官方參考架構把 AI 應用切成哪幾層?

**結論**:2025–2026 官方藍圖收斂到一套「洋蔥式」分層,各家名字不同但對得上。以 Azure「Baseline Foundry Chat」最完整地示範了企業級全棧分層:

| 層 | Azure Foundry 基線 | AWS GenAI Lens | Anthropic 觀點 | OpenAI 觀點 |
|---|---|---|---|---|
| UI / 對話層 | Chat UI on App Service(前面掛 App Gateway + WAF) | 應用前端 | 「agent 介面」 | Chat / client |
| Orchestration / 編排 | Foundry Agent Service(持久 prompt agent) | agent workflow / orchestration | agent loop(harness) | Agent runtime(管 turn) |
| 工具層 | tool catalog + MCP + A2A | tool use | 內建工具 + MCP | Tools（function/MCP）|
| 知識 / 檢索層 | AI Search(grounding) | vector store / RAG | JIT retrieval as tool | Retrieval tool / File search |
| 守門層 | content safety(內建 agent service) | 「mitigate harmful outputs & excessive agency」 | permissions / hooks | Guardrails(平行) |
| 狀態 / 記憶層 | Cosmos DB conversation object + Blob 檔案 | session / artifact 版本化 | sessions + memory(檔案) | Sessions |
| 觀測 / 評測層 | App Insights + Azure Monitor | operational excellence / observability | tracing | Tracing(預設開) |
| 網路 / 隔離層 | VNet + Private Link + Firewall(egress) | security pillar | — | — |

**關鍵證據**:
- Azure 明列企業 chat 四大件:「A chat UI… Data repositories… Language models that reason… A persisted orchestration definition or long-lived agent that oversees the interactions」。編排層(Foundry Agent Service)負責 “Process user requests / Orchestrate calls to tools and other agents / Enforce content safety / Integrate with enterprise identity, networking, and observability”。
  來源:Azure Architecture Center, *Baseline Microsoft Foundry Chat Reference Architecture*,ms.date **2026-06-17**。<https://learn.microsoft.com/en-us/azure/architecture/ai-ml/architecture/baseline-microsoft-foundry-chat>
- AWS GenAI Lens 用 Well-Architected 六支柱(Operational excellence / Security / Reliability / Performance / Cost / Sustainability)橫切,並貫穿生命週期六階段(scoping → model selection → customization → development → deployment → continuous improvement),提供 **8 個架構情境**(含 autonomous call center、knowledge-worker co-pilot、**multi-tenant generative AI service**)。
  來源:AWS Well-Architected *Generative AI Lens*,發布 **2025-11-19**。<https://docs.aws.amazon.com/wellarchitected/latest/generative-ai-lens/generative-ai-lens.html>

**異同**:雲廠(AWS/Azure)分層最厚(多了網路隔離、可靠性、部署 stamp),因為要落地到自家服務;模型廠(Anthropic/OpenAI)分層薄,聚焦「agent runtime + 工具 + 觀測」。**共同不變量**:編排層在正中,工具與知識掛它旁邊,守門與觀測是橫切層。

**啟示(給 Caliburn)**:你的 api = 六邊形(core / adapters / services / authoring)本質上就是這套分層的一個實例——`authoring`(LangGraph 單層 loop)= 編排層、`adapters`(DB/LLM/knowledge)= 工具+知識層、embedder/indexer = 檢索層。官方藍圖佐證了「編排單層、邊緣做 adapter」的切法。

---

## Q2 — Agent 執行環境:Anthropic Agent SDK vs OpenAI Agents SDK 的架構假設與邊界

### Anthropic Claude Agent SDK

**核心假設**:「把 Claude Code 的 harness 當 library 用」。官方原文:「The Agent SDK gives you the same tools, agent loop, and context management that power Claude Code, programmable in Python and TypeScript.」agent **直接在你的行程 / 基礎設施上操作你的檔案與服務**。

架構元件(官方 docs 列出的能力面):
- **Built-in tools**:Read / Write / Edit / Bash / Glob / Grep / WebSearch / WebFetch / Monitor / AskUserQuestion —— 「so your agent can start working immediately without you implementing tool execution」。
- **Subagents**:`AgentDefinition`(description + prompt + tools),經 `Agent` 工具生成;子 agent **自帶隔離 context**,只回傳精煉結果(用於平行化 + context 管理)。訊息帶 `parent_tool_use_id` 可追蹤歸屬。
- **Sessions**:JSONL 存在你的檔案系統;可 resume、可 fork 探索不同路線。
- **Hooks**:`PreToolUse` / `PostToolUse` / `Stop` / `SessionStart/End` / `UserPromptSubmit`……做 validate / log / block / transform。
- **Permissions**:`allowed_tools` 白名單、`permission_mode`(如 `acceptEdits`)。
- **MCP**:第一級 client,接資料庫/瀏覽器/API。
- **檔案化設定**:載入 `.claude/`(skills / commands / CLAUDE.md / plugins)。

**適用邊界**(官方自陳的三段對比):
- vs **Client SDK**:Client SDK 你自己寫 tool loop;Agent SDK 由 Claude 自主跑 loop。
- vs **Claude Code CLI**:同能力不同介面。CLI 用於互動開發/一次性;SDK 用於 CI/CD、自訂應用、生產自動化。
- vs **Managed Agents**:SDK 跑在**你的行程/基礎設施**(state = 你檔案系統上的 JSONL);Managed Agents 是 Anthropic 託管的 REST(每 session 一個 managed sandbox、Anthropic-hosted event log),適合「不想自己營運 sandbox / session 基礎設施」「長時間、非同步」的生產 agent。官方建議路徑:**先用 SDK 本地雛型,再搬 Managed Agents 上生產**。

來源:*Agent SDK overview*, Claude Code Docs(2025,持續更新)。<https://code.claude.com/docs/en/agent-sdk/overview>
背景:*Building agents with the Claude Agent SDK*, claude.com blog;*Effective harnesses for long-running agents*, anthropic.com/engineering。

### OpenAI Agents SDK

**核心假設**:「runtime 幫你管 turn / tool execution / handoff / guardrail / session,原語少而可組合」。設計原則兩句(官方原文):「*Enough features to be worth using, but few enough primitives to make it quick to learn*」與「*Works great out of the box, but you can customize exactly what happens.*」2025-03-11 發布,是 Swarm 的生產級後繼。

六個原語:
- **Agents**:LLM + instructions + tools(+ 可選 handoffs / guardrails / structured output)。
- **Handoffs**:把 peer agent 當工具,委派控制權給專才 agent —— 不用手動接 state/控制流。
- **Guardrails**:輸入/輸出驗證與安全檢查**與 agent 執行平行跑,fail-fast**。
- **Sessions**:agent loop 內維持工作 context 的持久記憶層。
- **Tools**:Python function 或 MCP server 轉成可呼叫介面。
- **Tracing**:**預設開**,收 LLM generation / tool call / handoff / guardrail / 自訂事件;整合 20+ 第三方(Langfuse / LangSmith / Arize / MLflow / W&B…)。

**適用邊界**(官方):用 Agents SDK 當「you want the runtime to manage turns, tool execution, guardrails, handoffs, or sessions」、需要 artifacts / 多步 / 隔離工作區(Sandbox agents);**直接用 Responses API** 當「你想自己掌控 loop 與 state」「工作流短命、主要就是回一個 model response」。

來源:*OpenAI Agents SDK* 官方 docs。<https://openai.github.io/openai-agents-python/> ;tracing 章 <https://openai.github.io/openai-agents-python/tracing/>

### 兩者對照(架構哲學差異)

| 面向 | Anthropic Agent SDK | OpenAI Agents SDK |
|---|---|---|
| 多 agent 模型 | **subagent**(母派子、子隔離 context 回精煉結果) | **handoff**(平行 agent 交棒控制權) |
| 執行位置 | 你的行程/基礎設施(檔案上 JSONL) | 你的行程,或搭 hosted runtime |
| 守門 | hooks + permissions(生命週期切點) | guardrails(平行、fail-fast) |
| 工具起點 | **重內建工具**(檔案/bash 開箱即用) | 工具需你定義(function/MCP) |
| 核心賣點 | 「Claude Code 的 harness 給你」 | 「少原語、runtime 代管 turn」 |

**啟示**:Caliburn 的 `authoring` 是 LangGraph 單層 loop(ADR 0008,刻意不重構)。若未來要引入 subagent 式分工,Anthropic 的「子 agent 自帶隔離 context、只回精煉摘要」是最貼近你單層哲學的模型;OpenAI 的 handoff 較適合「多專才交棒」的客服型流程。

---

## Q3 — 對話 + 持久工作品(文件 / canvas / 程式碼)的雙載體參考做法

**結論**:官方沒有把它叫「參考架構」,但三個官方實作(OpenAI Canvas、Anthropic Artifacts/Claude Code、Azure Foundry conversation object)透露出一致的**雙 state 藍圖**:對話 state 與工作品 state 分開存,工作品是**可定址的持久物件**,模型透過工具對它做**定點編輯 vs 整篇重寫**兩種動作,誰能寫由權限/工具界定。

**關鍵證據**:
- **OpenAI Canvas**:UI 一分為二——左邊 chat 保留高階指令,右邊 canvas 是「fully editable workspace」。官方訓練模型「knows when to open a canvas, make targeted edits, and fully rewrite」——即**定點編輯 vs 整篇重寫**是模型的核心行為,不是 UI 糖。後續擴充加了 live cursors / inline comments / **version history** / 指派 section。
  來源:*Introducing canvas*, OpenAI,2024-10;2026 擴充。<https://openai.com/index/introducing-canvas/>
- **Azure Foundry conversation object**:回應前把「the request, the generated response, and tool invocation details」持久化到 **Cosmos DB 的 conversation object**(messages / tool calls / tool outputs 為 conversation items),**上傳檔案另存 Blob + 切塊進 AI Search**。即「對話歷史」與「工作檔案」是**兩個分開的持久存儲**,且 Foundry API 支援「multiple concurrent, context-isolated conversations」。也提供 **client-managed history** 變體(零資料保留/自訂 context window/多通道獨立 session 時用)。
  來源:同 Azure Foundry 基線(2026-06-17)。
- **Anthropic 的等價機制**:工作品即**外部檔案/notes**,agent 用 note-taking / memory 維持跨步狀態(見 Q4),Claude Code 直接把「檔案系統」當持久工作區,session state = JSONL。這使「持久工作品」不必進 context,而是可定址、按需載入。

**共通不變量**:
1. **雙 state 分離**:volatile 的對話 vs durable 的工作品,各自持久化。
2. **工作品可定址**:有 id / 檔案路徑 / 版本,模型用工具存取,不整包塞進 context。
3. **寫入受控**:模型的寫是「工具動作」(targeted edit / rewrite),受 permission / hook / guardrail 把關;人也能寫(協作編輯)。

**啟示(高度相關 Caliburn)**:你正是「chat + 持久職務說明書」的雙載體應用。官方藍圖佐證:(a) 把 OCS/JD 文件當**可定址持久物件**(你已有 ocs-contract),對話歷史另存;(b) 模型對文件的每次改動應是**受權限把關的工具動作**(定點編輯優先於整篇重寫,利於 diff/審計);(c) 多租戶下每個 conversation 要 context-isolated。

---

## Q4 — 檢索 / 知識層:2026 官方對 RAG 的最新定位,放在架構哪裡

**結論**:官方定位已從「一次性 RAG pipeline」轉向 **agentic retrieval / just-in-time**——**檢索 = 一次工具呼叫**,是 agent 推理迴圈的一部分,而非前置的獨立管線。但官方**不主張全盤丟棄 RAG**,而是**混合**:預先算好 metadata/索引 + 執行時由 agent 動態探索。

**關鍵證據**:
- Anthropic:「Rather than pre-processing all relevant data up front, agents built with the 'just in time' approach maintain lightweight identifiers (file paths, stored queries, web links) and use these references to dynamically load data into context at runtime using tools.」但明說 tradeoff(執行時探索比預算檢索慢),建議「**do the simplest thing that works**」,並以 Claude Code 為範本:**預存 metadata(CLAUDE.md)+ 用 grep/glob 自主探索**。檢索被收進「寫/壓縮/隔離 context」的迭代迴圈,而非一次性。
  來源:*Effective context engineering for AI agents*, Anthropic,**2025-09-29**。<https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>
- 佐證業界訊號(仍屬 Anthropic 官方行為):2025-05 Anthropic 在 Claude Code 中**移除向量檢索**,用 grep 取代 embedding pipeline + 本地向量庫 + chunking —— 「agent-as-retriever」把檢索與工具收斂成一次 tool call。(來源為二手轉述,僅作趨勢佐證,不作主張依據。)
- Azure 立場更保守/務實:RAG 仍是預設 grounding 模式,「a client application calls to an orchestration layer that fetches relevant information from a data store… passes that data as grounding data to the foundation model」;且明說「**Vector search is typical for RAG but not always required**」,可用 Cosmos/SQL 等既有資料庫。Foundry 亦推 **Foundry IQ** 做代管 grounding。
  來源:Azure *Secure Multitenant RAG*(2025-10-03,更新 2026-07-02)+ Foundry 基線。<https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/secure-multitenant-rag>

**放在架構哪裡**:
- **模型廠觀點**:檢索層「塌陷」進工具層——沒有獨立 retrieval 服務,retrieval 就是一個 tool(grep / query / MCP)。
- **雲廠觀點**:檢索仍是**獨立的 grounding 層**(AI Search / vector store),掛在 orchestration 旁,但越來越常被包成「agent 的一個 tool」(Foundry 的 AI Search tool / File Search tool)。

**兩者其實同構**:差別只在「檢索工具背後是不是一個重量級索引服務」。2026 共識:**檢索是工具呼叫;要不要預建索引,看語料規模與延遲需求**。

**啟示(高度相關)**:Caliburn 已把嵌入放進 GPU 容器 embedder + indexer(Qdrant),api 走 HTTP 呼叫——這正是「把檢索包成一個工具/服務、不塞進 app 進程」的官方對應做法。JIT 的啟示:考慮讓 authoring loop 把「檢索」當**一次可觀測的工具呼叫**(而非前置一律塞 context),對長文件著作能省 token、利於精準。

---

## Q5 — 守門與評測層的架構位置

**結論**:官方一致把 **guardrails 做成獨立的「分層防禦」**(不是塞進單一 prompt),多道特化防護平行疊加;**tracing/observability 是預設開、貫穿全程的橫切層**;**evals** 官方定位為生命週期中持續進行的獨立實踐(離線評測 + 線上監控)。

**Guardrails = 分層防禦**:
- OpenAI:「a single guardrail is unlikely to provide sufficient protection; using multiple, specialized guardrails together creates more resilient agents」。組合:deterministic(blocklist / 長度限制 / regex 擋 SQL injection)+ LLM-based + **Moderation API**;對工具做 **risk rating**(read-only vs write),高風險前**升級給人**(human-in-the-loop)。
  來源:*A practical guide to building agents*, OpenAI(2025)。<https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf> ;<https://platform.openai.com/docs/guides/agent-builder-safety>
- OpenAI Agents SDK:guardrails **與 agent 執行平行跑、fail-fast**(架構上是獨立、可搶先中止的並行檢查,不是串在 prompt 裡)。
- Anthropic:對等機制是 **hooks + permissions**——`PreToolUse` 可 block、`allowed_tools` 白名單、對高風險動作要人批准。守門是生命週期切點上的獨立回呼,而非 prompt 內文。
- Azure:content safety **內建在 Agent Service** 這個編排層,並在**網路層**用 Firewall 強制 egress 規則(擋 data exfiltration)。安全被拆成「內容守門 + 網路守門」兩道獨立層。

**Tracing / Observability = 橫切層,預設開**:
- OpenAI Agents SDK:tracing **enabled by default**,收 LLM generation / tool call / handoff / guardrail / 自訂事件,整合 20+ 觀測平台。
- Anthropic:SDK 有 tracing / hooks(`PostToolUse` 記 audit log);生產指南談 tracing + evaluation。
- Azure:App Insights + Azure Monitor 為觀測層;AWS GenAI Lens 把「implement observability」列為 Reliability 支柱要求。

**Evals**:官方(AWS GenAI Lens Operational Excellence:「achieve consistent model output quality」;Azure 有專門 *RAG solution design and evaluation guide*)都把評測當**貫穿生命週期的獨立實踐**——離線 golden/評測集 + 線上追蹤指標,而非一次性驗收。

**啟示(高度相關 Caliburn)**:你的工作紀律已強調「golden 當 characterization net、green-before==green-after」——這正是 evals-as-safety-net 的官方精神。架構上建議把 guardrails 做成**獨立層**(不要縫進 authoring prompt):輸入守門(平行)+ 工具風險分級(對「寫 JD 文件」這種 write 動作要更嚴)+ tracing 預設開,對多租戶的稽核與成本歸因都關鍵。

---

## Q6 — 框架 vs 自建:官方誠實的適用邊界

**結論**:罕見地,**所有官方立場一致**——先用 LLM API 直接寫最簡方案,只在必要時加複雜度;用框架必須讀懂底層,進生產時敢於拆掉抽象。

**關鍵證據**:
- **Anthropic**(最強硬):「find the simplest solution possible, and only increasing complexity when needed」;「The most successful implementations weren't using complex frameworks… building with simple, composable patterns」;「if you do use a framework, ensure you understand the underlying code. Incorrect assumptions about what's under the hood are a common source of customer error.」三原則:**simplicity / transparency / 精心設計 agent-computer interface (ACI)**。並區分 **workflows**(LLM+工具走預定 code path)vs **agents**(LLM 自主導引流程)。五個 workflow pattern:**prompt chaining / routing / parallelization / orchestrator-workers / evaluator-optimizer**。
  來源:*Building Effective AI Agents*, Anthropic,**2024-12-19**。<https://www.anthropic.com/engineering/building-effective-agents>
- **OpenAI**:先問「該不該建 agent」——「Agents are uniquely suited to workflows where traditional deterministic and rule-based approaches fall short… otherwise, a deterministic solution may suffice.」Agents SDK 賣點也是「few enough primitives」。用 Responses API 直寫,當你想自己掌 loop。
  來源:*A practical guide to building agents*(2025)。
- **LangChain / LangGraph**(框架廠自己也劃界):LangGraph 是「low-level orchestration framework and runtime for long-running, stateful agents」;官方說「若你剛入門或想要高階抽象,建議用 LangChain 的 prebuilt agents」,LangGraph 是給「複雜、公司特有、需精細 state 管理」的任務。LangGraph 1.0 於 **2025-10** 釋出。
  來源:*How to think about agent frameworks*, LangChain blog;LangGraph overview docs。<https://www.langchain.com/blog/how-to-think-about-agent-frameworks>
- **Azure**:基線用 codeless 的 Foundry Agent Service;但列出「何時該自建 orchestration(hosted agents)」的清單:需非受支援模型/工具、需 deterministic 精細控制、需程式碼稽核認證、需自訂記憶——「Self-hosted orchestration increases operational complexity」。

**共同判準**:任務是否**確定性規則就能解**→ 能就別上 agent;需要的是**可預測性**(workflow)還是**彈性/模型自主**(agent)。框架是加速起步的鷹架,不是終點。

**啟示**:Caliburn 選 LangGraph 做 authoring 且**刻意保持單層 loop**(ADR 0008),完全符合官方「理解底層、抗過度抽象」的告誡。你的記憶「Avoid overengineering」與此同源。若某段著作流程其實是**確定性**的(如格式 renumber),官方會建議它走 workflow/純 code,而非 agent。

---

## Q7 — 多租戶 SaaS 的官方架構建議(資料隔離 / per-tenant 知識 / 成本控制)

**結論**:官方對多租戶 AI 有明確藍圖。核心:**用 API/gatekeeper 層封裝所有租戶資料存取,在檢索時強制 security trimming**;隔離模型在 **store-per-tenant vs 共用 store(帶 tenant discriminator)** 間依租戶數/資料量權衡;身分要**一路流穿**到資料層。

**關鍵證據(Azure Secure Multitenant RAG,最直接)**:
- **鐵律——gatekeeper API**:「We recommend that you have an API in front of the storage mechanism… acts like a gatekeeper… Code that needs to access tenant data shouldn't be able to query the back-end stores directly. All requests for data should flow through the API layer.」該層負責:路由到 tenant-specific store、在共用 store 只選該租戶資料、用使用者身分做平台授權、執行 custom security trimming、**記存取 log 供稽核**。
- **隔離模型選擇**:
  - *Store-per-tenant*:資料+效能隔離、成本歸因單純;但管理開銷大、可能撞服務上限;**大量小租戶(B2C)不適用**。
  - *Multitenant store*(共用):成本優化、可承載更多租戶;但**資料隔離是最大顧慮**,查詢**必須帶 tenant discriminator**(如 partition key / row-level security)。
  - *Shared store*:全租戶共用的通用知識,不需過濾。
  - 可混用三者。
- **身分**:需 identity provider + identity directory,身分「flow through the request chain」讓下游 orchestrator/資料層識別使用者;需 **map user→tenant**。授權可更細(文件 tagging / 敏感度分級 / 角色)。
- **filtering / security trimming**:「Restricting access to only the data that users are authorized to access is known as filtering or security trimming.」可用 row-level security 或自訂 metadata 邏輯。
  來源:Azure *Design a Secure Multitenant RAG Inferencing Solution*,ms.date **2025-10-03**,更新 **2026-07-02**。<https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/secure-multitenant-rag>

**AWS**:GenAI Lens 的 8 情境明列 **multi-tenant generative AI service system**,並在 Cost Optimization 支柱要求「optimize vector stores and agent workflows」、Security 支柱要求「mitigate excessive agency / monitor & audit events」。
  來源:AWS GenAI Lens(2025-11-19)。

**Azure 多 agent 補充**:多 agent 架構可做「granular security boundaries at the agent level」——例如 HR agent 能碰員工資料、客服 agent 只碰產品資料,用**agent 層級**切權限。

**成本控制官方手法**:按查詢複雜度**路由到不同模型**(輕模型答簡單題、強模型做複雜推理);store-per-tenant 利於**成本歸因**;優化 vector store 與 agent workflow(AWS)。

**啟示(高度相關 Caliburn——你就是多租戶 B2B SaaS)**:
1. 你的 embedder/indexer/api 之間應有一層**強制租戶過濾的 gatekeeper**——檢索時務必帶 tenant discriminator,且 api 的知識 adapter 不該讓 authoring loop 繞過它直查 Qdrant。
2. B2B(公司數有限、每租戶資料多)→ 官方傾向 **store-per-tenant 或共用+強過濾**;你目前公司間隔離的設計與此一致。
3. 身分需一路流穿到檢索;每次 grounding 存取記 audit log。
4. 成本:對簡單著作步驟用輕模型、複雜推理用強模型的**模型路由**是官方推薦的降本手段。

---

## 來源總表(權威來源 + 日期)

### 模型廠官方(Anthropic / OpenAI / Google)
| 來源 | 日期 | URL |
|---|---|---|
| Anthropic — Building Effective AI Agents | 2024-12-19 | https://www.anthropic.com/engineering/building-effective-agents |
| Anthropic — Effective context engineering for AI agents | 2025-09-29 | https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents |
| Anthropic — Effective harnesses for long-running agents | 2025 | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| Claude Agent SDK — overview (Claude Code Docs) | 2025(持續) | https://code.claude.com/docs/en/agent-sdk/overview |
| Anthropic — Building agents with the Claude Agent SDK | 2025-09 | https://claude.com/blog/building-agents-with-the-claude-agent-sdk |
| OpenAI Agents SDK — 官方 docs | 2025-03-11 起 | https://openai.github.io/openai-agents-python/ |
| OpenAI Agents SDK — Tracing | 2025 | https://openai.github.io/openai-agents-python/tracing/ |
| OpenAI — A practical guide to building agents (PDF) | 2025 | https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf |
| OpenAI — Safety in building agents | 2025 | https://platform.openai.com/docs/guides/agent-builder-safety |
| OpenAI — Introducing canvas | 2024-10(2026 擴充) | https://openai.com/index/introducing-canvas/ |
| Google — Agent Development Kit (ADK) docs | 2025(持續) | https://adk.dev/ |
| Google Cloud — Introducing Gemini Enterprise Agent Platform | 2025 | https://cloud.google.com/blog/products/ai-machine-learning/introducing-gemini-enterprise-agent-platform |

### 雲廠官方架構中心(AWS / Azure)
| 來源 | 日期 | URL |
|---|---|---|
| AWS Well-Architected — Generative AI Lens | 2025-11-19 | https://docs.aws.amazon.com/wellarchitected/latest/generative-ai-lens/generative-ai-lens.html |
| AWS Architecture Blog — 三個新 Well-Architected Lens (re:Invent 2025) | 2025-11 | https://aws.amazon.com/blogs/architecture/architecting-for-ai-excellence-aws-launches-three-well-architected-lenses-at-reinvent-2025/ |
| Azure Architecture Center — Baseline Microsoft Foundry Chat | 2026-06-17 | https://learn.microsoft.com/en-us/azure/architecture/ai-ml/architecture/baseline-microsoft-foundry-chat |
| Azure Architecture Center — Secure Multitenant RAG | 2025-10-03(更新 2026-07-02) | https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/secure-multitenant-rag |
| Azure Architecture Center — RAG solution design & evaluation guide | 2025–2026 | https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/rag/rag-solution-design-and-evaluation-guide |
| Azure Architecture Center — AI agent orchestration patterns | 2025–2026 | https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns |

### 原廠框架官方(LangChain/LangGraph)
| 來源 | 日期 | URL |
|---|---|---|
| LangChain — How to think about agent frameworks | 2025 | https://www.langchain.com/blog/how-to-think-about-agent-frameworks |
| LangGraph — overview docs | 2025(1.0 於 2025-10) | https://docs.langchain.com/oss/python/langgraph/overview |
| LangGraph — 產品頁 | 2025 | https://www.langchain.com/langgraph |

### 佐證趨勢(二手,僅作趨勢參考,不作主張依據)
- Claude Code 2025-05 移除向量檢索改用 grep(多篇轉述);Pydantic AI 官方 docs(未深讀,列為後續)。

> 備註:未及深讀但值得後續補的官方來源——Anthropic *Building a multi-agent research system*(orchestrator-worker 實例)、OpenAI **AgentKit / Agent Builder** 官方頁、Google ADK 各子頁(Sessions/Memory/Runners/Eval)、Pydantic AI 官方 docs、AWS Prescriptive Guidance *Agentic AI frameworks*。
