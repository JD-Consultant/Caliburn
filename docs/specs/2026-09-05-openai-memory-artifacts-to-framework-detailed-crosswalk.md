# OpenAI Memory artifacts 對最新框架的逐項實作交叉表

> 日期：2026-09-05
> Topic：`LLM-Q017`
> 狀態：**G2 已複核修正；方案調整待 Owner 討論；不授權 production 施工**
>
> 後續先讀 [通用流程審核 F01–F07](2026-09-05-generic-memory-flow-framework-crosswalk-audit.md)。
> 下表保留 artifact 詳解，但 LangMem consolidation 的等價程度、Deep Agents 元件級候選、
> rollout 粒度與批次寫入保證已校正；不能再把「只剩薄接線」當成審核通過結論。

## 0. Preflight

```text
Topic ID:
  LLM-Q017
Current stage:
  G2 official evidence：逐一核實 OpenAI artifact 與 framework primitive 的真實等價性。
Binding decisions:
  LLM-Q015：最新 stable LangChain create_agent 作唯一根 Harness；
  LLM-Q016：Owner 暫時核准 stable create_agent＋LangGraph durable substrate＋
  LangMem primitives＋按責任選用 Deep Agents 元件的組合方向；
  現行 production 仍受 Accepted ADR 0060 約束。
This turn's only blocking question:
  是否暫時核准本文的逐 artifact 判定，作為下一輪 Compaction、background durability、
  Store contract 與 compatibility spike 的設計輸入？
Already reviewed evidence:
  OpenAI Conversation／Compaction／Sandbox Agents Memory 官方文件；
  OpenAI Codex 當前 main 的 memories README、Stage 1／Phase 2／read-path prompts 與 state model；
  LangChain／LangGraph／Deep Agents／LangMem 官方文件、API reference 與必要原始碼。
Out of scope / parking lot:
  不在本稿決定 production schema、namespace、CAS、背景排程產品、Compaction 引擎、
  JD mutation、UI、provider／model、migration、實作、merge、push 或 PR。
```

本稿只回答一個問題：**OpenAI 已公開的每一個 Memory 元件與中間 artifact，最新框架究竟能否
直接承接；若不能，差在哪裡、還剩下哪些責任。** 不因名稱相似就判成等價，也不要求
Caliburn 照抄 OpenAI 的 Markdown 檔名或 Git 工作區。

## 1. 來源與版本邊界

### 1.1 兩個 OpenAI 公開實作不能混成一套檔案契約

本稿同時研究兩個官方表面，但會分開標示：

1. **OpenAI Agents SDK Sandbox Memory（Beta）**：公開的是 workspace layout、Session 與
   Memory 的分工、progressive read，以及 conversation extraction／layout consolidation。
2. **OpenAI Codex CLI 當前 `main`**：公開的是較完整的 production-like orchestration，包含
   state DB、rollout job claim、lease／backoff、Stage 1 output、Phase 2 selection、Git baseline、
   workspace diff、consolidation sub-agent 與 read telemetry。

Sandbox 官方目前列出的預設目錄為：

```text
workspace/
├─ sessions/<rollout-id>.jsonl
└─ memories/
   ├─ memory_summary.md
   ├─ MEMORY.md
   ├─ raw_memories.md
   ├─ phase_two_selection.json
   ├─ raw_memories/<rollout-id>.md
   ├─ rollout_summaries/<rollout-id>_<slug>.md
   └─ skills/
```

**2026-09-05 定向校正：**本輪重新取得的 [Sandbox 官方頁](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)
明列 `phase_two_selection.json` 及上述逐檔 layout；先前「公開頁沒有」的說法不再適用。
這是 SDK 公開 layout，不能移植為 Codex CLI 的實作事實。既有固定 Codex 快照把實際選取基準記在
state DB 的 `selected_for_phase2`／`selected_for_phase2_source_updated_at`，另產生
`phase2_workspace_diff.md`；不因此改判 Codex 使用同名 JSON。兩者都不替 Caliburn 核准檔名或 schema。

