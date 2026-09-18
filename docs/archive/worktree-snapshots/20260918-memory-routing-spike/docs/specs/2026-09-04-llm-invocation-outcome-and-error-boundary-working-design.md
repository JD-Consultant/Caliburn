# LLM Invocation Outcome 與錯誤邊界（Working Design）

- 日期：2026-09-04
- Topic ID：`LLM-Q005`
- 階段：G3；Product Owner 已核准方案 A
- 父決策：`LLM-Q004` 已核准一份 JD 一個持久 thread、每則新員工訊息一個有界 logical invocation
- 效力：只決定不同結果由誰恢復，以及應映射的成熟 Runtime primitive；不授權 API enum、UI 文案、retry 數字、provider fallback、Tool schema、JD 審核或 production 施工

## 1. 本輪唯一問題

正常完成、需要員工輸入、模型可自行修正、暫時性失敗、達限／取消與不可恢復失敗，應如何分流，才不會全部退化成「分析錯誤，只能重試」？

## 2. 跨廠官方共同邊界

### F1．完成、等待外部輸入與失敗不是同一件事

- OpenAI Agents SDK 將 final output、approval interruption、cancel、`MaxTurnsExceeded`、timeout 與 `ModelBehaviorError` 分開處理。
- Anthropic Managed Agents 將正常完成回到 `idle`、需要 Tool 結果／確認標為 `requires_action`、暫時錯誤進入 `rescheduling`、不可恢復錯誤才是 `terminated`。
- LangGraph `interrupt()` 明確繞過 retry 與 error handler；它是可持久 resume 的暫停，不是 exception recovery。

### F2．只有確定可重播的暫時性失敗才適合自動 retry

Anthropic SDK 預設只重試連線、408、409、429 與 5xx 等指定類型，採短暫 exponential backoff；永久 spend-cap 429 沒有 `retry-after`，持續重試也不會成功。OpenAI Agents SDK 的 model retry 是 opt-in，retry policy 必須判斷錯誤，且收到任何 response event 後不會盲目 replay request。LangChain 的 Model／Tool Retry middleware 也允許依 exception type 限定 retry 與次數。

共同原則不是「失敗都重試」，而是「可判定 transient＋replay-safe 才有限重試」。

### F3．模型能修的 Tool 錯誤可以回給模型，但程式錯誤不應一律如此

Anthropic Tool Runner 會把 Tool exception 轉成 `is_error: true` 的 Tool result，讓 Claude決定下一步；只帶安全的 exception type／message，不帶完整 stack trace。OpenAI Agents SDK 可選擇把找不到 Tool 的錯誤回給模型再跑一輪，也可以維持預設 `ModelBehaviorError`；LangChain `ToolErrorMiddleware` 允許只處理選定 exception，其餘 exception 繼續向外拋出。

因此，invalid arguments、找不到項目或可解釋的 domain validation 可以成為模型可見的修正訊息；權限、程式 bug、資料庫損毀、未知 invariant failure 與秘密資訊不能一概丟給模型反覆猜。

### F4．達限必須保持可辨識，不能偽裝成成功

OpenAI 以 `MaxTurnsExceeded` 明確終止過長 agent loop；Anthropic Tool Runner 支援 `max_iterations`；LangChain 提供每 invocation 的 model／Tool call limit，且達限可選擇 graceful end 或 exception。對 Caliburn 而言，若採 graceful end 但 UI 無法分辨「真的完成」與「被成本上限截斷」，就會造成錯誤產品語意。因此達限必須保留為可觀測 outcome；exact framework 設定留待 implementation design。

### F5．最後一段串流文字不是完成訊號

OpenAI Agents SDK 明示，最後可見 token 之後仍可能有 session persistence、approval bookkeeping 或 compaction；stream iterator 結束後才算完整 run result。Anthropic 也把 delta 定位為 best-effort preview，buffered event／session idle 才是 authoritative record。故 Runtime 必須依正式 completion／interrupt／error event 收尾，不能以文字、連線關閉或前端 timeout 猜測成功。

## 3. 三個方案

| 方案 | 作法 | 優點 | 主要問題 |
|---|---|---|---|
| **A．按「誰能恢復」分流到 framework-native primitive（建議）** | 模型能修→安全 Tool error；員工必答→durable interrupt；transient infra→有限 retry；達限／取消→明確 bounded stop；bug／永久錯誤→terminal failure；正常 final→completed | 直接對齊 OpenAI／Anthropic／LangGraph／LangChain 的既有機制；成本最低且錯誤最可理解；不需自造第二套 agent loop | 需要一個很薄的 Runtime normalization boundary；後續必須定義 exception allowlist 與產品投影，但不用現在寫死 enum |
| **B．所有問題都回給模型自行修正** | Tool、provider、domain、衝突與未知錯誤都成為 model-visible message，再讓 agent loop 繼續 | 表面上流程單一，某些參數錯誤能自癒 | 會浪費 token、造成無限修正、洩漏內部錯誤，且模型無法修復權限／網路／程式 bug；也無法取代員工必要回答 |
| **C．任何非成功都終止並要求員工重試** | 不在 run 內分流；前端只顯示失敗與重試 | 實作最簡單 | 正是目前卡住的產品問題；把等待員工、可自癒參數錯誤、transient outage 與程式 bug 混在一起，員工重試也可能得到同一錯誤 |

