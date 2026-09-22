# AI 與人共同編輯文件／結構化內容的互動設計(UX)——2025–2026 主流做法與趨勢研究

> 研究者:Caliburn research agent。日期:2026-07-12。純學習研究,不綁定特定專案。
> 來源紀律:只收產品原廠官方文件/官方部落格、公認 HCI 準則(Microsoft HAX、Google PAIR、NN/g)、頂會論文/原廠研究。內容農場、無署名轉述一律排除;下方若引用二手,會明確標註且僅作趨勢佐證。
> 標註慣例:每條發現附「來源 + 發布/更新日期」。優先 2025 下半年–2026 材料。

---

## 摘要總判斷(給忙的人)

跨產品在 2025–2026 有一個**清楚的收斂方向**:AI 對既有文件的修改,從早期「直接覆寫」轉向 **「直寫 + 修訂標記(track changes / diff)+ 逐筆或批量 accept/reject」**。這是 2025 年最明確的產業共識——連最晚跟進的 Word Copilot 都在 2025 補上 word-level track changes,ChatGPT Canvas 補上「show changes」綠增紅刪。**「AI 改哪裡要可見、可審、可回退」已是預設,不再是加分項。** 對話(chat)與寫入(canvas/文內)則明顯**分面板**:側欄/底欄負責對話與意圖,文件本體負責呈現改動。同時 human-in-the-loop 的門正在往 **「審計畫(plan)而非審每一步」** 移動(Anthropic Plan Mode),因為逐步確認已被實測證實會造成 **approval fatigue(確認疲勞,93% 無腦點准)**。

---

## Q1. AI 直寫 vs 建議層——主流怎麼做,有無收斂?

**結論:** 明顯收斂到「**直寫入文件本體 + 修訂標記 + 人 accept/reject**」這一種心智模型,而非早期的「側欄貼一段、人自己複製」。四家做法趨同:Word Copilot(2025 補上 track changes)、Google Docs Gemini(suggested edits,核准前只有你看得到)、Cursor(apply → diff → accept/reject)、Canvas(inline + show changes)。差別只在「改動預設是否已寫進正文」:Gemini/Cursor 傾向「暫存/待核准層」,Word/Canvas 傾向「已寫入但以修訂樣式標記」。

**關鍵證據:**
- **Word Copilot**:2025 補上 word-level track changes,「changes visible by default」「edits are always transparent, auditable, and granular」。原本 Copilot 的編輯是**直接覆寫內容**,無法逐筆審核,在合約審閱/合規場景幾乎不可用——這正是補 track changes 的動機。(Microsoft 365 Copilot Blog, "Copilot in Word: New Capabilities for Document Workflows", 2025;the-decoder.com 2025 轉述同一發布)
- **Google Docs Gemini**:「Gemini's suggested edits are **only visible to you until you approve them**」「keeping you in full control」;可從底欄/側欄下指令跨全文改,或選取文字聚焦。(Google Workspace Updates blog, 2026-04-22)
- **Cursor**:「When you click apply... Cursor will **show the changes** that will be made rather than immediately modifying the file, allowing you to confirm the diff looks correct before accepting.」Edit/Agent 模式都是先產生 diff 再 accept/reject。(Cursor 官方 docs / 社群論壇彙整,2025)
- **OpenAI Canvas**:inline suggestions 直接標在正文;「show changes」按鈕顯示最近改動(綠增紅刪)。此功能是**回應使用者從 Canvas 上線起就要求 track/show changes**。(OpenAI "Introducing canvas" 2024-10;VentureBeat "ChatGPT's Canvas now shows tracked changes" 2024)
- **反向訊號(值得記):** 2026-05 OpenAI 把 Canvas 從 GPT-5.5 悄悄下架,寫作/程式改成 chat thread 內的 "writing blocks / code blocks"。顯示「獨立畫布」不是唯一終局,也有回流到對話串內聯呈現的實驗。(the-decoder / Medium 2026 二手,僅作趨勢佐證,非定論)

**別犯前人錯的啟示:** 不要讓 AI 靜默覆寫使用者的文字——Word 用血淚證明了這條(合規場景直接不可用)。預設就要修訂標記 + 可回退。若要抄一種模型,抄「直寫入 + track changes + accept/reject」這個已被四家驗證的主流。

