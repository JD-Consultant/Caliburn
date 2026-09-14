# LangChain／LangGraph 最小 Runtime 形狀（Working Design）

- 日期：2026-09-04
- Topic ID：`LLM-Q003`
- 階段：G3 Working Decision；Product Owner 於 2026-09-04 核准方案 A
- 父決策：`LLM-Q002` 已核准 LangChain stable 1.x＋LangGraph stable 1.x
- 效力：只比較第一版 runtime 根骨架；不授權版本 pin、Tool／Skill／Prompt schema、Memory mapping、JD schema、UI、spike 或 production 施工

## 1. 本輪唯一問題

第一版要以哪種最小 LangChain／LangGraph runtime 形狀承接 `S1`～`S7`，才能維持「有界單一顧問＋deterministic seams」，又不先把長訪談寫成固定 workflow？

## 2. 已固定邊界

1. 一名員工／一份 JD 對應一個可跨 request 與重啟延續的 thread。
2. 一位主顧問模型動態判斷本輪該理解、追問、讀取資料或提出 JD 變更；不是固定 wizard。
3. Runtime 管 model↔Tool loop、持久化、恢復、串流、通用 middleware 與有界停止。
4. Caliburn deterministic application code 管 scope、ID／版本、JD invariant、權限、冪等與核准 authority。
5. 員工對 AI JD 變更的日常審核，不預設等同「阻塞整個 agent run 的 HITL interrupt」；必要澄清與一般待審 JD 變更的恢復語意須在後續子決策分開處理。
6. 本輪不得決定 Tool 數量、Memory 表徵、模型呼叫次數、實體 JD state 數量或 UI。

## 3. 官方事實

### F1．`create_agent` 已是 LangChain 的標準 production-ready agent loop

LangChain 官方稱 `create_agent` 為 production-ready agent implementation；它在 LangGraph runtime 上建立「呼叫模型→模型選 Tool→執行 Tool→直到 final output 或 iteration limit」的 graph-based loop。Middleware 可在不改核心 loop 的前提下處理 context、動態 Tools、驗證、錯誤、重試、guardrail 與 logging。

### F2．`create_agent` 不是與 LangGraph 平行的第二套 runtime

`create_agent` 回傳的 agent 本身就是 compiled LangGraph；middleware 也在該 graph 內執行。若未來周邊拓撲真的超過標準 loop，官方允許把完整 agent 放進較大的 `StateGraph` 作 node／subgraph，原有 middleware 仍保留。

### F3．明確 `StateGraph` 適合有證據的複雜拓撲

LangGraph 官方建議 Graph API 用於多個條件分支、跨多元件共享 state、平行路徑與匯流，或需要 workflow 視覺化的情境。它提供更明確控制，但也要求先定義 nodes、edges 與共享 state。

### F4．Functional API 適合程序式或近線性的 workflow

官方將 Functional API 定位為：以既有 Python control flow、較少 boilerplate 加入 persistence、interrupt、streaming 與 durable execution；適合線性流程、簡單分支及既有程序式程式。它和 Graph API 共用同一 runtime，也可混用。

### F5．跨廠方向是從最簡單可成立的組合開始

Anthropic 將 workflow 定義為預定 code path、agent 定義為模型動態決定工具與流程，並建議先採最簡單方案，只有效果證明需要時才增加複雜度。OpenAI 最新 model guidance 同樣建議新 agent 系統使用成熟 SDK 的 orchestration／state／tracing，不重造通用 agent loop；實際產品不必因此採 OpenAI SDK。

## 4. 三個方案

| 方案 | 根骨架 | 優點 | 主要風險／不採條件 |
|---|---|---|---|
| **A．`create_agent` 作根 runtime（建議）** | 一個 `create_agent` compiled graph；接官方 persistent checkpointer／Store；只掛已證明需要的 middleware 與 Caliburn Tools | 直接符合動態單一顧問；標準 loop、persistence、streaming、middleware 與未來 graph composition 都保留；沒有第二層流程 wrapper | 若之後證明每個回合都必須經過不可省略的多節點順序、平行匯流或節點級 resume，才需要升級周邊拓撲 |
| **B．明確 `StateGraph` 作根 runtime** | 先建 nodes／edges／shared state，再將 model 或 agent 放入節點 | 固定分支、平行路徑、節點級觀測與視覺化最清楚 | 目前沒有證據證明長訪談需要固定拓撲；容易把理解、追問、JD 編輯誤寫成每輪 stages，增加不必要 state 與 replay seam |
| **C．Functional API 作根 runtime** | 以 `@entrypoint`／`@task` 寫程序式流程，必要時在 task 中呼叫 agent | 線性 batch、既有程序式流程與少量分支較精簡；持久化／interrupt 能力仍在 | 若根流程仍需動態 model↔Tool loop，就會再包一個 agent 或自行寫 loop；第一版沒有比 A 更直接，且可能先固定不必要順序 |

