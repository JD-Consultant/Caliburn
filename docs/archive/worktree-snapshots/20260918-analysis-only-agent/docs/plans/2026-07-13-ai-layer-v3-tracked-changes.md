# AI 層 v3 實作計畫(追蹤修訂直寫+一條腦+品質迴路)— 全細節版

> 依 [ADR 0030](../adr/0030-ai-coedit-tracked-changes-one-brain.md)、
> [研究紀錄 §6 已鎖決策清單](../specs/2026-07-12-ai-layer-redesign-research.md)、
> [現況碼對接附錄](../specs/2026-07-13-ai-layer-v3-code-annex.md)(逐 task 檔:行盤點)、
> [實作技術驗證](../specs/2026-07-13-ai-redesign-raw-impl-verification.md)(OpenRouter/promptfoo/OTel 官方查證)。
> **設計已逐點鎖定,不要重開設計討論**;本檔每個 task 自足,現況行號以對接附錄為準
> (若執行時行號漂移,以附錄描述的結構特徵定位)。

## 全局不變量

- TDD、一 task 一 commit、綠了才 commit、green-before==green-after;收尾 tag `ai-layer-v3`。
- **新載體先上、舊件後拆**(T12 最後);文件功能既有測試(存檔/併發 409/契約/renumber)全程當網。
- 0029 編輯器(選單三型/表格/位置碼)不動;**位置碼重編(renumber)由 web 獨佔**(ocsDoc.ts:86),
  後端永不重編——✓/✗ 落地沿用 ADR 0025 不變量「前端 applyAccepted 落地+renumber」。
- **AI 寫入唯一路徑:scribe op → verify → `_pending`**;任何直改文件的 AI 路徑都是 bug。
- 環境:Bash 先 `pwd`+`git branch --show-current`(cwd 會漂到別的 checkout);api reload 關,改碼手動重啟;
  `PYTHONUTF8=1`;DB 測試 `TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/caliburn`;
  codegen 比對用 `git diff`(autocrlf)。
- 檢索升級包(eval 集→metadata filter→中文分詞→reranker→Qwen3)不在本計畫,另開 plan 可平行。

## 現況五實錘(附錄「全域交叉發現」,決定 task 寫法)

1. scribe 現在**每回合無條件先跑且直寫文件**(service.py:125 呼 scribe_pass;低風險直寫 draft、
   高風險落 `interview_suggestions`)——T4/T5 是寫入模型翻修+回合順序重排,不是小改。
2. 溯源現在住 DB 表 `interview_evidence`(models/interview.py:71),web 追蹤標記靠
   `buildReviewMap` 讀 evidence(reviewMap.ts:20)——T1/T8 把溯源搬進文件 `_pending.src`,
   evidence/suggestions 兩表隨 T12 退場。
3. `_pending` 命名零碰撞(現有底線欄:`_tid/_uid/_id/_refs/_ref/_src/_levelSrc/_notes/...`);
   後端 `_strip_underscore`(ocs_doc.py:140)遞迴刪所有 `_` 開頭 key,export/finalize 都呼——
   **匯出剝 `_pending` 免費**。
4. backstop 現在是 **LLM 版且只在 run_finish 跑**(backstop.py:69 用 select_schema;service.py:287)
   ——T5 重寫成純函式+改成每 N 回合觸發(§6.4 禁令:backstop 禁 LLM 化)。
5. 回合順序現在 **scribe 先、consultant 後**——T5 重排成 consultant 先出訊號位。

---

### T1 契約:`PendingMark` 選填欄位

**現況**:schema 單檔 `packages/ocs-contract/schema/ocs-document.schema.json`,所有 `$defs`
`additionalProperties:true`(:8,19,65,76,87…)→ 加欄非破壞。物件節點=`TaskGroup`(:103)/
`OcuUnit`(:112)/`CompetencyBlock`(:74)/`CodeName`(:17)/`CodeText`(:23)/`OcsAttitude`(:126);
scalar=`OcsProfile.job_description/ocs_code/ocs_level`(:62)與 `TaskDetails` 11 槽(:85)。
`_src/_ref` 是純前端欄位(types/index.ts),不在 schema——不需正名,`_pending.src.ref_urn`
在 PendingMark 命名空間內,不與前端 `_ref` 撞名。codegen:`npm run codegen:py`(datamodel-codegen
→ `src/ocs_contract/models.py`)+`codegen:ts`(json2ts+strip-index-sig.mjs → `types/ocs-document.ts`)
+`check-codegen`。

