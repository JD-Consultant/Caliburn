# Memory 背景整併與即時修補：寫入協調、失敗恢復

> 2026-09-05 · `LLM-Q018` · **Owner 已釐清分工偏好；協調機制 OPEN，先回 Q017 確認前置流程**。
>
> Q017 的主要組合方向已獲 Owner 暫時同意；本文的協調策略尚未核准，不是施工計畫。只討論通用 Memory，不套 JD、舊元件或領域欄位。

## 1. 本輪唯一問題與既有依據

**背景整併 B 與即時修補 C 都能修改相同 Memory 時，框架原生會處理哪些並行寫入問題，還缺哪個接合？**

Owner 本輪釐清：B 根據對話整理，C 根據本輪資訊作即時修補；不應預設 B 會重新理解錯誤，更不能因此新增語意衝突驗證器。此前「舊理解蓋回去」的說法太容易混淆：本文真正查證的是**即使兩邊分析正確，儲存時是否仍可能互相覆蓋**。這不等於宣稱來源正確就能保證所有語意判斷永不出錯；本輪不討論該題。Owner 未核准「C 必須等待」，要求先查清框架既有能力。

**Owner 追加的執行角色釐清：** B 是額外執行的背景 Memory Agent，負責根據對話整理 Memory；C 是主 Agent 在當輪按需使用 Memory Tool 作局部修補，**不是第三個修補 Agent，也不是觸發整個 B**。後續研究的是「背景 Agent 的寫入」與「主 Agent 的工具寫入」如何共用框架的並行處理能力；不能為了排隊而未經討論把 C 改成委派背景 Agent 重新分析、或在 Tool 內再加一個模型。這是 Owner 對既有 A/B/C 概念的釐清，不是新增框架事實、指定工具 schema 或核准協調策略。

沿用 [Q017 框架接力](2026-09-05-openai-shaped-memory-framework-composition-research.md)：`create_agent`＋LangGraph＋獨立 `FilesystemMiddleware`／`StoreBackend` 為主要設計候選，LangMem 紀錄工具保留備選。不重選根 Agent、不重做 artifact 分層研究。

