---
title: 訪談流程重設計 — AI 輔助任務裁剪 + 分階段彈性 + 態度收尾(研究紀錄)
date: 2026-07-09
status: research(待維護者審 → ADR 0028 → plan)
audience: agent-primary(也給人)
scope: apps/api app/interview/*(ledger/scribe/consultant/service)+ routes/interview + apps/web 訪談面板/widget
---

# 訪談流程重設計:AI 輔助任務裁剪 + 分階段彈性 + 態度收尾

> 承 [§16.16](2026-07-06-consultant-not-formfiller-redesign-research.md) onboarding 修復後的**真人實測**
> (session `eb2af457`)。修好了「開場不再幻覺職類」,但暴露更深的斷點:**職類選了、任務進不了
> 文件**,連鎖出「態度轟炸」與「深聊不收斂」。本檔把問題釘死、找權威作法、收斂設計決策,
> 補齊 ADR [0027](../adr/0027-interview-engine-v2-consultant-agent.md) 沒做完的願景。
> **不重炒**既有 §15 的 DACUM/O*NET/BEI 基礎研究,只研究本次新機制。

## 1. 觸發:真人實測的硬證據(session eb2af457;受訪者=全端網頁工程師)

- **25 回合 → 結構化產出:0 任務、0 OPKS、0 知識技能,只有 39 條態度建議**(A01 親和關係×21、
  A02×7、A03×6、A04×2、A06×2、A05×1)。evidence 39 筆全 verified(引文逐字是真的,但**歸類是垃圾**
  ——「選了」「對」「舊電腦截圖」都被標成「親和關係」)。
- **文件狀態**:`ocs_code=INM3514-001v4`(職類**有**設)、**tasks=0**(任務**沒**進場)。
- **維護者回報**:顧問叫他〔選職責〕他選了,但**沒叫他〔選任務〕所以沒選**。
- **因果鏈**:選職類只寫 `ocs_code`、不拉任務;任務要另外手動〔選職責〕→〔選任務〕兩段挑
  → 文件停在「有職類、零任務」→ 書記每回合 `task_keys=[]`/`slot_paths=[]`,唯一能寫的通道剩
  **態度池**(文件層、不需任務)→ prompt「能記就記」驅使它把每句話硬塞一個最近態度 → 無去重/
  無上限累積 39 條。

**問題分層(因果序,非三個獨立 bug)**:
- **A【樞紐】** 職類→任務斷點:onboarding 只做到選職類,「任務進場」整棒斷掉;顧問在死區還
  回頭亂搜職類(幻覺「組織法務人員」——被網站主題「律師」語意帶偏)。
- **B** 態度轟炸:A 的下游(無正經通道)+ 逐句抽取態度本質就錯(違反 iCAP 2–4、故事佐證)。
- **C** 深聊不收斂:A 的下游(文件無任務→帳本無具體缺口→顧問空轉重複 STAR 框架)。

## 2. 維護者確認的顧問流程(北極星 = 取代顧問;對齊 DACUM/iCAP)

1. 拿到大概故事 → **確認職位**(可多選、任務池聯集、**主代碼一個** = codes[0])
2. **AI 預勾官方任務** → 一鍵套用 → **補缺任務**(官方池外才自訂)
3. 逐任務**細談 OPKS**
4. **收尾態度**(整體、2–4、故事佐證)

**最高原則(維護者原話)**:「不要被流程綁死、不要做死機器,是專業顧問」——上列是**骨架
(預設的下一步),不是鎖**;全程任何時刻冒出新任務/OPKS/態度都能**當場加**。
**多職位**:編輯器已支援多選、任務池取聯集(維護者告知;實作時驗 `setOccupations`/build-tasks)。

## 3. 研究錨(2026 權威;新機制)

### 3.1 AI 建議 + 人確認(HITL)——Eightfold「Trust but validate」
Eightfold/Workday:AI 從全球 job description + 個人經歷**推斷**技能/任務,呈現時**附清楚理由**
(為何建議、如何分類 core/emerging/sunsetting、何時分析),HR「review & validate with confidence」。
HITL 預標註實務:AI 預標 → 標註變成**快速 confirm/reject**,大幅降人力;精確度靠人**剔除誤選**。
→ **背書 D1**:AI 預勾任務、每項附理由、人一鍵確認/剔除。

### 3.2 Mixed-initiative / agenda-based——學界明確棄 rigid FSM
對話管理研究:主動權(control over dialogue flow)在系統與使用者間**持續交換**;系統需「評估話題
偏離與整體目標的關聯,決定**跟隨使用者主動權**還是**守住自己的議程(agenda)**」。領域已從
rigid state machine 移向 agenda + planning + POMDP 的彈性框架。
→ **背書 D2**:骨架 = **agenda(可被暫時打斷、之後收回)**,不是強制狀態機。這正是「別做死機器」。

### 3.3 態度 = 跨故事整體編碼(BEI thematic analysis)——非逐句
BEI/行為面談實務:準備 **8–10 個 STAR 故事**、覆蓋約 **6 個職能面向**;職能編碼用**主題分析**
(跨多個故事**反覆出現**的主題才立碼,迭代檢視)。**不是**逐句貼標籤。
→ **背書 D3**:態度從**全逐字稿整體**推斷少數幾條(iCAP 文件層 2–4),每條要跨故事的行為佐證。

### 3.4 自動化偏誤 / rubber-stamp——預勾要保守 + 附理由(反盲簽)
自動化偏誤(HDSR 2026「Bias in the Loop」、Springer 2026):人**傾向接受**自動建議、忽略矛盾證據;
「**越被認為好用的系統,連錯誤建議都越容易被採納**」。有效設計要**逼使用者看到推理、非只看結論**;
純「按 confirm」= rubber stamp = 無效控制。強調「AI 可能出錯」比強調準確率**更能**降低盲從。
→ **背書 D4**:一鍵套用要「**低摩擦但有據**」——保守預勾(高信心才勾、低信心列出不勾)、
每項顯示引文證據、可逐項剔;而非全勾盲簽。與維護者「讓我套用就好」的張力用此化解。

### 3.5 既有基礎(引用,不重炒)
DACUM 面板從「標準任務清單出發再裁剪」、O*NET Core Task 門檻、iCAP A01–A14/STAR/ABCD、
12-Factor Agents、GPT-4.1 prompting、arXiv 2410.01824 失敗模式 = 見 §15/§16 與 golden sample。

## 4. 設計決策(修訂/延伸 0027)

- **D1 職類→任務接軌 = AI 驅動「既有 v2 編輯器 pickers」(非另做 widget、非復活舊 CopilotKit)**。
  維護者定調「調用編輯器選單」——**復用** `OccupationPicker`(選職位)/`UnitPickerMenu`(選職責)/
  `TaskPickerMenu`(選任務):它們**已帶 `SourceLine` 引用、已有「自動勾選」(applyDefaults 規則預選)、
  已接 autosave 單一寫入路徑**。要補的縫=把「規則預選」升級為「**AI 依故事預選 + 每列附引文理由**」,
  並讓訪談引擎能**驅動開啟對的 picker 並預填**(`TurnResult.widget` 從「渲染自訂 UI」改為「**指令**:開
  哪個 picker、預填 query/預勾哪些、附理由」)。多職位→任務池聯集(編輯器已支援);主代碼 codes[0]。
  **補缺**:套用後顧問問「官方沒列、但你有做的?」→ 自訂任務(既有 add_custom_task 建議層)。
  **退役參考**:舊 `InterruptHandlers`(CopilotKit+LangGraph `jd_authoring`)的 `TaskCurator`/`ProfilePicker`/
  `CurateKs*` 是**理想 UX 樣張**(勾/改/刪/增+來源標),但綁退役棧——**移植樣式、不引其框架**(ADR 0027
  §6 inv.9 舊棧待清)。
- **D2 分階段 = agenda 非 gate**。帳本 phase 序:`onboarding_occupation → task_curation →
  opks_deep → attitudes`,但 next_gap 只給**建議下一步**;新任務/OPKS/態度**全程可加**,帳本追進度
  不擋新增。實作:phase 由 doc 狀態**推導**(無職類→occupation;有職類無任務→curation;有任務→
  opks;OPKS 足→attitudes),避免存不可重算狀態(12-Factor F5)。
- **D3 態度改收尾整體 pass**。**移除書記逐回合態度抽取**(record_attitude_pool 退役);態度在**收尾**
  由專責 pass 讀**全逐字稿** → 提 2–4 條、每條綁**最強故事引文** + 官方 A 碼;過程中僅在**明確聽到
  某態度的具體故事**時機會性記一條(非逐句)。去重 + 上限 MAX_A 當硬保險。
- **D4 反 rubber-stamp**。預勾**保守**(高信心才勾);widget 每項顯示證據 + 「AI 可能看錯,請掃一眼」
  的輕提醒;accept-all 可用但可逐項剔。沿用 0025 風險分層(選職類/任務清單 = 高風險 → 選單阻斷確認;
  細項/OPKS = 低風險 → 自動落地 + 待確認標記批次收)。

- **D5 套用/核准互動模型(維護者指定:像 Claude Code 選單)**。研究錨:LangGraph HITL 標準四動作
  (approve / edit / reject-with-feedback / respond);Claude Code 核准(allow once/always、deny **附訊息**
  → AI 據以調整、可改輸入);mixed-initiative(人給目標、AI 生替代、人 inspect/accept/reject/refine,
  **拒絕帶理由回饋** AI 重出,計畫=可編輯結構)。**Anthropic 重磅教訓**:Claude Code 核准率 93%
  = 逐動作提示會被**習慣性盲簽**;對策**不是加警告,而是「定義邊界內自由 + 只在少數高風險 interrupt」**。
  → 落地原則:
  - **少而準的 interrupt,不逐項煩人**。高風險結構決策(**選職位 + 選任務**)= **一次** widget 選單;
    細項/OPKS = 自動落地 + pending 標記 + **自然節點批次收** + undo(0025);態度 = **收尾一次整體審**。
  - **任務裁剪 widget 的動作集**(對映 LangGraph/Claude Code):
    ① **套用**(approve:落已勾集合)② **選**(edit:逐項勾/取消 = 部分套用)
    ③ **討論/退回附理由**(reject+respond:打字「不對,因為…我其實做 X」→ 當一回合回饋 → AI 重出清單)
    ④ **跳過**(defer:稍後再談,不擋對話)。
  - **每列顯示**:任務名 + 官方碼 + **引文理由**(觸發的員工原句)+ **官方溯源**(編輯器任務都帶引用)。
  - **拒絕 = 回饋非丟棄**:記「為何提議 / 為何被拒」,AI 重出更準(mixed-initiative;避免鬼打牆)。
  - **同一動作集**推廣到態度收尾審與細項批次收(一致的心智模型;非每處自創互動)。
  - **載體位置(修 bug)**:高風險選單 = **on-demand modal/popover**(在決策當下彈出、在視線內),
    非釘在滾動區頂端。**現況 bug**:`InterviewPanel` 把 `SuggestionReview` 放在對話串**最上方**、
    對話自動捲到底 → 清單一長就被推出視線(維護者實測「要拉到最上面才看得到」)。修:批審改**面板
    底部常駐「N 項待審」列/鈕**(近輸入框),點開才展開;結構決策走 picker modal,不進滾動串。

- **D6 缺項提醒 = 官方清單當檢查表反問完整性;官方參考、員工實際為準**(維護者兩點;對齊 O*NET
  relevance + write-in、DACUM Verify、job-analysis「comprehensive」)。
  - **完整性探測 tier**(帳本):官方任務池(選定職類聯集)= **檢查表**。帳本追每個官方任務處置:
    `covered`(在文件+細談)/`declined`(員工說不做→排除,記 `ledger_state.declined` 因文件無此任務、
    不可從 doc 重算)/`unasked`。**next_gap 新增**:AI 預勾 + 主動講的落地後,把**未涵蓋的官方任務
    成組反問**「官方這職類還有 A/B/C,你有做哪些?」→ 有→加+深談;沒有→標 declined(不再問、
    留「考量後排除」痕跡)。全部 covered-or-declined → 問**寫入項**「官方沒列、你卻常做的?」(write-in)。
  - **缺職責**:官方職責(unit)無任一任務被涵蓋 → 同法反問整個職責。
  - **官方參考、實際為準**:官方 = 候選檢查表;**presence 由員工 yes/no 定、寫入項第一級**,不強塞。
    **OPKS 同理**:官方 K/S/O/A 池 = 候選**類目**;實際**值/行為**依員工真需真產出(自訂通道第一級)——
    例:官方技能「測試工具使用能力」,實際填「會用 Postman/pytest」(員工具體)。JD = **員工定義、官方參照**;
    顧問級豐度來自員工的具體,不是官方樣板。**沿用**兩通道書記(池/自訂)+ 細項槽已體現此原則,強化不弱化。
  - **效率(避免審訊感)**:**成組**探測非逐項;尊重飽和(STALL_K);AI 已預勾/已談的不重問——「少而準」。

- **D7 人機共編同文件:入口可不同、UI 盡量同一;AI 變更=追蹤修訂樣式**(維護者定調)。
  人與 LLM 是**同一份文件的協作者**;寫入早已同路(autosave/persist 單一寫入路徑,ADR 0020/0025),
  本決策把**呈現**也收斂成同一套。研究錨:Tiptap Content AI(2026)AI 編輯=同編輯器內 tracked
  changes、逐筆 accept/reject/acceptAll;Word Copilot=同文件 co-author+審計軌跡;Fluent 2(2026)
  =AI 嵌既有介面、同元件維持視覺行為對齊;HaLLMark=AI 文字高亮+互動溯源;design-system
  parity(Material 3/Carbon)=同元件多入口;in-place editing 研究=改動落原位比 chat 可控。
  - **結構選擇**(職位/職責/任務):**同一 pickers**(D1)。入口不同(人點工具列鈕 vs 訪談引擎
    widget 指令開啟+預填),元件同一;AI 呼叫版**多掛**:預勾+每列引文理由。
  - **文件格**(細項/OPKS):AI 直寫(`review=pending`)在 **JobDocTable 同格**以追蹤修訂樣式呈現
    ——pending 高亮+「AI」徽章、改值=舊值刪除線+新值、新增=「新」標;hover 看引文(溯源);
    格旁逐筆接受/拒絕 + 「本段一次收」批次 + undo(0025 既定)。**人改的格無標記**(human_touched
    既有機制)。
  - **SuggestionReview 置頂清單退役**:合流 D5 載體修正——建議改為「文件內 inline 樣式 + 面板底部
    『N 項待審』計數鈕」,不再塞聊天串頂。
  - **資料縫**:pending/新增標記的真相來源=`interview_evidence(review=pending)`+`interview_suggestions
    (doc_path)`;web 需一個 path→狀態/引文 的映射查詢(實作時定形,plan 處理)。

- **D8 結構=點選、深度=對話(v2.2;真人實測 65b9aa3d 驅動;0028 D1/D5 範圍內細化,不另開 ADR)**。
  維護者假設「少打字、直接彈職責/任務選單、先選大概再修」→ **權威全面驗證成立**:
  - **打字負擔實證**(survey methodology):答一題開放題時間=4–6 題選擇題;開放題無回應率
    平均 18%(選擇題 1–2%),高負擔開放題達 50%+(Pew);最佳比例=每 10–15 選擇配 1 開放。
  - **Anthropic《Building Effective Agents》(正典)**:「workflow 給**可預測**的建結構、agent 探索
    **不可預測**的」;先選最簡單方案。→ 職類/職責/任務=可預測(官方清單存在)→ 選單 workflow;
    內隱知識故事=不可預測 → 顧問 agent 對話。
  - **2026 混合式共識**:結構化 UI 處理已知決策、對話處理開放探索(Notion/Linear/Copilot 形);
    對話式收集完成率 85% vs 表單 22%、快 30–45%;Hybrid-Trap 警告=混合要有原則非隨機。
  - **Google 對話設計**:chips 能點就別打;**PAIR Guidebook**:借用既有心智模型(=復用編輯器
    pickers)、回饋要可見其效果;**arXiv 2606.20630**:自主權移轉——開局 agent 主導、迭代人主導。
  - **DACUM**:duty→task 兩層=標準結構(維護者「先職責再任務」即此)。
  - 落地(P 系列):
    - **P1 選完職類立刻主動彈**(不等打字):新 `interview:curation` 隨叫端點(拿至今發言預勾;
      沒把握不勾但**全檢查表照列**)→ `CurationDialog` 升級**一窗兩步**(步1 職責勾選 →
      步2 所選職責的任務,AI 預勾+引文)→ 帶入。零打字即可鋪滿任務盤。
    - **P2 中途加選職類回路**(真人實測:顧問三度搜到「網站系統設計人員 1.0」卻無機制驅動加選,
      全端後半內容無家可歸 → 18 個 K 硬塞錯任務):widget 觸發放寬=顧問本回合搜過職類**且**
      top hit ∉ 現有 codes → 彈 occupation picker;顧問 prompt 補「工作明顯超出現有職類 →
      明講建議加選(可多選)」。
    - **P4 chips 僅限 meta 動作**(跳過/沒有/先記到這);**深聊不選單化**(BEI 故事=開放題
      不可取代的那一題;開放額度全留給深聊)。
    - **P5 書記三行修正**(實測 65b9aa3d):①內容不屬任何現有任務→`add_custom_task` 提議,
      不硬塞;②K/S 判準(知道=K、會操作=S;實測 K=18/S=0 全偏 K);③玩笑/比喻不當事實記
      (「AI 馴獸師」進了 outputs)。

## 5. 對 ADR 0027 的修訂點(開新 ADR 0028;0027 Accepted 不改內容)

- 0027「onboarding 併入對話 + AI 預勾清單」**補實作**(0028 定 widget 契約 + 帳本 phase 推導 +
  多職位聯集裁剪)。
- 0027 §3.3「態度 = 書記提建議(員工確認)」**修正**為 D3(收尾整體 pass;移除逐回合抽取)。
- 帳本 next_gap 增 `task_curation` phase(§16.16 的 ONBOARD_TASKS 升級為「AI 預勾裁剪」而非「叫你
  自己去選任務」)。
- 0025 批審**呈現載體**修正(D5/D7):建議清單置頂 → 文件內追蹤修訂樣式 + 面板底部計數;
  **寫入路徑與風險分層不變**(仍 applyAccepted→persist 單一路徑)。
- 帳本增**完整性檢查表** tier(D6):官方任務 covered/declined/unasked 三態,`declined` 存
  `ledger_state`(文件無此任務、不可重算);write-in 探測入收尾前流程。

## 6. 待決 / 風險

- **裁剪組件放哪**:顧問多一個「產預勾清單」職責 vs 獨立裁剪 pass(傾向獨立 pass,顧問維持無寫入
  純對話;widget 資料由 service 組)。→ ADR 定案。
- **phase 純推導 vs 存狀態**:傾向純推導(F5),但「補缺任務問過沒」需一個 flag(可存 ledger_state)。
- **多職位主代碼**:codes[0] = 第一順位;UI 已有排序(archived 設計)。驗編輯器現況。
- **態度收尾 pass 的模型/成本**:沿用 backstop(便宜模型)或獨立;收尾一次,成本可控。
- **回歸**:§16.16 的 onboarding 測試 + 既有 32 訪談測試不可壞;widget 走既有 setOccupations 路徑。
- **兩套流程並存(前端現況)**:舊 `intake` 流程(CopilotKit + LangGraph `jd_authoring` + `InterruptHandlers`)
  與 v2 `documents/[id]` 流程共存(CopilotKit 仍掛 `Providers`/`api/copilotkit/route.ts`)。本次**只動 v2**;
  舊棧清理另案(勿在此擴大戰線)。移植 `TaskCurator` UX 時只搬樣式、不引 CopilotKit。
- **pickers 現為手動觸發**(modal/popover 由使用者點按鈕開);要加「由訪談引擎程式化開啟 + 預填」的
  控制通道(page 級狀態:面板收到 widget 指令 → 開對應 picker 帶預填)。驗 `useSetOccupations`/
  build-tasks 是否吃「多職位聯集 + 預勾集合」。

## 7. 出處

- Eightfold「Trust but validate」skills validation — https://eightfold.ai/blog/trust-but-validate/
- Workday × Eightfold Career Hub(推斷+驗證) — https://eightfold.ai/wp-content/uploads/Workday_Career_Hub_Paper.pdf
- Plan-Based Dialogue Management 綜述(Springer 2022) — https://link.springer.com/article/10.1007/s12559-022-09996-0
- What is Mixed-Initiative Interaction?(Horvitz 系) — https://www.researchgate.net/publication/238068180
- Controllable Mixed-Initiative Dialogue(ACL 2023) — https://aclanthology.org/2023.acl-short.82.pdf
- Bias in the Loop: How Humans Evaluate AI Suggestions(HDSR 8.2, 2026) — https://hdsr.mitpress.mit.edu/pub/nrcn4h7d
- Warning about AI error mitigates bias acquisition(Springer, Cognitive Research 2026) — https://link.springer.com/article/10.1186/s41235-026-00726-w
- STAR/BEI 故事數與職能面向 — https://www.extern.com/post/behavioral-interview-questions-star-method-guide
- LangGraph Human-in-the-Loop(approve/edit/reject/respond 四動作) — https://docs.langchain.com/oss/python/langchain/human-in-the-loop
- Claude Code — Handle approvals and user input(deny 附訊息 → AI 調整) — https://code.claude.com/docs/en/agent-sdk/user-input
- Anthropic — Claude Code auto mode(93% 核准率 → 邊界內自由,非逐動作提示) — https://www.anthropic.com/engineering/claude-code-auto-mode
- Mixed-initiative 迭代精修 / 可編輯計畫(AIPOM)— AI Agentic Programming Survey — https://arxiv.org/html/2508.11126v1
- Feedback by Design: 對話代理的使用者回饋障礙(arXiv 2026) — https://arxiv.org/html/2602.01405v1
- Anthropic — Building Effective Agents(workflow=可預測/agent=不可預測;最簡先行) — https://www.anthropic.com/engineering/building-effective-agents
- Google PAIR — People + AI Guidebook(Mental Models / Feedback+Control) — https://pair.withgoogle.com/
- Design Principles for Human-Agent Interaction(自主權移轉;arXiv 2606.20630, 2026)
- 開放 vs 選擇題負擔實證 — https://www.nngroup.com/articles/open-ended-questions/ 、 https://www.surveymonkey.com/learn/survey-best-practices/comparing-closed-ended-and-open-ended-questions/
- Google 對話設計 chips — https://developers.google.com/assistant/conversation-design/chips
- 2026 混合式共識/完成率 — https://www.aiuxdesign.guide/patterns/conversational-ui 、 https://gnosari.com/blog/conversational-data-collection 、 https://markswebb.com/insights/conversational-ui-ai-agents-hybrid-trap/
- Shape of AI — AI 互動 UX 模式庫 — https://www.shapeof.ai/
- assistant-ui — Form-Filling AI Copilot / Generative UI(AI 填現成表單、人調整) — https://www.assistant-ui.com/examples/form-demo
- 混合式:AI 起草 + 引導式人審(降全自動風險)— arXiv 2312.09198
- Tiptap Content AI — AI 編輯以 tracked changes 呈現於同編輯器(accept/reject API) — https://tiptap.dev/docs/content-ai/capabilities/ai-toolkit/agents/review-changes/tracked-changes
- Microsoft — Human-centered Design for Agents / Fluent 2(AI 嵌既有介面、同元件對齊) — https://learn.microsoft.com/en-us/agents/design-guidelines/human-centered-design 、 https://fluent2.microsoft.design/
- HaLLMark — AI 寫作溯源高亮與互動視覺化(arXiv 2311.13057)
- Designing For Agentic AI(Smashing Magazine 2026-02;approval gates/undo/editable plans) — https://www.smashingmagazine.com/2026/02/designing-agentic-ai-practical-ux-patterns/
- O*NET 任務相關性 Core/Supplemental 分級 — https://www.onetonline.org/help/online/scales
- O*NET write-in tasks / emerging tasks(在職者可加官方外任務)— https://www.onetcenter.org/reports/EmergingTasks_RevisedApproach.html
- DACUM 三階段(含 Verify 驗證)— https://www.eku.edu/in/guides/dacum-occupational-analysis/
- Job Task Analysis 通則(完整反映日常、probe、Why)— https://omep.org/the-art-of-job-task-analysis/
- 既有前端件:`OccupationPicker`/`UnitPickerMenu`/`TaskPickerMenu`(引用+自動勾選+autosave)、
  退役參考 `InterruptHandlers`(CopilotKit `TaskCurator` 等)、bug 點 `InterviewPanel`(SuggestionReview 置頂)
- 既有:§15/§16 研究紀錄、golden sample、ADR 0025/0027
