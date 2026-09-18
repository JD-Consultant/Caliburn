# Memory Read Spike：共識、框架與實驗邊界最終稽核

- Topic：`MEM-Q004`
- Stage：G4 plan review
- 狀態：**Revision 2 audit complete；Product Owner 已於 2026-09-03 核准 G5 isolated spike**
- 稽核對象：[`2026-09-03-memory-routing-canonical-read-isolated-spike.md`](../plans/2026-09-03-memory-routing-canonical-read-isolated-spike.md)
- 核准條件：由整體到細節均先辨識大廠／框架共識；未經討論的 Caliburn 自訂作法不得冒充共識。

本文是薄型稽核索引，不重抄既有 Memory 研究。完整產品效果、跨家證據、方案比較與 read contract 分別由下列文件負責：

1. [`framework-independent-memory-contract.md`](2026-09-01-framework-independent-memory-contract.md)：M1～M11 與產品效果；
2. [`memory-conversation-and-semantic-responsibility-reconciliation.md`](2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md)：conversation／Store 責任；
3. [`memory-similar-case-detail-and-consolidation-reconciliation.md`](2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md)：相似案例與可修訂理解；
4. [`memory-canonical-conversation-search-read-reconciliation.md`](2026-09-03-memory-canonical-conversation-search-read-reconciliation.md)：canonical source deep-read；
5. [`memory-routing-canonical-read-and-isolated-spike-research.md`](2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md)：`MEM-Q004` contract 與 G5 假設。

## 1. 判定語言

| 標記 | 意義 |
|---|---|
| `共同方向` | OpenAI／Anthropic 與至少一個成熟 framework 的公開機制支持相同責任或效果；不宣稱內部實作完全相同 |
| `框架能力` | pinned LangChain／LangGraph／Store 已直接提供，不應自製 plumbing |
| `Caliburn mapping` | 為本產品效果做的命名、scope、安全或結果形狀；不是 vendor 標準，但已經 Owner 討論／核准 |
| `實驗變數` | 只為讓一次 spike 可重現而凍結；不得升格成 production 決策 |
| `Unknown` | 官方文件不能回答，且應由本 spike 量測 |

## 2. 從大到小的最終矩陣

