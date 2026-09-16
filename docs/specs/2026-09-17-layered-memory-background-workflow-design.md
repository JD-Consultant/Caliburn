# 分層 Memory 完整背景 Workflow 設計

**Topic：**`JD-R002 / MEM-L001`

**Stage：**G7 分段施工

**Status：**Owner 已核准方向；施工前精確設計
**Date：**2026-09-17

## 1. 目標與既有決策

本切片只把已完成的 B1 案例維護 Agent、B2 工作理解維護 Agent、分層 bundle authority 與既有 publication CAS／receipt 接成一個可恢復的完整背景工作：

```text
固定 document／canonical source batch
    ↓
以一個明確 base 執行 B1 case maintenance
    ↓
以同一 base 與 completed B1 candidate 執行 B2 understanding maintenance
    ├─ publishable changed／no_op
    └─ case_rework_required → 最多一次新的 B1 attempt → 新的 B2 attempt
    ↓
Runtime 組裝完整 candidate bundle
    ↓
一次 CAS publication；成功才推進 processed_source
```

有效產品語意仍以 [`MEM-L001`](2026-09-16-layered-case-and-work-understanding-memory-alignment.md) 為準：B1 維護完整、可持續修正的目前工作案例；B2 從目前案例維護穩定工作理解；兩層不是摘要關係，也不合併成同一 Agent。canonical 原始訪談、案例、工作理解與 JD 的權責不變。

## 2. 設計依據與本案映射

### 2.1 官方共同原則

- Anthropic 的 prompt chaining 建議固定、可分解的子任務採順序 workflow，並可在中間加入程式 gate；evaluator-optimizer 適合有明確評估條件的回饋迴圈，Agent 迴圈需要停止條件。B1→B2 是固定 chain，`case_rework_required` 是一次有界 feedback gate，不需要第三個 LLM orchestrator。
- LangGraph 的 persistence／durable execution 在 graph step 間保存 checkpoint；可能重執行的外部副作用應可冪等，或使用持久化 task result／idempotency identity。B1、B2、bundle prepare 與 publication 應保持可觀察邊界。
- AWS optimistic locking 以讀取版本的條件寫入攔截 stale writer，衝突後重新讀取並有限重試。現有 `PublicationStore` 已提供精確 base、CAS、receipt 與不明結果對帳，不另加長交易或程序鎖。
- OpenAI 官方 Agent 指引要求工具說明交代 side effect、retry safety 與常見錯誤；Runtime 應擁有版本、operation、重試及發布，不能交給模型填寫。

這些來源支持 workflow／恢復／並行控制的工程原則，不替 Caliburn 決定案例、工作理解或 JD 的產品語意。

### 2.2 沿用、不重做

- 沿用 `CaseMaintenanceWorkflow`／`CaseMaintenanceSession` 的 Prompt、語意工具、來源窗口、checkpoint、完成防護與模型／工具額度。
- 沿用 `UnderstandingMaintenanceWorkflow`／`UnderstandingMaintenanceSession` 的 Prompt、impact gate、按案例限制的原話讀取、`case_rework_required` 與額度。
- 沿用 `MemoryArtifacts.save_bundle()` 的完整 bundle 驗證與不可變 artifacts。
- 沿用 `PublicationStore.prepare()`／`publish()` 的 exact-base CAS、operation receipt、`PublicationUncertain` 與 `StalePublication`。
- 舊 `ConsolidationWorkflow` 只作 stale、receipt、游標與恢復證據；不沿用兩檔 Memory 產品形狀或舊 B2 Prompt。

### 2.3 Owner 追加確認：查找範圍與引用單位

本設計中的「本次待整理訪談來源範圍」只是一次背景工作的固定新增輸入及 `processed_source` 邊界，不是 B1 的閱讀權限邊界：

- B1 以本次新增範圍為起點，能從案例 guide／目前案例與來源導覽按需查閱同文件已安全完成的 canonical 訪談；不能把全部歷史預載進 request。
- B2 以案例 guide、B1 change set 與既有 bindings 為起點，有權按需讀取同一 candidate 中任何目前有效案例；必要時才沿已讀案例引用回查 canonical 訪談。必讀／直接影響集合是最低驗收，不是 B2 的案例閱讀權限上限。
- 一個案例可引用多個散落於不同訪談範圍的來源；同一來源也可支持多個案例。工作理解與案例同樣是多對多，且兩層在 revise／split／merge／retire 時都要重新分配仍真正支持目前內容的引用。