**改動**:
1. `$defs` 加 `PendingMark`:
   ```json
   {"type":"object","properties":{
     "op":{"enum":["add","mod","del"]},
     "by":{"const":"ai"},
     "turn_id":{"type":"integer"},
     "prev":{},                      // mod 必填(舊值);add/del 不填
     "src":{"type":"object","properties":{
       "ref_urn":{"type":"string"},
       "quote":{"type":"object","properties":{"turn_id":{"type":"integer"},"text":{"type":"string"}},
                "required":["turn_id","text"]}}}
   },"required":["op","by","turn_id"]}
   ```
2. 物件節點(CodeName/CodeText/TaskGroup/OcuUnit/OcsAttitude)加選填 `_pending: PendingMark`。
3. scalar 欄位採**父物件集合式**(附錄方案 a,與 reviewMap doc_path 定位同構):
   `TaskDetails._pending: {<槽名>: PendingMark}`、`OcsProfile._pending: {job_description|ocs_code|ocs_level: PendingMark}`。
4. 跑 `npm run codegen && git diff` 驗兩端生成物;`_pending` 必須是具名 optional prop
   (strip-index-sig 會砍 index signature)。

**測**:schema 驗證帶/不帶 `_pending` 皆過;`check-codegen` 綠;pydantic 端 `PendingMark` 可解析
ref+quote 並存/僅其一/皆無(皆無=僅結構合法,語意由 T3 擋)。
**commit**:`feat(contract): PendingMark修訂標記(物件節點inline+scalar父集合式;ADR 0030)`

### T2 api:審閱事件表+pending 計數(文件變換歸前端)

**現況**:文件存 `document_versions`(JSONB content+version+revision;persistence.py:37-122);
`upsert_draft` 雙 token 樂觀鎖(:70-98)。accept 現況=`interview:review` 端點轉 suggestion 狀態
(interview.py:173-195),**落地由前端 applyAccepted+PATCH**(InterviewPanel.tsx:142)——此分工保留。
無審閱事件表(最近似:evidence.review/suggestions.status,兩表將退場)。migrations 至 0006。

**改動**:
1. migration 0007:新表 `interview_review_events`
   `(id, profile_id, doc_path, decision: accepted|rejected|batch_rejected, op_meta JSONB, created_at)`。
2. 新端點 `POST /job-profiles/{id}/interview:review-events`(批量陣列)——前端 ✓/✗/批量後呼叫,
   純記事件;**文件變換(去標/還原/renumber/PATCH)由前端做**(沿用 0025 不變量,T8 實作)。
3. `GET …/interview` 回應加 `pending_count`(服務端數 content 裡的 `_pending`,供匯出鈕提示)。
4. ledger 摘要(T5)把「上輪被拒清單」讀自本表(§6.3:無聲記帳、下回合利用)。
5. 匯出剝除:確認 export/finalize 對含 `_pending` 文件過 `_strip_underscore`(現況已覆蓋,補一測)。

**測**:事件表寫讀;批量拒絕記單一 batch_rejected 事件;pending_count 正確;export 後無任何 `_pending`;
既有 409 併發測試不變。
**commit**:`feat(api): 審閱事件表+pending計數(✓✗無聲記帳;落地沿0025前端;ADR 0030)`

### T3 verify.py 六查(集中散落守衛)

**現況**:verify.py 不存在。等價守衛散落:`executor.quote_verified`(NFKC+空白摺疊子串比對,
executor.py:46)、`executor.writable_path`(:32)、`executor.get_at/set_at/resolve`(path 解析,
:56-101)、scribe 的 pool_id∈池守衛(scribe.py:102-116);表頭值∈參考集合後端現況**無**強制。
quote 已對 DB 逐字稿比對(service.py:118 `repo.list_turns`)。

