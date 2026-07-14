# 訪談引擎驅動層(議程)架構研究——事故診斷 + 權威先例

- 日期:2026-07-14(討論中,**尚未裁決**;ADR 待方向鎖定後開)
- 觸發:live 新手 persona 訪談(session `330a0bed`,doc `55f30517`)——28 輪 70 分鐘,
  P(行為指標)零筆、進度緩慢、單一故事連鑽十輪。
- 狀態:維護者已選**方向 B(架構收斂)**;細部設計討論中。本檔先記事故+研究,
  防止 bug 清單與研究散失。

---

## 1. 事故診斷(DB 稽核證據,session 330a0bed)

證據來源:`interview_llm_calls.guard_verdicts`(130 筆)、`interview_review_events`
(95 accepted/0 rejected)、`interview_sessions.ledger_state`、逐字稿 28 turns、
verify 空文件 repro 實測。

### BUG-1|空白文件上綠字直落全滅(T5c 實作漏洞;確定碼 bug)

- 第 3 輪裁剪縫觸發:5 官方職責殼 + 9 官方任務,**14 筆全被
  `permission:目標在文件中不存在` 擋**。
- Repro 實測(verify_ops 四種 doc):完全空 `{}` → 擋;`ocs_content:None` → 擋;
  `ocs_content:{}`(缺 ocu_units 鍵)→ 放行;`ocu_units:[]` → 放行。
  新訪談 doc 命中前兩種。verify 懶建殼分支只認「父節點已是 dict」。
- 連鎖:殼(第一相)全滅 → 任務(第二相)掛在不存在的 index 上全滅 →
  裁剪縫 attempts 2 次即 STALL → **綠字直落整場熄火**(第 5 輪例外:
  使用者已手動開盤建出職責,對「有殼文件」落成 8 筆)。
- 教訓:單元測試 DOC 全自帶 `ocs_content.ocu_units`,漏測「處女文件」。

### BUG-2|書記從不起草 P(教材斷鏈)

- `SCRIBE_SYS` 八條規則無一提行為指標/`draft_indicator`;
  「不推測、不美化、名字用他的話」壓制「把證據改寫成標準句式」。
- `behavior-indicator/SKILL.md` 內容完整(STAR/ABCD、Bloom 動詞、iCAP 出處),
  但**兩條注入路都斷**:書記結構上不吃任何 skill(scribe.py 無 load_skill);
  顧問只在 `gap==indicators` 時載入,而該 gap 從未出現(見 BUG-3)。
- 鐵證:第 22 輪顧問問「怎樣算做對」,第 23 輪員工給出教科書級 P 素材
  (「放開滑鼠後手沒再焦慮亂點就過關」「看 Terminal Log 確認」),
  書記把它塞進 `details.standards`;`draft_indicator` 整場 0 筆(130 裁決中)。

### BUG-3|帳本梯子 × 盤 bulk 勾 20 任務 → P 數學上不可達

- `next_gap` 線性梯子:①未分級任務預算槽(20 任務×2=40 題,實填 3)
  →②③core 細項槽(×11)→**④才到 O+P/K/S**→⑤淺掃→⑥態度。
- `TURN_BUDGET=40`;P 排在數十個槽之後。梯子為「邊聊邊長 1-2 任務」設計,
  未為 ADR 0032 的「盤一次倒 20 任務」重新設計節奏。
- 連鎖:gap 永不指向 indicators → 顧問永不載 behavior-indicator 教材(BUG-2 第 2 路)。

### BUG-4|停滯/飽和偵測形同虛設(progressed 粒度錯)

- `note_attempt(gap, progressed)` 的 progressed=`scribe_res.progressed`
  =「書記本回合**有任何** op 落地」,非「被提示的 gap 有進帳」。
- 對話越豐富→書記越有東西記→attempts 永遠歸零→`is_stalled`(STALL_K=2,
  iCAP 飽和讓路)永不觸發。實證:70 分鐘後 ledger attempts 全 0。
- 反向也錯:第 5 輪裁剪落 8 筆真進度,但 progressed 只看書記 →
  `curation:tasks` 照樣 +1 到 STALL → 裁剪縫永久熄火。