**Owner 最新裁決（2026-09-05）：** 優先維持主 Agent 與背景 Agent 分工、一般執行互不阻塞，在修改共用 Memory 時協調；不是硬性要求任何情況都零等待。若確實不可行，允許再比較替代方式。框架覆蓋不足時可研究必要自訂擴充，**但先把主 Agent、背景 Agent 與接力流程討論清楚，之後才決定是否新增、怎麼新增**。因此本題不再追問「是否偏好整輪等待」，也不立即開始 custom backend／queue 設計；先按 [Q017 §3.3](2026-09-05-openai-shaped-memory-framework-composition-research.md#33-owner-最新方向先確認分工與完整接力再補協調機制) 逐段確認。這是 Owner 的方向與研究順序，不是官方共識或施工授權。

本輪完整回讀既有[版本／並行／重播研究](2026-09-02-memory-versioning-concurrency-and-replay-research.md)與[最小切片重新驗證](2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md)。舊研究已說明 CAS、歷史版本與 idempotency 不等於跨家共同的必選實作；不能把整套候選重新加回來。新增查證的理由只有一個：現在 B、C 都是明確保留的寫入路徑，寫入重疊已成為具體接合問題。

本文以 **[官方事實]／[推導風險]／[待選組合]** 區分證據強度。不同廠商有共同的安全目的，不代表它們使用同一底層機制，更不代表某個組合已證明效果最佳。

## 2. OpenAI 公開實作不能混成一套

### 2.1 Agents SDK Sandbox Memory：以 session lifecycle 安排整理

**[官方事實]** SDK 文件描述：run 後累積互動片段，sandbox session 關閉時處理累積材料；`liveUpdate` 則是執行中修補。這與「每次訊息都重跑背景整理」不同。[官方 Memory 指南](https://openai.github.io/openai-agents-js/guides/sandbox-agents/memory/)

固定原始碼可進一步證實：

- generation manager 依 sandbox session 物件與 layout 重用，並登記 pre-stop hook；`flushPromise` 合併**同一 manager** 的重複 flush。這不是跨 process、跨 session 的 Memory 全域鎖。[manager／hook](https://github.com/openai/openai-agents-js/blob/e6c3663017e3e36af67370a4bc09db674ef0fd9f/packages/agents-core/src/sandbox/memory/generation.ts#L70-L175)、[flush](https://github.com/openai/openai-agents-js/blob/e6c3663017e3e36af67370a4bc09db674ef0fd9f/packages/agents-core/src/sandbox/memory/generation.ts#L237-L258)
- 所查 flush 路徑遇到 Phase 1／2 錯誤會記錄 warning；finally 清理 pending 集合並解除登記。**不能把這段描述為持久重試佇列或保證失敗後自動補完。**[錯誤處理](https://github.com/openai/openai-agents-js/blob/e6c3663017e3e36af67370a4bc09db674ef0fd9f/packages/agents-core/src/sandbox/memory/generation.ts#L269-L304)
- Phase 1 依序保存候選與 summary；Phase 2 Agent 完成後才保存 selection 記錄。此處沒有承諾所有檔案與處理狀態一起原子提交。[保存順序](https://github.com/openai/openai-agents-js/blob/e6c3663017e3e36af67370a4bc09db674ef0fd9f/packages/agents-core/src/sandbox/memory/generation.ts#L354-L444)

**可學的是整理時機、同一執行者的去重、產物與完成狀態分工。** 不能由 session-close 推論所有前台／背景 writer 都已共用互斥，也不能因其為官方實作便忽略上述恢復邊界。

### 2.2 Codex local Memory：背景 Phase 2 有明確的 job ownership

**[官方事實]** 所查 Codex 版本在 Phase 2 接觸 Memory workspace **之前**取得 global consolidation job claim；執行中更新 lease，失敗記錄 retry 狀態。這是背景整併 B 對 B 的明確協調。[Phase 2 入口](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/src/phase2.rs#L49-L84)、[job 狀態與重試](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/src/phase2.rs#L219-L324)

成功／失敗收尾也有具體順序：

1. 等 Agent 結束並要求關閉；若不能確認關閉，保留原 lease 到過期，避免立刻再放入背景 writer。
2. 完成後驗證產物，再確認仍持有 claim，才更新 workspace baseline 及 job 成功狀態。
3. Agent 失敗的分支清理 symlink 並記錄失敗；**所查分支沒有整份 Memory 正文回滾**。baseline 與資料庫 job 狀態也不是同一個跨儲存交易。[收尾原始碼](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/src/phase2.rs#L395-L487)

**可學的是先取得修改資格、確認執行者停止、完成與失敗分開記錄。** 目前證據不足以宣稱 C 的任意檔案編輯也會取得這個 global Phase 2 claim；不把 B/B 保護誇大成 B/C 全部安全，亦不把 lease 宣稱為檔案交易或 exactly-once。

## 3. 框架已提供什麼，沒有提供什麼

| 已核實的官方能力 | 真正保證／用途 | 不能直接推論 |
|---|---|---|
| Deep Agents 檔案 Memory | 官方明示同檔並寫可能 last-write-wins，建議考慮序列化背景整併或分檔降低競爭 | 使用 edit 工具便不會 lost update |
| `StoreBackend.edit/aedit` | 取得檔案、檢查字串匹配、形成新內容、寫回 Store | `old_string` 檢查等於資料庫 compare-and-swap |
| Agent Server `enqueue` | 同一 `thread_id` 的 run 排隊 | 不同 thread 寫同一 namespace 也自動排隊 |
| LangMem `ReflectionExecutor` | 延後／去除重複待執行背景工作；local instance 以單一 worker 依序 invoke reflector | 不經該 executor 的 C 也受保護；所有 process 都共用一把鎖 |
| LangGraph checkpointed task | 可重用已完成 task 的結果；未完成 task 可重新執行 | Store 副作用與 checkpoint 原子提交、失敗自動還原檔案 |
| Anthropic Managed Memory precondition | 可帶讀取時的 content hash，若已改變則拒絕更新，重新讀取後再處理 | 所有 Memory 服務都強制 CAS；或 LangGraph Store 已有同樣參數 |

來源：[Deep Agents concurrent writes](https://docs.langchain.com/oss/python/deepagents/memory#concurrent-writes)、[StoreBackend edit 原始碼](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L472-L545)、[Agent Server enqueue](https://docs.langchain.com/langsmith/enqueue-concurrent)、[Functional API idempotency](https://docs.langchain.com/oss/python/langgraph/functional-api#idempotency)、[Anthropic 安全更新](https://platform.claude.com/docs/en/managed-agents/memory#safe-content-edits-optimistic-concurrency)。

**[推導風險]** StoreBackend 的兩次編輯可能先各自讀到相同舊檔，再各自寫回整檔，後寫者蓋掉另一人的修改；即使兩人改的是不同段落也可能發生。因此只將 `put` 排隊，或只要求 LLM 填 `old_string`，都不足以保護整個「讀取 → 判斷 → 寫入」週期。這是由上述原始碼推導的風險，沒有在本輪重做併發實驗。

### 3.1 Owner 追問後的框架複核：有功能，不等於已自動覆蓋 B/C

- **B 讀對話整理是官方作法。** Deep Agents background consolidation recipe 明確讀 recent conversation，再合併進既有 Memory；本輪不把背景來源改成只讀舊理解。[官方 recipe](https://docs.langchain.com/oss/python/deepagents/memory#background-consolidation)
- **並行保護並未在新版 edit 自動補齊。** 本輪重新查詢 Deep Agents upstream HEAD `c366c495129a67629a4477c51e0d1dec778d36e3`，`edit/aedit` 仍是 get → 字串替換 → put，沒有在該方法把 read-modify-write 包成原子條件更新。HEAD 是定向源碼證據，不當作已安裝或已發佈相容組合。[此次固定 edit](https://github.com/langchain-ai/deepagents/blob/c366c495129a67629a4477c51e0d1dec778d36e3/libs/deepagents/deepagents/backends/store.py#L472-L545)
- **LangMem 背景 executor 有可用能力，但不是共用 Store 鎖。** 官方 delayed-processing guide 提供 per-thread debounce。固定源碼 local executor 用單一 worker 正常循序執行 reflector；pending cancellation 不會讓已進入 `invoke` 的任意寫入自動撤銷，也管不到旁路 direct Memory tool。remote executor 則提交 Agent Server run，使用 `multitask_strategy="rollback"`，不是 `enqueue`。[延後處理指南](https://langchain-ai.github.io/langmem/guides/delayed_processing/)、[remote submit](https://github.com/langchain-ai/langmem/blob/f8c7ebd6110c124a36995dab645a8cb0eb0b8210/src/langmem/reflection.py#L161-L200)、[local worker](https://github.com/langchain-ai/langmem/blob/f8c7ebd6110c124a36995dab645a8cb0eb0b8210/src/langmem/reflection.py#L253-L339)、[invoke 路徑](https://github.com/langchain-ai/langmem/blob/f8c7ebd6110c124a36995dab645a8cb0eb0b8210/src/langmem/reflection.py#L401-L448)
- **Agent Server 原生可排隊，不需要先發明 queue。** `enqueue` 是 Server 的同 thread run 策略；單獨 OSS LangGraph `compile(checkpointer=...)` 不因此取得 Server double-texting 策略。將 B/C 放在哪個受協調的執行入口，仍是組合問題，不以「相同 Memory namespace」冒充相同 run queue。[enqueue](https://docs.langchain.com/langsmith/enqueue-concurrent)、[Server／OSS 邊界](https://docs.langchain.com/langsmith/double-texting)
- **Tool error 可以修正，但只有錯誤確實回傳時才成立。** Deep Agents 文件提到模型通常可從 conflict error 重試；同頁仍警告 last-write-wins。不能推論每次遺失更新都會產生 error，也不能要求模型修正一個工具完全沒有告知的覆蓋。[官方並寫說明](https://docs.langchain.com/oss/python/deepagents/memory#concurrent-writes)

LangMem 指南也有「cross-thread coordination」的概括說法；沒有指定 Memory revision、原子 read-modify-write 或全 writer 互斥契約，故不能只靠該詞宣布本題已解決。[原指南位置](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/#with-storage)

**本次回答：框架已提供排隊、背景去重及錯誤回饋等零件；主要候選的 StoreBackend 不會自動替所有 B/C 寫入加保護。** 下一步先核對官方 execution 能力如何覆蓋兩條寫入路徑，不先製作自訂鎖、版本服務或新語意驗證流程；也不因 ReflectionExecutor 存在，就自動推翻 Q017 改成每層必用 LangMem。

### 3.2 實際接法複核：原生 enqueue 的單位是 run，不是 Memory Tool

**[官方事實]** Agent Server 的 background run 可以指定 thread，透過 `runs.create` 啟動、`runs.join` 等完成；`enqueue` 則讓同 thread 的前一個 run 完成後才開始下一個。背景是執行／等待方式，不代表它使用另一種 Store 寫入保護。[Background runs](https://docs.langchain.com/langsmith/background-run)、[Enqueue 契約](https://docs.langchain.com/langsmith/double-texting#enqueue-default)

**[官方事實]** 同 thread 可由不同 assistant 接續執行，但第二個 assistant 會使用第一個留下的 checkpoint。官方範例是同一 graph 的不同 assistant configuration；不是任意兩個 graph 的 state 都能直接互換、也不是兩套完全隔離的聊天紀錄。[Same-thread 官方範例](https://docs.langchain.com/langsmith/same-thread)、[Assistant 與 graph 的關係](https://docs.langchain.com/langsmith/assistants)

**[接法推導，不是已核准設計]** 若直接讓前台 A 與背景 B 的完整 invocation 都走同一 Server thread／enqueue，且沒有旁路 writer，便可避免兩個 run 同時執行各自的 Memory 工具。C 仍是 A 裡的 Tool，不新增修補 Agent。然而它有以下代價，不能描述成「只有存檔會短暫等一下」：

1. **B 已開始時，新的 A 也要等 B 的 run 結束**，即使這次 A 最後根本不使用 C。它協調的是整輪執行，不是僅協調 Memory 寫入。
2. **共用 checkpoint 的內容必須相容並分清用途。** B 的整理訊息與工具結果若直接寫同一 `messages`，就不能假設前台看不到；這需要明確 context／state 接法，不是只改成相同 thread ID。
3. **run 序列化不等於同 run 內所有 Tool 序列化。** `ToolNode` 支援平行工具執行；同一模型回應的多筆檔案修改仍須核對。官方模型介面對支援者提供 `parallel_tool_calls=False`，但不能因此推論所有 provider、所有旁路呼叫或外部 Store 都自動受保護，也不在此輪決定全面關掉平行讀取。[ToolNode](https://docs.langchain.com/oss/python/langchain/tools#toolnode)、[Parallel tool calls](https://docs.langchain.com/oss/python/langchain/models#parallel-tool-calls)

反過來，**A、B 使用各自 thread，C 在 A 中直接 edit 同一 Store**，則同 thread enqueue 只涵蓋各自的 runs，**不涵蓋 B/C 共用 Memory 的競爭**。這不是說該分工不合理，而是這個 queue 的保護範圍沒有跨過去。將 C 改包成專用寫入 job、縮小 queue 範圍，或用 backend precondition，都是後續接線候選；尚未證明它們是無需接合的官方完整 recipe，不能先宣布「框架全包」。尤其不能讓 A 的 Tool 等候排在 A 自己之後、同 thread 的子 run；這會形成互相等待，是由 enqueue 契約推得的接線禁例，不是要求新建 Agent。

**[執行與成本邊界]** 此能力屬 Agent Server／LangSmith Deployment，不是 OSS Checkpointer 開關。官方允許 self-host standalone，故不等於必須用雲端；但目前部署指南列出 Server、PostgreSQL、Redis 與 API／license 配置，不能把它當成零額外部署成本的工具函式。本輪不決定授權、部署或報價。[Server／OSS 區別](https://docs.langchain.com/langsmith/double-texting)、[Self-host prerequisites](https://docs.langchain.com/langsmith/deploy-standalone-server#prerequisites)

Cron 官方同時提供指定 thread 與每次新 thread 兩種形式；「有 cron」不代表自動選中共用修改佇列。其 background-run 示例輸出仍有較早的 `reject` 值，而現行 double-texting 契約明示預設 `enqueue`；研究以現行契約為準，未來接線仍應明寫所選策略，不照抄示例舊快照。[Thread／stateless cron](https://docs.langchain.com/langsmith/cron-jobs)、[現行預設](https://docs.langchain.com/langsmith/double-texting)

**本次收斂：**「可用原生 queue」已查清，但「只讓必要的 C 寫入等待、不影響一般 A、又不增加接合」尚未被所查資料證明。Owner 已回答分工偏好與研究順序（§1）；具體協調留待完整流程確認後，不再重問 B 是不是 Agent、C 是不是 Tool，也不重新蒐集相同 enqueue 文獻。

## 4. 兩種有官方依據的候選，不另造第三套平台

| 候選 | 如何處理同一 Memory | 優點 | 代價與尚未覆蓋 |
|---|---|---|---|
| **序列化方案：修改週期輪流執行** | B 的候選抽取可先做；真正整併的重新讀取、判斷與寫入，與 C 的修改週期輪流執行 | 較少 stale-write 衝突與額外模型重算；可保留主要候選的官方檔案工具 | 所有 writer 必須走同一協調入口。§3.2 查明直接採同 thread enqueue 會讓整個 A 等待；只排 C 的窄接法尚未核准，不能只排 put |
| **前置條件方案：允許並寫，帶儲存端 precondition** | 以讀取時版本／hash 保護寫入；不符就重新讀取並重新判斷 | 不必一開始等待整段背景整併 | 衝突會增加讀取／模型修正成本；主要候選 backend 沒有原生此保證，需另選支援能力或公開 backend 擴充 |

序列化方案學 Codex 的單一背景整併者與 Deep Agents 官方序列化建議；**將相同協調範圍延伸到 B＋C，是本案待審的組合選擇，不是已證明 OpenAI 逐字如此實作。** 前置條件方案有 Anthropic 的實際 API 作法作證；也不是因此要更換模型供應商。版本／hash 若採用，應由讀取工具與 Runtime 傳遞，不先新增要求 LLM 自行產生的欄位。本文 A／B／C 只指前台／背景／修補三條流程，不作新方案編號。

**研究建議的限定：** 先前「建議先選序列化」是目的層的研究建議，未成 Working Decision。經 §3.2 核實後，不能把它直接落成「前台與背景全部共用 conversation thread」。Owner 現在偏好分工、修改時協調，且要求先審整體流程；本表保留作之後的選項比較，不是已採用 CAS、增加 Server 或推翻 Q017。必要自訂接合可以提出，但尚未核准任何具體擴充。

### 序列化方案的可行邊界，不能用「框架會處理」帶過

- 序列化單位是共用的 Memory 修改範圍，不必是全服務；不同 Memory 範圍不需要一起等待。
- C 若排隊前已讀過舊內容，取得修改資格後仍須重讀必要正文、依最新內容決定是否還要改；不能排完隊直接套舊的整檔結果。
- 官方 Agent Server queue 可作候選執行基礎，**前提是所有相關修改都被送往同一協調 thread／入口**。它不是獨立的 Store namespace lock；這個接線及前台等待方式仍需 G4 核對。未授權引入第二套 durable runtime、自製鎖服務或決定實體 queue key。
- 序列化 writer **不自動提供跨多檔讀取快照**。A 的一般讀取仍可能看到 B 的部分完成內容／尚未刷新的 guide；不能宣稱此候選保證讀者永遠只見到完整批次。是否需要更強的發布一致性尚無已核准需求，不先設 staging／全庫交易。

上述窄範圍是候選目標，不是原生 enqueue 已實現的效果。實際直接同 thread 接法會讓新的前台 run 等待 B；若不能接受，須改選接合粒度／前置條件，不把中斷取消假裝成已完成安全交接。

## 5. 失敗後怎麼辦：與上述候選一起審閱

以下是 **[待選組合]**，依官方工具結果、重播與 OpenAI job 收尾規則提出；尚未核准完整錯誤契約。

| 實際狀況 | 建議行為 | 為什麼 |
|---|---|---|
| 參數／路徑／字串匹配錯誤，確定沒寫入 | 原生 Tool result 回模型，有界修正 | 已有框架工具回饋，不另做格式猜測或無限迴圈 |
| 寫入結果不明，例如寫入後連線中斷 | 重讀實際內容，再決定已完成、需補做或需重新判斷 | 不能把沒收到成功當成一定沒寫入；盲目重放新增可能重複 |
| 正文部分已改、guide 或批次收尾失敗 | 不宣稱整批成功；保留可用產物，之後根據目前內容補完／修正 | job 失敗不等於所有 Store 寫入被撤銷 |
| 中斷後其他 writer 已更新 Memory | 恢復時重新讀相關目前內容，不盲用中斷前的讀取結果寫回 | checkpoint 可重播先前結果，但那份讀取可能已過時 |
| writer 仍可能執行 | 先確認停止或失去有效寫入資格，再交接 | Codex 本身也處理關閉不確定時不能立即放下一個 writer 的問題 |

支援上述判斷的官方邊界：[LangGraph 重播與 idempotency](https://docs.langchain.com/oss/python/langgraph/functional-api#idempotency)、[Codex job 收尾](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/src/phase2.rs#L395-L487)、[LangChain 內建 tool retry／call limits](https://docs.langchain.com/oss/python/langchain/middleware/built-in)。

**不建議默認把全部 Memory 倒回背景開始前。** 它可能抹掉已成立的修改，也不能僅依 LangGraph 的 run/checkpoint 回復語意推論外部 Store 自動回滾。本輪傾向「重讀目前內容、向前補完」，不是宣稱任何不完整正文都正確，更不是允許把部分成功記為整批成功。若要求使用者永遠看不到部分產物，那是另一個明確效果要求，不能暗中承諾。

## 6. 本輪結論、停止點與下一步

- **已記錄核准：** Owner 本輪「同意」只承接 Q017 主要框架方向；Q015 根 Agent 不變，Q016 的 LangMem 優先組合改為備選。未核准本文協調策略或施工。
- **已補足證據：** SDK lifecycle／flush 與 Codex Phase 2 lease 是兩套具體機制；StoreBackend 的字串匹配不是 CAS；queue、checkpoint 與 Memory 寫入各有邊界。
- **本輪新增 finding：** §3.2 核實同 thread 多 assistant 會接續 checkpoint、enqueue 排完整 run、同 run 平行 Tool 另有邊界，以及 Server 並非 OSS／零部署成本。這些是會影響接法的差異，不是新的 Memory 功能需求。
- **建議：** 保留 B 背景 Agent／C 主 Agent Tool，不為了取得 enqueue 就直接合併前台與背景對話狀態。序列化仍候選，但具體等待／state／部署代價須先審閱；若只允許 C 短暫等待或重試，才定向核對較窄接法／原生 precondition backend，不先做自訂鎖。
- **Owner 已回答方向：** 優先 A／B 分工、修改 Memory 時協調；真的不可行仍可討論替代方式。框架不足時允許研究必要自訂，但不是核准開發。先前整輪等待問題不再作下一輪 blocking question。
- **最新下一步：** 回 Q017 §3.3，先審主 Agent 一輪，再審背景一次整理及兩者接力；完整流程確認後才回來選具體協調／恢復接法。本文證據與候選保留，機制仍 OPEN；不選預算、超時、鎖 key、schema 或實作，也不把「互不影響」宣稱為零延遲保證。
- **停止重複研究：** 舊 CAS／版本文獻不重新全量蒐集；所查 SDK 路徑不能作全域交易保證、StoreBackend edit 未提供 CAS，已有定位證據。只有新版本契約、具體接線不可行或 Owner 新需求才重開。
- **驗證範圍：** 文件／官方原始碼審閱，沒有新 API 實驗、安裝、spike、production 改動、commit 或 push；不得據此宣稱並行／恢復已實測通過。

## 7. 文件責任與證據快照

[Current register](../current-decisions.md) 保存決策狀態；[Q017](2026-09-05-openai-shaped-memory-framework-composition-research.md) 保存整體接力；本文只保存 B/C 協調與失敗恢復的差異證據、選項及未決取捨。背景補查、artifact／prompt 詳解仍回原研究，不複製成另一份總稿。

定向查閱日期 2026-09-05。固定源碼：OpenAI Agents JS `e6c3663017e3e36af67370a4bc09db674ef0fd9f`；Codex `574a36ff99f0807a24f5b043f593122bf151908d`；Deep Agents `4e5f9350e4d77b8bf19e472e8414662d3fa59dc0`。固定 SHA 是證據快照，不代表三者已通過相容性實測；SDK Sandbox／Deep Agents Beta 狀態不被寫成 stable。
