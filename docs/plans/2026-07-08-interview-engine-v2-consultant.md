# 訪談引擎 v2(顧問 agent)— 實作計畫

> **依據**:ADR [0027](../adr/0027-interview-engine-v2-consultant-agent.md)(四組件+門檻 v1)+
> 研究紀錄 [`2026-07-06-consultant-not-formfiller-redesign-research.md`](../specs/2026-07-06-consultant-not-formfiller-redesign-research.md)
> §7–§14(定稿)。黃金範本=品質尺(`2026-07-05-golden-sample-software-tester.md`)。
> **紀律**:一 task 一 commit、綠了才 commit、TDD、**不 push**;收尾 tag `interview-v2`。
> **驗證環境**:api `cd apps/api && uv run pytest -q`;web `npm run test` + `npx tsc --noEmit`;
> sim `uv run python evals/interview_sim.py`(CJK 記得 `PYTHONUTF8=1`)。

## 全域約束

- **研究關卡(每 task 必經)**:動工前先跑該 task 的「研」步——來源已在研究紀錄的,重讀
  對應節;標**微研究**的,查權威來源(官方/論文/大廠/資深)並記入研究紀錄 **§15 起**新節。
  **研究結果與既定設計矛盾 → 停手**,把發現寫進研究紀錄、必要時開新 ADR,再繼續;
  北極星=世界最強品質、無時限壓力(維護者 2026-07-08 定調),「把功能做完」永遠讓位給
  「發現更好的作法」。
- ADR 0023 約束全沿用:引擎狀態只住 DB+文件、**禁止**模組級可變狀態;LLM 不選通道、
  不能繞 guard(分流與門檻全在 executor);quote 驗證=NFKC+空白摺疊子串,失敗 retry 1 →
  unverified;pydantic `extra="ignore"`。
- **安全網**:green-before==green-after;既有 sim 校準不得低於 v1 基線(1.0/0.91);
  v1 行為在各 task 完成後仍可跑(換心臟不斷電)。
- **文檔義務**:task 若使 `docs/design/interview-engine.md` 某句失真 → 同 commit 修那句;
  全面改版收在 T15。
- 員工輸入=**資料非指令**(OWASP LLM01):所有新 prompt 含此宣告;T14 加對抗樣本。

---

## Phase 0 — 確定性帳本(地基,不碰 LLM)

### T1 `ledger.py` 純函式 + 門檻 v1

- **研**:ADR 0027 門檻節 + 研究紀錄 §11(iCAP n/a 規則、O*NET core 判準)+ 黃金範本
  附-4(core 12 槽/淺掃 4 槽自檢)。確認 SLOT_DEFS 現況(`app/interview/slots.py`)與 12 槽
  對齊(缺「產出」槽則本 task 一併補進 slots+contract,參照 v1 plan T1 的 additive 慣例)。
- **檔**:`apps/api/app/interview/ledger.py`(新)——輸入 doc+turns+skips+覆寫,輸出:
  `task_tier(task)->core|light`(比重×頻率建議,可被人工覆寫)、`coverage(doc)->per-task
  (filled,required,na)`、`next_gap(doc)->path|None`(優先 core 靈魂槽:等待/例外/標準)、
  `is_stalled(history,K=2)`、`can_finish(doc)->(bool,blockers)`(core 12/12、淺掃 4/4、
  每職責 P≥1、A≥2、比重加總=100%±容差)。
- **測**:`tests/interview/test_ledger.py`——黃金範本結構做 fixture(7 任務 4 core);
  各函式邊界(n/a 計入、比重≠100 擋、飽和 K=2、空文件)。
- **驗**:pytest 綠。**commit**:`feat(api): v2 覆蓋帳本純函式(門檻v1;ADR 0027)`

### T2 sessions 攜帶帳本持久狀態

- **研**:12-Factor F5/F12——**可從 doc+turns 重算的一律 derive 不落庫**;只存不可重算的:
  per-task attempted 計數、tier 人工覆寫、probe 設定(深度/風格常數)。
- **檔**:alembic migration(sessions 加 `ledger_state jsonb`)+ repo 讀寫;
  `ledger.py` 增 `apply_state/merge_state`。
- **測**:repo 往返 + 重算一致性(存的狀態餵回=同結果)。
- **驗**:`npm run db:migrate` + pytest 綠。**commit**:`feat(api): sessions.ledger_state(僅存不可重算態)`

## Phase 1 — 書記(抽取 pass)

### T3 書記 schema(兩通道)+ 對抗驗收

- **研**:研究紀錄 §7.3 spike 方法 + §9.1 兩通道;OpenAI strict 文件複核(function-calling
  guide,確認 enum/anyOf 限制現況——**微研究**:若 strict 對 anyOf 分支有新限制,記 §15)。
- **檔**:`app/interview/scribe_schema.py`(新)——per-turn 建構:池內寫入(`pool_id` enum=
  當前合法池)/自訂寫入(`name`+`quote` 必填)/`route_task`(items:match 候選 enum)/`none`。
