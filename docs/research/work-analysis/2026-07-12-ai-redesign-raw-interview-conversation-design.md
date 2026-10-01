# AI 主導訪談 / 資訊蒐集對話設計 — 權威做法研究紀錄

- 研究日期:2026-07-12
- 目的:為「AI 顧問訪談受訪者、產出專業文件」系統設計對話層。
- 方法:以業界通用詞彙(conversation design、AI interviewer、mixed-initiative dialogue、
  elicitation、probing、laddering、structured interview)廣掃,挑一手資料深挖。
- 來源紀律:僅收大廠官方設計準則、AI 訪談產品原廠一手資料、模型廠官方、CHI/CUI/CSCW 等頂會論文
  (2024–2026)。每條標 URL + 日期。**孤證 / 二手已明示**。

> 給設計者的一句話結論:文獻的共識是「**結構化議程 + 逐題節奏 + 有節制的自適應追問**」。
> 最反覆出現的失敗模式不是 AI 追問太少的能力問題,而是**追問時機(timing)與節奏**——過早、過機械、
> 不肯閉嘴、不肯離題、收尾像機器人。設計對話層的槓桿主要在「何時停、何時讓路、何時覆述」,而非「能問多深」。

---

## Q1. 提問策略:一次一題 vs 多題;開放 vs 封閉;深度 vs 廣度

**結論**:業界準則一致主張**一次只問一題**、以**開放題開場再用封閉題收斂**;AI 訪談實證顯示深度
(probing)與廣度(coverage)是真實的取捨,而**主流架構用「固定 main questions 保證廣度 +
自適應 follow-up 補深度」來同時吃兩端**。

**關鍵證據**
- Google Conversation Design(官方,developers.google.com,持續維護):明確要求「**Don't keep
  speaking after asking a question. Don't overwhelm the user with options**」、「present only one
  question at a time rather than multiple options simultaneously」。依 Grice 合作原則四準則
  (Quantity / Quality / Relevance / Manner),「saying too much is as uncooperative as saying too
  little」。 URL: https://developers.google.com/assistant/conversation-design/learn-about-conversation
- OpenAI Realtime Prompting Guide(官方,2025):建議「**2–3 sentences per turn**」、
  「Prefer bullets over paragraphs」、以 sectioned prompt 降低模型負荷。
  URL: https://developers.openai.com/cookbook/examples/realtime_prompting_guide
- AInterviewer(arXiv 2606.20588,AI-led qualitative interview 平台,2026):架構把 **main
  questions(設計者預定、每場必問以保證 cross-comparability)** 與 **probing agent(依 guide + 受訪者
  回答生成 follow-up)** 分離。等於「廣度由固定題保證、深度由追問補」。
  URL: https://arxiv.org/html/2606.20588v1
- Outset(AI 訪談產品官方 blog,2026):設計者可指示 AI「probe generally, probe in specific ways,
  or not probe at all」;probing 由 sentiment / enthusiasm / hedging 等 linguistic cue 觸發;深度可
  開到「up to 10 smart follow-ups per question」(稱 Abyss mode)。顯示深度是**可調參數**而非固定值。
  URL: https://outset.ai/resources/blog/what-actually-happens-in-an-ai-moderated-interview

**設計建議**
- 對話層強制「一 turn 一題」;禁止 compound question(把兩個問題塞一句)。
- 每個議程節點配一組:1 條必問開放題(保證覆蓋)+ 允許 0–N 條自適應 follow-up(補深度),深度上限為
  **可調參數**(見 Q2 建議 2–3 層)。
- 開放題開場("能不能描述一下…")→ 視回答用封閉題定錨("所以是 X 對嗎?")。

---

## Q2. 追問(probing)的時機、深度、與 laddering

**結論**:追問應由**明確訊號觸發**(回答太短 / 模糊 / hedging / 意外或矛盾),而非每題都追;
深度以 **laddered probe(逐層往下)** 為技法,但**主流建議 2–3 層即止**;實證的頭號問題是**時機**
(過早追問破壞流程),而非追問能力。過度追問傷 rapport。

