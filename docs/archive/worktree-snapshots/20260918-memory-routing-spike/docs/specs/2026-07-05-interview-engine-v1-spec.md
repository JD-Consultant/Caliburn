# 訪談引擎 v1 — 設計 spec

> **類型**:設計 spec(**定稿 2026-07-05;維護者授權自審**——維護者指示「不用問我,自己研究
> 自己查文檔自己找資料」,北極星=顧問等級職務說明書;自審紀錄見 §11)。**決策依據**:ADR [0023](../adr/0023-interview-engine-stateless-turns.md)(骨幹)
> / [0024](../adr/0024-llm-wiring-select-schema.md)(接線)/ [0025](../adr/0025-coedit-authority-dual-channel.md)(共編權限)
> / [0020](../adr/0020-interview-authoring-interaction-model.md)(載體)/ [0015](../adr/0015-document-save-optimistic-concurrency.md)(樂觀鎖)。
> **研究依據**:[接線研究](2026-07-05-llm-integration-wiring-research.md)(輪 1–10)·
> [黃金範本樣張 v0](2026-07-05-golden-sample-software-tester.md)。
> **一句話**:員工在側欄面板被 LLM 顧問訪談(盤點→深掘→總審三段軌道),文件在旁邊即時長出;
> 引擎=無狀態回合服務,寫入走**編輯器同一條 PATCH seam**,人碰過的內容走建議層。

## 0. 定位、範圍、非目標

- **v1 對談者 = 員工**(不專業;語氣友善、防呆);做完後**顧問看**文件+訪談紀錄(溯源稽核)。
- **v1 軌道三段**(勞動部六面向的最小可用縱切):
  - **A 盤點**:確認任務清單——公版反推「你是不是有做?」勾選卡片 + **抓漏**(「還有沒有
    佔時間但沒提到的?」→ add_duty/add_task);
  - **B 深掘**:逐任務細項——core 任務 12 槽全套、淺掃 4 槽(黃金範本 §8.3);
    追問受三重保險節流;
  - **C 總審**:變更摘要 + 建議批審(0025 節點批審)+ 完成。
- **①定位沿用既有,不對話化**:intake 三題表單(已有)+ 選職類/選任務用**既有編輯器 widget**
  嵌面板(OccupationPicker / TaskPickerMenu 已驗證);訪談從「文件已有職類+初版任務」起跑,
  A 段負責把任務清單**修對**。
- **非目標(v1)**:重要度確認回合、K/S 對話式策展(留編輯器勾選)、rubric 品質分自動化、
  文件級新章節(協作/績效/工作條件/任職資格——黃金範本完整版,v2)、語音、多語、
  舊 authoring graph 退役(另開 task,新引擎可用後一次清,ADR 0023 決定 6)。

## 1. 契約裁決:任務細項槽位進 `ocs-contract`(**已裁決——維護者授權自審**)

**裁決**:`task["details"]` 以 **additive optional** 欄位進 ocs-contract(JSON-schema SSOT =
[`packages/ocs-contract/schema/ocs-document.schema.json`](../../packages/ocs-contract/schema/ocs-document.schema.json)
的 task $def → codegen pydantic+TS,`check-codegen.sh` 守;contract-strategy row 2 生命週期)。
依據:細項是承重產出、必須活過 finalize/export 的 `_strip_underscore`(document-of-record §3),
且 web/TS 要渲染——三個約束只有正式欄位同時滿足。

```jsonc
"details": {                      // 全部 optional;v1 = 黃金範本 §8.3 的 11 槽(outputs 已有 O 欄)
  "frequency": "每雙週一輪",       // 頻率(自由文字,含事件驅動描述)
  "time_share_pct": 20,           // 工作比重 %(number;全文件加總≈100 由 UI 提示,不進 validate)
  "duration": "2–3 個工作天/輪",
  "volume": "每輪 40–80 條案例",
  "trigger": "sprint backlog 開出後",
  "inputs": "PRD、UI 設計稿、上版缺陷清單",
  "tools": "TestRail、Figma、Jira",
  "collaborators": "PM(需求釐清)、開發 Lead(可測性)",
  "wait_points": "等 PRD 定稿,常延遲 0.5–1 天",
  "exceptions": "需求中途變更→標記受影響案例重審",
  "standards": "組長審查通過;覆蓋全部驗收條件"
}
```

- **為什麼進契約**:細項=產品承重價值(比公版更細),必須活過 finalize/export
  (`_` 前綴欄會被剝,見 document-of-record §3)且 web/TS 要渲染 → 正式欄位。
- **溯源不進契約**:每槽的 `quote`/`verified` 是稽核資料,住**訪談 session**(§2),
  顧問審閱視圖 join;契約文件保持乾淨。