持久案例引用沿用現有 source owner 簽發的 `purpose="source"` reference，不新增第四種 citation token，也不讓模型填 message／character offset或保存模型自行切出的文字區段。現有 `source` 已固定在該輪 checkpoint，內容是該輪保存的使用者回答，以及如存在，它前面最接近且未跨過另一個使用者輸入的公開 AI 問題／上下文。來源 owner 解析 reference 時回傳 `message_id`、`role` 與原文；使用者與公開 AI 訊息都屬 canonical conversation，但 AI 文字只提供問題與上下文，不自動成為已確認的員工事實。

三種既有 purpose 的責任固定如下：

| purpose | 責任 | 可否存成案例證據 |
|---|---|---|
| `window` | 本次背景工作的完整新增訪談範圍與 `processed_source` 進度 | 否 |
| `source` | 一筆可持久驗證的訪談交換：公開顧問問題／上下文＋該輪員工回答 | 是 |
| `context` | window 讀取時的暫時消歧前綴 | 否；其中真正相關的已完成交換應改選各自的 `source` |

一筆 `source` 已能處理常見的「顧問問完整問題、員工簡答」；但單一交換仍不一定足以讓人獨立理解完整案例。例如員工可能只回答「對，就是那個」，而真正主體散落在更早的問答、補充或更正。因此一個案例保存的是按 canonical 順序排列的**回合證據集合**，可由一個或多個 `source` references 組成。若答案依賴前題、代名詞、先前補充或更正，B1 必須把理解該案例所需的相關完整交換一併選入；效果目標是不了解案例正文的人只看引用也能理解其工作情境、細節、補充與更正。

順序是證據語意的一部分，不是 UI 裝飾：

- source owner 對同一 canonical conversation 的安全完成使用者輪次提供 ordered source records，順序來自 conversation message order。settled failed／cancelled 回合的員工原話仍可列入；第一個 unsettled gap 後不列出。ID／reference 只負責身分與固定讀取，不能拿來排序。
- Runtime 把本 attempt 已提供／已讀的 records 配置短 `evidence_key`，把 key→reference 對照及 owner order proof 保存進 checkpoint。模型只可選擇已展示的 key；key 不是全域輪次、時間或持久 citation，也不由模型創造。案例 artifact 仍保存 signed references，由 Runtime 依 owner order 驗證、去重並保存成先後順序。
- B1／B2 展開來源時以明示 `oldest_to_newest` 的 ordered blocks 回傳 `evidence_key`、role 與完整文字。若分頁，cursor／offset 由 Runtime 保存，下一頁接續同一順序；模型不填 offset，page 內或 page 間都不能重排。
- 第一版不把 wall-clock timestamp 送進模型，也不以時間戳判斷先後；如 UI 日後顯示時間，只是輔助資訊，不是 citation authority。
- 不同文件、不能證明位於同一 canonical lineage、未知／重複 key 或模型自行製造的 reference 一律拒絕，不猜測修正。

既有 `context_reference` 可幫助當次模型理解，但 context token 本身不冒充 evidence；若其中問答確實支持案例，來源 owner 要沿用既有 `source` 格式為對應的已安全完成使用者輪次提供可持久驗證的 references，B1 再選入案例證據集合。Runtime 可驗證完整交換、固定位置、文件範圍、已提供／已讀、去重與 canonical 排序；「是否足以獨立理解案例」是語意品質，交由 B1 規則、B2 沿引用反查及自然訪談驗收，不用關鍵詞或字數假裝純程式已證明。

因此要先修正現有 B1「凡本次改動就自動附整批 `stage.source_reference`」的過粗行為：

