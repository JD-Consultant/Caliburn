# 持久 AI JD 工作草稿與語意審核研究

- 日期：2026-08-22
- 狀態：Design aligned；owner 已於 2026-08-22 核准書面版本，ADR 0066／0067 Accepted
- 範圍：AI 工作草稿生命週期、跨輪持久化、低階編輯、驗證、部分接受／拒絕、stale review、員工 authority
- 不在本輪：RAG／Reference、能力級別、A、auto-accept、多草稿 fork、多人協作、正式品質 eval
- 前置決策：ADR 0060–0065；其中 ADR 0064 的 run-scoped candidate 生命週期由本研究重新檢視

大方向仍以 [`2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`](2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md) 為準。VS Code、Claude Code、GitHub PR、Word 與 Google Docs 只提供成熟機制與互動證據，**不是要求 Caliburn 複製 IDE、Git、PR、檔案格式或其完整介面**。

## 0. 結論

採用**每份 JD 一個持久、非權威的 AI 工作草稿，員工以核准 JD 與工作草稿之間的語意差異作決策**。

這取代 ADR 0064 的「每個 run 建立 `/candidate/<run_id>`、未發布 scratch 不跨一般 run、模型最後發布 checked receipt」生命週期，但保留 ADR 0064 已證明有效的 Deep Agents VFS、低階 editor verbs、canonical JD resources、確定性 Evidence anchor、semantic verifier、atomic dependency 與員工 authority。

第一版的白話效果：

1. AI 在同一份 JD 的工作草稿中持續新增、修改與刪除 Duty／Task／OPKS；員工沒有立即決定也不妨礙後續訪談與 AI 繼續編輯。
2. 核准 JD 對 AI 永遠唯讀；只有員工接受、修改後接受或直接編輯正式 JD，內容才進入核准成品。
3. 員工可獨立接受或拒絕互不相依的語意變更；會造成非法中間態的相依變更必須整組裁決。
4. 接受後，核准 JD 吸收該組內容，工作草稿保留，兩者的差異自然縮小；拒絕後，草稿撤回該組內容並保存拒絕理由；延後則維持差異。
5. AI 或員工再改動一個尚未核准的 group 時，任何針對舊內容的 review token 失效；不相干 group 不受影響。
6. 工作草稿可以暫時不完整或無效，但 blocking diagnostics 未清除前不顯示可接受動作，也不能提交到核准 JD。
7. 模型不再回填 candidate revision、digest、action handles、used Skill receipts 或 quote offsets；這些由 framework／application 從實際 state 產生。

## 1. owner 澄清與產品不變量

### 1.1 owner 澄清

2026-08-22 owner 明確說明：VS Code 是概念參考，不是要完全一樣。可轉移的是「持久隔離工作區、模型可繼續編輯、差異可見、最後由人整合」；不可直接移植的是 Git branch、commit、PR、檔案中心 UI、程式碼 hunk、多人 code review 與 IDE permission mode。

### 1.2 不可被技術方案改寫的產品效果

- 一位主要職務分析顧問，以目前焦點訪談並保留旁支線索。
- Duty、Task、OPKS 都可隨訪談修正，分析 Skills 按需載入。
- 員工原話、更正、決策與拒絕理由不因模型失敗或關閉頁面消失。
- AI 可以修訂自己的工作草稿，但不能直接修改核准 JD。
- 需要進入正式文件的 LLM 內容都必須讓員工接受、修改後接受或拒絕。
- 重大衝突或缺少必要事實時先詢問員工；一般未決事項留在待處理缺口，不阻塞整場訪談。
- 第一版不做 RAG、能力級別、A、auto-accept 或多 Agent。

## 2. 現況診斷

### 2.1 已做對的部分

ADR 0064 與現行 code 已建立：

- Deep Agents `FilesystemMiddleware` 與 provider-neutral VFS；
- `ls／read_file／grep／write_file／edit_file／delete` 小型低階工具；
- `/skills`、`/sources`、`/approved`、`/pending` 只讀，candidate 可寫；
- canonical Duty／Task／OPKS resources；
- application 產生正式 identity、semantic diff、dependency 與 Evidence offsets；
- 模型不能呼叫 accept／reject／authority commit；
- split／merge 以 create／edit／delete 的相依組合表達，不另建 business Tool。

這些都應保留，不需退回 mega-form 或每種 domain operation 一個 Tool。

### 2.2 與最新 owner 方向衝突的部分