- **測**:schema 產生器單測(池空→無池內分支;enum 內容正確)。
  `scripts/validate_select_schema.py --role scribe` 加敵意樣本(誘池外碼、假 quote、
  一句多任務)→ **0 逃逸才過**。
- **驗**:pytest + validate 腳本 PASS。**commit**:`feat(api): 書記兩通道 schema+對抗驗收(0027)`

### T4 書記 service + 跨任務歸位

- **研**:§9.2(跨任務、模糊掛最像+標記)、executor 現有守衛面盤點(writable_path/quote/
  budget 哪些直接可用)。
- **檔**:`app/interview/scribe.py`(新)——讀逐字稿增量→呼叫 `select_schema`(role=select)
  →命令交 executor;片段先 `items:match` 歸位(候選=文件任務清單);守衛拒絕→**精簡錯誤**
  (12-Factor F9)回饋重試 1 次→仍敗則丟 backstop 佇列。
- **測**:fake LLM+fake knowledge——一句多任務→多筆寫入不同任務;池外→只能走自訂+quote;
  quote 驗證失敗→unverified;重試路徑。
- **驗**:pytest 綠。**commit**:`feat(api): 書記抽取pass(跨任務歸位+守衛重試;0027)`

### T5 風險分流接線

- **研**:ADR 0027 核准節(低→pending 標記+undo;高→suggestion;**0025 #1 已修正**)。
- **檔**:executor/scribe 出口分流——細項槽=直接落地+`pending` 標記(evidence 表帶
  provenance);加自訂任務/職責、模糊歸類=suggestion(既有表)。undo=既有版本機制,
  確認 revision 路徑通。
- **測**:分流矩陣單測(槽/自訂/模糊 × 高低風險 → 落點正確)。
- **驗**:pytest 綠。**commit**:`feat(api): 寫入風險分流(低=pending標記,高=建議;0027)`

## Phase 2 — 顧問 agent

### T6 READ 工具層

- **研**:§12 表 #2 = Anthropic《Writing effective tools》檢核清單**逐條過**:search>list、
  回語意名稱(`ocu_name`+code 並回)、top_k 截斷預設、錯誤訊息可操作、評估是否加
  `occupation_brief`(職類+任務+職能一呼帶齊,省迴圈次數)。
- **檔**:`app/interview/tools.py`(新)——KnowledgePort 四讀包成 tool defs(JSON schema)
  +dispatcher(純函式,回壓縮後結果);namespacing `knowledge_*`。
- **測**:dispatcher 單測(fake knowledge;截斷、錯誤格式、brief 組裝)。
- **驗**:pytest 綠。**commit**:`feat(api): 顧問READ工具層(Anthropic tool 檢核;0027)`

### T7 `LlmPort.chat_with_tools`(手刻迴圈)

- **研**:§8.5 手刻 gotchas 清單(tool_call_id 對回、逐 provider 可靠度、`max_tool_iterations`、
  attribution header、loop 關 adapter 後)+ OpenAI function-calling 官方 loop 形複核。
- **檔**:`app/core/ports.py`(LlmPort 加 `chat_with_tools`)、`app/adapters/llm_openrouter.py`
  (實作:while 迴圈、上限預設 5、每次呼叫/工具結果經稽核 hook 落 turns 附掛欄或新表——
  與 T13 對齊,先留 hook)。role=interview(0026)。
- **測**:fake transport——0 次工具、N 次工具、超上限截停、tool_call_id 錯配防禦。
- **驗**:pytest 綠。**commit**:`feat(api): LlmPort.chat_with_tools 手刻迴圈(上限+稽核hook;0027)`

### T8 顧問 prompt v2(**微研究關卡**)

- **研(微研究,記 spec §15)**:BEI/CTA 問句庫——Critical Decision Method 探針問法
  (Klein 原始 probe set)、O/P/K/S/A 各塊引出句(K/S 從「你怎麼做到的」、A 從故事編碼
  不直接問,§10.5);NN/g 揭露文案要素;hedging 觸發詞表(中文:「可能/大概/不太確定/
  還好/就那樣」)。**產出=§15 問句庫+來源**,prompt 引用之。
- **檔**:`app/interview/context.py` 改版——顧問人格(BEI 故事開場)、開場揭露(AI 身分/
  時長/資料用途/有人審核)、資料非指令宣告、飽和換題話術、低品質處理(換問法→舉例→
  標記前進)、probe 深度常數(`app/config.py`)。
- **測**:prompt 組裝單測(帳本缺口注入、揭露必在開場、宣告存在);sim 冒煙。
- **驗**:pytest 綠。**commit**:`feat(api): 顧問prompt v2(BEI+揭露+注入硬化;§15 問句庫)`

### T9 回合管線改組

- **研**:§12 誠實殘留(序列 vs 並行)——本 task 埋**延遲量測點**(每段耗時落稽核),
  數據進 T14 報告再裁並行。
- **檔**:`app/interview/service.py`——管線改:載入→**書記 pass**→帳本更新→**顧問
  chat_with_tools**(context=帳本摘要+文件+逐字稿)→`_ensure_visible` 保底(卡關在此觸發
  強制換題)→寫回。progress 改由帳本出(coverage 比例)。
- **測**:整合測(fake 全件)——一回合走完五段;書記敗不擋顧問;帳本閘門擋 finish;
  **v1 既有測試全綠**(相容或明確汰換並記錄)。
- **驗**:pytest 綠;sim 分數 ≥ 基線。**commit**:`feat(api): v2 回合管線(書記→帳本→顧問→保底;0027)`

## Phase 3 — 前端與核准

### T10 核准 UI:高風險選單 + 低風險批次收

- **研**:§9.4/9.5;盤點既有件(SuggestionReview/ChoiceCard/applyAccepted);
  **讀 `node_modules/next/dist/docs`**(repo 慣例:web 是 breaking 版 Next)。
- **檔**:web——ChoiceCard 升級「AI 預勾清單」(高風險);文件 pending 標記色+
  「本段一次收」+undo(走既有版本/patch 路徑);InterviewPanel 接新 progress。
- **測**:vitest(applyAccepted 擴充、預勾清單狀態);`npx tsc --noEmit`+lint。
- **驗**:web 三驗綠。**commit**:`feat(web): 風險分層核准UI(預勾清單+pending批次收;0027)`

### T11 onboarding 併入對話

- **研**:§9.3(空白起跑、手動 picker 平行保留);既有 start 前置檢查點盤點。
- **檔**:api——start 放寬(無職類/任務也可開,顧問開場走選職類流程:search→清單 widget);
  web——開始畫面文案更新。
- **測**:api 整合測(空白 doc 起跑→第一輪出職類清單 widget);既有「先選好才開」路徑不壞。
- **驗**:pytest+web 綠。**commit**:`feat(api+web): onboarding 併入訪談對話(空白起跑;0027)`

## Phase 4 — 收尾、稽核、品質

### T12 backstop 複查 pass

- **研**:§8.4(收窄:兩題、只提案、便宜模型、單 writer)。
- **檔**:`app/interview/backstop.py`(新)+ service 收尾接線(finish 前跑;產 suggestions)。
- **測**:fake——漏記偵測、出處違規偵測、只提案不直寫。
- **驗**:pytest 綠。**commit**:`feat(api): backstop 收尾複查(兩題、只提案;0027)`

### T13 稽核落庫

- **研**:§13 收編 5(自建 observability;多租戶欄位:company/session/turn 維度)。
- **檔**:migration(`interview_llm_calls` 表:role/model/耗時/token/工具呼叫 JSON/守衛判定)
  +T7 hook 落地+T9 量測點落地。
- **測**:repo 往返;一回合寫入筆數正確。
- **驗**:migrate+pytest 綠。**commit**:`feat(api): 訪談LLM/工具呼叫稽核落庫(0027)`

### T14 interview_sim v2 + 門檻校準

- **研**:§10 收編 3(pre-testing 制度化)+ §12 #7(Anthropic eval 指標:accuracy/工具
  呼叫數/token/耗時)+ 2410.01824 失敗模式做對抗劇本(裝傻/離題/一句多任務/誘導池外)。