**改動**:
1. 新 `app/interview/verify.py`(純函式,無 LLM,無 IO——合法集合/逐字稿/現行 doc 當參數傳入):
   - ①契約合法:op 目標 path 可解析、值過 ocs-contract pydantic;enum 值先正規化
     (`unicodedata.normalize("NFKC")`+casefold)再比官方枚舉。
   - ②quote 存在性:`src.quote.text` NFKC+空白摺疊後必須是該 turn 逐字稿的子字串;查無→整筆拒收,
     錯誤附「該 turn 最接近片段」(用最長公共子串或簡單相似度取 top-1,僅供 retry 提示)。
   - ③來源一致:`src.ref_urn` 必須∈傳入的參考集合合法碼;custom(無 ref)必有 quote;兩者可並存,
     **至少一**。
   - ④寫入權限:op 只能產生/修改/收回 `_pending`;目標已有他筆 `_pending`(同 path)→ 拒收
     (AI 改自己的綠字=同 path 覆寫自己的 pending,允許;判定鍵=`by=="ai"` 且原 op 同源)。
     「無 `_pending` 的內容=已確認」——對已確認節點僅允許 op=mod/del **以 pending 形式**掛標,
     絕無直改值路徑(結構上 T4 只產 pending,此查是防禦性斷言)。
   - ⑤結構不變量:`task_codes`/位置碼欄 path 一律拒收;add task 的父 duty 必須存在;attitude 只掛
     文件層;表頭 `ocs_code` 的 mod 值必須∈profile.selected_ocs_codes;同 path 重複 add→拒收並回
     「已存在」。
   - ⑥尺寸衛生:欄位長度上限(預設 500 字,details 槽 200)、無控制字元、純文字(無 markdown 記號)。
   - 回傳 `VerifyResult{ok, errors:[{op_index, check, message, hint?}]}`——message 可行動
     (哪查沒過+建議),餵 T4 retry。
2. **搬螺絲**(附錄處置表):`quote_verified/normalize`+`get_at/set_at/resolve` 從 executor.py 移入
   verify.py(或並列 `docpath.py`);`_obj/_s/_variant` 從 commands.py 抽到新 `schema_utils.py`;
   scribe/curation/attitudes/backstop 改 import 新位置。executor/commands 剩 v1 死碼,T12 刪。

**測**:六查每查至少一過一擋;幻覺 quote 拒收+hint 含最接近片段;表頭值∈集合;同 path 重複 add 拒;
搬螺絲後全套既有測試綠(import 改向)。
**commit**:`feat(api): verify六查=output guardrail+守衛集中(quote逐字/權限/不變量;ADR 0030)`

### T4 scribe op 化(寫入模型翻修)

**現況**:scribe_schema.py 是多變體 tagged-union(set_slot/record_task_pool/record_task_custom/
draft_indicator/record_attitude_custom/add_custom_task/none,:39-70);scribe.py `apply_scribe`(:71)
確定性落地**三路**(直寫 doc/建議表/證據表),`scribe_pass`(:218)max_retry=1 只回灌 pydantic 錯字串。

**改動**:
1. scribe_schema 改**單一 op 形**(strict):
   `{target_path, op: add|mod|del, value?, src:{ref_urn?, quote?:{turn_id,text}}}` 的陣列;
   舊變體→op 映射:set_slot→`mod details.<槽>`;record_task_pool→`add task(src.ref_urn)`;
   record_task_custom/add_custom_task→`add task(src.quote)`;draft_indicator→`add|mod indicator`;
   record_attitude_custom→`add attitude(src.quote)`。池空不生 ref 選項的零幻覺設計**保留**
   (enum 動態鎖池碼)。
2. scribe_pass 新流程:`select_schema → pydantic → 逐 op 過 verify(T3)→ 全過:落 `_pending`
   (寫 doc 經 `upsert_draft` 雙 token,409 重讀重放一次沿現況 service.py:89-103)→
   部分失敗:retry×2,prompt 尾附 VerifyResult.errors 逐條(op 幾/哪查/hint)→ 仍敗:該 op 丟棄,
   trace 記 `verify_rejected`(T6),ledger 記缺口不打擾使用者`。
3. 刪除三路落地:不再直寫值、不再寫 `interview_suggestions`/`interview_evidence`(兩表資料路徑
   斷源,表本身 T12 退場)。

