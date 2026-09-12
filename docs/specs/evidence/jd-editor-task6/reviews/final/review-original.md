# Task6 獨立實作審查報告（Claude Opus5，唯讀）

**Spec：PASS**　**品質：APPROVED（附 I1 於 commit 前釐清；不需改動 source）**
BASE `44441672`（Task5 已接受）。未執行任何測試／指令／Git；以下全部為靜態閱讀與 raw log 判讀。

## 一、F5 閉合（明確）

**CLOSED。**

- 修正在 `web/src/jd/useJdSession.ts:156-175`：`change` 讀取移出 `if (!this.dirty)` 區塊，套用前於 **line 169** 重核 `!this.dirty`；已手改時保留 `this.value` 與原 `this.head`（原保存基準），只走 line 174-175 的既有通知分支，未新增保存／重試／rebase／鎖。此重核位於 `refresh()` 全部 await 之後，因此同時覆蓋 metadata/runs、messages/head 兩段 await 期間的手改，不只 change 那一段。
- RED：`evidence/task6-review-dirty-red.log` 為 **1 fail／3 pass**，失敗訊息確為 buffer 被 `AI 新稿` 取代，對應資料遺失情境；GREEN：`task6-review-dirty-green.log` **9 檔 41 passed**；最終 built Web 重開 `task6-browser-reopened.log` `status:PASS`。
- 我未將較早的完整旅程當成此 guard 的實機反例；證據文件本身也已明示此點。
- 一項事實差異見 M1（RED log 取自該測試的較早寫法）。

## 二、規格逐項核對

| 要求 | 結果 | 依據 |
|---|---|---|
| 新增按需 Skill 保留已核准專業規則 | PASS | `write-customized-jd/SKILL.md`（現檔全讀）＋兩 references 對 `method-mapping.md` §2 十二列概念逐條命中：何時足以寫稿／不每輪改稿、全工作範圍與低頻、中立追問與未知停留、案例不成永久任務、成果與要求平行各可多項且不互為父子、K/S 定義一份且關係需支持、數字保範圍、更正有界不連帶刪除、最新已保存對話可先於 Memory、手改是 current 不成訪談事實、雙向核對與誠實收尾、依工具真結果說明保存 |
| 不得含禁止材料（§5） | PASS | 三檔無 schema／持久 ID／digest／DB 細節、無固定輪數或必填欄位、無自評分數、無 fixture 答案內容 |
| 實際 factory 與離線 factory 共用同一顧問指示 | PASS | `api.py:26-39` 定義 `ADVISOR_INSTRUCTIONS`；`api.py:210-211` 實際 `open_service` 使用；`tests/jd_offline_service.py` 由 `analysis_agent.api` import 同一常數；`test_memory_prompt_contract.py` 的 `application_instructions()` 以 AST 斷言該 keyword 必須是 `Name('ADVISOR_INSTRUCTIONS')` 後才回傳模組值，堵住「測試用短 prompt」 |
| 只移除否定句、保留周邊已驗原則 | PASS | diff 顯示 11 句原文逐字保留，僅末句換為能力句，`不顯示隱藏推理` 保留 |
| 三份舊 Skill 僅窄改否定句 | PASS | 每檔僅 1 行變更，原方法內容未動 |
| `/skills` 維持唯讀、不授寫檔權 | PASS | `skills.py:76` 邊界句改為責任分離；`SkillAssets` 仍無 write/edit/delete/upload/execute；`test_jd_skill_contract.py` 對 4 種 mutation 斷言 NotImplementedError／error 且內容不變 |
| 最終 SDK request 的漸進揭露 | PASS | 首個實際 request 含新方法 metadata 與路徑、不含三份正文標題；三次 `read_file` 後正文只以 `function_call_output` 出現，且 `next_request['tools'] == first['tools']` |
| 三個 JD 工具 schema／description 未變 | PASS（見 M3） | `test_jd_end_to_end.py:73-77` 以 SSOT `SCHEMA_PATH` 的 `$defs` 逐 schema 與 description 比對；diff 未觸及 contract／schema |
| 無每輪強制載入方法 | PASS | system prompt 明文不每輪載入；request 僅 metadata；prompt delta 僅新增一行 metadata |
| 來源取得保留既有 current_input 授權 | PASS | `jd_tools.py:199-204` 僅對**同一 reference** 併入既有 metadata 再附 tool_call；`sources.py`／`jd_references.validate_sources` 證實：有 `current_input` 走身分＋canonical 訊息核對，無者必過 `_extraction_range`（未閉合窗必拋）。`test_jd_current_source_acquisition.py` 三案（正向、未發配較寬窗、偽造 payload）與 owner-read guard 一致 |
| 固定六段旅程走真服務／PG／native、真 ID/refs | PASS | `jd_offline_service.py` 只替換 HTTP transport，其餘為真 AnalysisService／router／PostgresSaver／Store／Catalog／JdStore／JdEngine；`create_app` 用 `analysis_agent.api.create_app`；無 live fallback、無縮水 API；初稿由真 `jd_edit` insert/remove 產生，非種入 r2 |
| bootstrap 先於 DB/native/client | PASS | `jd_offline_service.py:143-146` 先 `require_bootstrap()` 再建 engine／saver／store／client；`create_app()`（同檔 183-187）明示 `bootstrap()` |
| 手改→AI 續編的真通知、有界更正、commit 回覆遺失、純聊天取消 | PASS | `test_jd_end_to_end.py` 斷言 `manual_count==3`／`baseline=='known'`；更正以整份 fragment 全值比對（只換月檢文字與 source_refs），故障工作全值不變；遺失案僅 1 次 edit、0 次額外模型請求、僅 1 份 committed ToolMessage；取消後 JD 全值不變且無假 receipt |
| 真瀏覽器旅程與跨程序重開 | PASS（證據界線見下） | `task6-journey.mjs` 由空白建檔起，逐段斷言含「只有一份可編正文」（兩處 `contenteditable` count==1）、歷史 5 筆、來源原問答、network 僅 3001/8091；`--reopened` 對前次快照與原 run 結果做 deep-equal。兩份 console log 均 `status:PASS` 且 document id 相同 |
| Memory 契約不改、delta 各命中一次 | PASS | `fixtures/jd-task6-prompt-delta.json` 三筆 replacement，測試對每筆 `assert matches == 1`；CT25 原件與 CT41/43/48 既有 delta 流程不變 |
| 固定回應不冒稱自然品質 | PASS | 證據文件、`ACCEPTANCE.md`、fixture `purpose`、測試 docstring 均明示；IME／自然品質／真人 P6 標示 NOT RUN |
| 既有 raw 數字與文件宣稱一致 | PASS | 620 passed／151 skipped（72.54s）、JD 156 passed（280.81s）、Memory 45 passed（38.55s）、native 68、Web 最終 41、build/types/lint exit_code 0 全部與 log 一致；`task6-web-tests.log` 的 Web 為 40，文件正確地以 `task6-review-dirty-green.log` 的 41 作最終值 |

