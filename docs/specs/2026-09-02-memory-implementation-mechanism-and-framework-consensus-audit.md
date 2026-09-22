# Memory 實作機制與成熟框架共識稽核

- 日期：2026-09-02
- 狀態：**Working Research；框架與底層機制尚未完成 Owner 裁決，暫不授權施工**
- 上位產品契約：[`2026-09-01-framework-independent-memory-contract.md`](./2026-09-01-framework-independent-memory-contract.md)
- 第一切片草稿：[`2026-09-02-memory-foundation-vertical-slice-design.md`](./2026-09-02-memory-foundation-vertical-slice-design.md)
- 範圍：只審核 Memory 功能要如何由成熟 framework primitive 落地；不寫 schema、migration、graph node 或 production code

> **核心規則**：功能效果相同，不代表底層機制相同。只有多家獨立官方系統公開採取相同責任分離或同類 primitive，才可稱為「機制共識」。若各家只是達成同一效果，但分別使用 hash CAS、revision、idempotency token、checkpoint task 或 managed operation，本文必須列為「共同效果、實作分歧」，由 Owner 選擇，不能由實作者自行拼出一套機制再宣稱是大廠作法。

> **2026-09-02 最新能力校正**：本文 §10 已否決把完整 Semantic Memory collection 放進 Checkpointer 的候選；[`Memory Foundation 最小垂直切片設計`](./2026-09-02-memory-foundation-vertical-slice-design.md) 已依該結論重寫為 Store-first 待審方案。最新候選回到官方責任分層：Checkpointer 保存 thread／run state，per-JD PostgreSQL Store 保存 durable source 與可修訂 Semantic Memory。本文較早段落若仍描述 Checkpointer current collection，以 §10 與重寫後切片為準。

## 1. 本輪修正了什麼

先前研究已正確收斂 Memory 的必要產品效果，但第一切片草稿把幾個 **Caliburn 候選映射** 寫得太接近跨家共同底層：

- per-JD single writer；
- Runtime deterministic Memory key；
- checkpoint 內的 inventory worklist；
- LangGraph `offset` pagination 加 backend contract tests；
- 一次 bounded model repair。

這些都可能是合理作法，但目前官方證據只能支持其中一部分效果，不能證明它們是 OpenAI、Anthropic、Microsoft、Google、AWS 與成熟 framework 共用的底層。本文因此不再只用「有共識／沒共識」二分，而是逐項標示六級：

| 等級 | 意義 | 能否直接進實作計畫 |
| --- | --- | --- |
| F1 功能／效果共識 | 多家都要求達成同一結果 | 成為不可漏掉的 acceptance criterion；不能據此推定底層 |
| R1 責任分工／mechanism-family 共識 | 多家公開採同類分層或同族 primitive | 可以約束模組邊界；仍須選 framework 的具體實作 |
| I1 相同底層 primitive 共識 | 多家公開介面真的提供同一類操作語意 | 可進實作候選，但仍要驗證版本、交易邊界與 failure semantics |
| V1 單家成熟 framework primitive | 某個成熟 framework 已完整提供，但不是跨家共同底層 | 可以作正式候選；必須列出 lock-in、缺口與替代方案 |
| P1 Caliburn 產品映射 | 為本機、單操作者、每員工一 JD 等條件做出的選擇 | 必須明示取捨並經 Owner 同意；不得標成大廠共識 |
| D1 延後能力 | 沒有第一切片證據或需求 | 不施工 |

因此，「各家都防止重試造成重複」只能先列為 F1；只有找到相同 idempotency primitive 才能升到 I1。「原始對話與整理後 Memory 分層」則有足夠資料列為 R1，但不能因此宣稱各家都使用 checkpoint＋同一張 Store table。

## 2. 官方實作事實

### 2.1 OpenAI／Codex

- Codex 把 `generate_memories` 與 `use_memories` 分離，並可分別指定 extraction 與 consolidation model；Memory 是 recall layer，不是必守規則的唯一權威。
- OpenAI Responses compaction 回傳不透明的 compaction item，保留下一個 Context window 所需的 prior state；它不是 application Semantic Memory CRUD API。
- Function calling 官方建議使用 strict schema、讓 code 提供已知參數、減少初始 Tool 數量；大量 Tool 可用 tool search 延後載入。
- OpenAI Agents SDK Session 能保存完整 history，並在每次 run 透過 limit／input callback 控制送入模型的部分；Session persistence 與 Semantic Memory 仍是不同責任。
- OpenAI 沒有公開一套可供一般 application 直接自架的 Semantic Memory CAS、exact inventory 或 revision Store 契約；不得猜測 Codex 內部資料庫。

