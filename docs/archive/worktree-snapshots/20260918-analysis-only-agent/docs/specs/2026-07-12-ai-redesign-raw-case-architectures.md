# 領先 AI 產品公司的真實系統架構(2024–2026 一手案例)

> 純學習研究,不綁專案。來源紀律:只收各公司**自家官方 engineering blog / 技術文章 / 官方演講(署名工程師)**與**模型廠官方 customer engineering 案例**。每條標 URL + 日期。無一手資料者明說。
> 調查日期:2026-07-12。深挖 7 家:Anthropic、Cognition(Devin)、Cursor、Intercom(Fin)、Sierra、GitHub Copilot、Notion。

---

## 1. Anthropic — Claude Code / Agent SDK + Multi-Agent Research

一手資料最豐富的一家。兩篇官方 engineering blog 交叉印證:一篇講**通用 agent 設計**(SDK),一篇講**生產環境多 agent 系統**的真實踩雷。

### 架構摘要
- **核心迴圈是三段式**:`gather context -> take action -> verify work -> repeat`。這是刻意的、可自我修正的 feedback loop。LLM 被當成 stateless reasoning engine,harness 負責 state / 安全 / context 截斷 / 工具路由。
- **Orchestrator-worker + subagents**:主 agent(lead)拆解任務、派給並行 subagent。**subagent 有自己隔離的 context window,只把相關結論回傳給 orchestrator**——這是「context 管理」而非只是「並行加速」的手段。
- **模型分工**:生產研究系統用 **Claude Opus 4 當 lead、Claude Sonnet 4 當 subagent**;此組合在內部 research eval 上「outperformed single-agent Claude Opus 4 by 90.2%」。
- **狀態/記憶**:長任務靠**外部化**。「The LeadResearcher begins by thinking through the approach and **saving its plan to Memory to persist the context**, since if the context window exceeds 200,000 tokens it will be truncated.」context 接近上限時自動壓縮摘要;檔案系統本身是 context 的一部分(`grep`/`tail` 選擇性取用)——「The folder and file structure of an agent becomes a form of context engineering」。
- **寫入/守門(verify 這一段)**:「The best form of feedback is providing clearly defined rules for an output, then explaining which rules failed and why」——rule-based lint、visual feedback、LLM-as-judge 三種驗證。研究產出最後由獨立的 **CitationAgent** 補來源歸屬。
- **品質管線(生產做法,非理論)**:
  - LLM-as-judge 單一評審打五軸:factual accuracy / citation accuracy / completeness / source quality / tool efficiency。
  - 「People testing agents find edge cases that evals miss」——保留人審。
  - 全量 production tracing + 監控 agent 決策模式;上線用 **rainbow deployments**(逐步轉流量,不打斷跑到一半的 agent)。

### 演進教訓(最值錢的部分,全是他們自述的「一開始做錯」)
- **早期 subagent 暴走**:「spawning 50 subagents for simple queries, scouring the web endlessly」。解法:把 scaling rule 寫進 prompt——「Simple fact-finding requires just 1 agent with 3-10 tool calls」。
- **任務拆解太模糊**:早期給「research the semiconductor shortage」這種短指令,subagent 誤解或彼此重複搜同樣的東西。解法:每個 subagent 必須有「an objective, an output format, guidance on the tools and sources to use, and clear task boundaries」。
- **來源品質**:agent「consistently chose SEO-optimized content farms over authoritative but less highly-ranked sources」——加 source quality heuristics 到 prompt 才修好。(這條剛好呼應本研究的來源紀律。)
- **搜尋策略**:agent 預設用「overly long, specific queries」→ 改成「start with short, broad queries... then progressively narrow」。
- **成本現實**:「agents typically use about **4× more tokens** than chat interactions, and **multi-agent systems use about 15× more tokens** than chats」;「token usage by itself explains 80% of the variance」in 品質。→ 多 agent 只在高價值、可並行、任務夠重時才划算。

