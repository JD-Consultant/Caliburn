# AI Agent 應用架構設計 — 2025–2026 主流共識與趨勢研究紀錄

> 研究日期:2026-07-12。純學習研究,不綁任何專案。
> 來源紀律:只收模型廠官方工程文章、知名框架原廠、有署名資深實務者原著、頂會/大實驗室論文。
> 每條發現標 URL + 發布日期;優先 2025 下半年–2026 材料。

---

## 摘要(給趕時間的人)

2026 年的共識可濃縮為一句話:**「先用最簡單的東西,把複雜度留到你能證明它值得為止」**——這條線從
Anthropic 2024 年底的〈Building Effective Agents〉一路貫穿到 2026 年所有官方材料,沒有被推翻,只被
細化。幾個高信度的收斂點:

1. **單一 agent 優先,多 agent 是例外**。多 agent 只在「breadth-first、可平行、read-only 資訊蒐集」型
   任務有明確回報(Anthropic 內部 +90.2%,但吃 ~15× token);寫入型/強耦合任務(尤其 coding)仍該
   單執行緒。Cognition 從「別建多 agent」修正為「寫入單執行緒、附加 agent 只貢獻智力不動手」。
2. **編排的重心從「graph 硬編排」往「單 loop + 好工具 + 好 context」移**。Anthropic 官方立場是
   「給 agent 一台電腦」,靠 `gather context → take action → verify` 這個泛用 loop,而不是把流程寫死成圖。
   LangGraph 仍活躍,但定位收斂成「當你真的需要 durable execution / 分支 / 人在迴路才用的 low-level 層」。
3. **Context engineering 取代 prompt engineering 成為第一工程職責**。核心敵人是 context rot / 有限注意力
   預算;主流手法是 just-in-time retrieval、compaction、note-taking/memory、sub-agent 隔離。
4. **工具要為 agent 設計,不是包 API**:高槓桿整併工具、namespacing、回人類可讀內容、token 效率、
   可行動的錯誤訊息。2026 新方向是 **code execution with MCP**(把工具當程式碼模組按需載入)。
5. **狀態放你自己的系統**(12-factor:stateless reducer + 統一 execution/business state),別綁死在框架
   checkpoint 裡。
6. **前人踩坑清單**已被官方明講:過早多 agent、過度編排、框架綁死加無謂複雜度、prompt 疊補丁、
   把中間結果全塞進 context。
7. **2026 新方向**:long-horizon agents(靠 檔案/artifact 當記憶橋接跨 context window)、code execution
   as backbone、模型端 agentic 能力內建化(讓多 agent 中「smart friend 委派」開始可行)。

---

## Q1. 單 agent vs 多 agent:2026 的共識走到哪

**結論**:共識是「**預設單 agent;多 agent 僅限可平行、read-only、breadth-first 的資訊蒐集型任務,且要接受
~15× token 成本**」。這條辯論在 2026 年沒有「一邊贏」,而是**兩邊收斂到同一組適用判準**:寫入(action)要
單執行緒,平行只用在「貢獻智力/蒐集」而非「同時動手改同一份東西」。Anthropic 與 Cognition 表面對立,實則
都指向「context 連續性 + 單執行緒寫入」是可靠性的關鍵。

**關鍵證據**
- Anthropic〈Building Effective Agents〉(2024-12-19):定義 workflows =「systems where LLMs and tools are
  orchestrated through predefined code paths」,agents =「systems where LLMs dynamically direct their own
  processes and tool usage」;核心建議「we recommend finding the simplest solution possible, and only
  increasing complexity when needed」,甚至「might mean not building agentic systems at all」。
  <https://www.anthropic.com/engineering/building-effective-agents>
- Anthropic〈How we built our multi-agent research system〉(2025-06-13):orchestrator-worker;「multi-agent
  system with Claude Opus 4 as the lead agent and Claude Sonnet 4 subagents outperformed single-agent
  Claude Opus 4 by 90.2%」但「multi-agent systems use about 15× more tokens than chats」。明確劃界:
  「some domains that require all agents to share the same context or involve many dependencies between
  agents are not a good fit for multi-agent systems today」,並點名 coding「most coding tasks involve fewer
  truly parallelizable tasks than research」。
  <https://www.anthropic.com/engineering/multi-agent-research-system>