- `processed_source`／job source range 繼續表示本次完整處理進度；
- source owner 增加受控的歷史安全交換列舉／固定讀取能力，沿用現有 `AiRunHistory.find()`、固定 checkpoint 與 `source` 簽章，不另存第二份 conversation；
- `CaseArtifact.source_references` 改保存 B1 已實際看過、由 Runtime 提供並驗證的 `source` references，並依 owner 的 canonical order 排列；
- 模型只可用 Runtime 顯示的 attempt-scoped `evidence_key` 選擇當次已提供／已讀證據；Runtime 將 key 解析成真正 reference，模型不可直接製造 reference、key 或序號；
- create／revise／split／merge 必須表達本次正確的來源分配，Runtime 保留既有未變引用並驗證新增、移除與 replacement 的引用都可讀且屬同文件；不得為方便而把整批引用無差別複製到每個案例。

工具參數依[模型／Runtime 參數權責審核](2026-09-17-model-runtime-parameter-ownership-review.md)收斂：B2 exact-source read 不再讓模型填 `source_reference＋offset`，rework 使用已綁 case/source 的 `evidence_key＋reason`，B1／B2 finish 不再讓模型重填可由 stage 算出的 `changed/no_op`。

這是完整背景 workflow 的前置正確性修正，不新增第二個 conversation owner、文字區段 citation、RAG 或 citation Agent。

## 3. 公開責任與命名

新增 `caliburn_memory.background_workflow`，主要公開類別命名為：

- `BackgroundMemoryWorkflow`：B1→B2→bundle→publication 的 deterministic Runtime workflow。
- `BackgroundMemoryWorkflowState`：只保存 JSON-safe 的 job control／checkpoint 狀態。
- `BackgroundMemoryResult` 如確有跨模組 typed consumer 才新增；第一版若現有 dict state 已足夠，不為命名完整性多造 wrapper。

沿用 `Workflow`，因 package 既有同層公開型別都是 `CaseMaintenanceWorkflow`、`UnderstandingMaintenanceWorkflow`、`RepairWorkflow`。使用 `BackgroundMemory` 而非 `Consolidation`，避免把 B1 案例維護誤稱為單純摘要／整併。

公開操作維持小而明確：

```python
workflow.start(source_reference)
workflow.resume()
```

`start()` 開始一份固定 canonical batch，或查回同一份已完成結果；pending job 必須 `resume()`，不能被新輸入替換。來源範圍的切割與通知准入仍由後續 App dispatcher／source owner 負責，本 workflow 不自行尋找 latest conversation。

## 4. 正常資料流

### 4.1 固定 base

背景工作載入 `PublicationStore.current()`，固定：

- `base_publication_revision`
- exact `base MemoryVersion`，初版則為 `None`
- `source_reference`

三者存入 durable job state。模型不能提供或修改。B1 與 B2 都必須使用同一 base；中斷恢復不刷新。

每個 B1 semantic attempt 另有 Runtime-owned durable `case_attempt_id`。transport resume 沿用同一 ID；B2 退回後的 B1 rework 與 CAS stale 後的語意重做都配置新 ID。B2 attempt identity 必須包含完整 B1 stage 與這個 attempt ID，避免新 B1 重讀後即使產生相同內容，B2 卻錯誤查回上一個 `case_rework_required`。

### 4.2 B1 與 B2

1. 若 B1 對此 attempt 尚未完成，呼叫其 `start()`；若其 checkpoint pending，呼叫 `resume()`。B1 request 先取得案例 guide／本次來源，其他目前案例與 canonical 訪談按需讀取。
2. B1 完成後，將完整 `CaseMaintenanceStage` 固定到 job state。
3. B2 以該 completed B1 stage `start()`；pending 時 `resume()`。B2 可以從案例 guide 按需讀取完整 candidate 的任何目前案例，不把 Runtime 推導的 required／directly affected IDs 誤作唯一可讀集合。
4. B2 只有 `changed`／`no_op` 可進入 candidate bundle；`case_rework_required` 走 §5。

外層 job 不重算 B1／B2 的語意不變量，不直接修改兩層 stage。

### 4.3 Bundle 與 publication

Runtime 從兩個 completed stage 取得：

- B1 `current_cases()` 與 `case_guide`
- B2 `current_understandings()` 與 `understanding_guide`
- 本次 B1／B2 supersessions