- **工作摘要零新增**:寫進既有 `ocs_profile.job_description`。
- `validate()`(finalize gate)對 `details` **不設必填**——覆蓋率是訪談引擎的門檻,不是契約的。

## 2. 資料模型(api;`npm run db:migrate` 慣例)

| 表 | 欄位(要點) | 用途 |
|---|---|---|
| `interview_sessions` | id, job_profile_id, status(`active/review/done`), phase(`survey/deep/review`), focus(jsonb:任務ref+槽), counters(jsonb:每槽追問數), human_touched(jsonb:path[]), timestamps | 進度列(0023 唯一引擎狀態);**一 profile 同時最多一個 active** |
| `interview_turns` | id, session_id, seq, role(`employee/consultant`), text, commands(jsonb), ts | **逐字稿=溯源真相**(quote 驗證對這裡;勞動部 2.2.2 紀錄義務) |
| `interview_evidence` | session_id, doc_path, quote, turn_seq, verified(bool) | 槽值→員工原話對照(顧問稽核視圖) |
| `interview_suggestions` | id, session_id, doc_path, old_value, new_value, reason, status(`pending/accepted/rejected`), turn_seq | 建議層(0025;= 未套用 diff) |

`human_touched`:人走 PATCH 存檔時,server diff 前後文件、把變動 path 記入 active session
(無 session 則略)——0025 的 provenance,不建獨立鎖。

## 3. 端點(AIP-136 `:verb`,掛既有 `/job-profiles/{id}` router)

| Method Path | 用途 | 錯誤 |
|---|---|---|
| `POST …/interview:start` | 建/續 session(**冪等**:有 active 回同一個);回狀態+第一個 payload | 文件無任務且無職類→409(先走選職類) |
| `POST …/interview:turn` `{answer\|choice\|control}` | 一回合(§4);回 `{say, widget?, doc_changed, progress, pending_suggestions}` | LLM 掛→503(session 不毀,可重試);指令 schema 違規→內部重試後 502+log error(=受限解碼失效,0024 保險絲) |
| `GET …/interview` | session 全貌(續談;**顧問視圖**:turns+evidence+suggestions) | — |
| `POST …/interview:review` `{accept_ids, reject_ids}` | 批審套用(走文件 seam,帶樂觀鎖) | 409 同文件 PATCH 語意 |

> **後記(T9 實作裁決,2026-07-05)**:`:review` 改為**只轉建議狀態**,套用由**前端**以既有
> ocsDoc 純函式 + autosave PATCH 執行——對齊 ai-suggestions 深文檔不變量 1(「提議由前端
> 套用後走 PATCH」),且 add_task/add_duty 的重編碼(renumber)本是前端職權;server 端
> 套用會造成第二個重編點。單一寫入路徑因此更乾淨(人核准的變更=人的寫入)。

## 4. 回合管線(engine service;核心純函式、可 fake 測)

```
① 載入   draft 文件 + session(slots/counters/human_touched)+ 近窗逐字稿
② 組脈絡 結構化狀態優先(當前任務+缺槽+追問預算+黃金範本槽位定義+官方問法片段)
         + 近窗對話(v1 預設近 12 回合,可調)+ 當前任務相關 evidence;
         **不整卷重播**(記憶體研究:結構化 context > raw replay)
③ 一呼   LlmPort.select_schema(role=deep) → TurnOutput{commands[], saturation}
④ 驗證   quote 必須=逐字稿正規化子串(NFKC+空白摺疊,與 matching.core.preprocess 同族);
         失敗 retry 1 次;仍失敗→值收下、evidence 標 unverified
⑤ 執行   確定性 executor:
         · 寫入通道分流(0025):目標 path ∈ human_touched → suggestions;否則直改 draft
           (低風險維度豁免;刪除類永遠阻斷=只能建議)
         · guard:advance 未達覆蓋門檻→拒絕回缺口;ask 超追問預算→強制 skip/advance
⑥ 寫回   draft 走內部同一條 PATCH seam(帶雙 token;409→重讀重放一次,再衝突→建議化)
         + session 更新 + turn/evidence 落庫
⑦ 回應   下一題 / choice widget / 進度 / 建議數
```

**LLM 不選通道、不能繞 guard**——0023/0025 的信任機制全在 executor(確定性碼)。

## 5. 指令詞彙表 v1(9 個;TurnOutput = tagged union array)