| 層 | 計畫內容 | 判定 | 框架承擔 | 稽核結果 |
|---|---|---|---|---|
| 產品流程 | 完整訪談來源＋可修訂 Semantic Memory＋有界召回＋必要時深讀來源 | `共同方向`＋`MEM-D001～D003` | Checkpointer、Store、Tool loop | 通過；spike 只驗 read path，不冒充完整 Memory 系統 |
| 最終完整性 | 最終全面製作／檢查 JD 才列舉全部 current Memory | Caliburn 必要效果；不是日常 retrieval 共識 | Store 無 query listing／pagination 可提供 primitive | 明確 out of scope；不得由本次 PASS 宣稱 M9 成立 |
| Conversation authority | 每份 JD 的完整、有序 conversation 由 Checkpointer 保存 | Owner 核准 mapping；與 durable conversation／thread state 的共同責任相符 | `AsyncPostgresSaver`、stable message IDs | 通過；不再另存 employee-source 文字副本 |
| Semantic authority | focused、current、可修訂 Memory 放 Store | Owner 核准 mapping；Store 是 framework 的 application-defined durable data | `AsyncPostgresStore` | 通過；本次只 seed，不驗 writer／manager |
| Context | 模型每次只看近期訊息、導覽、按需結果；不刪 canonical state | `共同方向` | transient model-context projection | 通過；「最後 6 則」只是實驗變數 |
| 導覽 | 從 current Memory title 重建小型主題表 | Caliburn mapping | Store exact-scope listing＋deterministic projection | 通過；不是第二份 persisted Memory |
| 搜尋 | `search_semantic_memory(query)` 回少量、逐筆完整 Memory＋輕量 refs | progressive disclosure 是共同方向；名稱與結果 shape 是已核准 mapping | Store semantic index／`asearch` | 通過；`top 4`、embedding 型號皆是實驗變數 |
| 深讀 | `read_conversation_context(message_ref)` 回 canonical 最小問答窗口 | canonical deep-read 是共同方向；message-ref adapter 與窗口是 mapping | Saver latest state＋stable ID lookup | `Unknown`；正是 spike 要驗證的薄 adapter |
| Tool schema | 每個 tool 只讓模型填一個語意字串；scope／limit／window 由 Runtime 注入 | OpenAI／Anthropic 的窄 schema、strict、少讓模型填已知值方向 | Pydantic、`ToolRuntime`、strict provider payload | 通過 |
| Tool loop | 模型請求 → framework 執行 → `ToolMessage` 回模型 | `共同方向` | `StateGraph`＋`ToolNode` | 通過；不得手寫 agentic while loop |
| Tool error | 無效參數與可預期 read error 回穩定資料；未知 exception 停止 | 穩定可修正錯誤是共同方向；code 名稱是 mapping | 一個 typed `ToolNode(handle_tool_errors=...)` | 修正後通過；不再疊加 `BaseTool.handle_tool_error` |
| Scope | 模型不能填 document／thread；Runtime 只查目前文件 | OpenAI 已知參數由程式注入方向＋Caliburn 隔離要求 | `ToolRuntime.context`／Store namespace | 通過；exact namespace equality guard 是必要薄 adapter |
| Search→read linkage | read 只接受本次 search 揭露的 ref | Caliburn 安全／流程 mapping，不是跨家標準 | 暫態 graph state | 修正後通過；tool graph 不掛 checkpointer，因此 refs 不跨 run 累積 |
| Provider contract | 實際送出的兩個 tool 都是 strict、不可平行 | 官方 strict 契約＋本流程的順序要求 | `ChatOpenRouter.bind_tools`，以 HTTP capture characterization | 通過；不能只看本地 schema |
| 成本 | 一個 Luna scenario、固定 calls／tokens／timeout／USD 上限 | 實驗治理，不是 Memory 架構 | provider usage receipt＋runtime counters | 修正後通過；價格無法建立保守上界便不發模型 call |
| Growth | 40／100／200 rounds 量 Checkpointer bytes／latency | `Unknown` | PostgreSQL Saver＋framework tables | 通過；只記數據，不預設 production 門檻 |

## 3. 本次發現與處理

### `MEM-AUD-001` — P1：持久來源與單次 agent messages 混層

- 位置：舊計畫 Task 3.1、3.3。
- 問題：`ToolNode` 必須把 AI tool call 與 `ToolMessage` 加入其 message state；若直接使用保存 80 則訪談的同一持久 channel，就不可能同時宣稱「tool loop 已執行」和「checkpoint messages 仍恰好 80 則」。
- 產品影響：實作者可能污染 synthetic canonical interview，或為了讓測試過而不實際保存正確 tool linkage。
- 修正：Task 2 的 PostgreSQL Checkpointer 單獨保存 80 則 canonical fixture；Task 3／live smoke 使用**不掛 checkpointer的單次暫態 `StateGraph`**，只把最後六則 canonical messages 投影進模型。Tool 透過 trusted runtime context 讀相同 Saver／Store。這次 spike 不測 agent-run resume，不能宣稱已證明。
- 狀態：已修正計畫。

### `MEM-AUD-002` — P1：強迫 tool call 無法證明 routing

- 位置：舊計畫 Task 4.2 live prompt。
- 問題：直接命令「先 search，再 read」只證明 plumbing 與模型可組 query，不能證明模型依工具描述和任務需要選對路徑。
- 產品影響：實驗可能 PASS，但日後真實訪談模型根本不會在需要時查 Memory。
- 修正：不指定 tool 名稱或固定呼叫步驟；題目本身要求一項只有 canonical conversation 才有的精確原句。模型必須依工具的「何時使用」描述自行 search，並在需要核對原句時 deep-read。單次 smoke 仍只支持這一代表情境，不泛化成所有 routing 品質。
- 狀態：已修正計畫。

### `MEM-AUD-003` — P2：錯誤處理重疊

