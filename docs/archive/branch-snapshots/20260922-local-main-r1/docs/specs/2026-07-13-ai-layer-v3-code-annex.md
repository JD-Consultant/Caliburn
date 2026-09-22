# AI 層 v3 對接附錄（T1–T14 現況碼盤點）

> 產出對象:[docs/plans/2026-07-13-ai-layer-v3-tracked-changes.md](S:\caliburn\docs\plans\2026-07-13-ai-layer-v3-tracked-changes.md) 的執行 session。
> 只讀盤點,未改任何碼。分支已驗證 `research/llm-interview-integration` @ `S:\caliburn`。
> 每節=**現況事實(檔:行)** → **落點建議** → **風險**。文末附「executor/commands 處置」與「intake 頁裁決」。

---

## 全域最重要的五個交叉發現(先讀)

1. **scribe 現在是直寫,不是 op→verify→pending**。`service.run_turn` 每回合**無條件先跑 scribe_pass**
   (scribe.py:125),`apply_scribe` 直接回 `new_doc` 並經 `_persist_scribe_doc` 用 `upsert_draft`
   雙 token 寫進 draft(service.py:78-103)。低風險項(pool/slot)**直寫文件**、高風險項(custom/
   indicator/add_task)才落 `interview_suggestions` 建議表。T4 要把**全部**收斂成「op→T3 verify→
   `_pending` 載體」,是寫入模型的根本翻修,不是小改。

2. **溯源現在住 DB 表、不住文件**。quote/verified/review 住 `interview_evidence`
   (models/interview.py:71),web 的追蹤修訂靠 `buildReviewMap` 讀 evidence(review=="pending")
   (reviewMap.ts:20)。T1/T8 要把溯源搬進**文件節點的 `_pending.src.quote`**。evidence 表角色會
   變(→ 帳本事件表或退場)。

3. **`_pending` 命名零碰撞、且匯出自動剝除**。文件節點現有底線欄:`_tid/_uid/_id/_refs/_ref/
   _src/_levelSrc/_notes/_prerequisites/_supplements`(見 ocsDoc.ts、JobDocTable.tsx:188),**無 `_pending`**。
   後端 `_strip_underscore` 遞迴刪**所有** `_` 開頭 key(ocs_doc.py:140),`assemble_final`(finalize)
   與 export 都呼它 → **只要叫 `_pending`,匯出/定稿剝除是免費的**(T2「匯出剝 `_pending`」幾乎不用寫)。

4. **backstop 現在是 LLM 版、且只在收尾跑** —— 與 plan 直接矛盾。`backstop_pass` 用
   `llm.select_schema`(backstop.py:69),只在 `run_finish` 呼叫(service.py:287)。T5/§6.4 要求
   backstop = **每 N 回合的確定性掃描(禁 LLM)**。T5 必須把 backstop 從 LLM 重寫成純函式,並改觸發點。

5. **執行順序與「按需喚醒」相反**。現在 scribe **先跑**(每回合、無條件),consultant **後跑**。
   T5/§6.2 要 consultant 先出「有無素材」訊號位 → 有才喚醒 scribe。這是回合流程的**重排**
   (service.run_turn 的 ①→③ 順序要倒過來或加分類前置)。

---

## T1 契約:`_pending` 選填欄位

**現況事實**
- Schema 單一檔:[packages/ocs-contract/schema/ocs-document.schema.json](S:\caliburn\packages\ocs-contract\schema\ocs-document.schema.json)。
  所有 `$defs` 都 `additionalProperties: true`(schema:8,19,65,76,87…)→ 加選填 `_pending` **非破壞性**。
- 節點型別:`TaskGroup`(:103,含 `task_codes`/`competency_blocks`/`details`)、`OcuUnit`(:112)、
  `CompetencyBlock`(:74,含 `indicators`(CodeText)/`outputs`/`knowledge`/`skills`(CodeName))、
  `TaskDetails`(:85,11 個 scalar 槽,全 optional nullable)、`OcsProfile`(:62,`job_description` 是
  裸 string)、`OcsAttitude`(:126)。
- `CodeName`/`CodeText`(:17,:23)是 `{code,name|text}` 物件 → OPLKS 條目可直接掛 `_pending` 子物件。
- **`_src`/`_ref` 目前不在 schema、也不在 pydantic** —— 它們是**純前端型別欄位**(types/index.ts +
  ocsDoc.ts 的 `setCategory`/`taskFromPool` 等),靠 `additionalProperties:true` 穿透。TaskDetails 的
  註解明說「溯源(quote)不落文件,住訪談 session」(schema:88)。