然後以固定 base 呼叫 `save_bundle()`。即使本批是語意 no-op，仍需建立以本次 base 驗證過的完整 candidate bundle，因為 publication 也要可靠地表示這個 canonical source 已處理；不得直接拿舊 bundle 換游標。

`prepare()` 產生的完整 `PublishRequest` 必須先 checkpoint，再執行 `publish()`。因此 commit 成功但回覆遺失時，恢復會重送同一 operation／request digest，由 receipt 查回，不配置新 operation。

publication 的 `kind` 仍為 `consolidation`，`processed_source=source_reference`。這是現有持久契約的相容名稱，不表示產品重新採用舊兩檔 consolidation。

## 5. B2 退回 B1

### 5.1 返工不是 transport retry

`case_rework_required` 是語意返工，不是失敗後重送同一次模型請求。新的 B1 必須是另一個 durable attempt；原 B1 對「同一 source＋同一 base」的冪等查回不能被誤用成返工。

在 `CaseMaintenanceWorkflow` 增加明確的 rework 接點，命名採：

```python
start_rework(source_reference, *, base_publication_revision, base_version,
             review_issues)
resume_rework(review_issues)
```

若實作後 `resume_rework()` 可從 checkpoint 安全驗證並恢復原 issues，則不重複要求 caller 傳入；精確簽章以最少可驗狀態為準。rework 使用獨立、可重建的 thread／attempt identity，不覆寫正常 B1 completed checkpoint。

### 5.2 Runtime review 的證據邊界

B2 的 `case_id`、exact `source_reference` 與 `reason`，以及 Runtime 從被退回 B1 stage 精確解析出的 candidate case 內容，會作為 `RUNTIME_REVIEW` 提供給新 B1。Runtime 同時標示該 ID 是正式 base 既有案例，或只是本次被拒 candidate 才出現的暫存 ID。這些欄位都明確標示：

- 它是 Runtime 審查提示，不是員工原話或案例證據；
- 被拒 candidate 只供理解「哪份草稿被指出什麼問題」，不直接匯入新 stage，也不因此成為正式案例；
- B1 必須重新讀本次待整理來源，並至少核對 review 指向的 exact canonical source；除此之外仍保有同文件訪談的正常按需查找能力；
- B1 可依原話修正案例，也可判定該提示不成立；
- 不得直接複製 B2 reason 進案例正文。

B2 可能在相關既有案例中發現問題，該 `source_reference` 不保證位於本次新來源範圍。返工 B1 使用與正常 B1 相同的訪談查找／完整回合讀取能力；review 列出的 exact reference 是完成返工前必讀的最低集合，不是唯一 allowlist。正式 base 既有案例仍須先用 `read_case` 讀取；被拒 candidate-only ID 在新 stage 中不存在，不能假裝成 current case，改由 Runtime 提供其非權威草稿內容並只用該 ID 作 review locator。至少一次成功讀取每個 review reference 才能完成返工。來源工具回傳的是 source owner 的 canonical 原話，B2 reason 與 rejected candidate 仍只是 Runtime 診斷／草稿。

若新 B1 認為 candidate-only 案例應保留，必須根據重讀的 canonical source 呼叫既有 `create_case`，由 Runtime 配發新的案例 ID；若不成立則不建立。未發布的舊 candidate ID 沒有跨 attempt 的正式身分，不建立 alias 或 supersession。正式 base 案例則沿既有 read-before-revise／split／merge／retire 規則處理。

這個按需讀取避免把較早批次的整段原話預載進 request，也不把它冒充本次 `NEW_SOURCE`、不改 source cursor。只在 B1 Prompt／request payload 加必要邊界，不重寫案例分析方法或一般 attempt 行為；後續 compaction 也必須像保護 `NEW_SOURCE` 一樣保護這次真正載入的 canonical review source。

### 5.3 有界停止

每個完整背景 job 最多自動返工一次。返工後的新 B2 再次回傳 `case_rework_required` 時：

- 不發布任何 staging；
- 保留上一個正式 head 與 processed source；
- job 以可診斷 `blocked` 結束，error code 為 `case_rework_limit_reached`；
- App dispatcher 後續只映射結果，不自行重跑或強制覆蓋。

## 6. Stale、失敗與恢復

