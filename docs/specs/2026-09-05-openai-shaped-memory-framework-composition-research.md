# OpenAI-shaped Memory：框架接力、可重用能力與剩餘接合

> 2026-09-05 · `LLM-Q017` · **G3 Owner 暫時同意主要框架組合方向；未授權施工**。
>
> 本輪目的：以公開框架能力承接已研究的 OpenAI A／B／C 流程，保留每層存在的理由；不套入 Caliburn JD、舊元件或領域 schema。
>
> 本文保存已同意的整體候選；依 Owner 最新指示，先按 §3.3 審閱主 Agent、背景 Agent 與整體接力，再決定 [Q018：B/C 寫入協調與恢復](2026-09-05-memory-background-live-repair-coordination-research.md)。該協調機制尚未核准。查歷史判斷讀[審核稿 §8](2026-09-05-generic-memory-flow-framework-crosswalk-audit.md#8-owner-同意後先固定能力再比較兩種工具組合)。狀態只以 [current register](../current-decisions.md) 為準。

## 1. 這輪完成什麼、沒有改什麼

**最新 gate：**Owner 要求深入底層再設計；[原生 backend 接法審閱](2026-09-05-memory-artifact-native-backend-design-review.md)已提出②的待審建議，依據是實際 producer／路由／Store／ToolMessage 呼叫鏈，不是只看名字。①／③的舊優先建議已撤回；三者仍未選型。原文／Compaction、背景生命週期及 Q018 保留後續接線 gate，不重問摘要保存用途。

**研究結論：有可具體組裝的路徑，不需要自己重寫 Agent loop、檔案讀寫引擎或 Memory 資料庫；但沒有一個框架開關原生完成全部 OpenAI 生命週期。**

Owner 本輪「同意」後，主要設計候選採 `create_agent`＋LangGraph＋獨立 Deep Agents filesystem／StoreBackend 元件；LangMem 紀錄工具保留備選，不因 manager 的限制而排除整個 LangMem。**Q015 根 Agent 不變；Q016 的 LangMem 優先組合改由本輪接續為備選。** 這是可翻案的方向核准，不是品質／成本最佳的實證、最終 artifact contract 或施工授權。

本輪補足前輪留下的三類接法：導覽如何讀到更新、獨立 filesystem 元件的公開權限擴充、紀錄型方案如何提供精確 reader。另核實背景恢復與寫入協調的框架邊界。沒有安裝套件、執行 spike、呼叫付費模型或修改 production。

## 2. 必須保留的不是檔名，而是分工與理由

| OpenAI 公開責任 | 必須保留的目的 | 不能錯誤替換成 |
|---|---|---|
| Conversation／原始 rollout | 保存實際互動，必要時能回查，而非把整理後的內容冒充原話 | 只有一份會持續改寫的摘要 |
| Compaction continuation | 在 context 壓力下延續當前工作；不是建立長期知識庫 | 永久刪掉原始訪談，或濃縮掉所有 Memory 正文 |
| Phase 1 extraction | 隔離一段互動的整理成果，減少後續反覆重讀所有歷史 | 每回合把全部歷史重新整併一次 |
| `raw_memory`＋rollout summary | 前者提供候選知識；後者保留可補查的互動脈絡。兩者都是整理產物 | 把 `raw_memory` 當逐字 transcript，或只保存候選而沒有補查材料 |
| Phase 2 consolidation | 對照既有 Memory 去重、補充、修訂；需要時補查 summary | 起始搜尋 top-k 後，無論缺什麼都只能看這批資料 |
| `MEMORY.md`／小型 guide | 可搜尋的知識與導覽分工；先用便宜入口定位，再讀詳細內容 | 每次固定注入全部正文；或把 guide 當唯一真實資料 |
| Live repair | 當前 run 發現明確過時內容時，就地修補所需 Memory | 為改一處而同步重跑整個背景流程 |

本表是對既有[OpenAI 系統圖](2026-09-05-openai-conversation-context-and-memory-system-map.md)與[artifact 詳表](2026-09-05-openai-memory-artifacts-to-framework-detailed-crosswalk.md)的用途核對，不另發明資料類型。OpenAI SDK 的 generation／liveUpdate 與 Codex 公開 pipeline 並非每個細節相同；這裡保留共同責任，差異仍在原研究中。[SDK Memory](https://openai.github.io/openai-agents-js/guides/sandbox-agents/memory/)、[Codex pipeline 固定 README](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/README.md)

**背景補查的邊界已確認，不重開：** SDK Phase 2 可按需開 conversation summaries；所核對 Codex 背景 prompt 明確禁止打開 raw sessions／original transcripts。因此前台必要時回查原話，與背景整併補查摘要，是不同的資料可見範圍。[SDK Phase 2](https://openai.github.io/openai-agents-js/guides/sandbox-agents/memory/#generate-memory)、[Codex raw 邊界](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/consolidation.md#L159-L167)

## 3. 建議如何接成完整流程

以下全屬 **[組合建議]**，不是宣稱框架已提供同名 turnkey pipeline。

```text
A 前台
新訊息 → Conversation／run continuity
       → 有界 continuation＋最新小型導覽
       → create_agent：需要時搜尋 Memory、讀正文／summary、再回查原始互動
       → 回答／工具結果

B 背景
已選定的互動片段 → Phase 1：產生 summary＋候選知識
                 → 保存這批中間產物
                 → Phase 2 create_agent：讀既有 Memory
                      ↔ 搜尋／深讀相關 summary
                      ↔ 修改 Memory，讀取工具結果，必要時修正
                 → 整理小型導覽 → 回報這批處理結果

C 同輪修補
A 發現明確過時 Memory → 讀取目標正文 → 同一個前台 Agent 局部修改
                     → 看工具結果，成功後才把它當已寫入
                     → 同段互動仍可在之後進 B，B 對照屆時的 Memory
```

圖中箭頭表示資料接力，不代表每格呼叫一次 LLM；B 不是每次使用者訊息都跑，C 不是另開一個完整背景 Agent。A 的自動少量召回是先前暫定策略；本圖不把它說成 Codex 必定每輪做的行為。

### 3.1 每段用什麼官方能力

| 責任 | 可重用元件 | 仍需明確組裝／選擇 |
|---|---|---|
| Conversation／run continuity | LangGraph persistent Checkpointer | 保存的 canonical messages 與壓縮後 model view 需分清；Checkpointer 只保存實際交給 state 的資料 |
| 有界 continuation | 既有 Compaction 候選：provider compaction 或 Deep Agents preservation／transient view | 此輪不選引擎；一般摘要本身不保證另存完整原話 |
| 注入最新小型 guide | LangChain `dynamic_prompt`／`wrap_model_call`，可讀 Runtime Store／backend | 指定來源、缺內容時怎麼表示；不能假設 `MemoryMiddleware` 會自動刷新 |
| 搜尋、深讀、局部編輯 | 獨立 `FilesystemMiddleware`＋`StoreBackend` | 把正文、guide、summary 真正保存成可定位內容，並給各角色適當讀寫範圍 |
| Phase 1 雙產物 | LangChain structured output＋LangGraph workflow task/node＋Store／backend | extraction instructions 與輸出角色；`rollout_slug` 只是可讀命名提示，不拿它冒充可信 identity |
| Phase 2 整併途中補查 | 另一個背景 `create_agent`，重用相同官方 filesystem 工具 | 整併 instructions、候選與 summary 的可見範圍；不是再包一層自製 model/tool while-loop |
| Guide 形成／更新 | 同一套寫入／局部編輯工具 | 由整理 Agent 在正文處理後維護；middleware 負責載入，不負責生成 |
| C live repair | 前台 Agent 使用同一 Memory backend 的官方 edit 工具 | 何時應修補是 instructions／模型判斷；同步寫入協調仍待下一層設計 |
| 耐久背景執行 | LangGraph checkpointed tasks／graph；Agent Server 有 queue／run 能力 | 任務何時觸發、何時重試、B/C writer 協調不是 Checkpointer 自動完成 |

來源：[LangChain agents](https://docs.langchain.com/oss/python/langchain/agents)、[Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)、[Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)、[FilesystemMiddleware 獨立接法](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/filesystem.py#L1641-L1721)、[StoreBackend](https://docs.langchain.com/oss/python/deepagents/backends#storebackend-langgraph-store)、[Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api)。Compaction 保留[既有候選研究](2026-09-05-conversation-compaction-framework-gap-review.md)，不在本輪偷選。

StoreBackend 是「Store 內的虛擬檔案」，不是要求開放電腦檔案系統或 shell。`grep` 是內容文字搜尋，不是向量搜尋；若後續需要語意召回，須另外使用已公開的 Store semantic search／retrieval 能力並核對索引欄位，不能只改工具名稱便宣稱支援。

### 3.2 為什麼沒有強迫每層都使用 LangMem manager？

LangMem manager 的抽取／更新能力有價值，但不會自動提供 Phase 1 雙產物及 Phase 2 中途開 summary 的完整生命週期。若選 Agent＋filesystem，模型整理由官方 Agent loop 完成，**不需要為了湊元件再固定呼叫一次 manager**。若選紀錄型方案，LangMem search／manage tools 可直接交給 Agent；這與「把 store manager 當整條背景流程」不同。[框架事實圖 §6](2026-09-05-langchain-langgraph-deepagents-langmem-official-memory-flow-map.md#6-langmemmemory-formation-primitives)、[LangMem tools](https://langchain-ai.github.io/langmem/reference/tools/)

**適用範圍澄清（Owner 追問，2026-09-05）：不是「LangMem 不適合」，而是不能把一個 manager 等同整條 OpenAI 流程。** 官方明列 background formation 與 Agent hot-path tools；`create_thread_extractor` 可用自訂 schema 抽取中間內容，`create_memory_manager` 可修訂傳入紀錄，`create_memory_store_manager` 再串接搜尋及 Store 寫入。這些仍可重用，不因主要候選採 filesystem 便整包排除。[LangMem 官方分工](https://langchain-ai.github.io/langmem/)、[Memory API](https://langchain-ai.github.io/langmem/reference/memory/)

本輪重新讀取官方 `extraction.py`：StoreManager 在整理前搜尋，後續 `phases` 傳遞既有工作集及本次產物；沒有自帶「整理途中決定再開另一份 rollout summary」的 reader loop，也沒有自動保存獨立 summary／raw candidates、重建 guide 的整套接力。**這是該內建流程的邊界，不是 LangMem 資料不能保存細節或不能擴充。** `query_limit=5` 是可調預設，不能當成只能讀五筆；提供自訂 schema 也不等於已自動完成產物保存與讀取流程。[官方實作](https://github.com/langchain-ai/langmem/blob/main/src/langmem/knowledge/extraction.py)（2026-09-05 定向讀取 `MemoryManager.ainvoke`、`MemoryStoreManager.ainvoke` 與 factory；固定證據入口見 §7）

若採紀錄型組合，可用 Agent loop＋LangMem search／manage tools，再接 summary reader、產物保存與 guide 更新；filesystem 候選同樣需要產物／guide／排程接線。**現有判斷是互動流程對應程度，不是 LangMem 效果較差的實證，也不是兩條組合不能共用抽取元件。** 是否重用 extractor／manager 由後續逐項資料契約判斷，沒有在本輪新增同步 manager、重選整套框架或授權施工。

### 3.3 Owner 最新方向：先確認分工與完整接力，再補協調機制

**[Owner Working direction，2026-09-05；不是新增官方事實]** 優先讓主 Agent A 與背景 Agent B 各自運作，不因 B 整理便一律阻塞前台；C 仍是 A 按需使用的 Memory Tool。兩者共用 Memory，修改時需要協調，但「互不影響」不表示資料互不往來，也不保證零等待／零資源競爭。若維持此分工確實不可行或代價不合理，允許提出替代方式再討論；不是已同意整輪排隊。

框架若無法覆蓋實際需要的協調能力，**可以研究必要的自訂擴充**，但須先完成下列流程討論，再提出缺口、官方依據、替代方案、效果、延遲／成本與維護代價，經 Owner 審閱才採用。不因「可自訂」便先寫鎖、queue、版本平台或額外 Agent；也不能為堅持零自訂而扭曲分工。

接下來沿用 §2–3 與原始研究，按順序補齊，不把已確認內容重新變成選項：

1. **主 Agent 的一輪：** 輸入、Context 組裝、按需搜尋／深讀、Tool 結果回模型、正常完成；釐清何時需要 C、何時僅讀取／回答。
2. **背景 Agent 的一次整理：** 何時觸發、這次接收哪段互動、extraction 產物、consolidation 補查／修改、guide 與完成／失敗的交付；不先寫死排程間隔或模型次數。
3. **兩條路徑接力：** B 尚未完成時 A 依靠哪些已可用資料；C 改完之後 B 如何再次讀取與整理；完成結果何時供後續 A 使用。先確定讀寫位置與依賴，再決定需要協調哪段。
4. **框架接線與缺口：** 逐段區分可直接使用、須組合公開元件、仍需擴充；此時才回 Q018 比較具體協調與恢復方案。

**第 1 項 §3.4 與第 2 項 §3.5 的 B 流程均已由 Owner 暫時同意。** 下一步依 §3.6 已同意順序展開資料細節；不把方向同意當成 schema／存取契約全數核准。已核准的 A／B／C 用途、背景補查與 artifact 分工不從零研究；只對真正未決、矛盾或缺少直接證據的細節補查。原始官方引用仍由 §2、§3.1 與[官方流程事實圖](2026-09-05-langchain-langgraph-deepagents-langmem-official-memory-flow-map.md)承接，不重複複製成另一份總稿。本節不授權 implementation／spike。

### 3.4 主 Agent A 的一輪：資料如何進來、被讀取與完成

**狀態：G4 流程經 Owner「同意」，2026-09-05；沿用 Q004／Q005／Q014 已核准用途，不新增 Agent，不授權施工。** 此同意承接本節的 A 一輪與下列邊界；明列未選定的接法仍未決，不自動核准 B 或 Q018。本節屬框架組合說明；官方事實與尚未選定的接法分開如下。

#### 正常流程

1. **接收新訊息，延續同一 conversation。** 本則訊息啟動一次 logical invocation；A 讀取此 conversation 的既有狀態。員工、AI 與必要 Tool 互動由 canonical conversation 保存，不靠背景 B 才能記得上一句。LangGraph Checkpointer 保存實際 graph state，不自行替應用補出未曾保存的歷史；完整保存／有界 model view 是既有需求，不是套上 Checkpointer 就自動達標。[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[OpenAI Session 與 Memory 分工](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)
2. **組裝本次模型可見的 Context。** 精簡規則、適用工具、近期對話／Compaction continuation、小型 Memory 導覽及本輪訊息，搭配 Q014 已暫准的少量相關召回。不是注入全部 Memory；本輪訊息若已在 messages，不因畫成另一格就再貼一份。LangChain 可用 transient model-context override 而不改已保存 state；Compaction 引擎仍依既有候選待選。導覽載入沿用 §4.1 的公開 model hook 接法，不等於每次另叫 LLM 生成導覽。[Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)、[既有 Compaction 候選](2026-09-05-conversation-compaction-framework-gap-review.md)
3. **同一主 Agent 判斷需要什麼。** 已足夠就回答；缺 Memory 就先搜尋，再讀相關正文；需要互動脈絡才開 summary，需要精確原始內容才回查 conversation。每一層滿足本輪資訊需要即可停止，不必逐層讀到底。OpenAI SDK 明確提供 guide → 搜尋 Memory → 按需 summary；raw fallback／停止提示屬已核對的 Codex 開源 read prompt，不誇大成所有 OpenAI 產品的固定契約。[OpenAI Memory read](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)、[既有 read-path 細節與原始碼路由](2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md#4-讀取每一步到底發生什麼)
4. **Tool 執行後，實際結果回到同一 Agent。** 讀到的內容、成功或可交由模型處理的錯誤，隨對應 Tool call 回傳；A 據此決定繼續讀取、修正參數、採取下一步或回答。這是 `create_agent` 的 model↔Tool loop，不另造 while-loop。一次 invocation 可以有多次模型呼叫；不是每個流程名詞都多叫一次模型。需繼續推理的 Memory read／repair 不適合 `return_direct=True`，因該設定會跳過模型對結果的後續處理。[OpenAI tool calling flow](https://developers.openai.com/api/docs/guides/function-calling#the-tool-calling-flow)、[LangChain tool returns](https://docs.langchain.com/oss/python/langchain/tools#return-directly-from-a-tool)
5. **需要 C 時，在上述 loop 中修補；否則不修改 Memory。** 仍沿用已准條件：已讀完整目標、修正對象清楚、內容明確過時、同輪後續需要新版。A 使用 edit Tool 局部修補，讀取結果後才可說已成功寫入；未釐清的矛盾先問使用者，不自行選一方覆寫。這不是固定每回合 extraction，也不是 C 另叫 B。格式／匹配等可修正錯誤回模型；基礎設施失敗、重試與上限依 Q005／§4.5 分流，不保證每次修復成功。[OpenAI live memory updates](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)、[Deep Agents memory](https://docs.langchain.com/oss/python/deepagents/memory)、[工具結果的已核對實作](2026-09-05-langchain-langgraph-deepagents-langmem-official-memory-flow-map.md#54-長期-memory)
6. **完成當輪回答，保留對話及實際執行狀態。** 提問也是一次正常回答，使用者下一則訊息另開 invocation；不把所有問句做成 durable interrupt。A 不為了等 B 整理完才一律結束，這是 Owner 已選的分工偏好，不是框架已保證零阻塞。哪些 conversation 片段、何時交給 B，下一節流程審閱才決定；本節不新增「每輪結尾必跑 manager／必等待 B」規則。[LangChain Agent loop](https://docs.langchain.com/oss/python/langchain/agents)、[有效 Q004–Q006／Q017–Q018](../current-decisions.md#4-llmagent-working-baseline)

#### 本輪核對的三個易錯細節

- **保存 ≠ 進入模型 Context。** 本輪剛取得的 Tool 結果經 loop 回模型；背景在 Store 寫好內容，則需後續 hook／Tool 讀取並送入模型才會被看到。已送出的模型 request 不會因 Store 更新而被追溯改寫。前兩句有官方 context／Tool 契約；最後一句是由 request 邊界得出的工程判斷，不冒充 OpenAI Memory 的額外協調保證。[Transient／persistent context](https://docs.langchain.com/oss/python/langchain/context-engineering#transient-context)、[Tool result flow](https://developers.openai.com/api/docs/guides/function-calling#the-tool-calling-flow)
- **載入 ≠ 生成，也 ≠ 每 step 重搜。** `before_agent` 每 invocation 一次，`wrap_model_call` 每模型呼叫執行；model hook 讀取小 guide 是 I/O，不增加一次摘要模型呼叫。Q014 的少量自動召回仍有效，但搜尋何時重做、budget 與方式未定；不能把「每次模型看到少量相關資料」誤實作成「每個 Tool step 都另跑 retrieval model」。OpenAI 公開 read path 是按需搜尋，不證明固定每輪自動召回。[Hooks](https://docs.langchain.com/oss/python/langchain/middleware/custom#hooks)、[Store-aware prompt](https://docs.langchain.com/oss/python/langchain/context-engineering#system-prompt)
- **A 的 C 結果 ≠ B 整批已完成。** C 只確認本次 Tool 的實際結果；沒有代表 summaries、導覽與全部 Memory 都已同步更新。B/C 交錯、導覽與正文一致性、失敗恢復留到 §3.3 第 3–4 項，不在 A 流程中暗加全局鎖或全部刷新。

#### 審閱結果與下一個 gate

方向與已准分工一致；本輪無需再選第三個 Agent、固定雙模型或同步 manager。**但這是可組裝流程，不是全部接線已完成。** 精確 Compaction、auto-recall 觸發／成本、canonical raw reader、artifact 權限、B/C 協調仍沿用原待決路由；不以「官方有 primitive」當成無缺口。

本節新增的是正常一輪的接力說明與官方 tool-result／hook 邊界核實，沒有新增 production schema。Owner 已同意，**接續只看 B 的一次背景整理**，再看 A/B/C 接力，最後才回 Q018。若新官方事實或 Owner 回饋改變此流程，局部重開本節，不重做整份 Memory 研究。

### 3.5 背景 Agent B 的一次整理：獨立子稿路由

詳見 [B 背景一次整理審閱稿](2026-09-05-memory-background-cycle-flow-review.md)，同屬 Q017 G4，**流程已由 Owner 暫時同意**。分清觸發與對話範圍、extraction 的摘要／候選、consolidation 按需補查、導覽與實際完成／失敗結果；保留官方 SDK、Codex 與框架觸發差異，不照抄固定排程數字。

本輪沒有選 executor、具體鎖／CAS、最終 schema 或原始資料 retention；沒有將 B 的兩階段誤寫成每輪兩次固定模型呼叫。子稿不複製完整 Memory 研究，原始細節仍回讀 §7 所列證據文件。B 確認後先審 A/B/C 交接，再回 Q018。

### 3.6 資料細節應何時討論：已同意順序與完整範圍

**[Owner Working approved，2026-09-05]** Owner 同意在 A/B/C 接力階段深入對話／Memory／中間產物的保存、讀取與搜尋；並要求以既有 OpenAI 完整研究補齊未口頭列出的項目，不只研究這次點名的資料。順序如下；不是核准各項最終 schema、儲存格式或施工，也不先跳去選鎖。

**Owner 後續澄清：OpenAI 各項代表什麼、如何保存／找回，既有深入研究已說明；現在不是重開這些概念，而是決定它們對應框架的什麼。** 以下每項從既有用途直接開始，輸出「框架資料／元件 → 寫入 API／自動行為 → 讀取／搜尋 API → 缺口與需組合部分」，再串後續框架流程。只有官方版本差異或尚缺證據才補查 OpenAI；不再把名詞解釋列成 Owner 的下一個決策題。Conversation 首批對照見 [既有 gap review §8](2026-09-05-conversation-compaction-framework-gap-review.md#8-q017-對話資料的框架存取對照)。

**Owner 再次收斂研究層次：首要找更小元件與公開開發接點，追「輸入資料→處理→回傳→reducer→實際保存」，不是只列高階名稱。** 「只改 LLM Context」「改目前 state」「刪 DB 歷史」分開；查清原文 reader 可否共用後，才判斷需要擴充什麼。OpenAI 不重查，除非既有證據確有缺口。本輪固定 source 發現 Deep Agents 正常摘要沒有清除 state.messages、LangMem 有公開短期摘要元件；更正及三層證據集中於[小元件資料流](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md)，不因此另建原文副本或先換 Compaction 引擎。

1. **Conversation 與模型可見上下文**：對應 `AgentState.messages`、thread／checkpointer、state 讀取 API 與 compaction／archive 元件，核對完整問答片段的取得方式；不是重新定義原始歷史用途。
2. **Extraction 中間產物**：對應 structured extraction、產物保存 backend、locator／來源引用、讀取工具及 B 的輸入選取；沿用已研究的 summary／候選分工。原始三方案見[接力子稿](2026-09-05-memory-extraction-artifact-framework-handoff-review.md)，最新底層查證與②待審建議見[原生 backend 審閱](2026-09-05-memory-artifact-native-backend-design-review.md)。不把 checkpointed result 或 ToolMessage.artifact 誤當可搜尋產物庫；①／③仍備選，沒有選型或施工核准。
3. **可修訂 Memory**：對應檔案／紀錄表示、search／read／edit API、合法修改目標及框架結果／錯誤，核對過長／未命中處理。
4. **小型導覽與 Context 注入**：對應導覽保存／更新與 model hook，核對刷新、實際模型輸入及去除不必要重複的接法；不是重問導覽存在理由。
5. **回看 A/B/C 整體交接，再進 Q018**：在已知讀寫單位與可見時點後，討論並行修改、部分成功、排程與恢復；最後形成實作計畫。

每項都沿用「既有已准效果 → 原官方／框架資料 → 尚未收斂的契約」；至少回答內容與保存者、讀寫者、查找與回傳、錯誤／成本及可驗證例子。**先講資料與行為契約，具體欄位／SDK 接法在同項後段收斂**，不是先發明 schema 再找框架來套。可由官方契約回答的技術問題不交給 Owner 猜；影響目的、資料保留、成本或複雜度的取捨才請 Owner 決定。

既有材料已有 [artifact 詳表 §4–6、§10.2](2026-09-05-openai-memory-artifacts-to-framework-detailed-crosswalk.md) 與 [框架事實圖](2026-09-05-langchain-langgraph-deepagents-langmem-official-memory-flow-map.md)。其中舊 LangMem 優先與 record ID 接法須以 Q017 現行候選判讀，不直接復活。只補缺少或有版本差異的官方證據；不重做整份研究、不為每輪再開一份總稿。本順序依[既有 decision-process G4](../decision-process.md)的先資料流後細節原則提出，不宣稱是 OpenAI 內部逐項流程。

**完整範圍的檢查入口，不是新增資料表清單：**

| 依既有研究逐項核對 | 本段要回答的核心問題 |
|---|---|
| Conversation、SDK Session、sandbox session、run／rollout、raw rollout | 哪些是同一互動的不同抽象或身分，哪些是實際保存資料；如何累積與回查，避免憑名稱重複存對話 |
| Compaction continuation | 與原始歷史的關係、模型拿到什麼、如何找回未在 Context 內的內容 |
| `rollout_summary`、`raw_memory`、`rollout_slug`、來源／runtime metadata | 摘要、可重用候選、路由標籤各自的內容、產生者、保存與讀取者；`raw_memory` 不當成 raw transcript |
| Phase 2 的選取紀錄、`raw_memories.md`、summary 集合及 workspace diff | B 這次整理哪些輸入、如何增量接續及按需補查；區分 SDK 檔案與 Codex DB bookkeeping，不混成共同必填契約 |
| `MEMORY.md`、`memory_summary.md`、supporting references、選擇性 `skills/` | 正文、導覽、佐證與程序知識如何接力；何時讀／改、誰重建、哪些只是可選產物 |

各項的細節、來源與 SDK／Codex 差異維持在 artifact 詳表，不在本段重複展開。OpenAI Sandbox 公開文件也分開 Session history 與持久 Memory，並列出 raw sessions／抽取產物／正文／guide 的 layout；**不能因此推論每個名詞都要一份獨立副本、Tool 或 Agent**。[官方 Sandbox Memory](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)

## 4. 本輪深入核實的接合問題

### 4.1 Guide 更新後，模型如何看到？

**[官方事實]** 固定版本 `MemoryMiddleware` 在 state 已有 `memory_contents` 時跳過重新載入。官方測試也直接驗證此條件；這只證明 reload 條件，不等於所有跨 process／checkpoint 恢復都一定保留舊快取。[載入原始碼](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/memory.py#L279-L345)、[條件測試](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/tests/unit_tests/middleware/test_memory_middleware.py#L337-L353)

**[公開接法]** LangChain 官方有 Store-aware `@dynamic_prompt` 範例，在模型 Context 組裝時讀 `request.runtime.store.get`。`before_agent` 是每 invocation 的 hook，`wrap_model_call` 是模型呼叫的 hook，兩者不可混稱。[Store-aware prompt](https://docs.langchain.com/oss/python/langchain/context-engineering#system-prompt)、[Hooks](https://docs.langchain.com/oss/python/langchain/middleware/custom#hooks)

**[建議]** 候選先用 model hook 讀取小型導覽，不另造版本快取引擎。紀錄型讀 Store item；虛擬檔案型經 backend 讀內容，不能錯把 StoreBackend 內部 JSON 當純文字。這只是 I/O＋Context 注入，不是每次重新呼叫 LLM 摘要。仍須承認：讀後若發生另一筆寫入，不等於本次 Context 有跨寫入的快照一致性；錯誤時也不能假裝已讀最新內容。

### 4.2 Summary 可讀但不能改，Memory 可改，怎麼限制？

**[官方事實]** 完整 `create_deep_agent` 提供公開 `permissions` 參數；獨立 filesystem middleware 的 `_permissions` 是 private。不能為保持 Q015 的根 Agent 而直接依賴私有參數。[公開 permissions](https://docs.langchain.com/oss/python/deepagents/permissions)、[獨立 middleware 簽名](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/filesystem.py#L1641-L1721)

**[公開接法]** 官方 backend 文件另提供 subclass／wrapper 的 policy hooks，回傳 framework-native `WriteResult(error=...)`／`EditResult(error=...)`。因此可以維持 `create_agent` 根，經 BackendProtocol 擴充讀寫政策；不用發明另一套檔案引擎。[Policy hooks](https://docs.langchain.com/oss/python/deepagents/backends#add-policy-hooks)

**[限制]** 這仍有 adapter code，不是零自訂。官方示例只示範 write／edit，不能直接宣稱已涵蓋 delete、upload 與 async 路徑；要按實際暴露的工具逐項核對。namespace／目錄名字本身也不是存取控制。本輪只確認公開擴充路徑，未選定 policy class、目錄名或安全契約。

**[接續補核]** standalone middleware 已有公開 `tools` allowlist，可直接不註冊不需要的工具；但 A/C、B2 混合讀寫目錄仍需 path policy。原生 StoreBackend 也不支援所有 backend 的全部操作，不能按名稱宣稱全 CRUD。實際註冊／資料流與接法集中在[原生 backend 審閱 §1／§3.2](2026-09-05-memory-artifact-native-backend-design-review.md)，不再重寫工具或分頁引擎。

### 4.3 紀錄型方案真的缺 reader 嗎？

不是 Store 不能精確讀，而是 LangMem search／manage 工具沒有自動成為 rollout summary reader。LangChain 官方 `ToolRuntime` 工具範例直接使用 `runtime.store.get(namespace, key)`，能作精確 reader 的標準接法；locator 與作用域如何交付仍是組合契約。[Tools：long-term memory](https://docs.langchain.com/oss/python/langchain/tools#long-term-memory-store)

另有一個**名稱容易誤判的邊界**：LangMem manage 的 update 要求 UUID，但實作直接 `put/aput`，沒有先 `get` 檢查該 ID 是否存在；create 才禁止模型自填 ID 並由 runtime 產生。因此不能把它描述成「工具已驗證目標存在、且只可能修改既有紀錄」。這是所讀版本的契約邊界，不是已證實的產品 bug，也不據此自行加 guard。[固定 tools 原始碼](https://github.com/langchain-ai/langmem/blob/f8c7ebd6110c124a36995dab645a8cb0eb0b8210/src/langmem/knowledge/tools.py#L271-L337)

### 4.4 背景與 C 都會更新同份 Memory，框架是否已解決？

**[官方事實]** Codex 所讀 pipeline 在 Phase 2 接觸 Memory root 前取得 global consolidation job claim，並以成功處理狀態追蹤輸入；有「避免多個背景整併互相干擾」的明確做法。但不能由此宣稱所有前台 live repair 也自動受同一把鎖保護。[Codex Phase 2 lifecycle](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/README.md)

**[框架事實]** Deep Agents 官方提醒同檔並行寫入可能 last-write-wins。Agent Server 的 enqueue 是同 `thread_id` 的 run 排隊；兩個 thread 指向同 Store namespace，不因此取得 namespace 級互斥。[Concurrent writes](https://docs.langchain.com/oss/python/deepagents/memory#concurrent-writes)、[Enqueue](https://docs.langchain.com/langsmith/enqueue-concurrent)

**[待設計，不偷裁決]** 必須避免 B 讀舊內容後蓋回 C 的新修補；選哪種官方支援的執行／寫入協調方式，是下一層問題。這不要求現在建 CAS、整批發布系統或自製鎖，也不能當作「全部框架已無縫接好」。

### 4.5 按需補查會不會沒有上限、失敗就重跑全部？

官方已有 `ModelCallLimitMiddleware`／`ToolCallLimitMiddleware` 控制 run 或 thread 用量；run limit 與長期 thread limit 不同。框架也提供 tool/model retry，但重試哪種錯誤仍需設定，不能假設所有錯誤都會成功。這些是可用零件，不另造迴圈引擎。[內建 middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-call-limit)

LangGraph Functional API 的 task 能恢復已完成結果；恢復 entrypoint 會重播，未完成 task 可能再執行。因此持久化可重試的寫入仍需可重入，不能宣稱 checkpoint 提供 Store 多筆寫入 exactly-once／原子回滾。Agent Server 提供背景 queue／workers；單獨本機 checkpointer 不是排程器。[Functional API：idempotency](https://docs.langchain.com/oss/python/langgraph/functional-api#idempotency)、[Agent Server queue](https://docs.langchain.com/langsmith/agent-server#task-queue)

## 5. 兩個候選怎麼選：現在可以下的判斷

| 面向 | Agent＋filesystem／StoreBackend | Agent＋LangMem 紀錄 tools／Store |
|---|---|---|
| 貼近 OpenAI 補查與局部編輯流程 | 目錄、文字搜尋、分段深讀、文字替換已有一組官方工具 | search／manage 已有；summary 精確 reader 使用官方 ToolRuntime＋Store.get 擴充 |
| 修改錯誤形狀 | 字串匹配／路徑錯誤；不是 AST 或語意 merge | ID／內容替換；update 不自動檢查目標存在 |
| 自訂部分 | artifact 形成／安排、guide hook、backend policy／生命週期接合 | 同類生命週期工作，另有 summary reader 與需核對的 record shape |
| 成本不能忽略 | 多步讀取／修補會增加 model steps；grep 不等於 semantic recall | semantic search 配置可能有 embedding 成本；整筆 replacement 也消耗內容 token |
| 成熟度 | 根 LangChain／LangGraph stable；所用 Deep Agents 元件仍 Beta | LangMem pre-1.0，且最新公開 release 較舊；不能把名稱當成熟度保證 |

**建議：下一步以 filesystem 組合作為主要設計候選，紀錄工具保留作對照。** 理由是此輪目標明確包含「補查、深讀、局部修訂」的完整接力，官方檔案元件對這些互動提供較直接的能力；不是因為 Markdown 必然效果最好，也不是 Codex 用檔案所以一定照抄。

版本快照沿用已核對的[框架事實圖 §1](2026-09-05-langchain-langgraph-deepagents-langmem-official-memory-flow-map.md#1-版本快照)：LangChain 1.4.0、LangGraph 1.2.11、Deep Agents 0.7.13、LangMem 0.0.30；固定原始碼證據不等同已實測這四個 release 的組合。進施工前才需鎖相容版本。本輪不以 Beta 當 stable，不宣稱檔案組合已通過品質或成本測試。

## 6. 審核結論與下一步

- **方向未偏移：** A 延續上下文／按需讀取；B 形成與整併長期 Memory；C 同輪修補。Conversation、summary、候選、正文、guide 的目的沒有被同名框架元件偷換。
- **已補齊：** 可公開使用的 guide hook、backend policy 擴充、record reader；框架足以作為流程骨架，不需要再次從「Memory 是什麼」開始研究。
- **仍需組合設計：** artifact 可見範圍、背景 job 生命週期、B/C 共用寫入協調、導覽／正文部分成功如何恢復；都標成待決，不冒充 OpenAI 共識或框架自動保證。
- **已完成的 gate：** Owner 暫時同意主要組合方向、A／B 流程及資料細節研究順序，並已理解摘要引用／按需深讀。**最新 gate 是[原生 backend 接法審閱](2026-09-05-memory-artifact-native-backend-design-review.md)**，不是重問保存用途。本稿曾殘留的③優先描述已撤回；最新研究建議②、仍待 Owner 選型。原文、ToolErrorMiddleware 與 Q018 證據沿用子稿。Compaction、背景 executor／恢復、B/C 協調仍未定，不因完整圖已畫出就施工。
- **停止重複研究：** 官方已明證「背景可補查 summary」，不再重問；已存在的完整 OpenAI／框架事實只連結回讀。新增查證只針對會改變候選的差異。
- **重開條件：** Owner 改變目的、官方公開契約／版本改變，或後續最小相容性驗證推翻本輪可組合判斷。

## 7. 證據定位與文件分層

本文旁附原始引用；以下是深入查證的路由，不複製完整研究：

1. [OpenAI 系統圖](2026-09-05-openai-conversation-context-and-memory-system-map.md)：公開 OpenAI 機制、版本差異與未知。
2. [Artifact 詳表](2026-09-05-openai-memory-artifacts-to-framework-detailed-crosswalk.md)：Session／rollout／raw_memory／summary／slug 等逐項責任。
3. [框架官方事實圖](2026-09-05-langchain-langgraph-deepagents-langmem-official-memory-flow-map.md)：官方元件，非本輪選型。
4. [通用審核](2026-09-05-generic-memory-flow-framework-crosswalk-audit.md)：F01–F07、Q017 中途補查與歷史判斷。
5. 本文：把已證實的能力接成候選，明列接合與剩餘風險。

原始碼快照：OpenAI Codex `574a36ff99f0807a24f5b043f593122bf151908d`；Deep Agents `4e5f9350e4d77b8bf19e472e8414662d3fa59dc0`；LangMem `f8c7ebd6110c124a36995dab645a8cb0eb0b8210`。官方 docs 為 2026-09-05 定向查閱；查不到的保證不推測。本輪沒有把各家共同目的誇大成唯一、百分之百正確或最佳實作。