- 位置：舊計畫 Task 3.1。
- 問題：同時指定 `ToolNode`、`ToolException` 與 `BaseTool.handle_tool_error`，增加兩層格式化和行為差異。
- 產品影響：同一錯誤可能得到不同 payload，或意外吞掉真正程式錯誤。
- 修正：explicit graph 統一由一個 typed `ToolNode(handle_tool_errors=...)` 處理 `ToolInvocationError` 與明列的 expected read errors；handler 只回穩定 JSON。其他 exception 原樣向外拋出並停止。
- 狀態：已修正計畫。

### `MEM-AUD-004` — P2：成本上限不能靠模糊 catalog 價格

- 位置：舊計畫 Task 4.2。
- 問題：模型清單的彙總價格不必然足以推得指定 endpoint 的保守最高成本。
- 產品影響：文件宣稱 USD hard cap，但第一個請求前其實無法證明。
- 修正：只採官方 model／endpoint metadata；若 chat、reasoning、embedding 任一項無法依 input/output caps 建立保守上界，就不送第一個 paid request。每次回應另保存官方 `usage.cost`，在下一 call 前再次檢查。
- 狀態：已修正計畫。

## 4. 刻意保留但不得冒充共識的項目

以下都已討論或屬可重現實驗所需，無須再開產品題，但 report 必須標成 experiment-only：

- 40 組／80 則 synthetic conversation；
- 三筆 seeded Memory；
- 最近六則 context；
- search 最多四筆；
- 相鄰「前一顧問問題＋目標員工回答」窗口；
- `openai/text-embedding-3-small`、1536 dimensions；
- Luna medium、3 model calls、2 tool calls、1200 output tokens／call、USD 0.20；
- stable message reference 的字串格式；
- `invalid_input`、`reference_unavailable`、`temporary_failure` 等 public error code；
- same-ID same-content no-op、same-ID different-content reject 的 fixture intake guard。

這些值若 spike 成功，也不會自動進 successor ADR 或 production。

## 5. Framework reuse 結論

本計畫沒有自製下列成熟能力：

- checkpoint／restart／state history：LangGraph PostgreSQL Saver；
- namespace key-value／semantic search：LangGraph PostgreSQL Store；
- embedding interface：LangChain embedding adapter；
- tool schema／validation：Pydantic＋LangChain tools；
- scope／Store injection：`ToolRuntime`；
- tool-call/result linkage 與 error `ToolMessage`：`ToolNode`；
- graph loop 與 step bound：`StateGraph`／recursion limit；
- provider request：`langchain-openrouter`＋OpenRouter SDK。

仍需薄 Caliburn code 的只有：exact namespace equality、Saver message-ID lookup 的最小窗口、安全 result view、synthetic fixture/rubric 與實驗 stop conditions。這些是產品 scope 或框架缺少單一 message read primitive 所造成，不能假稱 framework 內建，也沒有建立第二套 Memory framework。

## 6. 直接官方來源

- OpenAI：[Function calling／strict 與窄工具建議](https://developers.openai.com/api/docs/guides/function-calling)、[Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)、[Compaction](https://developers.openai.com/api/docs/guides/compaction)
- Anthropic：[Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)、[How tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)、[Troubleshooting tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/troubleshooting-tool-use)
- LangChain／LangGraph：[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[Stores](https://docs.langchain.com/oss/python/langgraph/stores)、[Tools](https://docs.langchain.com/oss/python/langchain/tools)、[Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)、[`ToolNode` reference](https://reference.langchain.com/python/langgraph.prebuilt/tool_node/ToolNode)
- OpenRouter：[Model catalog API](https://openrouter.ai/docs/api/api-reference/models/get-models)、[Usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting)

## 7. Verdict

修正後計畫沒有剩餘的未揭露產品選擇，也沒有把 Caliburn mapping 或實驗常數冒充大廠共識。它只足以進入 G5 isolated spike；**不授權 production、Memory writer、完整 JD audit、UI、RAG 或 ADR 翻案**。

核准結果：Product Owner 已於 2026-09-03 核准 revision 2 plan 執行一次隔離 spike。下一個 gate 是實驗 report review；結果不得自行擴大為 production 授權。
