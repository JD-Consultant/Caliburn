# Conversation／Compaction 框架承接差異審核

> 日期：2026-09-05
>
> Topic：`LLM-Q014 / G4.3b-3` mechanism revalidation
>
> 狀態：**G3 Owner approved（只核准 A／B 隔離 mechanism comparison）；不選定框架、不授權 production 施工**
>
> **Q017 底層複核更正：**本稿原先把 Deep Agents 正常摘要誤寫成 state replacement，並漏列 LangMem 公開 short-term summary 元件。下文已更正；完整 source／小元件追蹤見[原文與摘要 primitives](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md)。原 Owner 核准的比較 scope 保留，不把事實更正當成新選型核准。
>
> **2026-09-06 §9.1–9.6 的研究沿革：**依已准「非破壞 Context／不另建原文副本」比較兩條既有候選，原提出優先 LangMem 公開 short-term 函式；該優先建議已因 §9.7 新證據要求重審。**未選定引擎、未執行比較**；§6 的先測 A 亦是先前建議，不當成已採用 A。
> **最新增補見 §9.7 的接線子稿 §5：**Owner 優先可組合的公開框架元件；先釐清摘要時點、Context 與元件接法，不要求先在兩套套件間二選一。`CC-F13` 工具配對與 §9.6 保存／retry 證據仍有效，**尚未選型**，不能只讀舊推薦就施工。

## 0. Preflight

```text
Topic ID:
  LLM-Q014 / G4.3b-3
Current stage:
  已核准產品效果與 authority 邊界；本稿只用新完成的 framework 事實圖重驗 mechanism。
Binding decisions:
  完整 conversation 與 bounded model context 分離；模型／Provider 可替換；
  Compaction 不得冒充 Semantic Memory 或精確原話來源。
This turn's only blocking question:
  現成 framework 元件是否已能取代既有「薄、非破壞性 continuation middleware」候選？
Already reviewed evidence:
  既有 OpenAI 系統圖與 progressive-disclosure 深入查證；
  LangGraph／LangChain／Deep Agents／LangMem 官方流程事實圖。
Out of scope / parking lot:
  Semantic Memory extraction／consolidation、Memory 導覽與搜尋、JD Tools、UI、
  exact token threshold、production schema、migration、部署及框架總選型。
```

## 1. 本稿不重做 OpenAI 研究

OpenAI 基準已由下列兩份既有文件完成，本稿直接引用，不重新依記憶改寫：

1. [`2026-09-05-openai-conversation-context-and-memory-system-map.md`](2026-09-05-openai-conversation-context-and-memory-system-map.md)
2. [`2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md`](2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md)

框架端事實以
[`2026-09-05-langchain-langgraph-deepagents-langmem-official-memory-flow-map.md`](2026-09-05-langchain-langgraph-deepagents-langmem-official-memory-flow-map.md)
為入口。只有該文件沒有回答，或研究日官方文件已有變化時，本稿才回查官方來源。

## 2. OpenAI 基準責任

既有研究已確認：

```text
Conversation／Session
  └─ 保存實際 message、Tool call、Tool result，負責同一對話延續

Compaction
  └─ 到 context 壓力時產生較小的後續工作視圖

Canonical conversation／raw record
  └─ 需要精確內容時仍可回查；不因 Compaction 消失

Semantic Memory
  └─ 另一條 extraction／consolidation 流程，不是 Conversation 或 Compaction
```

OpenAI Responses 的 compaction item 是 opaque continuation；standalone compact 回傳的是
下一個 canonical **context window**，不是完整逐字 transcript，也不是 Semantic Memory。
Conversation object 則有 durable ID，可保存 messages、Tool calls 與 Tool outputs。即使使用
`previous_response_id`，先前 input tokens 仍會計費，因此 continuity 與成本壓縮也是兩項責任。

直接來源：[OpenAI Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)、
[OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction)。

## 3. Framework 真正提供什麼

### 3.1 LangGraph Checkpointer

**Official fact：**Checkpointer 以 `thread_id` 保存 graph-state checkpoints，官方用途包括
conversation continuity、interrupt／resume、time travel 與 fault tolerance。它不會自行決定
如何縮短模型 Context，也不會自動建立完整對話之外的 compaction artifact。

若 state 的 `messages` 被 middleware 永久摘要／刪除，Checkpointer 會保存新的 state；不能只因
仍有 checkpoint history，就宣稱目前 state 永遠是一份可直接使用的完整逐字 conversation archive。

