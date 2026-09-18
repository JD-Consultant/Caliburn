# 研究紀錄:AI 共編產品中「審閱動作(accept/reject)之後的系統與 AI 行為語意」

- 研究日期:2026-07-12
- 範圍:2024–2026 主流 AI 共編 / coding agent 產品 + HCI 準則(HAX)
- 方法:用產品/業界通用詞彙(track changes、suggested edits、accept/reject、diff review、agent feedback loop、dismiss、resolved)廣掃,再挑有一手資料者深挖。
- 來源紀律:僅收原廠官方文件/官方部落格/官方 changelog + 公認 HCI 準則(Microsoft HAX)。內容農場一律排除;查不到一手處已明說。

---

## 核心區分(先講結論框架)

主流產品在「審閱動作之後 AI 做什麼」上,分成兩大類,語意完全不同:

- **A. 文件寫作類(Word Copilot、Google Docs Gemini、Notion AI、OpenAI Canvas)**:
  accept/reject 是**純粹、無聲的 UI 動作**。AI 一次性產出建議 → 使用者逐筆或批量 accept/reject → 接受就 "bake in"、拒絕就 revert/移除。**審閱動作本身不觸發 AI 說話、不重新生成、不彈訊息**。官方文件也**沒有**描述把「這一筆被拒」當作持久回饋去調整未來建議(它是 one-shot 批次,不是連續 loop)。
- **B. Coding agent 類(Claude Code、Cursor、GitHub Copilot)**:
  審閱動作**會**進入 agent loop。拒絕會被當成訊號回饋給模型(至少 in-session),模型可據此改路;Copilot 的 autocomplete 另有把 accept/reject 當**離線訓練資料**的機制(非 in-session 即時)。

---

## 逐產品

### 1. Microsoft Word — Edit with Copilot(A 類)
- 行為:Copilot 直接改文件;若文件開了 **Track Changes**,Copilot 的編輯會落成標準 tracked changes,由使用者用 Word **既有** track changes 介面 accept/reject。Copilot 本身**不能**幫你 accept/reject tracked changes,也不觸發 AI 回應——accept/reject 是 Word 原生的無聲動作。共享文件情境下,Edit with Copilot 會**先在 chat 顯示 preview**,確認後才套用。
- Q1:accept/reject 不觸發 AI 回應。Q4:走 Word 原生 Accept All / Reject All(整份或逐筆),純套用/還原。
- 官方沒有描述「某筆被 reject 後,Copilot 之後不再重提」的 per-suggestion 抑制機制。
- 證據:
  - "Edit with Copilot cannot turn on/off or accept/reject tracked changes. However, Edit with Copilot will respect Track Changes… changes will be tracked."
  - Edit with Copilot in Word — Microsoft Support(存取 2026-07):https://support.microsoft.com/en-us/word/edit-with-copilot-in-word
  - Accept or reject tracked changes in Word — Microsoft Support:https://support.microsoft.com/en-us/word/accept-or-reject-tracked-changes-in-word

### 2. Google Docs — Gemini「Help me write / Refine」(A 類)
- 行為:Gemini 的 suggested edits 以 **tracked-changes 形式**呈現,**在你核准前僅你可見**、不套用。逐筆 **Accept suggestion**、整批 **Accept all**、整批 **Reject all**。
- Q1:accept/reject 不觸發 AI 回應(是安靜的套用/還原)。Q4:Accept all / Reject all 直接套用或丟棄整批,無 AI 動作。若要調整,使用者是**主動**再對 Gemini 下 "refine" 指令,而不是 reject 本身觸發重生成。
- 官方未描述 per-suggestion 拒絕記憶或再提防制。
- 證據:
  - "Gemini's suggested edits are only visible to you until you approve them." / "click Accept suggestion… Accept all… Reject all."
  - Collaborate with Gemini in Google Docs — Google Docs Editors Help:https://support.google.com/docs/answer/14206696
  - Write & edit with Gemini in Docs:https://support.google.com/docs/answer/13447609
  - New Gemini capabilities in Google Docs(Workspace Updates, 2026-04):https://workspaceupdates.googleblog.com/2026/04/new-gemini-capabilities-in-google-docs-help-you-go-from-blank-page-to-brilliance.html

