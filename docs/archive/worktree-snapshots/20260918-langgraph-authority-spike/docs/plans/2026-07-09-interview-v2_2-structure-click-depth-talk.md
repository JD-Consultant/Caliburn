# 訪談 v2.2 實作計畫:結構=點選、深度=對話(spec D8;真人實測 65b9aa3d 驅動)

> 依 [研究紀錄 D8](../specs/2026-07-09-interview-flow-task-curation-and-flexibility-research.md)
> (Anthropic effective-agents「workflow=可預測/agent=不可預測」+ survey 負擔實證 + PAIR +
> DACUM duty→task)。0028 範圍內細化,不另開 ADR。
> 慣例同 v2.1 plan:一 task 一 commit、TDD、green-before==green-after、**不 push**;
> web=Next 16.2.6;DB 測 `TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/caliburn`。

## 全局不變量(每 task 隱含)

- **深聊不選單化**(BEI 故事=不可取代的開放題;chips 僅 meta 動作)。
- 顧問無寫入權;寫入單一路徑;quote 逐字;官方 strict enum;§16.16/16.18 回歸測不可壞。

## T1(P5)書記三行修正

- **研**:實測 65b9aa3d——K=18/S=0(全偏 K)、Docker/CI 內容硬塞「需求分析」任務、
  「AI 馴獸師」玩笑進 outputs。
- **檔**:`scribe.py` SCRIBE_SYS 補三規則:①內容不屬任何現有任務 → `add_custom_task` 提議
  新任務,**不硬塞不相關任務**;②K/S 判準:知道的概念=K、會操作的手藝=S;③玩笑/比喻/
  客套不當事實記。`tests/test_interview_scribe_apply.py` 加 prompt 關鍵語斷言。
- **驗**:pytest 綠。**commit**:`fix(api): 書記prompt三行(歸位/KS判準/玩笑;D8 P5)`

## T2(P2)中途加選職類回路

- **研**:實測——顧問三度搜到「網站系統設計人員 1.0」但 widget 只在無 ocs_code 時發;
  `dispatch_tool` 搜尋回 `{"occupations":[{ocs_code,name,score}]}` 可截。
- **檔**:`service.py`——dispatch 包 closure 截 `knowledge_search_occupations` 命中;
  chat 後:**首次搜尋的 top-1 `ocs_code` ∉ `_doc_ocs_codes(work_doc)`** → occupation widget
  (query=該次搜尋詞;統一取代原 ONBOARD 條件,空白 doc 天然涵蓋)。
  `consultant.py` system prompt 補:「員工工作明顯超出現有職類 → 明講建議**加選**(可多選,
  任務池會聯集),請他從畫面選職類。」
- **測**:integration——已有 code、顧問搜到**不同** top-1 → widget 帶 query;top-1=現有 code
  → 無 widget;§16.16 onboarding 測不壞。
- **驗**:pytest 綠。**commit**:`feat(api): 中途加選職類回路(top-hit∉codes→彈picker;D8 P2)`

## T3(P1a)`interview:curation` 隨叫端點 + 選職類後主動開窗

- **研**:D8「選完職類立刻彈、零打字鋪任務盤」;service 已有 build_task_pool/checklist/
  curation_pass 可組。
- **檔**:api——`service.run_curation(profile_id)`(讀 session+doc+發言 → pool → unasked →
  curation_pass → declined 落 ledger_state → 回 `{precheck:[…含quote], others:[{key,name,unit}]}`
  =**全檢查表**,AI 沒把握的列在 others 未勾)+ route `POST …/interview:curation`(無 active
  →409;llm 缺→precheck 空、others 照列=fail-open)。
  web——`lib/api.ts` 加 fn;page:`OccupationPicker` 加 `onApplied` 回呼 → 訪談面板開著時
  呼端點 → `setCuration(payload)` 開窗。
- **測**:integration(端點回全檢查表+declined 落地);web tsc/vitest/lint。
- **驗**:綠。**commit**:`feat(api+web): interview:curation隨叫+選職類即彈任務盤(D8 P1a)`

## T4(P1b)CurationDialog 一窗兩步(職責→任務;全清單)

- **研**:DACUM duty→task;PAIR mental models(同編輯器樣式);items 形擴為
  `{prechecked, others}`(turn widget 同步帶 others,兩入口同資料形)。
- **檔**:web——`CurationDialog` 步1:職責 checkbox 清單(有 AI 預勾任務的職責預勾;
  全部官方職責照列)→ 步2:所選職責的任務(AI 預勾=勾+引文;others=未勾可勾;已加入鎖定);
  `lib/curation.ts` 擴 rows 組裝(others 併入);`service.py` turn widget 補 `others`。
  types:`OpenPickerWidget.others?`。
- **測**:vitest(rows 併 others、步1 職責集合推導、步2 過濾);tsc/lint。
- **驗**:綠。**commit**:`feat(web): CurationDialog一窗兩步(職責→任務+全檢查表;D8 P1b)`

## T5(P4)chips meta 動作

- **檔**:web `InterviewPanel`——輸入框上方三顆 chips:「跳過這題」「沒有/不適用」
  「先記到這,下一題」→ 點=send 該字(走既有 turn;後端 skips 語彙已認得「跳過」)。
  **僅 meta 動作,不做內容答案 chips**(D8 邊界)。
- **測**:tsc/lint;vitest 可略(純 send 轉發)。
- **驗**:綠。**commit**:`feat(web): 深聊meta快速回覆chips(跳過/沒有;D8 P4)`

## T6 文檔驗收

- **檔**:`docs/design/interview-engine.md`(D8 鐵律入不變量、flow 補 curation 隨叫+中途加選)
  + 研究紀錄 §16 驗收紀錄。
- **驗**:全套 turbo test 綠 → tag `interview-v2.2`。
- **commit**:`docs(design): v2.2文檔(結構點選/深度對話;D8)`

## 驗收(整體)

1. 選完職類**立刻**彈職責→任務兩步窗,零打字鋪滿任務盤(AI 預勾+全清單可勾)。
2. 聊到後端/部署(超出現有職類)→ 顧問明講建議加選 + **職類窗自動彈**(top-hit∉codes)。
3. 書記:內容找不到家 → 提議新任務而非硬塞;K/S 分流;玩笑不入格。
4. 深聊仍是純對話;chips 只有跳過/沒有/下一題。