**測**:op schema strict(OpenRouter `require_parameters:true` 見 T13);映射表逐變體;retry 回灌
內容含具體 check;三次敗丟棄不落 doc;`_pending` 寫入含 src 雙欄。
**commit**:`feat(api): scribe輸出op化→verify→_pending(唯一寫入口成立;ADR 0030)`

### T5 回合重排+議程狀態機+確定性 backstop+疲勞

**現況**:run_turn 順序=scribe 先(無條件)→consultant 後;consultant 純說話無訊號位
(consultant.py:143 組 messages);ledger 三態 covered/declined/unasked(ledger.py:89)+
next_gap(:140)+is_stalled(:186)+can_finish(:218),無 held/boundary/拒絕事件/疲勞;
backstop=LLM 版收尾用;tools.py 僅 2 個 knowledge READ 工具(:19-43)。

**改動**:
1. **重排 run_turn**:①consultant(chat_with_tools)→②consultant 最終輸出改 strict 結構
   `{reply:string, has_material:bool, held_question?:string, boundary?:string}`(select_schema)→
   ③`has_material` 才跑 scribe(T4)→④ledger 更新。
2. ledger 四態:`declined` 更名語意=refused(平滑遷移 ledger_state key);新增
   `held:[{question, since_turn}]`(consultant 回報→存;next_gap 在「當前 topic 收斂後」優先吐 held)、
   `boundary:[{topic, quote, since_turn}]`(硬遮罩:next_gap/backstop/consultant context 一律跳過,
   **無任何程式路徑可自動解除**,僅使用者訊息再提該 topic 時由 consultant 明確確認後移除)。
3. 每輪 coverage 分類:scribe 落的 `_pending` 路徑→自動勾銷對應 checklist 項(現況靠 doc 重算,
   補 pending 也算「已觸及」)。
4. **backstop 重寫**:純函式——每 N 回合(N=5,常數)掃「上次掃描後的逐字稿」,規則比對
   (SLOT_DEFS 關鍵詞/未勾銷 checklist 項的名詞命中),命中且 doc/_pending 無對應→下輪以
   `held_question` 形式排入;**刪 LLM 呼叫**(backstop.py:69 select_schema 整段移除)。
5. 疲勞偵測純函式(ledger 或新 `fatigue.py`):最近 3 則使用者回答長度滑動平均 < 前段 40%
   或命中敷衍短語表(「就這樣」「沒了」「差不多」…)→ `fatigued=True` 供 T10。
6. tools.py 加 `read_document` 工具:回四態視圖(每節點+`status: confirmed|pending_add|
   pending_mod|pending_del`,由 `_pending` 推導)+上輪被拒清單(讀 T2 事件表)。

**測**:訊號位 false 不呼 scribe;held 延後吐出;boundary 不被 next_gap/backstop 覆寫、
使用者重提才解除;backstop 零 LLM 呼叫斷言;疲勞觸發矩陣;四態視圖推導。
**commit**:`feat(api): 回合重排consultant先+議程四態+確定性backstop+疲勞(ADR 0030)`

### T6 tracing 搬家(手動埋 span)

**現況**:authoring/tracing.py=自製 OTel 中立層(setup_tracing/get_tracer :16,:31),
`traced_node`(:38)依賴 langgraph(隨 authoring 死)。llm_openrouter.py:19 已用 get_tracer 且
span 已有 `gen_ai.*` 部分屬性(:83,128,149)。setup_tracing 現由 copilotkit_live_app.lifespan 呼(:27)。

**改動**:
1. 新 `app/observability.py`:搬 setup_tracing/get_tracer,**不搬 traced_node**;
   `app_factory.configure()` 內呼 setup_tracing(T12 換 root 後 tracing 才不斷)。
2. 屬性對齊現行 semconv(驗證報告:`gen_ai.*` 仍 Development;`gen_ai.system` 已棄用→
   **`gen_ai.provider.name`**):model/input・output tokens/finish_reason/latency;手動埋,
   不裝 auto-instrumentation(無 Anthropic auto-instr;只需 otel api/sdk 輕依賴,不違 ADR 0012)。