- **檔**:`evals/interview_sim.py` 擴充——**coverage/depth 兩軸**評分、黃金範本比對報告、
  對抗劇本、延遲報告(T9 量測);跑校準 → 結果記研究紀錄新節(§16 校準 #3),
  **據此調門檻常數**(調=改 config,不改 ADR;若動搖門檻設計才回 ADR)。
- **驗**:sim 報告產出;分數/覆蓋達標(core 覆蓋 ≥ 黃金範本同構、無守衛違規)。
- **commit**:`feat(api): interview_sim v2(coverage/depth+對抗+校準#3)`

### T15 文檔改版 + 收尾

- **檔**:`docs/design/interview-engine.md` 全面改版 v2(四組件、回合管線、不變量、
  退役禁令更新);`CLAUDE.md` 指路句若失真同步;研究紀錄補「實作期發現」總節。
- **驗**:全 repo 測試綠(`npx turbo test`);文檔 dual-audience 清單過(動作→請求、真名、
  不變量、退役禁令)。
- **commit**:`docs(design): interview-engine v2 改版` → **tag `interview-v2`**。

---

## 驗收(整體)

1. 真人試訪重跑 2026-07-06 的失敗劇本:不再逐欄問、會查資料提議、卡住給例子、
   一句多任務全落對、OPKS 有引出、收工被閘門把關。
2. sim v2:coverage/depth 達標、對抗劇本 0 守衛違規、延遲報告在案。
3. 黃金範本同構性:同輸入訪談產出的文件結構(分層、標記、溯源)對得上範本圖例。