---

## Q2. 修訂呈現——顏色、粒度、accept/reject 細節

**結論:** 呈現語彙高度統一:**綠=新增、紅=刪除**,支援**逐筆 accept/reject** 與**批量 accept-all**。粒度戰爭是關鍵差異點——Word 特意做到 **word-level**(而非整段替換),因為「整段 diff」在長文審閱時噪音太大。鍵盤批量操作(Cursor 的 Cmd+Enter 全接受)是效率剛需。

**關鍵證據:**
- **Canvas**:「highlighting added information in **green** and deleted sections in **red**」。(OpenAI/VentureBeat 2024)
- **Word Copilot**:強調 **word-level** track changes、可 rollback、逐筆審。刻意從「覆寫」升到「詞級修訂」以符合法務/財務/合規的細緻審閱。(Microsoft 365 Copilot Blog 2025)
- **Cursor**:「Cmd + Enter to **accept all** changes(apply all),Cmd + Backspace 取消/拒絕全部」;逐檔逐塊導覽 accept/reject。套用後檔案進入 diff-edit 模式,連後續手動編輯都要 accept/reject 才退出。(Cursor docs/forum 2025)
- **與傳統 track changes 的異同**:相同=顏色語彙、accept/reject 心智模型直接沿用 Word 幾十年的慣例(降低學習成本);不同=(a) 改動來源是 AI 非人,故需額外的「來源/理由」標示(見 Q5);(b) 常有「一次一大批 AI 改動」湧入,故 accept-all / reject-all 的批量操作比人對人協作時更關鍵;(c) diff 常是**暫態預覽**(apply 前),而非持久修訂記錄。

**別犯前人錯的啟示:** (1) 沿用 track-changes 的顏色與 accept/reject 慣例,別發明新語彙。(2) 粒度要細到詞/句級,別讓 AI 回一整段替換讓人重讀全部——那會製造 review 負擔。(3) 一定要有批量 accept-all / reject-all,因為 AI 一次會丟很多改動。(4) diff 是暫態預覽 vs 持久修訂,要想清楚你的模型是哪種,別混。

---

## Q3. 審批與自主度——門怎麼設,官方準則怎麼說

**結論:** 兩條並行趨勢。(a) 產品層:**預設保守**——修改動作前要人核准(Claude Code 預設每次 file write/shell/network 都要簽核;GitHub Copilot agent 跑 terminal command 前必須確認)。(b) 準則+研究層:逐步確認已被實測證明會製造 **approval fatigue**,所以前沿在往 **「審計畫而非審每步」(Plan Mode / Intent Preview)** 與 **autonomy dial(自主度隨信任漸增)** 移動。關鍵設計組:**preview(先看要做什麼)、undo(可回退)、intervene-when-it-matters(能在關鍵處介入,而非事事簽核)**。

**關鍵證據:**
- **Anthropic《Measuring AI agent autonomy in practice》(2026-02-18)**——本研究是這一節的金句來源:
  - 「Users approved roughly **93% of permission prompts**, indicating potential **approval fatigue**.」(逐步確認會退化成無腦點准)
  - 「effective oversight **doesn't require approving every action** but being in a position to **intervene when it matters**.」
  - 信任隨經驗漸增:新手 ~20% 開全自動、老手 >40% 開全自動;老手不是不管,而是改成**監看+關鍵介入**(打斷率新手 5%→老手 9%)。
  - 工具呼叫 80% 至少有一層保護、73% 有人參與、**只有 0.8% 是真正不可逆**——啟示:把確認力氣集中在那不可逆的少數。
  - 建議方案:**Plan Mode**——「reviewing execution plans upfront rather than approving individual agent actions」。
  - Agent 也會**自我限縮**:複雜任務主動停下問澄清(在方案間抉擇 35%、蒐集診斷資訊 21%、要憑證 12%)。
