# 產出專業級文件的 AI 應用怎麼蓋(2024–2026)

> 研究範圍:法律文件起草、合約審閱、法律檢索、顧問報告、合規文件——「錯了有代價、要專家等級品質」的領域。
> 純學習研究,不綁專案。
> 來源紀律:優先各公司**自家官方 blog/技術文章**、模型廠**官方 case study**、**頂會/官方評測**。
> 二手或行銷性材料一律標註。日期為文章發布日。

---

## 快速地圖:誰是誰

| 廠商 | 領域 | 底層模型 | 一手技術資料程度 |
|---|---|---|---|
| **Harvey** | BigLaw 通用法律著作/檢索 | 多模型(自研微調 + Claude + OpenAI) | **高**——工程 blog 有真內容 |
| **Thomson Reuters CoCounsel**(原 Casetext) | 法律檢索/著作 | 多模型 + Westlaw/Practical Law 內容 | **高**——TR Institute 技術 blog |
| **Hebbia** | 金融+法律高風險分析 | OpenAI GPT-4o 等 | **中高**——工程 blog 有架構細節 |
| **Ironclad** | 合約審閱/CLM | 自研法律模型 + GPT-4(Rivet 框架) | 中——多為產品文,技術一手少 |
| **Robin AI** | 合約審閱 | Anthropic Claude + 200 萬份合約庫 | 中——lawyer-in-loop 模式明確,技術細節少 |
| **Writer** | 企業內容/合規 | 自研 Palmyra + Knowledge Graph RAG | 中高——工程 blog + RobustQA benchmark |
| **McKinsey Lilli** | 顧問報告/提案/簡報 | 內部平台(聚合知識庫) | 低——多為新聞轉述,無技術一手 |

---

## Q1. 品質怎麼撐到專家級

**結論:沒有單一銀彈。專家級品質 = 「權威內容 grounding + 檢索優化 + 多步 pipeline + 引用強制 + 專家 rubric + 人審」六件事疊加,而且每一家都在公開文件裡強調 RAG 本身不夠。**

關鍵證據:

- **Stanford HAI 直接打臉「RAG = 無幻覺」**:研究測試 Lexis+ AI、Westlaw AI-Assisted Research、Ask Practical Law AI,結論明言 *"RAG is not a panacea"*,列出三個結構性難點:法律檢索本身難找對權威、會抓到不適用管轄區的判例、AI sycophancy(順著使用者的錯誤前提走)。實測幻覺率:Westlaw ~34%、Lexis+ ~17%、Practical Law ~17%、通用 GPT-4 類 58–82%。
  - 來源:Stanford HAI,*AI on Trial: Legal Models Hallucinate in 1 out of 6 (or More) Benchmarking Queries*,2024-05-23。https://hai.stanford.edu/news/ai-trial-legal-models-hallucinate-1-out-6-or-more-benchmarking-queries
  - 論文:*Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools*(JELS, 2025)。https://law.stanford.edu/wp-content/uploads/2024/05/Legal_RAG_Hallucinations.pdf

- **Harvey 的品質定義是「補完律師級工作成品的百分比」**,不是「答對題」。BigLaw Bench 的 Answer Score 問的是 *"What % of a lawyer-quality work product does the model complete?"*,rubric 對必要內容給正分、對幻覺/語氣/離題**給負分**。自研模型可達 *"74% of a final, expert lawyer-quality work product"*。
  - 來源:Harvey,*Introducing BigLaw Bench*,2024-08-29。https://www.harvey.ai/blog/introducing-biglaw-bench

- **CoCounsel 把「可驗證」寫進架構本身**:每個答案都帶引用與 hyperlink 回 Westlaw;內容 grounding 在 *"35 million West Key Number classifications and 3.9 million Precision Research attributes"* 這種數十年精煉的權威分類體系,而非爬來的公開資料。TR 自稱 *"verification part of the system's architecture rather than an afterthought"*(fiduciary-grade)。
  - 來源:Thomson Reuters Institute,*Rebuilding for the Agent Era: The Next Generation of CoCounsel Legal*,2026-03-10。https://www.thomsonreuters.com/en-us/posts/innovation/rebuilding-for-the-agent-era-the-next-generation-of-cocounsel-legal/