- 疊加顧問 prompt「從故事自然帶出」偏置 → 單一盲測故事從第 8 輪鑽到第 28 輪。

### 附帶觀察

- 第 1 輪(最豐富的全包自述)結構上不可記:無任務無池 → 書記 schema 只剩 `none`。
- 95 筆 ✓ / 0 筆 ✗:審閱流健康,問題全在供給端。
- phase=review 後行為不變(無「補漏模式」)。
- 共同體質:**驅動層 = 十幾條散落確定性條件的隱式協調,無單一決策點**;
  斷法全是「靜默斷」(該發生的沒發生,不報錯)。寫入層
  (op→verify→`_pending`→人審)健康,事故中零失誤。

---

## 2. 權威先例研究

### 2.1 職能訪談方法論(領域黃金標準)

- **BEI(McClelland;Spencer & Spencer 操作化)**:訪談單位=**完整事件故事**
  (「講一件實際發生的事:你做了什麼/說了什麼/當下想什麼」);
  能力證據=**事後對逐字稿做主題編碼**(thematic analysis / CAVE),
  一個事件天然橫跨多個能力主題。
  來源:[McClelland 1998, Psychological Science](https://journals.sagepub.com/doi/abs/10.1111/1467-9280.00065)、
  [InterviewEdge BEI 實務](https://www.interviewedge.com/articles/Conducting-the-Behavioral-Event-Interview-BEI.htm)、
  [DDI STAR](https://www.ddi.com/solutions/behavioral-interviewing/star-method)。
- 涵義:**「訪談=填表」是範式錯配**。P 是「從事件敘事提煉的可觀察證據」,
  不是等著被填的空格。提煉(coding)是獨立步驟——我們目前沒有任何零件在做。

### 2.2 任務導向對話系統(TOD)

- **Over-answering / multi-intent 是常態**:一句話帶多槽多意圖,標準處理=
  狀態追蹤器**全寬更新**所有被提到的槽,policy 在更新後狀態上重規劃。
  來源:[MultiWOZ 2.2](https://arxiv.org/pdf/2007.12720)(active intents 多值)、
  [multi-domain DST survey](https://www.mdpi.com/2076-3417/13/15/8943)。
- **動態槽生成**:2024 職涯訪談對話系統(LLM-based dynamic slot generation)
  ——不固定 schema,邊聊邊由 LLM 生成該問的新槽;技能靠 abductive reasoning
  從敘事推。來源:[arXiv 2412.16943](https://arxiv.org/abs/2412.16943)。
- **階層目標**:HierTOD(VLDB 2025 DaSH)以階層目標驅動對話,取代平面槽序。
  來源:[HierTOD](https://www.vldb.org/2025/Workshops/VLDB-Workshops-2025/DaSH/DaSH25_6.pdf)。
- **趨勢**:硬編碼 NLU→DST→POL→NLG 管線 → LLM 主導規劃
  ([TOD survey, ACM 2025](https://dl.acm.org/doi/pdf/10.1145/3771090))。
  我們的 `next_gap` 梯子=最該被取代的硬編碼 POL。

### 2.3 大廠 agent 架構主張(Anthropic / OpenAI)

- **Anthropic**([Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)):
  workflows(預定碼路)vs agents(LLM 自主導向);「find the simplest solution
  possible」;多層抽象/脆弱 if-else「obscure…harder to debug」;
  agent 適用於「can't hardcode a fixed path」——訪談正是。
- **Anthropic**([Effective Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)):
  最小高訊號 token 集;避免「hardcoding complex, brittle logic」;
  just-in-time 載入指引。
- **OpenAI**([GPT-4.1 Prompting Guide](https://cookbook.openai.com/examples/gpt4-1_prompting_guide)):
  顯式 planning 提升 agentic 成功率;persistence/tool/planning 三提醒。

### 2.4 「planner 決策點」大廠先例(維護者指定深查;2026-07 補)

三家一手資料,結論一致:**不要獨立 planner 模組;規劃放在行動 agent 自己的
迴圈裡,以 function calling 呈現;議程外化成 artifact;確定性當 guardrail 不當駕駛。**

- **Microsoft(反面教材,最有力)**:Semantic Kernel 的獨立 Planner
  (Stepwise/Handlebars)**整個廢除**。官方理由:「as function calling has gotten
  increasingly more accurate…the need for additional 'planning' logic on top of
  the model has become less necessary, and **in some cases, can reduce the speed,
  cost, and accuracy** of a plan」;改用迴圈內 function calling 後
  「fewer tokens, more control, significantly lower time-to-first-token」。
  來源:[The future of Planners in SK](https://devblogs.microsoft.com/agent-framework/the-future-of-planners-in-semantic-kernel/)。
- **Anthropic(Claude Research lead agent)**:規劃在**行動 agent 自己的迴圈內**
  (thinking + 「saving its plan to Memory」——計畫是**外化 artifact**,防 context
  截斷丟失);**確定性 effort-scaling 規則寫進 prompt 當指引**
  (「simple fact-finding=1 agent/3-10 calls;direct comparisons=2-4 subagents…」),
  不是碼裡的分支。來源:[Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)。
- **OpenAI(A Practical Guide to Building Agents / Agents SDK)**:單 agent 迴圈
  跑到 exit condition;guardrails=迴圈外確定性過濾;multi-agent
  「shouldn't be your go-to solution」。決策=模型在迴圈內的 tool call。
  來源:[Building agents track](https://developers.openai.com/tracks/building-agents)、
  [Practical guide](https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/)。

**對本案的直接涵義**:§3 初稿的「獨立 planner 決策點(另一次 LLM 呼叫)」
是微軟已踩過並廢除的形。修正:**議程工具給顧問**(一顆腦不變)——
顧問在既有 chat_with_tools 迴圈內呼叫 enum 鎖死的議程工具(開/收事件),
service 確定性執行;覆蓋地圖/飽和/預算由碼算好**當事實注入**;
確定性 auto-close 當兜底 guardrail。主路徑零新增 LLM 呼叫。
(scribe.py 早留此縫:「LLM 訊號位需動 chat 介面,留縫待 chat 結構化輸出就緒」。)

### 2.5 「是否 2026 最新主流」核查(維護者追問;2026-07 補)

證實骨架,且共識更保守(往 governance 收斂,非往自主放飛):
- 「mature architecture **does not maximize autonomy—it maximizes conscious
  control**」;「Workflows, not fully autonomous agents, dominate production…
  hybrid architectures…hold up」;全自主僅 ~15% 企業試行。
- 「Each use case requires **deterministic validation of agent outputs before
  they reach a system of record**」= 我們的 verify 六查,教科書級樣板。
- 「reliability…comes from **engineering the system around** [the model]」= context
  engineering 為主。來源:[deepset spectrum](https://www.deepset.ai/blog/ai-agents-and-deterministic-workflows-a-spectrum)、
  [Vellum agentic workflows 2026](https://www.vellum.ai/blog/agentic-workflows-emerging-architectures-and-design-patterns)、
  [O'Reilly AI Agents Stack 2026](https://www.oreilly.com/radar/the-ai-agents-stack-2026-edition/)。

兩個 2026 細化(上輪未納,對本案有利):
- **異質模型 + Plan-and-Execute**:「expensive frontier models for…orchestration,
  …small language models for high-frequency execution」;plan-and-execute
  「capable model creates strategy that cheaper models execute」可省成本 ~90%。
  → 我們的**顧問(策略腦)/ 書記+裁剪+收割(執行腦)**天然同構;
  但現配置兩邊都 gpt-5.4-mini。主流答案:**orchestration 腦(顧問)該升**,
  執行腦維持小模型。回應上輪開放問題「顧問模型要不要升」=要(異質配置)。
- **MCP 成標準工具介面**(~80% 生產部署)。本案內部單體暫不相關;記為對外工具未來縫。

**誠實邊界**:AI 趨勢只背書**骨架**(單腦迴圈內規劃 + tool-call 決策 + 確定性
guardrail/validation + 外化 state + 異質模型)。「**收割 pass=事件結束做編碼**」
這個特定選擇來自 **BEI 領域黃金標準**(§2.1),非 AI hype——是 design-by-precedent,
precedent 是職能訪談方法論而非流行架構。兩者獨立成立、互不冒充。

**殘留風險**:讓小模型做議程判斷(開/收事件)可靠度存疑——正是 2026 異質模型主張
「orchestration 用強模型」的理由;配套=顧問升模型 + 確定性 guardrail 兜底。

### 2.6 一手文件真實日期 + 2026 H1 後續核查(維護者三問時效;2026-07 補)

**誠實揭露引用文件日期**(避免「近=可信」的錯覺):
| 文件 | 發布 | 狀態 |
|---|---|---|
| Anthropic Building Effective Agents | 2024-12 | 現行,未撤未改寫 |
| Anthropic Multi-agent research system | 2025-06 | 現行 |
| Anthropic Effective Context Engineering | 2025 秋 | 現行 |
| Anthropic **Writing tools for agents** | 2025-09 | 現行(工具設計,見下) |
| OpenAI Practical Guide / GPT-4.1 guide | 2025-04 | 現行 |

**判準**:架構「原則」文件的時效,看**是否被官方後續撤回/改寫/推翻**,非發布月份。
核查 2026 H1 兩家最近動作 → **核心未被推翻,兩點反被強化**:
- OpenAI(2026-04 Agents SDK 更新;收掉視覺化 Agent Builder+Evals,2026-11-30 下線):
  「For workflows that should continue as code, OpenAI **recommends the Agents SDK**」
  → 官方明推 **code-first**,棄視覺 builder;強化我們程式化做法。
  新 harness「aligned with how frontier models like **GPT-5.4** perform best」
  → 強化「orchestration 腦(顧問)升模型」。
  來源:[TechCrunch 2026-04-15](https://techcrunch.com/2026/04/15/openai-updates-its-agents-sdk-to-help-enterprises-build-safer-more-capable-agents/)、
  [The next evolution of the Agents SDK](https://openai.com/index/the-next-evolution-of-the-agents-sdk/)。
- Anthropic(Code execution with MCP):工具**爆炸**時把 MCP server 當 code API,
  token 150k→2k。**對本案暫不適用**(我們僅 2 個議程工具,非工具爆炸)——記為對外
  工具未來縫,非漏看。來源:[Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)。

**新增該納入的一手資料——Anthropic《Writing tools for agents》(2025-09)**,直接指導
議程工具(open/close_episode)設計:
- 「More tools don't always lead to better outcomes」;少而精、**整合相關操作**
  (範例:給 `schedule_event`,別拆 `list_users`+`list_events`+`create_event`)
  → 議程工具收斂成 open/close_episode 兩顆,不是一堆微決策旗標。
- 「return only **high signal** information back to agents」;別回 UUID,回語意名
  → 議程 artifact 注入「覆蓋地圖」用任務名/事件摘要,不塞內部碼。
- 參數無歧義命名 + 錯誤訊息給「specific and actionable improvements」
  → open_episode 的 target 用候選事件語意標籤;guardrail 回可行動提示(同 verify)。
- 「Building an **evaluation**…systematically measure」→ 議程工具改動要有 eval(persona 重測 + 單元)。

**結論**:引用骨架是 2024末–2025 的**奠基文件**(非最新月份),但經 2026 H1 後續核查
**未被推翻、反被延續強化**;工具設計另納 2025-09《Writing tools for agents》。時效站得住。

### 2.7 AI 訪談業界(2026)

- AI 主持訪談平台(Listen Labs、Outset、CleverX、Userology 等)把
  **depth logic(何時追問 vs 何時換場)**當頭號架構評估題;
  benchmark:AI 場均追問 3.2× 於人類腳本訪談。
  來源:[UserIntuition 平台評估指南](https://www.userintuition.ai/posts/evaluating-ai-moderated-interview-platforms-2026/)、
  [Listen Labs 2026 指南](https://listenlabs.ai/articles/run-ai-moderated-interviews-2026/)。
- 涵義:我們的「單故事鑽十輪」不是顧問壞,是**缺 depth logic 的換場機制**
  (BUG-4 讓飽和訊號永不觸發)。

### 2.8 「不用過時方法」終查:模型世代紀律 + Agent Skills + 本專案適用判定(2026-07 補)

**抓到的真實過時點**:本 repo 全部 prompt 紀律註記「GPT-4.1 指南」,但模型已是
gpt-5.4-mini。OpenAI 官方 GPT-5 世代指南 5/5.1/5.2 之後,**最新為 GPT-5.6 Sol
官方 prompting guidance(2026-07-09 發布;維護者指正後補查)**:
[官方指南](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)。

**GPT-5.6 關鍵主張(對本案有直接影響,T9 依此)**:
- **Outcome-first**:「Describe the destination rather than prescribing every
  step…states **what good looks like**」——prompt 給成功判準+停止條件+約束,
  路徑讓模型選。內部 eval:精簡 system prompt 分數 +10–15%、token −41–66%。
  → 議程設計天然同構:artifact 給覆蓋判準、close_episode 給停止機制;
  顧問 prompt 改寫成「成功判準式」而非「步驟指令式」。
- **刪重複規則**:「repeated statements of the same rule」「examples that do
  not change behavior」要刪;「**conflicting rules can create more instability
  than missing detail**」→ 本 repo「關鍵規則首尾各一份」(GPT-4.1 紀律)
  在 5.6 世代是**反模式**,CONSULTANT_SYSTEM 首尾重複段必須合併成一份。
- **預設更簡潔**:粗放的「至多三句」類指令可能過剪;長度用 `text.verbosity`
  參數當底、任務特定要求寫 prompt。
- 多輪 agentic:「short visible preamble before the first tool call, then
  sparse outcome-based updates…Do not ask the model to narrate routine calls」。
- 模型陣容:5.6 家族為 T10 升級候選(interview 升 5.6 級;select 家族對應
  mini 過考卷再定)。

沿用仍成立的 5.x 通則(5/5.1/5.2 累積,5.6 未推翻):
- **Agentic eagerness 校準**:5 系預設更主動,要「controlled scope and deliberate
  stopping points」「Do not expand the task beyond what the user asked」
  → 顧問 prompt 的「每回合恰一個問題」「離題拉回」紀律要以 5 系語彙重寫;
  議程工具=顯式 stopping/decision points,正合此紀律。
- **預設低冗長** → 長度要求要顯式(顧問「至多三句」仍需,但別再用 4.1 式反覆轟炸)。
- **Schema 嚴格**:「Always follow this schema exactly…set it to null rather than
  guessing」→ 我們受限解碼路線(select_schema strict)正是官方建議形,保留。
- **長流程 compaction**:「Compact after major milestones…not every turn」
  → **事件收割後可壓縮該事件逐字稿為摘要**注入後續 context(episode=天然里程碑);
  v1 先不做,記縫。
- 工具描述「crisply: 1–2 sentences」= Anthropic Writing tools 同款。

**Anthropic 側最新(維護者指示補查)**:
- **Agent Skills**(2025-10 起;[官方工程文](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)、
  [平台文件](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)):
  SKILL.md + YAML frontmatter、**progressive disclosure**(metadata=觸發訊號層,
  內文按需載入)、body<500 行、「description 是給模型的觸發訊號不是人類文件」。
  → 本 repo `app/interview/skills/` 教材格式**正是此模型**;`skills_for()` 的
  確定性掛載=progressive disclosure 的碼實現,**格式不過時**;要修的是
  「載入路斷了」(BUG-2),不是格式。收割 pass 固定掛 behavior-indicator+
  ks-distinction;書記按回合場景掛精簡版。
- Code execution with MCP:工具爆炸時才適用(我們顧問共 5 工具,不適用;記縫)。

**HierTOD 補注**([arXiv 2411.07152](https://arxiv.org/abs/2411.07152)):
「unifies two TOD paradigms: **slot-filling for information collection and
step-by-step guidance for task execution**」+ 階層目標 + mixed-initiative
→ 支持「平面槽序 → 階層議程(事件>任務>槽)」的方向;混合主導=顧問可順著
員工話題走、議程盯住整體覆蓋。

**現有 LLM 介面適用判定(逐條,防「為新而新」)**:
- `select_schema`(json_schema+strict 受限解碼)= GPT-5.2 官方建議形 → **保留**。
- `chat_with_tools` 手刻迴圈(agent_loop.py,12-Factor F8)= OpenAI Agents SDK
  同構(loop until no tool_calls / max iterations)→ **保留**,議程工具直接掛。
- 兩腦分離(顧問說話零格式負擔/書記受限抽取)= 異質模型 plan-and-execute 同構
  → **保留並強化**(顧問升模型)。
- OpenRouter require_parameters / 模型備援 / OTel semconv = 現行主流 → 保留。

---

## 3. 目標架構設計 v4(方向 B 已鎖;細節依 §2 全部先例)

**保留(健康層)**:書記全寬抽取(schema task-enum 歸位)、verify 六查、
`_pending` 審閱流、官方池、裁剪綠字直落、review events。

**收斂(生病層;形依 §2.4 大廠先例修正——不做獨立 planner 呼叫)**:
1. `next_gap` 線性梯子 + 散落驅動條件 → **議程收斂到顧問迴圈內**:
   (a)覆蓋地圖+事件狀態+飽和/疲勞/預算訊號由碼確定性計算,
   當**議程 artifact 注入 context**(取代 ledger_summary 的單行 hint);
   (b)顧問獲得 enum 鎖死的**議程工具**(如 open_episode(target∈候選集)/
   close_episode →觸發收割),在既有 chat_with_tools 迴圈內呼叫,
   service 確定性執行——決策可 log 可測,主路徑零新增 LLM 呼叫;
   (c)確定性 guardrail 兜底:連 N 輪無新槽收益自動收割、硬預算強制換場
   ——guardrail 是後衛不是駕駛(Anthropic effort-scaling 同型)。
2. **議程單位:任務 → 事件(episode)**:顧問一次深挖一個具體事件(BEI/STAR);
   一個事件天然橫跨多任務=效率來源(一次餵多任務的 details+P+K+S)。
3. **新增事件收割 pass(coder pass)**:事件結束時對該事件逐字稿片段跑編碼——
   起草 P(STAR 句式,behavior-indicator 教材注入)、補 K/S、掛回被觸及各任務,
   走既有 op→verify→`_pending`。= BEI 事後編碼搬到每事件即時做;P 從此有結構性的家。

**多任務跨越問題的答案**(維護者提問):議程與抽取分層——
「一次一個」約束的是**顧問注意力**(一個事件),不是**內容歸屬**;
書記/收割全寬歸檔(已運作:session 330a0bed 第 25 輪一句話分掛兩任務)。
planner 每次換場對**更新後**的覆蓋地圖重規劃,順帶填掉的不重問
(= MultiWOZ over-answering 標準處理)。

以上為摘要;完整設計如下。

### 3.1 命名表(維護者授權重整;概念名=繁中,模組名=英文)

| 概念 | 模組/符號 | 說明 |
|---|---|---|
| 事件 | `episode` | BEI 訪談單位:一件實際發生過的事(非任務、非槽) |
| 議程 | `agenda.py`(新) | episode 狀態機 + 議程 artifact 組裝 + guardrail 訊號 |
| 覆蓋 | `coverage.py`(自 ledger.py move-only 拆出) | 純函式:iter_tasks/blocks_missing/share_sum/coverage/can_finish/checklist/slots 門檻 |
| 收割 | `harvest.py`(新) | 事件收割 pass(BEI coding 的即時版);「收割員」 |
| 顧問 | `consultant.py`(留) | 策略腦;+議程工具指引、GPT-5 世代紀律改寫 |
| 書記 | `scribe.py`(留) | 執行腦;逐回合全寬機會性抽取(+P 機會性規則) |
| 裁剪 | `curation.py`(留) | 官方任務 quote-backed 直落(修 BUG-1) |
| 撿漏 | `backstop.py`(留) | 確定性週期 sweep(不動) |
| 態度 | `attitudes.py`(留) | 收尾整體編碼(不動) |
| 帳本 | ~~ledger.py~~ | **退役拆分**:純計算→coverage;狀態/訊號→agenda;`next_gap` 梯子**整支退役** |

命名原則:BEI 術語 coding 因與本案「位置碼/官方碼」語義相撞,取 harvest(收割)。

### 3.2 回合序 v4(取代 v3;service.run_turn)

```
① 載入(doc/turns/profile/官方池)
② coverage 重算(純函式)→ agenda artifact 組裝(episode 狀態+覆蓋地圖+訊號)
③ 裁剪縫(保留;無任務+有參考時 quote-backed 直落;含 BUG-1 修=落地前 seed 骨架)
④ 顧問 chat_with_tools(READ 工具 + 議程工具):
   - open_episode(target)→ service 記 episode 狀態(不動文件)
   - close_episode(reason)→ service 記帳 + 本回合尾排收割
⑤ 書記 pass(照舊,全寬;SCRIBE_SYS 補 P 機會性規則)
⑥ 收割 pass(僅當本回合 close_episode 或 guardrail auto-close):
   事件逐字稿片段+被觸及任務 → 受限 schema 批次(P/K/S/槽)→ land_ops → `_pending`
⑦ backstop sweep(照舊,週期)
⑧ 議程收帳:episode 收益評定(BUG-4 修:progressed=「episode 相關路徑本回合有無新值」;
   curation 落地計入 curation 縫)+ 疲勞/預算訊號
⑨ widget/寫回/稽核(照舊)
```

### 3.3 議程 artifact(注入顧問 context;取代 ledger_summary 單行 hint)

高訊號、語意名、byte 穩定區塊(快取紀律同 §T13):

```
<議程>
事件:進行中「<員工的話起的名>」第 n 輪|無(建議開新事件)
本事件已觸及:任務名A、任務名B
覆蓋地圖(壓縮):已餵飽 k/20;空白區(前5):任務C(全空)、任務D(缺P)…
訊號:[飽和|疲勞|輪數 n/40](僅列成立者)
候選事件方向(前3,語意標籤):「任務C 最近一次實際發生」…
</議程>
```

規格:任務以**語意名**呈現(Anthropic Writing tools:不回裸碼/UUID);
20 任務地圖壓縮成分組計數+前 N 名單(GPT-5.2:smallest high-signal)。

### 3.4 議程工具(2 顆;掛進 CONSULTANT_TOOLS 同一迴圈)

- `open_episode(target: enum<候選事件方向 id>, note?: str)`
  「開始深挖一個具體事件。當你要請員工講『最近一次實際發生的事』時呼叫。」
  service:記 `agenda_state.episode={target, opened_seq}`;回確認+該方向空缺摘要。
- `close_episode(reason: enum<saturated|covered|user_shifted>)`
  「當這個事件已問透(細節/標準/驗收都有了)或員工明顯換話題時呼叫;系統會把
  事件內容編碼進文件。」
  service:記帳+排收割;回收割結果摘要(落了幾筆待審)。
工具描述 1–2 句(GPT-5.2/Anthropic 同款紀律);錯誤回可行動訊息(同 verify 風格)。
決策=tool call ⇒ 稽核表 `tool_calls` 原生可 log 可 eval(§2.4 骨架第 2 件)。

### 3.5 收割 pass(harvest.py;P 的結構性的家)

- 輸入:episode 期間員工逐字稿(turn 範圍由 episode 狀態界定)、被觸及任務清單
  (書記本事件落點∪open_episode target)、官方池、教材(behavior-indicator、
  ks-distinction 固定掛載=progressive disclosure 的「按需全文」層)。
- 輸出:受限 schema(mirror 書記形):`draft_indicator`(STAR 句式,quote 逐字)
  /`record_task_pool`/`record_task_custom`/`set_slot`/`none`。
- 落地:records_to_ops → land_ops(verify 六查、dup 由⑤查擋)→ `_pending` 綠字。
- 模型:select(執行腦,小模型);失敗 fail-open(不擋回合,漏的下事件/收尾再收)。
- 與書記分工:書記=逐回合**機會性**(員工明說標準時逐字掛);收割=事件級**系統性**
  (從敘事起草)。兩者同走 verify,重複由 dup 檢查擋。

### 3.6 Guardrails(確定性;後衛不是駕駛)

| 訊號 | 條件(碼算) | 動作 |
|---|---|---|
| 事件飽和 | episode 開著、連 2 輪書記對 episode 相關路徑零新值 | artifact 注入「該收了」;第 3 輪 **auto-close+收割** |
| 該開沒開 | 無 episode、連 2 輪顧問未 open | artifact 強化提示(附候選) |
| 硬預算 | 輪數 ≥ TURN_BUDGET | suggest_finish(既有) |
| 寫入 | 全部 op | verify 六查(不變) |

STALL_K/is_stalled 概念保留但**掛到 episode 粒度**;attempts 舊語義隨梯子退役。

### 3.7 模型配置(異質,§2.5)

- interview(顧問/策略腦):**升 frontier 級**;型號過 T11 考卷再定(OpenRouter;
  若換 Anthropic 系,adapter H1 cache_control 必處理)。
- select(書記/裁剪/收割/態度/執行腦):維持 mini。

### 3.8 零件遷移對照(重構安全網:一 task 一 commit;green-before==green-after)

| 現行 | 動作 | 去向 |
|---|---|---|
| ledger.next_gap 梯子+ONBOARD/CURATION 縫常數 | 退役/搬家 | 縫判定進 agenda;梯子刪除 |
| ledger 純函式群 | move-only | coverage.py |
| ledger attempts/held/boundary/fatigue | 改造 | agenda.py(episode 粒度) |
| consultant.ledger_summary/_ONBOARD_STEER | 重寫 | agenda artifact(agenda.py 組裝) |
| consultant CONSULTANT_SYSTEM | 改寫 | +議程工具指引;GPT-4.1 參照→GPT-5 世代 |
| scribe SCRIBE_SYS | 小改 | +P 機會性規則(規則 9) |
| curation/verify | 小修 | BUG-1(seed 骨架/頂層容器特判)+處女文件測試 |
| service.run_turn | 大改 | 回合序 v4 |
| tools/agent_loop/backstop/attitudes/slots/docpath/diff/schema_utils | 不動 | — |
| sessions.ledger_state | 沿用欄位 | 內容改 agenda_state 形(episode/attempts v2);無 DB migration |
| （新)harvest.py | 新建 | §3.5 |

web 端:零改動(`_pending` 渲染/✓✗ 早已泛化;T8 驗證過)。
文檔:實作同 commit 更新 `docs/design/interview-engine.md`(§4 回合序、§5 載體、
不變量、退役禁令加 next_gap 梯子)。

## 4. L1 止血清單(與方向 B 無關,遲早要修;暫記不動)

1. BUG-1:落地前 seed `ocs_content.ocu_units` 骨架(或 verify 頂層鏈缺席=空容器)
   +「處女文件」測試。
2. BUG-2 短效:SCRIBE_SYS 加 P 規則 + 書記注入 behavior-indicator 教材
   (長效歸宿=coder pass,見 §3)。
3. BUG-4:progressed 改「被提示 gap 對應路徑本回合有無新值」;
   curation 落地計入 curation 縫進帳。

## 5. 開放問題收斂紀錄(2026-07-14 討論定案)

1. 事件邊界:**混合**——確定性訊號提示、顧問 close_episode 決定、guardrail
   第 3 輪 auto-close 兜底(§3.6)。
2. 收割觸發:**每事件結束一次**(每回合貴+重複;僅收尾太晚=態度 pass 老路)。
3. planner 頻率:**問題消解**——無獨立 planner,決策=顧問迴圈內 tool call(§2.4)。
4. 動態槽(2412.16943):**v1 不採**(固定 11 槽是契約);記未來縫。
5. 研究待補:**已補**(§2.6–§2.8:GPT-5.2 指南、Agent Skills、HierTOD、
   2026 H1 兩家後續動作)。
6. 事件逐字稿 compaction(GPT-5.2 里程碑壓縮):v1 不做,記縫(§2.8)。
7. 顧問升哪顆模型:留 T11 考卷驗收定(§3.7),不在本檔裁。