3. 新 span:`interview.turn`(父)→`consultant.tools`→`scribe.ops`→`verify.result`
   (含 rejected checks 屬性)→`review.event`(accept/reject);`llm.fallback` 與
   `usage.cached_tokens`(OpenRouter 回報欄位)屬性。
4. 測試重指:test_tracing_setup→observability;test_traced_node/test_graph_spans 標記隨 T12 刪。

**測**:span 樹形與屬性斷言;verify 拒收事件入 trace。
**commit**:`refactor(api): tracing搬observability+gen_ai.*手埋(verify/審閱事件span;ADR 0030)`

### T7 skills/ 八檔+載入器+context 分層

**現況**:skills/ 不存在;prompt 全行內常數(CONSULTANT_SYSTEM consultant.py:16、SCRIBE_SYS
scribe.py:26、CURATION_SYS、BACKSTOP_SYS、ATTITUDES_SYS);可回收判準文字另在 authoring 的
prompts/indicator.py 與 deep_nodes/curate_nodes 的 node prompt(K/S/態度/STAR/5W2H)。
context 組裝在 build_consultant_messages(consultant.py:143),無快取分層。
context.py 的 build_prompt/ROLE_HEADER 是 v1 死碼(**勿回收其 set_slot 語彙**)。

**改動**:
1. `app/interview/skills/<name>/SKILL.md` 八檔,**內容大綱與出處**(起草時逐條標來源):
   - `consultant-principles`(常駐):C″ 六規則(§6.5)+開場揭露/議程預覽文案(回收 consultant.py:68)
     +BEI 探針段(回收 :29-42)。
   - `duty-task-structure`:職責/任務定義與切分(iCAP 指引功能陳述「動詞+受詞+條件」;
     O*NET task statement Action>Object>Purpose 三段式+禁則:禁分號/e.g./and-or/寧拆多條;
     粒度=「最小有意義產出單位」)。
   - `output-writing`:工作產出=有形交付名詞句(iCAP 指引原文;「產出內含於任務 purpose」的
     國際對照)。
   - `behavior-indicator`:STAR/ABCD 句式(iCAP)+Bloom 修訂版壞動詞清單(understand/know/
     state/list/demonstrate 禁用)+19 可觀察動詞表。
   - `ks-distinction`:iCAP K/S 定義+ESCO 句式(knowledge=名詞化概念不加動詞;skill=動作短語)
     +S01–S24 官方目錄。
   - `level-judgment`:iCAP 級別 1–6 原文+四判定軸(情境可預測性/監督程度/工作性質/認知能力)
     +SFIA 四軸升階措辭當佐證語言。
   - `attitude-writing`:A01–A14 官方目錄逐字+文件層規則+與 K/S 界線(O*NET Work Styles 16 項
     當補充)。
   - `probing`:laddering 2–3 層+反 under-probe 觸發清單+holding+覆述三時機(§6.5)。
   原料檔:[iCAP 標準](../specs/2026-07-13-ai-redesign-raw-icap-field-standards.md)、
   [國際標準](../specs/2026-07-13-ai-redesign-raw-intl-competency-standards.md)。
   **SME gate:維護者逐檔審改後才算完成。**
2. 載入器(純函式):`skills_for(phase, gap_kind)`→檔案清單;對應表=常駐 principles;
   duty/task 缺口→duty-task-structure;O 槽→output-writing;indicator→behavior-indicator;
   K/S→ks-distinction+probing;level→level-judgment;態度 pass→attitude-writing;深聊→probing。
3. build_consultant_messages 重構三層:前綴 1(system+principles+few-shot 範本,全域凍結,
   Anthropic 系路由時帶 `cache_control`——T13)→前綴 2(參考基準摘要,per-doc)→動態區
   (四態文件+ledger 摘要+近 10 輪全文+舊摘要)。同 session 前綴 byte 級穩定
   (**禁時間戳/UUID 進前綴**)。

**測**:載入對應表逐 kind;前綴穩定性(同 session 兩回合前綴 hash 相等);skill 檔 frontmatter
可解析。
**commit**:`feat(api): skills八檔+確定性載入+context三層快取分層(ADR 0030)`

### T8 web:`_pending` 渲染+✓✗落地(取代 reviewMap)