主要來源：[OpenAI Agents SDK Memory](https://openai.github.io/openai-agents-js/guides/sandbox-agents/memory/)、
[Codex memories README](https://github.com/openai/codex/blob/main/codex-rs/memories/README.md)、
[Codex Stage 1 prompt](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/stage_one_system.md)、
[Codex consolidation prompt](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/consolidation.md)。

### 1.2 框架版本

| 套件 | 2026-09-05 最新公開版 | 成熟度 | 本稿只採用的角色 |
|---|---:|---|---|
| LangChain | 1.4.0 | Stable | `create_agent`、middleware、model／Tool loop |
| LangGraph | 1.2.11 | Stable | thread Checkpointer、Store、graph、durable run substrate |
| Deep Agents | 0.7.13 | Beta | Skills、filesystem backend、context compression 等可選元件 |
| LangMem | 0.0.30 | pre-1.0 | extraction／consolidation／search／manage primitives |

來源：[LangChain](https://pypi.org/project/langchain/)、
[LangGraph](https://pypi.org/project/langgraph/)、
[Deep Agents](https://pypi.org/project/deepagents/)、
[LangMem](https://pypi.org/project/langmem/)。現行 repo pin 只在未來 migration gate 作 inventory，
不能限制本次選型。

## 2. 判定語言

| 標記 | 意義 |
|---|---|
| **Direct** | 官方 primitive 的輸入、輸出、生命週期與責任大致相同，可直接使用 |
| **Close** | 提供相近效果，但資料語意或生命週期不同，必須明示差異 |
| **Compose** | 多個官方 primitive 可以組成，不需重寫底層演算法 |
| **Gap** | 本輪核對的元件未內建該責任；可能可組合，工作量與替代元件仍須確認，不預設很薄 |
| **Physical-only** | 只對應 OpenAI 的實體檔案形狀；可用別的持久表示達到相同效果 |
| **Do not copy** | OpenAI 為自身 CLI／workspace 採用的機制，不是 Caliburn 必須照抄的語意 |

只有輸入、輸出、觸發時機、authority 與失敗語意相符，才可標 **Direct**。

## 3. OpenAI 的完整資料流

### 3.1 即時讀取 A

這是逐層取資料的概念圖，不是每輪必經的固定呼叫鏈。Sandbox SDK 公開說明是在 run 開始注入導覽；Codex 的具體 read prompt／停止指引見[摘要路由 §3](2026-09-05-memory-summary-routing-and-deep-read-source-review.md#3-讀取端每次多讀一層都有明確依據)。不由下圖推論每個 model step 都重貼導覽或讀到 raw。

```text
Conversation／Session append items
  → token 壓力時維持有界 continuation／Compaction
  → 取得小型 memory_summary.md 導覽
      ├─ 當前資料足夠：正常工作
      └─ 需要過去知識：搜尋 MEMORY.md 並讀命中區段
          ├─ 足夠：正常工作
          └─ 缺當時脈絡：沿引用選讀相關 rollout summary
              ├─ 足夠：正常工作
              └─ 仍需精確證據：才沿定位讀 raw rollout／conversation
```

`raw_memory` 是 B 的候選輸入，不是 A 的必經閱讀層；後兩層通常是依引用選讀，不是重新全庫搜尋。1～2 份摘要是既有 Codex quick-pass 指引，非跨產品硬限制；這裡不改 B／C 的不同權限。

### 3.2 背景形成 B

```text
eligible、已閒置 rollout
  → Phase 1 extraction
      ├─ rollout_summary
      ├─ rollout_slug
      └─ raw_memory
  → Stage 1 record 存 state DB
  → Phase 2 選取一批 Stage 1 records
  → 同步 raw_memories.md＋rollout_summaries/
  → 產生 phase2_workspace_diff.md
  → consolidation sub-agent
      ├─ 更新 MEMORY.md
      ├─ 可選更新 skills/
      └─ 最後重建 memory_summary.md
```

### 3.3 執行中修補 C

```text
main agent 讀到一筆明確過時的 MEMORY.md 內容
  → liveUpdate 在同一 run 修補該內容
  → 後續推理使用修補後內容
  → 該 conversation 之後仍可進正常 Phase 1／Phase 2
```

三條路互補：A 保持當前對話連續；B 低頻整理跨段知識；C 只處理同輪已確定過時且需要
立即修正的 Memory。C 不是拿 B 全跑一次。

## 4. OpenAI artifact 的精確語意

### 4.1 Conversation／SDK Session

- **Conversation** 保存實際 message、Tool call、Tool result 等 items；是執行歷史與連續對話。
- **SDK Session** 是跨多次 `run(...)` 維持同一 conversation 的 client-side abstraction。
- Sandbox Memory 的 conversation identity 依序採 `conversationId`、SDK Session ID、`groupId`，
  都沒有時才產生 per-run ID。
- 它們不是 `MEMORY.md`；Conversation 保存「發生過什麼」，Memory 保存「以後值得重用什麼」。

來源：[Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)、
[Agents SDK Memory：multi-turn conversations](https://openai.github.io/openai-agents-js/guides/sandbox-agents/memory/#multi-turn-conversations)。

### 4.2 Rollout／raw rollout record

- Codex Phase 1 的 rollout extraction 是 per-thread；rollout 可包含多輪互動，不能直接當成一次 invocation。Sandbox 的 accumulated conversation file 也可包含多個 run segments。
- Sandbox runtime 將 run segment append 到 `sessions/<rollout-id>.jsonl`；同一 stable conversation
  identity 的多次 run 可累積在同一 Memory conversation。
- Codex CLI 當前實作從 state DB 選 eligible rollouts，不把 `thread_id`、`run_id`、
  `checkpoint_id` 當同一概念。
- raw rollout 是不可任意修改的底層證據；它不是每輪都注入 Context，也不是 final Memory。

### 4.3 Phase 1：`rollout_summary`、`rollout_slug`、`raw_memory`

Stage 1 model 必須回傳且只回傳：

```json
{
  "rollout_summary": "...",
  "rollout_slug": "...",
  "raw_memory": "..."
}
```

| 欄位 | 真正用途 | 不等於什麼 |
|---|---|---|
| `rollout_summary` | 一段 rollout 的完整可讀參考：目標、演變、結果、失敗、員工修正與核實狀態；未來需要細節時可讀 | final durable Memory；逐字 transcript |
| `raw_memory` | 給 Phase 2 的高訊號、可重用候選；按 task 分組並保留檢索 handles | 原始對話；可直接注入每輪的 current Memory |
| `rollout_slug` | filesystem-safe、最多 80 字元的 routing／檔名標籤 | truth ID；版本；來源證據 |

若沒有值得跨 run 保存的訊號，官方明確允許三個欄位全為空字串，形成
`succeeded_no_output`。此 status／state DB／secret redaction 是 Codex CLI 證據；
刪除 system／developer／reasoning 與過長時保留頭尾截斷，是 Sandbox SDK 文件明示的政策。
兩個表面不能混成單一 schema 契約。Codex 成功結果另連同 rollout identity、來源更新時間、
cwd／branch 等 runtime metadata 寫回 state DB。

OpenAI 也分開設定 Phase 1／Phase 2 model，並允許用 `extraPrompt` 指定特定領域應優先保留的
訊號。這表示「抽取」與「跨段整併」是可獨立調整模型與 instructions 的責任，而不是必須綁成
同一次模型呼叫。

### 4.4 Phase 2 輸入與控制 artifacts

| Artifact | 語意 |
|---|---|
| Stage 1 DB records | 每個 rollout 的抽取結果、status、lease／retry、來源更新時間與 selection bookkeeping |
| `raw_memories.md` | 目前被選取 Stage 1 `raw_memory` 的機械合併與 routing inventory；不是 final Memory |
| `raw_memories/` | Sandbox SDK 本輪公開 layout 列 `<rollout-id>.md`；Codex 固定快照由 DB record＋聚合檔承接。SDK layout 不等於跨產品穩定格式保證 |
| `rollout_summaries/` | 被選取 rollout 的可深讀 summary；Phase 2 消歧、未來 progressive deep-read 都可用 |
| selection snapshot | Codex CLI 以 DB 欄位記錄「成功 Phase 2 實際消費哪個 Stage 1 snapshot」 |
| `phase2_workspace_diff.md` | 前一次成功 baseline 到本批輸入同步後的 Git-style diff；只用來路由 consolidation，本身不是 durable Memory |

Phase 2 先取得全域 lock，只選有界 top-N，排序考量 `usage_count`、`last_usage`，沒有使用紀錄時
回退 `generated_at`。它把本批輸入同步到 memory workspace，若沒有 diff 就不呼叫 model；有 diff
才啟動無網路、無 approval、不可遞迴 delegation 的 consolidation sub-agent。

### 4.5 Phase 2 輸出

| Artifact | 真正用途 |
|---|---|
| `MEMORY.md` | 可 grep、按 task family 聚類、保留 rollout-summary refs 與 keywords 的 durable retrieval handbook |
| `memory_summary.md` | 每輪固定注入的高密度 routing guide；第一行必須是 `v1`；不是 mini handbook |
| `skills/` | 只有形成可重用程序時才選擇性建立／更新；屬 procedural knowledge，不是所有 Semantic Memory |

Consolidation 先讀 workspace diff，再處理新增／修改／刪除的 raw candidates；只有衝突、模糊、
高價值或需更強佐證時才開 rollout summaries。它會增量整併、去重、保守刪除只由已移除輸入支持
的內容，最後才由 final `MEMORY.md` 重建 `memory_summary.md`。

## 5. 框架元件的真實責任

### 5.1 LangGraph Checkpointer

```text
thread_id
  → 每個 graph super-step 保存 StateSnapshot
  → message state、next nodes、metadata、tasks、parent、pending writes
  → failure／interrupt 後可恢復；可查 state history
```

- **原生做到**：thread-scoped conversation continuity、checkpoint、fault recovery、interrupt、
  time travel、成功 sibling node 的 pending writes。
- **不會做到**：判斷 rollout 何時封口、抽取 Semantic Memory、建立 `rollout_summary`、搜尋 Store、
  形成 Memory guide。
- Checkpoint history 是 graph snapshots，並非 OpenAI 的 immutable JSONL rollout artifact；若拿來作
  canonical conversation，必須透過明確 reader 取 message／Tool item，而不是把整個 snapshot 當 transcript。

來源：[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、
[Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)。

### 5.2 LangGraph Store／PostgresStore

```text
namespace + key + arbitrary JSON value
  ├─ put：新增或覆寫 current value
  ├─ get：依 key 讀取
  ├─ search：exact/filter；設定 embeddings 後可 semantic search
  └─ list_namespaces／pagination：確定性列舉
```

- **原生做到**：durable application data、namespace 隔離、current item CRUD、語意搜尋、分頁列舉。
- **不會做到**：決定什麼值得存、去重／修訂、Stage 1／2、usage ranking、guide、保留版本歷史。
- 同 namespace／key 的 `put` 是覆寫 current value；官方 Store 契約不自動保存每次 revision。

來源：[LangGraph Stores](https://docs.langchain.com/oss/python/langgraph/stores)、
[BaseStore reference](https://reference.langchain.com/python/langgraph.store/base/BaseStore)。

### 5.3 LangChain `create_agent` 與 middleware

- `create_agent` 提供標準 model → Tool → Tool result → model loop，底層是 compiled LangGraph。
- `wrap_model_call`／dynamic prompt 可只改**本次模型可見**的 prompt、messages、tools 或 model，
  適合注入 guide、少量 recall 與有界 Context；不必改 durable Checkpointer state。
- `SummarizationMiddleware` 在 token／message／context-fraction threshold 後，用另一模型摘要舊消息並
  保留指定 recent messages。這是 LLM summary，不是 OpenAI Responses 的 opaque compaction item，
  也未單獨保證完整原 conversation archive。
- `ChatOpenAI` 可直接使用 Responses API `previous_response_id` 與 server-side `context_management`
  compaction；這是 **OpenAI provider 專用**，不是 provider-neutral framework contract。

來源：[LangChain agents](https://docs.langchain.com/oss/python/langchain/agents)、
[Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)、
[Prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)、
[ChatOpenAI](https://docs.langchain.com/oss/python/integrations/chat/openai)。

### 5.4 LangMem `create_thread_extractor`

**小元件接線補充（2026-09-05）：**它不自行從 Checkpointer 抓原文；實際先將 caller 傳入 messages 經 merge／pretty rendering，再交給 extractor。這不是原始 message object 的無損序列化，也不自動攜帶每則 canonical message ID。共用原文讀取、序列化、模型視圖及 backend 的細節與固定來源集中於[原文 source trace §6](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#6-接續核對同源原文如何供-b-抽取與-a-深查)；不得因高階元件缺 reader 就另存一份原文，亦未選定此 extractor。

```text
messages
  → Trustcall structured extraction
  → default SummarizeThread(title, summary)
     或 caller 提供的自訂 Pydantic schema
```

這是最接近 OpenAI Phase 1 model call 的 primitive，但它只負責「輸入 messages，輸出一個 structured
object」。它不提供 rollout eligibility、filter、truncation、secret redaction、job claim、lease、retry、
persistence 或 Phase 2 接力。要同時產生 summary、slug 與 candidates，必須提供自訂 schema。

### 5.5 LangMem `create_memory_manager`

```text
messages + optional existing memories + max_steps
  → Trustcall create／update／optional delete
  → list[ExtractedMemory(id, content)]
```

- 它是 **stateless Runnable**；原始碼實際回傳結果，呼叫者負責持久化。
- 預設 Memory 只有一個 rich standalone `content`。
- `max_steps` 讓模型在同一 invocation 對同一 working set 反覆精煉，Tool result 會回饋下一步。
- 這提供 consolidation 的結構化修訂 primitive，但模型不能在其中自行搜尋或打開工作集外的
  rollout summary；它不等同 OpenAI 可按需取證的 consolidation agent。提高 `max_steps`
  只會反覆精煉既有工作集，不增加外部 read 能力。見審核 F01。

官方 API doc 有一句「automatically persisted」，但同頁 return contract 與當前原始碼均顯示
`create_memory_manager` 只回傳 `ExtractedMemory`；真正自動寫 BaseStore 的是下一個元件。設計應以
可驗證的 runtime 行為為準。

### 5.6 LangMem `create_memory_store_manager`

```text
conversation messages
  → 產生 query 或用 dilated message windows
  → Store semantic search（預設總上限 5）
  → create_memory_manager 修訂 retrieved current memories
  → optional phases 依序精煉同一批 in-memory candidates
  → 最後發出各筆 put／delete 到 Store（非整批原子提交）
```

優勢是少量接線即可完成 retrieve＋consolidate＋write；但它**不是** OpenAI Phase 1 → durable
intermediate artifacts → Phase 2：

- 不產生／保留獨立 `rollout_summary`；
- 不保留 `raw_memory` candidate inventory；
- `phases` 只是同一 working set 的連續 manager passes；
- 預設只取 top-5 相關既有 Memory，不是全量 consolidation／最終全量 JD coverage；
- 不建立 `MEMORY.md` 等價的 routing taxonomy 或 `memory_summary.md` guide。

另有兩個文件／原始碼落差不可忽略：

1. API 說明文字稱會維護「versioned history」，但當前實作對同一 key 呼叫 Store `put`，而
   BaseStore 契約是 store-or-overwrite；官方公開原始碼看不到自動保留 revision ledger 的步驟。
2. 當前 API signature 的 `enable_deletes` 預設是 `False`，同頁參數說明卻寫「Defaults to True」。

所以 retained history 與 delete default 都不能靠說明文字假設；必須以鎖定版本的實際 contract／
compatibility test 為準。

因此可作「簡化的一步式替代方案」，不能標成完整承接 OpenAI pipeline。

### 5.7 LangMem hot-path tools

`create_manage_memory_tool` 的 model-facing shape：

```text
content?: string
id?: UUID
action: create | update | delete
```

`create_search_memory_tool` 的 model-facing shape：

```text
query: string
limit: int = 10
offset: int = 0
filter?: object
```

搜尋 Tool 可回 serialized content，也可把原始 Store items 作 artifact 交給 runtime。它們是很接近
live repair／progressive search 的 primitive，但 LangMem 0.0.30 有兩個已公開風險：

1. manage tool 寫入 `{"content": ...}`，StoreManager 使用 `{"kind": ..., "content": ...}`；
2. 有使用者回報 PostgresStore 上 search tool 無法直接取回 StoreManager 寫入的 schema Memory。

原始碼可證明 value shape 不同；issue 只能證明存在相容性風險，不能推論所有 backend 必然失敗。
在選定版本實測前，不得把 hot tool 與 StoreManager 宣稱為同一個無縫 lifecycle。

另有 `create_memory_searcher`：它先讓模型從 conversation 產生一至多個搜尋 query，再呼叫 Store、
去重並排序結果。這可承接較複雜的自動 recall，但會增加一次模型工作；若本輪新訊息本身已是良好
query，直接使用 Store semantic search 是較低成本的官方 primitive。兩種都是框架提供的選項，
本稿不先固定每輪必須額外呼叫 query model。

來源：[LangMem Memory API](https://langchain-ai.github.io/langmem/reference/memory/)、
[Tools API](https://langchain-ai.github.io/langmem/reference/tools/)、
[extraction source](https://github.com/langchain-ai/langmem/blob/main/src/langmem/knowledge/extraction.py)、
[issue #138](https://github.com/langchain-ai/langmem/issues/138)、
[issue #140](https://github.com/langchain-ai/langmem/issues/140)。

### 5.8 LangMem `ReflectionExecutor`

- local mode 以 thread debounce；新 submission 會取代尚未執行的舊 payload，但 worker 是 process 內
  thread，重啟後不具 durable job 保證。
- remote mode 可委派 LangGraph Agent Server run；這才可借用 durable queue／run lifecycle。
- 它不自動提供 OpenAI rollout eligibility、Stage 1 status、Phase 2 selection 或 global consolidation lock。

### 5.9 Deep Agents

- `StateBackend`：thread 內 filesystem，透過 checkpoints 保存；適合 scratch／大型 Tool output offload。
- `StoreBackend`：把虛擬檔案寫進 LangGraph Store；是 OpenAI Markdown physical layout 的最近似
  primitive，但不產生那些檔案內容。
- `memory=[paths]`：指定 Memory 檔會始終注入 system prompt；**不是** `memory_summary → search →
  deep-read` 的自動完整流程。但可以只指定小導覽，其他檔案仍按需 read；不能據此說
  Deep Agents 無法組成 progressive disclosure。FilesystemMiddleware 官方亦可獨立接 create_agent。
- Skills middleware：只先暴露 metadata，按需讀完整 Skill；直接承接 procedural progressive loading。
- context compression：大型 Tool payload 自動 offload；接近 context 上限時生成 in-context summary，
  並把完整原 messages 另存 backend。比一般 summarization 多 canonical preservation，但仍不是
  OpenAI Responses opaque compaction。
- background consolidation 是官方 recipe：另一個 agent＋自訂 conversation search Tool＋cron；
  並非啟用 Deep Agents 就自動得到的 pipeline。

來源：[Deep Agents memory](https://docs.langchain.com/oss/python/deepagents/memory)、
[context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering)、
[backends](https://docs.langchain.com/oss/python/deepagents/backends)。

### 5.10 LangGraph Agent Server

Agent Server 提供 graph deployment、PostgreSQL persistence 與 durable task queue：run 先入 queue，
worker 取得 lease，且同一 thread 同時最多執行一個 run。它能**承載** background extraction／
consolidation graph，但不會替應用定義 eligibility、watermark、artifact schema、selection 或 guide。

來源：[Agent Server](https://docs.langchain.com/langsmith/agent-server)、
[Runs](https://docs.langchain.com/langsmith/runs)。

## 6. 逐 artifact 交叉表

| OpenAI 元件／artifact | 框架最接近元件 | 判定 | 精確差異／仍需責任 |
|---|---|---|---|
| Conversation object | LangGraph thread＋Checkpointer message state | **Close** | 都能跨 run 保存對話；但不是 OpenAI provider Conversation API，item schema／retention 不同 |
| SDK Session | stable `thread_id`＋compiled graph | **Close** | 維持同一 conversation；不會在 close 時自動觸發 Semantic Memory 生成 |
| Rollout | thread conversation 記錄＋選定的抽取輸入範圍 | **Close** | Codex 為 per-thread；Sandbox 累積多次 run segment；不是一個 Agent Server run 的直接別名 |
| Raw rollout record | Checkpointer history；或 Deep Agents canonical conversation file | **Close** | 前者是 state snapshots，後者是 summary 時另存的檔；都不是 OpenAI JSONL 格式 |
| Rollout eligibility | graph node＋Agent Server queue／lease | **Gap＋Compose** | queue／lease 可用；idle、age、allowed source、claim limit、已處理 watermark 是 policy |
| Memory-relevant item filtering／secret redaction | LangChain middleware／deterministic preprocessing | **Gap＋Compose** | middleware有 hook，但哪些 item可進 extraction、哪些敏感內容必須遮蔽仍是應用 policy |
| Phase 1 extraction call | LangMem `create_thread_extractor(custom_schema)` | **Direct primitive** | model extraction 可直接用；filter／truncation／redaction／job lifecycle 仍在外層 |
| Phase 1／2 分開選模型 | extractor與manager各自接收 model | **Direct** | 兩個 primitive可用不同模型；成本／品質選型留後續 provider gate |
| 領域額外 extraction／consolidation 指示 | extractor `instructions`＋manager `instructions` | **Direct** | 可承接 OpenAI `extraPrompt` 的效果；實際職務分析內容是 Caliburn Skill／prompt責任 |
| `rollout_summary` | extractor custom field | **Close** | 可生成相同語意，但框架不自動持久保存或供未來 deep-read |
| `rollout_slug` | extractor default `title` 或 derived label | **Close** | title 不是 filesystem-safe slug；兩者都不能當 truth ID，ID 應由 runtime 提供 |
| `raw_memory` | extractor custom `raw_memory: str`；或等價 candidate collection | **Close** | extractor 可產生相同候選 artifact；manager output 已較接近 consolidated current Memory，生命週期不同 |
| Stage 1 DB record | LangGraph Store structured item | **Compose** | Store 能保存；status、source snapshot、lease、retry、selection flags 需 job graph／runtime |
| `raw_memories/` physical directory | Stage 1 Store namespace；可選 StoreBackend files | **Physical-only** | candidate artifacts 可存 Store；SDK 公開 layout 有 `<rollout-id>.md`，本案是否採檔案仍待決，不因範例自動照抄 |
| `raw_memories.md` | Store list/search＋derived inventory view | **Compose** | BaseStore 可列舉；合併、穩定排序與「本批選取」投影需薄 node |
| `rollout_summaries/*.md` | Store namespace of segment summaries；可選 StoreBackend file | **Compose** | Store 可存完整 summary；精確檔名與 Markdown 是可選 physical presentation |
| Phase 2 selection snapshot | Store query/list＋background graph state | **Gap＋Compose** | 沒有 Codex usage-count／recency selector；需明確 selection node與成功 watermark |
| `phase2_workspace_diff.md` | graph state 的 changed IDs／before-after；或 filesystem Git diff | **Do not copy** | 其目的在讓 file-editing sub-agent只看增量；DB-native manager 不必造 Git diff |
| Global Phase 2 lock | Agent Server 同-thread serialization；或 DB/application lock | **Close** | Server保證同 thread一 run；跨獨立 background scope 的精確 mutex仍需部署設計 |
| Phase 1 status／retry／backoff | LangGraph retry＋Agent Server run lifecycle＋Store status item | **Compose** | durable execution可用；`succeeded_no_output`、eligible snapshot與何時重試仍需明確 job contract |
| Consolidation model | create_agent＋search/read/edit tools；或 LangMem manager | **Compose／部分 Close** | 前者可整併中按需取證；後者只精煉傳入工作集，不提供外部 summary 深讀迴圈，見審核 F01 |
| 一站式 consolidation | `create_memory_store_manager` | **Direct alternative** | 可少寫接線，但壓平 Stage 1/2，不留 summary/candidate bridge，只取 top-k |
| `MEMORY.md` | PostgresStore current Semantic Memory collection | **Functional Compose** | 可搜尋／修訂 current heads；沒有 OpenAI 固定 taxonomy、citations、usage telemetry |
| `MEMORY.md` physical file | Deep Agents `StoreBackend`＋FilesystemMiddleware | **可組合功能候選** | 不只是檔案形狀；提供 grep/read/edit，可獨立接 create_agent；內容政策與一致性仍須 workflow |
| `memory_summary.md` | derived guide＋LangChain dynamic prompt middleware | **Gap＋Compose** | middleware會注入但不會從 current Memory 重建 guide；生成／失效規則需薄 projection |
| `skills/` | Deep Agents Skills middleware＋StoreBackend | **Direct／optional** | 很貼近 procedural memory progressive loading；不代表 Semantic Memory 應存成 Skill |
| Progressive `summary→search→deep-read` | middleware＋Store semantic search＋LangMem search tool＋read adapter | **Compose** | 沒有一個 component 自動協調完整階梯 |
| Memory search | Store semantic search／LangMem search；或 filesystem grep/read | **Close；檢索策略可選** | vector top-k 與 Codex 文字搜尋不是同一機制；自動 recall 也不是跨家每輪必備，見審核 F05 |
| Full Memory deep-read | Store search result full value／`get` | **Direct** | 如果 search 已回完整 self-contained record，不應再造多餘 read-by-ID Tool |
| Raw conversation deep-read | Checkpointer history＋受限 read adapter | **Gap＋Compose** | history primitive存在；無現成 model-facing conversation semantic-search/read Tool |
| Compaction | ChatOpenAI server compaction；LangChain／Deep Agents summarization | **Direct provider-only／Close fallback** | OpenAI native compaction最接近；provider-neutral summary的 artifact與恢復語意不同 |
| Live repair | LangMem manage Tool＋Store update | **Close** | CRUD primitive存在；「目標已深讀、唯一且確定 stale」政策與 value-shape相容性不在框架 |
| Supporting evidence | Store metadata／segment-summary references | **Gap＋substrate** | 框架能存 refs，但沒有 OpenAI／Caliburn通用 evidence schema |
| Usage telemetry／citations | LangSmith tracing＋application metadata | **Close** | tracing記錄 calls/writes；不自動形成 Codex memory citation parser或 per-memory usage_count |
| Forgetting／pruning | manager delete＋Store delete＋selection policy | **Compose** | CRUD有；何時 retire、何時只移除失效 support 是 consolidation政策 |
| Final all-Memory inventory | Store namespace pagination/list | **Direct substrate** | 可確定性遍歷；「全部處理過」的 coverage loop／receipt 是 workflow responsibility |
| Versioned current head | Store overwrite＋可選 Checkpointer job history | **Gap** | Store不自動留 semantic revision ledger或CAS；是否需要另由後續 concurrency gate裁決 |

## 7. 三條流程如何用框架完成

### 7.1 A：即時讀取

```text
LangGraph Checkpointer：canonical conversation／run continuity
  → LangChain per-call middleware：組裝有界 recent／continuation Context
  → middleware 注入 derived guide
  → LangGraph Store semantic search：少量自動 recall
  → create_agent：main model↔Tool loop
       ├─ LangMem search Tool 或窄 facade：按需增加 Semantic Memory
       ├─ Store full item：深讀完整 Memory
       └─ thin Checkpointer reader：必要時回查 canonical conversation
```

- 直接可用：Checkpointer、middleware、Store search、agent loop、LangMem search。
- 仍待選：OpenAI server compaction 或 provider-neutral summarization fallback。
- 薄缺口：guide builder、canonical conversation model-facing reader。

### 7.2 B：背景形成

```text
durable background LangGraph
  1. runtime 選出已封口且未處理的 conversation segment
  2. create_thread_extractor(custom schema)
       → rollout summary＋routing label＋raw-memory candidate artifact（可為空）
  3. Stage 1 result 寫 Store
  4. Store search／list 取 candidates 相關 current Memory
  5. 候選 A：create_memory_manager(messages=candidates, existing=current heads)
       → 既有工作集的結構化修訂結果；不含按需外部深讀
     新增比較 B：create_agent＋受限 search/read/edit
       → 整併中可再讀 summary，較接近 OpenAI 的取證迴圈
  6. 套用變更；部分成功／恢復契約未定，不宣稱自動整批原子寫入
  7. 成功後重建小型 guide
```

這個組合保留 extraction／consolidation 分工，但原先只用 LangMem manager 的版本未涵蓋
OpenAI 整併中的按需深讀。LangMem 為 pre-1.0，不能僅憑 primitive 存在就稱已成熟等價；
候選比較、接力與恢復契約見審核 F01–F07。

若未來實證不需要 per-segment summary／candidate bridge，可改採
`create_memory_store_manager` 簡化；但那是**有意壓平生命週期**，不是等價實作。

### 7.3 C：live repair

```text
main agent 已完整讀到一筆 current Memory
  → 發現目標唯一且明確過時
  → 以 runtime-issued existing ID 呼叫窄 update Tool
  → Tool 驗證 scope／shape並寫 Store
  → success Tool result 回模型後，後續 step才依賴新版
  → 同一段 conversation日後照常進 B；B看到最新版並對已涵蓋內容 no-op
```

LangMem manage tool 提供 close primitive，但因 0.0.30 hot／background value shape 不一致，不能
直接把它與 StoreManager 混接。下一個 compatibility gate 應先選一個 canonical Store value shape，
再決定使用原工具、薄 wrapper，或以 `create_memory_manager` 統一寫入。

## 8. 哪些可以直接用、哪些不能

### 8.1 可直接採用的成熟能力

1. LangChain `create_agent` 的 model／Tool loop。
2. LangGraph PostgreSQL Checkpointer 的 thread continuity 與 durable graph state。
3. LangGraph PostgreSQL Store 的 namespace、current item CRUD、semantic search、pagination。
4. LangChain middleware 的 per-model-call Context 組裝。
5. LangMem `create_thread_extractor` 的 structured segment extraction。
6. LangMem `create_memory_manager` 的 existing-aware incremental consolidation。
7. LangGraph graph／Agent Server 的 durable background execution substrate。
8. Deep Agents Skills 的 procedural progressive loading（若 Skill gate選用）。

### 8.2 只有功能相似，不能當完全等價

1. LangGraph thread/run/checkpoint 與 OpenAI Conversation/rollout/raw rollout。
2. LangChain／Deep Agents summarization 與 OpenAI Responses compaction。
3. LangMem StoreManager `phases` 與 OpenAI Phase 1／Phase 2。
4. Deep Agents always-injected memory file 與 OpenAI progressive Memory read。
5. Deep Agents background consolidation recipe 與 Codex 內建 Stage 1／2 pipeline。
6. LangMem manage tool 與 OpenAI liveUpdate policy。

### 8.3 本次組合尚未自動承擔的責任（不預設都很薄）

1. 定義何時一段 conversation 足夠穩定可進 extraction。
2. Stage 1 job eligibility、processed watermark、no-output／retry bookkeeping。
3. 持久保存 segment summary／candidate bridge 的 application schema。
4. Phase 2 candidate／current-head selection 與批次邊界。
5. current Memory 成功變更後重建小型 routing guide。
6. 將 Checkpointer history 以有界、安全格式提供給模型深讀。
7. 最終全量 Memory 列舉後的 coverage workflow。
8. 統一 LangMem hot/background Store value shape；若要 version/CAS，另由 concurrency gate決定。

這些是 control plane／產品語意，不是重新實作 embedding、Store、agent loop、structured extraction
或 consolidation 演算法。

## 9. 明確排除的錯誤設計

1. 不把 `thread_id`、`run_id`、`checkpoint_id`、`rollout_id` 當同一 ID。
2. 不把 Checkpointer 當 Semantic Memory manager。
3. 不把 Store 的 `put` 視為自動有 revision history／CAS。
4. 不把 `create_memory_store_manager` 稱為 OpenAI 兩階段 pipeline。
5. 不把 `raw_memory` 當 raw conversation；它已是模型抽取候選。
6. 不把 `rollout_summary` 當逐字證據；精確核實仍回 canonical conversation。
7. 不把 `memory_summary.md` 當全部 Memory；它只是 routing guide。
8. 不因 OpenAI 用 Git diff／Markdown，就要求 DB-native Caliburn 也照抄。
9. 不把 semantic top-k search 當 final all-Memory coverage。
10. 不在實測前把 LangMem hot tool 與 StoreManager 宣稱為 schema-compatible。

## 10. 目前建議與尚未決定事項

### 10.1 研究結論

以下是上一輪暫時核准方向；本輪發現尚未證明它最貼合。新增 agentic consolidation
元件級候選，待 Owner 討論，詳見[審核 §5](2026-09-05-generic-memory-flow-framework-crosswalk-audit.md)：

```text
stable LangChain create_agent
＋ LangGraph PostgreSQL Checkpointer／Store／background graph
＋ LangMem create_thread_extractor／create_memory_manager／search primitives
＋ selected Deep Agents Skills／compression components（逐責任選用）
＋ 很薄的 segment、selection、guide、conversation-read control plane
```

底層 agent loop、存取、搜尋與 structured output 可重用；哪些接力需要應用決策、哪些能再由
其他官方元件承接，須逐責任核實，不能斷言任何通用框架都不會提供。

### 10.2 下一階段仍須逐題裁決

1. **Compaction gate**：OpenAI server-side compaction、Deep Agents preservation，及非 OpenAI provider fallback。
2. **Background durability gate**：自架 Agent Server、既有本機 job runner，或較薄 durable graph trigger。
3. **Artifact retention gate**：segment summary 永久保留多久；raw candidates只作 job state或也耐久保存。
4. **Store compatibility gate**：以最新選定版本驗證 manager/search/update 的 value shape、ID 與 Postgres 行為。
5. **Concurrency gate**：一 JD 一 active run 是否已足夠；若 background/live repair競爭，再決定serialization／CAS。
6. **Guide gate**：導覽的生成、最大長度、失效與全量 coverage contract。

本稿不偷決定以上六題，也不授權 production 施工。

## 11. Closure

```text
Status:
  G2 複核修正完成；F01–F07 與新的元件級候選待 Owner 討論。
Decision:
  尚未形成 Accepted architecture；LLM-Q016 的組合方向維持暫時核准。
Reason:
  已逐項核實 OpenAI artifact 與最新 framework primitive，並分開 Direct／Close／Compose／Gap。
Evidence reviewed:
  本稿 §1、§4、§5 與下列官方來源。
Reopen triggers:
  OpenAI Codex memory pipeline、LangChain／LangGraph、Deep Agents 或 LangMem 發生重大版／契約變更；
  compatibility spike推翻目前 value-shape／persistence判定。
Next gate:
  先依通用流程審核 §5 比較整併中途深讀能力，再收斂實作方案；不直接施工。
```

## 12. 官方來源

### OpenAI

- [Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- [Compaction](https://developers.openai.com/api/docs/guides/compaction)
- [Agents SDK Sandbox Memory](https://openai.github.io/openai-agents-js/guides/sandbox-agents/memory/)
- [Codex memories README](https://github.com/openai/codex/blob/main/codex-rs/memories/README.md)
- [Codex Stage 1 system prompt](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/stage_one_system.md)
- [Codex Stage 1 input](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/stage_one_input.md)
- [Codex consolidation prompt](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/consolidation.md)
- [Codex read-path prompt（已核對正確位置；摘要／原文路由詳見本輪子稿）](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/ext/memories/templates/memories/read_path.md)
- [摘要引用的寫入→讀取 source review](2026-09-05-memory-summary-routing-and-deep-read-source-review.md)
- [Codex memory state model](https://github.com/openai/codex/blob/main/codex-rs/state/src/model/memories.rs)

### LangChain／LangGraph／Deep Agents

- [LangChain agents](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- [LangChain prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [ChatOpenAI integration](https://docs.langchain.com/oss/python/integrations/chat/openai)
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph Stores](https://docs.langchain.com/oss/python/langgraph/stores)
- [LangGraph Agent Server](https://docs.langchain.com/langsmith/agent-server)
- [Deep Agents Memory](https://docs.langchain.com/oss/python/deepagents/memory)
- [Deep Agents Context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering)
- [Deep Agents Backends](https://docs.langchain.com/oss/python/deepagents/backends)

### LangMem

- [LangMem Memory API](https://langchain-ai.github.io/langmem/reference/memory/)
- [LangMem Tools API](https://langchain-ai.github.io/langmem/reference/tools/)
- [LangMem extraction source](https://github.com/langchain-ai/langmem/blob/main/src/langmem/knowledge/extraction.py)
- [LangMem tools source](https://github.com/langchain-ai/langmem/blob/main/src/langmem/knowledge/tools.py)
- [LangMem ReflectionExecutor source](https://github.com/langchain-ai/langmem/blob/main/src/langmem/reflection.py)
- [LangMem issue #138](https://github.com/langchain-ai/langmem/issues/138)
- [LangMem issue #140](https://github.com/langchain-ai/langmem/issues/140)

## 13. 與其他研究稿的關係

- OpenAI 系統全圖：[`2026-09-05-openai-conversation-context-and-memory-system-map.md`](2026-09-05-openai-conversation-context-and-memory-system-map.md)
- OpenAI progressive read 深入研究：[`2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md`](2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md)
- Framework 官方流程事實圖：[`2026-09-05-langchain-langgraph-deepagents-langmem-official-memory-flow-map.md`](2026-09-05-langchain-langgraph-deepagents-langmem-official-memory-flow-map.md)
- 上一層功能交叉表：[`2026-09-05-openai-memory-flow-to-latest-framework-functional-crosswalk.md`](2026-09-05-openai-memory-flow-to-latest-framework-functional-crosswalk.md)

本稿補的是 artifact／primitive 級差異；它不重寫上述來源，也不取代 Accepted ADR。