| 情況 | 行為 |
|---|---|
| B1／B2 transport 或程序中斷 | 保留各自 checkpoint；外層 job 保持 pending，`resume()` 接回同一 base／attempt |
| B1 完成、B2 尚未完成 | B1 staging 不外露、不發布；恢復 B2 |
| bundle save 後、prepare checkpoint 前中斷 | 可重做並留下未選用 immutable artifact；第一版不做 GC |
| publish commit 回覆不明 | 保留同一 `PublishRequest`；同 operation 查 receipt／重送同請求 |
| CAS stale | 舊 candidate 完整拒絕；先核新 head 的 `processed_source`，仍可處理時才建立新的 B1 與 B2 語意 attempts，不搬舊 staging或只換版本 |
| stale 次數耗盡 | `blocked / stale_retry_limit_reached`，保留正式 head |
| source／artifact 不可讀 | 不轉成空白或 no-op；保留可恢復錯誤 |

`max_stale_retries` 是 Runtime 必填的正整數組裝參數，第一版不在 package 偷選產品預設。它限制同一背景 job 因競爭重做的總次數；B1／B2 各自既有模型／工具上限仍限制單一 attempt。`case_rework` 次數不因 stale 而重設，避免同一 job 無界循環。

初次載入與每次 stale reload 都必須由 source owner 驗證來源單調性：若 head 的 `processed_source` 已等於或涵蓋本 job，視為已由其他 writer 完成並查回正式結果；若不同，只有本 job 固定來源被證明緊接在目前 cursor 之後時才可繼續。較舊、重疊、跳過中間訪談或不同 lineage 的來源不得發布，以免 CAS 雖成功卻把 `processed_source` 倒退。dispatcher 仍負責排程／通知准入；這裡只保護 publication 正確性。

## 7. Durable graph 邊界

外層 graph 使用獨立 document-scoped thread，不與 B1 或 B2 共用 thread identity。建議節點：

```text
load_base
→ run_b1
→ run_b2
→ route_b2_result
   ├─ rework_b1 → run_b1
   └─ assemble_bundle
→ prepare_publication
→ publish
   ├─ stale → reload_after_stale → run_b1
   └─ success → END
```

B1／B2 仍使用自己的 durable graphs。外層節點若在子 workflow 完成後、父 checkpoint 前失敗，再次執行時由子 workflow 的 pending/completed state恢復或冪等查回，不重播已完成語意操作。

父 workflow 的 `start()`／`resume()` 一律使用 `invoke(..., durability="sync")`。完整 `PublishRequest` 所在 checkpoint 必須同步完成後，控制流才能進入 `publish`；不能依賴 LangGraph 預設 async durability，否則 commit 成功而前一 checkpoint 尚未落盤時會遺失原 operation／request digest。

不使用新的 LLM orchestrator、不將模型 call 包進長 SQL transaction、不用 process-local lock 作正確性邊界。

## 8. 驗收

至少覆蓋：

1. B1 changed → B2 changed → 完整 bundle 一次發布，來源游標成功後才推進。
2. B1／B2 semantic no-op 仍發布一致 bundle 並推進該 source。
3. B1 完成後 B2 transport failure；resume 不重跑 B1 已完成語意操作。
4. B2 回 `case_rework_required`；新 B1 收到非證據 review，必須重讀 review 的完整回合原話，並可沿正常訪談導覽按需查找其他相關回合；新 B2 才能發布。同時覆蓋正式 base 案例與 rejected candidate-only 案例，後者不得直接沿用未發布 ID。
5. 第二次 rework 進 blocked，不發布、不推進游標。
6. C／另一 writer 先發布造成 stale；舊候選被拒，B1 與 B2 都基於新 head 重做。
7. stale 次數上限，不無限呼叫模型。
8. publication 回覆遺失；同 operation receipt 查回，只有一個 revision。
9. bundle／guide／binding／supersession 任一驗證失敗時零 publication。
10. 文件隔離、同 source completed 查回、pending 拒換輸入。
11. 同一完整訪談回合可支持多個案例；同一案例可持有多個回合引用。revise／split／merge 後引用依實際支持重新分配，不能自動把整批來源複製給所有案例。
12. B1 與 B2 的按需查找權限不被 required／impact hints 縮窄；未被預載的相關案例／訪談可經受控工具讀取，但不全量塞入 request。
13. B1 rework／stale 配置新 `case_attempt_id`，transport resume 沿用；即使新 B1 內容與舊 candidate 相同，B2 也必須建立新的語意 attempt。
14. stale 時相同／已涵蓋來源查回完成；較舊、重疊、跳號或不同 lineage 禁止發布，`processed_source` 不倒退。
15. `PublishRequest` checkpoint 使用同步 durability；模擬 checkpoint／publish 邊界中斷時仍只產生一個 revision。
16. 訪談使用代名詞、簡答或依賴前一個 AI 問題時，案例的回合證據集合包含足以理解主體與回答的相關完整回合；不保存文字 offset，也不把 context-only token 冒充 evidence。
17. 多筆來源即使以反向 evidence key 順序送入，Runtime 仍依 source owner 證明的 canonical order 保存；checkpoint resume 後 key→reference 不漂移，B1／B2 分頁讀回後前後關係不變，模型不控制 offset，context 也不含用來猜順序的時間戳。