來源：[LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、
[LangGraph Memory](https://docs.langchain.com/oss/python/langgraph/add-memory)。

### 3.2 LangChain `SummarizationMiddleware`

**Official fact：**它在 token／message／context-fraction 門檻達成時另呼叫模型摘要舊 messages，
將 summary **永久寫回 state 並取代舊 messages**，保留指定數量的近期 messages。這是成熟的
provider-neutral working-context 壓縮元件。

**Gap：**最新 state 不再含完整舊訊息，但這**不等於資料庫歷史被刪除**。普通 PostgresSaver 保留舊 checkpoints，可透過 history／指定 checkpoint 取回；單獨此 middleware 沒有另外建立完整 transcript reader／archive。是否可由現有 history 承接精確回查，須審讀取與保留契約，不能直接推論原文遺失或必須另建副本。固定 reducer／Saver 來源見[底層追蹤 §1–3.1](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#1-必須分清三種替換)。

來源：[LangChain Context Engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)、
[LangChain Summarization Middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in#summarization)。

### 3.3 OpenAI provider-native compaction through `ChatOpenAI`

**Official fact：**`ChatOpenAI` 可透過 Responses API 的 `context_management` 啟用 server-side
compaction。回傳的 compaction blocks 必須保留於後續歷史；最近 compaction item 之前的
messages 可保留，也可為 latency 丟棄。

**Gap：**這是 OpenAI provider capability，不是跨 Provider 的 LangChain contract。opaque block
不能成為模型切換後唯一的恢復資料。它最適合作為 OpenAI adapter 的最佳化，而不是可替換模型產品
的唯一 continuation substrate。

來源：[LangChain ChatOpenAI — Context management](https://docs.langchain.com/oss/python/integrations/chat/openai#context-management)、
[OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction)。

### 3.4 Deep Agents `SummarizationMiddleware`

**固定 source 複核：**正常路徑將 summary＋recent 送入 `request.override`，另以 Command 保存摘要事件；**不以 RemoveMessage 清掉 state.messages**。同時將被摘要段落的文字 rendering 寫到 backend，預設使用內部 session ID 的 `/conversation_history/session_<uuid>.md`，不是 thread_id。所核對 commit 與原研究相同；是原解讀需更正，不以版本升級帶過。

它另提供 tool payload offloading、token trigger、recent-message keep、overflow 後摘要重試，
是目前候選中最接近「provider-neutral summary＋原始內容保存」的官方現成元件；但
`deepagents` 套件目前仍標示 Beta，不能把「功能較完整」寫成「成熟度已等同 LangChain／
LangGraph stable」。

**重要邊界：**

- 完整採用 `create_deep_agent` 會連同 filesystem、subagent、patch-tool-call、prompt-cache 等
  harness 責任一起帶入；是否需要整套是下一個 Harness 題，不能為了 Compaction 偷決定。
- `deepagents.middleware.summarization.SummarizationMiddleware` 是公開的標準 `AgentMiddleware`
  元件；LangChain `create_agent` 能組裝 `AgentMiddleware`。但官方主要使用範例仍放在
  `create_deep_agent`，所以「抽出該 middleware 接到目前 plain `create_agent`」是合理的
  framework composition，**不是官方逐字推薦 recipe**，仍需以確切版本做小型 compatibility test。
- **撤回原「必須把原文 authority 搬到 backend」推論。**正常摘要保留 state 訊息；但 overflow 支線可能回寫縮短的 ToolMessage，history rendering 也可能含截短工具參數／媒體路徑。archive 寫入失敗仍可能繼續摘要，不能保證是無損 canonical 備份。逐路徑證據見[底層追蹤 §3.2](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#32-deep-agents-summarizationmiddleware修正前輪誤讀)。

來源：[Deep Agents Context Engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering#context-compression)、
[Deep Agents SummarizationMiddleware reference](https://reference.langchain.com/python/deepagents/middleware/summarization/SummarizationMiddleware)、
[Deep Agents source](https://github.com/langchain-ai/deepagents/blob/main/libs/deepagents/deepagents/middleware/summarization.py)、
[LangChain Middleware](https://docs.langchain.com/oss/python/langchain/middleware/overview)。

## 4. 差異矩陣

| 候選 | Conversation continuity | 有界 Context | 完整舊內容可回查 | Provider 可替換 | 現成程度 | 主要代價 |
|---|---:|---:|---:|---:|---:|---|
| OpenAI native compaction | 是 | 是 | 需另留 Conversation | 否 | 高 | opaque、provider-specific |
| LangChain SummarizationMiddleware | 是 | 是 | 需 history reader；最新 state 不完整 | 是 | 高 | current state replacement，不等於刪除 DB history |
| 完整 Deep Agents harness | 是 | 是 | 正常摘要保留 state；另有 history rendering | 是 | 高 | 額外 harness 與 tool eviction 邊界 |
| Deep Agents summarization component＋plain agent | 是 | 是 | 同上，非無損 archive 保證 | 是 | 中高 | 組合及例外路徑待核對，不預設 authority 必須改 |
| 薄 transient view＋公開 summary primitive 候選 | 是 | 是 | 可維持 Checkpointer messages | 是 | 中 | 可重用 LangMem summary 函式；接線與錯誤仍待設計 |

LangMem `summarize_messages`／`SummarizationNode` 的公開能力與 output key 行為見[底層追蹤 §3.3](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#33-langmem-的小型公開元件原事實圖漏列)。這是補足可重用元件，不是新增選型裁決或已完成相容性測試。

## 5. 本輪 finding

### `CC-F01`：現成框架已覆蓋大部分效果，但沒有零決策替換

Deep Agents 已有官方現成的「摘要＋原始 conversation offload」元件；因此不能再說所有
provider-neutral canonical preservation 都必須由 Caliburn 從零實作。

**Q017 更正：**原先由此推論 canonical data placement 必須改變，已被同一固定 source 的 request-view／event 機制推翻。先核對正常摘要與 tool eviction 的實際保存範圍，再判斷要怎麼接原文 reader；不能以錯誤依據要求 Owner 搬移 authority。新 findings `CC-F04–07` 與公開接點集中在[底層追蹤](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md)。

### `CC-F02`：一般 LangChain summary 不足以單獨達標

它處理「縮小目前 working state」。沒有接原文 reader 時，模型只會看到最新摘要；但普通 Saver 的歷史 snapshots 可能仍有原文。這是存取／保留設計尚未完成，不把「模型看不到」等同「DB 已刪光」。

### `CC-F03`：Provider-native compaction 應是 capability，不是共同基線

它最接近 OpenAI 自己的 continuation engine；但 Caliburn 要可換模型，因此只能作有支援時的
adapter optimization。若日後啟用，仍須保留可由其他模型重建的 conversation 資料。

## 6. 建議與 Owner 裁決

既有 G4.3b-3 的**產品效果**不需要重開；新 framework 事實只要求重驗 mechanism：

1. 不採一般 LangChain `SummarizationMiddleware` 單獨作完整方案；
2. 不採 OpenAI native compaction 作唯一共同基線；
3. 在下一個 isolated mechanism spike 只比較：
   - **A：**公開的 Deep Agents summarization component＋backend preservation；
   - **B：**既有薄 transient context-view 候選。

推薦先驗證 **A**，因為它重用的官方現成元件最多；但 Deep Agents 仍是 Beta，只有同時
證明以下三點才可取代 B：

- 能與 plain LangChain `create_agent`、選定 Checkpointer／Store backend 及確切套件 pin 正確組合；
- 原始員工 conversation 可完整、按 scope 隔離且可精確回讀，不只留下摘要；
- 不必為此引入 Caliburn 不需要的 subagent、shell／execute 或整套 Deep Agents harness。

若任一點不成立，回到 B；先核對 LangMem 公開 summary primitive 等較小元件能否重用，不預設 B 的摘要引擎須自行發明，也不是重新發明整套 Memory 或 agent loop。

**Owner 裁決（2026-09-05）：**核准把 G4.3b-3 的下一個 mechanism gate 改為上述 A／B
最小比較，而不是直接按舊設計施工。這項核准只允許隔離比較；它不等於採用 Deep Agents、
不等於採用 A，也不允許修改 production。比較完成後仍須依 pass／stop 證據另行裁決 mechanism。

## 7. 原輪 Closure（Harness 已由 Q015／Q017 接續）

```text
Decision / finding:
  OpenAI 既有研究不需重做。Deep Agents 已原生提供 provider-neutral summary＋原始
  conversation backend preservation；一般 LangChain summary 與 OpenAI native compaction
  各只覆蓋部分責任。是否由 Deep Agents component 取代薄 transient middleware，需一個
  只驗證 composition／完整回讀／額外 harness 負擔的最小 mechanism gate。
Status:
  G3 Owner approved：只核准 A／B 最小隔離 mechanism comparison；框架與 production 均未裁決。
Why:
  新框架事實沒有推翻產品效果，但新增一個可能減少自訂機制的成熟候選，足以重驗 mechanism。
Sources:
  本稿 §1、§3 的既有研究與官方連結。
Affected artifacts:
  本稿；不改 production、ADR 或既有 Working Decision。
Reopen trigger:
  Deep Agents／LangChain middleware contract 或確切 pin 改變；Owner 改變模型可替換或完整
  conversation 回查要求；最小 compatibility test 提供新證據。
Next gate:
  先完成 Harness 責任 G2：比較完整 Deep Agents harness 與 plain LangChain create_agent
  ＋必要公開元件；A／B spike 須待 Harness 邊界收斂後另寫可驗證設計，仍不得接 production。
```

## 8. Q017：對話資料的框架存取對照

**2026-09-05，框架契約核對；不新增選型裁決。** Owner 已澄清：OpenAI 的用途／分層以既有研究為準，本段只把它們對到框架資料、API 與剩餘接線，不重做名詞研究。§6 只核准過兩候選的比較範圍，並未選定 Compaction 路線；最新狀態見 [Q017 register](../current-decisions.md#4-llmagent-working-baseline)。

| 已研究責任 | 框架資料／元件與寫入 | 取回方式與邊界 |
|---|---|---|
| 目前 conversation 的訊息 | `create_agent` 的 `AgentState.messages`；新訊息隨 `invoke/ainvoke` 輸入，model／tool loop 將實際回覆與工具結果更新進 state | invocation 結果或 `get_state/aget_state(config).values["messages"]`；是當時保存的 messages，不保證被永久摘要前的原文仍在 |
| 跨 invocation 接續 Session 的責任 | 在每次 config 提供同一 `thread_id`；不必為名稱對齊再建 SDK Session 副本 | 以同 thread 讀取或續跑；`thread_id` 不是一次 run 或一個 checkpoint ID |
| 跨 process 保存與恢復 | `create_agent(checkpointer=...)` 接 `PostgresSaver`／`AsyncPostgresSaver`；框架保存 state checkpoints，初始化使用官方 saver setup | 透過 graph 公開 state API；不是手寫 SQL 存取 framework 內部表，也不是 LLM 決定是否保存對話 |
| 指定過去的執行狀態 | Checkpointer 的歷史 snapshots | `get_state` 加 `checkpoint_id` 或 `get_state_history`（及 async 版本）；history 是 snapshots，不能把全部 snapshot 的 messages 串接成 transcript，以免重複 |
| A／B 所需的原始互動片段 | 依具體更新路徑，從目前 messages、指定歷史 checkpoint 或已保存的 backend 內容讀；Deep Agents 正常摘要不要求只能從 backend 取原文 | scoped reader／filesystem read-search 可共用官方 primitives，但須分清完整 message、文字 rendering 與 tool eviction 指標；Store semantic search 不會自動查 Checkpointer |
| 只送模型需要的上下文 | LangChain `wrap_model_call` 的 `request.override(messages=...)` 是 transient 接法；摘要生成／保存另依選定 compaction 元件 | 本次 model request 使用該 view；單純 override 不改原 state，也不等於已實作整個 Compaction |

直接來源：[LangChain short-term memory](https://docs.langchain.com/oss/python/langchain/short-term-memory)（`AgentState.messages`、invoke 與 database saver）、[LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers#get-state)（state／history API）、[Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering#transient-context)（transient view）；raw archive 的官方能力與限制沿用本稿 §3.4，不在此重新假設為無損 provider-payload 備份。

**對照結論：** messages、thread、耐久 saver、state reader 已有官方元件；raw rollout 的「可回查互動」不要求照抄 JSONL 檔名，但完整舊內容到底由哪個 reader 回傳，不能在 Compaction 路線尚未裁決時宣稱已全部確定。按片段定位、B 本次取哪些資料及對模型暴露什麼 reader，是需組合的契約，不是 Checkpointer 自帶的全文／語意搜尋功能。

**Reader 核對已補齊，選型未決：**[底層追蹤 §6](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#6-接續核對同源原文如何供-b-抽取與-a-深查)已確認 graph state/history、ToolRuntime、訊息 serialization／filter 及 backend 接點；StateBackend 的 files 不自動等於 messages。直接 reader Tool／唯讀檔案投影是待審組合，不是新增原文副本，也不是已選 Compaction。接續依 Q017 §3.6 對照抽取中間產物的保存／引用，讓 reader 接力一併收斂；Memory／guide 及 Q018 按原順序。沒有重選 Harness、重做 OpenAI 研究、執行 spike 或更改 production。

## 9. 非破壞性延續：兩條既有候選的接線取捨

**2026-09-06／Q017 G4，接法建議待審，不施工。** Owner 同意五 artifact／單一導覽／按需停止的澄清後，回到原定 Context 題。本節只回答「壓縮給模型的對話，如何不破壞 A 回查及 B1 抽取的原文」。不重開 Memory 分層，不決定 B 觸發、Q018 或新增對話庫。

### 9.1 官方證據沒有要求另存一份原文

**Owner 同輪補充：不能由「函式回傳延續摘要＋近期訊息」推論對話沒有保存；底層可能已自動保存。** 本稿採此閱讀紀律，接續 §1／§8 及原文 primitives 的既有研究，不將此題當成剛發現的新需求。判斷必須追到 caller → state update → reducer → Saver。

| 資料／接點 | LangMem 官方例子的實際行為 |
|---|---|
| 完整對話 `state.messages` | Graph 輸入及模型回覆更新此欄位，由 Checkpointer 保存；摘要函式的回傳不會自行取代它 |
| 摘要函式回傳的 `result.messages` | 呼叫者送給模型的視圖；不是資料庫的寫入清單 |
| `result.running_summary` | 呼叫者另作 state update，由同一 Checkpointer 保存；跨 process 重開需配置耐久 Saver，不能把範例的 InMemorySaver 當磁碟保存 |

官方例子在 model call 後回傳的是新回覆及 summary 欄位，**不是將整份 `result.messages` 覆寫原文**。若換成其他 caller／middleware，必須重查其回傳，不能推廣成所有接法都自動保留完整原文。下文「不額外存原文」只指不另建 transcript 庫／backend 歷史檔，**不是不存對話，也不是保證 checkpoint 物理上沒有多版本資料**。[官方 caller 範例](https://langchain-ai.github.io/langmem/guides/summarization/)、[既有 graph／reducer／Saver 追蹤 §1–3](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md)

- **LangChain 公開接點：**`request.override(messages=...)` 可只改當次模型輸入；額外持久狀態則由 lifecycle hook 或 `ExtendedModelResponse`／`Command` 回傳。兩者可分開，不必將縮短後列表寫回 canonical `messages`。[Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering#transient-context)、[State updates](https://docs.langchain.com/oss/python/langchain/middleware/custom#state-updates)
- **LangMem 官方 recipe：**保留完整 messages，另保存 `RunningSummary`；再次使用時帶回摘要與已處理訊息位置，避免每輪重做同一段摘要。`summarize_messages`／async 版本提供縮短後輸入，不自行存 Store 或刪對話。這是可重用的小元件，**不是重新選 LangMem manager 作整套 Memory pipeline**。[官方完整例子](https://langchain-ai.github.io/langmem/guides/summarization/)、[函式／RunningSummary API](https://langchain-ai.github.io/langmem/reference/short_term/)
- **Deep Agents 現成元件：**除模型延續摘要，還有 backend 歷史文字保存與 overflow 復原。既有固定 source 已證明正常摘要仍留 state messages；歷史檔是另行 rendering，不能直接當無損原文 authority。這不是說多一份衍生 rendering 本身錯誤，而是本案已有同源原文 reader，是否再要此產物必須有用途。[官方 context compression](https://docs.langchain.com/oss/python/deepagents/context-engineering#summarization)、[既有完整 source trace §3.2](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#32-deep-agents-summarizationmiddleware修正前輪誤讀)

### 9.2 比較與本輪推薦

> 本節保留原輪推薦及理由；**目前優先序須依 §9.7 新 finding 重審**，不單獨作選型入口。

| 既有候選 | 能承接什麼 | 仍須處理／取捨 |
|---|---|---|
| **LangMem short-term 函式＋LangChain model middleware（本輪建議優先）** | 既有摘要＋新增尾段的增量延續；原始 messages 不改；不額外寫對話歷史檔 | 接摘要狀態保存、完整 request 預算、錯誤與 async；不是已內建的完整 create_agent 配置 |
| Deep Agents 獨立 summarization middleware | 現成 trigger／keep、延續事件、歷史 rendering、overflow 處理 | 額外 backend rendering／reader 及工具 eviction 路徑；未找到本輪可證明的公開「僅關 archive」配置，不能靠 no-op backend 假裝保存成功 |

**推薦理由屬本案映射，不是品質排行榜：**第一條更直接符合已准「Checkpointer 原文同源、縮的是模型 Context」，並重用官方摘要函式，不複製 private helper。第二條功能較整合；若後續確需其檔案式歷史入口／overflow 能力，且願意明確配置額外衍生產物，它可能更合適。未比較摘要品質／成本實測，不能宣稱 LangMem 效果一定較好，亦不因文件範例模型較舊就直接判定 API 過時。部署時另鎖相容版本，不照抄範例模型或舊 agent factory。**兩條都可能由 Checkpointer 保存原對話；差別不是「一家存、另一家不存」。** 此優先建議另受 §9.6 的「最新員工訊息／工具配對及完整 request budget」門檻約束；不能只因少一份 history rendering 就宣布勝出。

此建議細化 §6 的兩條既有候選，**不把 Owner 的「同意繼續」寫成引擎已核准**。一般 LangChain 的 state-replacing summary 與 provider-specific opaque compaction 的限制仍見 §3，不再展開第三輪廣泛選型。

### 9.3 若採第一條，資料如何走

```text
Checkpointer 恢復完整訪談 messages＋上次 RunningSummary
  → 官方摘要函式：未達門檻則重用；達門檻才生成／更新延續摘要
  → 得到「摘要＋尚未摘要的尾段」模型視圖（不能由此保證本輪員工原句必在尾段，見 §9.6）
  → model middleware 組入規則、既定導覽／相關召回、當次工具等 Context
  → 主顧問回答或使用工具
  → graph 保存真實新增訊息及成功產生的摘要狀態；不以視圖覆寫原文

B1 抽取／A 原文回查 → 既有 canonical graph reader，不讀上述摘要冒充原文
```

這是公開元件組合的**設計建議**，不是官方逐字提供的完整 pipeline。以下邊界不能在接線時省略：

1. **摘要位置不由 LLM 填。**框架 `RunningSummary` 管理已處理訊息 IDs；模型負責摘要文字。將新 summary／位置作 state update 保存，不能只留 process 變數；也不可只前移位置卻沒保存對應摘要。
2. **當輪員工訊息只出現一次是接線要求，不是函式無條件保證。**§9.6 已發現 cutoff 可走到最後一則；必須核對實際 model view，不能一面聲稱它必在近期 messages，一面未審分段。guide／自動召回不是員工原話，不反覆追加到 canonical 對話再拿去摘要。導覽由 B 維護，此步是讀取，不另叫模型重建；精確刷新時機留 Context 組裝題。
3. **計算的是完整 request 預算。**對話可用空間要容納規則、導覽、召回、工具 schema 與輸出預留；單看 messages 的 token 不能保證整次 request 不超限。不在本輪硬定 85%、固定輪數或跨模型通用數字。
4. **保留工具呼叫／結果配對。**使用官方分段能力；測試需涵蓋多工具與較長 Tool result，不手切最後 N 則而拆散配對。FilesystemMiddleware 另有 offload 副作用，改選摘要函式不等於其它 middleware 都已核對完成。[既有 filesystem 邊界](2026-09-05-memory-artifact-native-backend-design-review.md#33-搜尋與-context-副作用不能略過)

### 9.4 成本、限制與必須避免的誤解

**新增 API 核對：**LangMem 的 `max_summary_tokens` 是預算估算，並不自行限制摘要模型輸出；要以所選模型支援的輸出設定配合。它也明示：待摘要內容若大於摘要輸入上限，可只摘要其最後一部分。因此**縮短後輸入不等於已完整閱讀全部原文，更不是完整 Memory 盤點**。這些不能靠「用了框架」就忽略。[參數原始說明](https://langchain-ai.github.io/langmem/reference/short_term/#langmem.short_term.summarize_messages)、[固定函式 source](https://raw.githubusercontent.com/langchain-ai/langmem/f8c7ebd6110c124a36995dab645a8cb0eb0b8210/src/langmem/short_term/summarization.py)

- **正常成本：**未到門檻只重用／組裝，不新增摘要模型呼叫；觸發時才付摘要 request，主顧問仍需自己的 request。重試可能增加次數，沒有「每輪固定多一次」或「永遠只需一次」保證。
- **細節保存：**摘要可有損；原文及既有 Memory／詳記回查責任不變。B1 不以延續摘要代替已定原文範圍；不能用摘要成功宣稱所有工作細節已抽取。
- **失敗：**摘要失敗不移動成功摘要位置、不刪原文；沿既有有界 retry。若仍無法形成可送出的 Context，回報本輪未完成，不能假裝壓縮成功或無限加大模型預算。具體 hook 保存時點與 failure replay 在接線驗證中核對，未另建恢復狀態機。
- **儲存：**縮小 prompt 不會縮小 Checkpointer 的完整 messages。長 thread 的儲存／載入成本仍須審；官方 `DeltaChannel` 是有版本／beta 條件的優化，不在此直接啟用，更不以清除有引用的 checkpoints 換空間。[官方儲存優化](https://docs.langchain.com/oss/python/langgraph/checkpointers#optimize-checkpoint-storage)

### 9.5 Closure 與停止線

- **Status／Finding：**非破壞性延續已有官方小元件；本輪提出優先 LangMem short-term＋公開 middleware 的建議，待 Owner 審閱；原 A/B 隔離比較的 scope 核准不等於比較已執行。`CC-F08` 記錄「額外 archive 不應被漏報」，`CC-F09` 記錄「摘要預算／原文完整性不可混稱」，均非產品功能已通過。Owner 補充後於 §9.1 明列「函式輸出≠持久化結果」；不因本輪追問重新研究已證實的原文保存責任。
- **閱讀／來源：**完整回讀 register、decision-process、本文、原文 primitives、主流程；定向回讀全流程提案 §3–4 及 backend §1–3.3。新查官方 LangMem guide/API、LangChain context/custom middleware、Deep Agents context compression、LangGraph checkpointers；成功重取 LangMem 固定 source。Deep Agents 固定 source／reference 直取失敗，內部細節沿用已記錄研究，不宣稱本輪驗證了最新 HEAD 或確切安裝組合。
- **Affected／Reopen：**本文持有接法與證據；主流程及 register 只指路。若公開元件新增不需 archive 的等價配置、相容性／效果證據推翻推薦，或 Owner 更改原文保留邊界，再重開。
- **Next：**Owner 審閱此取捨後，收斂 Context 組裝（最新導覽、既定少量召回與額外工具內容的預算），再 B 生命週期及 Q018；不重問五 artifact。未做模型／框架測試，不安裝、不改 production、不寫實作計畫；實作前仍需摘要前後原文回讀、重開後增量延續與工具配對的最小檢查。

### 9.6 接續查證：成功保存時點、恢復與接線門檻

**2026-09-06／Q017 G4，研究結果與接法建議，未核准施工。** 本輪只補 §9.4 未決的 caller／failure 路徑；不重新研究 OpenAI 或選 Memory 分層。以下限定所列框架與來源，**不是宣稱 OpenAI／Anthropic 使用相同內部 hook**。

#### 已核對的官方行為

1. **同一 node 內摘要再問主模型，不等於摘要已先保存。** LangMem simple-chatbot recipe 在主模型成功回傳後，才回傳新訊息＋`RunningSummary`。若主模型拋錯且沒有被外層處理，這個 node 尚未交回新 summary；重新執行它可能再次付出摘要呼叫。這是依官方程式順序的推導，不是實測故障結果。同頁另有獨立 `SummarizationNode → call_model` recipe，提供不同的保存邊界。[官方兩種 caller](https://langchain-ai.github.io/langmem/guides/summarization/)
2. **Graph 保存已交回的 state，不保存任意函式區域變數。** LangGraph 在 super-step 邊界 checkpoint，也保存成功 node 的 pending writes；失敗恢復能重用已保存的結果。`sync` 在下一步前完成寫入，`async` 與下一步並行而有 crash window，`exit` 只於退出保存。故「摘要步驟已返回」與「程序現在崩潰仍能恢復」還須連同 durability 配置判斷，不能給 exactly-once 保證。[Checkpointer 邊界](https://docs.langchain.com/oss/python/langgraph/checkpointers#super-steps)、[durability](https://docs.langchain.com/oss/python/langgraph/checkpointers#durability-modes)
3. **公開接點能分開 state 與模型視圖。** LangChain node-style `before_model` 可回傳 state update；`wrap_model_call` 可只改 request。若選擇在 wrap 內回傳 `ExtendedModelResponse`，更新隨回覆交回；多層 Command 由框架組合，retry 未採用的呼叫結果不應自行先寫入另一個庫。[State updates／composition](https://docs.langchain.com/oss/python/langchain/middleware/custom#state-updates)
4. **LangMem 並未自帶整套 retry／最近一輪保留政策。** 固定 source 的 sync／async 方法先等待摘要模型成功，再建立新 `RunningSummary`；函式未自行 catch／重試該錯誤。分段掃描可以一直到最後一則；例如門檻直到最新 HumanMessage 才達到，該訊息也可能被納入摘要。公開參數沒有獨立 `keep` 保證。因此「返回 summary＋tail」不能推成「本輪原句一定仍在」。這是 source 可達分支，不是已觀察到的產品 bug。[分段及函式完整 source](https://raw.githubusercontent.com/langchain-ai/langmem/f8c7ebd6110c124a36995dab645a8cb0eb0b8210/src/langmem/short_term/summarization.py)

#### 若繼續第一候選，優先研究的接法

**[本案組合建議，尚非選型裁決]** 優先對照官方「先獨立摘要、再主模型」recipe，以 `create_agent` 公開 node-style hook 承接摘要 state update，model hook 承接視圖，不另造恢復狀態機或第二個 agent loop。官方 `SummarizationNode` 可提供摘要及輸出視圖；接到 `create_agent` 的 schema／hook 是需要驗證的組合，**不是把 node 名稱直接塞進 middleware 清單就完成**。

| 接法 | 正常成本／狀態 | 主模型失敗後的差異 |
|---|---|---|
| 同一步摘要＋主模型，最後一起交回 | 接線少，沒有獨立摘要保存邊界 | 本步尚未交回的摘要可能需重做 |
| 摘要結果先經 framework step 保存，再主模型 | 多一個 graph 保存邊界；不是因此多一個摘要模型呼叫 | 可重用已保存摘要，仍受 durability／選定恢復位置限制 |

這個比較只談 **LangMem 官方兩種接線及其 `create_agent` 組合**；不據此猜 Deep Agents 的全部 failure branch。若保存輸出視圖，該欄位是可替換的衍生 Context，不能加到 canonical `messages` 或當成另一份訪談來源。若只保存 `RunningSummary`，如何以公開 API 重建本次 view 也要明寫，不能使用跨 thread 共用的 middleware instance 變數藏摘要，或依賴 private helpers。

**重試使用官方元件，但需放對位置。** 摘要模型可用公開 Runnable `with_retry`（限制暫時錯誤與嘗試次數）；官方建議縮小 retry 範圍，不為主模型暫時失敗而重跑整段工作。主 Agent 的 `ModelRetryMiddleware` 不會自動包住更早 `before_model` 內另一個摘要模型呼叫。兩層 retry 與 provider SDK 內建 retry 須一併計算，不能無限疊乘。[RunnableRetry](https://reference.langchain.com/python/langchain-core/runnables/retry)、[with_retry](https://reference.langchain.com/python/langchain-core/runnables/base/Runnable/with_retry)、[Model retry](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-retry)

**失敗語意：**保留已保存原文與上次有效摘要；摘要錯誤不能假裝已完成壓縮。若重試後仍無有效可送出的 view，按既定 Q005 回報本輪未完成，不把 SDK 錯誤當訪談知識交給 B。官方 ModelRetry 可在用盡後回傳錯誤 AIMessage 或拋錯，故不能只看「得到 AIMessage／graph 結束」判定顧問分析成功；具體 outcome 接線留原題，不新增一套產品狀態。

#### 本輪 findings 與停止線

| ID／等級 | 缺口與影響 | 狀態／要求 |
|---|---|---|
| `CC-F10`／P2 | §9.3 未指定保存邊界，容易把摘要成功誤當已 checkpoint，低估重跑成本 | 已列官方兩種接法；建議分步保存，待組合確認，不保證零重算 |
| `CC-F11`／P2 | §9.4「沿既有 retry」容易被寫成只接主模型 retry，摘要呼叫實際未覆蓋 | 已指出 retry scope／SDK 疊加／錯誤 AIMessage 邊界；不手寫通用重試系統 |
| `CC-F12`／P1 | §9.3 曾直接說本輪訊息已在近期段；LangMem cutoff 沒有此無條件保證，可能降低當輪回答精確性 | 更正文義；成為 Context 接線與兩候選比較門檻，尚未解決／未選引擎 |

**Closure：**完整回讀 register／流程／本稿／主流程，定向回讀原文 primitives §1–6.3；重新取得 LangMem guide、固定 short-term source（含 sync／async／node）、LangChain custom／prebuilt middleware 與 LangGraph checkpoint docs。RunnableRetry reference 直取失敗，官方索引結果可讀；LangChain factory／Deep Agents 固定 source 本輪直取失敗，舊 trace 保留但不宣稱新核驗。**不以版本或未成功取得的 source 補猜**。本輪未安裝、執行模型或框架測試。

**Next：**先收斂 A 的「本輪原句＋成對工具訊息＋完整 request budget」以及兩候選對此的公開接法；必要時只做已核准範圍內的最小機制檢查，不先跑新付費實驗。未釐清前不將 LangMem 優先建議升成已選方案；之後仍是 B 生命週期與 Q018。實作／ADR gate 不變。

### 9.7 最新接續：近期保留、工具配對與完整預算

細節分至[Context 接線審閱](2026-09-06-context-window-retention-and-budget-wiring-review.md)，避免本文再堆疊完整 API 研究。`CC-F13` 發現 LangMem 固定 source 可能切開多工具結果；`CC-F14` 補上新版官方含工具 schema 的 token counter。**因此 §9.2 的 LangMem 優先推薦需重審，不再作目前推薦排序。**前輪 Deep Agents 獨立元件優先建議亦非定案；最新 Owner 偏好見子稿 §5：優先公開元件組合，先摘要再組 Context 可行，但不自動解決切段／保存問題。未核准引擎、額外 artifact 或施工；下一步與停止線見子稿 §4–5。