- codegen 兩條(package.json:9-12):`codegen:py`= `datamodel-codegen … pydantic_v2.BaseModel`
  → `src/ocs_contract/models.py`;`codegen:ts`= `json2ts` + `scripts/strip-index-sig.mjs`
  → `types/ocs-document.ts`。`check-codegen`= `scripts/check-codegen.sh`(diff 驗生成物同步)。

**落點建議**
- `_pending` 定義成一個 `$defs`(如 `PendingMark`:`{op,by,turn_id,prev?,src?:{ref_urn?,quote?:{turn_id,text}}}`),
  以選填 property 掛到 **CodeName / CodeText / TaskGroup / OcuUnit**(這四個是「物件節點」)。
- **表頭主基準/自由文欄的落點**:`job_description`、`ocs_code`、`ocs_level`、`details.*` 全是 **scalar**,
  無法在標量上掛 `_pending`。落點二選一:(a) 在**父物件**掛集合式 `_pending`(如 `TaskDetails._pending:
  {frequency:{op,...}}`、`OcsProfile._pending:{job_description:{...}}`);(b) 把這些欄位包成物件。
  建議 (a)——與現有 `reviewMap` 用 `doc_path` 定位的做法同構,改動面最小。
- codegen 後**務必**跑 `npm run codegen && git diff`(CLAUDE.md:autocrlf 用 `git diff` 不看原始 diff),
  確認 pydantic + ts 兩端都生出 `_pending` 選填欄(`strip-index-sig.mjs` 會砍 index signature,
  故 `_pending` 必須是**具名 optional prop** 才會出現在 TS 型別)。

**風險**
- scalar 槽(details 11 槽 + 表頭)無法掛 inline `_pending` —— 這是 T1 最需要先定案的落點,牽動 T2/T8。
- `additionalProperties:true` 讓 web 早已偷塞 `_src/_ref/_levelSrc` 而 schema 從不知情;若 T1 想把
  `_pending.src.ref_urn` 正名,要留意別和前端既有 `_ref`(池身分引用)語意撞名。

---

## T2 api:修訂層核心操作

**現況事實**
- 文件存 `document_versions`(JSONB `content` + `version` + `revision`;persistence.py:37-122)。
  `DocRepo.upsert_draft` 是唯一並發守衛點:`expected_version`+`expected_revision` **兩者皆給**才做樂觀鎖,
  不符 raise `DocConflictError`(persistence.py:70-98)。`revision` 由 SQLAlchemy `version_id_col` 自增。
- 現有寫入路徑:PATCH `…/document`(web 走 `patchDocument`,api.ts:97;守衛用 `?expect_version&expect_revision`)。
  引擎側寫入走 `service._persist_scribe_doc`(scribe.py 直改 → upsert_draft;409→重讀重放同 records 一次
  →再衝突放棄,service.py:89-103)。
- **帳本/事件表現況**:沒有專屬「審閱事件表」。最接近的三張:`interview_evidence.review`
  (auto/pending/accepted/reverted,models:86)、`interview_suggestions.status`(pending/accepted/rejected,
  models:103)、`interview_llm_calls`(稽核,models:113)。accept/reject 現況=`interview:review` 端點只
  **轉 suggestion 狀態**,實際套用由**前端** `applyAccepted` + PATCH(interview.py:173-195、InterviewPanel.tsx:142)。
- migrations:0003 建四表、0004 加 `ledger_state`、0005 加 evidence.review、0006 建 llm_calls。

**落點建議**
- pending 寫入/accept(去標)/reject(還原 prev 或整筆移除)= 對 `document_versions.content` 內的 `_pending`
  做確定性操作的**新服務**(建議放 `app/services/` 或 `app/interview/` 的 revision 模組),沿用 `upsert_draft`
  雙 token 併發守衛(**不變量:409 行為不變**)。