### 來源
- Thariq Shihipar et al., "Building agents with the Claude Agent SDK", Anthropic Engineering, 2025-09-29. https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk (現重導向 https://claude.com/blog/building-agents-with-the-claude-agent-sdk)
- Jeremy Hadfield, Barry Zhang, Kenneth Lien, Florian Scholz, Jeremy Fox, Daniel Ford, "How we built our multi-agent research system", Anthropic Engineering, 2025-06-13. https://www.anthropic.com/engineering/multi-agent-research-system

---

## 2. Cognition (Devin) — 從「別做 multi-agent」到「寫入必須單線程」

同一作者(Walden Yan)前後兩篇,是**業界對多 agent 立場演進最清楚的一手紀錄**,且與 Anthropic 恰成對照。

### 架構摘要與立場演進
- **2025-06(Don't Build Multi-Agents)**:主張大多數情況用**單線程線性 agent** 就好,因為「the context is continuous」。兩條原則:
  1. 「**Share context, and share full agent traces, not just individual messages**」——subtask 失敗多因只看到片段而非完整決策軌跡。
  2. 「**Actions carry implicit decisions, and conflicting decisions carry bad results**」——並行 subagent 各自做隱含假設 → 結果互相打架。
  - 結論:「running multiple agents in collaboration only results in fragile systems」。長任務改用「LLM-based history compression layer」壓縮而非分裂。
- **2026-04(Multi-Agents: What's Actually Working)**:立場**收斂而非翻案**。有一類多 agent 現在能用:「setups where multiple agents contribute intelligence to a task **while writes stay single-threaded**」。
  - 核心規則:**寫入永遠單線程,額外的 agent 只貢獻「智慧/資訊」而非「動作」**。
  - 實作:「A manager Devin can break a larger task into pieces, spawn child Devins to work on them, and coordinate their progress through an **internal MCP**」;模式是 **map-reduce-and-manage**(manager 拆、children 執行、manager 綜合回報)。
  - 尚未解的都是**通訊問題**:「How does a weaker model learn when to escalate? How does a child agent surface a discovery that should change its siblings' work?」

### 教訓
把「多 agent 有沒有用」重新框成「**哪一段可以並行**」:讀取/研究可以扇出,**寫入這道 seam 必須單一 writer**,否則隱含決策衝突。這是跨案例最重要的共識點之一。

### 來源
- Walden Yan, "Don't Build Multi-Agents", Cognition Blog, 2025-06-12. https://cognition.com/blog/dont-build-multi-agents
- Walden Yan, "Multi-Agents: What's Actually Working", Cognition Blog, 2026-04-22. https://cognition.com/blog/multi-agents-working

---

## 3. Cursor (Anysphere) — Shadow Workspace:AI 寫入前的隔離驗證關

一手 engineering blog,聚焦**寫入路徑的守門機制**,對「AI 產出如何安全進到使用者程式碼」講得最具體。

### 架構摘要
- **問題**:「the AI iteration needs to happen in the background, without affecting your coding experience」——AI 要能反覆試錯,但不能污染使用者的 buffer。
- **Shadow Workspace = 隱藏的第二個編輯環境**:「whenever an AI wants to see lints for code that it wrote, we spawn a **hidden window** for the current workspace」。這個窗「completely independent from the user, so the AIs can freely do any changes」。
- **驗證靠 LSP/lints**:「**Letting AIs get lints for their edits is one of the most impactful ways to improve code generation**」。復用 VS Code 的 language server,讓 AI 能看到自己改動的編譯錯誤、型別錯誤、跳定義。
- **通訊/隔離**:走 extension host 之間的 gRPC(非 renderer 直連);多個 AI 請求以「重置資料夾狀態」序列化;opt-in、閒置 15 分鐘自動收。
- **未來方向**:kernel 層 FUSE 檔案系統代理,做到真正 disk-level 隔離供執行程式碼用。

### 演進教訓
Shadow Workspace 是「AI 先在沙盒裡改、拿到 lint 反饋、驗證過才呈現給人」的具體實作。**注:** 據多方(含 Cursor 官方 changelog 生態)報導,Shadow Workspace 在 v0.45 後被更全面的 agentic tool-use 架構取代——即 agent 透過工具直接跑 lint/測試來驗證。此「被取代」細節屬二手,原理(先驗證再落地)仍成立。

### 來源
- Arvid Lunnemark, "Iterating with shadow workspaces", Cursor Blog, 2024-09-01. https://cursor.com/blog/shadow-workspace
- (Composer MoE 模型、Merkle-tree 增量索引、Tree-sitter 分塊等 retrieval 細節目前僅見於二手整理,**未取得對應一手 blog**,故不作結論性引用。)

---

## 4. Intercom (Fin) — 客服 agent 的 RAG 三段管線 + 驗證關

一手 engineering blog(產品/工程角度)+ 官方 Help 文件描述 Fin AI Engine。技術深度不如前三家,但**寫入前的驗證關與生產 eval 流程**講得清楚。

### 架構摘要
- **RAG 為底,而非裸呼叫 foundation model**:「Fin's answers use generative AI technology to create the answer based on a range of support content using the Retrieval-Augmented Generation (RAG) framework」。
- **每則訊息走三段循序管線**(官方 Fin AI Engine 描述):**Refine Query(理解真正在問什麼)→ Generate Response(RAG 取材、生成有據答案)→ Validate Accuracy(驗證再出口)**。這道「Validate」是明確的守門關。
- **寫入/交接路徑**:能答就答,超出能力則「seamlessly hand over to a support agent」——AI 與人審之間有明確 handover seam。
- **針對 email 加專屬架構層**:「we partnered with Machine Learning scientists and engineers to create a **new component in the AI agent's underlying architecture specifically for email**」——含「一封信拆多問題分別處理」、內建 spam/自動信過濾、忽略無關簽名圖片。
- **品質管線(生產做法)**:每個新模型先跑「structured offline tests」再上「live A/B trials」,評 instruction following、tool call accuracy、coherence 才部署。

### 生產規模數據(佐證真實上線,非 demo)
上線首月:「Fin processed over 1 million end user emails... provided an AI-generated answer to over 81% of the email conversations」且平均「automatically resolving more than 56% of them」。

### 演進教訓
Intercom 強調 Fin「built on top of Intercom's existing customer platform」,由 20 個工程團隊、數百工程師直接改處理 Fin 互動的碼——即**AI 能力被縫進既有產品工作流,而非另起爐灶**。(其自研 "Apex" 模型、~67% resolution 等數字散見二手/OpenAI 案例,非本篇一手 blog,列作旁證。)

### 來源
- Julia Godinho, "Fin over email: How we built a multichannel AI agent", Intercom Blog, 2024-10-17. https://www.intercom.com/blog/fin-over-email-how-we-built/
- "The Fin AI Engine" (官方 Help,三段管線描述). https://www.intercom.com/help/en/articles/9929230-the-fin-ai-engine
- 旁證(模型廠 customer 案例,非架構一手):"Intercom's three lessons for creating a sustainable AI advantage", OpenAI. https://openai.com/index/intercom/

---

## 5. Sierra (Bret Taylor) — 宣告式 Agent SDK + Supervisor 層層把關

一手 blog(工程角色說明)+ 官方 τ-bench 研究。核心是**用宣告式程式與 supervisor 把不可靠的 LLM 包成可上線的企業 agent**。

### 架構摘要
- **Agent SDK = 堆疊 composable skills**:「a powerful framework that enables Agent Engineers to construct agents by **stacking composable skills and enforcing deterministic API interactions**」;用「declarative programming language」定義行為(「building with lego bricks instead of pouring concrete」)。
- **Orchestration/控制流**:SDK「powers the orchestration necessary to manage agent control flow, ensuring that Sierra's agents access the right systems of record at the right time」——多個 API 呼叫按特定順序達成結果。
- **Supervisor 守門(關鍵)**:「built-in supervisors to ensure that agents perform appropriately」。數學論證:第一個模型 90% 對,疊一個也 90% 對的 supervisor 驗證/修正,「the combined accuracy of the two models can skyrocket to **99%**」。可為受規管客戶(醫療/金融)建 custom supervisor。
- **determinism 可調**:「tune agent creativity and determinism according to the context」;高度規管場景可「**selectively bypass an LLM**」以求一致性——即容許「這一步不要 LLM,走死板 code」。

### 教訓
Sierra 的立場:單一 LLM 不可靠是前提,**可靠性來自架構(supervisor 層 + 可調 determinism + 宣告式控制流),而非寄望模型變強**。這與其 τ-bench 論文結論一致:「agents built with simple LLM constructs (like function calling or ReAct) perform poorly」。

### 來源
- Natalie Meurer, "Meet the AI agent engineer", Sierra Blog, 2024-07-11. https://sierra.ai/blog/meet-the-ai-agent-engineer
- Bret Taylor, τ-bench 發布(agent 可靠性 benchmark), 2024-06. https://x.com/btaylor/status/1803805751951167755

---

## 6. GitHub Copilot — Coding Agent 與 Code Review 轉向 agentic tool-calling

一手 GitHub Blog / Changelog。Copilot 從「補下一行」演進到「規劃-執行-迭代跨 repo」;code review 也從逐行掃 diff 改為 agentic 探索。

### 架構摘要
- **Coding agent 的寫入路徑**:從 GitHub Issue 描述寫碼、跑 terminal 指令自修 build error、推 draft PR 供人審。**產出一律進 draft PR + PR review**——即寫入路徑天然被 GitHub 既有的 PR/CI/人審關卡包住(這是它最重要的 seam 設計:AI 不直接寫 main,而是產 PR)。
- **繼承自 Copilot Workspace**:「took its **sub-agent architecture, issue-to-PR workflow, and natural language planning** from the original Workspace, then rebuilt them as the coding agent」。
- **Code review 轉 agentic(2026-03-05)**:不再逐行掃 diff,而是「uses agentic **tool calling** to gather broader repository context as needed (relevant code, directory structure, and references)」→ 探索 repo、讀相關檔、追跨檔依賴,再評論。宣稱「higher-quality findings... Lower noise」。
- **執行基礎設施**:agentic code review「runs on **GitHub Actions**」(可自架或 GitHub-hosted runner)——即 agent 的執行環境就是既有 CI runner,不另造 sandbox 概念。
- **整合面**:coding agent 接 GitHub Issues、Azure Boards、Jira、Linear、Slack、Teams 及任何 MCP 工具。

### 教訓
GitHub 的架構選擇 = **把 AI 塞進既有 SDLC 的守門結構(PR → CI → review)**,而非發明新的信任機制。寫入路徑的「幾道關」直接復用 pull request / status check / 人審。

### 來源
- "Copilot code review now runs on an agentic architecture", GitHub Changelog, 2026-03-05. https://github.blog/changelog/2026-03-05-copilot-code-review-now-runs-on-an-agentic-architecture/
- "How to maximize GitHub Copilot's agentic capabilities", GitHub Blog. https://github.blog/ai-and-ml/github-copilot/how-to-maximize-github-copilots-agentic-capabilities/
- "GitHub Copilot: the agent awakens", GitHub Blog. https://github.blog/news-insights/product-news/github-copilot-the-agent-awakens/

---

## 7. Notion — 為「LLM 已懂的東西」而設計,harness 重寫 5 次

**注:無專屬 engineering blog 一手貼文**;一手性來自**兩位 Notion 工程負責人(共同創辦人 Simon Last、AI 工程經理 Sarah Sachs)的具名公開演講/播客**(Latent Space),屬可查證 talk,採信但標明性質。二手(VentureBeat/Braintrust)僅作佐證。

### 架構摘要與教訓(此案例本身就是「演進教訓」)
- **核心 agent harness 重寫 4–5 次**才上線 Custom Agents。關鍵領悟:**要為「LLM 已經理解的東西」設計,而非為公司內部工程方便設計**。
- **工具介面向模型語言靠攏**:放棄自家內部資料模型/專有 JSON API,改用**模型早已熟悉的介面**——DB 查詢用 **SQLite 語法**、文件格式從 custom XML 改成 Notion-flavored Markdown。「100+ tools」、MCP vs CLI 取捨是其設計主軸。
- **檢索**:pipeline 為「提問 → 即時取相關 chunk → 餵 LLM → 回答」;強調 **agent 在意 top-K 取回準確率**(而非給人瀏覽的排序名單),因此投資「agentic find」——生成多個 query 變體、把檢索當成一段整合旅程。
- **品質管線**:自建「headroom evals(Notion's last exam)」,並設立專職 **Model Behavior Engineer**(資料科學+PM+prompt engineer 混合);evals 已「saturated」到「could no longer provide meaningful feedback to frontier labs beyond 'it's not worse'」。
- **團隊文化**:「I explicitly hire for **low ego and comfort with deleting one's own code**」——因為 harness 註定要一再打掉重練。

### 來源
- Simon Last & Sarah Sachs (Notion), "Notion's Token Town: 5 Rebuilds, 100+ Tools, MCP vs CLIs...", Latent Space Podcast, 2026(具名工程負責人演講). https://www.latent.space/p/notion
- 佐證(二手):"To scale agentic AI, Notion tore down its tech stack and started fresh", VentureBeat. https://venturebeat.com/ai/to-scale-agentic-ai-notion-tore-down-its-tech-stack-and-started-fresh ; Notion evals @ Braintrust. https://www.braintrust.dev/customers/notion

---

## 跨案例歸納

### 多家共同的架構選擇(強共識)
1. **寫入路徑必須單一 writer / 有明確守門關**。Cognition 明講「writes stay single-threaded」;Cursor 用 shadow workspace 先驗證再落地;GitHub 一律走 draft PR→CI→review;Intercom 有 Validate 段 + 人審 handover;Sierra 用 supervisor 疊加。**讀取/研究可並行扇出,寫入不可並行**——這是最一致的一條。
2. **可靠性來自架構,不寄望模型變強**。Sierra 的 supervisor(90%×90%→99%)、Anthropic 的 verify 段與 LLM-as-judge、Intercom 的三段驗證——都把「不可靠的 LLM」包在確定性的守門/驗證層裡。
3. **Context / 記憶外部化**。長任務不靠 context window 硬撐:Anthropic 存 plan 到 Memory + 檔案系統當 context;Cognition 用 history compression;共識是「context engineering 是核心」。
4. **工具(tool-use)是執行的主要積木,且要向模型已懂的介面靠攏**。Anthropic「tools are the primary building blocks」、Notion 改用 SQLite/Markdown、GitHub/Cognition/Sierra 全靠 MCP + tool calling。**自建 loop 為主,框架為輔**——沒有一家把核心編排外包給重量級 agent 框架;都是自建 harness + MCP/tool 標準。
5. **生產級 eval + 觀測是標配**:LLM-as-judge + 人審 + 全量 tracing(Anthropic)、offline test + live A/B(Intercom)、專職 eval 角色(Notion MBE)、τ-bench(Sierra)。理論 eval 不夠,都靠「人找到 eval 抓不到的 edge case」。
6. **把 AI 縫進既有工作流的守門結構**,而非另造信任機制:GitHub 復用 PR/CI、Intercom 建在既有客服平台、Cursor 復用 LSP。

### 分歧點
- **要不要多 agent**:Anthropic 力挺 orchestrator-worker 多 agent(研究類任務 +90%);Cognition 起初反對、後來只認可「智慧並行、寫入單線程」的窄類。分歧的真正軸線不是「幾個 agent」,而是**任務可不可並行拆解 + 寫入是否單線程**——研究/檢索類適合扇出,連續改寫類不適合。
- **模型策略**:Anthropic 明確大小模型分工(Opus lead / Sonnet subagent);Cursor、Notion 走自訓/專用模型(Composer MoE、Notion 自家後訓);Sierra 刻意可「bypass LLM」走死板 code。單模型 vs 多模型路由**無統一答案**,依任務結構決定。
- **隔離粒度**:Cursor 到 process/VM/未來 kernel-FUSE 級隔離;GitHub 用 CI runner;Sierra/Intercom 用 API-level 確定性交互 + supervisor。**寫程式碼類 agent 需要重隔離,客服/知識類 agent 靠邏輯守門即可**。
- **成本自覺**:只有 Anthropic 公開量化(chat 的 4×、multi-agent 15× token),明講多 agent 只在高價值可並行任務才划算;其餘家未公開對應數字。

### 給架構設計者的一句話萃取
真實系統的共同骨架 =「**自建 harness 迴圈(gather→act→verify)+ MCP/tool 當執行層 + context 外部化 + 寫入單一 writer 且過守門關 + 生產 tracing/eval**」;差異主要落在**是否多 agent、模型如何分工、隔離做多重**,而這三者由「任務能否並行拆解、寫入是否連續」決定。

---

## 來源總表(僅列一手 / 具名演講;二手佐證已在各節標明)

| # | 公司 | 標題 | 作者 | 日期 | URL |
|---|------|------|------|------|-----|
| 1 | Anthropic | Building agents with the Claude Agent SDK | Thariq Shihipar et al. | 2025-09-29 | https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk |
| 2 | Anthropic | How we built our multi-agent research system | Jeremy Hadfield et al. | 2025-06-13 | https://www.anthropic.com/engineering/multi-agent-research-system |
| 3 | Cognition | Don't Build Multi-Agents | Walden Yan | 2025-06-12 | https://cognition.com/blog/dont-build-multi-agents |
| 4 | Cognition | Multi-Agents: What's Actually Working | Walden Yan | 2026-04-22 | https://cognition.com/blog/multi-agents-working |
| 5 | Cursor | Iterating with shadow workspaces | Arvid Lunnemark | 2024-09-01 | https://cursor.com/blog/shadow-workspace |
| 6 | Intercom | Fin over email: How we built a multichannel AI agent | Julia Godinho | 2024-10-17 | https://www.intercom.com/blog/fin-over-email-how-we-built/ |
| 7 | Intercom | The Fin AI Engine (官方 Help) | Intercom | — | https://www.intercom.com/help/en/articles/9929230-the-fin-ai-engine |
| 8 | Sierra | Meet the AI agent engineer | Natalie Meurer | 2024-07-11 | https://sierra.ai/blog/meet-the-ai-agent-engineer |
| 9 | GitHub | Copilot code review now runs on an agentic architecture | GitHub | 2026-03-05 | https://github.blog/changelog/2026-03-05-copilot-code-review-now-runs-on-an-agentic-architecture/ |
| 10 | GitHub | GitHub Copilot: the agent awakens | GitHub | — | https://github.blog/news-insights/product-news/github-copilot-the-agent-awakens/ |
| 11 | Notion | Token Town: 5 Rebuilds, 100+ Tools (具名工程負責人演講) | Simon Last & Sarah Sachs | 2026 | https://www.latent.space/p/notion |

### 沒取得一手架構資料的項目(誠實標註)
- **Cursor 的 retrieval/Composer 細節**(Merkle-tree 增量索引、Tree-sitter 分塊、Composer MoE):目前僅見二手整理(ByteByteGo、Medium),**未找到對應一手 engineering blog**,故本報告不作結論性引用。
- **Intercom "Apex" 自研模型與 ~67% resolution**:見二手/OpenAI 案例,非 Intercom 架構一手 blog。
- **Perplexity / Glean / Linear AI / Vercel v0 / Bolt**:本輪未取得夠格的一手架構貼文,未納入深挖(避免二手腦補)。
