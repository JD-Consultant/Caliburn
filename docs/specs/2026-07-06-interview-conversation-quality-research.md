# 訪談對話品質研究紀錄(真人試訪根因#3;顧問「像機器人、不理員工」)

> 觸發:2026-07-06 首次真人試訪逐字稿(profile 02bc45a3)。RC1(幽靈槽)/RC2(保底輸出)
> 已修「靜默/垃圾槽」的**機械**病;本紀錄處理**對話智能**病——顧問把訪談當填格機器、
> 不確認員工的話、重複問、對「剛剛就說了/為啥不回我」無反應、爛答案照收。
> 紀律:改的是 ROLE_HEADER(措辭)+ context 狀態組裝(確定性),**不動指令詞彙表/guard/門檻數字**
> (design 不變量 1、5)。改後重跑 `evals/interview_sim.py` 留校準紀錄。

## 1. 症狀(逐字稿實據)

| seq | 員工 | 顧問 | 病 |
|---|---|---|---|
| 5 | 「1吧」 | (收下 time_share_pct)→ 直接問下一槽 | 爛答案照收,不追「1 成?還是隨口?」 |
| 9 | 「滑鼠」 | (收下 tools)→ 問下一槽 | 「滑鼠」不是工具答案,senior 會追「用哪個系統登記?」 |
| 10, 13 | | **兩次一字不差**問「例外情況?」 | 重複問(部分源於 RC1 幽靈槽,部分無「已答」感知) |
| 11→12 | 「床位滿了」→「要套用嗎?」 | 無視,續問例外 | 員工在問**建議卡片** UI,顧問不知情、不回應 |
| 14,15,17,18 | 「剛剛不是說了」「?」「剛剛就說了用滑鼠」「為啥不回我了」 | 續問下一槽 | **grounding 破裂**:員工明示「你沒在聽」,顧問零修復 |

**共通根因**:prompt 把 LLM 定位成逐槽推進器,缺三個 senior 訪談員的核心動作——
**先確認再問(active listening)**、**爛答案往下追(broad→specific)**、**破裂就修復(repair)**。

## 2. 權威來源(2 支方法論 + 2 支實證,交叉收斂)

### A. 認知任務分析 / 知識引出(這產品的本質學門)
- Hoffman, Crandall, Shadbolt (1998) *Use of the Critical Decision Method to Elicit Expert
  Knowledge*(Human Factors);Crandall/Klein/Hoffman *Working Minds*。
- **CDM = 對真實事件施「認知探針」多次回溯**,把**隱性知識**問出來(explicit + tacit)。
  → 對應本專案「員工有做但沒說(漏說)」:抽象問「你的流程?」問不出,要**錨在具體事件**
  (「上次床位滿了,你當下怎麼處理?」)。
- Brown, Power, Gore (2025) *Cognitive Task Analysis: Eliciting Expert Cognition in Context*
  (Org. Research Methods):半結構訪談 + 認知探針,**在情境中**引出。

### B. LLM 訪談員實證(2024–2026 arXiv)
- *AI Conversational Interviewing: LLMs as Adaptive Interviewers*(2410.01824)——系統指令原文:
  - 先確認:「**restate concisely in one or two sentences what was said, using mainly the
    respondent's own words. Then ask whether you properly understood.**」
    (人類訪談員 94% 違反此則,LLM 反而好執行——**這是 LLM 的強項,該用足**。)
  - 連舊答:「When it makes sense, **try to connect the questions to the previous answer**.」
  - 追問時機:「ask follow-up questions when a respondent gives a **surprising, unexpected or
    unclear answer**」;探針庫:「Why is that? / Could you expand? / Can you give me an example?」
  - 爛答案:「If they answer in **very short sentences** ask follow up questions... **elicit as
    much information as possible**.」
  - 實測 LLM **88% 的失誤是追問不足**——方向該往「多追一層」推(我們的預算 guard 兜上限)。
- *Improving LLM-Generated Follow-Up Questions*(2509.12709)——好追問的特徵:
  **topical alignment / depth(broad→specific)/ conversational bridge(接住剛說的)/
  contextual relevance(用對方的話,非通用問法)**;壞追問:generic、out-of-scope、premature。
  「built on what I originally had and went further」=好;domain grounding 勝過通用閒聊。

