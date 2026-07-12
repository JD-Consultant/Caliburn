# AI 層 v3 實作計畫(追蹤修訂直寫+一條腦+品質迴路)

> 依 [ADR 0030](../adr/0030-ai-coedit-tracked-changes-one-brain.md) 與
> [研究紀錄 §6 已鎖決策清單](../specs/2026-07-12-ai-layer-redesign-research.md)。
> **設計已逐點鎖定,不要重開設計討論**;疑義先讀研究紀錄 §6 與對應原始報告。

## 全局不變量

- TDD、一 task 一 commit、綠了才 commit、green-before==green-after;收尾打 tag `ai-layer-v3`。
- **新載體先上、舊件後拆**(T12 退場排最後);文件功能既有測試(存檔/併發/契約)全程當網。
- 0029 編輯器(選單三型/表格/位置碼)**不動**;AI 走同一條資料路徑寫入。
- 環境:Bash cwd 先 `pwd`+`git branch --show-current` 驗證;api reload 關(改碼手動重啟);
  `PYTHONUTF8=1`;DB 測試 `TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/caliburn`。
- 檢索升級包(eval 集→metadata filter→中文分詞→reranker→Qwen3)**不在本計畫**,另開 plan 可平行。

## Tasks

### T1 契約:`_pending` 選填欄位