### 3. Notion AI — Suggested edits(A 類)
- 行為:AI 產出後,使用者 **Accept / Discard(或 Replace / Discard / try again)**。對 AI 建議或人類 suggested edit,**approve 會「bake in」並移除該建議;reject 會把文字 revert 回原版並讓建議消失**。
- Q1:accept/reject 是安靜 UI 動作,不觸發 AI 回應(可另按 "try again" 才重生成——那是使用者主動,不是 reject 自動觸發)。Q6(改寫歸屬):approve 後內容併入頁面成為一般內容,不再標為建議。
- 官方未描述被 discard 的建議會被記住而不再重提。
- 證據:
  - "approving will 'bake in' the edit and remove the suggestion, and rejecting will revert the text to its original version."
  - Suggested edits — Notion Help Center:https://www.notion.com/help/suggested-edits
  - Notion 2.43 release(2024-07-29):https://www.notion.com/releases/2024-07-29

### 4. OpenAI — ChatGPT Canvas /（後續）writing blocks(A 類)
- 行為:"Suggest edits" 產生 **inline 建議**,右側列出、正文對應段落高亮,使用者按 **apply / keep / reject** 決定。"you decide whether to keep it or reject it… you never lose control."
- Q1:inline accept/reject 不觸發 AI 回應。註:2026-05-28 OpenAI 在 GPT-5.5 系列**移除 Canvas**,寫作/程式改回 chat thread 內的 "writing blocks / code blocks"(產品形態變動,審閱語意不變:仍是使用者主導的 keep/reject)。
- 證據:
  - "The AI makes suggestions inline… you decide whether to keep it or reject it… you never lose control of your content."
  - What is the canvas feature in ChatGPT — OpenAI Help Center:https://help.openai.com/en/articles/9930697-what-is-the-canvas-feature-in-chatgpt-and-how-do-i-use-it
  - Introducing canvas — OpenAI(2024-10):https://openai.com/index/introducing-canvas/

### 5. Claude Code / Claude Agent SDK(B 類,最有價值的一手來源)
- 這是唯一**官方明確描述「reject 訊號回饋給模型、模型據此改路」**的產品文件。
- 機制:agent 要用工具(含 Edit/Write)時觸發 `canUseTool` callback,使用者回 **allow / deny**:
  - **Reject**:`{ behavior: "deny", message }` → 官方原文:*"Deny: tool doesn't execute, **Claude sees the message** and **may try a different approach**."* 亦即拒絕**不是無聲**——deny message 直接進模型 context,模型可換做法。
  - **Suggest alternative**:deny 時把使用者的替代想法寫進 message,*"Claude will read this and decide how to proceed based on your feedback."*
  - **Approve with changes**(對應 Q6 改寫歸屬):使用者可在執行前改 input,官方原文:*"**Claude sees the result but isn't told you changed anything.**"* → 改寫後模型只看到最終結果,不知使用者動過手。
  - **Redirect entirely**:用 streaming input 直接給新指令。
- in-session 學習:官方定位「reject + 附言」是即時、in-session 的引導(不是持久跨 session 學習)。已知痛點(社群 issue,非官方保證):CLI 端若只點 reject 不附言,模型有時**收不到回饋**、以為已套用或得重讀檔——說明「無聲 reject」在 agent loop 是**明確的壞味道**。
- 證據:
  - Handle approvals and user input — Claude Code Docs(存取 2026-07):https://code.claude.com/docs/en/agent-sdk/user-input
  - (社群佐證 broken loop 痛點,非一手保證)anthropics/claude-code issues #10595 等。

### 6. Cursor(B 類)
- 行為:Agent 產 diff → 底部 review 介面 **accept / reject**,可**部分或整批**接受;undo 以 per-agent 為單位;保留 agent run **歷史**,被拒的變更可事後回頭 reapply(不是永久丟失)。
- in-session 回饋:官方 learn/blog 描述 agent 會**記住近期修正**——"if you correct a bug and then ask for another feature, it might proactively avoid similar bugs"。定位為**對話 session 內**的 context 適應,而非跨 session 的持久學習。
- Q2:對「使用者改掉/退回 diff」的後續行為,官方**沒有**明講把 reject 當顯式訊號記帳;較接近「靠對話上下文自然適應」。
- 證據:
  - Reviewing and Testing Code — Cursor Docs:https://cursor.com/docs/agent/review
  - Best practices for coding with agents — Cursor Blog:https://cursor.com/blog/agent-best-practices
  - Working with Agents — Cursor Learn:https://cursor.com/learn/working-with-agents

