# LLM machine effects 與同輪並列結果工作設計

- Decision ID：`LLM-Q014`
- 狀態：**G4.1／G4.2／G4.3b-1～4e Product Owner 已核准；G4.3b-4f 待討論**
- Production 效力：**無**；不得據此修改 production，仍須完整 G4、successor ADR 與 implementation gate
- 決策入口：[`../current-decisions.md`](../current-decisions.md)
- 依賴決策：[`MEM-Q005`](./2026-09-04-memory-persistence-and-jd-effect-reconciliation.md)

## 1. 本節只決定什麼

本節只決定一次 bounded consultant invocation 內，Semantic Memory mutation 與 JD 待審變更由誰提出、透過什麼 framework primitive 執行，以及是否要固定先跑第二個 Memory model。

本節不決定 exact Tool schema、重試次數、背景 queue／worker、UI、模型與價格、Reference RAG、production migration 或任何 production code。

## 2. 官方事實與不能過度宣稱的地方

1. OpenAI 與 Anthropic 的 client Tool contract 都是：模型提出 Tool call，application 執行，將對應結果送回模型，模型再回答或繼續呼叫 Tool。Tool call 不是模型自行完成 side effect。
2. Anthropic 明確說多個 Tool call 的執行順序由 application 決定；獨立讀取可並行，具有 side effect、共享狀態或排序依賴的操作可以依序執行。每個呼叫仍須得到對應成功或錯誤結果。
3. LangMem 提供兩條不同路徑：
   - `create_manage_memory_tool`／`create_search_memory_tool`：主 Agent 直接使用的 Store Tool；
   - `create_memory_manager`／`create_memory_store_manager`：由另一個 Memory model 根據 conversation 與既有 Memory 做 extraction／consolidation 的 manager。
4. LangChain／LangMem 將 hot path 與 background 都列為正式模式。Hot path 可立即使用新 Memory，但增加主流程負擔與延遲；background 不阻塞主要回覆，但結果較晚可用且需要觸發與失敗管理。公開資料不存在「所有產品一律選其中一種」的跨廠規則。

因此，下節是 Caliburn 依產品效果做的 mapping，不冒充 OpenAI、Anthropic 或 LangMem 的唯一推薦架構。

## 3. Product Owner 核准的 G4.1 設計

### 3.1 一個根 Agent loop

第一版維持一個 LangChain `create_agent` compiled graph 作唯一根 model↔Tool loop。每則被接納的員工訊息啟動一個 bounded logical invocation；同一 invocation 內允許多個 model／Tool steps，但不建立第二套 agent loop。

### 3.2 Memory 與 JD 都走 Tool，但責任不同

- Semantic Memory 讀取優先使用已核准的 `search_semantic_memory(query)` 與 `read_conversation_context(message_ref)` 路徑。
- Semantic Memory 的一般 extraction／consolidation 由背景 manager 候選承接；主顧問的 direct Memory Tool 只保留給已知 stale Memory 的窄幅 live repair。這是 §13 已核准的生命週期責任，具體 framework wiring、名稱與最小 schema 留到後續 gate。
- JD 新增、修改、移動、解除關聯與刪除使用 Caliburn application-specific JD editing Tools；Tool 只形成員工可審核的 JD 變更，不得自行變成核准文件。
- 對員工的內容使用 canonical assistant message，不把人類可讀回覆塞進大型 structured output。

`create_memory_manager` **不**包成主顧問 Tool，也不固定在每個實質回合前先執行。原先「第一版不加入 background consolidation」的限制已被 §13 的 G4.3b-4a 裁決取代；背景整理現在是必要責任，但何時 debounce、如何排程及由哪個 framework primitive 最終承接仍未核准為 production 實作。

### 3.3 同一 Context，兩個並列 machine effects

```text
canonical conversation + relevant current Memory + latest JD + current input
                                  ↓
                        one bounded create_agent run
                     ↙              ↓                 ↘
       optional live Memory repair  assistant message  optional JD editing Tool
                     ↓                                  ↓
              Memory result                       pending-JD result
                     └──────── results return to the same loop ────────┘
                                      ↓
                         invocation completes／background
                         extraction＋consolidation may be scheduled
```

兩類 Tool call 由同一個 Agent Context 形成，但各自驗證、各自產生結果。Runtime 可以為 side effects 採可預測的依序執行，卻不得把「執行順序」誤寫成「Memory 成功是 JD 的語意前置條件」。Memory 技術性失敗不阻擋自身驗證通過的 JD 待審變更；精確行為沿用 `MEM-Q005`。

Framework 的 thread／run／Tool-call metadata 用來關聯同一 invocation；scope、namespace、新 ID、版本、時間、budget、retry state 等可信欄位由 Runtime／framework 供應，不讓模型捏造。模型只填必須由語意判斷的 Memory 內容／既有目標選擇與 JD operation 內容。

### 3.4 已被後續 G4.3b-4a 取代的早期候選

| 早期候選 | 目前狀態 | 原因 |
|---|---|---|
| 每輪固定先跑 `create_memory_manager` | 仍不採 | 每個實質回合固定增加獨立 Memory model call，且會在片段尚不完整時重複整理。 |
| 把 `create_memory_manager` 包成主顧問 Tool | 仍不採 | 形成主模型→Tool→另一模型的巢狀呼叫；背景 manager 應是 runtime lifecycle，不是模型可見 Tool。 |
| 第一版完全不加入 background manager | 已被取代 | 無法承接已核准的 extraction／consolidation 責任；§13 改採即時讀取、背景整理與窄幅 live repair 三路協作。 |

## 4. G4.2 官方事實：Tool 失敗不是同一種東西

### 4.1 Provider 的共同契約很小

OpenAI Function Calling 與 Anthropic client Tool 都要求 application 將每個 Tool call 的結果以原 call ID 回傳，模型再決定回答或繼續呼叫。OpenAI 允許 application 自行決定 result 字串格式；Anthropic 以 `is_error: true` 表示 Tool 執行錯誤，並要求錯誤內容說清楚發生什麼事與可採取的下一步。兩家都沒有要求 application 發明一套跨 Tool 的五狀態模型輸出 schema。

Anthropic 另明確要求一個 Tool call 對應一個 Tool result；LangChain 的 `ToolMessage.tool_call_id` 採相同配對方式，`status` 只有 `success`／`error`。因此「成功但沒有資料變更」應是成功結果中的語意，不應偽裝成 error。

### 4.2 Framework 已提供的責任

目前 LangChain／LangGraph stable 路徑已提供：

- `ToolNode`／`create_agent`：執行 Tool 並將結果配回同一 call ID；argument binding／validation error 在 Tool 執行前轉成 error `ToolMessage`；
- `ToolRetryMiddleware`：只對指定 exception／指定 Tool 做有限重試、backoff 與 jitter；重試耗盡後可回 error `ToolMessage` 或拋出；
- `ToolErrorMiddleware` 或 `wrap_tool_call`：只將明確認得、可安全交給模型修正的 exception 轉成 error `ToolMessage`；未處理 exception 保持拋出，避免把 stack trace、secret 或未知錯誤送進模型；
- `ModelCallLimitMiddleware`／`ToolCallLimitMiddleware`：限制單次 invocation 的 model／Tool 次數，避免修正 loop 失控；
- Checkpointer／trace：保存 Tool call／result 與 run 狀態，供恢復、觀測與除錯；不必把完整技術 receipt 都塞進模型 context。

LangGraph 官方的 error taxonomy 亦依「誰能恢復」分流：暫時性錯誤由系統重試；模型可修正錯誤回給模型；需要人補資料的情況交給人；未知錯誤交給開發者。這是共識分類；Caliburn 第一版已另行決定，員工語意不清時以一般顧問問題正常完成本輪、下一則訊息另開 invocation，不採通用 durable interrupt。

### 4.3 不能從官方資料過度推論

- OpenAI 與 Anthropic 沒有替 Caliburn 定義 domain error code、員工畫面文案或 JD／Memory 的 no-op 語意。
- LangChain middleware 能執行重試與錯誤回傳，但不能自行知道某 exception 是「重跑安全」還是「重複寫入」；side-effect Tool 的 idempotency 與 exception 分類仍是 application contract。
- LangGraph `ToolMessage.status` 的二值狀態不等於產品只能顯示成功／失敗；較細的 invocation receipt 可以留給 Runtime／UI，但不必成為模型必填欄位。

## 5. G4.2 三個候選

### 5.1 方案 A：每個 Tool 都回傳大型統一 envelope

例如要求每個 Tool 都填 `status／code／retryable／changed／message／version／details`。優點是表面上一致；缺點是重複 framework 已有的 call ID 與 success/error，增加 schema、模型 context 與每個 Tool 的樣板，而且把「誰該重試」誤交給 Tool payload。這不是 Provider 要求，**不建議**。

### 5.2 方案 B：framework-native result＋依恢復者分流（建議）

模型只看到下一步所需的最小結果；Runtime／framework 保留完整 receipt：

| 情況 | Tool／Runtime 行為 | 模型接下來做什麼 | 對員工的結果 |
|---|---|---|---|
| 成功且有變更 | 正常 `ToolMessage(status=success)`，內容只摘要已形成的效果 | 可繼續其他分析／Tool 或回答 | 顯示實際已形成的 Memory／JD 待審結果 |
| 成功但合法 no-op | 仍是 success，明說目前狀態已符合、沒有重複新增 | 不要用同參數反覆呼叫 | 不製造假的變更或錯誤 |
| 模型可修正 | validation／known domain error 以安全、具體、可操作的 error `ToolMessage` 回傳 | 在同一 bounded loop 修正參數或改用正確 Tool | 修正成功才顯示效果；不顯示內部嘗試 |
| 暫時性 Runtime／I/O 失敗 | 只對已知 transient 且 replay-safe 的操作由 middleware 有限重試 | 重試期間不要求模型猜測；耗盡後才收到安全結果或 invocation failure | 保留已成功的 sibling effect，說清楚哪一部分未完成 |
| 未知／terminal failure | 不將原始 exception 塞給模型；讓它拋到 invocation boundary 並記錄 trace | 不反覆猜參數 | 聊天不得永久鎖住；回報本輪哪些完成、哪些未完成，允許下一則訊息繼續 |

模型可修正的 error 內容只需要：哪個操作失敗、哪項輸入／目前狀態不成立、允許的下一步。它不包含 stack trace、SQL、secret，也不要求模型填 retry flag。員工語意矛盾、資料不足或顧問想確認理解，屬正常對話，不偽裝成 Tool error。

同一 model step 若提出多個呼叫，每個 call 都必須得到自己的 result。Memory 與 JD 是 failure-isolated sibling effects：一邊 terminal failure 不抹掉另一邊已驗證的成功；最終 assistant message 只能陳述實際 receipt，不能把部分成功說成全部成功，也不能全部退化成「分析錯誤，請重試」。

bounded repair 使用 framework 的 invocation-level model／Tool call limit；精確數字、可重試 exception allowlist、idempotency key 與最小 result 內容留到後續 contract，不在本節先猜。

### 5.3 方案 C：另建 effect state machine／補償 graph

每個 Memory／JD effect 都建立自訂 workflow state、補償節點與重放流程。它能支援真正跨系統 transaction 或長時間背景工作，但第一版的兩個並列效果不要求原子一致，也沒有 saga；會增加第二層 orchestration。**目前不建議**，只有未來出現不可逆外部 side effect 或跨 invocation unfinished workflow 才重開。

### 5.4 Product Owner 裁決

Product Owner 於 2026-09-04 核准方案 B。它直接使用 Provider Tool result loop 與 LangChain stable middleware，不自訂第二套 agent loop，也不把 Runtime 欄位推給模型；同時保留 Caliburn 必須定義的最薄 domain 邊界：哪些失敗可由模型修、哪些只可由 Runtime 重試，以及 sibling effect 的真實完成狀態。

這項裁決取代 [`2026-08-28-llm-authored-field-contract-audit.md`](./2026-08-28-llm-authored-field-contract-audit.md) §19.3「模型可見共同小型 envelope」的舊候選。舊文的官方 Tool-result pairing、錯誤分類與 domain diagnostics 研究仍可作證據；但不得再要求所有 Tool 回傳自訂 `status／workspace_effect／errors[]` 外殼。成功／錯誤與 call pairing 由 framework-native `ToolMessage` 表達，模型只取得修復下一步真正需要的最小內容。

## 6. G4.2 完成時的下一個 blocking question（歷史快照）

以下 preflight 已由後續 §8、§10～§12 依序處理；目前 blocking question 一律以本稿
最末節及 `docs/current-decisions.md` 為準，不得把這段歷史快照重新當成待決事項。

```text
Topic ID: LLM-Q014
Current stage: G4.3b；G4.1／G4.2／G4.3a 已核准
Binding decision:
  一個 create_agent 根 loop；主顧問直接使用 LangMem Memory Tool 與 JD Tools；
  不固定先跑 create_memory_manager；Memory／JD 是 failure-isolated sibling effects；
  Tool result 使用 framework-native success/error，並依真正恢復者分流。
This turn's only blocking question:
  除已核准的 Runtime-issued id 外，Semantic Memory 的 title、content 與
  message_refs[] 各自應是 canonical data、derived projection、hidden artifact，
  還是 model-visible Tool result？先逐欄裁決，不同時展開 JD Tool。
Out of scope:
  JD mutation Tool、其餘 production JSON／資料表、retry 次數、UI 視覺、provider 修復、
  background worker 與 production code。
```

## 7. 直接來源

