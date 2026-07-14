# 0033. 訪談議程 v4:事件驅動議程=顧問議程工具+覆蓋 artifact+事件收割 pass(退役 next_gap 梯子)

日期:2026-07-14
狀態:Accepted

## 背景

Live 新手 persona 訪談(session `330a0bed`,70 分鐘 28 輪)驗屍:P(行為指標)
**零筆**、進度緩慢、單一故事連鑽十輪。DB 稽核(130 筆守衛裁決、95 ✓/0 ✗)定位四個
根因,共同體質是**驅動層=十幾條散落確定性條件的隱式協調、無單一決策點**,斷法全是
「靜默斷」;寫入層(op→verify→`_pending`→人審)零失誤。細節與證據:
`docs/specs/2026-07-14-interview-agenda-architecture-research.md` §1。

- BUG-1:空白文件(`ocs_content` 缺席/None)上,裁剪綠字直落被 verify permission
  全擋(T5c 漏測處女文件)。
- BUG-2:書記 prompt 無一字提 `draft_indicator`;behavior-indicator 教材兩條注入路
  皆斷(書記不吃 skill;顧問載入條件 `gap==indicators` 從未成立)。
- BUG-3:`next_gap` 線性梯子(預算槽→細項槽→**才到 P/K/S**)×盤 bulk 勾 20 任務
  → P 排在數十槽之後,`TURN_BUDGET=40` 內數學上不可達。
- BUG-4:`note_attempt` 的 progressed=「書記有任何落地」→ attempts 永遠歸零、
  飽和讓路(STALL_K)永不觸發;反向 curation 落地不計進帳→裁剪縫兩輪即永久熄火。

深層診斷:把「顧問訪談」實作成「機械填表」是**範式錯配**——BEI 黃金標準
(McClelland/Spencer)的訪談單位是**事件故事**,能力證據靠**事後編碼**萃取;
P 是「從敘事提煉的可觀察證據」,不是等被填的空格,而現行無任何零件在做提煉。

先例研究(同 spec §2):Anthropic Building Effective Agents/multi-agent lead
agent(規劃在行動 agent 迴圈內+計畫外化 memory+判準寫 prompt)、OpenAI agent
指南(單腦迴圈、決策=tool call、guardrails 外圍)、**Microsoft SK 獨立 Planner
廢除**(疊在模型上的 planning 邏輯「reduce the speed, cost, and accuracy」)、
2026 共識(maximize conscious control、確定性驗證閘、異質模型 plan-and-execute)、
HierTOD(階層目標統一 slot-filling+步驟導引)、GPT-5 世代 prompt 紀律、
Anthropic Agent Skills(progressive disclosure;本 repo skills/ 格式同型)。

## 決策

1. **議程單位:事件(episode)**。顧問一次深挖一件實際發生的事(BEI/STAR);
   事件天然橫跨多任務=效率來源。「一次一個」約束顧問注意力,**不**約束內容歸屬
   ——書記/收割全寬歸檔(over-answering 標準處理)。
2. **議程決策=顧問迴圈內的 tool call**(不設獨立 planner,採 Microsoft 教訓):
   `open_episode(target)`/`close_episode(reason)` 掛進既有 chat_with_tools;
   service 確定性執行;主路徑零新增 LLM 呼叫;決策入稽核 `tool_calls` 可測可 eval。
3. **議程 artifact**:覆蓋地圖+事件狀態+飽和/疲勞/預算訊號由碼確定性計算,
   組成高訊號語意區塊注入顧問 context(取代 `ledger_summary` 單行 hint)。
4. **事件收割 pass(`harvest.py`)**:close_episode(或 auto-close)時,對事件
   逐字稿片段跑受限 schema 編碼——起草 P(STAR 句式;固定注入 behavior-indicator
   +ks-distinction 教材)、補 K/S/槽,走既有 op→verify→`_pending`。
   = BEI 事後編碼的即時版;**P 的結構性的家**。書記另補機會性 P 規則(員工明說
   標準時逐字掛);重複由 verify dup 擋。
5. **`next_gap` 梯子退役**;`ledger.py` 拆分:純覆蓋計算 →`coverage.py`
   (move-only)、狀態/訊號/artifact →`agenda.py`(episode 粒度)。
   guardrail 兜底(後衛不是駕駛):事件連 2 輪零新值→提示、第 3 輪 auto-close
   +收割;無事件連 2 輪未開→強化提示;硬預算沿用。
6. **異質模型**:interview(策略腦)升 frontier 級(型號過 T11 考卷再定);
   select(書記/裁剪/收割/態度)維持 mini。
7. **止血修**併入:BUG-1(落地前 seed `ocs_content.ocu_units` 骨架+處女文件
   測試)、BUG-4(progressed=episode 相關路徑有無新值;curation 落地計入)。
8. **prompt 紀律世代更新**:全 repo「GPT-4.1 指南」參照改 GPT-5 世代
   (eagerness 校準、低冗長顯式化、schema 嚴格、工具描述 1-2 句)。

## 後果

- **修正 0027**:確定性覆蓋帳本從「決策駕駛」降為「事實供給」(coverage 純函式
  +agenda artifact);四組件(顧問/書記/帳本/backstop)之上加事件議程與收割,
  成五組件。顧問「無寫入權」不變(議程工具寫的是 session 議程狀態,非文件)。
- **修正 0028**:議程化彈性流程的實現載體由 next_gap 提示改為議程工具;
  檢查表/裁剪縫、態度收尾 pass 保留。
- 0030 寫入層(verify/`_pending`/一條腦=書記唯一文件寫入口)**不動**;
  收割/裁剪/態度皆經同一 op 通道,不破「單一寫入貨幣」。
- sessions.ledger_state 欄位沿用、內容改 agenda 形(episode/attempts v2),
  無 DB migration;web 零改動(`_pending` 渲染早已泛化)。
- 風險:小模型議程判斷不可靠 → 顧問升模型+guardrail 兜底;顧問忘開/忘收
  → guardrail 第 3 輪強制;收割與書記重複 → verify dup 擋。
- 退役禁令:next_gap 梯子及其「補丁」(改優先序/加特例)不得復活——議程決策
  一律走顧問工具+guardrail;若要翻案本 ADR,開新號。
- 計畫:`docs/plans/2026-07-14-agenda-v4-episode-harvest.md`(L1 止血在前、
  characterization green-before==green-after、一 task 一 commit)。