**關鍵證據**
- AI Conversational Interviewing(arXiv 2410.01824,LLM 當自適應訪談者的大型 survey 實驗):
  指令為「ask follow-up questions when a respondent gives a **surprising, unexpected or unclear
  answer**」,用中性 probe("Why is that?"、"Could you expand on that?"、"Can you give me an
  example?")。實測 AI 反而**追問不足**:違規案例中 88% 是 AI「該追沒追」。顯示 LLM 的預設傾向是
  under-probe,需刻意調校。 URL: https://arxiv.org/html/2410.01824
- Harnessing AI in Qualitative Research(arXiv 2509.12709,半結構訪談 AI 生成 follow-up,17 位研究
  員,2025):**「Timing emerged as the primary weakness」**;多數抱怨 AGQ 來得太早、打斷既定提問序;
  受訪偏好「mid-to-late interview insertions」(先鋪陳再深挖);建議「**holding mechanisms**」把好但
  時機不對的問題留到後面。核心洞見:「**Question quality and communication skills operate as coupled
  conditions**」——好問題時機錯照樣失敗。 URL: https://arxiv.org/html/2509.12709v1
- Probing in qualitative research interviews: Theory and practice(Tandfonline,2023,Gorden 式 probe
  理論):probe 可 **laddered**(對上一個 probe 的回答再 probe,逐層往下探到自傳式敘事的隱藏層);
  probe 兩大功能:(1) 激勵受訪者、(2) 導向 relevant/complete/clear 的回答。
  URL: https://www.tandfonline.com/doi/full/10.1080/14780887.2023.2238625
- Laddering(QRCA 2025-09-16;UXmatters 2009,均署名業界實務):laddering 從 attribute → functional
  consequence → personal value 逐層爬升,揭露決策背後的動機鏈;**取得關鍵屬性後要 restate 確認**
  ("You mentioned you prefer X because [attribute]. Is that right?")。
  URL: https://www.qrcaviews.org/2025/09/16/taking-questions-upward-sideways-and-forward-using-laddering-and-scaffolding-for-better-interview-outcomes/
- Ethics of AI-generated follow-ups(arXiv 2606.30980,2026):過度 / 不當追問傷 rapport,尤其對
  vulnerable population;原則「**maintaining rapport and respecting interpersonal boundaries should
  take precedence over maximizing AI involvement**」。 URL: https://arxiv.org/html/2606.30980v1

**設計建議**
- 明確化「該追問」訊號成規則:回答字數過短、出現 hedging("大概"、"不太確定")、答案模糊 / 抽象、
  與先前陳述矛盾、或出現值得深挖的高價值線索。**答得完整清楚就不追,直接前進**。
- 追問深度預設 **2–3 層**(laddering)即收;深度設為可調參數,對高價值主題才放寬。避免 Outset 那種
  10 層 Abyss 當常態(那是特例)。
- 對 LLM 要**主動反制 under-probe 傾向**(2410.01824 的教訓):在 prompt 明確給「至少追一次」的觸發清單。
- 內建 holding 機制:好但時機不對的追問延後,不打斷受訪者當下的思路。
- 追問取得關鍵資訊後 restate 確認(接 Q3)。

---

## Q3. 確認與覆述(paraphrasing / active listening)

**結論**:**要覆述,但要有節制**——active listening(覆述"我聽到你說 X")是 AI 訪談相對人類的**已知
弱項**,補上能顯著提升 rapport;但**每題都確認會拖慢、變機械**,應在關鍵節點(取得核心資訊、要收斂、
要轉題前)才 restate。

**關鍵證據**
- AI Conversational Interviewing(arXiv 2410.01824):human 訪談者的違規中 **94% 集中在「沒做 active
  listening(沒 restate 受訪者的回答)」**——反過來說,restate 是人類也常漏、但被視為應做的行為。
  對照組凸顯這是可設計補上的差距。 URL: https://arxiv.org/html/2410.01824
- Expecting Too Much(arXiv 2601.02775,asynchronous AI interviewer 挑戰研究,2026):明列 AI 的設計
  缺口是「**AI interviewers rarely employed paraphrasing techniques**…absence of clarifying
  statements that human interviewers routinely use to demonstrate comprehension」。
  URL: https://arxiv.org/pdf/2601.02775
- AInterviewer(arXiv 2606.20588):設 **reformulating agent** 產生「smooth conversational
  transition」,並會「update the question itself to incorporate information already provided by the
  respondent」——即用「你剛提到 X,那麼…」把已知資訊織進下一題,達到隱性確認 + 不重複問。
  URL: https://arxiv.org/html/2606.20588v1
- Laddering 實務(UXmatters / QRCA):取得 differentiating attribute 後 restate 確認是標準動作。

**設計建議**
- 在三個時機才做顯性覆述:(a) 剛萃取到要寫進文件的核心事實 / 決策;(b) 偵測到模糊或矛盾要澄清;
  (c) 轉大題前的小結。其餘用**隱性確認**(把已知資訊織進下一題,如 reformulating agent)。
- 覆述要簡短、可被否認("我理解成 X,對嗎?"),讓受訪者能糾正——這也是資料品質的校驗點。
- 不要每 turn 都 "So what I'm hearing is…";過度確認會被感知為機械、拖沓(呼應 Expecting Too Much
  對 mechanical 互動的批評)。

---

## Q4. 議程管理與彈性(mixed-initiative);跳題;已答內容跳過

**結論**:主流做法是 **mixed-initiative**——AI 持結構化議程當骨架,但**允許受訪者主導局部流向、跟過去、
再自然拉回**;**跳題不該硬拉回**,而是跟隨並在議程上勾銷已涵蓋項目;**已答內容必須偵測並跳過 / 改成用已知
資訊 reformulate**,絕不重問。剛性照稿是 AI 訪談最被詬病的失敗模式。

**關鍵證據**
- Expecting Too Much(arXiv 2601.02775):受訪者最大抱怨之一是 AI「**rigidly adhered to predetermined
  question sequences regardless of conversational flow or emerging insights**」。剛性議程 = 頭號壞味道。
  URL: https://arxiv.org/pdf/2601.02775
- AInterviewer(arXiv 2606.20588):以 **classification agent** 管議程,評三個條件:
  (1) 此題**是否已被先前回答**(是 → 觸發 reformulate,不重問);(2) 受訪者是否拒答;
  (3) 此 main question 的 follow-up 是否已足夠(足夠 → transition 到下一題)。這是可直接借用的
  「議程狀態機」。 URL: https://arxiv.org/html/2606.20588v1
- 資訊 elicitation("If we misunderstand the client…",arXiv 2506.11610,2025):明指 rigid script
  與 excessive flexibility 之間存在張力,「Rigid adherence to scripts limits dialogue quality, while
  excessive flexibility can result in scattered, incomplete information gathering」,主張
  **mixed-initiative**(AI 與人共同引導)產出最完整。 URL: https://arxiv.org/pdf/2506.11610
- Horvitz mixed-initiative 12 準則(1999,經典權威)/ Microsoft HAX 18 Guidelines(2019,官方):
  當系統無法安全消解歧義時,用短澄清問題勝過自信答錯。
  URL: https://www.microsoft.com/en-us/haxtoolkit/ai-guidelines/
- Outset(官方):「Participants can give open-ended answers or go **off-script**, and the AI will
  follow along while still keeping the conversation on track per your discussion guide and research
  goals」——業界產品的預設就是「跟過去、再回到議程」。
  URL: https://outset.ai/resources/blog/what-actually-happens-in-an-ai-moderated-interview

**設計建議**
- 用「議程狀態機」而非線性腳本:每個 topic 有 covered / partially / refused 狀態;每輪回答後先跑
  **coverage 分類**(這回答涵蓋了哪些待答項?),命中就勾銷、跳過或改 reformulate。
- 受訪者跳題 = 跟過去先答(尊重其 initiative),再用一句橋接拉回未涵蓋項("這很有幫助;回到剛才
  提到的…")。**不要當下硬打斷拉回**。
- 絕不重問已答內容;需要確認時用「你剛提到 X…」的 reformulate 版本。

---

## Q5. 離題與閒聊處理

**結論**:**先承接、再溫和橋接回議程**——AI 訪談最被批評的是「abruptly redirected…without
acknowledging」(粗魯地硬切回稿)。正確做法是先短認可 / 承接離題內容,再用一句話帶回目標,不失禮。

**關鍵證據**
- Expecting Too Much(arXiv 2601.02775):AI 常「**abruptly redirected conversations back to
  scripted questions without acknowledging or validating off-topic contributions**」,造成 awkward
  互動——這正是要避免的反例。 URL: https://arxiv.org/pdf/2601.02775
- Google Conversation Design(官方):合作原則 Relevance 準則 + 「follow-up intents within
  conversational threads」——persona 應理解對話串裡的指代與延伸意圖,自然承接而非機械切斷。
  URL: https://developers.google.com/assistant/conversation-design/learn-about-conversation
- Outset(官方):產品層級把「follow along then keep on track」當預設(見 Q4 引文)。
- Ethics of AI follow-ups(arXiv 2606.30980):rapport 與 boundary 優先於「把議程跑完」。

**設計建議**
- 離題處理三步:(1) 一句短認可承接("聽起來這對你影響很大");(2) 判斷是否含可用資訊(有 → 併入
  文件);(3) 溫和橋接("我想確保有涵蓋到…,可以回到…嗎?")。
- 設離題容忍度上限(如連續 2 輪離題才積極拉回),避免既失禮又失焦兩頭空。

---

## Q6. 沉默與節奏(文字介面裡 AI 何時"不說話")

**結論**:在**文字**介面,「沉默」等同於**克制訊息長度與資訊量、把 turn 讓給受訪者、不搶回麥克風**。
準則一致:短 turn(2–3 句 / 一題)、問完就閉嘴、不追加干擾指令。訊息長度**沒有單一最佳值**,但一次一個
資訊單位是共識。(語音介面另有「留白給思考」的維度,文字介面則靠不搶 turn 體現。)

**關鍵證據**
- Google Conversation Design(官方):turn-taking 的核心是「who has the mic」——take / hold / hand
  over;「**if you ask the user a question and yield your turn, don't throw in additional
  instructions that interfere with their right to answer you**」。即問完不要再補話。
  URL: https://developers.google.com/assistant/conversation-design/learn-about-conversation
- OpenAI Realtime Prompting Guide(官方):2–3 sentences per turn;bullets over paragraphs。
  URL: https://developers.openai.com/cookbook/examples/realtime_prompting_guide
- NN/g「The 6 Types of Conversations with Generative AI」(署名 Raluca Budiu / Feifei Liu,分析 425
  次互動):結論「**there is no one optimal conversation length**」——短長皆可服務不同目標;主張
  be upfront about the bot、allow hybrid input(按鈕 + free text)。
  URL: https://www.nngroup.com/articles/AI-conversation-types/
- Expecting Too Much(arXiv 2601.02775,語音 async 情境):AI「**failed to allow adequate silence for
  reflection, instead filling pauses with immediate follow-up prompts**」——填滿停頓是反例(語音維度,
  對文字則對應「不要在對方還在打字 / 思考時搶著追問」)。 URL: https://arxiv.org/pdf/2601.02775

**設計建議**
- 硬性限制單訊息長度(預設 2–3 句、一次一題、一個資訊單位);長說明改用 bullet 或拆多輪。
- 問完問題就停,不在同一訊息追加指令 / 補充,把 turn 完整讓給受訪者。
- 文字介面提供 hybrid input(必要時給選項 chip 降低打字負擔,但核心仍走 free text)。

---

## Q7. 收尾:如何判斷"問夠了"並收尾;要不要總結給受訪者確認

**結論**:收尾由**三個訊號**觸發——(a) **coverage 完成**(議程項目都勾銷)、(b) **受訪者疲勞訊號**
(回答變短 / 敷衍 / 能量下降)、(c) **時間 / 輪數預算**到頂。收尾**應做一段總結給受訪者確認**(這對「產出
文件」型系統尤其關鍵,是文件正確性的最後校驗),且要避免「機械式結尾」的反例。

**關鍵證據**
- AInterviewer(arXiv 2606.20588):classification agent 明確以「該 main question 的 follow-up 是否
  **足夠**」作為 transition 判準;整場的終止即所有 main question 走完 + 各自 follow-up 足夠——即
  **coverage-driven 收尾**。 URL: https://arxiv.org/html/2606.20588v1
- Expecting Too Much(arXiv 2601.02775):兩個可操作訊號:(1) 疲勞——系統「continued questioning
  without perceptible adjustment for respondent energy levels」導致 fatigue(反例:要偵測能量下降就
  收);(2) 收尾品質——AI 給「**mechanical closing statements lacking genuine acknowledgment**」是
  反例,收尾要有真誠認可。 URL: https://arxiv.org/pdf/2601.02775
- Laddering / 質性訪談實務(QRCA / UXmatters):restate-to-confirm 是標準收束動作;對「產出文件」情境,
  收尾總結 = 把萃取的要點回讀給受訪者確認。
- NN/g:無單一最佳長度——**收尾條件應綁 coverage + 疲勞,而非固定輪數**。

**設計建議**
- 收尾判準三選一先到即收:coverage 全勾銷 / 連續 N 輪偵測到疲勞(回答變短、"就這樣"、"沒了")/
  達時間或輪數上限。
- **收尾必做結構化總結**:把要寫進專業文件的關鍵點條列回讀 → 請受訪者確認 / 補充 / 更正
  ("我整理到這幾點…有沒有要補或改的?")。這是文件正確性的最後守門,也給受訪者掌控感。
- 收尾語要有真誠認可(感謝其時間 / 具體回顧一個亮點),避免罐頭結尾。

---

## Q8. AI 訪談 vs 人類訪談的已知差距(CHI/CUI/CSCW 2024–2026 實證)

**結論**:實證上 **AI 不輸人類的地方**:回答品質相當、AI 甚至**引出更長 / 更多的內容**、一致性高、
受訪者對敏感話題**更敢講**。**AI 明顯不如人的地方**:rapport / 情感承接、追問時機的臨場判斷、
active listening(覆述)、對能量與情緒的即時調適、彈性(易剛性照稿)。設計上**用結構補彈性、用刻意規則
補 active listening 與追問觸發**。

**關鍵證據(帶數字)**
- AI Conversational Interviewing(arXiv 2410.01824,大型 survey 實驗):AI 引出的回答顯著更長——
  **平均 52.39 tokens vs 人類 32.81 tokens(+59.7%）**;人類編碼員評 clarity / relevance / grammar /
  specificity **兩組相當**,「engaging with an AI interviewer does not lead to a significant decline
  in response quality」。差距在**分工**:AI 常 under-probe(違規 88%),human 常漏 active listening
  (違規 94%)。 URL: https://arxiv.org/html/2410.01824
- AInterviewer 前導研究(arXiv 2606.20588,40 人對照 AI vs human):**AI 場次顯著更長(p=0.012)**;
  relevance(兩組 M=4.9)與 specificity(M=3.8 vs 3.5)**無顯著差**;但**人類單則回答長 38%**
  (AI 靠總量取勝)。即 AI 廣度 / 總量佳,人類單點深度佳。 URL: https://arxiv.org/html/2606.20588v1
- AI-Assisted Conversational Interviewing(arXiv 2504.13908,1,800 人隨機分派):AI probe 讓 open-ended
  回答「more detailed and informative」,但「**at a slight cost to respondent experience**」——
  深度 vs 體驗的取捨是實測存在的。 URL: https://arxiv.org/abs/2504.13908
- Strella(產品官方):「**Participants open up more with the AI moderator, resulting in deeper and
  more honest feedback**」——無評判感讓人更敢講(產品側佐證,與學界一致)。
  URL: https://www.strella.io/
- Expecting Too Much(arXiv 2601.02775):質性列出 AI 的弱項——判斷何時該深挖 / 前進、剛性照稿、
  不留白、缺覆述、不隨能量調適、機械收尾。 URL: https://arxiv.org/pdf/2601.02775

**設計建議**
- 把 AI 的強項(一致性、無評判、耐心、可長談)當賣點;弱項(rapport / 時機 / active listening)用
  **規則化補償**:明確追問觸發清單、關鍵節點強制 restate、能量偵測驅動節奏與收尾、離題先承接。
- 定位取捨:若要**廣度 / 標準化 / 規模**,AI 優勢明確;若單點要**極深的自傳式挖掘**,保留 human-in-loop
  或 escalation。

---

## Q9. 受訪者感受:什麼讓人願意講、什麼讓人反感

**結論**:**願意講**的要素——透明揭露"你在跟 AI 對話"、無評判 / 隱私感(讓人更敢講)、進度感 / 掌控感、
簡短不壓迫的節奏、被聆聽(適度覆述)。**反感**的要素——剛性照稿、粗魯打斷 / 硬拉回、機械覆述與罐頭結尾、
不顧疲勞硬問、過度 / 不當追問(尤其踩到邊界)、技術摩擦(錄音失敗等)。

**關鍵證據**
- NN/g(署名):「**be upfront about bots**」——透明揭露是信任前提;allow hybrid input 給掌控感。
  URL: https://www.nngroup.com/articles/AI-conversation-types/
- Strella / Outset(產品官方):無評判使受訪者「open up more…deeper and more honest feedback」;
  Outset 靠 sentiment / hedging cue 「probe in ways that **keep participants engaged**」。
  URL: https://www.strella.io/ · https://outset.ai/resources/blog/what-actually-happens-in-an-ai-moderated-interview
- AI-Assisted Conversational Interviewing(arXiv 2504.13908):更深的追問**以體驗為代價**——反感來自
  被追問的壓力,需平衡。 URL: https://arxiv.org/abs/2504.13908
- AI Conversational Interviewing(arXiv 2410.01824):受訪者覺得 AI 訪談「**less interesting**」、
  「less likely to repeat」,但作者歸因於**技術摩擦(音訊失敗)** 而非追問本身——UX 可靠度對滿意度的
  影響大於追問精巧度。 URL: https://arxiv.org/html/2410.01824
- Ethics of AI follow-ups(arXiv 2606.30980):不當提問(如對移民評論口音)、踩邊界會嚴重傷體驗,
  vulnerable population 尤甚。 URL: https://arxiv.org/html/2606.30980v1
- Expecting Too Much(arXiv 2601.02775):剛性、打斷、機械、不顧疲勞 = 反感來源全表。
  URL: https://arxiv.org/pdf/2601.02775

**設計建議**
- 開場即揭露 AI 身分與此對話的用途 / 產出("我會把我們的對話整理成一份 X 文件")。
- 顯性**進度感**(第 3 / 7 個主題)與**掌控感**(可跳過、可說"這題不想答"、可要求回看)。
- 強調隱私 / 無評判(降低受訪者的 emotional labor,提高揭露意願)。
- **把介面可靠度當一級需求**——技術摩擦對滿意度的殺傷大於追問品質(2410.01824 的反直覺發現)。
- 尊重邊界:偵測敏感 / 拒答訊號即收手,不硬追。

---

## 跨題總綱:給對話層的 10 條可操作規則

1. 一 turn 一題,禁 compound question(Q1,Google/OpenAI)。
2. 開放題開場 → 封閉題收斂;固定 main question 保覆蓋、自適應 follow-up 補深度(Q1,AInterviewer)。
3. 追問只在訊號觸發(短 / 模糊 / hedging / 矛盾 / 高價值線索),否則前進;預設 laddering 2–3 層即止
   (Q2)。主動反制 LLM 的 under-probe 傾向(2410.01824)。
4. 好但時機不對的追問延後(holding mechanism),不打斷當下思路(Q2,2509.12709)。
5. 只在關鍵節點做顯性覆述確認;其餘用「你剛提到 X…」隱性確認,避免每 turn 機械覆述(Q3)。
6. 議程狀態機:每輪先跑 coverage 分類,勾銷已答、絕不重問;跳題先跟後橋接,不硬拉回(Q4/Q5)。
7. 離題先承接再溫和帶回,設離題容忍上限;不粗魯硬切(Q5)。
8. 短 turn、問完閉嘴、把 turn 完整讓給受訪者;無單一最佳訊息長度但一次一個資訊單位(Q6)。
9. 收尾綁 coverage 完成 / 疲勞訊號 / 預算三選一;**必做結構化總結回讀請受訪者確認**(對產文件系統是
   正確性守門),收尾語要真誠不罐頭(Q7)。
10. 開場透明揭露 + 進度感 + 掌控感 + 隱私無評判;介面可靠度當一級需求(Q9)。

---

## 來源總表

大廠官方設計準則 / 模型廠官方
- Google Conversation Design — Learn about conversation(cooperative principle / turn-taking / one
  question at a time),官方持續維護。
  https://developers.google.com/assistant/conversation-design/learn-about-conversation
- OpenAI Realtime Prompting Guide(2–3 sentences/turn、sectioned prompt、conversation flow states),
  官方 cookbook,2025。 https://developers.openai.com/cookbook/examples/realtime_prompting_guide
- OpenAI Voice Agents Guide(Role/Objective、Conversation Flow、Safety & Escalation 結構),官方。
  https://developers.openai.com/api/docs/guides/voice-agents
- NN/g — The 6 Types of Conversations with Generative AI(署名 Raluca Budiu / Feifei Liu;425 次互動;
  no single optimal length;be upfront about bots;hybrid input)。
  https://www.nngroup.com/articles/AI-conversation-types/
- Microsoft HAX — Guidelines for Human-AI Interaction(18 準則;含不確定時用澄清 / mixed-initiative),
  官方,2019 起。 https://www.microsoft.com/en-us/haxtoolkit/ai-guidelines/

AI 訪談產品原廠一手資料
- Outset — What Actually Happens in an AI-Moderated Interview(linguistic/contextual cue 觸發 probe;
  probe general/specific/none;up to 10 follow-ups;follow off-script then keep on track),2026。
  https://outset.ai/resources/blog/what-actually-happens-in-an-ai-moderated-interview
- Strella — 官方產品頁(real-time adaptive probing;participants open up more / more honest),2026。
  https://www.strella.io/
- Listen Labs — 官方(concierge / managed AI-led qualitative research),2026。 https://listenlabs.ai/

頂會 / 學術論文(CHI/CUI/CSCW/AAPOR 圈,2024–2026)
- AInterviewer: A Platform for Designing and Conducting AI-led Qualitative Interviews(arXiv
  2606.20588,2026)——probing/reformulating/classification agent 架構;40 人前導,AI 更長 p=0.012,
  單則回答人類長 38%。 https://arxiv.org/html/2606.20588v1
- AI Conversational Interviewing: Transforming Surveys with LLMs as Adaptive Interviewers(arXiv
  2410.01824)——52.39 vs 32.81 tokens(+59.7%);probe on surprising/unclear;AI under-probe 88% /
  human 漏 active listening 94%;less interesting 歸因技術摩擦。 https://arxiv.org/html/2410.01824
- Expecting Too Much, Getting Too Little: Challenges of Asynchronous AI Interviewers(arXiv
  2601.02775,2026)——剛性照稿 / 粗魯拉回 / 不留白 / 缺覆述 / 不顧疲勞 / 機械收尾等反例全表。
  https://arxiv.org/pdf/2601.02775
- Harnessing the Power of AI in Qualitative Research: AI-Generated Follow-Up Questions(arXiv
  2509.12709,17 位研究員,2025)——timing 是頭號弱點;偏好 mid-to-late 插入;holding mechanism;
  quality 與 timing 耦合;四模式 role-assignment(backstage→frontstage→solo)。
  https://arxiv.org/html/2509.12709v1
- Ethics and Social Responsibility in AI-Assisted Interviewing: LLM-in-the-Loop Study of Follow-Up
  Questions(arXiv 2606.30980,2026)——rapport/boundary 優先於 AI 涉入最大化;vulnerable population
  風險。 https://arxiv.org/html/2606.30980v1
- AI-Assisted Conversational Interviewing: Effects on Data Quality and Respondent Experience(arXiv
  2504.13908,1,800 人隨機實驗)——更詳盡回答但以體驗為代價;live coding 可用但有 acquiescence bias。
  https://arxiv.org/abs/2504.13908
- "If we misunderstand the client, we misspend 100 hours": Conversational AI for information
  elicitation(arXiv 2506.11610,2025)——rigid vs flexible 張力;mixed-initiative 產出最完整;
  response types 影響資訊完整度。 https://arxiv.org/pdf/2506.11610

質性訪談方法學(probing / laddering 權威)
- Probing in qualitative research interviews: Theory and practice(Tandfonline,2023,Gorden 式 probe
  理論;laddered probe)。 https://www.tandfonline.com/doi/full/10.1080/14780887.2023.2238625
- Taking Questions Upward, Sideways, and Forward: Laddering and Scaffolding(QRCA,2025-09-16)。
  https://www.qrcaviews.org/2025/09/16/taking-questions-upward-sideways-and-forward-using-laddering-and-scaffolding-for-better-interview-outcomes/
- Laddering: A Research Interview Technique for Uncovering Core Values(UXmatters,2009;restate-to-
  confirm 實務)。 https://www.uxmatters.com/mt/archives/2009/07/laddering-a-research-interview-technique-for-uncovering-core-values.php

查不到 / 限制說明
- Anthropic 官方**無專門的 AI-interviewer / elicitation 對話設計指南**(僅有一般 agent / tool-use 指南),
  故本報告模型廠一手以 OpenAI 的 realtime / voice agent 指南為主。
- Google PAIR People+AI Guidebook 有 mixed-initiative / feedback 模式,但無針對「AI 訪談」的專章,
  故以 Google Conversation Design + HAX 為對話層主要準則來源。