- Cognition〈Don't Build Multi-Agents〉(Walden Yan,2025-06-12):兩原則「Share context, and share full
  agent traces, not just individual messages」與「Actions carry implicit decisions, and conflicting
  decisions carry bad results」;主張 context engineering 是「the #1 job of engineers building AI agents」;
  推 linear single-threaded agent,並點名批評 OpenAI Swarm / Microsoft AutoGen「pushing concepts which I
  believe to be the wrong way of building agents」。
  <https://cognition.com/blog/dont-build-multi-agents>
- Cognition〈Multi-Agents: What's Actually Working〉(Walden Yan,2026-04-22):立場更新——「models have
  become way more naturally 'agentic'」、Devin 用量 ~8× 成長;但可行 pattern 仍窄:「multi-agent systems
  work best today when writes stay single-threaded and the additional agents contribute intelligence rather
  than actions」、「most multi-agent setups in the world are limited to 'readonly' subagents」;剩下的難題
  「The open problems are all communication problems」。
  <https://cognition.com/blog/multi-agents-working>
- OpenAI〈A practical guide to building agents〉(2025):同調——「prefer single-agent design unless
  complexity, tool overload, or conditional logic warrants separation」。
  <https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf>

**別犯前人錯的啟示**
- 不要一開始就切多 agent。先問:任務能真平行嗎?子任務彼此獨立(不共享寫入)嗎?回報值得 ~15× token 嗎?
  三個都 Yes 才考慮。
- 若一定要多 agent:**寫入單執行緒**,平行的 subagent 只做 read-only 蒐集/審查,結果收斂回主 agent。
- 別被「90.2%」誘惑而忽略它是「breadth-first research」情境;coding / 強耦合任務照官方說法仍不適合。

---

## Q2. 編排:workflow(程式控制流)vs agentic loop(模型控制流)怎麼選;graph 還是主流嗎

**結論**:選擇準則沒變——**能把路徑寫死、要可預測就用 workflow;無法預測步數、需要模型自己決策就用 agent
loop**。2026 的移動方向是重心從「graph 式硬編排」往「單一泛用 loop + 好工具」傾斜:Anthropic 官方明說要
「給 agent 一台電腦」用 `gather context → take action → verify` 的通用迴圈跑幾乎所有 agent 任務,而非把流程
畫成圖。LangGraph 沒死,但定位收斂為「當你真的需要 durable execution / 明確分支 / 人在迴路 / 嚴格延遲控制
才下沉去用的 low-level 層」,不是預設起手式。

**關鍵證據**
- Anthropic〈Building Effective Agents〉(2024-12-19):「workflows offer predictability and consistency for
  well-defined tasks, whereas agents are the better option when flexibility and model-driven decision-making
  are needed」;agent 適用「open-ended problems where it's difficult or impossible to predict the required
  number of steps」;框架警語「frameworks … can also make it tempting to add complexity when a simpler
  setup would suffice」。
- Anthropic〈Building agents with the Claude Agent SDK〉(2025-09-29):核心 loop「gather context → take
  action → verify work → repeat」;設計哲學「give your agents a computer, allowing them to work like humans
  do」;團隊從「把 Claude Code 當 coding 工具」演化成通用 harness——「it has begun to power almost all of
  our major agent loops」(research、video、customer support 都跑同一 harness)。
  <https://claude.com/blog/building-agents-with-the-claude-agent-sdk>
- LangChain/LangGraph 官方(2026):LangGraph 自我定位為「low-level orchestration framework for building
  stateful, long-running agents with durable execution」;並明講「if you are just getting started … LangChain's
  agents provide prebuilt architectures for common LLM and tool-calling loops」,LangGraph 是「when you have
  advanced needs … deterministic + agentic workflows, heavy customization, carefully controlled latency」才用。
  <https://docs.langchain.com/oss/python/langgraph/overview>