- **Claude Code 預設**:read-only 免核准,任何**修改**動作前要人簽核;可對信任的例行任務授予持久權限。(Anthropic framework / TechTimes 2026-07 "Claude Code Defaults to Human Approval")
- **GitHub Copilot agent mode**:「user must **confirm terminal commands** before they are run — a critical human-in-the-loop safeguard」;agent 的 PR 需人核准才能跑 CI/CD。(VS Code blog 2025-02-24;GitHub Docs "Responsible use / Agents")
- **HAX 準則(Amershi et al. 2019,仍是現行權威;HAX Toolkit 2025–2026 持續使用未翻案)** 對這題最相關的幾條:**G8 Support efficient dismissal(易於忽略建議)**、**G9 Support efficient correction(易於修正 AI 的錯)**、**G10 Scope services when in doubt(不確定時縮小服務範圍/寧可少做)**、**G16 Convey the consequences of user actions(讓人明白動作後果)**、**G17 Provide global controls**。(Microsoft HAX Toolkit, AI Guidelines 頁,持續維護)
- **NN/g / State of UX 2026**:trust 被列為 AI 體驗的頭號設計問題,「AI 採用上升但信任下降」;使用者要 **legibility**——「see what's happening, intervene when needed, understand why」;**Intent Preview** = 執行前先展示 AI 打算做什麼,給人 proceed / modify / stop。(NN/g 主題頁 + State of UX 2026;Smashing Magazine "Designing For Agentic AI" 2026-02 佐證 Intent Preview + Autonomy Dial 模式)

**別犯前人錯的啟示:** **不要用「每一步都簽核」當安全感來源——它會退化成 93% 無腦點准,反而讓真正危險的動作也被放行。** 正確做法:(1) 風險分級——只在**不可逆/高風險**處硬性確認,其餘給 undo 就好;(2) 提供 **plan preview**,讓人審計畫一次,而非審動作 N 次;(3) autonomy 隨信任可調(dial),別鎖死;(4) 一定要有 undo/回退,讓「事後修正」比「事前簽核」承擔更多把關。

---

## Q4. AI 在哪裡說話——chat 側欄 vs inline vs 命令面板

**結論:** 主流採**雙面板分工**:「**對話/意圖**」放**側欄或底欄**(chat),「**寫入/改動**」放**文件本體**(canvas 或 inline 修訂)。文內互動則靠**選取文字 → 就地小指令**(Gemini 的 Refine chip、Canvas 的 block comment、Cursor 的 inline edit Cmd+K)。2026 的新方向是 **background / ambient agent**:任務**非同步**跑,完成後才回報,而非同步逐字生成。

**關鍵證據:**
- **Gemini in Docs**:對話在「new bottom bar or side panel」;文內用**選取 → Refine chip → 下 prompt** 聚焦局部,「without regenerating the entire document」。(Google Workspace Updates 2026-04-22)
- **Canvas**:獨立畫布(chat 在左、文件在右)是「first major update to ChatGPT's visual interface in two years」;文內用 highlight 或 block-comment icon 就地下指令。(OpenAI 2024-10)
- **Cursor**:chat/Composer 面板 vs 文件內 diff;inline edit(Cmd+K)就地改。(Cursor docs 2025)
- **2026 背景/非同步趨勢**:「Cursor background agents... **asynchronous** nature... You fire off a task and forget it」;2026「最重要的轉變是 long-running autonomous workflows... execution loops」。ambient agents 透過共享事件流溝通,嵌入整個工作流而非點對點。(Swarmia/Prosus/Akira 2026 二手趨勢彙整,佐證方向)
- **NN/g**:好的 agent 介面要「expose agent state, intent, history, and decision points so humans remain informed and in control **without being overloaded**」;agent 要挑對時機打斷(別在使用者開會時丟非緊急更新)。(NN/g "AI Agents as Users" / legibility 主題 2026)

**別犯前人錯的啟示:** (1) 別把「對話」和「改動」塞在同一個視覺區——會讓人分不清「AI 在說話」還是「AI 已經改了」。側欄說話、正文改動,是已驗證的分工。(2) 局部意圖用「選取 → 就地小指令」最省認知,別逼人回側欄打「請改第三段」。(3) 背景 agent 非同步回報是趨勢,但要設計好「完成通知 + 可審的 diff 包」,別讓使用者回來面對一堆已成事實的改動卻無從審起。

---

## Q5. 溯源與標示——AI 內容要不要標、怎麼標

