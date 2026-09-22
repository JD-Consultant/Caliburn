# ADR 0028 — 訪談流程 v2.1:AI 驅動共用編輯 UI(追蹤修訂)+ 議程化彈性流程 + 完整性檢查表 + 態度收尾

- **狀態**:Accepted(2026-07-09)。
- **研究依據**:[`../specs/2026-07-09-interview-flow-task-curation-and-flexibility-research.md`](../specs/2026-07-09-interview-flow-task-curation-and-flexibility-research.md)
  (D1–D7;真人實測 session `eb2af457` 診斷 + Eightfold/O*NET/DACUM/mixed-initiative/
  automation-bias/LangGraph-HITL/Claude Code/Tiptap/Fluent 2 等 2026 權威錨)。
- **關聯**:四組件=ADR 0027(**本 ADR 修正其態度通道與 onboarding 實作形**);共編權限=
  ADR 0025(風險分層沿用,**修正其批審呈現載體**);互動模式=ADR 0020(沿用);
  知識包=ADR 0021(pickers 資料源,沿用);§16.16 onboarding 帳本縫(本 ADR 升級其 ONBOARD_TASKS)。

## 脈絡

§16.16 修復後真人實測(2026-07-09,session `eb2af457`):25 回合深聊,結構化產出
**0 任務、0 OPKS,僅 39 條垃圾態度**(A01×21;「對」「選了」都被貼標)。因果鏈:選職類
只寫 `ocs_code` 不拉任務 → 文件停在「有職類、零任務」死區 → 書記 `task_keys=[]`,唯一可寫
通道剩態度池,「能記就記」逐句轟炸;顧問無具體缺口可導,空轉重複問法,甚至回頭亂搜職類。
根本缺口=0027 定的「onboarding 併入對話 + AI 預勾清單(選單阻斷確認)」**沒做完**:
`TurnResult.widget` 恆 None、職類→任務接軌斷棒、批審清單釘在聊天串頂端看不見。

維護者確認顧問流程骨架並加三原則:「不要被流程綁死、不要做死機器」;「官方是參考,
員工實際工作為準」;「人跟 LLM 共同編輯這份文件——入口可不同,UI 盡量同一」。

## 決定

### 1. AI 驅動「既有編輯器 pickers」,不另做聊天 widget(D1/D5 載體)

職位/職責/任務的結構選擇**復用** `OccupationPicker`/`UnitPickerMenu`/`TaskPickerMenu`
(已有 SourceLine 引用、「自動勾選」、autosave 單一寫入路徑)。訪談引擎經
`TurnResult.widget` 送**指令**(開哪個 picker、預填 query、預勾哪些、每列引文理由),
前端開同一元件。多職位=聯集任務池、主代碼 `codes[0]`。舊 CopilotKit `InterruptHandlers`
(TaskCurator 等)=UX 樣張,**只移植樣式不引其框架**(退役棧)。

### 2. 議程化但彈性的流程(agenda,非 gate;D2)

階段序:`故事 → 確認職位(可多選)→ AI 預勾任務+補缺 → 逐任務 OPKS → 收尾態度`。
phase 由 doc 狀態**推導**(不可重算者才存 `ledger_state`);next_gap 只給建議下一步。
**全程任何時刻**可加新任務/OPKS/態度(mixed-initiative:跟隨員工主動權,之後收回議程);
帳本追進度、**永不擋新增**。學界共識:棄 rigid FSM,用 agenda + 主動權交換。

### 3. 完整性檢查表:官方=候選盤,員工實際=準(D6)

官方任務池(聯集)=**檢查表**,帳本追三態 `covered/declined/unasked`(declined 存
ledger_state)。AI 預勾+主動講的落地後,**成組反問**未涵蓋官方任務(「還有 A/B/C,你有做
哪些?」;O*NET relevance 式確認,非誘導)→ 無=declined 留痕不再問;全處置後問
**write-in**(「官方沒列你卻常做的?」)。缺職責同法。**清單確認求廣度、故事追問求深度**
——兩種問法分開(BEI 挖細節仍不帶預設答案)。OPKS 同原則:官方=類目候選,實際值=
員工具體(兩通道書記已體現,強化不弱化)。

### 4. 態度退出逐回合書記,改收尾整體 pass(D3;修正 0027 §3.3)

移除 `record_attitude_pool` 逐回合通道(39 條轟炸的機制根)。態度=收尾專責 pass 讀
**全逐字稿**,提 2–4 條(iCAP MIN_A–MAX_A),每條綁最強故事引文+官方 A 碼;過程中僅在
明確聽到具體態度故事時機會性記(非逐句)。去重+上限=硬保險。依據:BEI 跨故事主題編碼。

### 5. 核准互動:少而準的 interrupt + 四動作(D4/D5)

高風險結構決策(選職位、選任務)=**一次** picker 選單:**套用(approve)/選(edit)/
討論退回附理由(reject+respond→AI 重出)/跳過(defer)**——對映 LangGraph HITL 與
Claude Code 核准語彙。低風險(細項/OPKS)=自動落地+pending 標記+**自然節點批次收**+undo
(0025)。反 rubber-stamp:**保守預勾**(高信心才勾)、每項附引文理由、可逐項剔
——Anthropic 教訓:逐動作提示 93% 核准率=習慣性盲簽;對策是邊界內自由+少數高風險 interrupt,
不是加警告。

### 6. 人機共編同文件:入口可不同、UI 同一,AI 變更=追蹤修訂(D7;修正 0025 批審載體)

寫入早已同路(autosave/persist);呈現收斂:AI 直寫(`review=pending`)在 **JobDocTable
同格**以追蹤修訂樣式呈現(pending 高亮+「AI」徽章、舊值刪除線+新值、新增標「新」、
hover 引文溯源),格旁逐筆接受/拒絕+「本段一次收」+undo;人改的格無標記。
**SuggestionReview 置頂清單退役**→ 面板底部「N 項待審」計數鈕 + 文件內 inline。
依據:Tiptap tracked-changes、Word Copilot 審計軌跡、Fluent 2 同元件對齊、HaLLMark 溯源。

## 後果

- **+** 職類→任務斷棒接上:深聊有真任務可填,書記有正經通道(態度轟炸機制性消失),
  顧問有具體缺口可導(空轉/重複問法收斂)。
- **+** 完整性有確定性保證(檢查表三態),且「官方參考、實際為準」白紙黑字。
- **+** UI 一套:人與 AI 改動同格呈現、同路寫入,溯源可 hover;批審不再看不見。
- **−** 前端工程量:pickers 加「程式化開啟+預填+理由列」控制通道、JobDocTable 加
  pending/diff 渲染、path→狀態映射查詢——分 bite-size task 逐一驗。
- **−** 檢查表反問若做壞會像審訊:靠成組探測、STALL_K 飽和、已談不重問緩解;
  sim + 真人試訪驗語感。
- **風險**:AI 預勾精確度不足會放大 automation bias → 保守預勾 + 引文理由 + 可剔;
  預勾品質入 interview_sim 量測。
- **退役**:`record_attitude_pool` 通道、SuggestionReview 置頂形;舊 CopilotKit 棧仍待清
  (0027 inv.9,不在本 ADR 擴大)。

## Limitations(誠實記載)

沿 0027:單信息源、純文字。新增:檢查表僅覆蓋**選定職類聯集**的官方池(跨職類借用靠
write-in 與顧問追問);AI 預勾的 precision/recall 未經校準(plan 內建 sim 量測項)。
