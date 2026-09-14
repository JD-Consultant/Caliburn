# LangChain／LangGraph／Deep Agents／LangMem 官方記憶流程事實圖

> 日期：2026-09-05
>
> Topic：LLM-Q014 研究前置
>
> 狀態：**Research only；不構成選型、產品設計、ADR 或 production 施工授權**
>
> 目的：先還原框架官方真正提供的完整流程，再另行判斷如何承接已研究的 OpenAI 記憶流程。本文刻意不做 Caliburn 映射。
>
> 後續更精確的能力邊界見[通用流程審核](2026-09-05-generic-memory-flow-framework-crosswalk-audit.md)：
> LangMem manager 不包含外部按需深讀；Deep Agents 可只固定注入 guide，其他檔案按需讀取；
> 多筆 Store writes 不是原子交易。以下「原生」只指所列 primitive，不保證整條 pipeline。
>
> 原文／摘要的最新固定 source 複核見[小元件資料流](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md)：已修正 Deep Agents state replacement 誤讀、DB history 與 model context 混淆，以及漏列 LangMem short-term summary。細節以該子稿為準，不只看「summary／canonical」名稱。

## 0. 研究邊界與證據規則

本文只回答四件事：

1. 每個框架原生負責什麼；
2. 哪些行為會自動發生，哪些只是可組裝的 primitive；
3. 各框架之間如何銜接；
4. 與 OpenAI 已公開流程相比，哪些責任完整、部分或尚未覆蓋。

本文不決定：正式框架組合、Memory schema、Tool 名稱、Prompt、資料 namespace、Caliburn JD 流程或任何 migration。

證據標籤：

- **[官方契約]**：目前官方文件明確承諾的行為。
- **[官方原始碼]**：目前 upstream `main` 原始碼可直接驗證的行為；仍可能隨版本改變。
- **[專案風險]**：upstream issue 或版本狀態，只能證明需要驗證，不能當作框架永遠如此。
- **[比較結論]**：由前述證據做的責任對照，不冒充框架官方說法。
- **[未知]**：公開資料沒有保證，不能自行補故事。

## 1. 版本快照

### 1.1 研究與選型基準：研究當日最新公開版本

| 套件 | 2026-09-05 最新公開版 | 成熟度訊號 |
|---|---:|---|
| LangChain | 1.4.0 | PyPI：Production/Stable |
| LangGraph | 1.2.11 | PyPI：Production/Stable |
| Deep Agents | 0.7.13 | PyPI：Beta |
| LangMem | 0.0.30（2025-10-27） | pre-1.0；相較其餘套件已久未發版 |