**結論:** 兩層。(a) **文件內互動層**:AI 改動用修訂樣式 + 「這是 AI 改的」歸屬 + 可展開「為什麼這樣改」的理由(對齊 HAX G11「Make clear why the system did what it did」)。(b) **跨平台可信度層**:媒體/檔案級的 **C2PA Content Credentials**(密碼學綁定的「內容成分標籤」)成為 AI 生成標示的事實標準,且正被法規(EU AI Act 2026-08 生效)推成硬需求。純文字的 provenance 標準仍在早期(IPTC 2025.1 加了 AI metadata 欄位;學界有 faceted attribution 提案),尚未定於一尊。

**關鍵證據:**
- **C2PA / Content Credentials**:密碼學綁 metadata、記錄來源與「哪些是 AI 增強/生成」的「nutrition label」;v2.2 於 2025-05 發布、v2.3 (2025-12) 為現行。OpenAI(DALL·E 3/Sora)、Adobe Firefly、Google Imagen 都嵌入 C2PA 標示 AI 生成。**EU AI Act(2026-08 生效)要求 AI 生成內容透明標示,C2PA 的 AI assertion 直接對應。**(Numonic / C2PA 官方 / Wikipedia Content Credentials 2025–2026)
- **IPTC 2025.1**:新增 4 個 AI metadata 欄位(AISystemUsed、AISystemVersionUsed、AIPromptInformation、AIPromptWriterName)——文字/資產級 AI 標示的萌芽。(IPTC 2025.1 / Numonic 2025)
- **HAX G11**「Make clear **why** the system did what it did」——文件內層對應:AI 每筆改動應能展開理由/依據。**Word Copilot** 的 contextual comments(AI 可把說明錨定到正確文字)就是這條的產品化。(Microsoft HAX 2019;Word Copilot Blog 2025)
- **PAIR People + AI Guidebook** 的 **Explainability + Trust** 章:溯源/可解釋是六大核心之一,generative AI 時代持續更新。(Google PAIR, "Updating the People + AI Guidebook in the age of generative AI", Medium)

**別犯前人錯的啟示:** (1) 文件內至少要能回答「這段是不是 AI 寫/改的」和「為什麼」。(2) 若內容會外流/當正式產出,考慮 C2PA 這類可驗證溯源——法規已在逼(EU AI Act)。(3) 但別過度標示到噪音——見 Q6 的「AI 標記永遠不消」坑;溯源要**可查而非強制常駐**。

---

## Q6. 前人踩坑——官方/研究明講的失敗模式

**結論:** 有五個被反覆點名的坑,設計時當「禁忌清單」用:靜默覆寫、確認疲勞、建議洪水/AI 疲勞、過度依賴、標記/介入時機錯位。這些都有實證或官方發布佐證,不是傳聞。

**關鍵證據(逐坑):**
1. **靜默覆寫破壞信任/不可審**:Word Copilot 原本直接覆寫、無法逐筆審,合約/合規場景「nearly unusable」——直到補 track changes 才救回。(Microsoft/Windows Forum 2025)
2. **確認疲勞(approval fatigue)**:逐步簽核退化成 **93% 無腦點准**(Anthropic 2026-02);啟示見 Q3——別靠「事事確認」當把關。
3. **建議洪水 / AI 疲勞(AI fatigue)**:「When AI is always suggesting, completing, rewriting, and offering alternatives, it creates... **increasing the number of micro-decisions**」;AI fatigue = cognitive overload + emotional strain + behavioural disengagement。已有正式量表開發(《AI Fatigue in Human–AI Interaction》, ScienceDirect 2026)。(對齊 HAX G3 Time services based on context、G8 efficient dismissal)
4. **過度依賴(overreliance)**:人「接受 AI 建議即使建議是錯的」;信任一旦被錯誤打破,要很長無錯期才能重建。**Cognitive Forcing Functions** 可降低 overreliance(《To Trust or to Think》, ACM CSCW 2021,經典且仍被引)。
5. **介入/標記時機錯位**:agent 在錯的時機打斷(開會時丟非緊急更新)會惹人厭;好的做法是挑對 decision points 才現身(NN/g 2026)。**推論坑:AI 修訂標記若永遠不消/無法一鍵清乾淨,會變視覺噪音**——所以 accept-all / 一鍵清修訂是必要退場機制(對齊 Q2)。