## 三、Findings

**Critical：無。** 本次未發現會造成資料遺失、越權、假保存或違反已授權範圍的產品缺陷。

**Important**

- **I1｜凍結包檔案數不一致（`change.diff:2`）**
 觸發：header 宣告 `Explicit files: 32`，但 diff 實際只有 **30** 個 `diff --git` 區段，`manifest.json` 也只有 30 個 source/doc 項。
 影響：獨立審查者無法確認變更集完整；若真有 2 個已改檔未入包（`ACCEPTANCE.md` 提到的 `task6-python-regression.py`／`task6-web-checks.py` 等 helper 是可能人選），這 2 檔等同未經審查即進 commit。
 要求：凍結包須為完整明示變更集（review-brief 第 3 段）。
 最小修正：commit 前更正 header 計數，或補列並補入該 2 個路徑；兩者擇一即可，不需改 source。

**Minor**

- **M1｜RED log 非最終測試檔的 byte-exact 反例**：`task6-review-dirty-red.log:29` 顯示當時 `release({ status:'ok', before_revision_ref:'r0', … })` 為 inline literal，最終 `JdSavedProjection.test.tsx:107` 改用 `change(...)` helper。兩者語意等價、舊碼皆會失敗，但「精確反例」宜註明是同一情境的較早寫法；最終檔以 41 PASS 覆蓋。最小修正：證據文件加半句限定。
- **M2｜端到端測試以相對路徑寫證據**：`test_jd_end_to_end.py:59`（`'../../scratch/task6-e2e-wire.jsonl'`，以 append 開檔）與 `:137`（結果 JSON）依 cwd；換 cwd 會在全部斷言之後才失敗，且 wire log 會跨次累積。最小修正：改用同檔既有的 `jd_offline_service.ROOT` 組絕對路徑，記錄檔改 `'w'`。
- **M3｜schema 比對排除 `$defs`**：`test_jd_end_to_end.py:76` 以 `{k:v for k,v in tools[name]['parameters'].items() if k!='$defs'}` 比對，被 `$ref` 指向的子 schema 內容未逐項核對。最小修正：另加一行比對 `parameters['$defs']` 與 SSOT 對應子定義。（F4 的主要缺口已由此測試的逐 schema／description 比對關閉，此為殘餘覆蓋面。）
- **M4｜`api.py:39-41` PEP8 E302**：常數與 `class DocumentInput` 之間只有 1 個空行。最小修正：補 1 個空行。
- **M5｜F5 之後的下一步未在本包內可核**：dirty 保護後，員工接著保存仍以舊 `head.revision_ref` 當 `base_revision_ref`（`useJdSession.ts:270-273`），其被拒／提示是否足以引導員工，取決於 Task5 已接受的 manual-save admission；本包未含 `jd_service`，我無法核對，故不作判定。同類「晚到寫入覆蓋 buffer」在 `save()` 路徑（`useJdSession.ts:288-298`）靠 `JdEditor.tsx:120-131` 的 capture 階段 `preventDefault` 擋輸入，而真人 IME 已明示 NOT RUN——這是既有 Task5 機制，本切片未要求變更，僅作為與 F5 同類風險記錄，不構成本次 CHANGES REQUIRED。

