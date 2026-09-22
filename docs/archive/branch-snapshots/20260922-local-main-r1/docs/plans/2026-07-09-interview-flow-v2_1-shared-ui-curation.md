# 訪談流程 v2.1 實作計畫(ADR 0028;AI 驅動共用 UI + 裁剪 + 檢查表 + 態度收尾)

> 依 [ADR 0028](../adr/0028-interview-flow-shared-ui-curation.md) +
> [研究紀錄 D1–D7](../specs/2026-07-09-interview-flow-task-curation-and-flexibility-research.md)。
> 慣例:**一 task 一 commit、TDD(紅→綠→commit)、green-before==green-after**;
> 改後端要手動重啟 api(reload 關);CJK 測試 `PYTHONUTF8=1`;**不 push**。
> web 是 Next 16.2.6(breaking 版)——動 Next 專屬 API 前讀 `node_modules/next/dist/docs`。
> DB 整合測 `TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/caliburn`。

## 全局不變量(每個 task 隱含)

- 顧問無寫入權、書記無對話(0027 inv.1);寫入單一路徑(前端 applyAccepted→persist PATCH、
  後端 executor 守衛);quote 逐字驗;官方碼 strict enum。
- 帳本=純函式零 I/O;不可重算態才進 `ledger_state`(attempts/tier_override/**declined**)。
- §16.16 onboarding 測試、既有 api 291+/web 40+ 測試不可壞。

## Phase 1 — 後端(帳本→書記→兩個新 pass→接線)

### T1 帳本:檢查表三態 + phase 推導 + curation 縫

- **研**:D2/D6;`ledger.py` 現 next_gap ⓪–⑥;pack 的任務身分(provenance ocs_code+task_code,
  web `taskUrns` 同源)。
- **檔**:`apps/api/app/interview/ledger.py`(+`tests/test_interview_ledger.py`)。
  - `checklist(doc, state, pool_tasks) -> {"covered": [...], "declined": [...], "unasked": [...]}`;
    `pool_tasks=[{key, name, unit, ocs_code, task_code}]`(service 從 knowledge 組;純函式吃參數)。
    covered=池任務出現在 doc(以 task_codes/provenance 對身分);declined=`state["declined"]`。
  - `derive_phase(doc, state, pool_tasks) -> "onboarding_occupation"|"task_curation"|"opks_deep"|
    "attitudes_wrapup"`(顯示/引導用;由 doc 推導,不落庫)。
  - next_gap:有職類且(無任務或 unasked 非空)→ `CURATION_TASKS="curation:tasks"`
    (取代原 ONBOARD_TASKS 位;ONBOARD_OCCUPATION 不變);**尊重 STALL_K**(成組問兩輪
    無進帳 → 先往 deep,unasked 留給收尾補問——避免審訊感)。
- **測**:三態分類、declined 不再回 unasked、curation 縫優先序(在 ①預算槽前)、
  stalled 後 fall-through、既有 onboarding 測試不壞。
- **commit**:`feat(api): 帳本檢查表三態+phase推導+curation縫(0028 D2/D6)`

### T2 書記:移除逐回合態度池通道

- **研**:D3;`scribe_schema.py` 變體、`scribe.py` `record_attitude_pool` 分支、SCRIBE_SYS 第 6 條。
- **檔**:`scribe_schema.py`/`scribe.py`(+兩測試檔)。移除 `record_attitude_pool`
  (schema 變體+apply 分支+prompt 句);**保留** `record_attitude_custom`(建議層,
  「明確聽到具體態度故事」的機會性通道)。
- **測**:回歸守衛「同句態度式發言 → 不產池選態度 suggestion」;既有兩通道測試改對應。
- **commit**:`feat(api): 書記退場逐回合態度池通道(0028 D3;39條轟炸機制根)`

### T3 裁剪 pass(AI 預勾/排除;新模組)

- **研**:D1/D4/D6;mirror `scribe.py` 形(strict schema+確定性守衛);O*NET relevance 確認式。
- **檔**:`apps/api/app/interview/curation.py`(新)+ `tests/test_interview_curation.py`。
  - `curation_schema(pool_keys)`:strict enum(unasked 池 key)+quote;
    `apply_curation(records, pool, employee_texts)`:守衛 quote 逐字、key∈pool →
    `CurationResult{precheck:[{key,name,quote}], declined:[{key,quote}]}`。
  - `curation_pass(llm, *, pool_tasks, employee_texts)`(role=select、重試 1、fail-closed 空結果)。
  - **保守預勾**(D4):prompt 明示「不確定=不勾」;declined 只在員工**明說不做**時標。
- **測**:fake llm——預勾+quote 驗、池外 key drop、明說不做→declined、含糊→兩者皆無。
- **commit**:`feat(api): 裁剪pass(AI預勾/排除+quote守衛;0028 D1/D4)`

### T4 態度收尾 pass

- **研**:D3(BEI 跨故事編碼);`backstop.py` 形(收尾、便宜模型、只提案)。
- **檔**:`apps/api/app/interview/attitudes.py`(新)+ `tests/test_interview_attitudes.py`。
  - `attitudes_pass(llm, *, pool, employee_texts, existing)`:讀**全**逐字稿 → 2–4 條
    `{pool_id, quote(最強一句), rationale}`;守衛:pool_id∈A 池、quote 逐字、去重(含 existing)、
    硬上限 `MAX_A`;產 suggestions(review 層,員工確認才落——0027 §3.3 精神不變)。
- **測**:fake——2–4 條夾取、重複 code 去重、quote 未驗 drop、existing 滿 → 空。
- **commit**:`feat(api): 態度收尾整體pass(全逐字稿→2-4條+最強引文;0028 D3)`

### T5 service/route 接線:widget 指令 + 檢查表反問 + finish 掛態度

- **研**:D1/D5/D6;`service.run_turn` ②–⑥、`routes/interview.py` finish/view;`stubs.py`。
- **檔**:`service.py`/`consultant.py`/`routes/interview.py`/`adapters/stubs.py`(+integration 測)。
  - service:組 `pool_tasks`(knowledge.occupation_tasks 聯集);gap=`curation:tasks` 時跑
    `curation_pass` → `TurnResult.widget={"kind":"open_picker","picker":"task",
    "precheck":[{key,name,unit,quote}...]}`;declined 併入 `ledger_state["declined"]`;
    gap=ONBOARD_OCCUPATION 且顧問已提議職類 → `{"kind":"open_picker","picker":"occupation",
    "query":<員工工作描述>}`(輕量:由最近員工發言组 query)。
  - consultant:`ledger_summary` 對 `curation:tasks` 吐**成組反問**引導(unasked 名單 ≤5/組;
    「A/B/C 你有做哪些?沒做直接說沒有」);全 covered-or-declined → write-in 探測句
    (「官方沒列、你常做的還有嗎?」)。
  - route:GET view 的 evidence 加 `review` 欄(D7 前端渲染資料源);finish 在 backstop 旁掛
    `attitudes_pass`(fail-open:llm 缺仍可收尾)。
- **測**:integration(StubLlm/StubKnowledge)——空白→occupation widget;有職類無任務→task
  widget 帶 precheck;declined 落 ledger_state 且不重問;finish 產態度 suggestions ≤MAX_A。
- **commit**:`feat(api): widget指令+檢查表反問+finish態度pass接線(0028 D1/D5/D6)`

## Phase 2 — 前端(同 UI 追蹤修訂)

### T6 型別/api 層

- **研**:`types/index.ts` InterviewWidget 現形(choice);`lib/api.ts` getInterview。
- **檔**:`apps/web/src/types/index.ts`(widget 判別聯集:`ChoiceWidget|OpenPickerWidget`)、
  `lib/api.ts`(evidence.review 型別)。
- **測**:`npx tsc --noEmit` 綠(型別 task 以 tsc 為測)。
- **commit**:`feat(web): widget判別聯集+evidence.review型別(0028)`

### T7 AI 驅動 pickers(程式化開啟+預填+理由列)

- **研**:D1/D5;**讀 `node_modules/next/dist/docs` 相關段**;`OccupationPicker`(defaultQuery 已可
  外帶)、`TaskPickerMenu`/`UnitPickerMenu`(applyDefaults 形)、舊 `InterruptHandlers.TaskCurator`
  (樣式參考,**不引 CopilotKit**)。
- **檔**:`documents/[id]/page.tsx`(pickerRequest state:InterviewPanel `onWidget` 回呼 → 開
  對應件)、`OccupationPicker.tsx`(prop:`initialQuery`+自動首搜)、新
  `components/interview/CurationDialog.tsx`(任務裁剪 modal:按職責分組、預勾+每列
  **引文理由**+SourceLine 溯源、勾/剔/加自訂;**寫入走既有 `addFromPool`/`addTasksToUnit`+
  persist**——同資料源(pack)、同列樣式、同寫入路;「討論」鈕=關窗把理由文字回填輸入框)。
- **測**:vitest(CurationDialog 勾選→輸出 picks 形狀、剔除不落、自訂列);tsc+lint 綠。
- **commit**:`feat(web): AI驅動pickers(occupation預填+CurationDialog預勾引文;0028 D1/D5)`

### T8 JobDocTable 追蹤修訂渲染(D7)

- **研**:D7;`JobDocTable` 格渲染點;`useInterview` view(evidence+suggestions)。
- **檔**:新 `lib/reviewMap.ts`(evidence(review=pending)+suggestions → `Map<path,{state,quote}>`)
  + `JobDocTable.tsx`(pending 格高亮+「AI」徽章+title/hover 引文;新增項「新」標)+
  格旁 ✓/✗(走既有 review→applyAccepted→persist)。人改格無標記(不讀 human_touched,
  無 evidence 即無標)。
- **測**:vitest(reviewMap 映射、accept 後標記消失);tsc+lint。
- **commit**:`feat(web): 文件格追蹤修訂樣式(pending高亮+引文hover+格旁批審;0028 D7)`

### T9 待審計數鈕(置頂清單退役)

- **研**:D5 載體修正;`InterviewPanel` 現佈局(SuggestionReview 在滾動區頂=bug)。
- **檔**:`InterviewPanel.tsx`——SuggestionReview 移出滾動串,改**底部(輸入框上)**
  「N 項待審」列,點開展開(內容復用 SuggestionReview);滾動行為不變。
- **測**:vitest(有 pending 顯示計數、展開/收合);tsc+lint。
- **commit**:`fix(web): 待審清單移底部計數鈕(置頂看不見bug;0028 D5)`

## Phase 3 — 品質閘門與文檔

### T10 interview_sim v3:裁剪/檢查表/態度量測

- **研**:§16.14 教訓(確定性指標當閘門);黃金範本任務清單當 ground truth。
- **檔**:`apps/api/evals/interview_sim.py`——劇本擴到 curation 段(模擬員工述職→量
  **預勾 precision/recall**(vs 事實表應做任務)、declined 正確率、態度收尾條數 2–4+引文
  驗證率);閘門仍=確定性指標(引文驗證率+進帳率+**預勾 precision≥0.8**);跑校準記
  研究紀錄 §16 新節。
- **commit**:`feat(api): sim v3(裁剪precision/recall+檢查表+態度收尾;校準#4)`

### T11 文檔改版 + 收尾

- **檔**:`docs/design/interview-engine.md`(流程=議程五段、widget 指令契約、追蹤修訂呈現、
  不變量增補)+ 研究紀錄 §16 驗收紀錄 + roadmap 項清理(開場揭露未觸發若未修仍留)。
- **驗**:全套 `npx turbo test` 綠 → **git tag `interview-v2.1`**。
- **commit**:`docs(design): 訪談引擎v2.1文檔改版(0028)`

## 驗收(整體)

1. 空白文件開訪談 → 顧問問工作 → **職類 picker 自動開+預填**(不硬猜、不問態度)。
2. 選定職類 → 述職一段 → **CurationDialog 預勾+引文理由** → 套用 → 任務入文件。
3. 反問未涵蓋官方任務(成組)→ 說「沒做」→ 不再重問(declined 留痕)。
4. 深聊寫入 → **文件格 pending 高亮+hover 引文** → 格旁/批次收;待審計數在面板底部。
5. finish → 態度建議 2–4 條各綁引文 → 員工確認才落。
6. sim v3 閘門 PASS;全套測試綠。