**啟示**:專家級不是靠更大模型,而是靠**「權威內容 + 流程約束 + 負分懲罰幻覺 + 以成品完成度計分」**。單發生成天花板低;品質是被 pipeline 和 rubric「逼」出來的。

---

## Q2. 文件生成的架構(單發 vs 多步 vs agent 迭代;模板 vs 模型分工)

**結論:2024→2026 明顯從「單發 RAG 生成」轉向「agentic 多步分解」。共識架構 = 中央 orchestrator 規劃 → 分解子任務 → 專職 subagent 各管一步(檢索/讀取/推理/輸出格式化)→ 帶引用合成。結構由程式/rubric 定,內容由模型生。**

關鍵證據:

- **Hebbia:把 retrieval 和 output 拆成不同 agent 是消除幻覺的關鍵**。Agent 1.0 是單一 monolithic agent 把所有工具塞一起,導致「搞混該用哪個工具」。2.0 改成 *"a central orchestrator and multiple specialized subagents"*(ReadAgent、OutputAgent…),orchestrator 只派發文字目標、不直接呼叫工具,像經理指派員工。技術核心叫 **Iterative Source Decomposition (ISD)** + 強型別階層 context class。成果:**tool-use 幻覺近乎消除**。
  - 來源:Hebbia,*Divide and Conquer: Hebbia's Multi-Agent Redesign*,2025-06-17。https://www.hebbia.com/blog/divide-and-conquer-hebbias-multi-agent-redesign
  - Matrix 是 tabular「data-grid」介面,把使用者查詢分解為 summarization / analysis / comparison / synthesis 這類律師工作流步驟,**每個 agent 擁有一步**。

- **CoCounsel 從「skill 路由」升級為「每個請求即時設計解法」**:*"It plans. It selects tools. It retrieves authoritative content. It adapts as new information emerges."* 這是明確的從固定 skill → 動態 agentic planning 的轉向。
  - 來源:同上 TR *Rebuilding for the Agent Era*(2026-03-10)。

- **Thomson Reuters「Deep Research」**:承認傳統 RAG 的侷限,做成 agentic 系統——自主規劃多步檢索、並行執行、選工具、依發現調整、套用停止準則。
  - 來源:ZenML LLMOps Database 整理的 TR 案例(二手彙整,原始為 TR 演講)。https://www.zenml.io/llmops-database/agentic-ai-for-legal-research-building-deep-research-in-westlaw-and-cocounsel

- **Harvey 用 OpenAI Agent SDK 消除自訂 orchestration**,以 **Tool Bundles**(模組化能力 + 部分 system prompt 控制)組合出跨檢索/起草/審閱/整合的 emergent 功能,把 in-thread 功能開發從 1 隊擴到 4 隊還能維持品質。
  - 來源:Harvey 工程文(經 ZenML 二手彙整:*Scaling Agent-Based Architecture for Legal AI Assistant*)。https://www.zenml.io/llmops-database/scaling-agent-based-architecture-for-legal-ai-assistant

**結構 vs 內容分工**:Ironclad 是最清楚的「模板/工作流程式定、內容模型生」案例——AI 內建進 workflow engine,Intake Agent 抽 metadata、Redlining Agent 依**公司標準**標出缺漏/風險條款,結構與規則是程式化的、由 Rivet 框架驅動,模型只負責在框內生成。
  - 來源:Ironclad,*AI That Works Where You Work*,2025–2026。https://ironcladapp.com/resources/articles/ai-agentic-launch

**啟示**:大廠對「一次到位生成整份文件」已不抱幻想。**分解 → 逐步 → 專職 agent → 合成**是主流;把「檢索」與「輸出格式化」拆開能顯著降幻覺;可程式化的結構(章節、條款清單、rubric)交給程式,只讓模型填內容。

---

## Q3. 領域知識怎麼進系統 + 怎麼防幻覺引用

**結論:主流是 RAG(向量 + LLM-based retrieval + metadata + 特徵工程),不是主靠 fine-tune;知識圖譜(Writer)是一條明確替代/增強路線。防幻覺引用靠「內容原生 grounding + trace/citation 驗證 + 幻覺引用自動拒收」,而非事後檢查。**

關鍵證據:

