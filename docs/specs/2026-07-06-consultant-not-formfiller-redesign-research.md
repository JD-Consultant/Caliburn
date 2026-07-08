# 「顧問而非填表機」互動重設計研究紀錄(根本範式修正)

> 觸發:真人試訪 profile 6d01cdd7 逐字稿。維護者判定:引擎「一欄一欄問、一任務一任務、
> 不會思考、答不出不幫忙、沒問 OPKS」=填表機器人,**員工何必不自己填**。這不是 bug,是
> 互動範式錯。北極星=[[north-star-replace-jd-consultant]](取代顧問)。本紀錄診斷+找權威+提重設計。
> 紀律:重設計會**部分翻案 ADR 0023 的「每回合 LLM 選指令詞彙=前景」**,另開 ADR;
> 但保留 0023 無狀態回合、0024 受限解碼信任軸、0025 共編權限——搬到背景,不丟。
>
> **狀態(2026-07-06):討論中,未定案、ADR 未開。** §3 的「顧問+書記(分離)」經第二輪討論
> 演進為 **§7 的「統一 agentic 顧問(寫入走守衛工具)」**——以 §7 為現行主張;§3 保留為演進脈絡。

## 1. 診斷(逐字稿實據,profile 6d01cdd7)

引擎照 `SLOT_DEFS` **順序 march 11 格**:頻率(seq2)→比重(4)→耗時(6)→數量(8)→觸發(10)
→材料(12)→工具(14)→協作(16)→等待(18)→例外(20)→標準(22)→產出(24)。病徵:

| 逐字稿 | 病 |
|---|---|
| seq1「我要說甚麼?」→ 直接問頻率 | **不引導**:員工一開場就迷路,顧問無視 |
| seq5「這不能算時間」;seq13/15「不用」 | **不幫忙**:答不出/不對題,不給例子不換路,硬凹或收垃圾(seq16「工具=不用」) |
| seq28/32 把氣話「成品阿我不是說了」塞進**等待瓶頸**槽,重複兩次 | **萃取與對話焊死**→歸錯槽、重複 |
| seq29-34「然後?下個任務是哪個?我不是說完了」→ 一直回「補齊了可往下走」卻沒真的換 | **advance 死結**:單任務焦點卡住 |
| 整場只碰 11 細項槽,**K/S/A/O/P 一個沒問** | **漏掉 OPKS**——職務說明書的核心;而我們手上有該職類標準 OPKS 池 |

**根因**:我逼 LLM **每回合輸出填槽/追問指令**——那本身就是填表思維。真顧問不是逐格想,
是**對話**,結構化在腦中/事後。焊死對話與萃取 = 機器人感的來源。

## 2. 權威依據(職能訪談方法 + LLM agent 架構,交叉收斂)

### A. 行為事件訪談 BEI / 職能建模(祖師爺方法)
- McClelland(1973/1998)+ Spencer & Spencer《Competence at Work》+ McBer/Korn Ferry/Workitect。
- 核心:**引出「實際情境的完整故事」**(具體行為/想法/actions),重「行動背後的思考」;
  **職能(K/S/A)是事後從故事編碼**,不是一欄一欄問。→ 對照本案:該讓員工「講他怎麼做」,
  顧問從故事**萃取** OPKS,而非審問 11 格。
