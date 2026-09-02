# Memory conversation／semantic responsibility reconciliation

- 日期：2026-09-03
- Topic ID：`MEM-Q001`
- 階段：**G3 Product Owner 已於 2026-09-03 核准；successor ADR 仍待建立**
- 狀態：**Working Decision；不授權 production、ADR 或 spike 施工**
- 決策入口：[`../current-decisions.md`](../current-decisions.md)
- 產品效果基線：[`2026-09-01-framework-independent-memory-contract.md`](./2026-09-01-framework-independent-memory-contract.md)

> 本文只回答一題：完整可續接 conversation、可修訂長期 semantic Memory、LangGraph Checkpointer／Store 與可選 Memory manager 應如何分工，以及是否需要把員工原話再複製成第二份 source leaf。A／B 相似案例如何整理與召回屬 `MEM-Q002`，本文不提前設計其 schema、embedding 或 admission policy。

## 1. 結論摘要

直接官方資料支持的跨家共同形狀是三層，而不是兩份相同來源：

1. **Durable conversation／event history**：保存員工與 AI 的實際互動，供續談、恢復及必要時回查原話；
2. **Derived semantic Memory**：從 conversation／events 抽取、整理、合併及修訂的長期知識；
3. **Model-facing context**：每次 run 只從前兩層組裝當下必要內容；限制、compaction 或 summary 只改本輪模型輸入，不等於刪除 canonical conversation，也不等於 semantic Memory。

`MEM-Q001` 的建議候選是：

```text
LangGraph Checkpointer
  = 一份 JD thread 的完整員工↔顧問 conversation
  + graph/run/interrupt/resume 所需狀態

LangGraph PostgreSQL Store
  = 該 JD 的可修訂 semantic Memory collection
  + CRUD／list／search

Memory manager（是否採 LangMem，留待後續窄驗證）
  = conversation delta + existing relevant Memory
    → add／update／delete／no-op 的候選變更
  ≠ conversation owner
  ≠ persistence owner

Context assembly
  = recent/relevant conversation + relevant semantic Memory + current input
  = non-destructive model view，不回寫成另一份 authority
```

**不建議建立重複的 `employee-source` 文字 leaf。**員工原話就是 canonical conversation 中的 user message；若 semantic Memory 日後需要來源關聯，只引用 runtime 產生的 message ID，不複製原文。員工更正是新的 user message；舊訊息保留在 conversation，semantic Memory 再依新資訊修訂。

這是目前最少重複、最貼近 OpenAI／Anthropic／Google／AWS 公開責任分層，也最直接使用 LangGraph 官方 primitive 的候選。它會取代現行 ADR 0060 的一部分 authority，因此在 Owner 裁決後仍必須另開 successor ADR；本文本身不改 production。

## 2. 本輪研究方法與停止條件

### 2.1 研究順序

1. 先以 `MEM-D001`～`MEM-D003` 判斷產品效果，不用舊元件替方案找理由；
2. 回到 OpenAI、Anthropic、Google、AWS 與 LangGraph／LangChain 的直接官方契約；
3. 將每項主張分成 Official fact、Inference、Caliburn mapping 或 Unknown；
4. 對照現行 code，確認候選是真正的責任變更，不只是名詞替換；
5. 最多保留三個實質方案，依完整性、錯誤風險、成本、複雜度與可逆性比較。

### 2.2 已達停止條件

- 多家來源都公開了 conversation／event 與 derived Memory 的分層；
- 沒有官方來源要求同一份 user message 必須同時存在 conversation 與額外 source leaf；
- LangGraph 已明確公開 Checkpointer、Store、request shaping 與 checkpoint storage growth 的契約；
- 剩餘不確定性是 implementation contract（長 thread 儲存量、Memory formation 品質），不再影響本輪責任分工選擇；
- 新增同類官方資料已不再產生第四種責任模型。

因此本輪停止廣泛搜尋；本方案其後已由 Product Owner 核准，正式 production 變更仍須 successor ADR 與獨立施工授權。