- 對照:Caliburn 專案 CLAUDE.md 記載其 authoring 層「刻意單層 loop,別重構」——與 Anthropic「單泛用 loop」
  方向一致(此為本 repo 慣例,非外部來源,僅作旁證)。

**別犯前人錯的啟示**
- 起手式用「單 loop + 一組好工具」,不要一開始就畫 graph。graph 是當你**已經**證明需要明確分支/durable
  resume/嚴格延遲控制時的下沉選項,不是複雜度的預設稅。
- 「能寫死的就寫死」——可預測的子步驟用程式控制流(便宜、可測),把模型的自由裁量留給真的無法預測的部分。
- 別把框架的表達力當成「應該用滿」。framework tempting to add complexity 是官方點名的壞味道。

---

## Q3. Context engineering:官方最新指引

**結論**:2025 下半年起,**context engineering 正式取代 prompt engineering 成為第一工程議題**。核心約束是
「context rot / 有限注意力預算」——context window 塞越多,召回與推理反而退化。官方指引一致收斂到五招:
(1) system prompt 寫在「對的海拔」(不要太細也不要太空)、(2) 工具要自足清晰、(3) **just-in-time retrieval**
(存輕量識別碼、runtime 才載入)、(4) **compaction**(接近上限就摘要重開 context)、(5) **note-taking/memory
+ sub-agent 隔離**(把細節丟到 context 外、子 agent 用乾淨 context 只回濃縮結果)。

**關鍵證據**
- Anthropic〈Effective context engineering for AI agents〉(2025-09-29):定義「Context engineering refers to
  the set of strategies for curating and maintaining the optimal set of tokens (information) during LLM
  inference」;context rot——「as the number of tokens in the context window increases, the model's ability
  to accurately recall information from that context decreases」(源於 transformer 的 n² pairwise 關係);
  「every new token introduced depletes this budget by some amount」。手法:just-in-time =「lightweight
  identifiers (file paths, stored queries, web links) … dynamically load data into context at runtime」;
  compaction =「summarizing its contents, and reinitiating a new context window」;structured note-taking =
  「regularly write notes persisted to memory outside of the context window」;sub-agent =「handle focused
  tasks with clean context windows … clear separation of concerns」。
  <https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>
- Anthropic 多 agent 文亦印證:sub-agent「use their own isolated context windows, and only send relevant
  information back to the orchestrator」——context 隔離是多 agent 少數真正的價值來源。
- Cognition 兩篇均把 context engineering 定為第一要務,並警告「breaking context across agents is
  fundamentally risky」(見 Q1 來源)。

**別犯前人錯的啟示**
- 不要因為「context window 變大」就把所有東西塞進去。**更大 ≠ 更好**(context rot 是實測現象)。
- 用「引用而非搬運」:存 file path / query / link,需要時才載入,而不是把整份資料 pre-load。
- 長對話要主動 compaction + note-taking;把「當前需要的最小集合」維持在 context,細節持久化到外部。
- sub-agent 的第一價值是**context 隔離**(乾淨窗口做髒活、只回摘要),而不是「更多腦袋」。

---

## Q4. 工具設計:給 agent 的工具怎麼設計;MCP 的角色與 2026 現況

**結論**:工具是「deterministic 系統與 non-deterministic agent 之間的契約」,要**為 agent 設計而非為開發者
包 API**。官方原則:高槓桿整併工具(一個 `schedule_event` 勝過三個 CRUD)、清楚 namespacing、回**人類可讀
內容**(不是原始 UUID)、token 效率(pagination/filter/response_format)、**可行動的錯誤訊息**、並用 Claude
自己跑 evaluate→optimize 迴圈。MCP 在 2026 仍是連接標準,但重心從「把工具全載進 context」移到 **code
execution with MCP**——把 MCP server 當程式碼模組、按需載入、在程式碼裡先過濾再回傳,大幅省 token。