**現況**:ocsDoc.ts 無 pending 輔助;JobDocTable 標記=藍 AI 徽章+hover 引文(資料源
buildReviewMap 讀 evidence,:370);api.ts 無 accept/reject(現 reviewInterview=建議批審,:163);
匯出走 getDocumentExport(:114)。details 11 槽 chips 呈現(:222-239)。

**改動**:
1. `ocsDoc.ts` 加 pending 輔助:`pendingStatus(node)`(四態推導)、`acceptPending(doc,path)`
   (去 `_pending`;mod=保新值;del=真刪節點)、`rejectPending(doc,path)`(add=刪節點;
   mod=還原 `prev`;del=去標留原)、`listPending(doc)`(路徑+計數)、scalar 集合式
   (`TaskDetails._pending.<槽>`)同套處理。**每次 accept/reject 後呼 `renumber()`**(web 獨佔)。
2. 新 `PendingMark.tsx`:綠字+淡綠底(add/mod;mod 舊值小字副行,樣式同 0029 原名副行)、
   紅字刪除線(del);hover 浮 ✓/✗/?;「?」出處卡=`src.ref_urn` 官方來源行(現有 SourceLine
   樣式)+`src.quote`「第 N 輪:『原話』」。
3. JobDocTable/UnitRow/TaskRow/FieldCombobox 呈現層接 `pendingStatus`;**刪 reviewMap 資料流**
   (buildReviewMap/taskMarks/藍徽章;reviewMap.ts 檔案 T12 刪)。
4. 工具列批量鈕「接受全部(N)/拒絕全部」(N=listPending 計數);筆級淡入(CSS transition,
   doc 更新即觸發)。
5. api.ts:`postReviewEvents(profileId, events[])`(對 T2);✓/✗/批量流程=改 doc(輔助函數)
   →renumber→PATCH(雙 token)→postReviewEvents。匯出鈕:`listPending>0` 時提示
   「還有 N 筆待審,匯出將不含未審項」。

**測**(vitest,src/lib):四態轉移矩陣(accept/reject × add/mod/del × 物件/scalar);renumber
在 accept 後正確;listPending 計數;tsc+lint 乾淨。
**commit**:`feat(web): _pending四態渲染+✓✗?出處卡+批量(取代reviewMap;ADR 0030)`

### T9 web:側欄改造

**現況**:InterviewPanel=整段回的逐字稿泡泡(:162,非 streaming)、ProgressHeader 覆蓋率條(:30)、
ChoiceCard chips(:48)、meta chips(:216)、SuggestionReview 掛在 pending 計數鈕(:188-211,
T12 拆)。後端 interview:turn 是一次性 POST JSON(interview.py:90)——**無串流端點**。

**改動**:
1. 對話呈現:**v1 用打字機動畫**(前端逐字顯示已回全文;體感=字元級 streaming,零後端改動);
   真 SSE 串流端點記縫(觸發條件:單回合 LLM 延遲>8s 需要提早顯示字)。此為降級裁量,理由:
   後端一次性架構改 SSE 是獨立工程,B″ 鎖的是「體感」而非傳輸協定。
2. 議程三態清單:新 `AgendaList` 元件,資料=ledger checklist+四態(T5 的 GET interview 回應),
   樣式=pending/in_progress/completed 勾選清單(update_plan 樣式)。
3. 開場:首回合顯示揭露+議程預覽(文案來自 consultant-principles skill,由後端 opening 回應帶)。
4. chips 升級:選項+`recommended` 標記+永遠附「其他(自由輸入)」(AskUserQuestion 樣式);
   保留 meta chips(跳過/沒有/下一題)。
5. 「正在整理…」狀態:mutation pending 且 has_material 時顯示小指示。
6. 拆 SuggestionReview 掛點(建議層已死),pending 計數改指表格捲動定位。

**測**:AgendaList 三態渲染;chips 推薦標記;打字機動畫可跳過(點擊即全顯)。
**commit**:`feat(web): 側欄=對話+議程三態+chips推薦+開場揭露(ADR 0030)`

### T10 收尾對帳(含 web finish 接線)