現行 `build_consultant_workspace_backend()` 每個 run：

1. 從當下核准 JD 重新 `project_candidate_files(..., run_id=run_id)`；
2. 建立新的 `StateBackend()`；
3. 只允許 `/candidate/<current-run-id>/**`；
4. 將初始 files 隨本次 `agent.ainvoke()` 傳入；
5. graph 最後只保存 checked receipt／published review queue，不保存未發布 after-state。

因此目前真正持久的是「已發布待審 changeset」，不是「AI 實際正在編輯的完整工作草稿」。一般新 run 會從 approved 重新開始；未完成、尚未 final publication 或只被員工延後的工作面無法自然成為下一輪的同一份 after-state。

另一個不必要負擔是 model-authored publication handshake：模型必須先呼叫 `check_candidate_document`，再在 final Structured Output 精確回送 revision／digest／完整有序 action handles。這些都是 application 已知資料；錯一個值就讓整輪在最後失敗，且額外增加 model step 與 token。

## 3. 官方資料研究

以下分成「官方明示」與「Caliburn 推論」。大廠採用只證明機制成熟，不等於已驗證本產品的職務分析品質。

### 3.1 OpenAI：編輯由 harness 真正套用並回報

OpenAI Apply Patch 明示：模型提出 create／update／delete diff，application 的 patch harness 套用、記錄成功或錯誤，再把結果送回模型，模型可繼續編輯或最後解釋。官方另要求 server-side validation；模型不應被當成真實執行結果的來源。

來源：