## 5. 依產品效果比較

| 判斷面 | A | B | C |
|---|---|---|---|
| `S1`～`S4` 自然、可回跳訪談 | **最佳貼合**：由模型在有界 loop 內選擇行動 | 能做到，但易過早把語意階段固化 | 能做到，但程序式順序誘因較強 |
| `S2`／`S6` thread、錯誤與恢復 | 原生 compiled LangGraph＋checkpointer | 原生 | 原生，但須正確切 task／side effect |
| `S3` 必要外部回答 | 可用 interrupt 或產品化 pending input；後續另定精確契約 | 可用 interrupt 節點 | 可用 interrupt |
| `S5` AI 變更待審 | 可由 product Tool／authority seam 承接；不能直接假設每次都用阻塞 HITL middleware | 可由專門節點承接，但目前尚無必要 | 可由程序式流程承接，但目前尚無必要 |
| `S7` 全量品質盤點 | 可由顧問按需呼叫 deterministic inventory／batch primitive；精確方式另定 | 若證明需平行或多階段，可局部升級 | 日後可作獨立、明確的 batch workflow 候選 |
| 過度設計與可逆性 | **最低**；未來可包進 StateGraph | 最高；先形成 graph state contract | 中等；可能形成第二層程序式 workflow contract |

## 6. G3 Working Decision

採 **A：`create_agent` 作第一版唯一根 runtime**。

其嚴格含義是：

1. HTTP／API composition root 將可信 invocation context 與 `thread_id` 交給一個 compiled agent；
2. agent 內由標準 model↔Tool loop 動態完成本輪語意工作，並以明確停止／成本界線結束；
3. checkpointer／Store、streaming 與少量 middleware 接在同一 LangGraph runtime；
4. Caliburn 只在 Tool／middleware 外圍寫必要的 deterministic product seam，不再建立第二個 agent loop；
5. **第一版不建立包住 agent 的自訂 `StateGraph`，也不以 Functional API 作根 workflow**；
6. 若代表性情境後來證明某一窄段必須固定拓撲，可將現有 agent 放入較大 graph，或將獨立 batch 工作改用 Functional API，不須推翻 agent 本體。

這是依官方 API 適用範圍與 `S1`～`S7` 作出的 Caliburn inference；不是宣稱 OpenAI、Anthropic 或所有大廠共同選用 `create_agent`。

Product Owner 的核准是目前設計基線，不是將底層細節永久寫死。後續在 invocation lifecycle、Tool／Memory／JD authority、錯誤恢復或代表性產品情境中取得符合 §8 的新證據時，必須回到本決策討論並明確修訂；不得因已進入細節設計而拒絕更好的方案，也不得由實作者自行翻案。

## 7. 這個決策沒有決定什麼

- 哪些 JD 操作是 Tool、structured final output 或兩者混合；
- 一般 AI 待審變更是否使用 LangChain HITL middleware；
- 必要澄清是同 run interrupt、結束本輪後續接，或其他產品呈現；
- exact agent state、Tool schema、Skill loading、Memory routing 與 context assembly；
- provider、default model、reasoning、retry 次數、token／cost cap；
- full-JD audit 是單次、分批、Functional API 或窄 StateGraph；
- exact dependency versions、spike、production migration 或 UI。

## 8. 重開條件

只有下列證據之一成立才重開根 runtime 形狀：

1. `S1`～`S7` 的代表性情境證明標準 loop 無法可靠表達必要順序或恢復；
2. 必須存在兩個以上固定分支、平行工作與匯流，且它們不是模型可選 Tool／middleware 能安全處理；
3. 必須在 agent 外保存可獨立恢復的多節點進度；
4. 官方 API／穩定度重大改變；
5. Product Owner 改變產品流程或 authority。

## 9. 官方來源

- [LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain Middleware overview](https://docs.langchain.com/oss/python/langchain/middleware/overview)
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph：Choosing between Graph and Functional APIs](https://docs.langchain.com/oss/python/langgraph/choosing-apis)
- [LangGraph Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api)
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangChain Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [Anthropic：Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- [OpenAI official model guidance](https://developers.openai.com/api/docs/guides/latest-model)

## 10. 決策紀錄與下一個 gate

2026-09-04：Product Owner 核准方案 A，並明確要求目前只能做最小方向決定；後續討論越詳細，若出現更好證據或原假設不成立，所有細節均可依治理流程調整。本核准不構成 Accepted ADR 或 production 施工授權。

下一個子決策為 `LLM-Q004`：設計一則員工訊息進入單一 `create_agent` runtime 後的最小 invocation lifecycle 與 state boundary；仍不得先固定 Tool、Memory、JD 或 UI schema。