**現況**:run_finish=LLM backstop+attitudes_pass→建議化→phase="review"(service.py:268-312);
無三訊號觸發;**web 完全沒接 finish**(api.ts 無函式;route 在 interview.py:135)。

**改動**:
1. 三訊號:`can_finish` 全綠(coverage)∕`fatigued`(T5)∕turn 數≥預算(常數 40)——任一成立,
   下輪 consultant 回應帶 `suggest_finish:true`,側欄顯示「進入收尾對帳」鈕(不強制)。
2. run_finish 重寫:①`attitudes_pass` 產出改走 op→verify→`_pending`(態度綠標)②結構化總結=
   本場寫入清單(從 turn 起點後的 `_pending`+已 accept 事件組)回讀,格式=按職責分組條列+
   「其中 N 筆綠字未審」③收尾語模板(真誠認可,禁罐頭;文案在 consultant-principles)。
3. web:api.ts 加 `finishInterview(profileId)`;側欄收尾卡=總結條列+「補充/更正」輸入框
   (回到 run_turn)+完成鈕。

**測**:三訊號各自觸發 suggest_finish;總結清單=本場 pending∪accepted;態度走 pending 不直寫。
**commit**:`feat(api+web): 收尾對帳(三訊號+總結回讀+finish接線;ADR 0030)`

### T11 evals 基建(promptfoo)

**現況**:`apps/api/evals/interview_sim.py` 已有受訪者模擬(import 現行引擎介面,T4/T5 改介面後
要同步);`scripts/validate_select_schema.py` 可參考。無 promptfoo/golden set/Source Score。

**改動**(細節照 [evals 深挖報告](../specs/2026-07-12-ai-redesign-raw-evals-design.md) 附錄 A/B 與
[驗證報告](../specs/2026-07-13-ai-redesign-raw-impl-verification.md) H3):
1. 佈局:`apps/api/evals/{golden/<case_id>/{transcript.txt,reference.md,rubric.yaml},
   source_score.py, assertions/, promptfooconfig.yaml}`。
2. promptfoo:**Python provider**(`call_api` 包引擎回合;`workers:1` 保狀態)跑單回合斷言;
   **Simulated User provider**(`maxTurns`+persona instructions)跑端到端(persona 含話少型/
   跑題型/自誇灌水型/矛盾型,§6 evals 鎖);deterministic assertions(python 自訂:K/S 歸位、
   位置碼未被寫、結構、Source Score 門檻)先行,`llm-rubric` 留 Phase 2(rubric.yaml 骨架先建)。
3. `source_score.py`:輸入=最終 doc+逐字稿+參考集合;分母=AI 寫入條目(`_pending`∪accepted
   事件),分子=src 過 verify ②③ 者;輸出比率+逐條明細。
4. 第一題 golden:**維護者手造**(transcript 可用 interview_sim 生成後人工修訂;reference=
   維護者顧問級成品)。reference 過 rubric 必須滿分(驗 grader)。
5. CI:`promptfoo/promptfoo-action@v1`,觸發=prompts/skills/引擎碼變更;紅燈擋 merge。

**測**:考卷可跑;reference 滿分;Source Score 對已知造假案例=正確扣分。
**commit**:`feat(evals): golden骨架+Source Score+promptfoo(python provider+simulated user;ADR 0030)`

### T12 舊件退場(依附錄逐檔)

**前置**:T8/T9 綠(新載體上線)。**intake 頁保留**(附錄裁決:純 3 題表單存 job_summary、
零 CopilotKit(檔頭自證 :5),是〔選職類〕預填的活功能——§6.7「純 CopilotKit 入口→退役」前提
不成立)。

**改動**:
1. web 刪:`app/api/copilotkit/route.ts`、`InterruptHandlers.tsx`(已是死碼,無人 mount)、
   `CurationDialog.tsx`(page.tsx:18,211 引用點拆除;其檢查表職能由 T5 議程狀態機+T9 側欄承接
   ——拆前手測「選職類→議程自動含檢查表項」流程)、`SuggestionReview.tsx`(T9 已拆掛點)、
   `reviewMap.ts`+`reviewMap.test.ts`;`Providers.tsx:6,42` 的 CopilotKitProvider 換成原
   QueryClientProvider 結構(**保留 react-query persist,勿連根拔**);package.json 刪
   `@copilotkit/react-core`/`react-ui`/`runtime`(1.61.0)。