- **Harvey 的檢索不只是語意搜尋**:三招疊加——(1) metadata enhancement 給段落加上下文、(2) feature engineering 納入 recency 等 embedding 忽略的因子、(3) **LLM-based retrieval** 讓模型做 relevancy 判斷抓 embedding 抓不到的語意。實測比 OpenAI / Voyage / Cohere 的 embedding+rerank 多找到 **up to 30%** 相關內容。指標是「固定 token 門檻下的 recall」,對照 in-house 法律團隊事先建的 ground truth。
  - 來源:Harvey,*BigLaw Bench Deep Dive: Retrieval*,2024-11-13。https://www.harvey.ai/blog/biglaw-bench-retrieval

- **防幻覺引用的機器化把關(Harvey Data Factory)**:自動化管線的四步評估裡,第 3 步 **Trace Validation** 明確——*"hallucinated citations trigger automatic rejection"*;第 4 步多 agent 分別評 URL 分類、引用品質、法律推理、呈現。每個資料源評估耗約 15 萬 token。這條管線讓覆蓋從 6 個管轄區→60+、20 個資料源→400+。
  - 來源:Harvey,*Using Agents to Scale Harvey's Knowledge Sources*(2025-08 起的 Data Factory)。https://www.harvey.ai/blog/using-agents-to-scale-harveys-knowledge-sources

- **CoCounsel 靠「權威內容原生」防幻覺**:grounding 只在 Westlaw / Practical Law 這類「數十年精煉、非爬蟲」內容;對外部權威源與客戶自有文件套用一致的 *"taxonomy, citation, and metadata discipline"*;檢索到案例→注入 context→生成時明確 cite→hyperlink 回原文。
  - 來源:同 TR *Rebuilding for the Agent Era*(2026-03-10);*Responsible AI for court systems with CoCounsel Legal*。

- **知識圖譜路線(Writer)**:自家 Knowledge Graph RAG 在 RobustQA benchmark 拿 >86 分,自稱在 8 種 RAG 實作中排第一,主張 graph-based 比純向量檢索**幻覺更少**。
  - 來源:Writer 工程 blog,*RAG benchmarking: Writer Knowledge Graph ranks #1*。https://writer.com/engineering/rag-benchmark/(廠商自評,方法為 RobustQA,需注意利益相關)

- **Robin AI**:Claude + **200 萬份合約專有資料集**,外加 lawyer-in-the-loop 把 edge case 路由給人。
  - 來源:Anthropic 投資與模式描述(二手彙整,見來源表)。

**Fine-tune 的角色**:Harvey 有自研微調模型(BigLaw Bench 上勝過基座),但**檢索 grounding 才是引用真實性的主力**;fine-tune 主要用來「講該事務所的話/語氣」與領域推理,不是拿來記憶法條。

**啟示**:引用真實性的正解是**「把引用綁死在檢索到的來源、並在管線裡自動驗證 trace,幻覺引用直接拒收」**,而非生成後再檢查。知識圖譜是降幻覺的一條實證路線,但目前公開 benchmark 多為廠商自評。

---

## Q4. 專家在迴路(律師/顧問審什麼、何時審、給什麼工具)

**結論:專家在迴路有兩種角色——(A) 建置期:專家建 rubric / ideal-answer 金鑰 / 標註訓練資料;(B) 生產期:專家審成品、edge case 路由給人。工具設計圍繞「可驗證」:逐句引用 hyperlink、trace 可展開、redline 可接受/拒絕。**

關鍵證據:

- **建置期——領域專家嵌進團隊**:Harvey *"secret sauce is this environment where we have domain experts embedded into teams"*(前 BigLaw 律師 + AI 工程師共同把「法律問題 map 成模型問題」)。BigLaw Bench 的 rubric 由這些律師依真實計費工時設計。
  - 來源:Anthropic/Claude 客戶故事,*Customer story | Harvey*。https://claude.com/customers/harvey

- **生產期——lawyer-in-the-loop 路由**:Robin AI 明確 *"wrapped in a lawyer-in-the-loop review model that routes edge cases to human experts"*。合約審閱工具給的是 redline(標缺漏/風險條款依公司 playbook),人做接受/拒絕決策。
  - 來源:Ironclad *AI That Works Where You Work*(Redlining Agent);Robin AI 模式描述。