**別犯前人錯的啟示(合併):** 把上面五坑當紅線。核心平衡:**改動要可見可審(對治坑1)**,但**別把「可見」做成永不消的噪音、別把「可審」做成事事簽核(對治坑2、3)**;用 undo + 風險分級 + 好的退場(accept-all/清標記)取代疲勞式確認;必要時加 cognitive forcing(強制人真的看一眼關鍵處)對治 overreliance。

---

## Q7. 表單/結構化文件特有——AI 填結構化欄位的互動設計

**結論:** 這塊最權威的產品案例是 **Airtable AI Fields / Field Agents** 與 **Notion AI Autofill**。兩者的共同設計語彙,和自由文編輯**不同**:AI 填的是**特定欄位**(有明確 output schema:single-select、number、JSON…),觸發時機**可設定**(手動/建立時/編輯時/排程),而且都有一條金律——**AI 不覆寫人手動編輯過的儲存格**。這對「結構化文件的 AI 填寫」是最直接可抄的權威範式。

**關鍵證據:**
- **Airtable AI Field / Field Agent**:AI 欄位在 cell 層自動檢索/分析/生成,存成**可篩選/分組/報表的結構化值**;field agent 由三件事定義:**source(讀哪些欄)、prompt/action(自然語言指令)、output format(single-select / multi-select / text / number / URL / image / JSON)**。可設「自動執行」;但**「Airtable will never automatically overwrite any cells that were edited by a human」**,即使開了自動生成。重新生成會覆寫既有 AI 內容,需按 Continue 確認。(Airtable Support "Using Airtable AI in fields" / airtable.com/guides 2025)
- **Notion AI Autofill**:hover 欄位 → 設定 AI Autofill → 選觸發時機(**manual / on page create / on page edits / schedule**)。分 Basic Autofill(摘要、標籤、翻譯)與 Custom Agent Autofill(多步、可搜尋)。2025 加 predictive autofill、依表格既有模式(類別/關鍵字/重複樣式)建議填值。(Notion Help Center "Notion AI for databases / autofill" 2025)

**別犯前人錯的啟示:** (1) 結構化 AI 填寫要**綁定明確 output schema**(選項/型別/JSON),不要讓 AI 回自由文再由人塞欄位——這是 Airtable/Notion 的共同做法,可直接抄。(2) **絕不覆寫人手改過的格子**——Airtable 明文把這當鐵律,是保護信任的關鍵不變量。(3) 觸發時機要可設(手動 vs 建立時 vs 編輯時 vs 排程),別只有「一鍵全填」一種暴力模式。(4) 逐格 AI 值同樣要可審/可回退,重生成前要確認(Airtable 的 Continue 二次確認)。

---

## 來源總表

**產品原廠官方**
- Microsoft 365 Copilot Blog — "Copilot in Word: New Capabilities for Document Workflows"(2025):https://techcommunity.microsoft.com/blog/microsoft365copilotblog/copilot-in-word-new-capabilities-for-document-workflows/4508974
- Microsoft Support — "Edit with Copilot in Word":https://support.microsoft.com/en-us/office/edit-with-copilot-in-word-647d5d14-eaec-4e8a-a574-7cefffa7f8f0
- Google Workspace Updates — "New Gemini capabilities in Google Docs..."(2026-04-22):https://workspaceupdates.googleblog.com/2026/04/new-gemini-capabilities-in-google-docs-help-you-go-from-blank-page-to-brilliance.html
- Google Workspace — Gemini in Google Docs 產品頁:https://workspace.google.com/products/docs/ai/
- OpenAI — "Introducing canvas"(2024-10):https://openai.com/index/introducing-canvas/
- OpenAI Help Center — "What is the canvas feature in ChatGPT":https://help.openai.com/en/articles/9930697-what-is-the-canvas-feature-in-chatgpt-and-how-do-i-use-it
- Cursor 使用指南(社群彙整,含官方行為):https://github.com/dazzaji/Cursor_User_Guide;Cursor Forum 診斷串:https://forum.cursor.com/t/regression-ai-edits-applying-automatically-without-diff-approval-ui/154887
- GitHub — "Coding Agent for GitHub Copilot"(press release):https://github.com/newsroom/press-releases/coding-agent-for-github-copilot
- VS Code Blog — "Introducing GitHub Copilot agent mode (preview)"(2025-02-24):https://code.visualstudio.com/blogs/2025/02/24/introducing-copilot-agent-mode
- GitHub Docs — Responsible use / Agents(HITL confirmation):https://docs.github.com/en/copilot/responsible-use/agents
- Notion Help Center — "Notion AI for databases / Autofill":https://www.notion.com/help/autofill
- Airtable Support — "Using Airtable AI in fields":https://support.airtable.com/docs/using-airtable-ai-in-fields;Airtable — AI agents 平台頁:https://www.airtable.com/platform/ai-agents