### 7. GitHub Copilot(B 類,唯一有官方「訓練用途」一手描述)
- **兩種面向要分開**:
  - **inline autocomplete 的 accept/reject**:是**無聲**的編輯動作(接受=插入、拒絕=不插入)。但 GitHub 會把 accept/reject(在使用者**同意**收集程式片段的前提下)當**離線模型改進**的資料——即所謂 30 秒後在插入點抓 "hypothetical prompt" snapshot 當訓練資料。**這是跨使用者、離線訓練,不是 in-session 即時調整**;關掉 "Allow GitHub to use my code snippets for product improvements" 就不記錄。
  - **Copilot code review**(PR 情境):建議以 review comment / suggested change 形式出現,走 GitHub **既有**的 comment resolve / suggestion apply 流程(對應 Q3:resolved 後該線程收起)。
- Q2:Copilot 對「autocomplete 被拒」有明確的**訓練資料**用途(官方 + 研究),但那是產品層級長期改進,非「這個 session 立刻不再提」。
- 證據:
  - Using GitHub Copilot code review — GitHub Docs:https://docs.github.com/copilot/using-github-copilot/code-review/using-copilot-code-review
  - "GitHub uses data, including information about which suggestions users accept or reject, to improve the model."(consent-gated)— GitHub Copilot 隱私/FAQ 文件族;community discussion #19328:https://github.com/orgs/community/discussions/19328
  - 研究佐證(非原廠但公認):Mozannar et al., "When to Show a Suggestion? Integrating Human Feedback in AI-Assisted Programming," AAAI 2024 — 明講以 telemetry(prompt + accept/reject 動作)訓練 CDHF 回饋迴路:https://www.erichorvitz.com/copilot_display_AAAI.pdf

### 8. Grammarly(A 類 + Q3 抑制機制標竿)
- 行為:單筆建議可 **Dismiss(忽略)**;`More Actions > Turn off suggestions like this` 可**抑制同類**建議;Premium/Pro 可在帳號設定(account.grammarly.com/customize/suggestions)關掉整組建議類型。Web 版對 dismiss 有**session/重整後仍記得**的記憶(有限度)。
- 這是 Q3「dismissed suggestion 不再出現」最清楚的一手案例:dismiss 是單筆消音,"turn off suggestions like this" 是**類別級抑制**。
- 證據:
  - How to deactivate certain suggestions in the Grammarly Editor — Grammarly Support:https://support.grammarly.com/hc/en-us/articles/360045784631
  - How to deactivate suggestions in Grammarly for Windows/Mac:https://support.grammarly.com/hc/en-us/articles/4412837103117

### 9. Figma(部分相關;審閱語意較弱)
- Make Designs / Check designs:AI 產出後由使用者 **review before applying**(如 "Check designs" 會建議對齊 design system 的 variable,"letting you check the work before applying")。屬 A 類「先審後套」,官方未描述 reject 回饋 loop。
- 證據:Introducing Figma AI(2024):https://www.figma.com/blog/introducing-figma-ai/;Config 2025:https://www.figma.com/blog/config-2025-press-release/
- Linear:未找到「AI 建議 accept/reject 之後 AI 行為」的一手描述(主要是被 MCP 當任務來源引用)。**明確標記:查不到一手。**

---

## HCI 準則(Microsoft HAX Toolkit — 一手)

- **G8 Support efficient dismissal**:"Make it easy to dismiss or ignore undesired AI system services." 強調**低成本忽略**(單鍵/語音)。頁面**未**規定「dismiss 後未來要抑制再現」,但「efficient」精神隱含忽略動作本身必須零摩擦。
  - https://www.microsoft.com/en-us/haxtoolkit/guideline/support-efficient-dismissal/
- **G9 Support efficient correction**:"Make it easy to edit, refine, or recover when the AI system is wrong." 官方解法**明確**包含:讓使用者改/修 AI 輸出,並 **"making clear that their correction will be used as feedback for its learning over time."** → 準則層級**主張把修正當回饋**。Patterns:switch classification、rich & detailed edits、undo automated actions、batch-edit。
  - https://www.microsoft.com/en-us/haxtoolkit/guideline/support-efficient-correction/
  - Pattern 9C Undo automated actions;9B Rich and detailed edits。
- **G15 Encourage granular feedback**:"Enable the user to provide feedback… at each item or instance of system output." 兩大理由:**使用者控制**(逐項表達偏好去導引系統)+ **系統監測/QA**(確保 AI 如預期運作)。Pattern 15A:Encourage explicit feedback on individual system outputs。
  - https://www.microsoft.com/en-us/haxtoolkit/guideline/encourage-granular-feedback/
  - https://www.microsoft.com/en-us/haxtoolkit/pattern/g15-a-encourage-explicit-feedback-on-individual-system-outputs/