### C. 對話修復 / grounding(HCI)
- Ashktorab et al. (CHI'19) *Resilient Chatbots: Repair Strategy Preferences*;
  *Conversational Repair Strategies in Customer Service Chatbots*(2024)。
- 使用者**偏好明確承認破裂**,但**重複的承認是 clutter**;修復要用**最具體的 repair initiator**、
  最小化使用者代價。→ 員工說「剛剛就說了」時:**承認 + 用他已說的話回填/確認**,別再問一次。

## 3. 診斷:病灶全在 LLM 的那條線(措辭),不在 guard

架構分工(design 不變量 1):**guard/門檻/分流=executor 確定性;理解+措辭=LLM**。
症狀全是「措辭/對話策略」層——正確修法是**強化 ROLE_HEADER + 餵對狀態**,不是加 guard:

| 症狀 | 修法 | 落點 | 動到 guard? |
|---|---|---|---|
| 不確認就問 | reflect-then-ask(用員工原話一句話回述再問) | ROLE_HEADER | 否 |
| 爛答案照收 | 短/模糊答 → 先追一層具體(broad→specific) | ROLE_HEADER | 否(預算=2 兜上限) |
| 破裂無修復 | 員工示意「沒在聽」→ 承認+回填,不重問 | ROLE_HEADER | 否 |
| 抽象問不出漏說 | 錨在具體事件問(CDM 探針) | ROLE_HEADER | 否 |
| 重複問已答/已跳 | context 顯示缺口**扣掉 skipped**;已填如實列 | context(確定性) | 否 |
| 不知員工在問建議卡 | context 帶入 pending 建議摘要 | context(確定性) | 否 |

**關鍵自檢**:這些不是把信任交給 LLM——填哪個槽、能不能 advance、quote 驗證仍全在 executor。
我們只是讓 LLM 在**它本來就該負責的對話**上做得像 senior。預算 guard(每槽 2)恰好是
「多追一層」的確定性上限:研究說 LLM 追問**不足**,我們往上推,guard 防止另一端失控。

## 4. 決策(不另開 ADR;屬 0023 既定分工內的 prompt/context 強化)

1. **ROLE_HEADER 重寫**為 senior 顧問操作守則:reflect-then-ask、broad→specific 追爛答、
   repair-on-confusion、CDM 具體事件錨定、用員工原話。**指令詞彙表不變**(仍那 9 個)。
   ⚠️ **校準#2 修正**:reflect 不可置頂——小模型會把「先回述」當優先序、用回述**代替**
   set_slot(覆蓋 0.91→0.45)。定案=**落槽優先**(set_slot 為不可違反的置頂硬規則,
   回述/追問/問下一題都不得取代);senior 動作降為「在落槽前提下」的次要層。
   見校準紀錄 [`2026-07-05-interview-sim-calibration.md`](2026-07-05-interview-sim-calibration.md) #2。
2. **context 確定性補強**:(a) 缺口顯示扣除 skipped(與 executor `_next_gap_question` 同源);
   (b) 帶入 pending 建議摘要(員工可能在問卡片);(c) 已填槽如實回述供「連舊答」。
3. **驗證**:單元測 context 狀態組裝(skipped 不再出現在缺口、pending 進 prompt);
   改後重跑 interview_sim 留校準紀錄#2(門檻不變,看覆蓋/關鍵字/quote 是否維持或更好)。

## 5. 延後(backlog,非本次)
- ask_choice 在 survey 段接池(見「選職類/選任務交 LLM」討論)。
- 多 persona/對抗版模擬(愛離題、答非所問)——本次修的正是這類,擴 sim 覆蓋。
- rubric 品質分(黃金範本對尺)自動評。

## 來源
- Hoffman, Crandall, Shadbolt (1998), *Human Factors* 40(2). https://journals.sagepub.com/doi/10.1518/001872098779480442
- Brown, Power, Gore (2025), *Organizational Research Methods*. https://journals.sagepub.com/doi/10.1177/10944281241271216
- AI Conversational Interviewing (2024). https://arxiv.org/pdf/2410.01824
- Improving LLM-Generated Follow-Up Questions (2025). https://arxiv.org/html/2509.12709v1
- Ashktorab et al., Resilient Chatbots (CHI 2019). https://dl.acm.org/doi/fullHtml/10.1145/3290605.3300484