**關鍵證據**
- Anthropic〈Writing effective tools for AI agents〉(2025-09-11):「tools represent a contract between
  deterministic systems and non-deterministic agents」;整併——「Instead of implementing a `list_users`,
  `list_events`, and `create_event` tools, consider implementing a `schedule_event` tool」;namespacing——
  「grouping related tools under common prefixes … help delineate boundaries」;可讀輸出——「return only
  high signal information」、優先「natural language names, terms, or identifiers」勝過 UUID;token 效率——
  `ResponseFormat` 讓 agent 選 concise(72 tokens)vs detailed(206 tokens);錯誤——「Clearly communicate
  specific and actionable improvements, rather than opaque error codes or tracebacks」;流程 Prototype →
  Evaluate → Collaborate,「you can even let agents analyze your results and improve your tools for you」。
  <https://www.anthropic.com/engineering/writing-tools-for-agents>
- Anthropic〈Building Effective Agents〉早已預示:「Tool definitions and specifications should be given just
  as much prompt engineering attention as your overall prompts」;SWE-bench 經驗「we actually spent more
  time optimizing our tools than the overall prompt」。
- Anthropic〈Code execution with MCP〉(2025-11-04):問題——「Tool definitions occupy more context window
  space」、中間結果反覆過 context(2 小時會議 transcript 可多耗「an additional 50,000 tokens」);解法——把
  MCP server 當 filesystem 內的 code 模組、按需 read tool 定義、在 code 裡先 filter/transform,案例把
  150,000 → 2,000 tokens(~98.7% 省);代價——「Running agent-generated code requires a secure execution
  environment with appropriate sandboxing, resource limits, and monitoring」。
  <https://www.anthropic.com/engineering/code-execution-with-mcp>

**別犯前人錯的啟示**
- 別把內部 REST API 一對一包成工具。工具數量爆炸 + 薄包裝 = agent 選錯 + token 浪費。整併成「一個工具做完
  一個工作流」。
- 工具輸出是給模型讀的:回人類可讀欄位、預設分頁/截斷、提供 concise/detailed 選項。
- 錯誤訊息要教 agent 怎麼修,不是丟 traceback。
- 工具多到一定規模(數十個 MCP server)時,考慮 code execution 模式;但要先備妥 sandbox——這是新增的
  營運/安全成本,不是免費午餐。

---

## Q5. 無狀態 vs 有狀態回合:狀態放哪

**結論**:資深實務共識(12-factor agents)是**把 agent 寫成 stateless reducer——`f(events) → next_action`
的純函數,狀態放你自己的系統/業務層,而不是綁死在框架 checkpoint 裡**。這帶來可測試、可重播、可暫停/續跑、
可從任意入口觸發的好處。框架端(LangGraph)則提供 durable execution + checkpointing 作為「你需要時的持久化
機制」——兩者不矛盾:你可以用框架的持久化,但**狀態的所有權與語意要握在自己手上**。

**關鍵證據**
- HumanLayer / Dex Horthy〈12-Factor Agents〉(GitHub,2025):十二因子含 Factor 3「Own your context
  window」、Factor 4「Tools are just structured outputs」、Factor 5「Unify execution state and business
  state」、Factor 8「Own your control flow」、Factor 10「Small, Focused Agents」、Factor 12「Make your agent
  a stateless reducer」;核心「agent 是 pure function:f(events) → next_action」讓 testing/replay/debug
  deterministic;狀態建議「keep state in your application's existing business layer, not isolated within
  agent frameworks」;Factor 3 被稱為 linchpin,並有「dumb zone」觀察(大 context 中段 40–60% 召回退化,
  來自 10 萬場 session 分析)。
  <https://github.com/humanlayer/12-factor-agents>
  <https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-03-own-your-context-window.md>
- LangGraph 官方(2026):「durable execution — build agents that persist through failures … automatically
  resuming from exactly where they left off」、「durable execution with configurable checkpointing」是核心
  特性——這是「機制」層,可搭配自有狀態語意使用。
  <https://docs.langchain.com/oss/python/langgraph/overview>
- Anthropic 長時程文(見 Q7)實務印證:狀態用 **檔案/git/JSON** 當跨 context 的記憶橋接(progress log、
  feature list),而非依賴框架內部隱藏狀態。