- 「匯出剝 `_pending`」→ 已由 `_strip_underscore` 覆蓋(見全域發現#3),只需確認 export/finalize 路徑
  對含 `_pending` 的 doc 跑過即可,幾乎零新碼。
- 審閱事件(accept/reject/批量拒絕)→ **建議新增事件表**(migration 0007),或擴充語意重用
  `interview_suggestions`。§6.3 要「無聲事件、下一回合才被 AI 利用」→ 事件要能被 context 讀成帳本摘要。

**風險**
- 現在「accept 由前端 applyAccepted 落地 + renumber」(ADR 0025 不變量)。T2 把 accept 改成「後端去 `_pending` 標」
  時,要決定 renumber(位置碼)還歸不歸前端 —— 位置碼由 web `renumber()` 獨佔(ocsDoc.ts:86)。若後端直接
  去標寫回,**位置碼可能不重編**。這條「誰 renumber」必須在 T2/T8 交界講清楚。
- reject「還原 prev」需要 `_pending.prev` 存舊值;mod op 才有 prev,add/del 語意不同,四態轉移矩陣要覆蓋。

---

## T3 verify.py(六查,新模組)

**現況事實**
- **`app/interview/verify.py` 不存在**(全新)。
- 現有等價守衛**散落**:`executor.quote_verified`(NFKC+空白摺疊子串比對,executor.py:46)、
  `executor.writable_path`(白名單,executor.py:32)、`executor.set_at/get_at/resolve`(path 解析,executor.py:56-101)、
  scribe 的 pool_id∈池、kind↔pool_id 語義守衛(scribe.py:102-116)、位置碼「誰寫都拒」目前靠 schema 不給
  set_slot 寫 task_codes(commands.py:112 註解)、表頭值∈參考集合目前**無**後端強制(web 端 `isOfficialBasis` 判定)。
- quote 對「DB 逐字稿」比對現況:`quote_verified(quote, employee_texts)`,employee_texts 由
  `repo.list_turns` 撈(service.py:118)—— 已是 DB 真相,符合 §6.2「verify 對 DB 查」。

**落點建議**
- verify.py 純函式化,把上述散落守衛**集中**:①契約合法(可呼 ocs-contract pydantic + enum 正規化)
  ②quote 存在性(搬 `quote_verified`)③ref∈參考集合(需吃 pack/knowledge 的合法碼集)④寫入權限
  (禁無聲改已確認 → 需比對目標節點是否已「確認」態)⑤結構不變量(位置碼拒收、任務必掛職責、表頭值∈參考集)
  ⑥尺寸衛生。
- 把 `quote_verified/normalize` 從 executor.py **移進 verify.py**(executor 是退場候選,見文末),
  scribe/curation/attitudes/backstop 改 import verify。

**風險**
- 「④禁無聲改已確認」需要一個「已確認」判定:現在文件沒有「確認態」欄位(human_touched 住 session,
  不在 doc)。§6.3 說「已確認=單一等級,不分作者」。要新增判定來源(可用「無 `_pending` = 已確認」)。
- 「表頭值∈參考集合」目前後端**完全沒管**(web 自律)。T3 要新引入,需拿到 profile 的 `selected_ocs_codes`
  / pack 當合法集,verify 才有得比對 —— 純函式要把這集合當參數傳入。

---

## T4 scribe op 化

**現況事實**
- [scribe_schema.py](S:\caliburn\apps\api\app\interview\scribe_schema.py):**多變體 tagged-union**
  strict schema —— `set_slot`/`record_task_pool`/`record_task_custom`/`draft_indicator`/
  `record_attitude_custom`/`add_custom_task`/`none`(scribe_schema.py:39-70);pydantic
  `ScribeOutput.records`(:133)。每變體 enum 全鎖死、池空不生變體(零幻覺設計)。
- [scribe.py](S:\caliburn\apps\api\app\interview\scribe.py):`apply_scribe`(:71,確定性落文件/建議/證據)
  + `scribe_pass`(:218,`max_retry=1`;失敗回 `records_failed=True` 不擋回合)。兩通道=池項直寫官方碼、
  自訂走建議層附 quote(:99-151)。
- 現況**沒有** op 的 `{目標URN, add|mod|del, 欄位, 值, 出處}` 統一形;src「ref+quote 並存」也沒有
  ——現在是「pool 走 code、custom 走 quote」二分。

**落點建議**
- scribe_schema 改成**單一 op 形**(add|mod|del + 欄位 path + 值 + `src:{ref_urn?, quote?}` 至少一)。
- scribe_pass 流程改:`select_schema → pydantic → 逐 op 過 T3 verify → 失敗 retry×2 回灌**具體失敗條目**
  (現在 retry 只回灌 pydantic 錯字串,scribe.py:240)→ 過關落 `_pending`(走 T2)`;再敗丟棄記 trace`。
- `apply_scribe` 的確定性落地邏輯大半可回收,但輸出目標從「new_doc/suggestions/evidence 三路」改成「`_pending` op 一路」。

**風險**
- retry 回灌「具體失敗條目」需要 T3 verify 回**逐條可行動錯誤**(哪個 op 哪查沒過 + 最接近原話建議);
  現在 retry 只有 pydantic 例外字串。T3 與 T4 的錯誤格式契約要對齊。
- 現有 `record_attitude_custom`/`draft_indicator` 是機會性提議;op 化後這些要映到 op 的哪種欄位/來源,要定義。

---

## T5 consultant 訊號位 + 議程狀態機 + backstop

**現況事實**
- [consultant.py](S:\caliburn\apps\api\app\interview\consultant.py):`build_consultant_messages`(:143)組
  system 人格(`CONSULTANT_SYSTEM`:16)+ `<進度>`(ledger_summary)+`<文件現況>`+`<待核准建議>`+近 12 輪。
  **輸出無「有無素材」訊號位**(現在 consultant 純說話 + READ 工具,chat_with_tools)。
- [ledger.py](S:\caliburn\apps\api\app\interview\ledger.py):覆蓋帳本,**非議程四態機**。有 `checklist`
  三態 covered/declined/unasked(:89)、`next_gap` 優先序(:140)、`is_stalled`/`note_attempt`
  飽和偵測(:186-197)、`can_finish`(:218)。`declined` 住 `ledger_state["declined"]`(≈ refused)。
  **無 held / boundary、無「拒絕事件」、無「每輪 coverage 分類勾銷」的顯式機制**(勾銷靠 doc 重算)。
- [backstop.py](S:\caliburn\apps\api\app\interview\backstop.py):**LLM 版、收尾用**(見全域發現#4)。
- [tools.py](S:\caliburn\apps\api\app\interview\tools.py):2 個 READ 工具
  `knowledge_search_occupations`/`knowledge_occupation_brief`(:19-43),**無「文件讀取工具回四態視圖」**。
- **無疲勞偵測**(回答長度滑動平均 / 敷衍短語)—— 全新。

**落點建議**
- consultant 輸出加訊號位:最省是讓 consultant 的結構化輸出多帶 `has_material:bool`,service 據以決定跑不跑 scribe。
- ledger 加 held/boundary 兩態 + 拒絕事件(存 ledger_state 或新事件表);`declined` 可平滑升成 `refused`。
- backstop **重寫成確定性**(掃 DB 逐字稿撿漏,禁 LLM),觸發點從 run_finish 改成 run_turn 每 N 回合。
- 新增文件讀取工具回四態視圖(pending 四態);疲勞偵測純函式放 ledger 或新模組。

**風險**
- 「訊號位省呼叫」要求 consultant **先跑**、scribe 後跑 —— 與現在 scribe-first 相反(全域發現#5)。
  service.run_turn ①③ 順序要重排。
- boundary「AI 不得自行解除」需要一個不可被 next_gap 覆寫的硬遮罩;現在 next_gap 只有 skip/stall 兩種跳過。

---

## T6 tracing 橫切層搬家

**現況事實**
- [app/authoring/tracing.py](S:\caliburn\apps\api\app\authoring\tracing.py):自製 OTel(非 langfuse)。
  `setup_tracing`/`get_tracer`(:16,:31)是廠商中立、預設近 no-op;**但 `traced_node`(:38)依賴
  `langgraph.errors.GraphBubbleUp`(:11)** —— graph-node 專用,隨 authoring 死。
- import 者:`llm_openrouter.py:19`(`get_tracer`,已用 `gen_ai.*` span 名:83/128/149,屬性已含
  system/model/tokens)、`copilotkit_live_app.py:22`(`setup_tracing`,隨 T12 死)、authoring 各 node
  (build_doc/curate_nodes/nodes/deep_nodes,隨 T12 死)。
- 測試依賴:test_tracing_setup / test_traced_node / test_graph_spans / test_llm_tracing 都
  `from app.authoring.tracing import …`(要重指或隨 traced_node 退場)。

**落點建議**
- 把 `setup_tracing`/`get_tracer` 搬到 `apps/api/app/observability.py`;**丟掉 `traced_node`**(graph 專用)。
- `llm_openrouter.py` 改 import;`gen_ai.*` 命名已到位(:83,128,149),補齊 finish_reason/latency + verify
  結果 span + 審閱事件 span。
- test_tracing_setup 重指新模組;test_traced_node/test_graph_spans 隨 authoring 退場(T12)一起刪。

**風險**
- `setup_tracing` 目前也在 `copilotkit_live_app.lifespan` 呼叫(:27);T12 換 run_live 到 app_factory 後,
  新 composition root 要有人呼 `setup_tracing()`(否則 tracing 不啟)。

---

## T7 skills/ 八檔 + 載入器 + context 分層

**現況事實**
- **`app/interview/skills/` 不存在**;interview 底下**沒有 .md prompt 檔**。現有 prompt 全是**行內常數**:
  `CONSULTANT_SYSTEM`(consultant.py:16)、`SCRIBE_SYS`(scribe.py:26)、`CURATION_SYS`(curation.py:20)、
  `BACKSTOP_SYS`(backstop.py:19)、`ATTITUDES_SYS`(attitudes.py:19)、`ROLE_HEADER`(context.py:14,v1 死碼)。
- 可回收的**既有判準文字**:上述行內常數 + authoring 的 `prompts/indicator.py`(唯一 prompt 檔,隨 authoring 死)
  + `deep_nodes.py`/`curate_nodes.py` 的 node prompt(K/S/態度/STAR/5W2H 判準)。
- [context.py](S:\caliburn\apps\api\app\interview\context.py):`build_prompt` 是 **v1 死碼**(只被測試引用,
  非 runtime;見文末 executor/commands 分析)。真正在跑的 context 組裝在 `consultant.build_consultant_messages`
  (consultant.py:143),**無快取分層**(每回合重組 system+動態,無前綴凍結)。

**落點建議**
- 八檔 SKILL.md 起草放 `app/interview/skills/<name>/SKILL.md`;載入器=按欄位/階段確定性對應(對到
  ledger 的 gap kind / phase)。
- context 快取分層改造點在 `build_consultant_messages`:前綴1(system+總則+few-shot 全域凍結)、前綴2
  (本文件參考基準,per-doc 凍結)、動態區。近 10 輪全文 + 舊摘要。
- **維護者審改 skill(SME gate)** —— agent 只起草。

**風險**
- `ROLE_HEADER`(context.py)含 `set_slot`/落槽語彙,是 **v1 心智**;起草 skill 時別回收這段舊語彙
  (與 v2 顧問無寫入權矛盾)。回收 `CONSULTANT_SYSTEM` 的 BEI/探針段(consultant.py:29-42)才對。

---

## T8 web:修訂層渲染與審閱

**現況事實**
- [ocsDoc.ts](S:\caliburn\apps\web\src\lib\ocsDoc.ts):文件操作全表 —— `renumber`(唯一重編點,:86)、
  `setOp/setKS/setAttitudes/setTaskLevel`(:445-519)、`addFromPool/addTasksToUnit/addCustomTask/addCustomDuty`
  (:352-414)、結構編輯 `add/delete/rename/relocate*`(:239-331)、`ensureIds`(:61)、`completion`(:521)。
  **無 pending 輔助**(全新)。
- [JobDocTable.tsx](S:\caliburn\apps\web\src\components\interview\JobDocTable.tsx):渲染路徑
  `JobDocTable→UnitRow→TaskRow`;OPLKS 用 `FieldCombobox`(:182-218)、details 11 槽用 chips(:222-239)。
  **現況 AI 標記=藍色「AI」徽章 + hover 引文**,資料源 `reviewMap`(buildReviewMap 讀 evidence,:370)
  —— **不是**四態綠紅追蹤修訂。`taskMarks` 用雙形 prefix(uid/index)對位(:124)。
- [reviewMap.ts](S:\caliburn\apps\web\src\lib\reviewMap.ts):`buildReviewMap`(:20)只認 review=="pending"。
  這整個 reviewMap 機制是 T8 要**取代**的(§6.7 明列 reviewMap+D7 徽章退場)。
- `PendingMark` 元件不存在(全新);`lib/api.ts` **無 accept/reject 端點**(現有 `reviewInterview` 是
  suggestion 批審,api.ts:163)。

**落點建議**
- ocsDoc.ts 加 pending 輔助(讀 `_pending` → 四態);新 `PendingMark` 元件(綠字淡綠底/舊值副行/紅刪除線)。
- 渲染改吃**文件內 `_pending`**(取代 reviewMap 讀 evidence)。details scalar 槽的 `_pending` 落點依 T1 決議。
- api.ts 加 accept/reject 端點(對 T2 新端點)。

**風險**
- details 11 槽現在是 chips 純呈現;若 T1 把 details 的 `_pending` 掛在 `TaskDetails._pending` 集合式,
  `taskMarks`/`DETAIL_SLOT_LABELS`(reviewMap.ts:13)的對位邏輯要改寫。
- 「匯出鈕待審提示 N 筆」:匯出走 `getDocumentExport`(api.ts:114,後端 strip),web 要先數 `_pending` 筆數。

---

## T9 web:側欄改造

**現況事實**
- [InterviewPanel.tsx](S:\caliburn\apps\web\src\components\interview\InterviewPanel.tsx):現況=
  逐字稿泡泡(:162,**非字元級 streaming**,整段回)、`ProgressHeader` 覆蓋率條(:30)、
  `ChoiceCard` chips(:48,結構化選項)、底部 meta chips「跳過/沒有/下一題」(:216)、
  pending 計數鈕 + `SuggestionReview`(:188-211)。
- widget 派發:`open_picker` 在 mutation `onSuccess` 一次性派發(:110,防重彈迴圈,有真人實測教訓註解)。
- **無**:開場議程預覽、議程三態清單(pending/in_progress/completed)、「正在整理…」狀態、
  推薦標記 chips。progress 只有 phase + coverage,無議程項清單。

**落點建議**
- 側欄大改:接字元級 streaming(需後端 SSE/stream 支援,現在是一次性 JSON turn)、議程三態清單(資料源=ledger
  四態,依賴 T5)、開場揭露(`opening_disclosure` 已在 consultant.py:68 有文案可回收)、chips 加推薦+Other。

**風險**
- 字元級 streaming 現在後端不支援(interview:turn 是一次性 POST 回 JSON,interview.py:90)。T9 若要真 streaming
  需後端串流端點 —— **這是 plan 未明列的隱藏工作量**,或降級成「打字機動畫」假 streaming。
- 議程三態清單依賴 T5 的 ledger 四態資料先就緒(順序依賴 T9 依 T5)。

---

## T10 收尾流程

**現況事實**
- [service.run_finish](S:\caliburn\apps\api\app\interview\service.py):現況=backstop 複查(LLM)+ 態度收尾
  pass(attitudes_pass)→ 建議化 → `phase="review"`(:268-312)。收尾**無三訊號觸發**(是端點被呼才收)、
  **無結構化總結對帳**。`can_finish`(ledger.py:218)給 blockers 但不主動觸發收尾。
- [attitudes.py](S:\caliburn\apps\api\app\interview\attitudes.py):`attitudes_pass`(:48)讀全逐字稿整體編碼 2–4 條。
- **web 無 interview:finish 呼叫**(api.ts 沒有 finish client 函式!route 有 interview.py:135,web 沒接)。

**落點建議**
- 三訊號(coverage 全勾銷 / 疲勞 / 輪數預算)任一觸發 → service 主動走收尾對帳。coverage 訊號可用 `can_finish`,
  疲勞來自 T5,預算來自 turn count。
- 結構化總結對帳=回讀本場寫入清單(可從 `_pending` + 已 accept 的清單組)。
- **web 要新增 finish 接線**(api.ts + 側欄鈕)。

**風險**
- 「總結內容=本場寫入清單」的資料源:現在寫入散在 doc(直寫)+ suggestions 表。op 化(T4)後統一到 `_pending`
  才好回讀 → T10 依賴 T4 完成。

---

## T11 evals 基建

**現況事實**
- 已有 `apps/api/evals/`(`interview_sim.py`,import consultant/ledger/attitudes/curation/scribe/tools,
  見 grep evals\interview_sim.py:26-31)—— 目前是模擬器,**非 promptfoo golden set**。
- **無** `promptfooconfig.yaml`、無 golden set 骨架、無 Source Score 計算、無 CI wiring。
- `scripts/validate_select_schema.py` 有 schema 驗證骨架(引用 TurnOutput/scribe_schema,可參考)。

**落點建議**
- 照 plan 抄 evals 深挖報告附錄建 golden set 骨架 + Source Score + promptfoo。可回收 interview_sim.py 的
  受訪者模擬。

**風險**
- interview_sim.py 依賴目前引擎介面(scribe_pass 等);T4/T5 改介面後 sim 要同步(T11 順序依賴 T4–T7)。

---

## T12 舊件退場(§6.7)

**現況事實 —— intake 頁裁決(重點)**
- [documents/[id]/intake/page.tsx](S:\caliburn\apps\web\src\app\documents\[id]\intake\page.tsx):
  **純 3 題表單**,送出存 `job_summary` 到 profile(:52 `updateProfile`),**完全不碰 CopilotKit**
  (檔頭註解 :5 明說「非對話、不碰 CopilotKit」)。**這是活功能,不是 CopilotKit 入口**。
  → **裁決:保留**(§6.7「純 CopilotKit 入口→退役」不適用)。它餵 job_summary 給後續〔選職類〕搜尋
  預填(document page.tsx:200)、CurationDialog 預勾脈絡。

**現況事實 —— CopilotKit 引用點(逐檔)**
- `apps/web/src/components/layout/Providers.tsx:6,42` —— `CopilotKitProvider` 包全 app(頂層 wiring)。
- `apps/web/src/app/api/copilotkit/route.ts` —— runtime 端點,連 8001 `/copilotkit`(整檔退場)。
- `apps/web/src/components/interview/InterruptHandlers.tsx:7` —— `useInterrupt`;**但此元件全 repo 無人 mount**
  (grep 僅出現在自身檔案)→ **已是死碼**,直接刪。
- `apps/web/package.json` —— deps:`@copilotkit/react-core` / `react-ui` / `runtime` 各 `^1.61.0`
  (注意:Providers.tsx import 的是 `@copilotkit/react-core/v2`,InterruptHandlers import `/v2`;
  但 package.json 是 1.61.0 —— v2 子路徑)。三個 dep 全刪。
- `CurationDialog`(document page.tsx:18,211 使用中)、`SuggestionReview`(InterviewPanel.tsx:13,203 使用中)、
  `reviewMap`+`buildReviewMap`(JobDocTable.tsx:27,370 使用中)—— §6.7 列退場,但**目前都還在用**,
  要等 T8 新載體上線才能拆(退場紀律:新載體先上舊件後拆)。
- 後端:`copilotkit_live_app.py`(全檔)、`run_live.py`(改指 app_factory)、`app/authoring/` 整包
  (tracing.py 先搬 T6 再刪)、`test_copilotkit_live_app.py`(存在則刪)。

**現況事實 —— run_live / 8001 接線**
- `run_live.py` 跑 `app.copilotkit_live_app:app`(:8001)。`copilotkit_live_app.py` 用
  `configure(FastAPI(...))`(app_factory,:41)掛全 REST + CORS,**再**在 lifespan 加 `/copilotkit`
  langgraph 端點(:31)。web `api.ts` BASE=8001(api.ts:17)。
- → T12「run_live 改 app_factory」= 讓 run_live 起一個**只有 configure() 的 app**(去掉 langgraph endpoint
  + PG checkpointer + setup_tracing 要移到新 root)。REST 全在 8001 不變,web 零改動。

**風險**
- **8001 必須續服 REST**:web 全部走 8001/api/v1。拆 copilotkit_live_app 時若不小心讓 run_live 起的 app 少掛
  router,web 全掛。`app.main`(ADR 0017,tests/docker 用)已是 `configure`,可當範本。
- `@copilotkit/react-core/v2` 是子路徑;刪 dep 前確認 Providers 換成普通 QueryClientProvider(別連 rq persist 一起拔)。
- CurationDialog 的「檢查表職能」§6.7 說歸議程狀態機(T5)—— 拆 CurationDialog 前,curation 縫功能要在
  新側欄(T9)有替代,否則選完職類的預勾流程斷掉。

---

## T13 工程輕項

**現況事實**
- [llm_openrouter.py](S:\caliburn\apps\api\app\adapters\llm_openrouter.py):`model_for_role`(:31)已有
  deep/indicator/cheap/select/interview 五 role → settings。`chat_with_tools`(:113,tool_choice=auto)、
  `select_schema`(:141,strict)、`complete_text/json`(重試)。
- **無** OpenRouter 顯式 `models` fallback 陣列、無 `provider.allow_fallbacks`、無 parallel tool calls
  設定(現在 max_tool_iterations 序列)。streaming 未開(一次性)。
- 模型 role 表現況只有一層 dict(:32),無 consultant/scribe/backstop 分工顯式表(靠 role 字串 interview/select)。

**落點建議** 直接在 llm_openrouter + config 加顯式 fallback + parallel tools;備援模型先過 T11 考卷。

**風險** parallel tool calls 會動到 agent_loop.run_tool_loop(現在假設序列成對回填,agent_loop.py:44-55)。

---

## T14 文檔同步 + 收尾

**現況事實**
- `docs/design/` 現有子系統端到端篇(需新增/更新「訪談引擎端到端篇」)。ADR 0030 落檔時 README 已更新(plan 稱)。
- CLAUDE.md 指路段(§指路)若因 skills/observability 新增而變,同 commit 更新。

**落點建議** dual-audience 清單:動作→請求、真名、不變量、退役禁令(含「verify 必 blocking」「backstop 禁 LLM 化」
「✓/✗ 無聲」)。tag `ai-layer-v3`。

**風險** 文檔 fossilization 是頭號壞味道(CLAUDE.md):動到引擎那條線的碼 → 同 commit 更新 design 篇。

---

## executor / commands / context / agent_loop / diff / slots —— 未入 plan 模組的處置建議

| 模組 | runtime 是否活著 | 現況角色 | 建議處置 |
|---|---|---|---|
| **executor.py** | **`apply`/`ExecResult`/`_ensure_visible`/`_next_gap_question` = 死碼**(runtime 無人呼;僅 `test_interview_executor.py` + `context.build_prompt` 用)。**但 `get_at/set_at/resolve/quote_verified/normalize/writable_path` = 活**(scribe/curation/attitudes/backstop 都 import) | v1 TurnOutput 落地器,v2 被 scribe 取代 | **拆兩半**:把 path 解析 + `quote_verified/normalize` 搬進 T3 `verify.py`(或新 `docpath.py`);`apply`/保底輸出那套 v1 死碼隨 T12 退場刪掉 + 刪 test_interview_executor.py |
| **commands.py** | `TurnOutput`/`turn_output_schema`/Command 類 = 死碼(僅 test + `scripts/validate_select_schema.py` + executor.apply)。**`_obj/_s/_variant` = 活**(scribe_schema/curation/backstop/attitudes 都 import) | v1 指令詞彙 + strict-schema builder | 把 `_obj/_s/_variant` 搬進中性 `schema_utils.py`;v1 `TurnOutput`/`turn_output_schema`/Command 隨 T12 退場刪 + 刪 test_interview_commands.py |
| **context.py** | **死碼**(`build_prompt`/`ROLE_HEADER` 僅 test_interview_context.py 用;runtime 走 consultant.build_consultant_messages) | v1 deep 階段 prompt | 隨 T7(context 分層在 consultant)/T12 退場刪 + 刪 test |
| **agent_loop.py** | **活**(llm_openrouter.chat_with_tools 用,:118) | 手刻工具迴圈 | **保留**;T13 parallel tools 會動它 |
| **diff.py** | **活**(routes/documents.py + interview.py 用 STABLE_ID_KEYS/doc_paths_changed) | path 文法 + human_touched 偵測 | 保留 |
| **slots.py** | **活**(ledger/scribe/consultant/context 用 SLOT_DEFS/gate_missing) | 11 槽定義 + 缺口判定 | 保留;T5/T14 校準門檻 |

**核心建議**:T3 建 verify.py 時,**順手把 `quote_verified/normalize` + path 解析從 executor 搬過去**,
再把 `_obj/_s/_variant` 抽到 schema_utils —— 這樣 executor.py / commands.py / context.py 就只剩 v1 死碼,
可在 T12 乾淨退場(連同 4 個 test 檔),避免「executor 這個名字還活著但只剩螺絲」的混淆。plan 沒點名這三個
模組,執行 session 需明確把它們排進 T3(搬螺絲)+ T12(刪死碼)。

---

## intake 頁裁決建議(彙整)

**保留,不退場。** 理由:intake/page.tsx 是純表單存 job_summary,零 CopilotKit(檔頭自證),且是後續
〔選職類〕搜尋預填 + CurationDialog 預勾脈絡的餵料來源。§6.7「純 CopilotKit 入口→退役」的前提不成立。
唯一牽連:若 T12 之後 CurationDialog 併入議程狀態機(T5),intake 的 job_summary 消費點(document page.tsx:200)
仍有效,無需動 intake 本身。