- [OpenAI — Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch)
- [OpenAI — latest model guidance／tools](https://developers.openai.com/api/docs/guides/latest-model)

可轉移到 Caliburn：模型只負責選擇與提出低階編輯，framework／application 套用實際 after-state 並回傳 diagnostics。不可轉移：使用 unified diff、host repository 或 OpenAI-only Tool 當 provider-neutral truth。

### 3.2 Claude Code：checkpoint 與工作狀態可恢復

Claude Code 明示每個 user prompt 建 checkpoint，checkpoint 隨 session 保存並可在 resume 後 rewind；file edits 與 conversation 可分開恢復。Desktop 提供 diff review 與後續 feedback。它也明示 checkpoint 不是永久版本控制，且 shell／外部修改不一定被捕捉。

來源：

- [Anthropic — Checkpointing](https://code.claude.com/docs/en/checkpointing)
- [Anthropic — How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works)
- [Anthropic — Claude Code Desktop](https://code.claude.com/docs/en/desktop)

可轉移到 Caliburn：員工每次送出、review command 與重要 graph transition 都應有 durable checkpoint；草稿與對話可恢復。不可轉移：30 天 retention、Git、Bash、permission mode 或完整 rewind UI。

### 3.3 VS Code／GitHub：先在隔離工作面迭代，再審 diff

VS Code 現行 Agent Host 明示：agent 直接在 session folder 或隔離 worktree 保存修改，不需要每一 edit 先 Keep／Undo 才能繼續；使用者最後透過 diff、Source Control 或 PR 整合。`Mark as Reviewed` 在使用者或 agent 再改檔時會清除。

GitHub ruleset 明示可把 approval 綁在當時的 diff；diff 改變後，stale approval 可被撤銷並要求重新核准。

來源：

- [VS Code — Review and revert agent changes](https://code.visualstudio.com/docs/agents/run/review-code-edits)
- [GitHub — Available rules for rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)

Caliburn 推論：normal AI edit 不需逐次工具核准；員工審核應綁定精確 workspace revision／semantic group digest，變更後 fail stale。VS Code 只是此生命週期的證據，不是 UI 規格。

### 3.4 Word／Google Docs：逐項接受與拒絕

Word Track Changes 與 Google Docs Suggesting 都明示：建議可以逐項接受／拒絕，也可整批處理；Google 原生 suggestion 在 owner 接受前不取代原始內容。Gemini in Docs 也把建議直接呈現在文件中並提供逐項接受。

來源：

- [Microsoft — Track changes in Word](https://support.microsoft.com/en-US/Word/training/track-changes-in-word)
- [Microsoft — Edit with Copilot in Word](https://support.microsoft.com/en-us/office/edit-with-copilot-in-word-647d5d14-eaec-4e8a-a574-7cefffa7f8f0)
- [Google — Suggest edits in Google Docs](https://support.google.com/docs/answer/6033474)
- [Google — Write & edit with Gemini in Docs](https://support.google.com/docs/answer/13447609)

限制：這些產品沒有公開的 Duty／Task／OPKS dependency graph 或不可分割 semantic group。Caliburn 可採其逐項 UX 原則，不能假裝框架已提供職務結構原子性。

### 3.5 LangGraph／Deep Agents：成熟 persistence 與 VFS primitive

官方明示：

- Deep Agents `StateBackend` 將 files 放入 LangGraph state，同一 thread 可藉 checkpoint 跨多輪保存；官方定位偏agent scratch，且graph外呼叫不會直接形成state update；
- `StoreBackend` 供跨 thread 的長期 filesystem namespace；
- `CompositeBackend` 依 virtual path route 到不同 backend；
- LangGraph checkpointer 每個 graph step 保存 state，支援記憶、HITL、time travel 與 fault tolerance；
- parent graph 與 subgraph 共享 state key 時，可直接把 subgraph 加為 node；per-thread subgraph 可累積狀態，per-invocation subgraph則可把共用 state 回寫 parent；
- `interrupt()` 會 durable 暫停並等待 `Command(resume=...)`；
- LangChain HITL middleware 的 approve／edit／reject 主要是「工具執行前的核准」，不是可延後、多筆並存的文件 diff queue。

來源：

- [Deep Agents — Backends](https://docs.langchain.com/oss/python/deepagents/backends)
- [Deep Agents — Context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering)
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph — Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangChain — Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)

Repo 實際 pin 為 LangChain 1.3.15、LangGraph 1.2.11、Deep Agents 0.7.5。Deep Agents 仍是 0.x，implementation 必須維持精確 pin 與 characterization tests，不能只因官方文件最新就未審核升版。

施工前映射另發現：pinned `FilesystemState.files`已使用LangGraph `DeltaChannel`，而employee review／direct-edit API需要在agent execution外重基線同一份workspace。Owner因此核准successor ADR 0067：`/workspace`改用framework內建`StoreBackend`＋既有Postgres Store；checkpointer保留messages、interrupt與run recovery。這不是增加第二份草稿，而是把唯一active workspace放到更符合官方用途、application command也能直接操作的backend。

## 4. 三種方案比較

| 方案 | 效果與功能 | 主要問題 | 裁決 |
|---|---|---|---|
| A. run-scoped candidate＋published pending queue | 現行 code 已有；publication fail closed | 未發布 after-state 不跨一般 run；模型必須完成 receipt handshake；LLM 下一輪不是自然接同一份草稿 | 不採用 |
| B. durable typed patch／suggestion queue 作主要工作面 | partial review、audit、dependency 容易顯式建模 | 模型編輯 operation 表而非完整文件；需要重建 conditional after-state；schema 與 receipt 再度膨脹 | 不採用作主要工作面；只保留 derived semantic diff |
| C. persistent workspace＋derived semantic review | AI 始終編輯真實候選 after-state；跨輪可續；diff review、部分接受、checkpoint自然 | 仍需 JD semantic diff、dependency、rebase 與 authority policy | **採用** |

方案 C 不是因為程式最少，而是最符合產品效果、模型編輯可靠性、員工理解與大廠成熟流程；省碼只來自直接使用 LangGraph persistence 與 Deep Agents VFS。

## 5. 採用設計

### 5.1 一份 JD 一個 active workspace

- 每份 JD 第一版只有一個 `/workspace/**`；沒有 run ID，也沒有多草稿 fork。
- workspace 在文件建立時由核准 JD seed 一次，之後跨員工 turn、provider retry、關閉與重新開啟持續存在。
- 新員工訊息不重建 workspace，不把 pending 重新 overlay，也不要求選擇某個 changeset 才能繼續。
- workspace 是 AI／員工共同可編輯的非權威 working state，不是第二份可匯出官方 JD。
- `/approved/**` 始終是核准 JD 的只讀 projection；export 只讀 approved，不讀 workspace。

### 5.2 framework mapping

| 產品目的 | 採用成熟元件 | Caliburn 只補的差額 |
|---|---|---|
| 工作草稿與跨輪續編 | Deep Agents `StoreBackend`＋document-scoped LangGraph Postgres Store namespace | canonical JD resource schema、path policy、digest manifest |
| 多來源 virtual workspace | Deep Agents `CompositeBackend`／`BackendProtocol` | `/sources`、`/approved`、`/review` 的 read-only projection |
| 對話與失敗恢復 | LangGraph checkpoint／pending writes／replay primitive | source-first idempotency 與產品錯誤碼 |
| 長期員工原話與決策記憶 | LangGraph Postgres Store | source lineage、拒絕重提條件 |
| 必要澄清 | LangGraph `interrupt()`／`Command(resume)` | 哪些職務歧義必須問、affected branch |
| context 按需載入 | LangChain middleware＋Deep Agents VFS／Skills | 目前職務焦點與最小充分資料政策 |
| low-level edit | `write_file／edit_file／delete` | canonical entity resources 與 scope |
| semantic review | LangGraph state／command 作 lifecycle substrate | JD semantic differ、dependency group、employee authority |
| Evidence | Pydantic、Store、exact quote resolver | claim-support、correction lineage、source trust policy |

不保留 `Work Model／Focus／Progress／Proposal／Current JD` 等舊元件身分。文件中若為了追溯提及，target implementation 仍應使用中立目的與 framework primitive；職務分析語意則由 Skills 與最薄 domain policy 表達。

### 5.3 namespace

第一版模型看到：

- `/skills/**`：只讀，按需載入完整分析方法；
- `/sources/**`：只讀，員工原話、metadata 與更正 lineage；
- `/approved/**`：只讀，唯一核准 JD；
- `/workspace/**`：可讀寫，持久 AI working draft；
- `/review/**`：只讀，由 approved vs workspace＋decision metadata 即時計算的語意差異與 diagnostics。

不使用 host filesystem、Git、shell、execute、network 或任意跨文件 query。VS Code／GitHub 只是 lifecycle analogy。

### 5.4 Tool surface 與自動驗證

模型只需要 `ls`、`read_file`、`grep`、`write_file`、`edit_file`、`delete`。不增加 `add_task／split_task／merge_duty／revise_opks`，也不保留 model-facing `check_candidate_document`。

驗證改成 graph／middleware 自動 gate：

1. backend 每次 mutation 先驗 path、permission、exact replacement 與基本 canonical resource shape；
2. mutation wave 後由 application validation node 讀 framework 真實 after-state；
3. 執行 Pydantic parse、JD invariant、handle／linkage、Evidence、read-set 與 dependency diagnostics；
4. 有可修 blocking error 時，以精簡 observation 回到同一 model loop，允許受預算限制的 repair；
5. 最新 workspace revision 通過後，`/review` 才標成 reviewable；
6. 模型 final response只承載員工可見顧問回答、目前焦點／問題或必要澄清，不再發布 receipt。

application 自己知道 workspace revision、digest、semantic action、Skill receipt 與 source offsets，不要求模型 echo。成功驗證後又發生任何 overlapping mutation，checked status自動失效。

### 5.5 review 與部分決策

`/review` 是 projection，不是第二份 raw changeset store。每個 review group 由 application 依 semantic paths、before／after、dependency component 與 exact content digest 產生 stable-per-revision identity。

- **接受**：重鎖 document、驗 expected approved revision、workspace revision 與 group digest；在同一 authority command 將 group after-state寫入 approved。workspace 不需整份重建，差異自然縮小。
- **修改後接受**：員工修改 workspace 的該組內容，重新驗證後以新 digest接受；員工實際輸入另保存為 employee source。
- **只修改草稿**：更新 workspace但不改 approved；舊 group identity失效，新差異重新產生。員工輸入仍先 durable 保存，但不代表已核准。
- **拒絕**：依目前 approved與 dependency group撤回 workspace 中該組變更；另保存 rejection decision、reason、evidence/read-set。沒有新 evidence、員工新要求或相關工作邊界改變，不得只換句話重新提出。
- **延後**：workspace不變，decision metadata標 deferred；下輪模型仍可讀到，但不得誤稱核准。

互不相依 group 可任意順序處理。會形成 invalid intermediate state 的 operations 由 application dependency graph 組成同一 atomic component，全有或全無。模型可提供人類可讀 intent，但不能指定 authority identity 或繞過 grouping。

### 5.6 stale、並行與正式 JD direct edit

- review command 綁 exact approved revision、workspace revision與 group digest；瀏覽器拿舊資料操作時 fail stale，不猜測套用。
- AI 或員工修改同一 group 後，舊 review token失效；不重疊 group維持可審。
- 員工直接修改正式 JD 時，command 先提交 approved；workspace 對不重疊 path做確定性 rebase，重疊 path形成 conflict diagnostic並只阻擋 affected group。
- 單一本機操作者仍需序列化同一 document 的 AI mutation／employee command，防止背景 run與 UI review競爭。
- 已接受內容永遠留在 approved；AI 若日後再挑戰，必須形成新的 workspace diff並重新審核。

### 5.7 checkpoint、記憶與 context 成本

- document-scoped `StoreBackend` namespace持有workspace files；consultant agent與employee command共用同一backend，不建立checkpoint channel bridge。
- 每個員工 input、重要 graph transition與 review command仍有checkpoint；第一版用於對話／interrupt／run恢復與內部稽核，不提供workspace fork／time-travel UI。
- employee source與 correction／decision memory繼續由 Store保存；checkpoint不是來源 truth，Store也不是核准 JD writer。
- workspace持久化不等於每次把完整草稿塞進 prompt。動態 context只帶 approved revision、workspace revision、目前焦點、gap／review摘要與導覽 path；完整 entity、來源、Skill按需 `read_file／grep`。
- 不引入 multi-agent、critic或額外 model pass。移除 model-facing check與publication echo後，應重新量測平均 calls／tokens；ADR 0065 的 11-call／160k仍先作 hard safety ceiling，不作使用目標，也不得因 redesign自動提高。

## 6. framework 無法替代、必須保留的最薄責任

截至查核日，沒有官方框架能直接提供：

1. Duty／Task／OPKS 的 semantic diff與 dependency grouping；
2. exact employee source是否足以支持某個職務主張；
3. correction lineage對既有 Evidence的失效；
4. accept一組結構修改時的 JD domain transaction；
5. 專業職務分析焦點與充分性判斷。

因此保留 Pydantic domain schema、deterministic semantic differ／verifier、employee authority command與分析 Skills。這些不是保留舊 workflow元件，而是框架沒有領域知識的具體差額。應優先使用 Pydantic validation、LangGraph reducer／Command、PostgreSQL transaction與 Deep Agents backend policy，不能再造通用 workflow／memory／filesystem framework。

## 7. 第一版明確不做

- 多個 active workspace、branch、fork或合併 UI；
- Git repository、PR、commit或 host file authority；
- auto-accept／Auto mode；
- 每個低階 edit 都彈員工核准；
- RAG／Reference；
- 能力級別與 A；
- 多 Agent、planner／writer／critic；
- 正式 eval平台、billing subsystem或版本歷史 UI；
- 把 pending、checkpoint或chat history當第二份核准文件。

## 8. 風險與施工 gate

1. **Store成長**：量測canonical workspace files、manifest與decision memory的Postgres Store大小及多輪成長；不得同時複製到checkpoint files channel。
2. **Store持久化**：必須證明關閉／重啟後同 document仍讀到完全相同 workspace，且新 source不會重新 seed。
3. **partial decision rebase**：至少覆蓋十項接受九項、拒絕一項 O，以及 Task拆分＋OPKS atomic group。
4. **stale review**：workspace或approved任一 overlapping path改變後，舊 command必須 fail；不相干 group仍可處理。
5. **failure recovery**：provider timeout、process crash與invalid workspace不得改 approved；下一輪可在保留 workspace與diagnostics基礎上繼續。
6. **authority零繞過**：VFS Tool、validation node、model final與Store都不能寫 approved；只有員工 authority command可寫。
7. **成本**：以 scripted tests先驗語意，再做一次窄 live smoke量測 calls／tokens／latency／cost；不建立完整eval平台。
8. **產品北極星**：每完成 workspace persistence、semantic review、partial authority與UI一個切片，都回看產品大方向；若框架要求改成 wizard、一次生成或逐edit核准，應停下討論而不是讓框架反定義產品。

## 9. 後續文件關係

- ADR 0064 保持 Accepted原文，作為為何從mega-form改用Deep Agents VFS的歷史。
- ADR 0066取代run-scoped candidate、model-facing check／publication receipt與第二份pending lifecycle；ADR 0067再把其`StateBackend` mapping修正為`StoreBackend`，其餘VFS、Evidence、authority與no-RAG決策明示保留。
- ADR 0065 的cost guard先保留，待新拓撲窄量測後再決定是否需要新successor；不得事後改寫0065。
- owner已審閱本研究並核准 ADR 0066；下一步先撰寫 implementation plan，經計畫交接後才修改production。