- Zhang et al.(2026,arXiv 2602.13084)《Competency Modeling with LLMs》:用**既有職能庫
  提議**回給受訪者確認/精修("uses these libraries to propose competencies back to
  interviewees for validation, rather than purely interrogating");答不出 →「offering
  examples, clarifying frameworks」;流程=訪談→逐字稿→**萃取編碼**→框架比對→回驗。

### B. LLM 對話 agent 架構(對話 vs 萃取分離)
- JAMIA Open(2025)自動問卷:**對話 agent 產逐字稿 + 另一個 LLM 事後萃取**——原話
  「two-stage approach allows the conversational agent to **sound natural without needing to
  enforce structured response formats**」;萃取用 self-consistency(重複 5 次取眾數)達 98%。
  警示:純對話會留模糊缺口 → **背景要追覆蓋、回饋顧問**該補哪。
- LLM-agent 綜述:goal-oriented 系統把**對話生成**與**結構化萃取**分成不同元件是主流;
  萃取小模型(schema-guided)專職填槽,對話模型專職自然互動。

**四源(BEI、競模 LLM、JAMIA、agent 綜述)同指**:對話(自然、引故事、從框架提議、會幫忙)
與萃取(背景、受限解碼、事後結構化)**必須分離**。

## 3. 重設計 v1:「顧問 + 書記」雙角色(Consultant + Scribe)

> ⚠️ **已由 §7 的統一 agent 取代**(第二輪討論)。保留此節記錄「為何一度想分兩個腦」的脈絡:
> 當時假設 OPKS 池靜態塞 context;§7 戳破——知識要動態查(indexer),顧問其實是 agent。

前景=顧問(員工只看到這個);背景=書記(隱形結構化)。**信任軸不動,只是搬到背景。**

```
員工訊息
 → ① 顧問(強模型,自由文字,不受 schema 綁):
      吃【職類標準 OPKS 池 + 任務清單 + 目前文件 + 覆蓋薄弱處(書記回饋)】,
      像資深顧問那樣:引故事、跨任務串、從池子「提議」標準 OPKS 給確認、答不出給例子、
      該收尾就收尾。**只輸出自然對話**(立即回給員工,體感即時)。
 → ② 書記(受限解碼,背景,可略慢/批次):讀近窗逐字稿,萃取→更新文件:
      11 細項槽 + OPKS(K/S/A 從池 id enum 鎖=零幻覺;O/P 敘述+quote 溯源),
      走既有 executor(通道分流/quote 驗證/建議層,ADR 0024/0025 原封不動)。
 → ③ 覆蓋追蹤:書記算「哪些任務/OPKS 還薄」→ 下一回合餵給顧問當導引(不當欄位丟給員工)。
```

**逐一對應維護者的抱怨:**

| 抱怨 | 雙角色怎麼解 |
|---|---|
| 一欄一欄問 | 萃取隱形;員工只跟顧問自然對話 |
| 沒有人與人訪談 | 顧問引故事、會串、會提議,像真人 |
| 侷限一個任務 | 顧問可跨任務走;書記把萃取歸到正確任務,覆蓋跨全表追 |
| 答不出不提醒 | 顧問給例子/從池子提議(BEI「offering examples」) |
| 沒問 OPKS | 書記萃取 K/S/A/O/P;顧問從標準池提議(我們有 knowledge pack) |
| 員工幹嘛自己填 | 顧問加值:懂框架、提標準職能、串接、起草;員工只need講故事 |

## 4. 重用既有資產(不打掉重練;守「別破壞架構」)

| 既有 | 新角色 |
|---|---|
| `select_schema`+`turn_output_schema`+受限解碼(0024) | **書記**的萃取路(K/S/A pool enum) |
| executor 通道分流/quote 驗證/建議層(0025) | 書記的確定性 apply(原封不動) |
| 無狀態回合、狀態=DB+文件(0023) | 保留;回合內多一次「顧問生成」呼叫 |
| knowledge pack(選職類=OPKS 池,ADR 0021) | 顧問「提議標準 OPKS」+ 書記 K/S 的 enum 來源 |
| model 分層(0026) | 顧問=強模型自由文字(無需 strict);書記=select 受限解碼 |

**變的只有**:前景從「LLM 每回合選指令」→「顧問自然對話」;萃取移到背景;新增 OPKS 萃取+
覆蓋追蹤。指令詞彙表從「前景互動語言」降為「書記內部萃取 schema」。

## 5. 選項與取捨

- **A(建議)雙角色分離**:對話×萃取徹底分離。最貼四源權威;顧問真自然。成本=每回合 2 呼叫
  (顧問先回、書記後跑,可不阻塞)。
- B 單 agent「故事優先」:仍一個模型,但改成先引敘事、只在任務邊界萃取。較省一次呼叫,
  但對話與 schema 仍同源→易回退成填表(JAMIA 已證純對話+無分離會漏缺口)。→ 不選。
- C 維持現狀加補丁(補 OPKS 問句+help):**治標**;維護者已否決「填表感」,補丁改不掉範式。→ 不選。

## 6. 待決 / 下一步(進 ADR + plan)

1. 開 **ADR 0027**:互動範式=顧問+書記(部分翻案 0023 §決定「指令詞彙=前景」;保留其餘)。
2. 覆蓋模型:OPKS 要納入 `gate`/覆蓋(擴 `slots.py` 或新 `coverage.py`);黃金範本當尺。
3. 顧問「提議標準 OPKS」的 pool 接線(survey/deep 通吃;呼應維護者「選職類/任務也交 LLM」)。
4. 校準:sim 擴「迷路員工/答非所問/氣話」persona(真人試訪證實這類最會踩雷),量「顧問有無幫忙」。
5. 延遲預算:顧問回覆優先顯示,書記背景更新文件(體感=邊聊邊長,對齊 ADR 0020 混合載體)。

## 7. 第二輪討論(2026-07-06 續):框架評估 → agentic 重定向 → 統一 agent

> §3 的「顧問+書記(分離)」演進為**統一 agentic 顧問(寫入走守衛工具)**。演進與證據如下。
> **本輪維護者指示:先記錄、繼續討論——尚未定案,ADR 0027 待對齊後開。**

### 7.1 該不該上編排框架?——不(權威 + 我們判準)
- Anthropic《Building Effective Agents》:「**start by using LLM APIs directly**」;框架
  「obscure the underlying prompts... harder to debug」、「tempting to add complexity when a
  simpler setup would suffice」;「**add complexity only when it demonstrably improves outcomes**」。
- 2026 掃描:LangGraph 最成熟但重,且把我們**剛退役**的狀態耦合(checkpointer)請回來
  (ADR 0023 刻意 12-factor 外部化);CrewAI/AutoGen checkpointing 弱;OpenAI Agents SDK/
  Google ADK 綁 stack;Pydantic AI / Claude Agent SDK 輕、typed。
- 判準:狀態已外部化、信任軸要 prompt 可稽核、少依賴好 debug → **手刻直用 SDK**;
  LangGraph/CrewAI/AutoGen **否決**。

### 7.2 但「顧問會查資料」= 它就是 agent(維護者戳破)
- 原判「固定 workflow」錯了:知識在 indexer 後、要**動態查**——`occupations:search`(查職類)、
  `occupations/{code}/tasks`(官方任務)、`.../competencies`(該職類 OPKS 池)、`items:match`
  (白話反查任務)、`tasks:search`;皆已封在 `KnowledgePort`。
- 「LLM 動態決定查什麼、何時再查」= Anthropic 對 **agent** 的定義;2026 agentic RAG 最佳實務:
  知識是活服務、相關性事前未知時,動態檢索大幅贏靜態塞 context——正是我們。
- → 顧問應為 **agentic-retrieval agent**(讀工具動態查 indexer)。

### 7.3 再進一步:寫入也給 agent 當工具(維護者提議)→ 統一 agent
- 提議:別分兩個腦;把「確定性書記寫入」做成 agent 的**寫入工具**,一個腦邊談邊記。
- 關卡=零幻覺守得住嗎?權威(2026):一般 tool calling 95–99%(schema 當提示);
  **但 `strict:true` 的 tool calling 拿到與 `response_format` 同級的受限解碼保證**(enum 不出池);
  且 function schema **逐請求傳** → 動態把該任務 OPKS 池 enum 塞進寫工具**可行**。
- **實測(2026-07-06 spike,scratchpad `spike_strict_tool.py`,OpenRouter / gpt-4.1-mini)**:
  strict 寫工具 + 對抗提示(誘記 K99 / DROP_TABLE / 量子運算 / 中文 / 混合合法非法)
  → **5/5 零逃逸 PASS**。細節:**強制 `tool_choice` 時它會硬記一個合法 id** → 實作須
  `tool_choice=auto`(讓它能「不寫」),否則為填而填。

### 7.4 深度評估:統一 agent vs 需求(R1–R10)

| 需求 | 統一 agent | vs 分離書記 |
|---|---|---|
| R1 最完整 / R2 抓漏 | 一個腦邊懂邊記,無「顧問→書記」落差 | **更好** |
| R3 OPKS 覆蓋 | 讀池→提議→寫,一氣呵成 | 相當 |
| R4 目錄零幻覺 | strict 寫工具**實測零逃逸** + executor 池成員 backstop | 相當(已驗) |
| R5 quote 溯源 / R6 共編 / R7 單寫路 | 寫工具=executor(quote 驗/human_touched 分流/upsert_draft) | 相當 |
| R8 不填表 | 自由文字對話 + tool call 側效(**非強制結構**) | **更好** |
| R9 稽核 / R10 動態查 | tool call=稽核軌跡;讀工具查 indexer | 相當 |

結論:strict 寫工具守得住零幻覺,合一反而**高保真 + 自然**;後者正解掉原機器人感根源
(逼每回合吐結構化指令)。JAMIA「分離對話與結構」的顧慮由 tool calling 另一路滿足
(對話仍自由文字,結構走旁路)。

### 7.5 信任紀律(不可退讓)
1. **寫工具 = 現有 executor**(通道分流 / quote 驗證 / 預算 / 覆蓋);模型提議、executor 處置。
2. 零幻覺雙保險:strict enum(生成時)+ executor 驗池成員(處置時,ADR 0024 defense-in-depth)。
3. **`tool_choice=auto`**——讓 agent 能選「不寫」。
4. 覆蓋追蹤仍在(背景算哪些薄,餵 agent),別全靠它自己記得。
5. 寫工具快 / 非阻塞——回覆優先顯示、文件隨後長(ADR 0020 邊聊邊長)。

### 7.6 框架再算(有工具後)→ 仍微傾手刻
- 特殊需求:池 enum **每回合隨任務動態變** → tools 陣列逐請求重建,**raw OpenAI SDK 最順**
  (spike 即如此);Pydantic AI / OpenAI Agents SDK 的裝飾器工具對動態 per-turn enum 反而卡。
- 加上單一 gateway + 全透明 + 零新依賴 → **手刻 tool loop 藏六邊形 port 後**;Pydantic AI 備選。

### 7.7 RC1–RC5 續用(非白做)
executor 守衛 → 寫工具實作(RC1 槽 enum → 寫工具 param enum);RC3 顧問守則 → agent system
prompt;RC5 強模型 → 會用工具的 agent 模型;quote 驗證 / 建議層 / 覆蓋全續用。**只打掉
「每回合吐指令」的前景**,信任軸整套搬進工具。

### 7.8 仍在討論 / 待 de-risk(未定案)
- `tool_choice=auto` 下「該寫才寫、該閉嘴才閉嘴」的準度 + 一輪多工具的延遲(未實測)。
- 框架最終取捨(手刻 vs Pydantic AI)——維護者若想試 Pydantic AI 再評。
- 統一 agent 是否保留一個「背景覆蓋 backstop pass」(JAMIA self-consistency)當增強。
- **survey 段**(LLM 幫選職類/任務)是否併入同一 agent(讀工具本就能查職類/任務)。
- 定案後才開 **ADR 0027** + plan。

## 8. 第三輪:三隊平行研究彙整 → v1 架構定形(2026-07-06)

三隊 subagent(架構 / 框架 / 可靠性)平行深挖 2025–26 權威,**高度收斂**。要點:

### 8.1 架構:單執行緒、單一 writer、agentic——但「對話」與「寫入」要解耦
- 兩派權威(Cognition《Don't Build Multi-Agents》+ Anthropic 多 agent 研究系統)**都同意**:
  單使用者、長、有狀態、共享演化文件、寫入相依 = **多 agent 受害區**。**不拆多 agent。**
  MAST(Berkeley,150+ traces)實證多 agent 頭號失效是 inter-agent 對不齊(結構性、非 prompt 可救)。
- 但**別把「談話 + 嚴格結構化寫入」塞進同一次 generation**:《Let Me Speak Freely?》證格式限制
  降推理 10–15% 且致 **satisfice**(記個淺欄位就跳)——正是田野失敗(從不 elicit 職能)。
  **解法 = NL→Format 兩步:對話純自然語言,萃取另一 pass。**
- **收斂設計**(仍單執行緒、單 writer、共享全逐字稿,**非**多 agent):
  - (A) **Interviewer 輪**:純自由文字對話,READ 工具 inline(動態查 indexer 職類/任務/OPKS 池/
    match);讀覆蓋帳本挑「最缺」的下一題;**不背負 strict 寫入**,才能自然探深。
  - (B) **解耦萃取 pass**:另一支結構化呼叫讀逐字稿 delta,提 guarded writes(strict enum + quote)
    交**現有 executor** 處置;可非同步、不擋回覆。
  - (C) **覆蓋帳本 + 完成閘門 + 卡關前進**(見 8.3)。
- 佐證:tacit-knowledge 論文(2507.03811)單 agent + 自我批判 + 覆蓋評分達 **94.9% recall**;
  COLING 2025 **dynamic slot** > 固定槽 march;AI Conversational Interviewing 證 LLM 天生
  **under-probe**(88% 該追未追)——探深要機制逼,不能只靠 prompt。

### 8.2 對「統一 agent 寫入工具」的修正(誠實)
維護者提議、spike 已驗「strict 寫工具零逃逸」——**機制留用**;但研究指出**不該在對話那次
generation 內 `tool_choice=auto` 邊聊邊嚴格寫**(降質 + satisfice)。→ 寫工具機制移到 (B) 解耦
萃取 pass 執行,不與共情對話同一次生成。**READ 工具仍 inline**(agentic 檢索,維護者論點成立)。

### 8.3 可靠性:最高槓桿是「確定性覆蓋帳本 + 閘門」,不是更多 LLM
- 進度從模型腦袋搬到**外部確定性狀態**(Anthropic context engineering note-taking;
  Magentic-One Task/Progress Ledger)。per-interview 帳本:task ×(11 細項 + OPKS 5 子塊),
  每槽 ∈ {empty, asked, recorded, n/a-有理由}。
- **完成閘門**:`advance_task`/`finish_interview` 在有必填空槽時**被 executor 擋**(除非正當 n/a)
  → 修「漏類別 + 早停」。
- **卡關前進**:per-topic turn budget + stall 偵測(K 回合沒填新槽)→ 標 attempted-insufficient
  交 backstop、強制前進 → 修「死鎖」(Magentic-One stall→replan;OpenAI stop conditions)。
- **grounded 寫入 + 相關性檢查**:每筆值綁支持引文,且驗「這句是否在回答此欄位」(非離題旁白)
  → 修「抱怨旁白記錯欄位」(Meta CoVe;Anthropic CitationAgent 分離 pass)。

### 8.4 backstop(Q4 裁決):v1 做,但收窄
- 回合/訪談邊界、便宜模型、只答兩題:(a) 完整性(有無員工發言其實回答了空的必填槽卻沒被記)
  (b) 歸屬(每個已寫值有無支持、未離題);**只提案給單一 writer,不並行直接寫**
  (Cognition「intelligence not actions」;JAMIA 兩階段 98%;Anthropic Completeness/Citation rubric)。
- **延後**:全文 self-consistency 多數投票(N× 成本,只對 backstop 標記的高價值低信心欄位如
  OPKS 選擇性用)、對話期間 live critic(加延遲、破一致性;DeepMind:無外部訊號的自糾可能反傷)、
  非同步多子代理。

### 8.5 框架(Q2 裁決):手刻 over OpenAI SDK → OpenRouter,藏 `LlmPort` 後
- 四約束(動態 per-turn enum / OpenRouter / 稽核透明 / hexagonal+pydantic)手刻全拿滿;
  Anthropic《Building Effective Agents》明挺直呼 API(「obscure the underlying prompts」是框架壞處)。
- **Pydantic AI = 唯一有原則的未來升級門**(`prepare`/`prepare_tools` 把 dynamic-enum 當一等公民、
  原生 OpenRouter、pydantic 契合;採用鎖 `>=1,<2`)。
- **不用 OpenAI Agents SDK**(預設 tracing 上傳 OpenAI 伺服器 = 多租戶稽核紅旗;動態 enum 逆框架);
  **不用 Claude Agent SDK**(跑 OpenRouter 要疊 LiteLLM proxy 兩次翻譯;per-turn enum 要每回合重建
  in-process MCP server)。
- 手刻 gotchas(streaming tool-call delta 拼裝、逐 provider tool 可靠度、**保留確定性 enum 驗證**、
  tool_call_id 對回、業務層 retry + `max_tool_iterations`、OpenRouter attribution header、loop 關
  adapter 後)——進 plan。

### 8.6 v1 範圍裁決
**進 v1**:(A)(B)(C) 單執行緒迴圈 + grounded 寫入 + 窄 backstop + 手刻 loop。
**延後**:self-consistency 全面、live critic、多子代理、Pydantic AI 遷移。
**RC1–5 續用**:executor 守衛→(B) 寫工具;RC3 顧問守則→(A) interviewer prompt;RC5 強模型→agent
模型;quote 驗證/建議層/覆蓋帳本雛形→(C)。**待開 ADR 0027 + plan。**

## 9. 第四輪:寫入 / 核准 / onboarding 的 UX 定案(2026-07-06→07)

延續 §8 的 v1 架構,補齊「AI 改動怎麼進文件、選擇怎麼呈現、onboarding 怎麼併」。

### 9.1 官方 = 參考,寫入分兩通道(非天花板)
職責/任務/OPKS/類別皆可與官方不同、更細。寫入分兩條,由**員工真實工作**決定走哪條:
- **對上官方** → 從池記(strict enum,零幻覺),帶官方 provenance。
- **對不上/更具體/官方沒有** → **自訂**(自由名字 + quote 溯源 + 人審),空 provenance。
`items:match` 只是提示。「零幻覺」= **宣稱官方的必真官方**,不是「全部得是官方」。

### 9.2 萃取跨任務(丟掉單一 focus 鎖)
一句話可橫跨多任務;萃取 pass 用 `items:match` + 文件任務清單把**每片段歸到正確任務**,
一句 → 多筆寫入不同任務。模糊 → 掛最像 + 標記交 backstop/對話釐清;清單外 → 自訂任務。
修掉舊版 `focus.task_path` 單鎖(那正是「氣話被塞進等待瓶頸」的成因)。

### 9.3 onboarding 併入同一 agent
選職位/選任務**不是另一階段,是對話開場**:agent 用讀工具(`occupations:search`/
`occupation_tasks`)提議、員工確認。**agent 可從全空白起跑**(拿掉「必須先選任務才能開訪談」)。
手動〔選職類〕〔選任務▾〕**保留為平行路徑**(想自己翻官方的人用)。

### 9.4 選擇用清單、敘述用對話
「從固定選項挑」(職位/任務/從官方池挑 OPKS)= **清單勾選**,AI **預先推薦勾好、排序**,
員工調整(decision=widget 原則,沿用現成 picker UI);敘述性內容才用對話。

### 9.5 核准模型 = 風險分層 + 批次審(2025–26 大廠/框架現行共識)
三家一致(OpenAI *Practical Guide to Building Agents* 2025;Anthropic Claude Code / **Plan Mode**;
LangChain/LangGraph HITL 2026):**按風險分層,只攔高風險/不可逆**——LangGraph rule of thumb
「**interrupt on irreversible, high-blast-radius actions only — not on every step**」;低風險/可逆
**自動放行**;用 **Plan-Mode 式批次審**(整段計畫一次審)治核准疲勞。落到我們:
- 低/可逆(細項槽、高信心官方項)→ 自動放行 = **就地標記 + 整段批次審 + 可 undo**。
- 高/影響結構(選職位、加自訂任務/職責、AI 沒把握的歸類)→ **明確核准(選單/清單)**。
- **一切可審、可退、可改、marked、留痕 = 永遠成立**(「人審」的真義,靠 suggest-mode + undo
  達成,**非逐筆攔**;逐筆攔會致核准疲勞→亂蓋章→錯誤↑)。
- **修正 ADR 0025**:不再「人沒碰過就直改」;改風險分層,AI 一律走可審提議層(高信心低風險
  可自動放行,但仍可逆可審)。

### 9.6 三元件澄清(信任靠「不是 LLM」的那個)
**2 個 LLM**(顧問=對話+查詢;書記=萃取)+ **1 個確定性程式**(覆蓋帳本/完成閘門/卡關偵測
——故意非 LLM,進度不交給會忘會亂的模型)+ **1 個便宜 backstop LLM**(收尾補漏/查歸屬)。

## 10) 第五輪:三角度獨立驗證(2026-07-08;維護者問「這大架構可以嗎?」)

前四輪是「邊設計邊找依據」;本輪反向:把定下來的大架構丟給三個獨立角度檢驗
(同類商業產品/大廠工程共識/科學方法論),找確證、反例、與「別人有我們沒想到的」。

### 10.1 角度一(產業):AI 主持訪談平台 2024–26 已商業化,模式與我們同構
Listen Labs / Outset / Strella / Wondering 等平台做的就是「AI 訪談真人 → 結構化洞察」。共同模式:
- **指南驅動,完成不交給 AI 自判**:Outset 官方(2025-10)——AI 在 discussion guide 框架內
  適應、「不自由發揮」;問完了沒**由指南決定**,AI 不自行終止。= 我們的覆蓋帳本。
- **主持與分析分離**:Outset「訪談中即時標記主題/情緒,結束時原料已結構化」;Listen Labs
  的分析(主題聚類/報告)是獨立 Research Agent。= 顧問/書記分離。
- **動態追問是核心賣點**:兩家都「依回答校準追問」,明確偵測 **hedging 語言**
  (「maybe」「I'm not really sure」)當追問觸發;研究員可調 probe 深度/風格。
- **引文出處**:Listen Labs——每個結論標籤「可回溯到精確時間戳+逐字引文」。= quote provenance。
- **人審保留**:Outset「研究員設計研究+詮釋發現」;Strella「研究員逐場審核後才付參與者費」。
- 我們未採:語音/視訊/情緒訊號(Ekman)——文字先行,記為未來縫。

### 10.2 角度一(學術):AI 訪談員論文,正反兩面都驗證「確定性帳本」
- **正面同構**——Stanford《Generative Agent Simulations of 1,000 People》(2411.10109):AI 訪談員
  照 AVP 半結構化腳本,在「結構與時間限制內」動態生成追問(腳本控推進、LLM 管追問)。
- **反面教材**——《AI Conversational Interviewing》(2410.01824):訪談員=單一 GPT-4、指南放
  prompt、「何時下一題」**全由 LLM 自判、無狀態機**→最大失敗=**漏追問(88% 追問違規來自
  AI)**;作者自陳關鍵缺口「缺乏明確狀態機制確保題目順序與追問觸發」,並建議上線前
  **pre-testing**。我們的帳本 + interview_sim eval 正是補這兩個洞。
- 2025–26 系列(Mic Drop or Data Flop 2509.01814;Scaling Up 2606.20064;SparkMe 2602.21136):
  **coverage/depth 已是標準評估軸**;對話蒐集與分析分 pass 是通行架構。

### 10.3 角度二(工程):2025-10 之後大廠共識未變,未見反例
- OpenAI **AgentKit**(2025-10)+ Agents SDK:「從單 agent 開始,必要才多 agent」不變;
  Guardrails 為模組化安全層(input/output/**tool** guardrails)= 我們的守衛寫入通道。
- Anthropic《Effective context engineering》(2025-09):「**分離、乾淨上下文的驗證者優於
  自我批判**」「確定性評分放進 check-runner」→ 直接支持 backstop 獨立 pass + 帳本非 LLM。

### 10.4 角度三(抽取品質):「格式限制傷推理」有反方——但我們兩邊都安全
dottxt《Say What You Mean》反駁《Let Me Speak Freely》:做對的受限解碼(區分 constrained
decoding 與 JSON-mode、prompt 給足資訊)不輸自由生成甚至更好;學界仍拉鋸。**含意**:爭議只
影響「同一個 LLM 同時推理+格式化」的設計;我們顧問全自由、書記只做簡單分類(enum 挑選,
非多步推理),不押任何一方贏。

### 10.5 角度三(方法論):iCAP 官方方法與我們同族;態度靠「從故事編碼」
- **iCAP 官方**(勞動部勞動力發展署;《職能基準發展指引》,工研院執行):職能分析方法族=
  DACUM、關鍵事件法(CIT)、行為事件訪談(BEI)、職能訪談;OCS 能力內容=O/P/K/S/A。
  我們「先聽故事→事後編碼」= 官方同族方法的正統做法。
- **職務分析權威實務**:多方法並用(訪談+關鍵事件+任務清單+**觀察**);觀察能抓「員工不會
  主動講」的部分。AI 顧問沒有觀察 → 用**官方標準當觀察替代品**主動提議(「同職類的人通常
  也做 X,你有嗎?」),這正是 READ 工具的方法論定位。
- **CTA**(Brown/Power/Gore 2024,*Organizational Research Methods*)+ Critical Decision Method:
  引出專家內隱知識的當代同儕審查方法——用「困難/非典型事件」當探針(餵 OPKS 問法設計)。
- **NLP 估 KSAO**(*J. of Business & Psychology*,2022):由任務敘述文字推 KSAO 重要性已有實證
  → 支持書記從故事推 K/S、顧問再確認的路。
- **態度(A)**:方法論共識=**不直接問**(社會期許偏誤),從行為事件敘述中編碼/行為錨定。

### 10.6 判定 + 收編三條新機制
**大架構成立**:四組件+風險分層+官方=參考+出處綁定,三角度全對齊;且拿到反面教材
(2410.01824 無狀態機的失敗)與正面同構(Stanford 訪談員、商業平台 guide-driven)雙重印證。
業界有、我們原本沒明說的,收編:
1. **probe 深度/風格可配置**(至少 prompt 常數起步,別寫死)。
2. **hedging 偵測當追問觸發**(「可能」「不太確定」「大概」→ 顧問 prompt 的明確追問規則)。
3. **上線前 pre-testing 制度化**= interview_sim eval 保留並隨 v2 擴充(coverage/depth 兩軸)。

## 11) 第六輪:放行標準的他山之石(2026-07-08;帳本「怎樣算補完」的權威做法盤點)

維護者要求「先看別人怎麼定完整,再自己想」。盤了五家(三個政府、一個顧問業方法、
一群 AI 訪談平台),原文出處見來源 §11 節。

### 11.1 iCAP 官方《職能基準發展指引》(勞動部/工研院;**同框架,最有約束力**)
自 PDF 全文抽出(80 頁;p35/37/48/49/73/76/77):
- **結構**:主要職責→工作任務,建議 **2 層**;每任務掛 O/P/K/S(+A 在基準層合併呈現)。
- **P(行為指標)**:官方定義「評估是否成功完成任務之標準;**需具體描述在何種任務情境下,
  有哪些應有的行為或產出**」;寫法**參考 STAR(Situation/Task/Action/Result)或 ABCD**;
  審核要求「具體清楚描述行為表現」且能對應職能級別;驗證時**每條 P 評重要性+難易度(必要)**。
- **O(工作產出)**:關鍵產出(過程+最終),**儘量有形交付**(書/文件/圖表);**「若該項任務
  僅有行動或操作性質之工作成果,則不必列出工作產出,建議將相關成果列於行為指標描述中」**
  → O 有官方認可的合法 n/a 規則。
- **K**:該領域可應用的「原則與事實」。**S**:hard skills(認知/技術操作)+ soft skills
  (社交/溝通/自我管理),軟技能**從共通目錄挑**(S07 品質導向、S12 時間管理…)。
  K/S 應**對應到行為指標**(避免重複、防孤兒項)。
- **A(態度)**:「內在動機及行為傾向」;**官方共通目錄 A01–A14**(主動積極/正直誠實/親和力/
  持續學習/自我管理/自信心/追求卓越/團隊意識/彈性/壓力容忍/應對不確定性/好奇開放/
  冒險挑戰/謹慎細心),**挑選+可自行增列**;因各任務態度多共通,**合併呈現於基準下方**。
- **停止/品質**:BEI「訪談足夠人數直到**資料飽和**(資料重覆且未產生新資訊)」;**三角檢核**;
  審核指標自我檢核表(9 指標/21 要求條件,**全數符合**才能申請認證);驗證=請實務工作者
  重新評項目**重要度與正確性**;職能項目 >15 項改用重要度排序驗證。
- 其他特質(非 K/S/A)因教育訓練難改變,**不納入基準**(招募時自行考量)。

### 11.2 O*NET(美國勞動部;統計門檻模型)
- 每職業任務清單由**在職者(≥15 人)評重要性+頻率**,可 write-in 新任務;
- **Core Task = 相關性 >67% 且平均重要性 >3.0**;10–66% 相關= Supplementary;
- 可轉用:任務層帶「重要性/頻率」兩個便宜評分;核心/次要之分。

### 11.3 Spencer/McClelland BEI(顧問業標準;iCAP 也引用)
- 每受訪者 **5–6 個完整行為事件**;事件要 **STAR 完整**(情境/任務/行動/結果+當時想法)
  才算證據——**形容詞不是證據,完整故事才是**;職能由事後編碼,不直接問。
- 建模規模(8–12 傑出+8–12 一般)是「建基準」用;單員工訪談可轉用的是**證據單位=完整事件**。

### 11.4 AI 訪談平台/論文(2025–26)
- 完成=**指南覆蓋**(guide-driven,AI 不自判);評估軸=**coverage+depth**;
  停止=飽和(重覆無新資訊);probe 深度可配置。

### 11.5 IfATE(英國政府;職業標準=職責×KSB)
- **雙向映射完整性**:每條職責配上最相關的 KSB;**每條 KSB 至少屬於一條職責**(禁孤兒);
  一份標準常見 20–40 條 KSB;用語精確規則(「including a,b,c」=必考;「for example」=舉例)。

### 11.6 對帳本規格的初步翻譯(待維護者裁決,先不定案)
- P:每任務 ≥N 條,每條=情境+行為/產出(STAR 式),各綁引文;可加重要性追問。
- O:有形交付優先;操作型任務可合法 n/a(理由=「操作型,成果併入 P」)。
- K/S:各 ≥N 條且**對應到某條 P**(IfATE 禁孤兒 + iCAP 對應行為指標);軟技能/態度走目錄池
  (strict enum 的天然好戲;A01–A14 池小而通用)。
- A:文件層合併、非逐任務;從故事**編碼**而非直接問(§10.5),池選+證據引文。
- 停止:任務層飽和規則(連續 K 次追問無新槽)+ 覆蓋閘門;收尾=員工對重要性/正確性
  快速再確認(= iCAP 驗證步的單人版)。

## 12) 第七輪:實作藍圖逐件對權威(2026-07-08;「怎麼實現」的依據驗證)

架構層已驗(§10);本輪驗**實作層**。新入檔兩個來源:Anthropic《Writing effective tools
for agents》(2025-09-11)與 **12-Factor Agents**(HumanLayer/Dex;24k stars,手刻 agent
工程的當前實務共識)。實作藍圖七件,逐件對應:

| # | 實作件 | 權威依據 |
|---|--------|----------|
| 1 | 手刻工具迴圈(顧問腦;while + 工具分發 + 上限) | Anthropic BEA(直呼 API;框架藏 prompt 是壞味);12-Factor **F2 own your prompts / F8 own your control flow**;OpenAI function-calling 官方即此形 |
| 2 | READ 工具設計(查職類/任務/職能/白話反查) | Anthropic Writing tools:**search 優於 list**、回語意名稱非裸 ID(回 `ocu_name+code`)、合併工作流(考慮 occupation-brief 一呼帶齊)、錯誤訊息可操作、top_k 截斷預設 → **直接當 plan 的工具驗收清單** |
| 3 | 書記=獨立受限解碼呼叫(NL→guarded writes) | 12-Factor **F1 NL→tool calls / F4 tools are just structured outputs**(命令是資料,executor 才執行);OpenAI strict + 內部 spike;解耦依據 §8 |
| 4 | 帳本=DB 狀態+純函式;回合無狀態重建(ADR 0023 留用) | 12-Factor **F5 unify execution & business state / F12 stateless reducer**;Magentic-One ledger;Anthropic context engineering(狀態外部化);反例 2410.01824 |
| 5 | 大事跳選單(人的核准=一個工具呼叫) | 12-Factor **F7 contact humans with tool calls**;風險分層 §9.5(OpenAI/Anthropic/LangGraph) |
| 6 | 三個小而專的角色,不做萬能 agent | 12-Factor **F10 small, focused agents**;Cognition;Anthropic「分離乾淨上下文的驗證者」 |
| 7 | 蓋序(帳本→書記→顧問→核准→複查)+ 上線前 eval | Anthropic tools 文章的 eval 法(while-loop runner;accuracy/工具呼叫數/token 指標)= interview_sim 擴充方向;2410.01824 pre-testing;repo 紀律 green-before==green-after |

**誠實殘留(工程裁量,非教義)**:書記與顧問「序列 vs 並行」——平台實務是分析與對話並行
(Outset 即時標記);v1 先**序列**(簡單、顧問看得到最新帳本),延遲用 sim 量測後再決定;
並行化記未來縫。F9(compact errors into context:守衛拒絕要精簡回饋給書記重試)與 F3
(own your context window:顧問 context 由我們手組)已隱含在設計,plan 時落實。

## 13) 第八輪:反向最終檢驗(2026-07-08;維護者指正「先看人家怎麼做,不是拿我們設計找佐證」)

方法改為**反向**:先中立重建「同類系統的完整端到端流程」與「大廠 agent 標配組件」,
再拿我們的設計對差(雙向:他們有我們沒有的=缺口;我們有他們沒有的=需自證)。

### 13.1 中立重建:別人的完整流程
**AI 訪談平台端到端**(Outset 2026 指南、NN/g《AI-Moderated Interviews: If, When, and How》、
Listen Labs):①設計(目標+討論指南,AI 輔助生成;可調 moderator 風格/probe 深度/skip
logic)→ ②邀請+**開場揭露**(告知是 AI、資料權利、取得同意;NN/g:**公開揭露反而提升
完成率與品質**)→ ③訪談(指南內動態追問、澄清模糊回答、**低品質/詐欺偵測**)→
④**研究員監看**(前幾場人工盯場、指南可在途調整)→ ⑤綜合(主題聚類、洞察連回引文、報告)。
**大廠 agent 標配**(OpenAI/Anthropic/LangGraph/Microsoft 現行):model+tools+instructions
+guardrails+orchestration(單→多)+HITL+**evals**+**observability/tracing**。
**安全基線**(OWASP Top 10 for LLM Apps 2025):LLM01 prompt injection 居首(指令與資料同
通道);防禦=權限最小化+敏感操作 HITL+輸出約束+**max iterations 上限**+縱深防禦。
**職業分析專業**(iCAP/O*NET/BEI):**多信息源三角檢核**(O*NET ≥15 在職者;BEI 8–12 傑出
+8–12 一般;iCAP 專家會議+三角檢核)+ 實務工作者驗證步。

### 13.2 對差結果
**吻合(骨架全中)**:指南/帳本驅動完成、對話與抽取分離、追問為核心、引文溯源、人審、
風險分層 HITL、飽和停止、無狀態狀態管理、evals——四層依據(大廠指南/商業平台/論文/
政府方法論)交叉印證,無結構性反例。
**缺口(他們有、我們沒設計,收編)**:
1. **開場揭露+同意+時長預期**(NN/g 最佳實務)→ v1 開場白就能做,加。
2. **低品質回應偵測**(平台標配;=我們清單上「擺爛/亂答」)→ 設計:顧問行為(換問法/
   舉例)+ 標記交人審,不硬闖。
3. **顧問使用者(B 端)監看/在途調整**(前幾場盯場、調重點)→ roadmap;v1 至少可即時
   看逐字稿(已有 view)。
4. **多信息源三角檢核**——與專業實務的**最大方法論差距**:我們 v1=單員工自述+顧問人審。
   誠實定位:人審=第二來源的最小版;路線圖=主管確認 pass、多員工同職務合併(O*NET/BEI
   的聚合本義)。**不擋 v1,但要寫進 ADR 的 limitations。**
5. **自建 observability/audit**(大廠標配;多租戶 B2B 更要;且我們棄用 SDK tracing 就得
   自己補)→ plan 項:每回合 LLM/工具呼叫、守衛判定落庫(turns/writes 已有雛形,補齊)。
6. **Prompt injection 硬化**(OWASP LLM01):員工輸入=資料非指令,寫進 system prompt+
   測試;天生緩解已有(工具唯讀、寫入 strict enum+人審、無對外動作、max iterations)。
**我們有、共識沒有(需自證,已證)**:確定性帳本強於「指南跟隨」(2410.01824 失敗+
Magentic-One);strict enum 零幻覺寫入(產出是受治理文件,非主題報告);官方基準檢索
grounding(領域護城河)。**刻意偏離**:純文字先行(無語音/情緒,未來縫)。

### 13.3 最終判定
骨架**成立且無需結構調整**;本輪收編 6 件(1、2、6 進 v1;3、5 進 plan;4 進 ADR
limitations+路線圖)。設計討論至此可收斂 → ADR 0027(含 limitations)+ bite-size plan。

## 14) 帳本門檻草案 v1(2026-07-08;依黃金範本校準 §11 五家標準;待維護者裁決)

黃金範本(`2026-07-05-golden-sample-software-tester.md`)已內建分層與門檻雛形
(core 12 槽全套/淺掃 4 槽;比重×頻率建議深問級別;A 從公版池挑+訪談印證;
「覆蓋率自檢=可機器檢查的完成度門檻雛形」§附-4)。草案=範本 × §11 合成:

- **任務兩小題(必問)**:頻率+工作比重(O*NET);**全文件比重加總=100%**(確定性檢查)。
- **深問分層**:比重×頻率自動建議 core/淺掃(人可改;範本 7 任務 4 core)。
  - **core**:12 槽全套(含靈魂槽:等待瓶頸/例外處理/完成標準),每槽填或合法 n/a。
  - **淺掃**:4 槽(頻率/比重/產出/完成標準)。
- **OPKS(core 任務)**:O ≥1 有形產出(📘或⊕;操作型可 n/a 併入 P,iCAP 規則);
  P=職責層 ≥1 條「指標+目標值」(範本 §6);K、S 各 ≥2 條且掛在該任務(禁孤兒),
  公版引用優先、自訂帶引文;**A=文件層一次,2–4 項從 A01–A14 池挑 + 每項一句訪談印證**。
- **停止**:同任務連續 2 次追問無新槽 → attempted-insufficient、換題(資料飽和)。
- **完成閘門**:core 12/12、淺掃 4/4(n/a 計入)、每職責 P≥1、A≥2、比重=100%。
- **收尾**:員工對比重表+關鍵槽快速再確認(iCAP 驗證步單人版)。

## 15) 問句庫 v1(2026-07-08;plan T8 研究關卡產物——顧問 prompt 的唯一素材來源)

### 15.1 訪談總體形(BEI,McClelland 1998)
- **短故事式**:請員工講「具體發生過的事」,不問一般性意見;**成功與失敗事件都要**。
- **記者式非引導追問**:繞著「你**做**了什麼/**說**了什麼/當下**想**什麼」挖,不給選項、
  不帶預設(引導式問句是 BEI 大忌)。
- 開場句式:「跟我說說你平常做什麼」→「最近一次做○○是什麼時候?從頭說一次那天的情況」。

### 15.2 CDM 探針中譯表(Crandall/Klein/Hoffman《Working Minds》2006;Hoffman et al. 1998)
多輪回溯同一事件,逐類探:
| 探針類 | 中文問法(素材) | 主要餵 |
|---|---|---|
| 線索 cues | 「你當時**看到/聽到什麼**,就知道要動手/不對勁?」 | K、P |
| 知識 knowledge | 「這個判斷需要知道什麼?**新人會漏看什麼?**」 | K |
| 目標 goals | 「那個當下你最想先保住什麼?」 | P、A |
| 選項 options | 「當時還有別的做法嗎?為什麼選這條?」 | S、K |
| 依據 basis | 「你怎麼知道這樣做會有效?」 | K |
| 經驗 experience | 「這靠的是哪次學來的?」 | K、S |
| 假想差異 | 「如果讓剛到職的人接手,他會卡在哪?」 | K、S(內隱) |
| 錯誤 errors | 「這一步最容易出什麼錯?出了怎麼救?」 | exceptions、S |
| 時間壓力 | 「趕的時候你會省哪步、絕不省哪步?」 | standards、A |
| 輔助 aiding | 「有什麼工具/表單幫你?沒有它會怎樣?」 | tools、S |

### 15.3 OPKS 各塊引出策略(iCAP p43 官方大綱句式為基底)
- **O 產出**:「這件事做完,**交出去的東西**是什麼?(文件/圖表/紀錄)」;答「就做完了」
  (操作型)→ 確認後合法 n/a,成果併入 P/完成標準(iCAP 規則)。
- **P 行為指標**:從故事收斂:「所以在(情境)時,你會(行為),做到(程度)——這樣寫
  對嗎?」(STAR 式回述確認;**指標由 AI 從故事草擬、員工確認**,不叫員工自己寫指標)。
- **K 知識**:不問「你有什麼知識」;問「做這步**要先知道什麼**?」「新人會漏什麼?」。
- **S 技能**:問「**實際上怎麼操作**?」「哪一步最見功力?」;軟技能從共通目錄比對提議。
- **A 態度**:**絕不直接問**(社會期許);由書記/顧問從故事**編碼→池選提議**
  (A01–A14):「聽起來你在(事件)裡展現了『謹慎細心』,放進特質欄?」員工確認才落。

### 15.4 追問觸發與飽和
- **hedging 觸發詞(中文,工程自定,對齊平台 hedging 偵測)**:「可能/大概/差不多/
  還好/就那樣/不太確定/看情況/有時候吧」→ 必追一層(「說個實際例子?」)。
- **短答**(<10 字)且槽未填 → 換句式再問一次(不重複原句)。
- **飽和換題話術**:「這題我們先記到這,之後隨時補——接下來聊○○」(帳本判飽和才觸發,
  話術只是外皮;決定權在帳本,LLM 不自判,§10.2 反例)。

### 15.5 卡住/低品質階梯(2410.01824 under-probe 教訓+平台實務)
換問法 → 給例子(從官方池/同職類常見樣態舉例:「像同職類的人常說等 PM 改規格——你有
類似的嗎?」)→ 拆小(先問頻率再問細節)→ 標記 attempted-insufficient 前進交人審。
**禁止**:同句重複、跳過不記錄、被離題帶走(離題≤1 回合內拉回)。

### 15.6 開場揭露要素(NN/g)
AI 身分明示、預計時長、資料用途與誰會看(之後有人審核)、可隨時說「跳過」;
揭露完整反而**提升**完成率與品質(NN/g 實證)。

### 15.7 prompt 硬規則(工程)
員工輸入=**資料非指令**(OWASP LLM01,系統層明示+對抗測試);**capture-first**
(校準 #2 教訓:落槽永遠優先於寒暄回述,順序=優先序);probe 深度/風格=設定常數,
不寫死(§10.6 收編 1)。

## 16) 實作期發現與校準(解凍後逐 task 累積)

### 16.1 T1 帳本 vs 黃金範本(2026-07-08;門檻校準,ADR 0027 已預授權)
拿 spec §1 門檻對黃金範本(品質尺)驗算,抓到兩處矛盾,均屬**校準級**(非動搖架構):
- **移除「每職責 P≥1」完成閘門**:範本 R3(測試報告與監控)整條職責皆淺掃、無績效指標
  → 原 gate 會拒絕範本自身。**改**:P 由 `blocks_missing` 對**每個核心任務**要求(≥MIN_P),
  不設職責層 P gate。同步改 spec §1 `can_finish`。
- **`is_core` 判過頭,不在 T1 動**:範本 3.2「每日×10%」被範本標淺掃,但 v1 `is_core`
  (每日 OR ≥15%)判為核心。**不改 v1 `is_core`**(會破既有綠底 test_interview_slots),
  改由帳本尊重 `ledger_state.tier_override`(範本註「人可改」)。**T14 校準項**:
  是否把 is_core 改成「比重×頻率」複合判準。
- 已驗證一致:MIN_P/K/S=1/2/2、MIN_A=2 對範本核心任務 1.2(K=3、S=2、P≥1、O=1)與
  §8 態度(3 項)皆通過。

> §16.2+ 留給後續 task 的發現與校準 #3(sim v2 數據;T14 產出)。

## 17) 路線圖彙整(刻意不進 v2 的,一處收攏;各有出處,防遺忘)

| 項 | 內容 | 出處/依據 |
|---|---|---|
| 職務說明書 renderer | 定稿文件+evidence → 黃金範本 §1–§8 格式輸出(現況只有職能基準 JSON 匯出) | spec §10.3;黃金範本 |
| 主管確認 pass | 員工版定稿後給直屬主管快檢(第二信息源) | §13 缺口 4(O*NET/BEI/iCAP 三角檢核) |
| 多員工合併 | 同職務多份訪談聚合(聚合本義=O*NET ≥15 人) | §13 缺口 4;ADR 0027 limitations |
| B 端監看/在途調整 | 顧問使用者看進行中訪談、調重點(前幾場盯場) | §13 缺口 3(NN/g/平台實務) |
| 語音/情緒訊號 | 語音訪談、情緒偵測(Ekman) | §10.1(Listen Labs);文字先行 |
| 書記並行化 | 抽取與對話並行(降延遲) | §12 誠實殘留;T14 延遲數據裁決 |
| self-consistency | 高價值低信心欄位 N 次投票 | §8.4 延後項 |
| Pydantic AI 遷移 | 唯一有原則的框架升級門(prepare/prepare_tools) | §8.5;ADR 0024 |
| 信任漸進調權 | 依接受率放寬自動放行範圍 | ADR 0025 未來縫 |

## 來源
- McClelland (1998) *Identifying Competencies with Behavioral-Event Interviews*, Psych. Science. https://journals.sagepub.com/doi/10.1111/1467-9280.00065
- Spencer & Spencer, *Competence at Work*;Workitect BEI/競模最佳實務。https://workitect.com/PDF/Competency-Modeling-Best-Practices.pdf
- *Exploring a New Competency Modeling Process with LLMs* (2026). https://arxiv.org/pdf/2602.13084
- *Automated survey collection with LLM-based conversational agents*, JAMIA Open (2025). https://academic.oup.com/jamiaopen/article/8/5/ooaf103/8306995
- Anthropic, *Building Effective Agents*(workflow vs agent、直接用 API、只在 demonstrably 改善才加複雜度). https://www.anthropic.com/research/building-effective-agents
- *Agentic Retrieval-Augmented Generation: A Survey*(2501.09136;動態檢索 vs 靜態 context). https://arxiv.org/abs/2501.09136
- Structured Output vs Tool Calling(2026):一般 tool calling 95–99%(schema 當提示);`strict:true`
  拿到與 structured output 同級的受限解碼(enum 零幻覺)保證。https://www.buildmvpfast.com/blog/structured-output-llm-json-mode-function-calling-production-guide-2026
- OpenAI Function Calling / Structured Outputs(`strict:true` 對 tool args 的 enum grammar 強制). https://developers.openai.com/api/docs/guides/function-calling
- 內部 spike:strict tool-calling enum 零逃逸(OpenRouter/gpt-4.1-mini,5/5 PASS;方法見本紀錄 §7.3)。
- **§8 第三輪(架構/可靠性/框架)**:
  - Cognition — *Don't Build Multi-Agents*(share-context / single-writer). https://cognition.ai/blog/dont-build-multi-agents
  - Cognition — *Multi-Agents: What's Actually Working*(intelligence-not-actions、generator-verifier). https://cognition.com/blog/multi-agents-working
  - Anthropic — *How we built our multi-agent research system*(+90.2% 但 15× tokens;CitationAgent 分離 pass). https://www.anthropic.com/engineering/multi-agent-research-system
  - Anthropic — *Effective context engineering for AI agents*(note-taking / compaction / context rot). https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
  - Microsoft Research — *Magentic-One*(Task/Progress Ledger、stall→replan). https://www.microsoft.com/en-us/research/articles/magentic-one-a-generalist-multi-agent-system-for-solving-complex-tasks/
  - *Why Do Multi-Agent LLM Systems Fail?*(MAST/MASFT,Berkeley). https://arxiv.org/abs/2503.13657
  - *Let Me Speak Freely?*(格式限制降推理 10–15%,NL→Format 兩步). https://arxiv.org/abs/2408.02442
  - *Leveraging LLMs for Tacit Knowledge Discovery*(單 agent 自我批判,94.9% recall). https://arxiv.org/abs/2507.03811
  - *Career Interview Dialogue System — Dynamic Slot Generation*(COLING 2025). https://arxiv.org/abs/2412.16943
  - Meta — *Chain-of-Verification Reduces Hallucination*. https://arxiv.org/abs/2309.11495
  - *Self-Consistency Improves CoT*(ICLR 2023). https://arxiv.org/abs/2203.11171
  - DeepMind — *LLMs Cannot Self-Correct Reasoning Yet*(自糾需外部訊號). https://arxiv.org/abs/2310.01798
  - OpenAI — *A Practical Guide to Building Agents*(stop conditions). https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf
  - Pydantic AI — *Advanced Tools*(`prepare`/`prepare_tools` 動態 schema). https://pydantic.dev/docs/ai/tools-toolsets/tools-advanced/
- **§9 第四輪(核准模型,2025–26 現行共識)**:
  - OpenAI — *A Practical Guide to Building Agents*(工具風險分級、高風險才暫停/升級人). https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/
  - OpenAI — *Guardrails and human review*(approval=暫停等核准/拒絕). https://developers.openai.com/api/docs/guides/agents/guardrails-approvals
  - Anthropic — *Claude Code*(權限 always-allow/needs-approval、**Plan Mode** 批次審治疲勞). https://www.anthropic.com/product/claude-code
  - LangChain / LangGraph — *Human-in-the-Loop*(按風險分層、「interrupt on irreversible, high-blast-radius only — not every step」). https://docs.langchain.com/oss/python/langchain/human-in-the-loop
- **§10 第五輪(三角度獨立驗證)**:
  - Outset — *What Actually Happens in an AI-Moderated Interview?*(2025-10-08;guide 決定完成、
    即時標記與對話分離、hedging 偵測、研究員詮釋). https://outset.ai/resources/blog/what-actually-happens-in-an-ai-moderated-interview
  - Listen Labs(AI 主持+獨立 Research Agent 分析;結論綁時間戳+逐字引文). https://listenlabs.ai/
  - Strella(chat-first AI 訪談;研究員逐場審核後才付費). https://www.strella.io/
  - Park et al. — *Generative Agent Simulations of 1,000 People*(2024-11;AI 訪談員=AVP 半結構化
    腳本+限制內動態追問). https://arxiv.org/abs/2411.10109
  - *AI Conversational Interviewing: Transforming Surveys with LLMs*(2410.01824;LLM 自判進度無
    狀態機→88% 追問違規來自 AI;建議 pre-testing). https://arxiv.org/abs/2410.01824
  - *AI Conversational Interviewing: Scaling Up Semi-Structured and In-depth Interviews*(2026-06;
    coverage/depth 評估軸). https://arxiv.org/abs/2606.20064
  - *Mic Drop or Data Flop?*(2025-09;AI 語音訪談員的資料適用性評測). https://arxiv.org/abs/2509.01814
  - OpenAI — *Introducing AgentKit*(2025-10;Guardrails 模組化安全層). https://openai.com/index/introducing-agentkit/
  - dottxt — *Say What You Mean: A Response to 'Let Me Speak Freely'*(受限解碼做對不輸自由生成;
    爭議只涉「推理+格式化同一次生成」). https://blog.dottxt.ai/say-what-you-mean.html
  - 勞動部 iCAP — 職能分析方法簡介(DACUM/CIT/BEI/職能訪談)與《職能基準發展指引》(工研院).
    https://icap.wda.gov.tw/Knowledge/knowledge_method.aspx
  - Brown, Power & Gore — *Cognitive Task Analysis: Eliciting Expert Cognition in Context*,
    Organizational Research Methods(2024;內隱知識引出). https://journals.sagepub.com/doi/10.1177/10944281241271216
  - *Evaluating an NLP Approach to Estimating KSA … Job Analysis Ratings*, J. of Business and
    Psychology(2022;文字→KSAO 重要性). https://link.springer.com/article/10.1007/s10869-022-09824-0
- **§11 第六輪(放行標準他山之石)**:
  - 勞動部勞動力發展署《職能基準發展指引》(工研院執行;80 頁 PDF,O/P/K/S/A 撰寫規範、
    STAR/ABCD、A01–A14 態度目錄、資料飽和、審核指標檢核表).
    https://icap.wda.gov.tw/ap/get_file.php?t=download&c=%E8%81%B7%E8%83%BD%E5%9F%BA%E6%BA%96%E7%99%BC%E5%B1%95%E6%8C%87%E5%BC%95.pdf&e=20221026143138.pdf
  - O*NET Resource Center — Task Statements / Data Collection(Core Task 門檻:relevance>67%
    且 importance>3.0;≥15 在職者;importance+frequency 量表). https://www.onetcenter.org/dictionary/30.2/excel/task_statements.html
    與 National Academies *A Database for a Changing Economy*(O*NET 資料蒐集審查). https://nap.nationalacademies.org/read/12814/chapter/7
  - McClelland (1998) / Spencer BEI 實務(每受訪者 5–6 事件、STAR 完整故事為證據單位、
    8–12 傑出+8–12 一般). https://journals.sagepub.com/doi/10.1111/1467-9280.00065
  - IfATE / GOV.UK — *Developing an occupational standard*(duty↔KSB 雙向映射、每 KSB 至少
    屬一 duty、20–40 KSB、including/for example 用語規則). https://www.gov.uk/guidance/developing-an-occupational-standard
- **§12 第七輪(實作藍圖對權威)**:
  - Anthropic — *Writing effective tools for agents*(2025-09-11;search>list、語意名稱、合併
    工作流、可操作錯誤、截斷預設、eval 迴圈與指標). https://www.anthropic.com/engineering/writing-tools-for-agents
  - HumanLayer(Dex)— *12-Factor Agents*(24k stars;own prompts/control flow、tools are
    structured outputs、unify state、stateless reducer、contact humans with tool calls、
    small focused agents). https://github.com/humanlayer/12-factor-agents
- **§15 問句庫**:
  - Crandall, Klein & Hoffman — *Working Minds: A Practitioner's Guide to Cognitive Task
    Analysis*(MIT Press, 2006;CDM 多輪回溯+探針法原典). https://books.google.com/books/about/Working_Minds.html?id=ZfcVGsJlyhMC
  - Hoffman, Crandall & Shadbolt — *Use of the Critical Decision Method to Elicit Expert
    Knowledge*, Human Factors(1998;CDM 方法學案例). https://journals.sagepub.com/doi/10.1518/001872098779480442
  - (BEI=McClelland 1998、iCAP 訪談大綱 p43、NN/g 揭露、OWASP——見前列)
- **§13 第八輪(反向最終檢驗)**:
  - Nielsen Norman Group — *AI-Moderated Interviews: If, When, and How to Use Them*(AI 揭露
    +同意最佳實務、前幾場人工盯場、在途調整指南). https://www.nngroup.com/articles/ai-interviewers/
  - Outset — *AI Moderated Research Platforms: Honest Guide (2026)*(端到端流程、probe/style
    可調、低品質偵測). https://outset.ai/almanac/ai-moderated-research-platforms-honest-guide-(2026)
  - OWASP — *Top 10 for LLM Applications 2025*(LLM01 prompt injection;縱深防禦、敏感操作
    HITL、max iterations). https://owasp.org/www-project-top-10-for-large-language-model-applications/