- **CoCounsel Trust Team 的人審閉環**:attorney SME 手工做出「ideal response」金鑰並經同儕審查;自動測試的**失敗案例由律師人工檢視根因**,再與工程迭代 prompt、重測;還會 spot-check 通過樣本確保自動評估對齊人類判斷。
  - 來源:TR Institute,*From Testcase to Trust: Benchmarking CoCounsel with Scorecard*,2025-09-26。https://www.thomsonreuters.com/en-us/posts/innovation/from-testcase-to-trust-benchmarking-cocounsel-with-scorecard/

- **顧問業(McKinsey Lilli)**:AI 接手初階格式化/建簡報/擬提案,junior 轉向 data storytelling、model validation、client workshop——**人往上游驗證與敘事移動**,而非審每個字。自動生成的 deck/proposal 占 Lilli 用量約 1/3。
  - 來源:Fortune(二手新聞),*McKinsey leans on AI…*,2025-06-02。https://fortune.com/2025/06/02/mckinsey-ai-consulting-powerpoints-proposal-technology/(無技術一手資料)

**啟示**:專業級系統把「人審」設計成**可負擔的驗證**——逐句引用可點回原文、redline 可逐條裁決、trace 可展開,讓專家審「有疑處」而非重讀全文。專家更大的槓桿其實在**建置期建 rubric 與金鑰**。

---

## Q5. 評測與信任(evals、benchmark、怎麼向專業客戶證明品質)

**結論:業界共識是「拿真實工作任務、由 SME 建金鑰、對照計分、且要公開/可審計」。內部有 Harvey BigLaw Bench、TR Scorecard;外部有 Stanford HAI 的獨立稽核。Stanford 明確呼籲「public benchmarking + 透明化」是專業客戶信任的前提。**

關鍵證據:

- **Harvey BigLaw Bench**:任務取自**真實律師計費工時**,涵蓋交易(策略/起草/盡調)與訴訟(案件分析/文件審查/庭前)。雙指標:**Answer Score**(補完律師級成品的百分比,幻覺/語氣/離題扣分)+ **Source Score**(*"What % of correct statements does the model support with an accurate source?"*)。發現:基座模型在 source score 上差距**急遽拉大**——即使明確要求也會幻覺來源。
  - 來源:Harvey,*Introducing BigLaw Bench*,2024-08-29。

- **TR Scorecard**(工程班底來自 Waymo 自駕測試基建):SME 手建 gold-standard,自動化以 recall/precision/accuracy 對照計分(案例中 1/5 vs 4/5);testset 數百+;跑「數百萬次 agent 模擬」;部署後每日多次持續監控。Casetext 時期上線前跑近 **4,000 小時訓練/微調、逾 30,000 個法律問題**。
  - 來源:TR *From Testcase to Trust*(2025-09-26);CoCounsel 安全性文(SOC 2 Type II / ISO 27001 / zero-retention)。

- **CoCounsel 新一代自報 76% 成功率**:在「無約束、多步」法律工作流上,基於數百個真實任務、SME 審查,累積「數萬小時專家審查與標註」。
  - 來源:TR *Rebuilding for the Agent Era*(2026-03-10)。

- **獨立稽核(第三方 evals 的重要性)**:Stanford HAI 用 200+ 預先登錄(pre-registered)的開放式查詢,分四類(一般研究/管轄區與時間敏感/假前提/事實回憶),**手工評分**,直接檢驗廠商「hallucination-free」宣稱並判其**誇大**。呼籲業界需要 *"public benchmarking and rigorous evaluations"* 與對工具設計/模型/評測結果的透明。
  - 來源:Stanford HAI(2024-05-23)+ JELS 論文(2025)。

- **Hebbia 對外宣稱 92% 準確率**(跨量化+質化任務、複雜法律/金融文件),分離架構後「近乎消除 tool-use 幻覺」。
  - 來源:Hebbia 產品頁 + 多 agent redesign blog(廠商自評,benchmark 方法未完整公開)。