2. api 刪:`app/authoring/` 整包(T6 已搬 tracing;prompts/indicator.py 判準先確認 T7 已回收)、
   `copilotkit_live_app.py`;`run_live.py` 改起 `app_factory.configure()` 的 app(**8001 必須
   續服全 REST**——web BASE=8001;setup_tracing 已在 T6 移入 configure)。
3. v1 死碼刪:`executor.py`(螺絲已 T3 搬走)、`commands.py`(`_obj/_s/_variant` 已抽
   schema_utils)、`context.py`(build_prompt/ROLE_HEADER)+對應 4 個 test 檔
   (test_interview_executor/commands/context、test_copilotkit_live_app、test_traced_node/
   test_graph_spans)。
4. DB:migration 0008 停用/刪 `interview_evidence`、`interview_suggestions`(T4 後無寫入方;
   歷史資料不搬——draft 期產品無存量包袱,確認後直刪)。
5. `npx turbo test` 全綠+tsc+lint;`npm run up` 起服手測:訪談全流程(開場→綠字→✓✗→收尾)
   +編輯器全功能+匯出。

**commit**:`refactor(api+web): 舊圖/CopilotKit/彈窗載體/v1死碼退場(0023清償;ADR 0030)`

### T13 工程輕項(OpenRouter 顯式設定)

**現況**:llm_openrouter.py `model_for_role`(:31)五 role;無 models fallback/provider 物件/
parallel/streaming;agent_loop 假設序列工具回填(:44-55)。

**改動**(參數名照[驗證報告](../specs/2026-07-13-ai-redesign-raw-impl-verification.md)):
1. 請求體加 `models:[主,備]`(備援先過 T11 考卷)+`provider:{allow_fallbacks:true,
   require_parameters:true}`(**require_parameters 保證只路由到支援 strict/tools 的 provider**)。
2. `parallel_tool_calls:true`+agent_loop 改支援同輪多 tool_call 成對回填。
3. streaming:側欄走打字機(T9),後端維持一次性;`complete_*` 逾時+指數退避尊重 Retry-After。
4. 快取:OpenAI 系自動;adapter 註記——**若 role 路由到 Anthropic 系,必須在前綴 content block
   帶 `cache_control`,否則完全不快取**(驗證報告 H1 頭號雷);讀 `usage.prompt_tokens_details.
   cached_tokens` 進 trace(T6)。
5. 模型 role 顯式表:consultant(interview role,強推理)/scribe(select role,便宜 strict)/
   judge(Phase 2,另家)/backstop 已無 LLM。

**測**:require_parameters 請求體斷言;parallel 回填;fallback 觸發記 trace。
**commit**:`feat(api): OpenRouter顯式fallback+require_parameters+parallel tools(ADR 0030)`

### T14 文檔同步+收尾

1. `docs/design/` 新增「訪談引擎 v3 端到端篇」(dual-audience:動作→請求、真名、不變量、
   退役禁令——「verify 必 blocking」「backstop 禁 LLM 化」「✓/✗ 無聲」「renumber web 獨佔」
   「AI 寫入唯一路徑 op→verify→_pending」);更新既有訪談 design 篇與 CLAUDE.md 指路
   (skills/observability 新增)。
2. 全綠驗收:`npx turbo test`+api 直跑含 DB+web vitest/tsc/lint;`npm run up` 手測全流程。
3. tag `ai-layer-v3`。
**commit**:`docs(design): AI層v3端到端文檔同步(ADR 0030)`

## 順序依賴

T1→T2→T3→T4→T5(引擎鏈,嚴格順序);T6 可在 T3 後任意點;T7 依 T5(gap kind);
T8 依 T1/T2;T9 依 T5/T8;T10 依 T4/T5/T9;T11 依 T4–T7;**T12 依 T8/T9 綠**;
T13 隨時;T14 最後。

## 執行時遇到的未決點處理

行號漂移→按附錄結構特徵定位;附錄/驗證報告未覆蓋的新問題→先查權威資料,查不到且屬產品
裁量→問維護者,**不腦補**。
