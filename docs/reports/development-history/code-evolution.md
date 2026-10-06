# 從程式與測試回讀架構演進

回到[演進索引](README.md)。這頁從前後程式與測試補查資料流、控制權及保存方式的變化。

盤點基準：2026-10-02，`target-rebuild@4d5759f4` 及可達 Git 歷史。日期採當時紀錄與 Git author date；部分提交經搬移／重放，committer date 不同，不能據此推算實際開發天數。

## 證據怎麼區分

- **程式可證明的變化**：前後版本實際多了、少了或改由誰處理什麼。不能只看 commit 標題、目錄搬家或刪除行數。
- **當時說明**：原設計、研究或提交訊息說的原因。它可以解釋背景，但不等於效果已經驗證。
- **回讀判斷**：本次由資料流推得的意義，明確與當時原話分開。找不到動機，就不補寫「當時是因為……」。
- **驗證界線**：測試程式、原實驗結果與本次實際執行分開。本頁沒有重跑舊系統或模型；團隊成員、AI 工具與其他協作者的實際分工及貢獻須依證據核對，不能只憑 Git 作者欄認定。

只有程式差異的部分保留為線索；當時原因與效果仍須原紀錄支持。

## 先找哪一組

| 關心的問題 | 本頁材料 | 與既有索引的關係 |
|---|---|---|
| 參考資料怎麼保存來源、何時能合併、換 embedding 有什麼風險 | §1、§2、§4 | 補足檢索演進的實際資料結構與反例 |
| 為什麼 API 已成功，畫面上的新字卻不一定已存 | §3 | 新增早期保存狀態的程式線索 |
| 顧問為什麼像填表、為何有教材卻不產出、短答如何成立 | §5–8 | 深化7月各次訪談重設計，保留接入後仍失敗的結果 |
| Memory 證據粒度、壓縮、背景恢復如何真正接線 | §9–11 | 補足9月中旬責任邊界，不以模組存在冒充整體可用 |

## 1. 多個知識端點改為共用知識包，合併顯示仍保留來源（7/3）

**程式可證明的變化。**早期編輯面分別取表頭、任務候選及逐任務能力資料，還有 `document:buildTasks` 寫入路徑。`d67f9272` 增加 `build_pack`：把知識、技能等依當時規則收在共用池；同名內容可以合併顯示，原來源則累積在 `srcs`，`source_tasks` 用 OCS＋原任務代碼組成的 URN 連回各池。`34fd61a1` 再實際移除舊端點及 `useTaskCatalog`，編輯面改讀知識包、經 PATCH 保存文件，不是只多包一層 API。