**啟示**:可信 eval 的配方——(1) 任務來自**真實工作成品**而非考題;(2) **SME 建 ideal-answer 金鑰**;(3) **分開計「答對」與「引用有據」**;(4) 驗證評估器本身(spot-check 對齊人類);(5) 接受**第三方獨立稽核**。廠商自評數字(92%、86、#1)要打折看,方法透明度是關鍵。

---

## Q6. 演進教訓(公開講過的失敗與轉向)

**結論:三大公開教訓——(1) 引用幻覺是真實災難(Mata v. Avianca 引爆,已 1,000+ 起法院裁定),催生「引用必驗證、幻覺即拒收」;(2)「RAG 就無幻覺」的行銷被獨立稽核打臉,倒逼公開 benchmark;(3) 單一 monolithic agent 撐不住複雜工作,全業界轉向多 agent 分解。**

關鍵證據:

- **引用幻覺醜聞(Mata v. Avianca, SDNY, 2023-05)**:律師用 ChatGPT 生成含**虛構判例**的動議,法官 Castel 依 Rule 11 罰款 $5,000。後續 Damien Charlotin 的公開資料庫追蹤到全球約 **1,490 起**、其中美國 1,000+ 起 AI 幻覺材料被法院處置的裁定(截至 2026-05)。這是整個法律 AI「引用必須可驗證」設計哲學的起點。
  - 來源:*Mata v. Avianca, Inc.*(Wikipedia,彙整court record);GC AI 幻覺裁定 tracker。https://en.wikipedia.org/wiki/Mata_v._Avianca,_Inc. / https://gc.ai/blog/ai-hallucination-legal-cases

- **「hallucination-free」宣稱被打臉 → 轉向透明**:LexisNexis/Thomson Reuters 曾宣稱避免/杜絕幻覺,Stanford 實測 17–34% 幻覺率,判宣稱**誇大**。此後 TR 的敘事明顯轉向「可驗證性寫進架構」「數萬小時專家審查」「Scorecard 量化」——用透明度重建信任。
  - 來源:Stanford HAI(2024-05-23);對照 TR 2025–2026 諸文的論述轉向。

- **從 monolithic 到 multi-agent 的架構轉向**:Hebbia 白紙黑字承認 Agent 1.0 單一 agent 會「搞混工具、參數給錯」,2.0 拆成 orchestrator + 專職 subagent 才近乎消除 tool-use 幻覺。CoCounsel 從 skill 路由改為動態 agentic planning。都是「demo 能跑、production 撐不住複雜任務」的公開修正。
  - 來源:Hebbia(2025-06-17);TR(2026-03-10)。

- **Harvey 從單模型到多模型**:為了「彈性與可靠性」把 Claude 加入原本的架構,並強調在他們 eval 上長 context 推理(upper token thresholds)是致勝點——承認沒有單一模型全能。
  - 來源:Claude 客戶故事(Harvey);多來源報導 Harvey 多模型轉向。

**啟示**:這個領域的每一次重大轉向都是被**真實代價**逼出來的——法院罰款逼出引用驗證、獨立稽核逼出透明、複雜任務失敗逼出多 agent。給任何要蓋專業級 docgen 的人的核心教訓:**先假設模型會幻覺引用,把「驗證」做成系統的骨架而非附加功能;用真實任務 + SME 金鑰做 eval;別信自家「無幻覺」直覺,交給獨立/可審計的測試。**

---

## 給「蓋專業級 docgen」的濃縮啟示(跨六問)

1. **grounding 是地基,但不是全部**——Stanford 已證 RAG 非萬靈丹;要疊 metadata、feature eng、LLM-based retrieval,並在**管線內驗證 trace、幻覺引用自動拒收**。
2. **結構程式定、內容模型生**——章節/條款清單/rubric/redline 規則交給程式;模型只在框內填內容並綁引用。
3. **多步 agent 分解 > 單發生成**;把**檢索與輸出格式化拆開**是降幻覺的高槓桿動作(Hebbia 實證)。
4. **eval 用真實工作成品 + SME ideal-answer 金鑰**,分開計「答對」與「引用有據」,並驗證評估器本身。
5. **人審設計成可負擔的驗證**(逐句引用可點、redline 可裁決、trace 可展開),把專家更多投在**建 rubric/金鑰**的上游。
6. **信任靠透明**:接受第三方稽核,自報數字打折看。

---

## 來源總表

### 一手 / 權威(優先採信)
- Harvey, *Introducing BigLaw Bench*, 2024-08-29 — https://www.harvey.ai/blog/introducing-biglaw-bench
- Harvey, *BigLaw Bench Deep Dive: Retrieval*, 2024-11-13 — https://www.harvey.ai/blog/biglaw-bench-retrieval
- Harvey, *Using Agents to Scale Harvey's Knowledge Sources*(Data Factory, 2025-08 起)— https://www.harvey.ai/blog/using-agents-to-scale-harveys-knowledge-sources
- Anthropic / Claude, *Customer story: Harvey* — https://claude.com/customers/harvey
- Thomson Reuters Institute, *Rebuilding for the Agent Era: The Next Generation of CoCounsel Legal*, 2026-03-10 — https://www.thomsonreuters.com/en-us/posts/innovation/rebuilding-for-the-agent-era-the-next-generation-of-cocounsel-legal/
- Thomson Reuters Institute, *From Testcase to Trust: Benchmarking CoCounsel with Scorecard*, 2025-09-26 — https://www.thomsonreuters.com/en-us/posts/innovation/from-testcase-to-trust-benchmarking-cocounsel-with-scorecard/
- Thomson Reuters, *Responsible AI for court systems with CoCounsel Legal* — https://legal.thomsonreuters.com/blog/responsible-ai-in-courts-the-answer-is-cocounsel-legal/
- Hebbia, *Divide and Conquer: Hebbia's Multi-Agent Redesign*, 2025-06-17 — https://www.hebbia.com/blog/divide-and-conquer-hebbias-multi-agent-redesign
- Hebbia, *Introducing Matrix: The Interface to AGI* — https://www.hebbia.com/blog/introducing-matrix-the-interface-to-agi
- Ironclad, *AI That Works Where You Work: Introducing Ironclad's Next Wave of AI Agents*, 2025–2026 — https://ironcladapp.com/resources/articles/ai-agentic-launch
- Writer, *RAG benchmarking: Writer Knowledge Graph ranks #1*(廠商自評,RobustQA)— https://writer.com/engineering/rag-benchmark/

### 學術 / 獨立稽核(高權威)
- Stanford HAI, *AI on Trial: Legal Models Hallucinate in 1 out of 6 (or More) Benchmarking Queries*, 2024-05-23 — https://hai.stanford.edu/news/ai-trial-legal-models-hallucinate-1-out-6-or-more-benchmarking-queries
- Stanford, *Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools*(JELS, 2025)— https://law.stanford.edu/wp-content/uploads/2024/05/Legal_RAG_Hallucinations.pdf

### 公共紀錄 / 事件
- *Mata v. Avianca, Inc.*(SDNY 2023;$5,000 sanction)— https://en.wikipedia.org/wiki/Mata_v._Avianca,_Inc.
- GC AI, *AI Hallucination Legal Cases: A Sanctions Tracker*(彙整 Charlotin 資料庫)— https://gc.ai/blog/ai-hallucination-legal-cases

### 二手彙整 / 需注意(有用但非一手,或含行銷味)
- ZenML LLMOps Database — Harvey *Scaling Agent-Based Architecture*(彙整 Harvey 演講)— https://www.zenml.io/llmops-database/scaling-agent-based-architecture-for-legal-ai-assistant
- ZenML LLMOps Database — Thomson Reuters *Deep Research*(彙整 TR 演講)— https://www.zenml.io/llmops-database/agentic-ai-for-legal-research-building-deep-research-in-westlaw-and-cocounsel
- Fortune, *McKinsey leans on AI to make PowerPoints faster*(二手新聞,**無技術一手資料**)— 2025-06-02 — https://fortune.com/2025/06/02/mckinsey-ai-consulting-powerpoints-proposal-technology/
- OpenAI case studies(Hebbia、Ironclad):行銷性 case study,技術細節有限(Hebbia 頁抓取時 403);內容以廠商宣稱為主,需打折 — https://openai.com/index/hebbia/ , https://openai.com/index/ironclad/

### 一手資料缺口(誠實標註)
- **McKinsey Lilli / Big 4 顧問報告生成**:僅有新聞轉述與行銷,**未找到技術一手資料**(架構、eval 方法未公開)。
- **Robin AI**:lawyer-in-loop 模式明確,但**檢索/評測技術細節未公開**;多為投資新聞與二手描述。
- **廠商自評 benchmark**(Hebbia 92%、Writer 86/#1):方法透明度不足,對外宣稱應打折。