- 準則與產品現況的落差:HAX(G9 + G15)**主張**把逐項審閱動作(尤其 correction)當回饋利用;但**文件寫作類產品現況**多半沒把 per-suggestion 的 accept/reject 當持久回饋(只當一次性套用/還原)。真正把審閱動作接進回饋 loop 的是 **coding agent(in-session)** 與 **Copilot autocomplete(離線訓練)**。

---

## 跨產品歸納

**共識(多家一致)**
1. **審閱動作預設是「使用者主導、AI 不搶話」**:文件寫作類 accept/reject 一律是安靜 UI 動作,不觸發 AI 立即說話/重生成。要 AI 動,得使用者**另外主動**下指令(refine / try again)。
2. **AI 產出保持「pending / 私有直到核准」**:Gemini、Word(shared 的 chat preview)、Notion、Figma 都採「先審後套」,accept=bake in、reject=revert/移除。
3. **批量操作是純套用/還原**:Accept all / Reject all 不引發 AI 動作。
4. **類別級抑制以「turn off suggestions like this」實現**(Grammarly 標竿):單筆 dismiss 消音 + 同類抑制分層。

**分歧 / 產品差異**
1. **reject 是否回饋給模型**:
   - 文件寫作類:官方**未**把 per-item reject 當回饋(無聲、無記帳)。
   - Claude Code:**明確**——deny message 進 context,模型**可即時改路**(唯一官方寫明 in-session 回饋語意者)。
   - Cursor:靠**對話上下文**自然適應(記住近期修正),非顯式 reject 記帳。
   - GitHub Copilot autocomplete:accept/reject 進**離線訓練**(consent-gated),非 in-session。
2. **改寫(rewrite)歸屬**:Notion「bake in 成一般內容」;Claude Code「Approve with changes → 模型看到最終結果但**不被告知**你改過」。→ 各家傾向把使用者改寫視為**最終事實**,不特別讓 AI 意識到「這是被人改過的我」。

---

## 對「審閱動作的正確系統語意」的結論建議

給 Caliburn(顧問著作、AI 逐筆建議 + accept/reject)設計參考,綜合一手證據:

1. **accept/reject 預設無聲、不搶話**(全業界共識)。使用者按 accept/reject 後**不要**讓 AI 自動彈訊息或重生成——那是使用者另外主動觸發的動作(對齊 Word/Gemini/Notion/Canvas)。

2. **但「無聲」≠「不記帳」**。HAX G9/G15 明確主張逐項審閱(尤其 correction)應被系統當回饋利用。建議:reject/改寫**靜默記錄成結構化事件**(哪筆、被拒還是被改寫、改成什麼),不打斷使用者,但供**之後**的互動使用。

3. **拒絕的再提防制(Q3)要做**:採 Grammarly 式分層——被 dismiss 的具體建議在同一輪不再出現;若使用者「turn off 這類」,則**同類抑制**。避免 AI 在後續回合重提剛被否決的同一建議(這是明確壞味道)。

4. **coding-agent 式 in-session 回饋值得借鏡但要克制**:若 Caliburn 有 agent loop(如整段重寫),reject 應像 Claude Code 一樣把「被拒 + 原因」餵回模型讓它改路;但**純逐筆 UI accept/reject 不該觸發 loop**——避免每次審閱都推動一輪運算(對齊本 repo 記憶「discuss-before-implement pacing / 避免過度設計」)。

5. **改寫歸屬(Q6)**:使用者改寫 AI 建議後,把成品視為**使用者的最終文字**(bake in),AI 後續**不宜**再宣稱那段是自己的建議、也不宜重提原版。若要讓 AI 之後認知「這裡被人改過」,需**顯式**記一筆(Claude Code 預設是**不**告知模型——這是刻意的低摩擦取捨,可依 Caliburn 需求選擇)。

6. **批量(Q4)保持純套用/還原**,不引發 AI 動作;但可在背景把「整批被 reject」記成一個較強的方向性訊號(對齊 HAX G15 的「系統監測」用途)。

**一句話**:審閱動作對「當下 UI」應是安靜、零摩擦、使用者主導的 accept/reject/revert;對「AI 的記憶」則應是被**靜默記帳、之後才被利用**的回饋訊號(不重提被拒項、必要時調方向),而非立即觸發 AI 說話或重算。這條線正是主流產品共識(安靜 UI)+ HAX 準則(把審閱當回饋)+ coding agent 一手實作(reject 進 context)三者的交集。