來源：[LangChain PyPI](https://pypi.org/project/langchain/)、[LangGraph PyPI](https://pypi.org/project/langgraph/)、[Deep Agents PyPI](https://pypi.org/project/deepagents/)、[LangMem PyPI](https://pypi.org/project/langmem/)。

本文直接以這組最新公開版本與對應官方文件判斷功能；不因 Caliburn 現行套件較舊而放棄可升級取得的能力。若最新元件仍是 Beta／pre-1.0，保留成熟度與相容性風險，但不把舊 pin 當作設計上限。

### 1.2 Caliburn 現行版本只作 migration inventory

`apps/api/pyproject.toml` 目前是 `langchain==1.3.15`、`langgraph==1.2.11`、
`deepagents==0.7.5`，且尚未安裝 `langmem`。這只表示日後施工需要升級／新增依賴；
進入 implementation gate 時，應重新確認當日最新版本並鎖定可重現組合，再做 PostgreSQL 與
middleware behavior compatibility test。

## 2. 官方整體分工

```text
Deep Agents：預組的 agent harness
    ↓ 建立於
LangChain create_agent：model ↔ tool 迴圈、middleware、structured output
    ↓ 執行於
LangGraph：graph runtime、checkpoint、Store、interrupt／resume

LangMem：可選的 Memory 抽取、修訂、搜尋與延遲處理元件
    ↓ 使用
LangGraph Store ＋ LLM structured extraction
```

這四者不是四套互斥 agent：

- LangGraph 是低階 runtime 與 persistence；
- LangChain 提供較高階 agent loop 與 middleware；
- Deep Agents 是建立在 LangChain／LangGraph 上的 opinionated harness；
- LangMem 是另外一組語意 Memory primitives，並非 Deep Agents 的必要內核。

官方定位來源：[LangChain agents](https://docs.langchain.com/oss/python/langchain/agents)、[LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview)、[Deep Agents customization](https://docs.langchain.com/oss/python/deepagents/customization)、[LangMem overview](https://langchain-ai.github.io/langmem/)。

## 3. LangGraph：執行與持久化層

### 3.1 官方原生流程

```text
invoke(thread_id, input)
    ↓
Graph node／model／tool 執行
    ↓ 每一個 super-step
Checkpointer 保存該 thread 的 graph-state checkpoint
    ↓
同 thread 可繼續、失敗恢復、time travel、interrupt／resume

Graph node／application code
    ↕
Store：namespace + key + application-defined JSON
    └─ 可選 exact／metadata／semantic search
```

**[官方契約]** Checkpointer 保存單一 thread 的 graph state snapshots，用於 conversation continuity、human-in-the-loop、time travel 與 fault tolerance。Store 保存 graph state 外的 application-defined key-value data，用於長期資料。兩者可以同時使用。[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)

**[官方契約]** Store 不會自動知道什麼值得記、如何去重或如何修訂；官方範例由 node／application code 自行搜尋與寫入。[LangGraph memory](https://docs.langchain.com/oss/python/langgraph/add-memory)

**[官方契約]** `interrupt()` 會保存狀態並等待 resume；恢復時使用同一 `thread_id`，而且包含 interrupt 的 node 會由開頭重跑，因此 interrupt 前的 side effect 必須可重入或放到其他 node。[LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)

### 3.2 自動做與不會自動做

| 能力 | LangGraph |
|---|---|
| 保存 thread state／對話 continuity | 原生；需 persistent checkpointer 才能跨 process restart |
| graph 失敗恢復與中斷續跑 | 原生 |
| 保存長期 JSON Memory | Store primitive |
| 向量／語意搜尋 | Store 配置後可用 |
| 判斷什麼值得記 | 不提供政策 |
| 抽取／去重／修訂 Memory | 不提供 pipeline |
| 自動建立 Memory 導覽 | 不提供 |
| 自動把久遠原話變成可深讀 artifact | 不提供 |

## 4. LangChain：model／tool loop 與每次呼叫的 Context

### 4.1 官方原生流程

```text
input + graph state + runtime context + Store
    ↓ middleware 組裝本次 model context
model call
    ├─ final response → 結束
    ├─ structured response → 驗證／回傳
    └─ tool calls → 執行 tools → ToolMessage → 回到 model
```

**[官方契約]** `create_agent` 提供 model-to-tool loop；middleware 可在 model、tool 與 agent lifecycle 前後介入，動態調整 prompt、messages、tools、model 與 structured output。[LangChain agents](https://docs.langchain.com/oss/python/langchain/agents)、[Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)、[Middleware](https://docs.langchain.com/oss/python/langchain/middleware/overview)

**[官方契約]** Structured output 在 provider 原生支援時可使用 `ProviderStrategy`，否則使用 tool calling；官方將 provider-native 稱為最可靠方式，但這只負責輸出契約，不等於 Memory 品質或流程。[Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)

### 4.2 一般 SummarizationMiddleware

**[官方契約]** `SummarizationMiddleware` 在 token／message／context fraction 門檻達成後，用另一個模型摘要舊訊息並保留指定數量的近期訊息。若不設 trigger，不會自動觸發。[Prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in#summarization)

固定 source 的 `before_model` 回傳 RemoveMessage＋summary＋recent，會更新目前 graph state；但**不等於刪除資料庫全部歷史**。普通 PostgresSaver 保留舊 snapshots；是否能作完整原文 reader 仍需接存取／保留契約。分層、SQL 與來源見[底層追蹤 §1–3](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#1-必須分清三種替換)。

### 4.3 OpenAI provider 專用能力

**[官方契約]** `ChatOpenAI` 可傳 `previous_response_id` 延續 Responses API 狀態；從計費角度等價於重新傳入先前訊息，不能宣稱它本身節省 input token 成本。[ChatOpenAI conversation state](https://docs.langchain.com/oss/python/integrations/chat/openai#managing-conversation-state)

**[官方契約]** `ChatOpenAI(context_management=[{"type": "compaction", ...}])` 可使用 OpenAI Responses API server-side compaction。回傳的 compaction blocks 必須保留在後續歷史；先前訊息可保留，或為降低 latency 丟棄。[ChatOpenAI context management](https://docs.langchain.com/oss/python/integrations/chat/openai#context-management)

這是 OpenAI provider 能力，不是 LangChain 對所有 provider 的共同保證。

### 4.4 定向補核：動態 Store 讀取與背景執行邊界

官方 Context engineering 提供 Store-aware `@dynamic_prompt`：經 `request.runtime.store.get` 讀取資料再組 prompt；custom middleware 分別提供 invocation 級 `before_agent` 與 model-call 級 hooks。這是可用的公開動態載入接法，不代表框架會自行產生 Memory 導覽。[Store-aware prompt](https://docs.langchain.com/oss/python/langchain/context-engineering#system-prompt)、[Hooks](https://docs.langchain.com/oss/python/langchain/middleware/custom#hooks)

LangGraph Functional API 可保存 task 結果並在恢復時重用；entrypoint 會重播，未完成 task 可能再執行，寫入仍須可重入。Agent Server 另有背景 queue；其 `enqueue` 是同一 thread 的 run 排隊，不是共用 Store namespace 的寫入鎖。不能把上述能力合稱「任意多筆 Memory writes 自動 exactly-once／原子回滾」。[Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api#idempotency)、[Agent Server](https://docs.langchain.com/langsmith/agent-server#task-queue)、[Enqueue](https://docs.langchain.com/langsmith/enqueue-concurrent)

## 5. Deep Agents：預組 harness 與長任務 Context 管理

### 5.1 官方預組 middleware stack

**[官方契約]** `create_deep_agent` 不是單純替 `create_agent` 換一個名稱；它會以固定順序預組 middleware，最後回傳 compiled LangGraph。只傳入 model 時，bare stack 通常已包含：

```text
FilesystemMiddleware
→ SubAgentMiddleware（一般用途 subagent 預設加入時）
→ SummarizationMiddleware
→ PatchToolCallsMiddleware
→ provider prompt-caching middleware（不支援的 model 會 no-op）
→ harness profile extras／excluded-tool filtering（有設定時）
```

完整 stack 還可依參數加入 Skills、async subagents、自訂 middleware、Memory 與 Human-in-the-loop；自訂 middleware 會依名稱取代既有 entry，或插入指定位置，而不是自動與預設設定合併。[Deep Agents customization](https://docs.langchain.com/oss/python/deepagents/customization#deep-agents-stack)

因此 Deep Agents 的「完整」是預組 harness 的完整，不代表它原生包含 OpenAI 式 extraction／consolidation artifacts。是否需要 filesystem、預設 subagent、prompt caching 等整組能力，屬後續選型問題，本文不先判斷。

### 5.2 啟動 Context

**[官方契約]** Deep Agents 的完整 system prompt 由 custom prompt、base prompt、Memory、Skills、filesystem、subagent、custom middleware 與 HITL prompts 組成。[Deep Agents context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering#complete-system-prompt)

- `memory=` 指定的 `AGENTS.md` 會始終注入 system prompt，沒有 progressive disclosure；官方要求保持精簡。
- `skills=` 只先載入 frontmatter，匹配任務後才讀完整 Skill。
- 未排除的 built-in tools 仍會在每輪傳送完整 schema；可用 harness profile 的 `excluded_tools` 移除完全不需要的工具。

**[2026-09-05 原始碼補核：導覽載入不等於自動刷新]** `MemoryMiddleware` 會完整載入設定的 `sources`，不是自行產生索引。其 `before_agent`／`abefore_agent` 在 state 已有 `memory_contents` 時直接跳過讀取；`wrap_model_call` 使用該 state 內容注入。因此不能僅憑此 middleware，保證背景改檔後已執行中的 agent／攜帶該 state 的後續執行會立即取得新導覽。是否重建 invocation state、重新讀檔或採其他官方 lifecycle 接法，仍須核對使用它的外層；本事實不等於框架一定出現 stale bug。[固定快照 memory.py：載入](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/memory.py#L279-L345)、[注入](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/memory.py#L347-L361)

### 5.3 內建 Context compression

```text
大型 tool input/output
    → offload 到 backend/file
    → working context 只留路徑與 preview

Context 接近上限
    → LLM 產生 structured conversation summary
    → model request 以 summary + recent messages 繼續
    → 正常摘要只保存摘要事件，不清除 state.messages
    → 該段歷史 rendering 另存 backend，供搜尋／深讀
```

**[官方契約]** 每個 `create_deep_agent` 都包含 context compression。預設大型 tool payload 超過 20,000 tokens 會 offload；摘要通常在模型 input window 約 85% 觸發、保留約 10% recent tokens。發生標準 `ContextOverflowError` 時會立即摘要後重試。另可選擇加入 `compact_conversation` tool 主動觸發同一引擎。[Deep Agents context compression](https://docs.langchain.com/oss/python/deepagents/context-engineering#context-compression)

**固定 source 更正：**不能把 history rendering 稱為無損 canonical 保證，也不能說 Deep Agents 只剩摘要 state。正常摘要採 request override＋event；overflow 的 ToolMessage eviction 另可能寫回縮短內容，archive 失敗仍可能摘要。完整 trace、固定原始碼與失敗測試見[底層追蹤 §3.2](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#32-deep-agents-summarizationmiddleware修正前輪誤讀)。它仍不是 OpenAI 的 opaque compaction artifact。

### 5.4 長期 Memory

**[官方契約]** Deep Agents 的長期 Memory 是 filesystem-backed files；可透過 `StoreBackend` 跨 thread 持久化。Agent 預設可在 hot path 使用 `edit_file` 更新。Skills／政策也可設為 read-only。[Deep Agents memory](https://docs.langchain.com/oss/python/deepagents/memory)

**[2026-09-05 工具契約補核]** `read_file` 支援有界分段讀取，backend 回報讀取錯誤時產生 `ToolMessage(status="error")`；`edit_file` 的模型參數是 path、要匹配的舊文字、新文字與可選 replace-all，backend 的失敗／成功同樣回成 ToolMessage。這提供模型取得實際結果後繼續處理的材料，不保證模型必定修復成功，也不涵蓋所有未捕捉的基礎設施例外。[官方工具參數與實作](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/filesystem.py#L1193-L1205)、[read 結果](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/filesystem.py#L1885-L1927)、[edit 結果](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/filesystem.py#L2157-L2252)

**[公開政策擴充邊界]** `create_deep_agent` 有公開 `permissions`；獨立 filesystem middleware 的 `_permissions` 是 private。官方另提供 BackendProtocol subclass／wrapper 的 policy hook 接法，因此可以研究公開 adapter，不必直接依賴私有參數；但示例只示範 write／edit，不能當作 delete／upload／async 也已受控。[Permissions](https://docs.langchain.com/oss/python/deepagents/permissions)、[Policy hooks](https://docs.langchain.com/oss/python/deepagents/backends#add-policy-hooks)

**[更細的公開能力]** standalone FilesystemMiddleware 另有 `tools=[...]` allowlist，排除的工具不進可分派清單；這是工具層，不取代同一 edit Tool 的不同 path 權限。StoreBackend 在固定快照沒有 `delete` 實作，Composite 的 delete 可回「子 backend 不支援」，不能概括所有 backend 原生全 CRUD。[allowlist 註冊](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/filesystem.py#L1668-L1792)、[可選 delete 契約](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/protocol.py#L722-L752)、[Composite 結果](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/composite.py#L778-L807)

### 5.5 Background consolidation 的真實範圍

```text
cron
    → 呼叫另一個 consolidation deep agent
    → 該 agent 使用自訂 tool 搜尋最近 threads
    → 讀取 conversation history
    → 依自訂 prompt 編輯 Memory files
```

**[官方契約]** 官方文件把 background consolidation 寫成「部署另一個 deep agent＋自訂 conversation-search tool＋cron」的推薦 pattern。主 agent 不會僅因啟用 Deep Agents 就自動得到這條 pipeline。官方亦說多數應用 hot path 已足夠；背景方式適合降低前台 latency 或跨多 conversation 綜合。[Deep Agents background consolidation](https://docs.langchain.com/oss/python/deepagents/memory#background-consolidation)

官方特別警告 cron cadence 與 lookback window 不同步會造成重複處理或漏掉 conversation。這表示排程、watermark／lookback 與 idempotency 仍是 application/deployment 責任。

## 6. LangMem：Memory formation primitives

### 6.1 `create_memory_manager`

```text
messages + optional existing memories
    → LLM／Trustcall structured extraction
    → create／update／delete decisions
    → 回傳 ExtractedMemory(id, content)
```

**[官方原始碼]** 預設 Memory 只有一個 `content: str`，要求形成可獨立理解的 memory。`create_thread_extractor` 是另一個獨立 primitive，預設輸出 `title + summary`。[LangMem extraction source](https://github.com/langchain-ai/langmem/blob/main/src/langmem/knowledge/extraction.py)

`create_memory_manager` 本身回傳結果，不持有 Store 寫入步驟；會寫 Store 的是下面的 `create_memory_store_manager`。因此不能只依函式 docstring 中「automatically persisted」的字句，把兩者視為同一件事。

### 6.2 `create_memory_store_manager`

```text
conversation messages
    ↓
從 Store 搜尋少量相關既有 Memory（預設總上限 5）
    ↓
Memory manager 對「訊息＋這批既有 Memory」抽取／修訂
    ↓
可選 phases 依序再精煉同一批候選
    ↓
所有 phase 完成後，才集中 put／delete 到 Store
```

**[官方契約＋原始碼]** 有 `query_model` 時，模型產生一至多個搜尋 query；沒有時，使用 conversation 的 dilated windows 搜尋。只取 `query_limit` 內的相關既有記憶，預設 5。[Memory API](https://langchain-ai.github.io/langmem/reference/memory/#create_memory_store_manager)、[官方原始碼](https://github.com/langchain-ai/langmem/blob/main/src/langmem/knowledge/extraction.py)

**關鍵非等價：** LangMem `phases` 是對同一批 in-memory candidates 做連續精煉，並在最後一起寫 Store；它不會自動產生並耐久保存 OpenAI Phase 1 的「conversation summary＋raw memory extract」，再讓 Phase 2 讀取這些 artifact。名稱相似，責任不同。

### 6.3 Hot-path tools

`create_manage_memory_tool` 的 model-facing schema 是：

```text
content?: string
id?: string
action: create | update | delete
```

建立時由工具 runtime 產生 UUID key；更新或刪除要求提供 ID。固定版本使用 `uuid.UUID` 型別；update 實際直接 `put/aput`，沒有先 get 驗證目標存在，因此「要求 ID」不等於「已驗證既有 ID」。[固定 tools 原始碼](https://github.com/langchain-ai/langmem/blob/f8c7ebd6110c124a36995dab645a8cb0eb0b8210/src/langmem/knowledge/tools.py#L271-L337)

`create_search_memory_tool` 的 schema 是：

```text
query: string
limit: int = 10
offset: int = 0
filter?: object
```

它把 BaseStore search results 序列化回模型，也可另外把原始 items 當 artifact 回給 runtime。[LangMem tools API](https://langchain-ai.github.io/langmem/reference/tools/)、[官方 tools 原始碼](https://github.com/langchain-ai/langmem/blob/main/src/langmem/knowledge/tools.py)

**[後續定向複核]** 上述工具可交給 Agent 在執行途中使用；§6.2 manager 不會中途外讀，不代表 LangMem 整包不提供這項工具能力。官方 [hot-path quickstart](https://langchain-ai.github.io/langmem/hot_path_quickstart/) 仍使用舊 `create_react_agent`；新組合應依 [v1 migration](https://docs.langchain.com/oss/python/migrate/langgraph-v1) 核對 `create_agent`，不能只照抄舊範例。元件組合與缺口比較見[審核稿 §8](2026-09-05-generic-memory-flow-framework-crosswalk-audit.md#8-owner-同意後先固定能力再比較兩種工具組合)，本輪未做新版本執行相容性測試。

精確 reader 並非 Store 的能力缺口：LangChain 官方工具範例已使用 `ToolRuntime`＋`runtime.store.get`。但將它接成 summary reader 的 locator／missing-result 契約，仍不是 LangMem search／manage 自動生成的功能。[官方工具範例](https://docs.langchain.com/oss/python/langchain/tools#long-term-memory-store)

### 6.4 Delayed processing／ReflectionExecutor

**[官方原始碼]** Local executor 以 thread 為單位 debounce：同 thread 新 submit 會取消尚未執行的舊任務，再依 `after_seconds` 排程最新 payload。它是 process 內 worker thread，不是耐久 queue。Remote executor 則委派 Agent Server run，使用 `multitask_strategy="rollback"`。[Delayed processing](https://langchain-ai.github.io/langmem/guides/delayed_processing/)、[ReflectionExecutor source](https://github.com/langchain-ai/langmem/blob/main/src/langmem/reflection.py)

因此，它解決的是「短時間多次訊息造成重複 reflection」；不等於 OpenAI Phase 1／2 artifact pipeline，也不能把 local executor 當成 process restart 後仍保證執行的 background job。

### 6.5 目前相容性風險

**[專案風險]** upstream 仍有兩個 open issues：

- hot-path `create_manage_memory_tool` 寫入的 `{"content": ...}`，與 store manager 寫入／讀取的 `{"kind": ..., "content": ...}` 形狀不一致：[issue #138](https://github.com/langchain-ai/langmem/issues/138)；
- 有使用者回報 search tool 無法從 Postgres Store 取回 store manager 寫入的紀錄：[issue #140](https://github.com/langchain-ai/langmem/issues/140)。

原始碼可確認兩條路徑的 value shape 確實不同；issue 則只能證明「存在待驗證風險」，不能直接推論所有 backend 都必然失敗。正式使用前必須用選定版本與 Postgres Store 做 compatibility test，不能宣稱無縫互通。

### 6.6 Short-term summary：先前漏列的公開小元件

`summarize_messages/asummarize_messages` 接收 messages 與可選 RunningSummary，回傳有界模型輸入及新 summary state；不自行存 Store／刪 checkpoint。`SummarizationNode` 包裝它，預設 input=`messages`、output=`summarized_messages`，將兩者分開；刻意設為同 key 才要求 reducer 移除舊列表。是官方公開 API，不必為了拆開原文與模型視圖就自行發明摘要演算法。來源與版本／相容性邊界見[底層追蹤 §3.3](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#33-langmem-的小型公開元件原事實圖漏列)、[LangMem short-term API](https://langchain-ai.github.io/langmem/reference/short_term/)。

## 7. 對照 OpenAI 已公開責任形狀

本節的 OpenAI 基準不是自行抽象出來的框架需求。OpenAI 官方把 conversational Session、Responses compaction 與跨 run Memory 分開；Sandbox Agents 的 Memory 又明確分成 progressive read，以及 conversation extraction／layout consolidation 兩階段 generation。詳細流程與證據見 [`2026-09-05-openai-conversation-context-and-memory-system-map.md`](2026-09-05-openai-conversation-context-and-memory-system-map.md)；原始官方來源列於 §11。[OpenAI conversation state](https://developers.openai.com/api/docs/guides/conversation-state)、[OpenAI compaction](https://developers.openai.com/api/docs/guides/compaction)、[OpenAI Agents SDK Memory](https://openai.github.io/openai-agents-js/guides/sandbox-agents/memory/)

標記：**原生**＝框架直接承擔；**部分**＝只覆蓋部分語意；**Primitive**＝提供材料但需組裝；**缺少**＝公開能力沒有承擔。

| OpenAI 責任 | LangGraph | LangChain | Deep Agents | LangMem |
|---|---|---|---|---|
| Conversation／session continuity | 原生 Checkpointer | 透過 LangGraph | 原生使用 graph state | 缺少 |
| 長 Context 壓縮 | Primitive | 一般摘要；OpenAI provider 可用 server compaction | request-view 摘要＋event／history rendering；有例外路徑 | 公開 summary 函式／node，預設分離 input/output |
| 小型 Memory 導覽 | Store primitive | 可由 middleware 注入 | `memory=` 可始終注入，但不會自動重建 | 缺少 |
| 相關 Memory 搜尋 | Store exact／semantic primitive | Tool／middleware 組裝 | filesystem search／自訂 retrieval | 原生 search tool／store manager search |
| Conversation extraction artifact | 缺少 | Structured-output primitive | 缺少 | thread extractor 與 memory manager 分開存在 |
| 跨時間 consolidation | 缺少 | Agent primitive | 官方 recipe：另一 agent＋cron | 原生 manager，但預設只對 top-k 相關 Memory |
| 同輪 live repair | Store write primitive | Tool loop primitive | `edit_file` primitive | manage tool 可 update by ID |
| 久遠完整 Memory 深讀 | Store get/search primitive | Tool 組裝 | filesystem read/search | Store/search primitive |
| 原始對話回查 | current/history state reader | Tool 組裝 | state／歷史 rendering／offload 檔案；逐路徑核對 | 不提供獨立原文 reader |
| 全量 Memory inventory | Store pagination primitive | Tool／workflow 組裝 | filesystem list/read primitive | manager 預設 top-k；不等於全量 |
| Durable background scheduling | Agent Server／deployment primitive | 缺少 | cron recipe | remote executor 可委派 Agent Server；local 不耐久 |

## 8. 必須避免的錯誤等同

1. **Checkpointer ≠ semantic Memory。** 前者保存 thread graph state；後者需要 application-defined Store data 與形成政策。
2. **Store ≠ Memory manager。** Store 能存取、搜尋資料，但不判斷應保存什麼、如何去重或修訂。
3. **LangMem phases ≠ OpenAI Phase 1／Phase 2。** 前者是候選記憶的連續 refinement；後者有不同耐久中間 artifact 與生命週期。
4. **Deep Agents background consolidation ≠ 內建自動 pipeline。** 它是官方提供的 architecture recipe。
5. **Deep Agents `memory=` 不自動產生整條 progressive 流程。** 但只指定小 guide，搭配 filesystem read/search，即可組成 Memory progressive retrieval；不只有 Skills 能按需讀。
6. **一般 LLM 摘要 ≠ OpenAI provider compaction。** 兩者都有縮短 Context 的效果，但資料契約與恢復機制不同。
7. **LangMem StoreManager ≠ 全量 consolidation。** 預設只先搜尋最多 5 筆相關既有 Memory。
8. **有 CRUD tool ≠ 有正確 live repair policy。** 何時判斷過時、應更新哪一筆與後續動作是否可依賴更新結果，框架沒有自動保證。

## 9. 本輪可下的事實結論

1. 本文核對的 LangChain／LangGraph／Deep Agents／LangMem 元件沒有單一開關原生完整複製 OpenAI 已公開的全流程；此結論不涵蓋所有框架，更不能忽略 OpenAI Sandbox SDK 自身的 Memory capability。
2. LangGraph、LangChain、Deep Agents、LangMem 提供的是不同層級、可組裝但不完全重疊的責任。
3. Deep Agents 在 provider-neutral 長 Context 管理上提供目前四者中最完整的現成 harness；但其 Memory 永遠注入與 background recipe 不等於 OpenAI 的 progressive disclosure pipeline。
4. LangMem 是四者中最接近「抽取＋修訂＋搜尋 Memory」的元件，但目前是 pre-1.0、發版較舊，且 hot/background 路徑存在需實測的契約風險，不能直接視為成熟無縫 replacement。
5. 目前只完成「官方能力事實圖」，**尚未選框架，也尚未判斷哪些 OpenAI 責任需完整承接、功能等價承接或暫緩**。

## 10. 下一階段才允許回答的問題

下一階段應逐責任做 gap analysis，而不是直接開始寫 code：

1. Conversation／Compaction：採 OpenAI provider-native compaction、Deep Agents provider-neutral preservation，或哪一種明確 fallback？
2. Harness：需要完整 Deep Agents，還是 LangChain＋LangGraph 的較薄組合即可？
3. Memory formation：LangMem StoreManager 的功能等價是否足夠，還是需要明確保留 extraction artifact／conversation summary？
4. Progressive disclosure：小型導覽、搜尋、完整 Memory 與原始對話回查，哪些框架 primitive 可直接承接？
5. Live repair：使用 LangMem tool、filesystem edit，或由 workflow 管理；如何保證後續 effect 只依賴成功修訂？
6. Background：使用 durable Agent Server／job，還是第一版只採可驗證的 hot path？

以上問題未經逐項研究與 owner 討論前，不得由本文推導 production 架構。

## 11. 主要來源

### OpenAI 官方基準

- [OpenAI conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- [OpenAI compaction](https://developers.openai.com/api/docs/guides/compaction)
- [OpenAI Sandbox Agents](https://developers.openai.com/api/docs/guides/agents/sandboxes)
- [OpenAI Agents SDK：Agent memory](https://openai.github.io/openai-agents-js/guides/sandbox-agents/memory/)
- [OpenAI Agents SDK：Sandbox Agents concepts](https://openai.github.io/openai-agents-js/guides/sandbox-agents/concepts/)

### LangGraph／LangChain／Deep Agents

- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph memory](https://docs.langchain.com/oss/python/langgraph/add-memory)
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangChain agents](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)
- [LangChain prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [ChatOpenAI integration](https://docs.langchain.com/oss/python/integrations/chat/openai)
- [Deep Agents context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering)
- [Deep Agents memory](https://docs.langchain.com/oss/python/deepagents/memory)

### LangMem

- [LangMem conceptual guide](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)
- [LangMem Memory API](https://langchain-ai.github.io/langmem/reference/memory/)
- [LangMem tools API](https://langchain-ai.github.io/langmem/reference/tools/)
- [LangMem background quickstart](https://langchain-ai.github.io/langmem/background_quickstart/)
- [LangMem delayed processing](https://langchain-ai.github.io/langmem/guides/delayed_processing/)
- [LangMem extraction source](https://github.com/langchain-ai/langmem/blob/main/src/langmem/knowledge/extraction.py)
- [LangMem tools source](https://github.com/langchain-ai/langmem/blob/main/src/langmem/knowledge/tools.py)
- [LangMem reflection source](https://github.com/langchain-ai/langmem/blob/main/src/langmem/reflection.py)