來源：[Codex Memories](https://learn.chatgpt.com/docs/customization/memories) · [Compaction](https://developers.openai.com/api/docs/guides/compaction) · [Function calling](https://developers.openai.com/api/docs/guides/function-calling) · [Agents SDK Sessions](https://openai.github.io/openai-agents-python/sessions/)

### 2.2 Anthropic／Claude

- Anthropic Memory Tool 是 client-side Tool：Claude 請求 file operation，應用執行並決定實際 storage；Claude 以目錄／檔案按需讀取，不必預載全部 Memory。
- Managed Agents Memory 是 workspace-scoped text-document store，官方建議 many small focused files；list 使用 stable server-defined order 與 opaque `next_page`。
- 每次 Managed Memory mutation 產生 immutable version；update 可選擇帶 `content_sha256` precondition，失配後重讀再試。
- Tool failure 以原 `tool_use_id` 對應 `tool_result`，並用 `is_error=true` 明確標示；未受信任內容留在 `tool_result`，不能提升成 system instruction。
- Managed Memory 是 beta 雲端服務；Memory Tool 的 client-side handler 仍要求應用自行處理 storage、path validation、大小限制與 write validation。

來源：[Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool) · [Managed Agents Memory](https://platform.claude.com/docs/en/managed-agents/memory) · [List Memories API](https://platform.claude.com/docs/en/api/http/beta/memory_stores/memories/list) · [Handle Tool Calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)

### 2.3 Google Memory Bank

- Memory generation 明確分成 extraction 與 consolidation。
- 預設 consolidation 會比較同 scope 的全部 existing Memories，處理重複、更新與矛盾；custom topics、instructions 與 few-shot 決定抽取範圍。
- 可使用 blocking 或 background generation；若當前 run 不依賴結果，官方通常建議 background。
- scope retrieval 明確分成 similarity top-k 與 retrieve-all；retrieve-all 有 pager，一頁最多 100，SDK 可自動走完全部頁面。
- current Memory 與 revisions 分離；revisions 預設啟用但可以停用，也有 TTL 與 rollback。
- Google 是 managed service，沒有公開可直接搬進本機 PostgreSQL 的 consolidation backend 實作。

來源：[Generate Memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories) · [Fetch Memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/fetch-memories) · [Memory Revisions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/revisions)

### 2.4 AWS AgentCore Memory

- Short-term Memory 保存 timestamped raw events；Long-term Memory 是從 events extraction／consolidation 後產生的 records。
- Long-term generation 在背景非同步執行；records 可 get、list 或 semantic retrieve。
- `CreateEvent.clientToken` 提供 no-more-than-once operation；這是 idempotency token，不是 record CAS。
- `ListMemoryRecords` 使用 namespace／namespacePath、`nextToken` 與每頁最多 100 筆。
- Memory strategy 有 managed、prompt override 與 self-managed；self-managed 才讓應用完整控制 prompt、schema、namespace 與演算法。

來源：[Memory Types](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-types.html) · [CreateEvent](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_CreateEvent.html) · [ListMemoryRecords](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_ListMemoryRecords.html) · [Memory Strategies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html)

### 2.5 Microsoft Foundry Memory

- Microsoft 明確區分 short-term conversation context 與 long-term distilled knowledge；長期層使用 extraction、consolidation、retrieval 三階段。
- Memory Store 以 application-selected `scope` 隔離資料；低階 API 必須由應用明確提供 scope，模型不應自行選擇可信邊界。
- 最新 preview 同時提供 memory search Tool 與 item-level create／read／update／list／delete API：前者簡化 agent 使用，後者讓應用控制 individual record lifecycle。
- 官方允許用 store instructions 限定要抽取的資料，並提供 direct remember／forget command、TTL 與 item-level user controls。
- 這是 managed public preview，且需要 Azure chat／embedding deployments；公開資料沒有提供可搬到本機 PostgreSQL 的 extraction／consolidation backend，也沒有公開 expected-version CAS 或 snapshot-grade list 契約。

來源：[What is Memory?](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/what-is-memory) · [Create and use memory](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/memory-usage)

### 2.6 LangGraph／LangChain

- Checkpointer 保存 thread-scoped graph state；Store 保存 application-defined long-term key-value data。
- Store 已提供 namespace、put／get／delete、非語意 listing、optional semantic search 與 PostgreSQL backend。
- Store 的 `put` 是 store-or-overwrite；官方介面沒有 expected revision、CAS、immutable history 或 operation token。
- 無 query／filter 的 Store listing 使用 prefix、limit／offset；PostgreSQL backend 預設按 `updated_at DESC`。官方未承諾 opaque cursor、stable tie-break 或跨頁 snapshot。
- LangGraph task replay 會重用已完成結果，但已開始未完成的 task 可能重跑；官方要求 side effect 自身用 idempotency key 或既有結果查核。
- Agent Server 的 enqueue／reject／interrupt／rollback 能處理 double texting；官方明示這不是 LangGraph OSS 功能。
- LangChain 1.x 已有 production middleware：`ToolErrorMiddleware` 把例外轉成 model-visible error；`ToolRetryMiddleware` 主要重試 transient Tool failure；`SummarizationMiddleware` 負責有界對話壓縮；HITL middleware 可 approve／edit／reject。

來源：[Stores](https://docs.langchain.com/oss/python/langgraph/stores) · [Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api) · [Double Texting](https://docs.langchain.com/langsmith/double-texting) · [Built-in Middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)

### 2.7 LangMem

- `create_memory_manager` 的標準形狀是 conversation＋current memory → LLM extraction／consolidation → updated memories。
- collection 保存多筆可搜尋、可更新的 record；profile 是單一 current-state document。
- LangMem 支援 insert／update／delete、自訂 instructions／Pydantic schema、hot path 與 background formation。
- Core API 只做 memory transformation，沒有 storage side effect；Store Manager 才接 LangGraph Store 並執行 upsert／delete。
- LangMem 可直接覆蓋「語意抽取＋與既有 Memory 整理」這一層，但不提供 CAS、exact inventory、權威 scope、來源真實性或完整 JD 保證。
- LangMem 仍未進 1.0，因此若採用，只能作可替換 leaf，不能把未文件化內部行為變成 authority contract。

來源：[LangMem Core Concepts](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/) · [Memory API](https://langchain-ai.github.io/langmem/reference/memory/)

### 2.8 Pydantic AI Harness Memory

- Application resolver 決定 namespace，scope 不出現在 model-facing Tool schema。
- 自動注入預設有約 2,000 token budget；read、list 與 search 都有硬上限，Memory 以低權限 user-role data 注入。
- Store mutation contract 原生包含 atomic optimistic CAS 與由 run／tool-call 衍生的 durable idempotency；PostgreSQL Store 在 DB transaction 內實作。
- bundled search 是 bounded literal search，沒有內建 semantic ranking。
- `list_paths(limit)` 沒有 iterate-all cursor；因此它不直接覆蓋完整 inventory。
- Pydantic retries 清楚分開 transport retry、Tool／output validation repair 與 terminal failure；`ModelRetry` 會用同一 tool-call ID 回饋錯誤並要求模型修正，但使用它代表採用 Pydantic agent runtime 的 retry contract。
- Harness 仍是 0.x；不能只為單一漂亮 primitive 就無條件混入第二套 runtime。

來源：[Harness Memory](https://pydantic.dev/docs/ai/harness/memory/) · [Pydantic AI Retries](https://pydantic.dev/docs/ai/core-concepts/retries/)

## 3. 跨家責任分工／mechanism-family 共識

下列不是 Caliburn 自行發明，而是至少三個獨立官方系統反覆出現的責任分工或同族 primitive。它們大多屬 R1，少數只有 F1；**本節不宣稱各家使用相同 database schema、交易、cursor 或 retry loop**。

| 分級 | 共同形狀 | 官方證據形狀 | 第一切片含義 |
| --- | --- | --- | --- |
| R1 | Raw conversation／events 與整理後長期 Memory 分層 | OpenAI session＋generated Memory、Microsoft short／long-term、Google source events＋Memory、AWS short／long-term、LangGraph checkpointer＋Store | 不把 transcript 複製成 Semantic Memory，也不拿摘要取代原始對話 |
| R1 | extraction 與 consolidation 分開思考 | OpenAI extract／consolidation model、Microsoft、Google、AWS、LangMem | 先決定新來源值得形成什麼，再與目前 Memory 比較新增／更新／刪除／no-op；不代表一定呼叫模型兩次 |
| R1 | scope／namespace 由應用可信 Context 決定 | Microsoft／Google scope、AWS namespace variables、LangGraph Runtime namespace、Pydantic resolver、Anthropic mount／store attachment | 模型不填 JD scope、tenant 或 canonical path |
| R1 | 模型產生語意內容；Runtime／Store 產生系統 metadata | OpenAI Tool guidance、Anthropic client-side Tool、Pydantic hidden namespace、各 managed API 的 service ID／time | 模型不填 canonical ID、版本、時間、retry 或權限資料 |
| R1 | 自動 Context 有界，完整資料可按需 search／read | OpenAI Sessions／compaction、Anthropic JIT file reads、Microsoft／Google／AWS search、LangGraph Store、Pydantic bounded injection | 日常 Context 不全量灌入；搜尋結果不足時仍能繼續讀取 |
| F1 | 可重試副作用不能重複 | LangGraph idempotent task guidance、AWS client token、Pydantic atomic idempotency、managed operations | 必須滿足 durable idempotency 效果；token、key、receipt 或 task-result 仍待選 |
| R1 | Tool 呼叫與結果以 call ID 對應，失敗明確回傳 | OpenAI call ID＋strict function schema、Anthropic `tool_use_id＋is_error`、LangChain ToolMessage、Pydantic RetryPrompt | 錯誤回到原呼叫；invalid、not-found、conflict、transient failure 不可混為成功 |
| R1 | Memory／Tool output 是低權限資料 | Anthropic tool-result／read-only guidance、Pydantic user-role delimiters、OpenAI Memory 不是唯一規則來源、Microsoft memory-corruption warning | Memory 不能覆蓋 system／Skill／authority policy |

這些共識可以直接約束設計邊界，但 F1 只能成為驗收效果，R1 只能成為模組責任；只有所選框架公開提供、且 failure semantics 相符的 I1／V1 primitive，才可直接寫入實作計畫。

## 4. 只有共同效果、沒有共同底層的議題

| 問題 | 各家不同機制 | 結論 |
| --- | --- | --- |
| 避免 stale overwrite | Anthropic content-hash CAS；Pydantic revision CAS；Google managed current＋revision；LangGraph Store 無 CAS | CAS 是成熟能力，不是單一共同實作 |
| replay 不重複 | AWS client token；Pydantic operation ID；LangGraph task＋應用 idempotency；managed service operation | 需要冪等效果，但 deterministic key、receipt table、token 都是候選 |
| 全量列舉 | Anthropic／AWS opaque cursor；Google pager；LangGraph offset；Pydantic 只有 bounded list | exact inventory 是產品必要效果，底層尚未選定 |
| 更新時序 | OpenAI／AWS 偏背景；Google、LangMem 同時支援 blocking／background；Anthropic agent 可 hot-path read/write | dependency-aware scheduling 是架構結論，不是共同 graph |
| Memory 表徵 | Anthropic files；Google／AWS records；LangGraph KV documents；LangMem collection／profile | `title＋rich content` 是產品語意候選，不是供應商共同 schema |
| 歷史與復原 | Anthropic immutable versions；Google revisions 可停用；其餘公開介面不同 | 第一切片不可把 immutable history 冒充必做共識 |
| 並行 run 排隊 | LangSmith Agent Server 內建；LangGraph OSS 沒有；managed services 各自管理 | per-JD lock／single writer 是產品部署選擇，不是 framework 共識 |
| model repair | Pydantic `ModelRetry`；Anthropic `is_error`；LangChain error ToolMessage；OpenAI strict validation | 「錯誤應可修正」是共同效果；重試次數與 middleware 組合待選 |

## 5. 成熟框架元件對照

| 需求 | 首要成熟候選 | 已覆蓋 | 尚未覆蓋／風險 |
| --- | --- | --- | --- |
| Durable conversation、resume、HITL | LangGraph Checkpointer／Functional API | thread state、task result、interrupt、resume | OSS 不含 run queue；side effect 仍需冪等 |
| Semantic Memory persistence | LangGraph PostgreSQL Store | namespace、CRUD、restart、optional semantic search | 無 CAS／revision／idempotency；listing 只有 offset |
| Managed end-to-end Memory | Microsoft Foundry、Google Memory Bank、AWS AgentCore、Anthropic Managed Memory | formation、scope、CRUD／search／list，部分另有 revisions／commands | cloud／provider lock-in、preview／beta 與本機部署不符；只作機制證據或整套替代候選 |
| Memory extraction／consolidation | LangMem Memory Manager | conversation＋current memories → insert／update／delete | pre-1.0；generic prompt 不保證職務細節 admission |
| Atomic CAS＋durable idempotency | Pydantic Harness `PostgresMemoryStore` | framework 原生 transaction boundary | 第二套 0.x capability；沒有 exact inventory；跨 runtime 接線尚未驗證 |
| Strict Tool schema | Provider structured output＋Pydantic models／LangChain Tools | schema validation、Runtime hidden params | schema 必須維持小型；不能讓模型填系統 metadata |
| Tool error 回饋 | LangChain `ToolErrorMiddleware` | 例外轉為安全的 error ToolMessage | 不自動做語意 repair budget |
| transient Tool retry | LangChain `ToolRetryMiddleware` | exponential backoff、jitter、retry filter | 不能拿來重試 deterministic invalid input |
| model correction | Pydantic `ModelRetry`；或 LangChain error ToolMessage＋call limit | 模型看到精確錯誤後改參數 | 兩者不是同一 runtime primitive；需選一條，不拼裝兩套 loop |
| Conversation compaction | OpenAI server compaction；Anthropic compaction；LangChain `SummarizationMiddleware` | 控制長對話 Context | compaction 不是 Semantic Memory，也不能承擔完整工作細節 |
| Exact scope all-pages | Google／AWS／Anthropic managed pager；LangGraph offset listing | managed 方案有成熟 cursor／pager | 本機 primary stack 尚無 snapshot-grade、opaque-cursor inventory primitive |

### 5.1 實作細節共識矩陣

這張表是後續 plan 的強制入口。每一列都要先指出共識到哪一層，再決定能不能直接使用 framework；不能從「功能必要」跳到自行設計 table／lock／ID。

| 實作面 | 共識層級 | 可直接採用的成熟 primitive | 尚須 Owner 決定／驗證 |
| --- | --- | --- | --- |
| 對話耐久化與 resume | R1＋LangGraph V1 | LangGraph PostgreSQL Checkpointer／task replay | pinned version 的 resume／crash contract test；不得另建 conversation store |
| 長期 Memory formation | R1；無共同演算法 | LangMem Manager；Microsoft／Google／AWS managed formation；provider strict structured output | 本機使用 LangMem 或 provider output；以極小 smoke 比較，不自行寫完整 manager |
| extraction／consolidation 排程 | R1 分層；時序屬 V1／P1 | LangMem hot path／background；Google blocking／background；AWS background | 若本輪後續依賴新 Memory 就等待；不依賴才可背景化。這是 dependency policy，不固定 node 數 |
| scope／namespace | R1 | LangGraph namespace、Pydantic resolver、managed scope | JD scope 由 Runtime 注入；確認 namespace leaf 規則，不讓模型填 |
| Memory 語意表徵 | F1 可修訂內容；無共同 schema | LangMem collection／profile、Anthropic focused files、各家 records | 必須先由上位語意契約決定；不得因某 framework demo 直接照抄欄位 |
| 目前內容 CRUD | I1 家族、語意細節有差 | LangGraph Store CRUD、Pydantic Harness Store、managed item API | `remove` 是 delete 還是 tombstone、no-op result、失敗語意要在 adapter contract 明示 |
| replay／冪等 | F1；無共同 primitive | LangGraph task＋app idempotency、Pydantic atomic operation ID、AWS client token | 只能選一個 owner；目前未裁決，不先自建 receipt table |
| stale-write protection | F1 條件式；V1 差異 | Anthropic hash CAS、Pydantic revision CAS、PostgreSQL conditional update | 第一切片是否真的有 overlapping writer；沒有證據不先加版本平台 |
| 日常召回 | R1 有界＋按需 | LangGraph Store search、LangMem search、Pydantic bounded tools、managed search | 先測非向量／framework search；Qdrant、reranker 不提前施工 |
| 完整盤點 | F1 產品硬效果；無共同本機 primitive | Anthropic／Google／AWS pager；LangGraph offset listing | 本機 exact inventory 路徑未裁決；不能把 top-k 或單頁當完整列舉 |
| Tool schema | R1 | provider strict structured output、Pydantic schema、LangChain Tools | 模型只填最小語意 payload；Runtime-known metadata 全部隱藏注入 |
| invalid input 修正 | R1 call-correlated error；無固定 retry 數 | LangChain ToolError＋call limit，或 Pydantic ModelRetry | 選一套 agent loop；錯誤需安全、精確、可動作，不能回傳 stack trace |
| transient failure | I1 retry family | LangChain ToolRetryMiddleware／provider transport retry | 只重試被分類為 transient 的錯誤；與語意 repair 分離 |
| conflict／stale | R1 reread-before-reason | CAS conflict result＋重新 read | 不盲重送舊 payload；是否再次呼叫模型由 dependency 與 repair budget 決定 |
| compaction | R1 conversation-context 能力 | OpenAI／Anthropic compaction、LangChain SummarizationMiddleware | 只能壓縮對話 Context；不能取代可列舉 Semantic Memory |
| audit／rollback | V1，不是共識硬門檻 | Anthropic versions、Google revisions、LangGraph checkpoint history | 只有產品需求或失敗證據成立才升級；不先自建 immutable history |
| 安全／信任 | R1 | ToolMessage／tool_result data boundary、read-only mounts、Runtime scope | Memory 視為資料；path、scope、大小、輸出與敏感內容由可信 Runtime 驗證 |

### 5.2 框架採用規則

後續每一個實作 task 都必須同時回答六題：

1. 要滿足哪個 F1 產品效果？
2. 官方資料支持到 R1、I1，還是只有某家 V1？
3. 現有成熟 framework 哪個 primitive 可直接承接？
4. 該 primitive 的 transaction、replay、pagination、error 與 version 邊界是什麼？
5. 若仍需 P1 薄 adapter，具體是哪一個必要效果沒有框架覆蓋？
6. 用什麼 framework contract test 證明，而不是靠實作者猜測？

任一題答不出來，就留在研究／Owner 討論，不得進 schema、migration 或 production code。這也表示「用了框架」本身不是通過門檻；只有框架公開保證的行為才算覆蓋，demo 剛好跑通不能升格成 authority contract。

## 6. Store 路徑原本不能直接施工的四個底層選擇

以下分析是目前 Store-first 候選必須正視的邊界。它們不代表第一切片要一次自建所有補丁：先以官方 PostgreSQL Store、現行單一 writer 產品邊界與 contract tests 驗證；只有具體缺口出現，才升級相應機制。

### 6.1 Mutation safety／replay

目前 LangGraph Store 不能原生承接 CAS＋operation idempotency。可比較的成熟路徑只有：

1. **LangGraph task＋Store upsert＋明示 serial writer**：最少依賴，但 idempotency key／single-writer admission 是 Caliburn 映射，不是 Store 原生保證。
2. **Pydantic Harness PostgreSQL Memory Store 作 leaf**：CAS＋冪等由成熟 framework transaction 承接，但會引入 0.x 第二框架，且 exact inventory 仍未解。
3. **採用成熟 PostgreSQL／ORM conditional update primitive**：能做 CAS／idempotency，但需要薄自訂 repository；只有前兩者無法同時滿足產品效果時才討論，不能由實作者直接開表。

在 Owner 選擇前，不把 deterministic key 寫進實作計畫。

### 6.2 Exact inventory

產品要求在完整製作／檢查 JD 時處理全部目前有效 Memory；但所選 LangGraph Store 只有 prefix＋offset，沒有 stable cursor／snapshot。可比較路徑：

1. 改用具有 exact-scope pager／opaque cursor 的 mature substrate；
2. 在明示凍結同 scope mutation 的條件下使用 pinned LangGraph backend，並把 offset 行為當版本相容性契約測試；
3. 若 Memory 數量有可信產品上限，單批 `cap＋1` 並 fail closed；
4. 最後才考慮最小 key catalog／keyset adapter。

其中 2～4 都是產品映射，不是共同底層。現有「checkpoint worklist」不能再被寫成大廠共識。

### 6.3 Semantic writer

LangMem 是目前最接近 extraction＋consolidation 共識的本機成熟元件；但它的 generic instructions 不等於職務分析 admission policy。正式計畫前只允許極小 comparison smoke：

- 同一組 conversation＋current Memories；
- 比較 LangMem Manager 與 provider strict structured output；
- 只看新增、補充、更正、不同案例、矛盾保留與 no-op；
- 不先建立 eval 平台，也不把 smoke 結果包裝成 production 保證。

### 6.4 錯誤與 bounded repair

底層至少分三類，不能使用同一 retry：

- schema／reference／domain invalid：回到同一 Tool call 的安全、精確錯誤，讓模型修正；
- transient network／database failure：framework exponential backoff；
- conflict／stale：重新 read current state 後重新做語意判斷，不能盲重送舊 payload。

LangChain `ToolErrorMiddleware`、`ToolRetryMiddleware` 與 call-limit middleware 已覆蓋大部分 runtime plumbing；是否為 invalid input 提供一次或其他數量的 model repair 是成本／效果政策，尚未形成跨家固定數字。

## 7. 第一切片的修正門檻

在寫實作計畫前，必須先完成：

1. Owner 複核 §10 的 Checkpointer／Store 責任分工；
2. 以真 PostgreSQL Store 驗證 restart／isolation、current-head CRUD、replay 與完整 listing；
3. Store contract 真的失敗時，才回到 §6.1／§6.2 比較 Harness 或其他成熟 substrate；
4. 以極小 smoke 比較 LangMem core／Store manager，決定哪個介面負責 Semantic writer；
5. 只使用所選 runtime 的 error／repair primitive，不混搭兩套 agent loop；
6. 每一個自訂 adapter 都要列出：哪個必要效果沒有任何成熟 framework 直接覆蓋、為何不能不用、如何保持最薄且可替換。

在這五項完成前，[`2026-09-02-memory-foundation-vertical-slice-design.md`](./2026-09-02-memory-foundation-vertical-slice-design.md) 只能視為候選設計，不能直接轉成施工計畫。

## 8. 明確禁止的「看似合理但屬自行發明」

- 因為本機單人就宣稱永遠沒有 replay／並行問題；
- 把 `asyncio.Lock`、single writer、deterministic key 或 checkpoint worklist 說成 LangGraph Store 原生能力；
- 因為有 offset pagination 就宣稱具備 snapshot-grade exact inventory；
- 把 LangMem generic prompt 當成完整職務分析方法；
- 同時採 LangChain Tool loop 與 Pydantic retry loop，卻沒有明確單一 owner；
- 自建 revision、receipt、manifest、outbox、vector index 或 graph，卻沒有 framework 缺口與代表性失敗證據；
- 讓模型填 scope、canonical ID、version、timestamp、source UUID、retry policy 或 Skill execution receipt；
- 把 compaction／summary 當成會保留所有員工工作細節的 Semantic Memory。

## 9. 現行結論

目前已能確認功能共識，也能確認責任分離層級的實作共識；但跨廠商沒有共同的 mutation、inventory 或 storage primitive。§10 的最新候選依官方責任分工把 thread／run state 留在 Checkpointer，把 per-JD durable source 與 current Semantic Memory collection 放在 PostgreSQL Store；具體 Store 邊界仍須 contract tests 證明。

最接近現行完整方向的候選組合仍是：

```text
LangGraph／LangChain 1.x
  = durable workflow、conversation、HITL、Tool error／retry、PostgreSQL Checkpointer＋Store

LangMem core／Store manager（可替換 leaf）
  = conversation＋existing collection 的 extraction／consolidation 候選；以窄 smoke 選一個介面

Pydantic Harness Memory（只作正式競爭候選）
  = LangGraph Store contract 失敗後，CAS＋durable idempotency 的成熟 reference／possible leaf
```

這不是最終 production 選型。任何框架只有在完整覆蓋必要效果、沒有引入第二套 authority，且其官方 primitive 確實優於薄自訂映射時才採用；最新可執行順序以垂直切片設計為準。

## 10. 以「滿分 JD 所需能力」重驗框架覆蓋（2026-09-02）

### 10.1 本輪先修正判斷順序

本輪不再從 Checkpoint、Store 或既有程式往回替產品找理由，而採下列順序：

1. 以 [`滿分 JD 的 LLM 能力研究`](./2026-08-31-perfect-jd-llm-capability-and-mechanism-working-research.md) 的 M1～M11 作驗收標準；
2. 先找 OpenAI、Anthropic 與成熟框架反覆採用的責任分層與 primitive；
3. 再判斷哪個成熟元件能直接覆蓋能力；
4. 只有沒有成熟元件覆蓋、且少了就無法達成產品效果的部分，才允許最薄產品政策；
5. 小型 demo 跑通、程式較少或元件已存在，都不能取代能力證據。

產品唯一目的仍是：長期訪談後產出準確、完整、不重複、抽象層級合理且由員工審核的 JD。Memory 只是達成目的的手段。

### 10.2 最新官方共同方向

| 共同方向 | OpenAI／Anthropic／框架證據 | 對 Caliburn 的限制 |
|---|---|---|
| Conversation／run state 與 durable Semantic Memory 分層 | Codex 把符合資格的歷史對話整理成獨立 generated memory files；Claude 以 memory files／stores 跨 session 保存；LangGraph 明確把 Checkpointer 定義為 thread-scoped short-term state、Store 定義為 long-term application data；Pydantic Harness 使用持久 notebook | 不能因一份 JD 只有一個長期 thread，就把兩種生命週期塞成同一個 checkpoint channel |
| Memory 是多筆聚焦、可按需讀取的內容，不是每輪全量 prompt | Codex 保存 summaries／durable entries／recent inputs／supporting evidence；Anthropic 建議 many small focused files，Memory Tool 按需 view；LangMem collection 與 Harness notebook 都支援搜尋／按需讀取 | 完整細節要耐久保存，但一般回合不必把全部 Memory 注入 prompt |
| 抽取與整併／修訂分開，可新增、更新、刪除或 no-op | Codex 公開分開 extraction／consolidation model；Anthropic 提供 CRUD、current head 與 versions；LangMem manager 以 conversation＋current Memory 做 extraction／consolidation | 可修訂理解應由成熟 Memory manager／Store primitive 承接，不應自行發明一套只追加 facts 的狀態機 |
| Runtime 擁有可信 scope／identity，模型只產生語意內容或 mutation intent | Anthropic store／path 由 application 掛載；LangGraph／LangMem namespace 由 runtime config 提供；Harness namespace 對模型隱藏 | 模型不填 JD scope、canonical ID、version、timestamp、來源 UUID 或 retry policy |
| 有界自動召回＋按需 search/read | Anthropic Memory Tool、LangGraph Store、LangMem search tool、Harness notebook 均採相同方向 | relevance search 服務日常 Context；不能拿 top-k 冒充完整 JD 盤點 |
| 原始來源與衍生 Memory 都保留，各自有生命週期 | Codex generated state 包含 supporting evidence；Anthropic、Google、AWS 都把 conversation／event 與 Memory 分層 | Compaction 或 Semantic Memory 不能取代完整訪談來源；需要時必須能回查原始內容 |

主要官方來源：

- [OpenAI — Codex Memories](https://learn.chatgpt.com/zh-Hant/docs/customization/memories)
- [Anthropic — Managed Agents Memory](https://platform.claude.com/docs/en/managed-agents/memory)
- [Anthropic — Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [LangGraph — Persistence：Checkpointer／Store 分工](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangMem — Core concepts](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)
- [Pydantic AI Harness — Memory](https://pydantic.dev/docs/ai/harness/memory/)

### 10.3 M1～M11 的框架覆蓋矩陣

| 必要能力 | 優先成熟機制 | 覆蓋判斷與仍需證明的效果 |
|---|---|---|
| M1 長期連續性 | LangGraph PostgreSQL Checkpointer＋durable source Store | 框架可覆蓋重啟、續談與 raw source persistence；仍需真 PostgreSQL contract test |
| M2 細節保真 | 聚焦、rich self-contained Store records＋LangMem manager／core | 表徵與修訂 primitive 已有；「所有影響 JD 的細節不遺失」仍需產品指令與代表性 smoke 證明，任何框架都不自動保證 |
| M3 廣度完整性 | durable source＋每個 source 的 Memory processing＋current collection | 框架可保存來源與集合；必須分別驗證 source→Memory 沒漏處理，不能只看 Store 裡已有什麼 |
| M4 可修訂目前理解 | LangMem extraction／consolidation＋Store CRUD/current head | 成熟 primitive 可直接承接 add／revise／remove／no-op；舊 head 不得進一般 Context |
| M5 未知／衝突 | rich semantic content＋Memory manager instructions | 各家支持可修訂內容，但沒有共同的 `unknown_status` schema；第一版先以自足文字保留，不為填欄位猜答案 |
| M6 語意關係 | 自足 records＋bounded search/read＋完整盤點 | 先採共同的 collection／retrieval；沒有證據前不建 knowledge graph |
| M7 工作案例與穩定工作 | collection 中可獨立修訂的 focused records | LangMem collection 可表達兩者；是否要兩種 schema 仍應由代表性資料決定，不能先造兩套 authority |
| M8 有界日常召回 | LangGraph Store search／LangMem search tool；需要時再啟用 semantic index | 框架直接覆蓋有界搜尋與按需 read；ranking 品質仍需小型測試，不提前接 RAG bounded context |
| M9 可驗證完整盤點 | Store 非語意 exact-scope listing＋Runtime 走完所有頁面 | 多家有 listing；LangGraph 是 `limit／offset` 而非 snapshot cursor，須在本專案 single-writer 邊界與 pinned PostgreSQL backend 做完整性 contract test，不能宣稱框架已保證 snapshot |
| M10 原始來源回查 | durable conversation/source Store | 成熟分層可直接承接；不要求模型填 quote offset 或可信 source UUID |
| M11 每份 JD 隔離 | Runtime-resolved JD namespace＋thread ID | 成熟 namespace／scope primitive 可直接承接；模型不能選 scope，且不做跨 JD fallback |

這張表顯示：成熟框架可承接大部分 persistence、CRUD、search、scope 與 durable execution plumbing；真正不能外包的是「什麼職務細節值得形成 Memory」及「如何由全部目前 Memory 產出滿分 JD」的職務分析語意。這兩項屬產品方法／Skill，不代表要自建 Memory 平台。

### 10.4 否決 Checkpointer current collection 候選

[`Memory Foundation 最小垂直切片設計`](./2026-09-02-memory-foundation-vertical-slice-design.md) 原候選把完整 Semantic Memory map 放入 LangGraph Checkpointer。重驗後否決，理由不是它一定不能運作，而是：

1. LangGraph 官方把 Checkpointer 定位為 thread graph-state snapshots，把 Store 定位為 long-term application-defined data；
2. OpenAI Codex、Anthropic Memory Tool／Managed Memory、LangMem stateful integration 與 Pydantic Harness 都使用獨立 generated records／files／Store／notebook 承接長期 Memory；
3. 完整 Memory collection 每次 graph step 隨 checkpoint snapshot 保存，會把長訪談的資料量與 workflow history 綁在一起；LangGraph 官方已明示長 conversation checkpoint 會無界成長，需要 retention／pruning；
4. 容量 gate 只能證明某個測試大小能塞得下，不能證明逐筆搜尋、修訂、列舉與長期生命週期的責任放對位置；
5. 這會把已於 mapping 研究 §9.47 確認的 Checkpoint／Store 分工靜默翻案，而沒有更強產品效果證據。

因此 Checkpointer 保留給 conversation／run state、interrupt／resume、待審工作流與短暫結果；不再作完整 Semantic Memory collection 的正式候選。

### 10.5 修正後的首選組合

```text
LangGraph PostgreSQL Checkpointer
  = 一份 JD 的 conversation／run state、interrupt／resume、故障恢復與短暫工作結果

LangGraph PostgreSQL Store（Runtime 固定每份 JD namespace）
  = 完整可回查的訪談來源
  + 多筆聚焦、詳細、可修訂的 current Semantic Memory

LangMem core／Store manager（先以窄 contract smoke 決定哪個介面）
  = conversation＋少量相關 current Memory
    → add／revise／remove／no-op 的 extraction／consolidation

LangGraph Store search/read
  = 日常有界 automatic recall＋主顧問按需深入

LangGraph Store non-semantic listing
  = 製作／全面檢查 JD 時，逐頁取得該 JD 全部 current Memory

職務分析 Skill＋主顧問 LLM
  = 使用全部目前理解判斷 JD 的新增、修訂、刪除、重組與缺口
```

這個組合優先沿用同一套 LangGraph／LangChain runtime 與官方 PostgreSQL primitive，避免混入第二套 agent loop。Pydantic Harness Memory 保留為正式競爭候選：其 notebook、CAS、idempotency 與 bounded injection 更完整，但目前仍是 0.x、listing 無 iterate-all 契約；除非窄 contract test 證明 LangGraph Store 無法滿足必要能力，第一切片不混用。

### 10.6 哪些不是「大廠共識」，不可偷渡成事實

- `topic＋content` 是目前最薄候選語意形狀，不是 OpenAI／Anthropic 公開共同 schema；
- 每筆 immutable revision、CAS、receipt table、inventory manifest 與強制 per-record lineage 都不是跨家第一版共同硬要求；
- LangGraph Store 的 offset listing 不是 snapshot-grade inventory；完整性必須在所選版本與單一 writer 產品邊界下實測；
- LangMem 可以提供抽取／整併 mechanism，但 generic prompt 不等於 Caliburn 的職務分析方法；
- 「所有 current Memory 都被列入一次 JD 作業」是 Caliburn 為完整 JD 必須加上的產品效果，不是任何 Memory 服務自動保證「JD 已完整正確」。

### 10.7 下一個正確步驟

在 Owner 複核本節前，不寫 production code。若方向確認，先重寫第一切片而不是修補舊稿：

1. 無模型 Store contract：JD namespace 隔離、CRUD/current head、restart、typed result、非語意全量列舉與 replay 不重複；
2. 極小 LangMem comparison smoke：同一組繁中訪談＋existing Memories，比較 core manager 與 Store manager 對新增、補充、更正、不同案例、unknown／conflict、no-op 與未提及細節保留；
3. 只選結果較好且沒有第二 authority 的 LangMem 介面；
4. 通過後才另寫日常 recall／按需 read 與 complete Memory→JD audit 切片；
5. 若官方 Store primitive 在 contract test 真的失敗，停止並帶實證比較 Harness 或其他成熟 substrate，不在同一 task 自行造 repository／manifest／CAS 平台。

本節是能力與框架覆蓋校正，不是 ADR、schema 或施工授權。