- [OpenAI — Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI Agents SDK — Tools／function Tool error handling](https://openai.github.io/openai-agents-python/tools/)
- [Anthropic — How tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)
- [Anthropic — Handle tool calls／`is_error`](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)
- [Anthropic — Parallel tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use)
- [LangChain — Tools／Tool return values and error handling](https://docs.langchain.com/oss/python/langchain/tools)
- [LangChain — `ToolMessage`](https://reference.langchain.com/python/langchain-core/messages/tool/ToolMessage)
- [LangChain — `ToolRetryMiddleware`](https://reference.langchain.com/python/langchain/agents/middleware/tool_retry/ToolRetryMiddleware)
- [LangChain — `ToolErrorMiddleware`](https://reference.langchain.com/python/langchain/agents/middleware/tool_error/ToolErrorMiddleware)
- [LangChain — `ToolCallLimitMiddleware`](https://reference.langchain.com/python/langchain/agents/middleware/tool_call_limit/ToolCallLimitMiddleware)
- [LangGraph — Thinking in LangGraph／error taxonomy](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph)
- [LangChain — Memory overview](https://docs.langchain.com/oss/python/concepts/memory)
- [LangMem — Memory Tools API](https://langchain-ai.github.io/langmem/reference/tools/)
- [LangMem — Memory Management API](https://langchain-ai.github.io/langmem/reference/memory/)
- [`MEM-Q005` 本地決策](./2026-09-04-memory-persistence-and-jd-effect-reconciliation.md)

## 8. G4.3a：Memory 更新目標不能靠模型猜

### 8.1 已查證的 framework／Provider 事實

1. LangMem 官方 `create_manage_memory_tool` 已提供單一 `manage_memory` Tool；模型可填的原生欄位是 `content`、`action=create|update|delete` 與可選 `id`。其中 update／delete **必須**提供既有 Memory `id`，create 則不得提供；namespace 由 Runtime config 決定。
2. LangMem 官方 search Tool 的原始結果含 Store Item 的 key／內容與其他 metadata；框架因此能讓 Agent 先搜尋，再使用既有 key 更新。先前 `MEM-Q004` 為縮小模型 context，刻意把 Store key／`memory_ref` 全部從搜尋結果移除。
3. Anthropic 官方 Memory Tool 採相同的「先看目錄／內容，再以模型可見 locator 操作」形狀：Claude 先取得 `/memories/...` path，後續 view／replace／delete 都將該 path 原樣帶回。Anthropic 的一般 Tool 指南也建議回傳模型下一步真正需要的 stable identifier，而不是洩漏整包 backend metadata。
4. OpenAI 官方要求不要讓模型填 application 已知的 scope／identity，也要求以 enum／object 排除非法狀態；但「多筆搜尋結果中要更新哪一筆」是模型的語意選擇，在模型選定前並不是 Runtime 已知值。Runtime 應供應可複製的 locator，而不是要求模型猜 UUID、重填 namespace 或靠 title 模糊解析。
5. LangChain `ToolRuntime` 可將 thread、context、Store、run／retry metadata 與 Tool call ID 隱藏注入，因此 document scope、namespace、版本、時間、權限與 retry state 都不應進模型 schema。

這些資料支持的是一個共通機制：**模型看得到足以選定既有資源的穩定 reference；application 隱藏並驗證執行 scope 與技術 metadata。** Provider 沒有規定 Caliburn 欄位必須叫什麼；LangMem 原生欄位叫 `id`，Anthropic 的 file-backed Memory 則叫 `path`。

### 8.2 與既有 `MEM-Q004` 的精確衝突

`MEM-Q004` 目前核准的 `search_semantic_memory(query)` 每筆結果只有：

```text
title + complete content + message_refs[]
```

並明文排除 Store key／`memory_ref`。這足以「讀」，卻無法直接配合已核准的 LangMem 原生 `manage_memory(update/delete)`：模型知道哪筆內容要修，卻沒有可合法回傳的 target `id`。

這不是 production bug，也不是推翻整個 read contract；它是 G4.1 選定 native LangMem manage Tool 後新暴露的介面相依。若不處理，只剩下用 title／序號模糊解析、另建 selection state，或包一套自訂 update Tool，三者都比提供既有 stable reference 更複雜。

### 8.3 候選

| 方案 | 做法 | 判斷 |
|---|---|---|
| A（建議） | 搜尋命中的每筆 Memory 多回一個 Runtime 產生、LangMem-compatible 的 `id`；模型只能把已看到的 `id` 原樣帶回 update／delete。Runtime 驗證它仍存在且屬於目前 JD namespace；scope、namespace、version、timestamp、score 仍不可見。 | 最貼近 LangMem 原生契約與 Anthropic locator pattern；只窄幅重開 `MEM-Q004` 一個 result 欄位。 |
| B | 不回 ID，讓模型以 title／第幾筆要求更新，再由 Runtime 猜對應 Store key。 | title 可重名、排序會變，增加模糊 resolver；不是 framework 原生形狀。 |
| C | 先呼叫 `select_memory` 將 target 暫存到 hidden state，再呼叫無 ID 的自訂 update Tool。 | 多一個 Tool、一次 round trip 與 selection state，仍需 Runtime 最後解析 ID；目前沒有需求證明值得。 |

方案 A 不表示「讓模型產生 ID」。ID 由 Store／Runtime 產生；模型只像複製 `message_ref` 或 Anthropic memory path 一樣，選擇並回傳自己實際讀到的 reference。Create 仍由 Runtime 產生新 ID；模型永遠不填 document ID、employee ID、thread ID、namespace、新 ID、版本或時間。

在 Owner 裁決前，`MEM-Q004` 原 read shape 維持有效；本節只是把新發現的相容性缺口、官方依據與最小候選寫清楚。G4.3a 未核准前，不進 JD Tool surface，也不寫 production schema。

### 8.4 Product Owner 裁決

Product Owner 於 2026-09-04 核准方案 A，窄幅修正 `MEM-Q004`：每筆模型可見的 Semantic Memory 搜尋結果必須帶一個 Runtime／Store 產生、LangMem-compatible 的既有 `id`。模型只能選擇並原樣帶回自己實際看過的 `id`；create 的新 ID、目前 document／thread、namespace、version、timestamp、score 與執行 metadata 仍由 Runtime 擁有並驗證。

這項裁決只解決既有 Memory update／delete 的 target identity；它尚未核准 `title／content／message_refs[]` 的最終責任、production JSON schema 或 JD Tool surface。下一步改為 G4.3b，逐欄確認哪些是 Memory 本體、衍生 routing projection、來源 pointer 或模型不需要看到的 artifact。

### 8.5 本節新增直接來源

- [OpenAI — Function calling：tool design 與 Runtime-known arguments](https://developers.openai.com/api/docs/guides/function-calling)
- [Anthropic — Define tools：consolidation、stable identifiers 與 high-signal result](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)
- [Anthropic — Memory tool：以 model-visible path 定位 read／update／delete](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [LangChain — Tools／`ToolRuntime` hidden injection](https://docs.langchain.com/oss/python/langchain/tools)
- [LangMem — Memory Tools API：native search／manage signatures](https://langchain-ai.github.io/langmem/reference/tools/)

## 9. G4.3b 前置稽核：先裁決 read topology，才能裁決欄位

2026-09-04 回查 framework 最新官方介面後，確認目前不能直接從
`id／title／content／message_refs[]` 逐欄往下裁決。先前討論已確立
「小型導覽 → 按需搜尋細節 → 必要時回讀原始對話」的效果目標，但仍混合了三套
不同的官方 read pattern；若不先拆開，會把 routing、Memory 本體與 conversation
provenance 錯塞進同一個 schema。

### 9.1 framework／Provider 實際提供什麼

1. **LangMem native search-first**：`create_search_memory_tool` 接受 query，直接回傳
   serialized Memory 內容與 raw Store Item；官方 model Tool 只有 manage／search，沒有
   另一個 `read_memory(id)`。LangGraph Store 本身有 application-side `search`／`get`
   primitive，但若要變成模型可呼叫的 read Tool，需要 application 組一個薄 adapter。
2. **LangGraph Checkpointer 是 conversation state owner，不是 conversation search
   engine**：官方可用 `get_state`／`get_state_history` 讀 thread snapshot，
   `MessagesState`／`add_messages` 會保存 message ID；但官方沒有把「依語意搜尋舊訊息」
   或「由某筆 Semantic Memory 自動定位原始訊息」做成內建 Tool。
3. **Anthropic Managed Memory 採 basic-list／full-read**：list 預設 `view=basic`
   不回 content，可按 path depth 導覽；命中後再以穩定 Memory ID retrieve `view=full`。
   這直接證明「先導覽、後開全文」是成熟官方 pattern，但它不是 LangMem
   `create_search_memory_tool` 的原生回傳形狀。
4. **OpenAI Codex／Agents SDK 採多層 progressive disclosure**：run 開始先注入小型
   `memory_summary.md`，再搜尋 `MEMORY.md`，需要細節時才開 1～2 份 rollout summary，
   需要精確命令／錯誤／佐證才深入 conversation rollout。SDK 同時明確把
   conversational Session memory 與 distilled Agent Memory 分開。
5. **OpenAI Conversations／Responses 與 LangGraph Checkpointer 的共同邊界**：兩者都能
   保存／延續 conversation items；長對話可做 context management／compaction。但它們
   都不等於一個現成的 raw-conversation semantic retrieval Tool。

### 9.2 目前真正未收斂的兩條 read path

#### A. 拿 Semantic Memory

有三個不能混稱為「framework 原生」的候選：

| 候選 | 模型看到的流程 | framework 對應 | 代價 |
|---|---|---|---|
| A1 LangMem search-first | `search_memory(query)` → 少量完整 Memory | LangMem 原生 Tool | 一次 Tool round trip；沒有先看完整目錄，需靠 query 命中。 |
| A2 Anthropic-style list/read | basic 導覽／搜尋 → `read_memory(id)` → 完整 Memory | LangGraph Store `search/get` 可承載，但 model-facing read Tool 是薄 adapter | 節省單次搜尋輸出，但每次深讀多一個 Tool step。 |
| A3 既有 hybrid | 每輪小型可重建導覽 → LangMem search 回少量完整 Memory | 導覽是 Caliburn projection；搜尋是 LangMem 原生 | 兼顧「知道有哪些主題」與較少 round trip，但每輪多固定導覽 token；不是單一廠商 turnkey recipe。 |

因此 `title` 是否需要、是否 model-authored、是否只是一個 derived routing label，取決於
A1／A2／A3；不能先獨立決定。`content` 則在三個候選裡都是 Semantic Memory 的完整
自成一體內容，只是何時送給模型不同。

#### B. 拿 canonical conversation

Checkpointer 已能保存完整 thread messages，但「找到並回傳哪一段」仍缺一個正式接縫：

1. 若每筆 Memory 有 Runtime 維護的 canonical message reference，模型可在搜尋 Memory
   後，把已看到的 opaque reference 原樣交給 `read_conversation_context`；Runtime 再從
   thread state 取該員工訊息及必要相鄰問答。
2. 若不保留 reference，只能在需要時掃描／搜尋整個 thread，或要求員工澄清。LangGraph
   沒有內建 semantic conversation search，故這不能冒充 framework-native 能力。
3. OpenAI 的 rollout summary／evidence path 證明「整理後 Memory 指向較深來源」可行；
   Anthropic Managed Memory 則沒有公開 per-memory conversation-message linkage。也就是
   `message_refs[]` **不是跨廠商共同 schema**；是否保留必須由 Caliburn 的「精確舊原話
   是否真的需要回讀」效果需求裁決。

目前只能確定：message ID／Memory ID 必須由 Runtime／Store 產生，模型不得捏造；
如果採 reference 路徑，模型只選擇自己剛看過的 opaque locator。尚未確定的是 reference
如何在 Memory create／update／consolidation 時正確繼承與附加，故不得先把
`message_refs[]` 宣告成 production canonical 欄位。

### 9.3 對 G4.3b 的影響

G4.3b 應先加一個前置裁決：**A1／A2／A3 哪一種是第一版 Semantic Memory read
topology？** 選定後才逐欄裁決 `title／content`；接著另以一個窄問題裁決 canonical
conversation deep-read 是否需要 per-memory Runtime-owned reference。這不是推翻
progressive disclosure 的效果目標，而是把 framework 原生能力與 Caliburn 尚未證明的
adapter 分開。

本節只記錄查證結果與 open candidates，不核准任何 production Tool、schema 或索引。

OpenAI 這條 read path 的寫入、四層 artifact、實際文字搜尋、rollout JSONL 深讀、
成本界線與不可照抄項目，已另以 focused evidence child 完整查證：
[`2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md`](2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md)。
該稿補足 A3 的事實基礎，但不自行裁決 A1／A2／A3。

### 9.4 本節新增直接來源

- [LangMem — Memory Tools API：search 直接回傳 serialized Memory 與 raw Item](https://langchain-ai.github.io/langmem/reference/tools/)
- [LangGraph — Persistence：Checkpointer／Store 的責任與存取模式](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph — Add and manage memory：messages、state、Store semantic search](https://docs.langchain.com/oss/python/langgraph/add-memory)
- [Anthropic — Managed Memory list：`basic`／`full` projection 與階層導覽](https://platform.claude.com/docs/en/api/http/beta/memory_stores/memories/list)
- [Anthropic — Managed Memory retrieve：以 stable Memory ID 讀取](https://platform.claude.com/docs/en/api/http/beta/memory_stores/memories/retrieve)
- [OpenAI Agents SDK — Agent memory：Session、summary、index、rollout progressive disclosure](https://openai.github.io/openai-agents-python/sandbox/memory/)
- [OpenAI Codex — Memory read path](https://github.com/openai/codex/blob/main/codex-rs/ext/memories/templates/memories/read_path.md)
- [OpenAI — Responses／Conversations state](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- [OpenAI Codex Memory progressive disclosure 深入查證](2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md)

## 10. G4.3b-1 Product Owner 裁決：採用 Codex 式責任分層

Product Owner 於 2026-09-05 核准直接學習 OpenAI Codex／Sandbox Agent 已公開的
Memory 分層與 progressive-disclosure 形狀，但不照抄 Markdown 檔名、檔案系統或
供應商內部格式。Caliburn 後續 framework design 必須能分別承接：

```text
durable Conversation／Session
        ↓
長對話 Context Compaction
        ↓
從訪談抽取可持久化工作資訊
        ↓
Consolidation／修訂目前 Semantic Memory
        ↓
每輪先提供小型 Memory 導覽
        ↓
相關時搜尋 Memory
        ↓
需要時深讀完整 Memory
        ↓
需要核實時回讀 canonical conversation
```

目前 JD／working workspace 與上述 Memory 分層保持不同責任；Memory 提供理解與召回，
不取得 JD authority。Caliburn 另因產品目的保留一條非日常的 exact-scope 全量盤點路徑，
供完整製作／最終檢查 JD 時處理全部有效 Memory；它不取代日常 progressive disclosure。

這項裁決取代 §9.2 把 A1／A2／A3 視為三個同等產品形狀的 open question。新的唯一
blocking question 是：**用哪個成熟 framework 組合最完整、最可靠地承接上述形狀？**
候選必須分清 framework-native、薄 adapter 與尚未覆蓋之處；未選定前不寫 production
schema、Tool JSON 或程式碼。

直接官方依據：

- [OpenAI — Sandbox Agents：Memory progressive disclosure、extraction 與 consolidation](https://developers.openai.com/api/docs/guides/agents/sandboxes)
- [OpenAI — Conversation state：durable conversation](https://developers.openai.com/api/docs/guides/conversation-state)
- [OpenAI — Compaction：長對話 continuation](https://developers.openai.com/api/docs/guides/compaction)
- [OpenAI — Codex 本機記憶](https://learn.chatgpt.com/zh-Hant/docs/customization/memories)
- [OpenAI Conversation／Context／Memory 系統圖](2026-09-05-openai-conversation-context-and-memory-system-map.md)

### 10.1 效力與下一個 gate

- **Status**：G4.3b-1 `APPROVED`；只核准責任分層與讀取形狀。
- **本 gate 當時未核准**：OpenAI Agents SDK、Deep Agents 或 LangChain／LangGraph／LangMem
  的正式選擇；後續 §11 已暫定 substrate。檔案／record 表徵、`title／content／message_refs[]`、
  Compaction exact 實作與 production 施工仍未核准。
- **Reopen trigger**：官方契約改變、代表性驗證證明此分層無法保留必要工作細節，或
  Product Owner 改變產品效果。
- **Next gate**：G4.3b-2 framework responsibility mapping。

## 11. G4.3b-2 Product Owner 暫時裁決：採用 LangChain／LangGraph／LangMem 作 substrate

Product Owner 於 2026-09-05 暫時同意以 LangChain `create_agent`＋LangGraph
PostgreSQL Checkpointer／Store＋LangMem 作第一版 framework substrate；OpenAI Agents／Sandbox
與 Deep Agents 保留為權威參考及必要時的局部替代，不整套引入，也不把產品鎖定在單一
模型供應商。

這項同意不是「找到名稱相近的元件就完成」。後續設計必須學習 OpenAI 為何把同一套
Memory 分成兩條生命週期，並逐段保存它們的責任：

```text
讀取／執行生命週期：
durable conversation
  → bounded／compacted model context
  → 小型 Memory 導覽
  → 相關時搜尋 Memory
  → 必要時深讀完整 Memory
  → 只有核實精確內容時回讀 canonical conversation

寫入／整理生命週期：
run segments 寫入 canonical conversation
  → extraction 產生本次對話的可持久化候選與詳細橋接內容
  → consolidation 與既有 Memory 去重、補充、修正或淘汰
  → 重建下一輪使用的小型導覽
```

OpenAI 把這些責任拆開的直接目的如下：

| 分層 | 為何不能被相鄰層取代 |
|---|---|
| Conversation／Session | 保存真正發生的 message、Tool call 與 result；distilled Memory 不是逐字歷史。 |
| Compaction | 只降低同一長對話的模型 Context 成本並維持 continuation；opaque continuation 不是可搜尋知識或精確來源。 |
| Extraction | 先把單次 conversation 的有效訊號與脈絡整理成候選，避免 global Memory 直接反覆吞整段 raw history。 |
| Consolidation | 把多次 extraction 與既有 Memory 比較後去重、更新與移除失去支持的內容；沒有新差異時可 no-op。 |
| 小型導覽 | 只支付很小的每輪固定 token，告訴模型有哪些相關主題與如何尋找。 |
| 搜尋／完整 Memory 深讀 | 平常只取少量相關知識；需要細節才增加 Tool step 與 context token。 |
| Canonical conversation 回查 | distilled 層不足以回答精確原話、錯誤或 Tool 結果時，回到最精確記錄。 |
| Workspace／JD | 是目前產品 artifact，不是 Memory；Memory 幫助判斷，但不取得文件 authority。 |

### 11.1 Framework responsibility mapping

| 已核准責任 | 第一候選 framework primitive | 覆蓋判斷 | 尚未決細節 |
|---|---|---|---|
| durable Conversation／Session | LangGraph `MessagesState`＋PostgreSQL Checkpointer | 原生覆蓋 thread continuity、Tool items、恢復與 trace | retention／讀取窗口後議 |
| model-visible Compaction | LangChain model-context／lifecycle middleware；provider 原生 compaction 可作 capability | **部分覆蓋** | built-in `SummarizationMiddleware` 會永久取代舊 messages，不能在沒有 canonical 保存設計時直接採用 |
| extraction | LangMem `create_memory_store_manager`／`create_memory_manager` | 原生分析 conversation 並形成 insert／update／delete 候選 | hot path、after-turn 或 deferred trigger 未決 |
| consolidation | LangMem store manager＋`ReflectionExecutor` | 原生搜尋既有 Memory、更新 Store，且可 debounce／背景執行 | 是否拆出可檢查的中間 artifact、何時執行未決 |
| 小型 Memory 導覽 | Store 內容的可重建 projection＋LangChain middleware 注入 | 需要薄 application projection | 大小、更新時機與內容未決 |
| 搜尋相關 Memory | LangMem `create_search_memory_tool`／LangGraph Store search | 原生覆蓋 | query/result 最小 contract 後議 |
| 深讀完整 Memory | LangGraph Store `get` | storage primitive 原生；model-facing read 需薄 Tool adapter | locator／result shape 後議 |
| 回讀 canonical conversation | Checkpointer state/history | storage primitive 原生；精確 model-facing read 需薄 adapter | message reference／鄰接窗口後議 |
| 最終全量 JD 檢查 | Store exact namespace enumeration／pagination | storage primitive 可承載；worklist 是產品邏輯 | 不可把 top-k search 冒充全量盤點 |
| 目前 JD／待審變更 | Caliburn application-specific document Tools | framework 不知道 JD domain | 留到 Memory 流程收斂後另議 |

### 11.2 與既有 G4.1 的衝突及後續解決

G4.1 §3.2 原本核准「只讓主顧問直接使用 `create_manage_memory_tool`，第一版不加入
background manager」。在 G4.3b-1 已核准 OpenAI 式 extraction／consolidation 分層後，
這個排除已沒有足夠依據，並已由 §13 的 G4.3b-4a 裁決取代：

- direct manage Tool 仍可作 run 中需要立即生效的修正路徑；
- 但它不能自動等同 extraction＋consolidation；
- 一般 extraction／consolidation 採背景 manager 責任，允許 debounce；
- exact trigger、freshness、成本與失敗邊界仍須依 §13.7 後續 gate 裁決；
- 不得再把「第一版不加入 manager」帶入後續設計或 production 計畫。

### 11.3 效力與下一個唯一問題

- **Status**：G4.3b-2 `WORKING APPROVED`；核准 framework substrate 與責任 mapping，
  不核准 production 組裝或 exact schema。
- **官方事實**：OpenAI Session／Memory 分層、Compaction opaque continuation、Sandbox
  extraction→consolidation 與 progressive disclosure；LangGraph Checkpointer／Store 分工；
  LangMem hot-path／background manager 能力。
- **Caliburn mapping**：採 LangChain／LangGraph／LangMem 並補最薄 adapter；不是 OpenAI
  或 LangChain 宣稱的唯一架構。
- **後續狀態**：Conversation／Compaction 接縫已在 §12 核准，三路 Memory 生命週期已在
  §13 核准；目前唯一 blocking question 以 §13.7 與 decision register 為準。

直接來源：

- [OpenAI — Sandbox Agents](https://developers.openai.com/api/docs/guides/agents/sandboxes)
- [OpenAI — Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- [OpenAI — Compaction](https://developers.openai.com/api/docs/guides/compaction)
- [OpenAI — Codex local memories](https://learn.chatgpt.com/docs/customization/memories)
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangChain — Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)
- [LangMem — Memory API](https://langchain-ai.github.io/langmem/reference/memory/)
- [LangMem — Delayed background processing](https://langchain-ai.github.io/langmem/guides/delayed_processing/)

## 12. G4.3b-3 Conversation／Compaction focused review（Product Owner 已核准）

本節只處理一個問題：**完整訪談應長期保存，但每次模型呼叫不應無限制重送全部歷史。**
它不決定 Semantic Memory extraction／consolidation、JD mutation、UI 或 token threshold。

### 12.1 已由官方文件證實的共同邊界

1. OpenAI Conversations 可用 durable ID 保存 message、Tool call、Tool output 等 items，跨
   session／device／job 延續；這是 conversation state，不是 distilled Semantic Memory。
2. OpenAI server-side／standalone Compaction 產生較小的後續 context window；其中的
   compaction item 是 encrypted、opaque，不供人或應用解析，也不是逐字來源。
3. Anthropic 同樣把 server-side compaction 列為長對話的主要策略；其 context editing
   明確允許 client 保留完整、未修改的 conversation，而 API 只調整真正送入模型的內容。
4. LangGraph Checkpointer 原生保存每個 thread 的 graph state／messages 並支援恢復；
   LangChain `wrap_model_call` 可只覆寫**單次 model request** 的 messages，而不修改 state。
5. LangChain `SummarizationMiddleware` 會把較舊 messages 以摘要取代；Deep Agents 因而採
   「工作中的摘要＋另外保存原始 conversation」雙層做法。若沒有另外的 canonical 保存，
   不能把被取代後的 `messages` 誤稱為完整歷史。

因此，共識不是「只保留摘要」，而是：

```text
完整、可恢復的 canonical conversation
                  │
                  ├─ 精確回查／稽核
                  │
                  └─ 產生有界的 model-visible continuation view
                                      │
                                      └─ 本次模型呼叫
```

### 12.2 本題不可犧牲的效果

- canonical conversation 不因 trim、summary 或 provider compaction 被刪除；
- 每次模型呼叫只收到可延續且有界的 context，不把「全部保存」誤作「全部重送」；
- Compaction 只負責同一 conversation 的工作延續，不冒充 Semantic Memory 或 Evidence；
- 更換模型／Provider 時，不能因舊 Provider 的 opaque compaction item 而失去歷史；
- trigger token、保留幾輪、摘要模型及 retention 數字留到後續量測，不在本題猜定。

### 12.3 三個候選

#### A. Provider-native Compaction 作唯一 continuation

OpenAI 或 Anthropic 到門檻後自行 compact，下一輪帶回其 compaction block。

- 優點：Provider 最了解自己的 reasoning／message format；不需 client-side summarizer；
  OpenAI 與 Anthropic 都已提供原生能力。
- 缺點：block／item 是 provider-specific，OpenAI 版本還是 opaque；模型切換、OpenRouter
  相容性、除錯及重建能力較差。
- 判斷：可作單一 Provider 的最佳化能力，**不宜作可替換模型產品的唯一基線**。

#### B. 非破壞性的 framework context view（推薦）

LangGraph PostgreSQL Checkpointer 保留完整 canonical `messages`；同一 thread 另保存一份
可重建、非權威的 continuation artifact 與其涵蓋邊界。LangChain `wrap_model_call` 在每次
模型呼叫前，只暫時組成：

```text
短而穩定的 instructions
＋最近一次 continuation summary（尚未觸發時可無）
＋摘要邊界之後的近期原始 messages
＋本輪新訊息
```

這個 override 不回寫、刪除或取代 canonical `messages`。到 context 壓力門檻時才更新
continuation artifact，不是每輪都多呼叫一次模型。Provider-native compaction 可在日後經
相容性／效益驗證後加入 model adapter，但不能成為唯一可恢復副本。

- 優點：直接使用 LangChain 官方 transient model-context seam；保留完整歷史；plain-text
  continuation 可跨模型；不另建第二份 canonical archive。
- 缺點：需一個薄 middleware 組裝與摘要邊界記帳；摘要品質及觸發策略仍須後續驗證。
- 性質：這是把 OpenAI／Anthropic 的「完整歷史與模型視圖分離」原則映射到已暫定的
  LangChain／LangGraph substrate；不是任何 Provider 宣稱的唯一架構。

#### C. 直接使用會取代 `messages` 的 SummarizationMiddleware，再另存 archive

- 優點：最接近 Deep Agents 現成雙層模式，summary trigger／keep 已有 framework 支援。
- 缺點：為保留完整訪談，必須再建立一份 canonical archive；這會重複目前 Checkpointer
  應負責的 conversation authority，也增加同步、retention 與回讀接縫。
- 判斷：適合沒有既有 canonical conversation owner 的 harness；不作目前第一候選。

### 12.4 Product Owner 裁決

採 **B 作 provider-neutral baseline**；A 只保留為後續可驗證的 provider capability；C 不採。

Product Owner 於 2026-09-05 核准此選擇。這仍是 Working Decision，不授權 production
施工；若代表性驗證顯示 continuation 失真、成本不可接受，或 Provider 原生能力成熟到能
在不犧牲模型可替換性的前提下完整取代，才重開本題。

這一裁決只固定 authority／loss boundary：

- Checkpointer 中完整 conversation 是 canonical；
- continuation artifact 是可重建的 derived context；
- middleware 只改本次 model request；
- 不在本節決定 artifact JSON、token threshold、摘要 prompt 或 storage retention。

### 12.5 直接來源

- [OpenAI — Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- [OpenAI — Compaction](https://developers.openai.com/api/docs/guides/compaction)
- [Anthropic — Compaction](https://platform.claude.com/docs/en/build-with-claude/compaction)
- [Anthropic — Context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing)
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangChain — Context engineering：transient 與 persistent model context](https://docs.langchain.com/oss/python/langchain/context-engineering)
- [LangChain — Short-term memory：trim／delete／summarize 的不同效果](https://docs.langchain.com/oss/python/langchain/short-term-memory)
- [LangChain — Built-in SummarizationMiddleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in#summarization)
- [Deep Agents — Context engineering：summary＋canonical preservation](https://docs.langchain.com/oss/python/deepagents/context-engineering#summarization)

### 12.6 效力與下一個唯一問題

- **Status**：G4.3b-3 `APPROVED`。
- **已固定**：完整 conversation 與 bounded model context 分離；Checkpointer 保存 canonical
  conversation；continuation artifact 可重建且非權威；middleware 只暫時改本次 model request。
- **仍未固定**：artifact schema、摘要 prompt／model、token trigger、retention、Provider 原生
  capability wiring。
- **後續狀態**：G4.3b-4a 已在 §13 核准即時讀取、背景整理與窄幅 live repair 三路協作；
  G4.3b-4b～4d 已在 §14～§16 依序核准；目前唯一 blocking question 是 G4.3b-4e live repair。

## 13. G4.3b-4a 三路 Memory 生命週期（Product Owner 已核准）

本節只處理一個問題：**即時讀取、背景形成與執行中修補三條路徑如何分責。**Product
Owner 於 2026-09-05 核准三者是互補流程，不是 A／B／C 三選一。本節不決定 Memory
欄位、prompt、模型、背景 queue、debounce 秒數、retry 次數、JD mutation 或 UI。

### 13.1 官方事實：三套公開機制並不是同一種寫入時機

#### OpenAI

1. Codex 本機 Memory 會略過仍活躍或太短的對話，等 conversation 閒置一段時間後才在
   **背景**產生 Memory；官方同時公開 `extract_model` 與 `consolidation_model`，代表個別
   conversation extraction 與跨既有 Memory consolidation 是不同工作。
2. OpenAI Sandbox Memory 另支援**執行中的 live update**，讓 Agent 修補 stale Memory 或
   回應使用者要求；session close 時，Runtime 又會先 extraction conversation summary／raw
   memories，再 consolidation 成供後續讀取的 Memory 與小型導覽。
3. 因此，OpenAI 公開的是「可即時修補＋可延後整理」兩種能力；不能把其中一條誤寫成
   OpenAI 對所有 Agent 產品的唯一 lifecycle。

#### Anthropic

1. Anthropic Memory Tool 是主 Agent tool loop 內的 client-side Tool。Claude 決定何時
   `view／create／str_replace／insert／delete／rename`，application 執行並回傳 `tool_result`。
2. Memory Tool 的自動 instructions 要求先查看 Memory，工作過程持續記錄，並保持內容一致、
   非必要不新增檔案；這是 **hot-path、模型主動管理**。
3. 該 Tool 文件沒有提供自動 background extraction／consolidation service；儲存、限制、
   安全與 operation handler 仍由 application 負責。

#### LangChain／LangMem

1. LangChain 官方把 long-term Memory 寫入分成兩種正式模式：hot path 可立即使用，但增加
   latency、Tool 決策與主 Agent 多工負擔；background 不阻塞回覆、可專心整理，但 Memory
   較晚才可用，且 application 必須選 trigger。
2. LangMem `create_manage_memory_tool` 支援 Agent hot-path 管理；
   `create_memory_store_manager` 會以新 conversation 與搜尋到的既有 Memory 做 extraction、
   update／insert／delete／no-op；`ReflectionExecutor` 可背景執行並 debounce。
3. LangMem 明確指出：活躍 conversation 若每則訊息都立即跑 manager，會造成重複工作、
   中途脈絡不完整與不必要 token 消耗；delayed processing 可取消舊排程，等互動暫歇後再處理。

### 13.2 哪些是共同邊界，哪些不是

| 類別 | 目前能由官方資料支持的結論 |
|---|---|
| 共同邊界 | canonical conversation 與 distilled Semantic Memory 分責；Memory 寫入需比較新 conversation 與既有 Memory；持久層與 trigger 最終由 application／runtime 控制。 |
| 多條成熟路徑 | 即時讀取、hot-path update 與 background formation 都是正式、現行能力；各自解決不同問題。 |
| 非共同規則 | 沒有跨廠規則要求每則訊息固定跑 manager，也沒有跨廠規則要求所有 Memory 都由主 Agent 直接 CRUD。 |
| Caliburn 必須自行選的政策 | 哪類資訊需要立即 durability、一般 extraction 何時排程、freshness 如何由近期 conversation 銜接。這是產品取捨，不可冒充 Provider 內部事實。 |

### 13.3 本題既有產品約束

1. `MEM-Q001` 已固定 Checkpointer 保存 canonical conversation；即使 Semantic Memory 尚未
   更新，新員工訊息也不會消失。
2. `MEM-Q002` 要求 extraction／consolidation 能對相似案例 no-op、補充、修訂或另建 focused
   Memory，不能只做 append。
3. `MEM-Q005` 已固定同一 Context 形成的 Memory mutation 與 JD pending change 是並列
   effects；JD 不必等待 Memory 先成功寫入 Store，才可形成自身驗證通過的待審變更。
4. 第一版是一份 JD、一個長期 thread，且訪談輪數可能很多；不應為每則短訊息無條件增加
   一次完整 manager model call。

### 13.4 已核准的三路協作拓撲

```text
每則被接納的員工訊息
  → 先寫入 canonical conversation
  → A. 即時讀取／執行
       ├─ 組成本次有界 model context
       ├─ 按相關性搜尋／深讀既有 Semantic Memory
       ├─ 主顧問正常訪談與形成其他 effects
       └─ C. 若已讀 Memory 明確過時，才在本 run 即時修補
  → 回覆員工；不等待一般背景整理完成
  → B. 對新 conversation segment 排程 extraction／consolidation
       ├─ 活躍訪談可 debounce，避免反覆處理零碎片段
       ├─ 對照最新既有 Memory 做 no-op／補充／修正／淘汰
       └─ 發布更新後的 Memory，並重建小型導覽
```

#### A. 即時讀取／執行流程

A 處理「模型這一次需要看到什麼並完成本輪工作」，不只處理聊天紀錄。它以完整
canonical conversation 為保存底座，組成有界 continuation context，提供小型 Memory
導覽，並在相關時逐步搜尋、深讀 Memory；真的需要核實時才回查 canonical conversation。
最新 JD／workspace 是否進入某次呼叫，取決於本輪工作，不把全部資料無條件塞入每次 prompt。

#### B. 背景 Memory 形成／整理流程

B 處理「哪些訪談內容應成為後續可取回、可修訂的工作理解」。它讀取新 conversation
segment 與最新既有 Memory，先 extraction，再 consolidation，形成 no-op、補充、修正、
新增或淘汰結果，最後更新小型導覽。B 不回答員工、不自行決定或修改 JD，也不取代
canonical conversation。

背景化不只是省 token：它也避免阻塞員工回覆、避免在每個零碎訊息後反覆整理不完整脈絡，
並讓 consolidation 能用較完整的 conversation segment 做比較。背景 Memory 尚未發布時，
A 仍可透過近期 canonical conversation／continuation context 看見新資訊，因此「尚未整理」
不等於「本輪忘記」。exact idle／debounce／session-boundary trigger 後議，不在這裡猜數字。

#### C. 執行中的窄幅 live repair

C 只處理「模型本輪已取回的 Memory 已被清楚新資訊證明過時」：例如員工明確更正，且
被更正的既有理解可確定定位。主顧問可在同一 bounded run 使用 direct Memory Tool 修補，
取得成功或錯誤結果後才進行下一個依賴該理解的步驟。

「看起來可能矛盾」不等於可以直接修補。若新舊說法仍有多種合理解釋，主顧問先以一般
訪談詢問員工，本輪不得偷偷挑一個版本。這不是額外的「更正原話」UI 或字串偵測規則。

### 13.5 三路之間的 freshness 與失敗邊界

1. Conversation durability 先於三路之後的衍生處理；因此 B 或 C 失敗不會刪掉員工訊息。
2. C 若已成功修補，稍後執行的 B 必須以**最新** Memory 為輸入，允許 consolidation no-op，
   不得用較舊 snapshot 把修補覆蓋回去。exact serialization／version check 留待 C 細節 gate。
3. B 的「已排程」不等於「Memory 已發布」；Runtime 與回覆不能虛報完成。
4. C 技術性失敗時，模型不能假裝 Memory 已更新；近期 conversation 仍可支撐本輪回答，
   後續 B 可再整理。若下一動作確實依賴成功修補，則該依賴動作不能先假設成功。
5. Memory formation／repair 不取得 JD authority。JD 待審變更仍是獨立、可驗證的 sibling
   effect，沿用 `MEM-Q005` 的失敗隔離規則。

### 13.6 本裁決刻意沒有決定的細節

- A：固定注入與按需讀取的 exact context recipe、Compaction artifact schema、token trigger；
- B：extraction 輸入邊界、中間 artifact、Memory schema、manager prompt、排程與模型；
- B：consolidation 的 identity、去重／補充／修正／淘汰判準與發布規則；
- C：可即時修補的精確門檻、Tool contract、版本檢查、與 B 的 concurrency；
- 全域：retry、queue、觀測、失敗 UI、成本 budget 與 production wiring。

這些必須依序收斂後，才回頭做 framework 最終 coverage／gap review；§11 的 framework
mapping 目前只是暫定 substrate，不得拿現成 API 名稱倒推產品資料結構。

### 13.7 後續單題決策順序

1. `G4.3b-4b`（已核准）：A 即時讀取——每次 model request 固定帶什麼、按需取什麼、何時 compact；
2. `G4.3b-4c`：B extraction——讀哪些 conversation segment、產生什麼可檢查中間結果；
3. `G4.3b-4d`：B consolidation——如何 no-op／補充／修正／淘汰並發布；
4. `G4.3b-4e`：C live repair——何時允許即時修補，以及如何不被稍後背景結果倒退；
5. `G4.3b-4f`：整體成本、失敗、觀測與 framework 最終責任 mapping。

`G4.3b-4e` 已在 §17 核准；目前唯一 blocking question 是 `G4.3b-4f`，不得在同一輪偷做
JD mutation 或 production wiring。

### 13.8 直接來源

- [OpenAI — Codex 本機記憶：背景產生、閒置門檻、extraction／consolidation model](https://learn.chatgpt.com/zh-Hant/docs/customization/memories)
- [OpenAI — Sandbox Agents：live Memory update 與 session-close extraction→consolidation](https://developers.openai.com/api/docs/guides/agents/sandboxes)
- [Anthropic — Memory Tool：模型主動 hot-path 檔案操作與 client-side handler](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [LangChain — Memory overview：hot path／background 的官方取捨](https://docs.langchain.com/oss/python/concepts/memory)
- [LangMem — Core concepts：active／background formation 與 manager 分層](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)
- [LangMem — Memory manager API：既有 Memory 搜尋、更新與 background executor](https://langchain-ai.github.io/langmem/reference/memory/)
- [LangMem — Delayed processing：debounce、取消重複工作與 token 成本](https://langchain-ai.github.io/langmem/guides/delayed_processing/)

## 14. G4.3b-4b A 即時讀取／Context 組裝（Product Owner 已核准）

本節只回答：**一次 model request 應固定看到什麼、可以自動少量取得什麼、又有哪些內容只在
需要時才深入讀取；Compaction 在其中扮演什麼角色。**本節不決定 exact token 數字、
Memory／continuation JSON、JD Tool、背景排程、模型或 production wiring。

### 14.1 重新核實的官方事實

| 來源 | 已公開的現行行為 | 本節能下的結論 |
| --- | --- | --- |
| OpenAI Conversation | Conversation 是具有 durable ID 的長期物件，保存 message、Tool call、Tool output 等 items；保存歷史不表示每輪都要自行重送同一份全文。 | canonical conversation 與單次 model-visible context 必須分開。 |
| OpenAI Compaction | 到 token threshold 才產生 compaction item；它用較少 token 承接後續 context。standalone compact 回傳的是下一個 canonical **context window**，不是新的長期 Semantic Memory。 | Compaction 解決目前 conversation 的延續與窗口壓力，不取代 canonical conversation 或 Semantic Memory。 |
| OpenAI Sandbox Memory | 每次 run 先注入 `memory_summary.md`；先搜尋 `MEMORY.md`，需要更多細節才打開 rollout summaries。 | 小型導覽＋搜尋＋深讀是 OpenAI 已出貨的 progressive disclosure，而非 Caliburn 自創。 |
| Anthropic Context Engineering／Memory Tool | 官方原則是用最小的高訊號 token 集；Claude Code 採少量 upfront context＋glob／grep 即時取用，Memory Tool 也主張按需讀取。官方同時指出純按需探索可能變慢或漏找，因此某些任務以 hybrid 最有效。 | 不應採「全部預載」或「完全不預載」兩個極端；需要一個小型固定入口與按需深入。 |
| Anthropic Compaction | 接近 token threshold 時才壓縮舊 conversation；官方明示 Memory 與 Compaction 可同時使用：前者保存跨摘要仍須存在的資訊，後者縮小 active context。 | Compaction 不是 Memory formation，也不能作精確原話來源。 |
| Google Memory Bank | 相同 scope 可 similarity top-k，也可不帶 similarity 參數而 retrieve all；ADK 可替 agent 協調一般 retrieval。 | 日常相關召回與全面盤點是兩種正式模式，不能拿 top-k 冒充全量。 |
| AWS AgentCore Memory | Short-term 保存 raw messages／Tool calls；long-term 另做 semantic／summary／episodic 等抽取；Harness 可調 history messages、retrieval top-k 與 relevance。 | Conversation continuity、長期 Memory 與 retrieval budget 是分離責任。 |
| LangChain／LangGraph | Model Context 是單次、transient；middleware 可從 State／Store／Runtime 組裝並只 override 該次 request。Checkpointer 保存 thread state，Store 保存長期 Memory。 | 可以用成熟 middleware 組裝 Context，不必建立第二份持久 conversation；不能直接用會永久覆寫 messages 的摘要機制當 canonical owner。 |

跨家共同形狀因此是：**完整保存不等於完整注入；短期延續與長期 Memory 分層；平常只提供
小而相關的工作集，需要時再逐步搜尋／深讀；只有接近窗口壓力才 compact。**沒有任何一家
公開一組適合所有產品的固定 token 數、最近訊息筆數或 top-k；那些是後續以模型窗口、品質、
延遲與成本量測校準的產品參數，不能在研究階段猜一個數字冒充共識。

### 14.2 三個候選

#### 方案 1：小型固定底座＋少量自動召回＋模型按需深入（採用）

```text
每次 model request
  ├─ 固定：精簡且穩定的顧問規則／安全與 authority 邊界
  ├─ 固定：有界 conversation continuation
  │        ├─ 尚未 compact：近期 canonical conversation
  │        └─ 已 compact：最新 continuation artifact＋其後 canonical messages
  ├─ 固定：小型、可重建的 Semantic Memory 導覽
  ├─ 自動有界：與本輪訊息相關的少量 current Semantic Memory
  ├─ 動態：本輪員工訊息與本次 Tool results
  └─ 按需：更多 Memory／原始 conversation／JD 局部／職務分析 Skill
```

完整 JD、全部 Memory、全部 conversation、全部 Skill 與所有低頻 Tools 都不固定注入。模型若
判斷要核對舊細節、比較 JD 或啟用 Task／Duty／OPKS 方法，再使用對應的受限 search／read／load
能力；Runtime 固定 JD scope、權限、limit 與結果整形，模型不填這些可信參數。

- 優點：符合 OpenAI 與 Anthropic 的 hybrid progressive disclosure，也保留 Google／AWS 的
  bounded retrieval；固定成本低，又不把「模型有沒有想起要搜尋」當唯一保障。
- 代價：某些回合會多一個 Tool step；需要觀測召回結果與 Tool 使用，而不是先猜 budget。

#### 方案 2：每輪自動預載較完整 Context

固定附上較長 conversation、較多 Memory、目前完整 JD 與多份分析方法。

- 優點：較少 search／read Tool steps，短期 demo 容易看似直接。
- 代價：每輪重付 token／延遲，無關內容增加 attention competition，資料越長越容易 context rot；
  也與 OpenAI／Anthropic 已公開的分層與按需讀取方向不符。**不推薦。**

#### 方案 3：幾乎全部交給模型按需尋找

固定只給近期 conversation 與能力名稱，Memory、JD、Skill 都等模型自行呼叫。

- 優點：固定 token 最少。
- 代價：模型可能不知道有哪段歷史值得找；每次先列目錄／搜尋會增加 latency。OpenAI 仍固定
  注入小型 memory summary，Anthropic 也明確主張 hybrid 可補純探索的缺點。**不推薦作預設。**

### 14.3 Compaction 的精確責任邊界

1. **觸發依據是實際 model context 的 token 壓力，不是訪談輪數、經過時間或每輪固定執行。**
2. Compaction 只把舊 conversation 轉成較小的 continuation view；完整 canonical conversation
   仍由 Checkpointer 保存，不刪除、不改寫。
3. 下一次呼叫使用「最新 continuation artifact＋artifact 之後的新 canonical messages」；不得把
   artifact 再與已被它涵蓋的全文一起重送，否則成本與語意會重複。
4. Compaction artifact 不是工作 Memory、不是員工逐字來源、不是 JD，也不進入最終全量盤點。
   需要精確舊說法時，仍沿 canonical conversation reference 回查。
5. Provider-native compaction 可作 adapter capability；第一版共同契約仍維持 provider-neutral、
   非破壞性的 bounded view，避免把 OpenAI opaque item 或 Anthropic beta block 變成產品權威。
6. exact trigger、保留多少 recent messages、summary instructions 與 fallback，留到成本／模型
   capability gate 以代表性長訪談校準；本節不虛構通用數字。

### 14.4 已核准的固定與不固定邊界

| 類別 | 本輪候選裁決 |
| --- | --- |
| 固定帶入 | 精簡穩定規則、有界 continuation、小型 Memory 導覽、本輪訊息、目前回合已產生且尚需模型處理的 Tool results |
| 自動少量帶入 | Runtime 在同一 JD scope 召回的少量 current Semantic Memory；結果逐筆完整，不把截斷片段冒充完整理解 |
| 按需取得 | 更多／完整 Memory、舊 conversation 脈絡、目前 JD 的相關局部、Task／Duty／OPKS Skill 內容、低頻 Tool |
| 只在特定工作使用 | 最終或全面 JD 檢查的 exact-scope all-current-Memory inventory；它不是日常 prompt 配方 |
| 不放進 model schema | JD scope、principal、namespace、limit、filter、token counter、版本、時間、retry 與 compaction bookkeeping |

這裡的「固定」是指每次 model request 的**資料類別**，不是固定全文或固定 token 數；每個類別
仍必須有界。此候選也沒有規定每輪一定讀 JD：顧問先理解員工工作，只有本輪真的需要分析、
比較或編輯 JD 時才讀相關文件內容，避免把 JD 寫作誤變成每輪固定流程。

### 14.5 Product Owner 裁決與下一題

- **Decision**：2026-09-05 核准方案 1：小型固定底座＋少量自動召回＋模型按需深入。
- **仍未決定**：exact token／top-k／recent-window 數字、provider-specific compaction、正式
  artifact schema 與 production wiring；不得由實作者自行補值。
- **Next gate**：G4.3b-4c 只討論 B extraction 讀取哪些新 conversation segment、產生什麼
  可檢查的中間結果，以及什麼情況合法產生空結果；不得同時偷定 consolidation 或 Memory schema。

### 14.6 本節新增／重核的直接來源

- [OpenAI — Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- [OpenAI — Compaction](https://developers.openai.com/api/docs/guides/compaction)
- [OpenAI — Sandbox Agents／Memory progressive disclosure](https://developers.openai.com/api/docs/guides/agents/sandboxes)
- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Anthropic — Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Anthropic — Compaction](https://platform.claude.com/docs/en/build-with-claude/compaction)
- [Google Cloud — Memory Bank fetch：similarity retrieval 與 retrieve all](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/fetch-memories)
- [AWS — AgentCore Harness Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness-memory.html)
- [AWS — AgentCore Memory architecture](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/how-it-works.html)
- [LangChain — Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)
- [LangGraph — Persistence／Checkpointer 與 Store](https://docs.langchain.com/oss/python/langgraph/persistence)

## 15. G4.3b-4c：B Extraction 聚焦審核（已核准）

> **狀態：APPROVED（2026-09-05）。** 本節只決定背景整理流程的 Extraction 邊界：
> 它讀哪段 canonical conversation、輸出什麼尚未合併進 Semantic Memory 的中間結果，以及何時
> 可以合法輸出空結果。Consolidation 規則、最終 Memory schema、排程數字與 production wiring
> 均不在本題範圍。

### 15.1 先分清直接事實、差異與產品推論

| 來源 | 官方公開的直接事實 | 本題不能冒充的結論 |
| --- | --- | --- |
| OpenAI Sandbox Agents Memory | Runtime 累積 conversation；第一階段處理一份 accumulated conversation，省略 system／developer／reasoning 內容，產生 conversation summary 與 raw memory extract；第二階段才讀 raw memories、必要時開 summary，整併成長期 Memory 與小型導覽。多次 `run()` 使用同一 stable conversation ID 時會累積成同一段交換。 | OpenAI 沒有公開要求 Caliburn 採某個固定 JSON schema，也沒有公開一個適用所有產品的 debounce 秒數。 |
| Google Cloud Memory Bank | 明確分 extraction 與 consolidation；可從直接 conversation events 或 Session 的時間區段產生；revision 可檢查 `extracted_memories`；可以關閉 consolidation 單看 extraction；沒有產生 Memory 也是正常結果。官方建議 production 優先非同步背景生成。 | Google 的 managed fact schema 不是 Caliburn 最終工作記憶 schema，也不能直接證明每一個 candidate 都應由模型填來源 ID。 |
| AWS AgentCore Memory | short-term raw events 與 long-term background memory 分開；semantic strategy 分 extraction／consolidation。預設 extraction prompt 把 `past_conversation` 當理解脈絡，只從 `current_conversation` 擷取；不猜模糊資訊、沒有 noteworthy information 時回傳空 list，輸出保持很小。 | AWS 的 `language`＋`fact` 是供應商預設，不表示 Caliburn 必須只存單句 fact。 |
| Anthropic Managed Memory／Dreams | Memory Store 提供聚焦文件、immutable versions 與 optimistic precondition；Dreams 是非同步 consolidation research preview，讀既有 Store＋歷史 Sessions，合併重複、替換過時／矛盾項目，預設寫入另一份可檢查、可丟棄的 Store。Memory Tool 仍是執行中的按需 CRUD 路徑。 | Anthropic 沒有公開等同 OpenAI 的 phase-one `summary＋raw extract` 契約；Dreams 也不是第一版可假定已穩定、可直接移植的 production primitive。本題只用它交叉確認「背景整理與即時 Memory Tool 是不同責任」。 |
| LangMem | delayed processing 可 debounce：有新活動時取消／重排背景整理，等活動穩定後用較完整的 context 處理；memory manager 可搜尋既有 Memory 並抽取、更新、刪除、整併。 | 公開 manager API 把 extraction 與 consolidation 合在一次管理操作中，沒有原生暴露 OpenAI 那組「summary＋raw extract」中間產物；是否需要薄橋接層是後續 framework gate，不能在本題偷定。 |

因此，跨 OpenAI／Google／AWS 可以成立的**共同核心**只有：

1. Extraction 處理一段有界的新 conversation events，而不是每次重讀全部歷史或全部長期 Memory。
2. 舊 conversation 可以作消歧脈絡，但不應被反覆當成這批的新資訊重新擷取。
3. Extraction 產生「待整併候選」，不能自己宣稱已經更新 final Memory，更不能編輯 JD。
4. 沒有新的、可持久保存的資訊時，空結果是成功的 meaningful no-op。
5. 長訪談宜在背景、活動穩定或明確區段邊界後處理，而不是每則訊息都做昂貴整理。
6. 抽取與整併必須可分開觀測；Anthropic 的 Dreams 進一步證明背景 consolidation 與執行中
   Memory Tool 是不同責任，後者屬另一條 C／live-repair 路徑，不能拿來取代 B。

### 15.2 Extraction 的責任邊界

候選輸入分成兩個角色，兩者不可混淆：

- **Target segment**：一段已由 Runtime 封口、尚未完成 Extraction 的連續 canonical
  conversation events。只有這一段可以產生新的 extraction candidates。
- **Support context**：必要時附上的有界 continuation／較早對話，只用於理解「那個網站」、
  「剛才說錯了」等指涉；不得把它再次當成本段的新資訊。

「封口」只表示 Runtime 認定這一批暫時完整、內容不再變動，可供背景工作重試；不是訪談結束，
也不是要求員工手動按結束。每份 JD 可以持續一個長 conversation，再由 Runtime 依穩定活動區段
切成多個 target segments。exact inactivity window、event count、token threshold 與 retry cursor
留到排程／成本 gate，以真實長訪談校準。

Extraction 只能：

- 從員工的新陳述辨識可持久的工作資訊、工作案例細節、明確更正或員工明確表露的未確定事項；
- 以 assistant 的提問理解員工回答的語境；
- 在不知道時輸出空結果，不能自行補答案。

Extraction 不能：

- 對照 current Semantic Memory 決定 add／update／delete／skip；那是 Consolidation；
- 因「員工尚未談到某欄」自行製造 coverage gap；那是顧問／分析 Skill 的工作；
- 修改 JD、核准內容、向員工提問或決定訪談焦點；
- 把 system prompt、developer instruction、模型 reasoning、JD Tool result 或模型自己生成的內容
  當成员工工作事實；
- 要模型填 canonical event ID、JD scope、principal、namespace、revision、時間、Skill ID、來源 UUID
  或 quote offset。這些可信 bookkeeping 由 Runtime 依 target segment 附加。

### 15.3 三個候選方案

#### 方案 1：一個 phase-one call 產生雙中間結果（建議）

對每個 target segment，一次背景模型呼叫同時產生：

1. **Segment summary**：自成一體地說明本段談了什麼、問答脈絡與重要限定；它不是 current
   Semantic Memory，也不能直接當員工逐字來源。
2. **Extracted candidates（0..N）**：只列本段新出現、可獨立理解的工作資訊／案例細節／更正；
   它們是下一階段 Consolidation 的材料，不帶 add／update／delete 指令。

Runtime 把兩者綁定到 target segment 的可信 lineage。正常情況下，Consolidation 只看精簡
candidates；需要更多脈絡才開 segment summary；需要精確原話才沿 Runtime reference 回查
canonical conversation。這直接學習 OpenAI 的 summary＋raw extract 分工，也保留 Google 可檢查
extraction revision 與 AWS 小型 candidate 的優點。

- **優點**：上下文、候選資訊與逐字來源分層；後續不必每次重讀長對話；較容易觀測、重試與診斷
  「擷取錯了」還是「整併錯了」。一次呼叫可同時產出兩者，不等於多一次模型 round trip。
- **代價**：比只輸出 candidates 多一些 token／storage；若最終採 LangMem combined manager，需在
  framework gate 驗證能否取得等價中間結果，或是否只需一層很薄的 extraction adapter。

#### 方案 2：只產生 Extracted candidates

target segment 只轉成 0..N 筆 standalone candidates，不另存 segment summary。這較接近
Google／AWS 的最小公開輸出。

- **優點**：最省 output token、資料面最小。
- **代價**：candidate 的語境若不足，Consolidation 必須更常回讀原始 conversation；長訪談較難
  調試「為何抽到這筆」，也失去 OpenAI 特意保留 summary 作 deeper evidence 的分層優勢。

#### 方案 3：直接交給 LangMem manager 改 final Memory

不保存獨立 Extraction 中間結果，直接讓 manager 搜尋現有 Memory 並更新。

- **優點**：框架接線最少。
- **代價**：把 B 與 Consolidation 合併，無法分辨抽取錯誤和整併錯誤；也偏離本輪已核准要先學
  OpenAI 兩階段責任的方向。**不建議作目前預設，但保留後續以實證證明功能等價的可能。**

### 15.4 合法空結果與不得誤判為空的情況

`Extracted candidates = []` 是成功，不是 retryable error，適用於：

1. 問候、確認收到、導覽操作或與員工工作無關的聊天；
2. assistant 提了問題，但員工尚未提供新工作資訊；
3. 本段只有不足以安全理解的模糊片語，擷取就必須猜測；
4. target segment 內原樣重複同一資訊，沒有新增限定或修正。

以下不得因方便而輸出空結果：

- 員工補了新的工作細節、例外、頻率、條件或案例；
- 員工明確更正先前說法；Extraction 應忠實擷取新說法，是否取代舊 Memory 留給
  Consolidation／必要時顧問澄清；
- 新說法可能與舊理解重複或衝突。Extraction 本題不讀 current Memory 作 final 判決，所以不能在
  這裡提前 skip；跨時間去重與修訂是下一題。

「員工沒有提到 O／P／K／S」也不是 Extraction 應憑空產生的 candidate。缺少某種分析資料可由
後續顧問 Skill／coverage 檢查發現，但 absence 本身不是員工陳述。

### 15.5 Product Owner 裁決

Product Owner 核准**方案 1**，但目前只核准概念契約，不核准 final schema：

```text
已封口、尚未抽取的 target conversation segment
  ＋ 有界 support context（只供消歧）
        ↓ background extraction，單次 call
segment summary
  ＋ 0..N extracted candidates
        ↓
等待後續 Consolidation；此時尚未改 current Semantic Memory／JD
```

這個選擇沒有要求每則員工訊息都跑一次模型，也沒有要求模型填 UUID、時間、版本、scope 或
來源 offset。Runtime 可將 target segment 與中間結果綁定，模型只負責語意內容；exact schema、
retention、重試與 framework adapter 後續再依核准責任設計。

### 15.6 本節刻意不決定

- candidates 如何與 existing Memory 比對、何時 add／update／delete／skip；
- correction／conflict 在 Consolidation 的正式狀態與是否需要員工確認；
- segment summary 與 candidates 保存多久、是否進正式資料庫；
- 背景 queue、debounce 秒數、batch size、token budget、模型與 reasoning effort；
- LangMem manager 是否足以功能等價，或需薄 extraction adapter；
- final Semantic Memory schema、JD 分析／編輯、UI 與員工審核。

### 15.7 直接來源

- [OpenAI Agents SDK — Agent memory：兩階段生成、conversation summary、raw memory、consolidation 與檔案分層](https://openai.github.io/openai-agents-js/guides/sandbox-agents/memory/)
- [OpenAI — Sandbox Agents](https://developers.openai.com/api/docs/guides/agents/sandboxes)
- [Google Cloud — Generate memories：extraction／consolidation、revision、empty result 與背景執行](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories?hl=en)
- [AWS — AgentCore Memory types：short-term events 與 long-term background strategies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-types.html)
- [AWS — Semantic extraction／consolidation default prompts 與最小輸出](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-system-prompt.html)
- [AWS — Long-term saving and retrieving insights](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-saving-and-retrieving-insights.html)
- [Anthropic — Memory Tool：執行中 client-side CRUD 與 tool-use loop](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Anthropic — Managed Agent Memory：聚焦文件、immutable versions 與 optimistic precondition](https://platform.claude.com/docs/en/managed-agents/memory)
- [Anthropic — Dreams：非同步、非破壞性的 Memory consolidation](https://platform.claude.com/docs/en/managed-agents/dreams)
- [LangMem — Delayed processing／debounce](https://langchain-ai.github.io/langmem/guides/delayed_processing/)
- [LangMem — Memory manager API](https://langchain-ai.github.io/langmem/reference/memory/)

### 15.8 Decision 與下一題

- **Decision**：2026-09-05 核准 B 每次只背景處理一段已封口的新 canonical conversation；
  較早內容只作有界消歧背景；一次產生 segment summary＋0..N extracted candidates；空
  candidates 是正常成功；B 不修改 current Semantic Memory 或 JD。
- **名詞釐清**：segment summary 保存該段問答的整體脈絡；extracted candidates 是從該段抽出、
  等待 Consolidation 整理的逐筆新工作內容。兩者都不是 Compaction continuation、正式
  Semantic Memory 或 JD。
- **Next gate**：G4.3b-4d 只討論 Consolidation 如何對照既有 current Semantic Memory，決定
  新增、補充、修正、去重、淘汰或 no-op，以及矛盾何時不得自行裁決。不得同時偷定 final
  Memory schema、C live repair、JD mutation 或 framework production wiring。

## 16. G4.3b-4d：B Consolidation 聚焦審核（已核准）

> **狀態：APPROVED（2026-09-05）。** 本節只把已核准的 `MEM-Q002` 效果——原始案例
> 不丟、共同理解不重複、重要差異保留、未解矛盾不選邊——映射到最新成熟 Consolidation
> 機制。不是重新討論案例要不要保存，也不在本題固定 final Memory schema、資料表或 production。

### 16.1 最新直接事實

| 來源 | 官方已出貨／公開的 Consolidation 行為 | 對本題的可靠結論 |
| --- | --- | --- |
| OpenAI Codex | Phase 2 由單一 global lock 串行更新；以前次成功 baseline 的 workspace diff 找新增、修改、刪除來源；先讀 raw inventory，只有高價值、模糊、重疊、衝突或需更強依據時才深讀 rollout summary；要求最小 churn、保留具體細節、不要過度合併，刪除來源時只移除 solely-supported 內容並保留仍有其他來源支持的部分。 | Consolidation 應做增量、來源敏感、必要時深讀，且不能把整塊 mixed Memory 因一項過時資訊全部刪掉。OpenAI 的 usage／recency forgetting 是 coding-agent 產品政策，不適合直接套成 Caliburn 工作真相的淘汰規則。 |
| Anthropic Managed Memory／Dreams | 每次 Memory 修改產生 immutable version，更新可使用 content hash precondition；Dreams 非同步讀 input Store＋Sessions，合併重複、替換過時／矛盾內容，預設建立另一份 output Store，input 不變，可先檢查再採用或丟棄。 | 支持版本化 current head、一致性保護與非破壞性全域整理；Dreams 是 research preview，且「最新值取代矛盾」不是 Caliburn 可直接採用的員工真實性規則。 |
| Google Memory Bank | 將 extracted information 與同 scope existing Memories consolidation，產生 CREATED／UPDATED／DELETED；預設比較 current revision，也可多讀歷史 revisions 作 corroboration；每次變更有 revision，可檢查與 rollback。 | 支持同 scope current head、create／update／delete、revision 與 rollback；Google managed contradiction policy 沒有提供「尚待員工釐清」結果，不能直接當產品 truth policy。 |
| AWS AgentCore | 預設 Semantic consolidation 對每筆 new memory 選 AddMemory／UpdateMemory／SkipMemory；Update 應保留原 details、timestamps、context 並整併冗餘；無變更回空 list。預設以語句 confidence cues 處理矛盾。 | Add／Update／No-op 是成熟共同操作族；保存細節是明確官方要求。但以「seems／definitely」決定哪個員工說法正確不適用於 Caliburn。 |
| LangMem | manager 自動搜尋 relevant existing Memories，能 insert／update，並可選擇啟用 delete；Store manager 持久化變更並保留 versioned history；可增加搜尋步驟取得更多 Memory。 | 可直接承接搜尋、CRUD 與背景 manager plumbing；generic instructions 不知道職務真相，且 `enable_deletes` 可關閉，適合先採保守政策。 |

### 16.2 真正可稱為跨家共同核心

1. Consolidation 的輸入不是只有新 candidate；還要取得同 scope、與它相關的 current Memory。
2. 共同最小操作族是 **create／update／no-op**；Google、Anthropic、LangMem 另有 delete，AWS 的
   Semantic default 則刻意沒有要求 delete，因此「自動硬刪除」不是共同必選能力。
3. 相同資訊不重複新增；同主題的新細節更新既有內容；真正不同且需獨立取回的資訊才新增。
4. 更新時不能因壓縮而遺失仍有效的具體條件、例外與細節；OpenAI、AWS 都直接要求保守整併。
5. current head 與歷史／來源分層；成熟服務以 revision、baseline 或新 output Store 提供可檢查、
   rollback 或 recovery 的路徑。
6. 日常 Consolidation 可以只先看相關 current Memories，再於重疊、模糊或衝突時深入更多 Memory／
   segment summary／canonical conversation；沒有共識要求每批都把全 scope 塞進一個 prompt。
7. 「語意矛盾該信哪個」沒有跨家共同答案：Google 可能更新／刪除、AWS 可能依 confidence cues、
   Anthropic Dreams 以 latest value 整理、OpenAI 要求看新舊 evidence 與 staleness。因此產品不能把
   任一 managed default 冒充員工真相。

### 16.3 不再重複討論的既有產品效果

[`MEM-Q002`](./2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md) 已核准：

- canonical conversation 保存每個案例原始內容；Semantic Memory 不固定一案例一筆；
- 相同案例 no-op，互補資訊更新，重要獨立差異新增；
- 明確更正修訂 current understanding；未解矛盾保留兩邊；
- 全面 JD 檢查才 exact-scope 盤點全部 current Memories，日常不必全量送入模型。

本題只補齊上述效果如何使用成熟 manager lifecycle，不復活舊元件或另建案例資料庫。

### 16.4 三個候選方案

#### 方案 1：直接採 managed default

把 candidates 交給 Google／AWS／LangMem 預設政策，讓它自動 create／update／delete／skip。

- **優點**：設定最少。
- **缺點**：AWS 可能依語氣 confidence 選邊，Google 可能刪除矛盾舊 Memory，generic manager 也可能
  過度合併；這會讓平台預設偷偷決定員工工作真相。**不建議。**

#### 方案 2：成熟 incremental manager＋保守 truth policy（建議）

```text
extracted candidates
  ＋ 少量相關 current Memories
        ↓ 必要時再深讀 summary／conversation／更多 Memory
Consolidation 產生語意 mutation plan
        ↓ Runtime 驗證 scope／existing reference／current revision
版本化寫入 current Semantic Memory
```

對每筆 candidate 的概念結果：

- **No-op**：既有 current Memory 已完整表達，沒有新增限定；
- **Create**：新的工作主題或必須獨立搜尋、理解、修訂的重要差異；
- **Revise**：同一主題的補充，或有明確對象的員工更正；更新後仍須保留原本有效細節；
- **Retire current head**：只有明確更正使整筆內容不再成立，或重複 Memories 合併後舊 head 已完全
  被另一 current Memory 涵蓋時使用。它表示退出一般 recall，不表示擦除 canonical conversation
  或 revision history。

不另發明 `merge／split` 操作：需要合併時可由「revise 保留完整內容＋retire 被取代 head」組成；
需要拆開時可由「revise 原 head＋create 獨立 Memory」組成。exact wire schema 留到 framework gate。

矛盾判斷採保守邊界：

1. **明確更正**：「剛才說錯，不是每週，是每月」，且對象／時點／條件唯一，可 revise current head；
2. **時間變化**：「以前每週，七月起改每月」要保留時間脈絡，不當互斥矛盾；
3. **條件／案例差異**：「平常自行核准，超過金額才主管核准」兩邊都保留；
4. **未解矛盾**：只有前後兩種互斥說法，沒有明確裁決時，不因新舊、語氣或模型 confidence 選邊。
   current Memory 應忠實保留兩種說法與「尚未釐清」的語意；下一次主顧問讀到後再決定何時詢問
   員工。Consolidation 背景工作本身不直接對員工發問。

這個方案用 LangMem／LangGraph Store 等成熟 primitive 承接搜尋、CRUD 與 history；Caliburn 只提供
不可由通用平台替代的職務真實性指令。它不要求額外 conflict table、confidence 欄位或模型填 ID。

#### 方案 3：每次都做 full-store rebuild

每批新內容都像 Anthropic Dreams 一樣，以完整 Store＋歷史 conversation 建立全新整理結果，通過後
切換 current Store。

- **優點**：全域去重與重新分組能力最強，舊 Store 天然可回退。
- **缺點**：每批成本與延遲高；Anthropic Dreams 本身仍是 research preview；對單一 JD 的持續訪談
  屬過度設計。可在將來實測出嚴重長期 fragmentation 時，作低頻 maintenance 候選；**不作第一版
  日常基線。**

### 16.5 建議方案的成本與完整性邊界

- 日常只比較少量相關 current Memories；遇到不確定、可能重複或衝突時才擴大搜尋，符合 OpenAI
  progressive deep-dive、Google／AWS candidate comparison 與 LangMem search-manager 路徑。
- 「沒有找到相似 Memory」不必盲目 create；manager 可再搜尋一次。exact query、limit、threshold
  與何時升級到較大範圍，留到 retrieval／cost gate 量測，不在本題猜數字。
- 最終或全面 JD 品質檢查仍 exact-scope 處理全部 current Memories；那是 coverage 工作，不要求
  每次 Consolidation 都全量重寫。
- Background Consolidation 失敗時不得發布部分 current heads；保留上一個成功 current view，
  中間 candidates 等待後續有界重試。transaction／CAS／serial writer 的實際做法留到 framework
  production gate。

### 16.6 本題刻意不決定

- final Memory 的欄位、`unknown／conflict` 是否需要薄欄位；
- model-visible mutation schema、一次可輸出幾筆 operation；
- retrieval query、top-k／threshold、embedding、全文搜尋與 exact-list escalation；
- revision retention、tombstone 的物理格式、CAS 或 per-JD serial writer；
- segment summary／candidate 保存期限、排程、模型與 token budget；
- C live repair、JD mutation、員工 UI 或 production migration。

### 16.7 直接來源

- [OpenAI Codex — Phase 2 consolidation canonical runtime template](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/consolidation.md)
- [OpenAI Codex — Memory pipeline README／Phase 1、Phase 2、lock、baseline 與 retry](https://github.com/openai/codex/blob/main/codex-rs/memories/README.md)
- [OpenAI Agents SDK — Agent memory](https://openai.github.io/openai-agents-js/guides/sandbox-agents/memory/)
- [Anthropic — Dreams](https://platform.claude.com/docs/en/managed-agents/dreams)
- [Anthropic — Managed Agent Memory／versions](https://platform.claude.com/docs/en/managed-agents/memory)
- [Google Cloud — Generate memories／consolidation actions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories?hl=en)
- [Google Cloud — Memory revisions／rollback](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/revisions?hl=en)
- [AWS — Semantic Memory consolidation prompt](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-system-prompt.html)
- [LangMem — Memory manager API](https://langchain-ai.github.io/langmem/reference/memory/)
- [LangMem — Semantic Memory extraction／update／delete examples](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/)

### 16.8 Decision 與下一題

- **Decision**：2026-09-05 核准方案 2：成熟 incremental manager 對 candidates 與相關 current
  Memories 作 create／revise／no-op；只有整筆已明確失效或合併後完全被涵蓋才 retire current
  head。明確更正可更新；時間／條件差異保留；未解矛盾不依 recency、語氣或 confidence 選邊，
  而是保留在 current knowledge，交給主顧問後續詢問。
- **Next gate**：G4.3b-4e 只討論 C live repair 的觸發條件、與 B background consolidation 的
  去重／一致性邊界，以及修補失敗時目前 run 如何安全繼續。不得同時偷定 final Memory schema、
  JD mutation 或 framework production wiring。

## 17. G4.3b-4e：C 執行中 live repair 聚焦審核（已核准）

> **狀態：APPROVED（2026-09-05）。** 本節只回答：什麼情況值得在目前 run 立即修補已讀取的
> stale Semantic Memory；如何讓稍後的 B consolidation 不重複新增或把修補倒退；若即時寫入
> 失敗，目前 run 能否安全繼續。這不是每回合強制 Memory 寫入，也不決定 JD mutation。

### 17.1 官方事實：hot path 是成熟能力，但不是跨廠強制預設

| 來源 | 官方已公開行為 | 本題能下的結論 |
|---|---|---|
| OpenAI Agents SDK Sandbox Memory | 每次 run 先用小型摘要與按需搜尋讀 Memory；`liveUpdate` 預設開啟，agent 發現 stale Memory 或使用者要求更新時可在同一 run 修改 `MEMORY.md`；延遲敏感或唯讀 run 可關閉。run 結束後另有 extraction／consolidation 生成流程。 | OpenAI 明確讓窄幅同輪修補與事後整理共存；即時更新不是每輪必做，且可因延遲或權限關閉。 |
| Anthropic Managed Agent Memory＋Dreams | session 中 agent 透過標準工具讀寫掛載的 read-write Memory；每次寫入形成版本。Dreams 之後再讀既有 Store 與 sessions，整理重複、矛盾與 stale 內容。API 更新可帶 `content_sha256` 前置條件；不相符時須重讀後重試。 | Anthropic 也把「執行中局部寫入」與「事後全域整理」分成兩層，並以版本／前置條件避免覆蓋別人的新修改；Dreams 仍是 research preview。 |
| Google Memory Bank／AWS AgentCore Memory | 主要託管路徑都是 conversation/event 寫入後，非同步 extraction＋consolidation；另提供直接 memory CRUD，但官方沒有把 agent 每輪即時修補列為所有應用的必要步驟。 | 背景整理是廣泛共同做法；C 是需要低 publication lag 的產品才選用的能力，不能冒充所有大廠都強制使用。 |
| LangMem | 正式區分 hot-path active formation 與 background formation：前者可立即更新關鍵資訊，但增加可感延遲與 agent 工具選擇負擔；後者不阻塞互動且適合較完整反思。`create_manage_memory_tool` 支援以 ID create／update／delete。 | Framework 已提供 C 的主要工具能力；產品仍須限制何時使用，不能把「存在 Tool」誤寫成「每輪必須呼叫」。 |

**跨來源可支持的結論：**成熟系統可以同時有 hot-path 與 background Memory；hot path 的價值是
降低關鍵修正的 publication lag，background 的價值是高召回、較完整的去重與整理。它們是互補
路徑，不是兩套都在每則訊息後重做同一份工作。

### 17.2 三個候選

#### 方案 1：完全沒有 C，只等待 B

- **優點**：最低互動延遲、最少 Tool call，也沒有 B／C 競寫。
- **缺點**：員工已明確更正一筆本輪讀到的 stale Memory 時，在 B 尚未發布前，後續 run／substep
  仍可能再次取到舊內容。只能依賴目前 conversation 暫時壓過它。
- **判斷**：適合唯讀或極度延遲敏感 agent，不適合 Caliburn 把「反覆修正員工工作理解」列為
  核心效果的情境。

#### 方案 2：每逢新工作資訊就在 hot path 更新 Memory

- **優點**：Memory 最快變新。
- **缺點**：把 extraction／consolidation 工作塞回主顧問；每輪增加延遲、Tool 決策與寫入，零碎
  訪談容易造成 churn、重複與不完整整理，正好失去 B 的用途。
- **判斷**：不採用。LangMem 官方也明示 hot path 會增加延遲與 agent 負擔。

#### 方案 3：dependency-aware 的窄幅 C（建議）

只有下列條件**全部成立**才立即修補：

1. 本輪已實際讀到一筆完整 current Memory，而非只看到小型導覽或搜尋摘要；
2. 本輪 canonical 員工訊息清楚證明該 Memory 的具體內容已過時，且可唯一定位修訂目標；
3. 這是明確更正／明確新狀態，不是仍有多種合理解釋的疑似矛盾；
4. 同一 run 後面確有動作需要依賴修正後理解，或在 B 發布前再次取回舊值會造成實質錯誤。

若只是普通補充、新案例、尚未確定的衝突，或本輪後面不再依賴該筆持久 Memory，主顧問直接使用
目前 conversation 的新資訊完成回覆，交給 B 後續整理；不為了「讓 Store 立刻漂亮」增加一次寫入。

### 17.3 建議的同輪流程

#### C 到底修改什麼：直接修訂一筆 current Memory，不執行 B

官方公開設計在**責任分工**上相當一致，但底層資料表示與 mutation API 不相同：

- OpenAI `liveUpdate` 透過 Filesystem 能力，要求目前 agent 在同一 run 驗證新證據、繼續使用
  新證據，並在 final response 前直接編輯已讀到的 `MEMORY.md`；run 結束後的
  extraction／consolidation 是另一條流程。OpenAI 公開介面是檔案編輯，沒有公開「單筆
  Memory ID＋record replacement」契約。
- Anthropic 讓 session 中的 agent 直接讀寫掛載 Memory；Dreams 是另外啟動的非同步
  consolidation job；直接 API 則可依 memory ID 更新完整內容。
- LangMem 的 hot path 使用 `create_manage_memory_tool`，background 則使用
  `create_memory_store_manager`／ReflectionExecutor；其 `manage_memory` Tool 依 ID 更新 Store
  record。兩者不是同一個呼叫的不同名稱。

因此跨廠共同點是「直接修補目前 Memory artifact，不同步執行背景 consolidation」，不是
「所有產品都使用同一種 ID schema」。Caliburn 若以 LangGraph Store＋LangMem 實作，本設計中的 C
**不呼叫 B，也不重新跑 extraction／consolidation**，而是只對本輪已搜尋並
深讀的一筆 current Semantic Memory 做 direct update。這裡的「一筆」是可獨立取回的完整
Memory record／current head，不是讓模型指定起訖位置去改一段任意字串：

1. 搜尋結果提供既有 Memory ID；
2. 主顧問取得該筆完整 current content；
3. 只改已明確過時的敘述，但提交的是保留其他有效細節後的完整新版 record；
4. Store 以同一 ID 發布新版 current head；若有搜尋索引，由 Store 的更新路徑重新索引；
5. 跨多筆去重、重新分組、從 conversation 發現其他新知，仍交給 B。

如果一項更正無法唯一定位、同時牽涉多筆 Memory，或必須比較較大範圍才能知道該怎麼改，
就不符合 C 的窄幅門檻。主顧問本輪以 current conversation 的新資訊繼續或詢問員工，之後由 B
做完整整理；不能為了立即發布而把 B 同步塞進主 run。

```text
本輪 current input 已進 canonical conversation
  → A 搜尋並深讀 current Memory M7
  → 員工新訊息明確指出 M7 的一項理解已過時
  → 若仍有歧義：不寫 C，正常詢問員工
  → 若四項門檻都成立：以 M7 的既有 ID 做窄幅 update
       ├─ success：Tool result 回到同一 agent loop；後續依賴動作使用新版
       └─ error：不得宣稱已更新；依 §17.5 的失敗邊界處理
  → run 正常完成
  → 相同 conversation segment 仍交給 B extraction
  → B consolidation 讀最新 current Memory
       ├─ C 已正確涵蓋：no-op
       ├─ 新 segment 還有其他補充：revise／create
       └─ 不能以 C 之前的 stale snapshot 覆蓋新版
```

**C 不消耗或隱藏 B 的輸入。**同一員工更正仍進 canonical conversation，B 仍正常 extraction；
B 是否 no-op 由「candidate 與最新 current Memory 是否已有相同語意」判斷。這讓事後 manager 可補
完整性，也避免另外發明 `handled_by_live_repair` 之類模型欄位。

### 17.4 不重複、不倒退的必要一致性規則

1. C 只修補已深讀的完整 Memory，保留其仍有效細節；不得從 routing summary 或截斷 snippet
   直接整筆覆寫。
2. C 使用搜尋／讀取結果提供的既有 Memory ID；模型不自行捏造 ID、scope、版本或時間。
3. B 發布前必須對照**最新 current head**；相同內容 no-op，不因同一 conversation 同時經過 C 與 B
   就新增第二筆。
4. B 與 C 不得各自以舊 snapshot blind overwrite。成熟官方機制有兩種：OpenAI 的 serial/global
   lock；Anthropic 的 optimistic precondition＋失敗後重讀。Caliburn exact 選擇留到 G4.3b-4f。
5. current head 可更新，canonical conversation 與舊 Memory revision 不因 C 被刪除。

Framework 邊界必須如實記錄：LangMem 的現成 `manage_memory(content, id, action)` 已覆蓋模型可用的
窄幅 update；但目前 LangGraph `BaseStore.put` 公開介面與 LangMem Tool schema 沒有 Anthropic 式
version precondition。故「如何 serial／compare-and-swap」是 G4.3b-4f 真實缺口，不能宣稱 framework
已自動保證，也不在本題先發明實作。

### 17.5 寫入失敗不是語意衝突

- 參數／目標錯誤：把 framework-native Tool error 回給同一 agent loop，允許有界修正；exact retry
  次數留到 G4.3b-4f。
- 版本已變：重讀最新 Memory，再判斷修補是否已被涵蓋或仍需重試；不得盲目覆蓋。
- 暫時性儲存失敗：current input 已在 canonical conversation，模型本輪仍看得到員工新說法；可以
  完成不依賴「Memory 已持久化成功」的一般回覆，但不得聲稱 Memory 已更新。B 稍後仍可從同一
  conversation segment 整理。
- 若後續步驟的正確性真的依賴已成功發布的新 Memory，該步驟必須停在 Tool error，而不是假設成功。
- 新舊內容仍有多種合理解釋不是技術寫入失敗；這種情況一開始就不呼叫 C，而是詢問員工。

### 17.6 建議裁決與刻意保留的未決項

**建議核准方案 3：**保留框架原生 hot-path Memory Tool，但只作 dependency-aware、可唯一定位、
明確 stale 的窄幅修補。普通新資訊與整體整理一律留給 B；C 成功後 B 仍讀同一來源並以最新 head
做 no-op／補充。這最接近 OpenAI live update＋背景生成、Anthropic session write＋Dreams，以及
LangMem hot/background 的共同形狀，同時控制長訪談的成本與失敗面。

本題不決定：

- Tool 的 final 名稱、JSON schema、provider binding；
- 用 serial writer、optimistic version check 或兩者結合；
- retry 次數、timeout、queue 與監控；
- final Memory schema、背景排程數字、JD mutation 或 UI。

### 17.7 直接來源

- [OpenAI Agents SDK — Agent memory：progressive read、liveUpdate、兩階段 background generation](https://openai.github.io/openai-agents-js/guides/sandbox-agents/memory/)
- [OpenAI Agents SDK Python — liveUpdate 原始指令：驗證現況、使用新證據、final response 前直接編輯 MEMORY.md](https://github.com/openai/openai-agents-python/blob/main/src/agents/sandbox/memory/prompts.py)
- [OpenAI Codex — Phase 2 consolidation canonical runtime template](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/consolidation.md)
- [Anthropic — Managed Agent Memory：session 讀寫、版本、optimistic precondition](https://platform.claude.com/docs/en/managed-agents/memory)
- [Anthropic — Dreams：session incremental writes 與事後 consolidation](https://platform.claude.com/docs/en/managed-agents/dreams)
- [Google Cloud — Generate memories：非同步 extraction／consolidation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)
- [AWS AgentCore — Memory types：event 與非同步 long-term extraction／consolidation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-types.html)
- [LangMem — Core concepts：hot path／background 的用途與成本](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)
- [LangMem — Memory Tool API：以 ID create／update／delete](https://langchain-ai.github.io/langmem/reference/tools/)
- [LangGraph — BaseStore `put` 公開介面](https://reference.langchain.com/python/langgraph.store/base/BaseStore/put)

### 17.8 Decision 與下一題

- **Decision**：2026-09-05 核准方案 3。C 以既有 ID 直接更新一筆已完整讀取的 current
  Memory，不同步執行 B；跨多筆比較、去重與重整仍交給 B。只有修訂目標唯一、內容明確過時，
  且同輪後續真的依賴新版時才即時修補；否則由 current conversation 支撐本輪，交給 B。
  C 成功不會讓 conversation 跳過 B；B 仍正常整理，但必須讀最新 head 並對已涵蓋內容 no-op。
- **Next gate**：G4.3b-4f 只做整體成本、失敗、觀測與 framework 最終責任 mapping；其中須依
  已核准的框架無關 Memory 契約，確認 final logical record contract 與物理 Store 表示是否仍有
  真實缺口。不得因 OpenAI 使用 Markdown 就直接選 Markdown，也不得先進 production wiring。

## 18. G4.3b-4f-1：單筆 Semantic Memory 邏輯內容與責任邊界（Product Owner 已核准）

> **狀態：APPROVED（2026-09-05）。** 本節只裁決一筆 current Semantic Memory 在邏輯上
> 需要哪些模型撰寫內容，以及哪些可信欄位必須由 framework／Runtime 管理。本節不決定 PostgreSQL
> 實體欄位、Markdown／JSON 序列化、current-head／revision／CAS、索引或 production wiring。

### 18.1 各家實際公開的資料形狀

| 來源 | 語意內容 | 可信識別／組織資訊 | 能直接支持的事實 |
|---|---|---|---|
| OpenAI Codex／Agents SDK Sandbox Memory | `MEMORY.md` 以可搜尋的 Task Group／Task 標題、scope、keywords 與具體內容組成；另有更小的 `memory_summary.md` 導覽與更深的 rollout summaries。 | 檔案路徑、workspace／layout 與 rollout references；其格式針對 coding／sandbox agent。 | 標題、關鍵詞與自足內容有助 progressive disclosure；但 Markdown block schema 是 Codex domain schema，不是通用 Memory record 標準。 |
| Anthropic Managed Agent Memory | 一筆 Memory 是一份 `content` text document；官方建議 many small focused files。 | service-issued `id`、hierarchical `path`、current `memory_version_id`、hash、size、created／updated time；path 可改名而 ID 不變。 | 聚焦文字與可信 identity／version 分離；path 承擔 routing label，但沒有另要求 `title` semantic field。 |
| Google Memory Bank | current Memory 的核心語意是單一 `fact`；生成時可被標記一或多個 managed／custom `topics`。 | resource `name`、immutable `scope`、create／update time、optional metadata；revision 另保存 extracted facts 與 consolidated fact。 | 最小語意可以只有完整 fact；topic 是可選 routing／filter 維度，不是所有 record 都必須由模型另填標題。 |
| AWS AgentCore Semantic Memory | 預設 extraction schema 只有 `language＋fact`，fact 必須是 standalone；consolidation 以既有 record ID 做 add／update／skip。 | `memoryRecordId`、strategy ID、namespace、created time 與 optional metadata 由服務承接。 | 自足 fact＋system metadata 是成熟形狀；更多結構化欄位屬可選、domain-specific metadata schema，不是 semantic Memory 共同硬欄位。 |
| LangGraph Store／LangMem | Store value 是任意 JSON document；LangMem 未指定 schema 時用 string content，也允許 Pydantic custom schema。Memory Tool 的預設語意輸入是 `content`，更新／刪除另帶既有 `id` 與 `action`。 | Store `namespace＋key＋created_at＋updated_at`；Tool／Runtime 可固定 namespace，Store key 可作 LangMem ID。 | Framework 原生可承接 content-only 或極薄 custom schema；不需為 `title＋content` 另建一套 Memory engine，但 title 也不是 framework 強制欄位。 |

### 18.2 跨家共同核心與明確差異

**直接共同核心：**

1. 長期 Semantic Memory 不是整段 raw conversation；它是整理後、可獨立取回的文字／document／fact。
2. 語意內容應在離開原始對話後仍足以理解；各家分別使用「rich block」「focused text document」或
   「standalone fact」表達相同責任。
3. canonical identity、scope／namespace 與建立／更新時間由 storage／service／Runtime 管理，不能要求
   模型捏造。
4. collection 可以有多筆並持續 create／update／delete 或 no-op；語意內容與 mutation intent／storage
   metadata 是不同責任。
5. 結構化 schema 是可選且依 domain 設計。沒有跨家共同要求把 action、object、frequency、status、
   confidence、Duty／Task／OPKS、source UUID 或 Skill ID 拆成模型必填欄位。

**不是共同 schema：**

- `title`：OpenAI 用 heading、Anthropic 用 path、Google 用 topic、AWS 預設沒有獨立 title；它是有用的
  routing 概念，但不是每家都用相同欄位。
- Markdown：只是一種 file-native representation；Google／AWS 使用 records，LangGraph 使用 JSON document。
- per-memory canonical message reference：OpenAI 的 coding Memory 保留 rollout-summary references；Anthropic
  Memory object 未公開 conversation linkage；Google 可在 revision label 記 data source；AWS record API 也
  沒有共同的 canonical message-ref 欄位。因此 reference deep-read 是 Caliburn 的產品需求與 Runtime
  mapping，不能冒充跨廠共同 semantic field。
- immutable revision／CAS：Anthropic與 Google 原生提供；LangGraph `BaseStore.put` 沒有文件化 expected-version
  precondition。這屬後續一致性決策，不應塞進模型內容。

### 18.3 三個候選邏輯形狀

#### 方案 A：模型只撰寫 `content`

```text
semantic document: content
framework/runtime: id, scope, timestamps
```

- **優點**：最接近 LangMem 預設，也與 Google／AWS 的 fact record 對齊；模型 schema 最小。
- **缺點**：導覽、list UI 與 keyword routing 只能截取 content、另做 title 生成，或每次讀較多全文；把
  title 改成 derived projection 仍需定義穩定且有辨識力的生成規則。

#### 方案 B：模型撰寫 `title／topic＋rich self-contained content`（建議保留 A+）

```text
semantic document
  title:   短、可辨識、可搜尋的工作主題標籤
  content: 聚焦、自足、保留 JD 判斷所需細節的目前理解

framework/runtime
  id/key, exact JD scope/namespace, created_at, updated_at
```

- **優點**：只有兩個簡單語意欄位，仍可由 LangMem custom schema 原生驗證；title 可直接支援小型導覽、
  人類檢視、lexical／hybrid query 與同名主題消歧，不必再呼叫模型生成另一份 routing label。
- **缺點**：title 並非跨家硬欄位，模型可能改名或產生相似標題；因此它只能是可修訂的 routing label，
  不能當 stable identity、scope 或完整性邊界。

#### 方案 C：模型撰寫多個職務結構欄位

例如 `action／object／purpose／condition／frequency／status／confidence／source refs`。

- **優點**：可直接 filter 或顯示個別維度。
- **缺點**：不是跨家共同 Semantic Memory schema；增加 strict schema 失敗面，會把未知資訊逼成空欄或猜測，
  也容易把 Memory 誤綁成 JD 欄位。與已核准「Memory 保存工作資訊、LLM＋Skill 才決定 JD」責任衝突。
- **判斷**：不建議。

### 18.4 若採方案 B，欄位責任仍須保持極薄

**模型／Memory manager 可以產生：**

- `title`：語意 routing label；可改名，不能當 identity；
- `content`：一項完整、自足、目前有效的工作主題；未知／未解矛盾直接以自然語言忠實表達。

**模型可選擇但不是 Memory 內容：**

- create／update／delete／no-op mutation intent；
- update／delete 時只能原樣使用搜尋結果實際提供的既有 `id`。

**Framework／Runtime／Store 產生或固定：**

- stable `id／key`、該 JD 的 exact `namespace／scope`、created／updated time；
- current-head／revision／hash／writer ordering（若後續一致性設計證明需要）；
- canonical conversation lineage（若後續保留），不得要求模型填 message ID、quote offset 或 source UUID。

**明確不加入模型 schema：**

- status／kind／conflict_type／confidence；
- Duty／Task／OPKS ID 或 JD 欄位；
- Skill ID／receipt；
- scope、version、timestamp、retry、權限與 observability metadata。

### 18.5 Decision 與下一題

**Decision：**Product Owner 於 2026-09-05 核准方案 B。單筆 current Semantic Memory 的模型語意內容
採用 `title＋rich self-contained content`；其餘 identity、scope、時間與可信 Runtime metadata 不交給模型
填寫。A+ 的地位必須說精確：它不是「跨家共同 schema」，而是以共同責任為底、採用
OpenAI heading／Anthropic path／Google topic 共有的 routing 作用，再映射成 LangMem 可原生承接的兩欄
custom schema。相較 content-only，它只多一個低複雜度欄位，卻避免另建 title projection 或每次讀全文；
相較 richer schema，它不會把 JD 結構、來源、狀態與可信 metadata 推給模型。

**Next gate：**`G4.3b-4f-2` 只裁決 canonical conversation lineage。它要回答：每筆 Memory 是否真的需要
持久 conversation reference；若需要，應屬於 current semantic record、revision／generation lineage，或於
需要時由 extraction artifact 解析。模型不得填 message ID。本題不決定 PostgreSQL 實體 schema、CAS、
JD mutation 或 production wiring。

### 18.6 直接來源

- [OpenAI Agents SDK — Agent memory](https://openai.github.io/openai-agents-js/guides/sandbox-agents/memory/)
- [OpenAI Codex — Phase 2 consolidation template 與 MEMORY.md strict format](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/consolidation.md)
- [Anthropic — Managed Agent Memory](https://platform.claude.com/docs/en/managed-agents/memory)
- [Anthropic API — List memories／basic 與 full projection](https://platform.claude.com/docs/en/api/beta/memory_stores/memories/list)
- [Google Memory Bank — API quickstart／Memory `fact＋scope`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/api-quickstart)
- [Google Memory Bank — generated topics、metadata 與 filtering](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/fetch-memories)
- [Google Memory Bank — revisions／current consolidated fact](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/revisions)
- [AWS AgentCore — semantic-memory extraction／consolidation schema](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-system-prompt.html)
- [AWS AgentCore — MemoryRecord](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_MemoryRecord.html)
- [LangChain — long-term Memory／LangGraph Store JSON document](https://docs.langchain.com/oss/python/langchain/long-term-memory)
- [LangGraph — Store Item fields](https://reference.langchain.com/python/langgraph.store/base/Item)
- [LangMem — Memory manager custom schema](https://langchain-ai.github.io/langmem/reference/memory/)
- [LangMem — model-facing Memory Tool](https://langchain-ai.github.io/langmem/reference/tools/)

## 19. G4.3b-4f-2：Canonical conversation lineage／reference（G2 完成；待 Owner 裁決）

> **狀態：OPEN（2026-09-05）。** 本節不重開「是否需要回查原始訪談」：`MEM-Q003` 與
> 2026-08-30 Memory landscape 的 D5 已核准 Semantic Memory 必須可按需回讀 canonical
> conversation，且逐字 message／quote citation 不是每筆 Memory 的通用必填欄位。本節只裁決
> **這條關聯應由誰產生、放在哪一層、最小粒度到哪裡**。不決定 PostgreSQL 實體 schema、
> retention、CAS、Tool 最終名稱、JD mutation 或 production wiring。

### 19.1 先分清三個不同物件

1. **Current Semantic Memory**：模型日常搜尋、讀取與修訂的目前理解；依 §18 已核准模型只撰寫
   `title＋rich self-contained content`。
2. **Mutation／revision／generation lineage**：記錄「哪一次 extraction／consolidation／live repair
   產生這個版本，以及當時處理哪一段 canonical conversation」的可信執行資料。
3. **Canonical conversation**：Checkpointer 內完整、耐久的員工↔顧問訊息與 Tool history；需要核實、
   更正、衝突或久遠細節時才有界深讀。

`source_context_ref` 以下只是一個**邏輯稱呼**：由 Runtime 依已封口的 canonical conversation segment
建立、不可由模型捏造，能解析回一段有界原始訪談。它不先承諾是一個 message ID、起訖欄位、資料表
foreign key 或 Tool 參數。

### 19.2 最新官方資料直接支持什麼

| 來源 | Official fact | 對本題能直接支持什麼 | 不能據此聲稱什麼 |
|---|---|---|---|
| OpenAI Codex／Agents SDK Sandbox Memory | Session message history 與跨 run Memory 分離；公開 Memory layout 同時保留 raw session JSONL、rollout summaries、durable Memory 與小型 summary。Codex 本機 Memory 文件另明載 memory artifacts 含 prior chats 的 supporting evidence。 | 原始 conversation、詳細橋接內容與 current Memory 可分層保存；核實時可往較深 artifact 走。 | 官方通用 API 沒有公布「每筆 semantic record 必填 message IDs」的跨產品 schema。 |
| Anthropic Managed Agent Memory | Current Memory 是 path-addressed text document；每次 mutation 建 immutable version。`memory_version.created_by` 可帶 agent `session_id`，官方要求另從 Sessions API 查 session provenance。 | 寫入者／來源 session 歸屬於 version lineage，而不是要求模型把來源塞進 current text content。 | `session_id` 不是逐句證據；Anthropic 沒要求每個 current Memory 包含 message refs。 |
| Google Memory Bank | Current `Memory` 是可由多個 requests／data sources 形成的 consolidated state；`MemoryRevision` 保存該次 mutation snapshot，GenerateMemories revision 另含 consolidation 前的 `extracted_memories`。呼叫者可把 `data_source` 等可信值放入 `revision_labels`。 | Extraction source 與 current consolidated fact 應分層；data-source lineage 適合跟 revision／generation 綁定。 | 任意 revision label 是 application-supplied metadata，不是 Google 替所有產品定義的 conversation reference schema。 |
| AWS AgentCore Memory | Immutable、timestamped Events 依 actor／session 保存；long-term Memory records 是另行抽取的層。Event metadata 只有 schema 指定的 keys 才進 extracted record，其他會被忽略。 | Canonical events 與 derived records 分離；可信來源 ID 不應靠 LLM 從文字推測。 | AWS 公開 contract 沒有自動保證每筆 Memory record 都保留 exact source event IDs。 |
| LangMem／LangGraph Store | Memory manager 接收 messages＋existing memories並產生 insert／update／delete；Store 提供 Runtime-issued key、namespace 與時間。Custom schema 可規定語意內容。 | Framework 可原生承接 `title＋content`、existing ID 與 CRUD。 | LangMem 沒有內建跨 conversation segment 的 provenance／source-reference contract；若產品需要，必須由 Runtime 以可信 input 補上，不能讓模型填。 |

### 19.3 跨家共同點與真正差異

**共同且可直接採用的責任：**

1. raw conversation／events 與整理後 Semantic Memory 是不同層；
2. current Memory 可以由多個來源與多次更新形成；
3. identity、scope、time、writer／session 等可信資訊由 service／Runtime 建立；
4. mutation history／revision／supporting-evidence 層可承接「這次怎麼形成」，不用污染 current
   semantic content；
5. exact message／quote linkage 不是跨家共同的每筆必填 schema。

**各家不同、不能假裝已有共同標準的部分：**

- OpenAI 使用檔案／rollout artifacts；Anthropic 使用 memory versions＋session actor；Google 使用
  revisions＋optional labels；AWS 使用 events、records 與 strategy schema。
- retention、是否保留完整 revision chain、是否能直接由 current head 列出全部 supporting sources，
  並沒有跨家相同契約。
- LangMem／LangGraph Store 不會自動複製其中任何一家完整 lineage 模型。

因此「每筆 Memory 都塞 `message_refs[]`」不是大廠共識；「來源與 current semantic content 分層，
可信 lineage 由 Runtime／service 管理」才是共同形狀。

### 19.4 三個可回答的方案

#### 方案 A：把 `message_refs[]` 放在 current Semantic Memory

```text
current memory = title + content + message_refs[]
```

- **優點**：讀到 Memory 就能直接取得原始訊息位置。
- **缺點**：一筆 Memory 經多輪補充、合併與更正後，refs 容易持續膨脹；必須另外定義繼承、刪除、
  合併與 stale 規則；也會把可信 Runtime metadata 拉進模型／semantic schema。
- **判斷**：不是跨家共同做法，也與 §18 已核准的極薄模型內容衝突，不建議。

#### 方案 B：由 Runtime 把來源放在 mutation／revision／generation lineage（建議）

```text
current Semantic Memory
  └─ title + content

Runtime-owned current revision / generation lineage
  └─ one or more opaque source_context_ref
       └─ resolves to a closed, bounded canonical conversation segment
```

- 模型只撰寫 `title＋content`，不填 message ID、range、version、time 或 UUID。
- Runtime 已知 extraction／live-repair 實際讀取的 canonical segment，因此由 Runtime 綁定 reference；
  不讓模型重新抄寫來源。
- Current head 不複製一串 provenance；需要核實時，由 current revision／generation lineage 解析到
  canonical conversation。
- 同一 current Memory 若歷經多次來源與 consolidation，可以有 1..N lineage inputs；本題不先規定
  物理 join table、revision retention 或 inheritance algorithm。
- exact message／quote reference 只在 Runtime 已能可靠取得、或後續代表性測試證明 segment 不足時作
  optional supporting evidence，不作第一版通用必填。

**優點**：最符合 OpenAI 的 evidence／rollout 分層、Anthropic 的 version→session attribution、Google 的
revision→data-source／extracted-memory 分層；也維持 LangMem 模型 schema 簡單。

**代價**：LangMem／BaseStore 不會自動建立這條 lineage；正式 framework mapping 必須確認能否用既有
checkpoint／Store metadata 或 revision primitive 承接，若不能，才允許一個最薄 Runtime adapter。

#### 方案 C：不保存 lineage，需要時掃描 canonical conversation

- **優點**：沒有額外 reference 資料。
- **缺點**：長訪談只能靠 semantic／exact scan 重新找來源，成本、延遲與漏找風險都較高；也使已核准的
  progressive deep-read 無法穩定從 selected Memory 導向相關 conversation。
- **判斷**：與 `MEM-Q003`／D5 已核准的產品能力不一致，不建議。

### 19.5 建議裁決與邊界

**建議核准方案 B：**保留已核准的 canonical deep-read，但不把 `message_refs[]` 加進模型撰寫的
Semantic Memory。Runtime 應替每次實際 Memory mutation／revision 保存至少一個可解析的
`source_context_ref`，指向當次處理的已封口 canonical conversation segment；exact message／quote 只作
optional supporting evidence。

這項裁決若通過，仍**不等於**已決定：

- PostgreSQL tables／JSON shape、revision retention 或 CAS；
- search result 是否直接附 reference，或由另一個 read path 依 Memory ID 解析；
- reference 的 final 名稱、segment 起訖表示與 fallback scan；
- background worker、retry、JD Tool、UI 或 production migration。

上述第一個後續問題應是 model-facing read projection：模型搜尋到 Memory 後，應拿到一個可用的 opaque
source handle，還是只帶 Memory ID 交由 Runtime 解析；它不能與本輪 lineage placement 綁在一起偷決定。

### 19.6 本輪唯一 blocking question

是否核准**方案 B**：模型內容維持 `title＋content`；可信 canonical conversation 關聯由 Runtime 放在
mutation／revision／generation lineage，指向一段已封口、有界的 conversation segment；exact
message／quote reference 不作通用必填？

### 19.7 直接來源

- [OpenAI API — Sandbox Agents：Session 與 Memory 分層、progressive disclosure、raw sessions／rollout summaries／Memory layout](https://developers.openai.com/api/docs/guides/agents/sandboxes)
- [OpenAI／ChatGPT Learn — Codex local memories：summaries、durable entries、recent inputs 與 supporting evidence](https://learn.chatgpt.com/zh-Hant/docs/customization/memories)
- [Anthropic — Managed Agent Memory：focused documents、immutable versions](https://platform.claude.com/docs/en/managed-agents/memory)
- [Anthropic API — Memory Versions：`created_by.session_id` 與 Sessions provenance](https://platform.claude.com/docs/en/api/beta/memory_stores/memory_versions/list)
- [Google Cloud — Memory revisions：current consolidated state、`extracted_memories`、`revision_labels.data_source`](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/revisions)
- [AWS AgentCore — Memory terminology：immutable events、sessions 與 derived records](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-terminology.html)
- [AWS AgentCore — Long-term Memory metadata：event metadata 到 record 的 schema-controlled flow](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-memory-metadata.html)
- [LangMem — Extract semantic memories：manager input、custom schema、Store CRUD](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/)