離線測試以固定模型回應證明控制流與資料邊界；不以 mock 證明自然模型品質。真 PostgreSQL／新程序完整旅程留給 App 接線切片，但既有 publication 真 PG CAS／receipt 證據直接沿用，不重做無關考卷。

## 9. 明確不做

- 不接 dispatcher、通知准入或自動尋找訪談範圍。
- 不做 C bundle repair。
- 不做 A／B1／B2 compaction 或 provider 切換。
- 不修改主顧問 Prompt、Skills、JD writer、UI 或 production authority。
- 不做文件封存、Memory history UI、artifact GC、舊資料 migration 或第二套 relational Memory。

## 10. 來源

- [MEM-L001 分層 Memory 對齊](2026-09-16-layered-case-and-work-understanding-memory-alignment.md)
- [B1 案例 maintainer 計畫](../plans/2026-09-16-b1-case-maintainer.md)
- [B2 staged maintainer 計畫](../plans/2026-09-16-b2-understanding-maintainer.md)
- [B2 Agent graph 計畫](../plans/2026-09-16-b2-understanding-agent.md)
- [舊 B1／B2 adoption mapping](2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)
- [Anthropic：Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)，查閱 2026-09-17
- [LangGraph：Functional API / durable execution](https://docs.langchain.com/oss/python/langgraph/functional-api)，查閱 2026-09-17；本案固定 `langgraph==1.2.11`
- [LangGraph：Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)，查閱 2026-09-17；只採本案固定版本實際存在的能力
- [AWS：Optimistic locking with version number](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/BestPractices_OptimisticLocking.html)，查閱 2026-09-17
- [OpenAI：Model guidance / agent orchestration](https://developers.openai.com/api/docs/guides/latest-model)，查閱 2026-09-17；只採工具／重試責任原則，不改目前 Luna provider 決策
- [OpenAI Responses：List input items](https://developers.openai.com/api/reference/resources/responses/subresources/input_items/methods/list)，查閱 2026-09-17；items 的身分、游標與 asc／desc 順序分開，本案只採「順序由 owner 明示、不可由 ID 猜測」原則
- [OpenAI Codex：Memory consolidation template](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/consolidation.md)，查閱 2026-09-17；raw rollout 為不可變證據，同一 reference 可在確有不同局部價值時重用
- [Anthropic：Citations](https://platform.claude.com/docs/en/build-with-claude/citations)，查閱 2026-09-17；transcript 類 custom content 的 citation 粒度與 block 順序由應用程式提供，不另作字元切片

## 11. Closure

- **Decision：**新增 deterministic `BackgroundMemoryWorkflow` 串接既有 B1、B2、bundle 與 publication；B2 review 只作 Runtime 診斷，新 B1 必須重讀原話；最多返工一次。
- **Why：**避免 B1／B2 各自發布或 App 重做語意不變量，同時保留精確恢復、stale 重整與一次原子 publication。
- **Next gate：**依本設計寫施工計畫，以測試先行完成 package 切片；完成後才接 App dispatcher 與真 PG／新程序旅程。