**別犯前人錯的啟示**
- 把 agent 設計成「吃 event 序列、吐下一步」的純函數;狀態(execution + business)存進你自己的 DB/檔案,
  這樣才能 replay/測試/從任意入口續跑。
- 框架 checkpoint 好用,但別讓它變成「唯一知道發生什麼事的地方」——那會綁死框架且難 debug。
- 「execution state 和 business state 分兩套」會漂移(agent 以為做了 vs 實際做了);官方建議統一。

---

## Q6. 常見前人踩坑(官方/資深來源明講的 anti-patterns)

**結論**:各家獨立列出的坑高度重疊,可整併成一張清單。核心壞味道是「在還沒證明必要前就加複雜度」。

**關鍵證據(逐條附出處)**
- **過早/過度多 agent**:寫入型與強耦合任務不該平行;coding 尤其不適合(Anthropic 多 agent 文,
  2025-06-13)。Cognition 把「別建多 agent」列為第一課(2025-06-12)。
- **破壞 context 連續性**:「breaking context across agents is fundamentally risky」;只傳單則訊息而非完整
  trace 會讓 implicit decisions 衝突(Cognition,2025-06-12)。
- **過度編排 / 框架誘導的無謂複雜度**:「frameworks … can also make it tempting to add complexity when a
  simpler setup would suffice」;「add complexity only when it demonstrably improves outcomes」(Anthropic
  BEA,2024-12-19)。
- **框架綁死狀態/控制流**:狀態該在自己的業務層,控制流該自己擁有(12-factor Factor 5/8/12,2025)。
- **把工具當薄 API 包裝、工具過多**:薄包裝 + 無 namespacing 讓 agent 選錯、吃 token(Anthropic writing
  tools,2025-09-11)。
- **中間結果全塞 context / 以為 context 越大越好**:context rot;「every new token … depletes this budget」
  (Anthropic context engineering,2025-09-29)。中間結果反覆過 context 是 code-execution 文要解的痛
  (2025-11-04)。
- **prompt 疊補丁**:12-factor「Own your prompts」+ context engineering「system prompt 要在對的海拔」——
  用堆疊 if-else 式補丁救 prompt 是反模式,應重構 context 配置。
- **autonomous 的隱性成本**:「autonomous nature of agents means higher costs, and the potential for
  compounding errors」(Anthropic BEA,2024-12-19)。

**別犯前人錯的啟示**:每次想加一層(多 agent / graph / 框架 / 新工具),先問「我有沒有證據證明簡單方案
過不了 eval?」沒有就別加。複雜度要靠 eval 買單,不是靠直覺。

---

## Q7. 2026 新出現的方向(官方已明說的趨勢)

**結論**:四條官方趨勢:(1) **long-horizon / long-running agents**——靠「檔案/artifact 當跨 context window 的
記憶橋接 + 自我驗證」跑數小時級任務;(2) **code execution as backbone**——把工具互動下沉成模型寫程式碼、
按需載入 MCP;(3) **模型端 agentic 能力內建化**——模型「天生更會當 agent」,讓某些過去不可行的多 agent
pattern(如 smart-friend 委派)開始能用;(4) **通用 agent harness / Agent SDK 產品化**——同一 harness 跑
research/coding/video/support。

**關鍵證據**
- **Long-horizon**:Anthropic〈Effective harnesses for long-running agents〉(2025-11-26):用 Initializer
  agent(建環境)+ Coding agent(逐段執行)跨多個 context window;handoff 靠**檔案**——`claude-progress.txt`、
  `feature_list.json`、git history、`init.sh`;「The key insight here was finding a way for agents to quickly
  understand the state of work when starting with a fresh context window」;自我驗證用 Puppeteer MCP 做
  end-to-end 測試才標記完成;compaction 單靠自己「proves insufficient」,需搭配檔案記憶。
  <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>
- **Code execution as backbone**:見 Q4〈Code execution with MCP〉(2025-11-04)——「LLMs are adept at
  writing code」故讓 agent 用程式碼組合 MCP 工具是效率新骨幹。