- **檔**:`packages/ocs-contract`(JSON-schema→Pydantic+TS codegen;契約 #1 流程)。
- **內容**:可掛 `_pending` 的節點(職責/任務/OPLKS 條目/表頭欄/自由文欄)加選填物件:
  `{op: add|mod|del, by: "ai", turn_id, prev?, src?: {ref_urn?, quote?: {turn_id, text}}}`。
- **測**:schema 驗證(帶/不帶 `_pending` 皆合法);codegen 後 `git diff` 檢查兩端生成物。
- **commit**:`feat(contract): _pending修訂標記選填欄位(四態載體;ADR 0030)`

### T2 api:修訂層核心操作

- **檔**:`apps/api/app/services/`(文件服務)+ persistence。
- **內容**:pending 寫入/accept(去標)/reject(還原 prev 或整筆移除)/批量;匯出剝
  `_pending`;樂觀並發沿用 version 守衛。審閱事件(accept/reject/批量拒絕)寫入帳本事件表。
- **測**:四態轉移矩陣逐一;匯出乾淨;併發 409 不變。
- **commit**:`feat(api): pending修訂層操作(accept/reject/批量/匯出剝除;ADR 0030)`

### T3 verify 關(六查)

- **檔**:新模組 `apps/api/app/interview/verify.py`(純函數,無 LLM)。
- **內容**:六查(契約合法含 enum 正規化/quote 存在性對 DB 逐字稿/ref∈參考集合/寫入權限
  禁無聲改已確認/結構不變量含位置碼拒收+表頭值∈參考集合/尺寸衛生);**可行動錯誤**格式
  (哪條沒過+最接近原話建議)。
- **測**:每查至少一過一擋;幻覺 quote 拒收;表頭提議合法路徑。
- **commit**:`feat(api): verify六查=output guardrail(quote逐字/權限/不變量;ADR 0030)`

### T4 scribe op 化

- **檔**:`apps/api/app/interview/scribe.py`、`scribe_schema.py`。
- **內容**:輸出改寫入 op(strict;src 可 ref+quote 並存至少一);經 T3 verify,失敗
  **retry×2 回灌具體錯誤條目**,再敗丟棄記 trace;過關落 `_pending`(走 T2)。
- **測**:op schema strict;retry 回灌路徑;丟棄不落文件。
- **commit**:`feat(api): scribe輸出op化+verify retry回灌(唯一寫入口;ADR 0030)`

### T5 consultant 訊號位+議程狀態機+backstop

- **檔**:`consultant.py`、`ledger.py`、`backstop.py`、`tools.py`、`context.py`。
- **內容**:consultant 輸出加「有無素材」訊號位(有才喚醒 scribe);ledger 議程四態
  (covered/refused/held/boundary)+拒絕事件+每輪 coverage 分類勾銷;文件讀取工具回
  四態視圖;backstop=每 N 回合確定性掃逐字稿撿漏;疲勞偵測(回答長度滑動平均+敷衍
  短語)。
- **測**:訊號位省呼叫;boundary 不自行解除;重複素材不重問;疲勞觸發。
- **commit**:`feat(api): 議程狀態機四態+scribe按需喚醒+疲勞偵測(ADR 0030)`

### T6 tracing 橫切層搬家

- **檔**:`app/authoring/tracing.py` → `apps/api/app/observability.py`;`llm_openrouter.py`
  改 import。
- **內容**:`gen_ai.*` 命名(model/tokens/finish_reason/latency);span:turn→consultant
  工具→scribe op→verify 結果(含拒收原因)→審閱事件;fallback 事件、cache 命中。預設開。
- **測**:span 屬性斷言;舊 import 全清。
- **commit**:`refactor(api): tracing搬橫切層+gen_ai.*命名(記verify/審閱事件;ADR 0030)`

### T7 skills/ 八檔+載入器+context 分層

- **檔**:`apps/api/app/interview/skills/<name>/SKILL.md` ×8;`context.py`。
- **內容**:八檔照 §6.8 格式起草(原料=
  [iCAP 全欄位標準](../specs/2026-07-13-ai-redesign-raw-icap-field-standards.md)+
  [國際框架規範](../specs/2026-07-13-ai-redesign-raw-intl-competency-standards.md)+既有
  prompts;每條判準標出處;**S01–S24/A01–A14 官方目錄入 attitude/ks 檔**);載入器=按
  欄位/階段確定性對應;context 重排快取分層(前綴1=系統+總則+few-shot;前綴2=參考基準;
  動態區),近 10 輪全文舊摘要。**維護者審改 skill 內容**(SME gate)。
- **測**:載入對應表;快取前綴穩定性(同 session 前綴 byte 不變)。
- **commit**:`feat(api): skills八檔+確定性載入+context快取分層(ADR 0030)`

### T8 web:修訂層渲染與審閱

- **檔**:`apps/web/src/lib/ocsDoc.ts`(pending 輔助)、`JobDocTable.tsx`、新
  `PendingMark` 元件;`lib/api.ts`(accept/reject 端點)。
- **內容**:四態渲染(綠字淡綠底/舊值副行/紅刪除線);hover ✓/✗/?;出處卡(官方來源行
  +訪談原話);工具列批量鈕(N 即時);筆級淡入;匯出鈕待審提示。
- **測**:vitest(lib 轉換+狀態);`tsc --noEmit`+lint。
- **commit**:`feat(web): 綠紅標四態渲染+✓✗?+出處卡+批量(ADR 0030)`

### T9 web:側欄改造

- **檔**:`InterviewPanel.tsx` 大改。
- **內容**:對話(字元級 streaming)+開場揭露與議程預覽+議程三態清單(ledger 資料)+
  進度+「正在整理…」狀態指示+chips(選項+推薦+Other)。
- **測**:vitest 元件邏輯;tsc/lint。
- **commit**:`feat(web): 側欄=對話+議程三態+進度+chips(ADR 0030)`

### T10 收尾流程

- **檔**:`service.py`、`attitudes.py`、web 側欄。
- **內容**:收尾三訊號(coverage/疲勞/預算)任一觸發→結構化總結對帳(指表格條列+
  「有沒有要補或改」)→併態度收尾 pass;真誠收尾語。
- **測**:三訊號各自觸發;總結內容=本場寫入清單。
- **commit**:`feat(api+web): 收尾對帳pass(三訊號+總結回讀;ADR 0030)`

### T11 evals 基建

- **檔**:新 `apps/api/evals/`(考題/金鑰/斷言)+ `promptfooconfig.yaml` + CI wiring;
  rubric YAML 模板與 judge prompt 骨架(抄
  [evals 深挖報告附錄](../specs/2026-07-12-ai-redesign-raw-evals-design.md),Phase 2 備用)。
- **內容**:golden set 骨架(첫 1 題=維護者手造;結構就緒可擴);Source Score 程式計算;
  確定性斷言(K/S 歸位/結構/覆蓋/位置碼);promptfoo:改 prompt/skill 必跑 regression。
- **測**:考卷本身可跑、reference 金鑰拿滿分(驗 grader 沒壞)。
- **commit**:`feat(evals): golden set骨架+Source Score+promptfoo CI(ADR 0030)`

### T12 舊件退場(§6.7 清單)

- **檔**:刪 `app/authoring/`、`copilotkit_live_app.py`、`test_copilotkit_live_app.py`;
  `run_live.py` 改 app_factory;web 刪 CopilotKit 全家(route.ts/Providers wiring/
  InterruptHandlers/引用/npm deps)、CurationDialog、SuggestionReview、reviewMap+徽章;
  **intake 頁先盤點**(純 CopilotKit 入口→刪;有活功能→拆遷)。
- **驗**:`npx turbo test` 全綠+tsc+lint;dev 起服手測訪談全流程。
- **commit**:`refactor(api+web): 舊LangGraph+CopilotKit+彈窗載體退場(0023欠債清償;ADR 0030)`

### T13 工程輕項

- **檔**:`llm_openrouter.py`/config。
- **內容**:OpenRouter 顯式 `models` fallback(備援先過 T11 考卷)+`provider.allow_fallbacks`;
  parallel tool calls;確認 streaming 全鏈;模型 role 表(consultant/scribe/backstop)。
- **commit**:`feat(api): OpenRouter顯式fallback+parallel tools(備援過eval;ADR 0030)`

### T14 文檔同步+收尾

- **檔**:`docs/design/`(訪談引擎端到端篇,dual-audience:動作→請求、真名、不變量、
  退役禁令——含「verify 必 blocking」「backstop 禁 LLM 化」「✓/✗ 無聲」);ADR README
  已於 0030 落檔時更新;CLAUDE.md 若有指路變動。
- **驗**:`npx turbo test` 全綠(api 另直跑含 DB);tag `ai-layer-v3`。
- **commit**:`docs(design): AI層v3端到端文檔同步(ADR 0030)`

## 順序依賴

T1→T2→T3→T4→T5(引擎鏈);T6/T7 可與 T3–T5 交錯;T8 依 T1/T2;T9/T10 依 T5/T8;
T11 依 T4–T7(考 scribe/skill);**T12 必須在 T8/T9 綠之後**;T13 隨時;T14 最後。