| 指令 | 參數 | 備註 |
|---|---|---|
| `reply` | text | 寒暄/銜接/離題拉回 |
| `ask` | question, target_path | 追問(記預算) |
| `ask_choice` | question, options[](**池內 id enum**), target_path | 盤點卡片/選單 |
| `set_slot` | path, value, quote | 填槽(quote 必填) |
| `correct_slot` | path, value, quote | 員工更正 |
| `add_task` | unit_ref, name, quote | 公版外任務(抓漏) |
| `add_duty` | name, quote | 公版外職責(抓漏升格) |
| `skip` | path, reason | justified skip(落 trace) |
| `advance` | next_focus | 換任務/段;**過門檻才生效** |

**schema 紀律(0024)**:TurnOutput 必須落在 provider strict 子集——根 object、
`additionalProperties: false`、欄位全列 `required`(可空用 null union)、tagged union 用
`type` enum + anyOf;**以 provider 官方 supported-schemas 為準**,對抗性驗收腳本首呼即驗
(不支援會直接報錯,不會靜默降級)。

## 6. LLM 接線落地(0024)

- adapter spike:**Pydantic AI `NativeOutput`(首選)** vs openai SDK `response_format`(備選);
  贏家標準=對抗性驗收腳本零池外 + 代碼乾淨;確認後汰換 `langchain_openai`。
- 模型:OpenRouter 底層挑**有原生受限解碼**者(OpenAI/Gemini 系);驗收紀錄留 `docs/specs/`;
  換模型=重跑驗收不改碼。既有 `i in known` 式事後篩保留為保險絲(觸發即 log error)。
- role:B 深掘/總審摘要用 `deep`;A 盤點 choice 用 `cheap`。

## 7. web 面板(0020 載體;鐵律沿用)

- 文件工作台常駐 + 側欄面板;三段軌道進度(盤點 → 深掘 任務x/y → 總審)。
- widget:choice 卡片(盤點)、自由輸入(敘事)、**文件側建議 badge**(新舊對照 popover)、
  總審清單(實質改動預設展開 diff、低風險預設勾;Accept all/逐條)。
- 寫入零新路:面板的人工操作照舊 autosave PATCH;engine 的寫入在 server 端同一 seam。
  池規則/預勾鐵律(design doc 不變量 6)不因面板繞過。
- 員工完成 → 顧問開 `GET …/interview`:逐字稿 + 槽值↔原話對照(evidence)+ 建議歷史。

## 8. 測試策略

- **executor 單測**(假 TurnOutput,無 LLM):通道分流(human_touched/低風險豁免/刪除阻斷)、
  覆蓋門檻拒絕 advance、追問預算強制 skip、quote 驗證失敗降級、409 重放。
- **契約**:details 欄位 schema→codegen 兩端(`check-codegen` 慣例)。
- **模擬受訪者回歸**(TOD user simulator):persona 卡+固定事實表(黃金範本樣張當劇本),
  量槽位正確率/覆蓋率/追問數;**只當回歸網**,上線前配真人試訪。
- **對抗性驗收腳本**(0024):誘導池外 id/違規指令,零逃逸=過,紀錄留 `docs/specs/`。
- **E2E 驗收**:模擬訪談跑出的文件 ≈ 黃金範本樣張(章節/槽覆蓋對照)。

## 9. 升級槽(記縫,不預建)

重要度確認回合(勞動部 7.6)· rubric 品質分(21 條審核指標)· K/S 對話式策展 ·
文件級章節補全(黃金範本完整 8 章)· 相似比對灰區對→鑑別提問(ADR 0022 預留)·
reranker 觸發條件不變 · MCP 曝露 tools(ADR 0007 沿用)。

## 10. 文檔更新義務(同 commit)

- 新深文檔 `docs/design/interview-engine.md`(端到端:面板×引擎×文件 seam;本 spec 定稿後轉寫);
- `apps/api/README.md`(interview 端點面)· `apps/web/README.md`(面板)·
  [`editor-knowledge-pack.md`](../design/editor-knowledge-pack.md)(單一寫入路徑不變量補 engine 分句);
- ocs-contract 變更走 [`contract-strategy`](../contract-strategy.md) §4 交付生命週期。

## 11. 自審紀錄(2026-07-05,維護者授權)

照 brainstorming spec self-review 清單跑過:無占位詞;§0/§4/§5 指令數一致(9);
機制驗證——契約 SSOT 檔與 task $def 位置、`check-codegen.sh`、alembic(`apps/api/alembic/`
+ `npm run db:migrate`)、`_strip_underscore` 剝欄行為、單一寫入路徑教義(editor-knowledge-pack
不變量 2)皆讀碼/讀文檔確認;strict schema 子集向 OpenAI 官方文件查證(enum ✓、
additionalProperties:false ✓、required 全列 ✓,完整清單以官方 supported-schemas 頁+首呼驗證為準)。
模糊點修正:quote 正規化定義、近窗預設值。§1 契約裁決由「待確認」轉「已裁決」(北極星:
細項=產品承重價值)。