## 3. 產品硬需求，不從 framework 名詞倒推

本輪只使用已登記的效果約束：

1. 一名員工、一份 JD、一個可長期續談的 thread；不需要跨 JD 共用 Memory；
2. 員工與顧問的對話必須可續接；員工回答常依賴前一個 AI 問題，因此不能只保存員工半邊；
3. 長期 semantic Memory 必須可新增、修訂、刪除、列舉及按需取回；
4. 日常 run 不把全部 conversation 或 Memory 灌入 prompt；
5. 最終全面製作／檢查 JD 時，必須能處理該 JD 全部有效 semantic Memory；
6. compaction、summary 或 top-k retrieval 不得讓任何員工工作永久遺失；
7. 同一份逐字內容不應有兩個彼此可能漂移的 authority。

## 4. 直接官方事實

### 4.1 OpenAI

**Official fact O1 — conversation/session 是可持久的互動歷史。** OpenAI Agents SDK Sessions 會在每次 run 前取回 session history，run 後保存新的 user input、assistant response 與 tool items；OpenAI Conversations API 也會把 input／output items 加入同一 named conversation。官方並明確提醒：一個 conversation 應選一種 persistence strategy，混用 client session 與 server-managed continuation 可能造成 context 重複。
來源：[OpenAI Agents SDK — Running agents](https://openai.github.io/openai-agents-python/running_agents/) · [Sessions](https://openai.github.io/openai-agents-python/sessions/) · [Responses／Conversations API](https://developers.openai.com/api/docs/guides/conversation-state)

**Official fact O2 — 保存 history 與本輪送入模型可分開。** `session_input_callback` 可以在 model call 前裁切或重排歷史，但 SDK 仍只保存本輪新 items，不會把舊 history 重存成新 items。
來源：[OpenAI Agents SDK — Sessions：Control how history and new input merge](https://openai.github.io/openai-agents-python/sessions/#control-how-history-and-new-input-merge)

**Official fact O3 — Agent Memory 與 conversational Session 是不同層。** OpenAI Agents SDK 的 Agent Memory 文件直接寫明，它與保存 message history 的 Session memory 分離；Memory 是從 prior runs 萃取、供未來按需使用的檔案。Codex memory 也被描述為由合格歷史聊天背景產生的獨立 memory store，而不是 canonical conversation 本身。
來源：[OpenAI Agents SDK — Agent memory](https://openai.github.io/openai-agents-python/sandbox/memory/) · [Codex — Memories](https://learn.chatgpt.com/docs/customization/memories)

**Official fact O4 — compaction 是下一次模型 context，不是逐字 transcript。** Responses compaction 產生可供後續 continuation 的 opaque compacted items；官方要求將其視為不可解析的 continuation state。
來源：[OpenAI — Compaction](https://developers.openai.com/api/docs/guides/compaction)

### 4.2 Anthropic

**Official fact A1 — session history 與 persistent Memory 分離。** Claude Managed Agents Session 會跨互動保存 conversation history／transcript；Memory Store 則是可掛載、讀寫及版本化的另一個 resource。Managed Agents 仍屬 beta，但其責任邊界是官方直接公開的。
來源：[Anthropic — Start a session](https://platform.claude.com/docs/en/managed-agents/sessions) · [Session event stream](https://platform.claude.com/docs/en/managed-agents/events-and-streaming) · [Memory Stores](https://platform.claude.com/docs/en/api/http/beta/memory_stores)

**Official fact A2 — Memory Tool 是 client-side、按需讀寫的長期資料。** Claude 會提出 view／create／update／delete 等 memory file operation，由 application 實際執行及控制 storage；官方建議保持內容 coherent、up-to-date，避免不必要的新檔案。
來源：[Anthropic — Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)

**Official fact A3 — 標準 Messages API 不替 application 保存完整對話。** 若不用 Managed Agents，application 必須自己 round-trip history；Memory Tool storage 也由 application 控制。這表示「conversation owner」必須明確存在，但不表示應複製同一段 user text。
來源：[Anthropic — Messages API](https://platform.claude.com/docs/en/api/messages/create) · [API and data retention](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention)

### 4.3 Google Vertex AI

**Official fact G1 — Session events 是 Memory generation 的來源。** Memory Bank 可以從 Agent Engine Session 的指定時間範圍讀取 events 產生 memories；generated memory 是獨立 fact，後續可有 revision。
來源：[Google — Generate memories](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/generate-memories) · [Vertex Session／Memory RPC types](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/reference/rpc/google.cloud.aiplatform.v1)

**Official fact G2 — Memory 同時支援 bounded retrieval 與完整 listing。** `RetrieveMemories` 可做 similarity top-k，也可在相同 scope 下取回全部 memories；`ListMemories` 可列出 Memory Bank 全部項目。
來源：[Google — Fetch memories](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/fetch-memories)

### 4.4 AWS Bedrock AgentCore

**Official fact W1 — raw events 與 extracted long-term Memory 是兩層。** Short-term Memory 以 immutable、timestamped events 保存整段 conversation，包括 customer question 與 agent response；Long-term Memory 從 raw interactions 做 extraction／consolidation，產生 facts、knowledge、preferences 或 summaries。
來源：[AWS — Memory types](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-types.html) · [Memory terminology](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-terminology.html)

**Official fact W2 — application 若已有 raw history，可只提交衍生處理。** `IngestData` 適用於 application 已自行保存 raw interaction、只需要 long-term extraction 的情境；不用再把 raw event 存入 AgentCore。這是官方直接支持「不要無理由雙存同一來源」的例子。
來源：[AWS — Ingest content into long-term memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-ingest-data.html)

### 4.5 LangGraph／LangChain

**Official fact L1 — Checkpointer 是 thread-scoped graph state。** 它保存每個 graph step 的 state snapshot，支援 multi-turn conversation、interrupt／resume、HITL、fault tolerance 與 state history。
來源：[LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) · [LangChain — Short-term memory](https://docs.langchain.com/oss/python/langchain/short-term-memory)

**Official fact L2 — Store 是 application-defined item collection。** Store 以任意 tuple namespace 保存 key／JSON value，提供 put／get／delete／listing 及 optional semantic search；官方示例常用跨 thread user memory，但 namespace 「可以代表任何東西」，不必是 user，也不要求 Caliburn 必須跨 JD。
來源：[LangGraph — Persistence：Memory store](https://docs.langchain.com/oss/python/langgraph/persistence#memory-store) · [LangChain — Long-term memory](https://docs.langchain.com/oss/python/langchain/long-term-memory)

**Official fact L3 — model request 可以有非破壞性 view。** LangChain middleware 可用 `ModelRequest.override(messages=...)` 產生新的 model request，而不修改原 request。OpenAI Agents SDK 的 `session_input_callback` 也公開了同一效果：持久 history 與本輪 model input 可以不同。
來源：[LangChain — Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom) · [OpenAI Agents SDK — Sessions](https://openai.github.io/openai-agents-python/sessions/#control-how-history-and-new-input-merge)

**Official fact L4 — 內建 SummarizationMiddleware 會改 canonical agent state。** 已安裝的 LangChain `1.3.15` 實作在觸發摘要時回傳 `RemoveMessage(REMOVE_ALL_MESSAGES)`，再放入 summary 與 preserved messages。若把它接到保存完整 transcript 的 outer graph，它會刪除舊 message state；因此它不能同時被宣稱為逐字 conversation authority。
來源：[LangChain — Prebuilt middleware：Summarization](https://docs.langchain.com/oss/python/langchain/middleware/built-in#summarization) · 本 repo pinned source `apps/api/.venv/Lib/site-packages/langchain/agents/middleware/summarization.py`

**Official fact L5 — 長 thread 的 checkpoint storage 會成長。** LangGraph 預設在每個 super-step 寫入所有 state channel 的完整值；官方提供 beta `DeltaChannel` 降低 append-heavy channel 的儲存量，但有 storage／read-latency 取捨。
來源：[LangGraph — Persistence：Optimize checkpoint storage](https://docs.langchain.com/oss/python/langgraph/persistence#optimize-checkpoint-storage)

## 5. 跨家共同結論與不能誇大的地方

### 5.1 可稱為共同責任分層

| 共同做法 | 直接證據 | 對 `MEM-Q001` 的限制 |
|---|---|---|
| conversation／events 與 derived Memory 分離 | OpenAI Session＋Agent Memory、Anthropic Session＋Memory、Google SessionEvents＋Memory Bank、AWS events＋long-term records | semantic Memory 不能取代完整互動歷史 |
| persistent history 與本輪 model context 分離 | OpenAI session callback／compaction、Anthropic JIT memory／compaction、LangChain request middleware | bounded context 不應破壞 canonical history |
| semantic Memory 是可獨立讀寫的內容 | OpenAI／Anthropic memory files、Google／AWS records、LangGraph Store items | 適合 Store，不適合每步重存整個 collection 的 graph channel |
| 原始互動包含 user 與 assistant | OpenAI Sessions、Anthropic Sessions、Google SessionEvents、AWS raw conversation events | 只保存員工訊息會遺失「員工回答了 AI 哪個問題」的語意 |
| Memory formation 與 persistence 是不同責任 | Anthropic application 執行 tool、Google／AWS generation service、LangMem manager＋Store | manager 不能變成第二個 authority |

### 5.2 沒有形成共同事實的主張

以下不能說成「大廠都這樣做」：

- 所有 vendor 都用 checkpoint 或同一資料庫 schema；
- 每段員工原話都要再複製成 `employee-source` record；
- semantic Memory 一定要保存 quote、offset、Skill ID 或 immutable revision；
- compaction 能保證保存每個工作細節；
- top-k retrieval 能代替最終完整盤點；
- LangMem 或任何 managed Memory 自動保證產出完整、無重複的 JD。

這些若日後成為產品必要效果，必須標成 Caliburn mapping 或另做 bounded test，不能借 vendor 名義自行發明。

## 6. 現行 production 的實際形狀

本輪只做 read-only code audit，沒有修改 production：

1. `ConsultantThreadState.messages` 存在，但 `apply_verified_consultant_commit()` 只追加顧問 `AIMessage`；員工逐字輸入放在 Store `sources`；
2. 每個 product turn 都建立新的 inner consultant agent，`agent.ainvoke()` 只收到當輪 `HumanMessage`；inner agent 沒有接 Checkpointer／Store；
3. `ContextAssemblyMiddleware` 從 checkpoint semantic state 與 Store sources 組裝 prompt，orientation 只帶少量先前顧問回覆；
4. `SummarizationMiddleware` 只處理該次 inner run 的 model/tool steps，不是跨訪談回合的 conversation memory；
5. 結果是 employee history、assistant history 與 semantic state 分散在不同 owner，沒有一份 canonical 雙角色 conversation。

因此 `MEM-Q001` 不是重新命名：任何採納本文建議的施工都會改變 production authority 與 context assembly，必須走 successor ADR。

## 7. 三個實質方案

### 7.1 方案 A — Checkpointer conversation／run，Store semantic Memory（建議）

```text
Checkpointer: full employee↔consultant conversation + run/interrupt state
Store:       revisable semantic Memory collection
Model view:  bounded, non-destructive selection from both
```

優點：

- 直接符合 LangGraph short-term／long-term primitive；
- 對應 OpenAI、Anthropic、Google、AWS 的 conversation/events＋derived Memory 分層；
- 員工與 AI 對話同處一個 canonical thread，回答的上下文完整；
- 不需要第二份 employee-source 文字；
- Store 專注處理 item CRUD／list／search，最終可全量列舉 semantic Memory；
- 一份 JD 一個 thread 也能使用 Store；namespace 是產品隔離邊界，不必跨 thread 才能成立。

風險與控制：

- 完整 conversation 讓 checkpoint 儲存量隨長訪談成長；先只保存 product-level conversation，不把 inner tool chatter複製進同一 transcript，並以真 PostgreSQL 量測；
- outer canonical conversation 不可套會 `REMOVE_ALL_MESSAGES` 的 SummarizationMiddleware；本輪 model view 用 request override／等效非破壞性組裝；
- `DeltaChannel` 仍是 beta，不列第一版必要條件；只有量測證明儲存問題成立才評估；
- 這些控制是 LangGraph primitive 的 Caliburn mapping，不宣稱 vendor 提供完整產品 policy。

### 7.2 方案 B — Store 保存 conversation events＋semantic Memory，Checkpointer 只保存 bounded run state

```text
Checkpointer: bounded graph/run/interrupt state
Store:       conversation events namespace + semantic Memory namespace
```

優點：conversation event 可獨立 paging/query，checkpoint 不累積完整 transcript；形狀接近 AWS／Google managed event API。

缺點：

- LangGraph Store 不是官方 conversation/session primitive；必須自行定義 ordering、append、retry、resume 與 Checkpointer↔Store failure consistency；
- recent history 通常仍會進 checkpoint/model state，容易形成重複；
- 需要把 LangGraph 原生 conversation memory 移到自訂 event layer，第一版程式與錯誤面更大。

只有方案 A 的 PostgreSQL 長 thread contract test 證明 storage／retention 不可接受，或產品需要獨立 event query/export 時，才重開此方案。

### 7.3 方案 C — 維持現行「員工 source 在 Store、AI messages＋semantic state 在 Checkpointer」

優點：不改 production authority；現有 Evidence／correction code 可沿用。

缺點：

- 沒有一份完整雙角色 conversation；
- 每輪 inner agent 只看到當輪訊息與人工投影，並不是 framework-native multi-turn continuity；
- semantic collection 綁在 checkpoint state，缺少 Store item CRUD／search／完整 listing 的自然邊界；
- 同時不符合本輪產品能力與最新跨家責任分層。

此方案可繼續作為 production 現況，但不應成為 Memory 升級的目標方案。

### 7.4 比較

| 判準 | A Checkpointer conversation＋Store semantic | B Store events＋semantic | C 現行分角色 |
|---|---|---|---|
| 完整雙角色 conversation | 是 | 是，但需自建 event semantics | 否 |
| semantic CRUD／list／search | Store 原生 | Store 原生 | 不自然 |
| 同文重複 | 無 | 可能有 recent copy | employee/AI 分散 |
| LangGraph 原生程度 | 最高 | 中 | 中，但用途錯位 |
| 第一版複雜度 | 最低 | 最高 | 表面最低，產品缺口未解 |
| 長 thread storage 風險 | checkpoint growth，需量測 | 較低 | semantic checkpoint growth |
| 建議 | **採用** | 條件式 fallback | 不採為升級目標 |

## 8. 「不重複保存 source」的精確意思

若採方案 A：

1. 員工輸入一進 graph，就成為 canonical conversation 的 user message；
2. 顧問可見回覆成為 assistant message；
3. 兩者都由 runtime 產生 ID／順序／時間，模型不填；
4. semantic Memory 可以在需要時引用 message ID，但不再複製同一段全文；是否第一版需要此 reference，留給後續 provenance decision，不在 `MEM-Q001` 擅自增加；
5. 員工說「我剛才說錯了」只是新的 user message；舊訊息留在歷史，Memory formation 依新舊內容更新 current semantic Memory；
6. 不再建立只含 employee half 的第二份 `employee-source-events`／`sources` authority；
7. direct JD edit、approved JD、pending review 等 authority 不由本題順便決定，production 仍依 ADR 0060，直到 successor ADR 完整裁決。

避免雙存的直接收益：

- 不會發生 Checkpointer 已寫、Store source 未寫，或相反的 split-brain；
- 不需要維護兩套更正、刪除、retention 與 replay 規則；
- 員工回答保留它前面的 AI 問題，不再只有孤立句子；
- provenance 若需要只指向 canonical message，不需比對兩份文字是否仍一致。

## 9. Context 與 compaction 邊界

完整保存不等於每輪全部送進模型。建議資料流是：

```text
canonical conversation in Checkpointer
        ├─ recent／relevant conversation selection ─┐
semantic Memory in Store                           ├─> bounded model request
        └─ relevant search／explicit read ──────────┘

canonical conversation 與 Store 本身不因本輪裁切而改變
```

實作上可利用 LangChain middleware 的 `request.override(messages=...)`，或在呼叫 inner agent 前明確組裝 model input。不得把 outer conversation 直接交給目前的 SummarizationMiddleware，因為 pinned implementation 會刪除舊 `messages` state。Inner ephemeral agent 的 tool/model chatter仍可使用 summarization/context editing，因為它不是 canonical employee↔consultant transcript。

OpenAI 的 session input callback、server compaction與 Anthropic JIT Memory 都支持「持久資料完整、model view 有界」這個效果；但各家底層不同，所以本文只採責任分層，不宣稱 request override 是跨家唯一實作。

## 10. Owner 裁決後才可進行的最小驗證

若 Owner 採方案 A，先重寫已暫停的 isolated spike，只驗證框架契約，不碰 production：

1. 多輪後重啟 process，employee 與 assistant conversation 均能按原順序取回；
2. 員工回答「是，每週一次」時，仍能取回它所回答的 AI 問題；
3. model request 只含 bounded view，但 checkpoint 中完整 conversation 不變；
4. semantic Memory 可 add／update／delete／no-op，且不在 Store 複製 conversation text；
5. 員工更正後，原始 conversation 留存，current semantic Memory 更新；
6. 最終 audit path 可非語意地走完該 JD 全部 current semantic Memory；
7. 真 PostgreSQL 下量測每 50／200／500 turn 的 checkpoint 儲存量與讀取延遲；未超過預先核准門檻就不引入方案 B 或 beta `DeltaChannel`；
8. retry／crash 不產生重複 conversation item。

這些是候選的可證偽 contract，不是本文宣稱已驗證通過。

## 11. 建議裁決

建議 Product Owner 將 `MEM-Q001` 裁決為：

> **採方案 A。** 每份 JD 的 LangGraph Checkpointer 保存完整員工↔顧問 conversation 及 graph/run/interrupt state；PostgreSQL Store 保存該 JD 的可修訂 semantic Memory collection。Memory manager 只負責 extraction／consolidation 候選，不擁有 persistence。每輪 model context 由兩層資料非破壞性地有界組裝。第一版不建立重複 employee-source 文字 leaf；若要 provenance，只引用 canonical message ID。production 在 successor ADR 與實作完成前維持 ADR 0060。

若 Owner 不接受 checkpoint 長期保存完整 conversation，應明確選方案 B；不能回到現行分角色資料形狀後仍宣稱已完成 durable conversation。

## 12. Parking lot／reopen trigger

本題不處理：

- `MEM-Q002`：相似案例、stable understanding 與案例差異的 Memory admission／consolidation；
- semantic schema、prompt、tool schema；
- embedding／Qdrant／Reference RAG；
- JD workspace／review UI；
- production migration／舊 source table cleanup；
- checkpoint retention 的最終數值政策。

只有下列證據可重開方案 A：

1. 真 PostgreSQL contract test 顯示長 thread checkpoint storage／latency 超過 Owner 核准門檻；
2. LangGraph 官方 primitive 改變，無法保留完整 thread conversation 或非破壞性組裝 model view；
3. 產品加入獨立 conversation event query/export/retention，Checkpointer 無法滿足；
4. 新官方資料直接證明方案責任分層有誤；
5. Product Owner 改變一份 JD／一個 thread 的範圍。