## 四、實際讀取 vs 未核對

**讀了現檔（全文或指定區段）**：`manifest.json`、`source/docs/specs/evidence/2026-09-10-jd-editor-core-integration.md`、`requirements/review-brief.md`、`requirements/official-skill-preflight.md`、`requirements/method-mapping.md`、`change.diff`（第 1–2849 行，全覆蓋）、`api.py`（1–70、180–229）、`skills.py`（全）、`jd_tools.py`（100–219）、`write-customized-jd/SKILL.md`（全）、`useJdSession.ts`（全）、`JdEditor.tsx`（全）、`context/sources.py`（全）、`context/jd_references.py`（全）、`evidence/` 全部 10 個 log/json/md。

**僅透過 `change.diff` 讀到完整新增內容（未另開現檔）**：`test_jd_skill_contract.py`、`test_jd_end_to_end.py`、`test_jd_current_source_acquisition.py`、`jd_offline_service.py`、`jd-task6-prompt-delta.json`、`core-scenario.json`、`JdSavedProjection.test.tsx`、`task6-journey.mjs`、兩份 references、`ACCEPTANCE.md`、`README.md`、`web/package.json`；六個既有測試檔（`test_context_budget`、`test_native_context_budget`、`test_extraction_role`、`test_postgres_service`、`test_memory_prompt_contract`、`test_read_recovery`）只看了變更 hunk 與其上下文，未讀現檔全文。

**未核對**：`context/jd_types.py`（包內但未讀）；`package-lock.json` 僅看 hunk；`test_analysis_skills.py`、`jd_service`／`jd_store`／`jd_engine`／`conversation`／`service`／`windows_lifecycle`、CT25 golden 與 CT41/43/48 fixtures、`web/README.md`、plan/ADR 原文——**均不在本包內**（不代表不存在）；`docs/specs/evidence/jd-editor-task6/` 的 raw JSON/PNG（`task6-browser-initial.json`、`task6-before-api-crash.json`、`task6-restarted-servers.json`、`task6-browser-reopened.json`、`task6-e2e-result.json`、`task6-web-codegen.log`、`*-final-*.json`）不在包內，因此真瀏覽器與跨程序重開我只能核到**腳本斷言內容＋兩行 console PASS**，無法核對逐值快照；codegen PASS 我沒有 raw 可核。

## 五、優點（簡述）

單一 `ADVISOR_INSTRUCTIONS` 加 AST 身分斷言，杜絕測試短 prompt；來源修正是最小併入且保留兩道陰性守衛；端到端多處用**整份 fragment 全值**比對而非片段包含；旅程腳本自行封住 network origin 與「只有一份可編正文」；文件對 skip≠通過、固定回應≠自然品質、wrapper exit≠pytest 結果的界線陳述準確。

## 六、界線

本次為 Task6 對 BASE `44441672` 的獨立實作審查，**不代表整體跨切片／whole-core 核准**。自然模型品質、真人 IME／P6、正式 authority 切換、備份還原與日常入口仍 NOT RUN；ADR0060 權責不變。固定 HTTP 回應不是自然品質證據。我未執行任何測試，以上通過項均為對斷言與 raw summary 的獨立判讀。