## 4. 方案 A 的最小 outcome 模型

這裡先固定語意，不固定 API enum 名稱：

| 情況 | 誰能恢復 | Runtime 行為 | 是否結束／暫停產品 invocation |
|---|---|---|---|
| 模型產生 final output，stream 與 persistence 完成 | 無需恢復 | framework completion | 完成 |
| 缺少不可推測的員工答案 | 員工 | durable interrupt＋checkpoint；回答後 resume | 暫停，不算錯誤 |
| Tool 參數、目標或 domain validation 可由模型修正 | 模型 | 回傳安全、精確、可操作的 Tool error；受 run limits 約束 | invocation 內繼續 |
| 已知 transient model／network／Tool failure | Runtime | 只對 allowlisted、replay-safe failure 做 exponential backoff＋有限 retry | retry 中仍 running；耗盡後 failed |
| model／Tool call、token、時間或成本達限 | 員工或後續新 run | 停止目前 loop並保留明確 limit outcome | 有界停止，不算 completed |
| 員工／系統取消 | 無 | 停止執行並完成必要 cleanup／checkpoint | cancelled |
| auth、permission、config、程式 bug、未知 invariant／storage failure | 工程／系統管理 | 不交給模型猜；記錄可追蹤診斷，對產品回傳安全失敗 | failed |

其中只有 `completed` 是成功；`waiting` 是可恢復暫停；模型修正與 transient retry 是 invocation 內部路徑；limit、cancel 與 failed 都必須讓 UI 離開永久鎖定狀態。這是 Caliburn 對官方 primitive 的產品映射，不宣稱各家使用相同 enum 名稱。

## 5. framework responsibility mapping

- `create_agent`：標準 model↔Tool loop與 final output。
- LangGraph Checkpointer＋`interrupt`／`Command(resume=...)`：需要外部輸入時的 durable pause／resume。
- LangChain `ToolErrorMiddleware` 或 Tool 的 typed result：只承接模型可修正的安全錯誤。
- LangChain `ModelRetryMiddleware`／`ToolRetryMiddleware`：只承接 allowlisted transient exception，採有限 backoff。
- LangChain model／Tool call limit與外層 timeout／cost accounting：阻止 runaway loop；結果不得偽裝成 completed。
- Framework stream completion／interrupt／exception：驅動 Runtime outcome；前端 delta 只作預覽。
- Caliburn Runtime 的最薄責任：把上述 framework 結果正規化成產品可理解的 outcome，隱藏 stack trace／secret，附上可信 operation／trace reference，並確保任何停止結果都能解除分析鎖。

最後一項是必要 application boundary；它不是另一套 agent loop，也不重新實作 framework retry、interrupt 或 persistence。

## 6. 本題不先決定

- outcome 的 wire enum 與繁中 UI 文案；
- 哪些產品問題必須 durable interrupt；
- retry exception allowlist、次數、delay、jitter、timeout 與成本數字；
- structured Tool error 的欄位；
- provider fallback 是否存在；
- JD changeset 的接受／拒絕／編輯；
- Memory、Skill、Prompt、RAG、schema、spike 或 production。

## 7. 建議與可重開條件

建議採 **方案 A**。它不是自創錯誤狀態機，而是依恢復責任把情況送到各 framework 已有的 completion、Tool result、retry、interrupt、limit／cancel 與 exception primitive，再由一層最薄產品 boundary 做安全投影。

若官方 API 改變、代表性情境證明分類不足、相同錯誤在不同 provider 無法穩定映射，或 Product Owner 改變員工體驗，重開本決策；不得因後續 schema 已寫就拒絕調整，也不得由實作者自行新增無上限 retry。

## 8. 官方來源

### OpenAI

- [OpenAI Agents SDK — Running agents and exceptions](https://openai.github.io/openai-agents-python/running_agents/)
- [OpenAI Agents SDK — Streaming lifecycle](https://openai.github.io/openai-agents-python/streaming/)
- [OpenAI Agents SDK — Model timeouts and retry](https://openai.github.io/openai-agents-python/models/)
- [OpenAI Agents SDK — Exception reference](https://openai.github.io/openai-agents-python/ref/exceptions/)

### Anthropic

- [Anthropic Managed Agents — Session operations](https://platform.claude.com/docs/en/managed-agents/session-operations)
- [Anthropic Managed Agents — Session event stream](https://platform.claude.com/docs/en/managed-agents/events-and-streaming)
- [Anthropic Tool Runner](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner)
- [Anthropic API errors](https://platform.claude.com/docs/en/api/errors)
- [Anthropic Python SDK retries](https://platform.claude.com/docs/en/api/sdks/python)

### LangChain／LangGraph

- [LangChain Prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [LangChain Tool error handling](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)

## 9. G3 裁決與下一個 gate

Product Owner 於 2026-09-04 核准方案 A：依「誰能恢復」使用 framework-native completion、durable interrupt、模型可修正 Tool error、allowlisted bounded retry、limit／cancel 與 terminal failure，再由最薄的產品 boundary 安全投影；不得把所有結果混成同一個「分析錯誤，請重試」。

下一個子決策 `LLM-Q006` 只選「哪些員工問題必須 durable interrupt、哪些只是正常聊天回合」；不在本題偷渡 JD 審核、Tool schema 或 UI。