- **模型端 agentic 內建化**:Cognition(2026-04-22)「models have become way more naturally 'agentic'」,
  使「smart friend delegation」「manager coordination」等多 agent pattern 從不可行變部分可行;但仍受限於
  模型間能力落差(「the gap between [SWE 1.5] and Sonnet 4.5 was too wide」)。
  <https://cognition.com/blog/multi-agents-working>
- **通用 harness / SDK**:Anthropic〈Building agents with the Claude Agent SDK〉(2025-09-29)——同一 harness
  「power almost all of our major agent loops」;built-in 檔案編輯/bash/web search/web fetch/subagents/
  sessions/MCP client。
  <https://claude.com/blog/building-agents-with-the-claude-agent-sdk>

**別犯前人錯的啟示**
- 要跑長任務,別指望「更大 context」或「純 compaction」撐住;用**檔案/artifact + git 當外部記憶**,讓每個
  fresh context 能快速重建工作狀態,並強制 end-to-end 自我驗證再標完成。
- code execution 是強力新工具但帶 sandbox/安全成本,值不值得看你的工具規模。
- 「模型變強」會持續改寫可行邊界:今天不可行的多 agent pattern 明年可能可行——所以架構要**可漸進演化**
  (單 agent 起步、必要時才長出 subagent),別一次押死在重編排上。
- 注意:有二手來源宣稱存在「2026-04 Planner/Generator/Evaluator 四小時循環」的 Anthropic 文,但我能核到的
  官方原文(2025-11-26)是 Initializer + Coding + 檔案記憶模式,未給小時數/循環數字。**以官方原文為準,
  勿引用未經核實的二手數字。**

---

## 來源總表

| # | 標題 | 作者/機構 | 日期 | URL |
|---|------|-----------|------|-----|
| 1 | Building Effective Agents | Anthropic | 2024-12-19 | https://www.anthropic.com/engineering/building-effective-agents |
| 2 | How we built our multi-agent research system | Anthropic | 2025-06-13 | https://www.anthropic.com/engineering/multi-agent-research-system |
| 3 | Don't Build Multi-Agents | Cognition / Walden Yan | 2025-06-12 | https://cognition.com/blog/dont-build-multi-agents |
| 4 | Multi-Agents: What's Actually Working | Cognition / Walden Yan | 2026-04-22 | https://cognition.com/blog/multi-agents-working |
| 5 | Effective context engineering for AI agents | Anthropic | 2025-09-29 | https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents |
| 6 | Writing effective tools for AI agents | Anthropic | 2025-09-11 | https://www.anthropic.com/engineering/writing-tools-for-agents |
| 7 | Code execution with MCP: building more efficient agents | Anthropic | 2025-11-04 | https://www.anthropic.com/engineering/code-execution-with-mcp |
| 8 | Building agents with the Claude Agent SDK | Anthropic | 2025-09-29 | https://claude.com/blog/building-agents-with-the-claude-agent-sdk |
| 9 | Effective harnesses for long-running agents | Anthropic | 2025-11-26 | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| 10 | 12-Factor Agents | HumanLayer / Dex Horthy | 2025 | https://github.com/humanlayer/12-factor-agents |
| 11 | 12-Factor Agents — Factor 3: Own your context window | HumanLayer / Dex Horthy | 2025 | https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-03-own-your-context-window.md |
| 12 | A practical guide to building agents | OpenAI | 2025 | https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf |
| 13 | LangGraph overview (docs) | LangChain | 2026(持續更新) | https://docs.langchain.com/oss/python/langgraph/overview |

### 來源可信度備註
- 1–9、13 為模型廠/框架**原廠官方**工程文章或文件;3–4 為 Cognition 官方部落格(署名 Walden Yan,
  Devin 團隊);10–11 為 12-factor agents 原作者 repo;12 為 OpenAI 官方 PDF。全部符合來源紀律。
- 搜尋過程中出現的 Medium 轉述、SEO 摘要站、awesome list 一律未採用,僅用官方原文核對引文。
- 一處二手來源(zylos.ai)宣稱的「2026-04 Anthropic long-running 四小時 Planner/Generator/Evaluator」
  數字**未能在官方原文核實**,已於 Q7 標記存疑、不採用。