這之間還有一個修正：`52b1b7c7` 把 catalog key 從文件內可重編的位置碼改成來源 URN。它和[拖曳項目的穩定身分](evidence-by-capability.md#8-修掉重複-key-後仍須解決位置不是物件身分62122)相關，但不是同一個 key：這裡辨認外部標準任務，前者辨認畫面裡可編輯的項目。

**當時說明與回讀判斷。**[ADR0021](../../adr/0021-knowledge-pack-single-sync-point.md)已指出分散抓取、來源被投影丟失及快取錯位。本次由程式補出的重點是：同名合併不代表來源也合併消失；讀取參考資料與寫入使用者文件逐步分開。這是資料身分、投影與讀寫責任的調整，不能簡化成「加快取所以變快」，也不能當作現行 Memory 的 title 定位規格。

**固定證據：**

- 前後端點：`34fd61a1^:apps/api/app/api/routes/documents.py` → `34fd61a1:apps/api/app/api/routes/documents.py`。
- catalog 身分修正：`52b1b7c7:apps/api/app/api/routes/documents.py` 的 `task_catalogs`，對照該提交 diff。
- 組裝：`d67f9272:apps/api/app/core/domain/knowledge_pack.py` 的 `build_pack`。
- 反例：`d67f9272:apps/api/tests/test_knowledge_pack.py` 的 `test_pools_merge_by_key_and_accumulate_srcs`、`test_attitudes_dedup_by_name_not_code`、`test_source_tasks_carry_refs_and_level`。

**驗證界線。**測試留有兩職類同名知識保留不同來源、兩個 `A01` 態度名稱不同不可錯併等案例。這是組裝契約的可查證材料；本次未重跑，不宣稱有新的延遲、流量或訪談品質改善數字。

## 2. 相似度不直接變成等價關係，改為非破壞的分組能力（7/4）

**程式可證明的變化。**原 `find_similar_tasks` 從 Qdrant 取任務再做配對；`de1b67dc` 增加 `match_items`，接受明確的候選項目，只有 embedding 是外部計算，分組不讀寫 Qdrant。`ff4df3a3` 的核心把分數分成高分、灰區及忽略區，另做星型分組：成員必須直接與中心達到門檻，不因 A 接近 B、B 接近 C，就把 C 沿鏈帶入 A 的群。回傳 `groups`、`possible_matches`，而不是刪除候選。

**當時說明與回讀判斷。**[檢索沿革](retrieval.md#2026-07真的相似不等於可以合併)已有真重複與相似但不同的分數重疊；[ADR0022](../../adr/0022-similarity-matching-items-match.md)交代非破壞呈現及灰區。本次補出一個可展示的演算法反例：A–B、B–C 都是0.96，A–C只有0.5，測試要求 C 不得鏈入。這不是說前版已使用連通分量並發生事故，而是新方法留下了防止錯誤遞移的檢查。

**固定證據：**

- 前後能力：`de1b67dc^:apps/ocs-indexer/src/jd_ocs_indexer/api/service.py` → `de1b67dc:apps/ocs-indexer/src/jd_ocs_indexer/api/service.py`，`find_similar_tasks`／`match_items`。
- 核心：`ff4df3a3:apps/ocs-indexer/src/jd_ocs_indexer/matching/core.py` 的 `band`、`star_clusters`、`medoid_of`。
- 反例：`ff4df3a3:apps/ocs-indexer/tests/test_matching_core.py` 的 `test_star_no_chaining`、`test_star_deterministic_ordering`；`de1b67dc:apps/ocs-indexer/tests/test_items_match.py` 的 `test_same_source_pairs_skipped`。
- 後續拆責任／退役：`12ca3c7d` 將 matching 移出 Qdrant API service；`4ebbe951` 退役舊 `tasks:findSimilar`。兩者是同一條演進的接續，不另算兩次品質改善。

**驗證界線。**上述反例使用可控分數或假 embedder，證明要檢查的分組行為，不證明真實語意等價。星型也不是保證任意兩個成員皆等價；當時各類門檻的校準限制仍見原研究。不能把三區分帶的借鑑寫成已建立完整機率式實體解析模型。

## 3. 從保存回應覆蓋畫面，到區分最新編輯與已存基準（6/26–7/2）

**程式可證明的變化。**`516fc2c4` 把 `usePatchDocument.onSuccess` 從直接覆蓋 query cache，改成只更新回應 metadata、保留 cache 的最新 `content`。接著 `f87bea52` 又區分「畫面內容」與「最後已存 baseline」：成功後 baseline 使用本次真正送出的 `content`，不能使用等待期間已再改過的 cache；409 時保留本地文字，而非把它回滾掉。

後端 `e18d2c0e` 同時加入 expected version／revision 檢查與409結果。**這時檢查仍是 opt-in**：只帶一個或兩者皆未帶，就沿用舊行為。因此不能直接把「加了樂觀鎖」寫成當時所有寫入已受到保護。

**當時說明與回讀判斷。**[ADR0015](../../adr/0015-document-save-optimistic-concurrency.md)提出回合制文件編輯不先做 CRDT／OT；但原 ADR 曾寫保留 mutation rollback，7/2實際程式已移除該處 rollback。報告應交代這個演進，不能只抄最早決策。可由程式推得的重點是：API成功、本地仍有新字、正式保存的是哪一份，是不同狀態；這也是日後討論候選、正式稿與恢復邊界的相近問題，**不是已證明直接導致後來架構的歷史因果**。

**固定證據：**

- 第一輪：`516fc2c4^:frontend/src/hooks/useDocument.ts` → `516fc2c4:frontend/src/hooks/useDocument.ts` 的 `usePatchDocument`。
- 第二輪：`f87bea52^:apps/web/src/hooks/useDocument.ts` → `f87bea52:apps/web/src/hooks/useDocument.ts` 的 `Baseline`、`useAutosaveDocument`、`flushPatch`。
- 後端：`e18d2c0e:apps/api/app/adapters/persistence.py` 的 `DocRepo.upsert_draft`；`e18d2c0e:apps/api/app/api/routes/documents.py` 的 `patch_document`。
- 反例：`e18d2c0e:apps/api/tests/test_documents_api.py` 的 `test_patch_no_expect_params_is_legacy_unguarded`、`test_patch_stale_revision_409_with_current_token`、`test_patch_first_save_expect_zero_zero_but_already_exists_409`。

**驗證界線。**有前後程式及後端測試可查；本次未找到與這兩筆前端修正配套的完整瀏覽器競態錄製或測試結果，不能宣稱 UI 所有異步／併發情況皆解決。此處也不推薦把當時整套 hook 原樣搬回現在。

## 4. 索引除了存資料版本，也開始記錄 embedding 身分（6/28）

**程式可證明的變化。**`31918254` 增加 `EmbeddingSignature`，記錄 provider、model、dim、revision；建索引後寫入保留的 manifest point。`f770f68a` 再把 `assert_compatible` 接到 `search_tasks`／`search_occupations` 的查詢向量生成之前，provider／model／dim不符就回報錯誤。測試刻意使用**同為1024維但模型不同**的情況，不只測維度不合。

**當時說明與回讀判斷。**[ADR0009](../../adr/0009-embedding-version-manifest.md)指出原 payload 的版本是 OCS 文件版本，無法回答由哪個模型產生向量。本次可補出的材料是：更換 embedding 不只是把一個設定字串換掉，索引與查詢端還有相容關係。這是預防與可診斷性設計；尚未找到證據證明它之前已造成哪一場真實檢索事故，不能把風險敘述改寫成事故。

**固定證據：**

- 身分與保存：`31918254:apps/ocs-indexer/src/jd_ocs_indexer/embeddings/base.py`、`31918254:apps/ocs-indexer/src/jd_ocs_indexer/pipeline.py`。
- 查詢前後：`f770f68a^:apps/ocs-indexer/src/jd_ocs_indexer/api/service.py` → `f770f68a:apps/ocs-indexer/src/jd_ocs_indexer/api/service.py`。
- 邊界：`f770f68a:apps/ocs-indexer/src/jd_ocs_indexer/embeddings/base.py` 的 `assert_compatible`。
- 反例：`f770f68a:apps/ocs-indexer/tests/test_compat.py` 的 `test_assert_compatible_raises_on_model_diff`、`test_search_tasks_raises_on_mismatch`；`31918254:apps/ocs-indexer/tests/test_manifest.py` 的 `test_manifest_round_trip`。

**驗證界線。**程式對舊索引缺 manifest、僅 revision 不同都只是警告放行；也未實作零停機模型遷移。不能把這段材料說成所有歷史向量都已完整驗證、換模型不用重建，或搜尋品質已改善。

## 5. 事件議程已存在，仍須移除另一套缺口排序（7/14）

**程式可證明的變化。**`480959e7` 的 `build_consultant_messages` 已有事件議程 `agenda_view`，卻同時注入 `ledger_summary` 產生的「下一個缺口」。`1223aa13` 移除 `next_gap`、`ledger_summary`、`gap_label` 的引導路徑，讓議程承接選題，教材則按階段選取。`run_turn` 也不再預存 `last_gap`，改以裁剪是否真正落地更新該部分進度。

**當時說明與回讀判斷。**[ADR0033](../../adr/0033-episode-agenda-consultant-tools.md)及[7/14診斷](../../research/work-analysis/2026-07-14-interview-agenda-architecture-research.md)指出線性槽位使行為指標難以到達，以及「任何寫入」不代表當前問題已有進展。程式顯示這次不只是新增事件工具，而是清掉新舊兩套控制同時引導模型的接縫；事件工具在此前已接入。

**固定證據：**

- Prompt 組裝：`480959e7:apps/api/app/interview/consultant.py` → `1223aa13:apps/api/app/interview/consultant.py`。
- 回合控制：`480959e7:apps/api/app/interview/service.py` → `1223aa13:apps/api/app/interview/service.py` 的 `run_turn`。
- 當時議程接線測試：`72d6b9f7:apps/api/tests/test_interview_service.py` 的 `test_agenda_artifact_injected_into_consultant_context`、`test_agenda_tools_open_close_update_episode_state`。

**驗證界線。**提交訊息有當時測試通過自述，本次核對的是程式與測試內容，不是重跑。移除雙重引導不能直接推成提問品質提高，也不表示此後再沒有規則主導對話。

## 6. 起草模組已寫好，不等於訪談流程真的會使用它（7/14–15）

**程式可證明的變化。**`a6a8574e` 的 `scribe_pass` 只把最新員工發言送進書記 prompt；該版本雖已有 `harvest.py`，服務還沒呼叫它。`9b80074d` 才在 `run_turn` 接入事件關閉／自動關閉 → `pending_harvest` → `harvest_pass`。後者選出事件期間多輪員工原文、注入實際起草需要的教材，逐筆定位 quote 所屬回合，再沿既有 `records_to_ops`／`land_ops` 成為待審草稿。

**當時說明與回讀判斷。**原模組檔頭說明跨輪定位與行為指標教材的用途；同題背景見[事件議程研究](../../research/work-analysis/2026-07-14-interview-agenda-architecture-research.md)。可用來展示的不是「多寫一個 Agent」，而是核對原料、教材、觸發點、寫入者是否真的連成一條路。

**固定證據：**

- 原書記：`a6a8574e:apps/api/app/interview/scribe.py` 的 `scribe_pass`。
- 接入前後：`a6a8574e:apps/api/app/interview/service.py` → `9b80074d:apps/api/app/interview/service.py`。
- 起草及定位：`9b80074d:apps/api/app/interview/harvest.py` 的 `_episode_turns`、`_locate`、`harvest_pass`。
- 測試：`9b80074d:apps/api/tests/test_interview_service.py` 的 `test_close_episode_triggers_harvest_lands_indicator`；`9b80074d:apps/api/tests/test_interview_harvest.py` 的 `test_harvest_prompt_injects_indicator_material`、`test_locate_finds_turn`。
- 實驗原文：`b8494e10:docs/specs/2026-07-05-interview-sim-calibration.md`「紀錄 #3 — 2026-07-15」；可讀[原文件](../../history.md#source-bbe1eedda0bb5779480a)。檔名日期不是這次實驗日期。

**驗證界線。**該次合成人設實驗記錄11條P、harvest落地1/1，但總閘門仍 FAIL：`verify_pass_rate=0.74`，原報告診斷主要為重複起草遭拒收，另有從非回答起草的雜訊。11條P不能全算成 harvest 產出；0.74也不能改稱事實正確率。這是接線後進一步暴露分工與量測問題的材料，不是全系統通過。

## 7. 短答失效，不只是模型沒看到前問（7/20–22）

**程式可證明的變化。**`9e9dba16` 已在 context 放入 `preceding_consultant_turn`；但當時 `verify_turn_interpret_output` 仍以本輪員工文字檢查 quote。因此這段歷史不能寫成「以前完全沒提供前問」。`7b2cec5a` 增加合資格的 QuestionFrame 與回答綁定：確認回答、前問及 frame 的關係，再由 `_materialize_binding` 依目標命題或 slot template 建立 `ContextualAnswerSupport`。

**當時說明與回讀判斷。**[ADR0037](../../adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md)保存「是」「每週」「主管」等短答問題。這次改的是**如何構成可追溯的證據**，不只是多塞幾輪 context；由前問加回答得到的命題，不能冒充員工逐字說過整句。

**固定證據：**

- 前後組裝：`9e9dba16:apps/api/app/interview_vnext/application/context_builder.py` → `7b2cec5a:apps/api/app/interview_vnext/application/context_builder.py` 的 `_eligible_question_frame`。
- 前後驗證：`9e9dba16:apps/api/app/interview_vnext/application/turn_interpret.py` → `7b2cec5a:apps/api/app/interview_vnext/application/turn_interpret.py`，`verify_turn_interpret_output`／`_materialize_binding`。
- 反例：`7b2cec5a:apps/api/tests/test_interview_vnext_turn_interpret.py` 的 `test_frequency_slot_accepts_exact_count_and_rejects_hidden_second_count`、`test_frequency_slot_fails_closed_on_unsupported_interval_range_or_irregular_count`。
- 後續限定驗證見[R5-D紀錄](../../history.md#source-7b42c231502a8e960a77)，不是後來新架構的驗收。

**驗證界線。**測試接受「每月2次」、拒收「每月2次或3次」，但也明確拒收當時不支援的「每兩週一次」。這揭示結構化規則的表達限制，不該只報正例或稱自然語言短答已普遍解決；當時資料庫測試通過也不等於真模型語意通過。

## 8. 分開解讀與選問，後來收斂成同次輸出分析與下一問（7月下旬）

**程式可證明的變化。**vNext 的 `continue_after_interpretation` 接收解讀 receipt，先做 `plan_loop_control`，再走獨立 `execute_question_select`。後來 Task Analysis 路徑的 `run_task_analysis_operation` 一次呼叫 `adapter.complete`，輸出 `work_signals`、`next_question`、`limitations`，再交程式解析與驗證；`durable_turn` 確實把下一問保存成顧問回合與 `active_question`。

**當時說明與回讀判斷。**[ADR0042](../../adr/0042-r1-screening-stop-and-a6-first-version-default.md)與[R1a結果](../../experiments/2026-07-27-r1-task-discovery/r1a-results.md)保留比較及時程取捨。這組是**兩條實作路徑的責任比較**，不是同一個函式直接改名；正常新回合的分析與提問合併，合法性檢查和提交仍由程式承擔。

**固定證據：**

- 舊路徑：`b69d1b4e:apps/api/app/interview_vnext/application/consultant_loop.py`。
- 新模型呼叫與輸出：`1b15fbbc:apps/api/app/job_analysis/application/operation.py`、`1b15fbbc:apps/api/app/job_analysis/llm/result.py`。
- 正式對話接點：`d7105d25:apps/api/app/job_analysis/application/durable_turn.py`。
- 測試：`1b15fbbc:apps/api/tests/test_job_analysis_operation.py` 的 `test_a_verified_round_makes_exactly_one_call_with_the_pinned_route`、`test_the_provider_only_ever_sees_the_rendered_packet`。

**驗證界線。**上述呼叫數測試使用假 transport；R1a另有共同拆分／合併缺口。不能說 one-stage 普遍優於多階段，也不能把比較實驗直接當成後續產品契約的品質驗收。這個例子呈現做減法，不是宣稱階段越少一定越好。

## 9. 整批工作範圍，不再自動充當每個案例的來源（9/17）

**程式可證明的變化。**舊 `create_case` 自動附上本批 `stage.source_reference`；`split_case` 又把同一組來源複製給所有新案例。`88713a9c` 改為模型用已提供的 `evidence_keys` 選擇支持關係，Runtime 解析正式引用並按來源順序保存；拆分時未分配給新案例的舊證據須明示處置。`cf60e4d4` 進一步把 B2 的 `read_case_source(case_id, source_reference, offset)` 收斂為 `read_case_source(evidence_key)`，來源與分頁位置交給 Runtime。

**當時說明與回讀判斷。**[引用施工計畫 §1–2](../../history.md#source-68f621f02972c31d1d41)區分處理範圍 `window`、證據 `source`、消歧 `context`。程式可證明引用選擇責任有改變：模型判斷「哪些內容支持這個案例」，App 處理地址與順序；不能因某段原話在本批出現，就自動視為支持每個案例。

**固定證據：**

- 案例前後：`d269e5d6:packages/consultant-memory/src/caliburn_memory/case_maintenance.py` → `88713a9c:packages/consultant-memory/src/caliburn_memory/case_maintenance.py`。
- B2 前後：`88713a9c:packages/consultant-memory/src/caliburn_memory/understanding_workflow.py` → `cf60e4d4:packages/consultant-memory/src/caliburn_memory/understanding_workflow.py`。
- 測試：`88713a9c:packages/consultant-memory/tests/test_case_maintenance.py` 的 `test_create_case_resolves_model_keys_and_saves_owner_order_not_key_order`、`test_split_assigns_evidence_per_replacement_and_requires_explicit_old_discards`；`cf60e4d4:packages/consultant-memory/tests/test_understanding_workflow.py` 的 `test_b2_uses_case_bound_evidence_keys_and_runtime_owned_source_cursor`。

**驗證界線。**這幾筆提交核對的是 staged 接點，不是共同發布或引用語意品質已通過；計畫頁後來另有發布整合的接續狀態。該年代對已安全保存 failed／cancelled 原話的來源資格，也不同於後來目標架構；不能把整份舊計畫搬成現在規則。

## 10. 摘要元件完成後，還有完整 request 與根 checkpoint 的接線（9/16）

**程式可證明的變化。**`5aef2596` 已有 `ContinuationCompactionMiddleware` 基礎，但 `build_consultant` 尚未預設注入；`6d8f0703` 才接入 A。同次還把 compaction 排在 Skills／App notices 投影之後，讓容量計算面對最後要送出的內容，並在根 `DocumentState` 加入 `continuation_compaction`，承接子圖返回。

基礎實作的 `build_request_view` 只改推論用視圖，不改 canonical messages；摘要另帶涵蓋邊界與 prefix digest，主模型未成功時不發布新的摘要狀態。這是**當時自建的接續摘要方案**，不可混同後來採用的 OpenAI 原生 standalone compaction。

**當時說明與回讀判斷。**[9/16設計及兩次小步結果](../../history.md#source-49fa82b26188aad2b075)保存當時供應商／框架限制及接線順序。本次補出的重點是：有摘要函式不代表已縮到真正的 request，也不代表重啟能拿回摘要；原始對話、送模投影與接續狀態是不同責任。

**固定證據：**

- A 注入前後：`5aef2596:experiments/jd-relational-app/src/jd_relational/consultant_app.py` → `6d8f0703:experiments/jd-relational-app/src/jd_relational/consultant_app.py`。
- 摘要基礎：`5aef2596:experiments/jd-relational-app/src/jd_relational/continuation_compaction.py`。
- 組裝與保存：`6d8f0703:experiments/jd-relational-app/src/jd_relational/consultant_context.py`、`6d8f0703:experiments/jd-relational-app/src/jd_relational/runtime_checkpoints.py`。
- 測試：`5aef2596:experiments/jd-relational-app/tests/test_continuation_compaction.py` 的 `test_main_failure_does_not_publish_new_summary`、`test_saved_summary_survives_graph_rebuild_and_next_chat_turn`；`6d8f0703:experiments/jd-relational-app/tests/test_consultant_context.py` 的 `test_context_compaction_counts_the_fully_projected_request`、`test_a_compaction_and_jd_notice_commands_are_saved_together`。

**驗證界線。**當時有離線 graph／Saver及合成HTTP整合紀錄，不等於真 provider、摘要忠實度或長訪談容量驗收。後來9/22–23仍出現壓縮邊界、摘要輸出額度及反覆摘要問題，見該設計後續條目與[長訪談沿革](memory-and-context.md)，不能止於這次接線成功。

## 11. 背景有恢復程式，仍可能在錯誤的啟動時機被擋下（9/17）

**程式可證明的變化。**舊 `_recover_previous` 在前景恢復期間直接 wake 背景；`0c742248` 移除這個呼叫，由 managed App 在 `finish_startup` 完成後才執行 `BackgroundCoordinator.resume_pending`。另一個接縫是 graph 建立時尚沒有 App 文件資源：`6e322fe5` 把建構 middleware 時綁定的 readers，改成每次 invoke 由 `ConsultantContext.background_availability` 注入，middleware 只讀取並呈現狀態，不啟動工作。

**當時說明與回讀判斷。**[背景接線設計 §2.2](../../history.md#source-7c86c662c16442ee0356)明確記錄過早 wake 遇到 `startup_pending`，上層又隔離錯誤；以及 graph 與 App 資源的建立順序問題。這能呈現生命週期診斷：不能只查「函式有沒有寫」，還要查呼叫時誰已 ready、資源屬於哪份文件。

**固定證據：**

- 恢復前後：`f920f010:experiments/jd-relational-app/src/jd_relational/ai_runtime.py` → `0c742248:experiments/jd-relational-app/src/jd_relational/ai_runtime.py`。
- 新接點：`0c742248:experiments/jd-relational-app/src/jd_relational/managed_app.py`。
- 每次 invoke 的注入：`fd1f1e97:experiments/jd-relational-app/src/jd_relational/background_availability.py` → `6e322fe5:experiments/jd-relational-app/src/jd_relational/background_availability.py`。
- 測試：`0c742248:experiments/jd-relational-app/tests/test_managed_app.py` 的 `test_ai_app_resumes_background_only_after_foreground_startup`；`6e322fe5:experiments/jd-relational-app/tests/test_background_availability.py` 的 `test_one_shared_middleware_uses_each_invocations_own_provider_once`。

**驗證界線。**原文有離線切片紀錄，也明示不是跨 process admission、真模型或完整瀏覽器旅程驗收。單 process 的協調與持久恢復權威分開，不能把 process 內物件可重建說成所有分散式失敗都已處理。

## 現行接續的程式核對

以上十一組保留 6–9 月的固定版本。2026-10-05 至 10-06 的新接線另有原件：

- [公版角色工具與消費端固定快照](../../experiments/engineering/README.md)：opt-in 接線、明確排除的工作狀態及 B1／B2 固定 bound 讀取，屬工程契約；不推定候選參考已能改善 JD。
- [取消與遲到 checkpoint 寫入](../../experiments/product-validation/2026-10-05-job-file-deletion.md#取消與保存競爭的接續驗證2026-10-06)：核對鎖定版 LangGraph 的 exit／executor 與官方 Saver，再以真 PostgreSQL 反例守住同一交易的保存／刪除邊界。最終程式為 `6750be5d8`，部署狀態另見原件。

新接續按[工程沿革](engineering-and-verification.md#9-取消已提交仍須等真正保存結束)閱讀；以上固定歷史版本保留當時的程式路徑。

## 回讀固定版本的方法

`提交:當時路徑` 是 Git 物件定位，`^` 表示該提交的第一個父提交；不用切分支、啟動舊系統或還原舊資料。例如：

```powershell
git show '516fc2c4^:frontend/src/hooks/useDocument.ts'
git show '516fc2c4:frontend/src/hooks/useDocument.ts'
git show ff4df3a3 -- apps/ocs-indexer/tests/test_matching_core.py
```

取材時先用前後程式確認變了什麼，再回讀原研究／結果。沒有留存的試用經過、當時判斷或測試輸出，明示待補，不用現在的推論補成當時發生過的事。

## 本輪核對範圍與仍缺的材料

2026-10-02：補入11組程式演進材料，主要深化6–9月的資料、訪談與 Memory 接線；3–5月原始起點仍沿[早期原件](../../history.md#source-662ea57dd88fb5eb0879)及[既有時間線](product-and-architecture.md)查，不把本頁最早日期當成專案起點。

該次核對 66 個不同 Git blob 定位均可讀，30 個具名測試在對應歷史檔案中存在，並回讀前後程式與原紀錄。新增本文、調整三個入口，四份文件的相對連結／章節定位無失效。這是材料與引用檢查，沒有執行該 30 個產品測試。

沒有留下的當時動機、完整 UI 競態、部分原模型 capture 與協作分工仍需補證。正式引用再沿固定版本確認原件及可公開範圍。