**Anthropic 原廠研究**
- "Measuring AI agent autonomy in practice"(2026-02-18):https://www.anthropic.com/research/measuring-agent-autonomy
- "Our framework for developing safe and trustworthy agents":https://www.anthropic.com/news/our-framework-for-developing-safe-and-trustworthy-agents

**HCI 準則(權威)**
- Microsoft HAX Toolkit — Guidelines for Human-AI Interaction(18 條;Amershi et al. 2019 CHI,Toolkit 持續維護):https://www.microsoft.com/en-us/haxtoolkit/ai-guidelines/;原論文:https://www.microsoft.com/en-us/research/publication/guidelines-for-human-ai-interaction/
- Google PAIR — People + AI Guidebook(六章,含 Feedback+Control、Explainability+Trust):https://pair.withgoogle.com/guidebook/;更新說明:https://medium.com/people-ai-research/updating-the-people-ai-guidebook-in-the-age-of-generative-ai-cace6c846db4
- Nielsen Norman Group — AI 主題頁:https://www.nngroup.com/topic/ai/;"AI Agents as Users":https://www.nngroup.com/articles/ai-agents-as-users/;legibility 主題:https://www.nngroup.com/topic/legibility/

**溯源標準**
- C2PA / Content Credentials(v2.2 2025-05、v2.3 2025-12):https://c2pa.org/;Wikipedia Content Credentials(彙整標準沿革,附一手連結):https://en.wikipedia.org/wiki/Content_Credentials
- IPTC 2025.1 AI metadata 欄位(Numonic 技術解說,附 IPTC 一手):https://www.numonic.ai/blog/iptc-2025-c2pa-ai-provenance-metadata

**頂會/學術論文**
- Buçinca, Malaya, Gajos — "To Trust or to Think: Cognitive Forcing Functions Can Reduce Overreliance on AI"(ACM CSCW 2021):https://dl.acm.org/doi/10.1145/3449287
- "AI Fatigue in Human–AI Interaction: Conceptual Framework, Scale Development and Validation"(ScienceDirect 2026):https://www.sciencedirect.com/science/article/pii/S2451958826002605

**二手趨勢佐證(明確標註為非一手,僅補趨勢方向,不作事實依據)**
- Smashing Magazine — "Designing For Agentic AI: Practical UX Patterns For Control, Consent, And Accountability"(2026-02):https://www.smashingmagazine.com/2026/02/designing-agentic-ai-practical-ux-patterns/
- VentureBeat — "ChatGPT's Canvas now shows tracked changes":https://venturebeat.com/ai/chatgpts-canvas-now-shows-tracked-changes
- the-decoder — "Microsoft Copilot in Word can now track changes":https://the-decoder.com/microsoft-copilot-in-word-can-now-track-changes-and-manage-comments/
- Swarmia / Prosus / Akira(2026 agent 自主度與 ambient/background 趨勢彙整)

---

### 附:與本研究最相關的 HAX 18 準則子集(供設計對照)
G3 Time services based on context · G8 Support efficient dismissal · G9 Support efficient correction · G10 Scope services when in doubt · G11 Make clear why the system did what it did · G15 Encourage granular feedback · G16 Convey the consequences of user actions · G17 Provide global controls · G18 Notify users about changes。
(來源:Amershi et al., "Guidelines for Human-AI Interaction", CHI 2019;Microsoft HAX Toolkit 現行維護版。)
