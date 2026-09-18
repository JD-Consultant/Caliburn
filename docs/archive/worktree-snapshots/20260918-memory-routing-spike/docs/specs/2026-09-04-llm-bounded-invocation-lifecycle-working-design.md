# LLM 有界 Invocation Lifecycle 與 State Boundary（Working Design）

- 日期：2026-09-04
- Topic ID：`LLM-Q004`
- 階段：G3 Working Decision；Product Owner 於 2026-09-04 核准方案 A
- 父決策：`LLM-Q002` 已核准 LangChain stable 1.x＋LangGraph stable 1.x；`LLM-Q003` 已核准一個 `create_agent` compiled graph 作第一版根 runtime
- 效力：只討論一則員工訊息如何啟動、暫停、恢復與結束一個有界 agent invocation；不授權 Tool／Skill／Prompt／Memory／JD schema、精確上限、UI、spike 或 production 施工

## 1. 本輪唯一問題

一則員工訊息進入 `create_agent` 根 runtime 後，應如何對應一個有界、可持久續接且能區分完成、等待與失敗的 invocation？什麼證據才足以在標準 agent loop 外再增加固定 runtime stage？

## 2. 先把名詞說清楚

- **Thread**：一位員工的一份 JD 所對應的持久訪談容器；可以跨很多次開關頁面、很多則訊息及很多次執行。
- **Invocation／run**：為處理一則新員工訊息而啟動的一次有界工作。它可以在內部呼叫模型與 Tool 多次，並不等於一次模型 API request。
- **Model step**：invocation 內的一次模型呼叫。模型可能要求 Tool，Runtime 執行後再開始下一個 model step。
- **Resume**：同一個 invocation 因必要外部輸入暫停後，以原 thread 與 checkpoint 繼續；不是把回答偽裝成另一個互不相關的新工作。

因此，「同一 thread 可以一直訪談」與「每則訊息必須有界結束」並不衝突：一個 thread 由很多次 invocation 組成，一次 invocation 又可包含多個 model／Tool step。

## 3. 官方事實

### F1．跨廠都區分持久 conversation／session 與一次 agent run

- OpenAI Agents SDK 明確說，一次 `Runner.run` 代表聊天中的一個 logical turn；該 run 內可以發生多次 LLM 呼叫、Tool、handoff，結束後下一則使用者訊息再呼叫一次 run。Session 會在 runs 之間保存 conversation history。
- Anthropic Managed Agents 以持久 session 保存跨互動狀態；送入 `user.message` 會啟動或繼續工作，agent 完成本次工作後 session 回到 `idle`，而不是銷毀 session。
- LangGraph／LangSmith 將 thread 定位為跨多次 runs 的持久 state container；每個 run 使用 thread 當前 state，執行 graph 後再更新 state。

這支持「長期 thread＋多次有界 invocation」，不是一個永不結束的 HTTP request，也不是每個 model step 都建立新 conversation。

### F2．標準 agent loop 本來就允許一個 invocation 內有多次 model／Tool step

LangChain `create_agent` 會反覆執行 model→Tool→model，直到模型輸出 final result 或達到 iteration limit。OpenAI Agents SDK 與 Anthropic Tool Runner 公開的 loop 也採相同基本形狀。故「可能需要八個 model step」不代表員工送了八則訊息，也不應被拆成八個產品 invocation。

### F3．持久 thread state、invocation context 與 stream projection 是不同責任

- LangChain agent 的短期 conversation state 位於 graph state，透過 checkpointer 依 `thread_id` 在每個 step 保存及讀取。
- LangChain `Runtime.context` 是本次 invocation 交給程式與 Tool／middleware 的可信依賴或識別資訊，不會自動送給 LLM。
- streaming 是執行中的進度投影；OpenAI 官方提醒最後一個可見 token 不等於 run 已完成，還可能有 session persistence、approval bookkeeping 或 compaction 在收尾。

因此 UI、API 與資料 authority 不能用「看到 assistant 最後一段文字」猜執行已完成；必須依 Runtime 的完成／暫停／錯誤結果解鎖。

### F4．等待外部輸入不是失敗，resume 也不是普通 retry

LangGraph `interrupt()` 會保存 checkpoint 並等待外部輸入；以相同 `thread_id` 和 `Command(resume=...)` 繼續。Interrupt 不進 retry／error handler。Anthropic custom Tool／confirmation 也會令 session 進入 `requires_action`，收到結果後再恢復執行；OpenAI Agents SDK 以 interruption＋`RunState` 支援相同的 pause／resume 語意。

LangGraph 同時明示，resume 時會從被中斷 node 的開頭重新執行，所以 interrupt 前的副作用必須可安全重做或具冪等性。這是後續 Tool／authority design 的硬限制，但本題不先固定 Tool schema。

### F5．成本與失控必須由有界機制控制，而不是靠 prompt 希望模型自己停止

- LangChain 提供 model-call limit、tool-call limit、model／tool retry 與 timeout 等 middleware／runtime 能力。
- OpenAI Agents SDK 以 `max_turns` 停止過長 loop，並區分 `MaxTurnsExceeded`、model timeout、tool timeout、model behavior error 等不同失敗。
- Anthropic Managed Agents 可設定 budget cap，達上限時暫停 session，而不是無限制繼續花費。

官方共同方向是「明確上限＋分類錯誤＋有限 retry」；沒有共同固定數字。精確 call／token／時間／成本上限必須等模型、Tool 與代表性情境確定後再設計。

### F6．同一 thread 同時接受兩個 run 是獨立的併發政策，不是 agent loop 的必要能力

LangSmith Agent Server 公開 enqueue／reject／interrupt／rollback 四種 double-texting 策略，其中 `reject` 會讓原 run 繼續並拒絕第二個 concurrent run；官方同時明示這組能力不是 OSS LangGraph 本身提供。OpenAI 與 Anthropic 也公開了 active steering／中途輸入能力，但都不是建立一般多輪 agent 的必要條件。

目前產品已選擇「分析中不送第二則訊息、也不與員工 JD 編輯併行」。這是 Caliburn 的第一版產品取捨，不冒充所有大廠唯一做法；若日後真實延遲證明需要 steering／queue，再獨立重開。

## 4. 三個方案

| 方案 | 形狀 | 優點 | 代價／主要風險 |
|---|---|---|---|
| **A．一則訊息＝同一 thread 上一次有界 invocation（建議）** | Runtime 接納一則新訊息後啟動 `create_agent`；內部可有多次 model／Tool step；完成、必要輸入 interrupt、達限、取消或失敗即停止。下一則一般訊息再開始下一個 invocation | 最貼近 OpenAI／Anthropic／LangGraph 公開 lifecycle；保留動態顧問判斷，不預設每輪固定 stages；成本與錯誤有清楚邊界 | 後續仍須逐題決定 interrupt 適用時機、上限數字、錯誤分類與產品投影；OSS 部署若不用 Agent Server，需要極薄的同-thread admission 機制 |
| **B．一個長時間 active run，允許中途 steering／排隊訊息** | session 長期保持 running；員工輸入可排隊、插入或中斷目前工作 | 長任務中可即時改方向，互動更連續 | concurrent Tool／partial side effect、rollback、訊息排序與 UI authority 複雜；與第一版分析時鎖定輸入的產品方向相反，尚無需求證據 |
| **C．每則訊息都先包固定多階段 workflow** | 例如固定 admission→理解→JD→回覆，每段有自己的 state／retry | 每段輸入輸出與觀測較明確；若每回合確有不可省略順序，容易強制 | 會把仍應由顧問動態判斷的工作寫死；可能增加模型呼叫、延遲、成本與中間 state；目前沒有證據每則訊息都需做 JD 工作或固定兩次模型呼叫 |

## 5. 建議方案 A 的最小語意

```text
同一份 JD 的持久 thread
  ├─ invocation 1：員工訊息 → model／Tool loop → completed
  ├─ invocation 2：員工訊息 → model／Tool loop → waiting_for_employee
  │                                      └─ resume → completed
  └─ invocation 3：員工訊息 → model／Tool loop → failed／limit_reached
```

若採 A，本輪只固定以下語意，不固定資料欄位與 UI 名稱：

1. 一份 JD 只有一個持久 thread；thread 可承接任意多次後續訪談。
2. 每則被 Runtime 接納的新員工訊息建立一次 logical invocation；同一 thread 第一版不可有兩個 active invocations。
3. 一個 invocation 可有零至多個 Tool call 與多個 model step，但必須受 model calls、Tool calls、時間、輸出／推理 token 或成本等至少一種以上的可觀測上限約束；精確組合留待後續決策。
4. invocation 只可落入可區分的結果類別：正常完成、等待員工輸入、達到上限、取消、可恢復暫時失敗、不可恢復失敗。這些是語意類別，不是現在就寫死 API enum。
5. 必要外部回答若使用 durable interrupt，收到回答後 resume 原 invocation；普通聊天問題仍可正常完成本輪，下一則員工訊息開新 invocation。兩者的產品判準另開子決策。
6. UI 只有在 Runtime 確認完成、暫停或失敗邊界後才解除「分析中」狀態；不能以最後一個 token、assistant text 或 SSE 斷線推測成功。
7. transient provider／network failure 才可有限自動 retry；模型可修正的 Tool 參數／domain validation error 可回傳安全且精確的結果，讓模型在同一 invocation 內有界修正；需要員工決定的問題不得偽裝成 retry；程式 bug／未知錯誤不得把 stack trace 丟給模型反覆猜。
8. checkpoint 只承接跨 step／pause／restart 必須恢復的 thread state；可信 scope、依賴、limit 與 operation metadata 走 invocation runtime context；stream／UI view 是投影，不成為第二份 authority。哪些 domain data 放在哪一層仍由後續 Memory／JD authority 子決策決定。

## 6. 什麼情況才增加固定 runtime stage

在根 agent loop 外增加 node／stage，至少要有以下一項可觀察證據，且 middleware、Tool 或 deterministic API seam 無法更簡單地解決：

1. 每個 invocation 都有一段不可省略、順序固定且必須獨立 checkpoint／resume 的工作；
2. 有兩個以上固定分支或平行工作必須 deterministic 匯流，不能安全交由 agent 動態選 Tool；
3. 某副作用需要與 agent loop 分離的 durable transaction／compensation boundary；
4. 代表性情境證明單一 loop 無法達到正確率、成本或可恢復性門檻；
5. framework 官方 API 或產品流程改變。

單純想把概念畫得整齊、想顯示進度、或某次 prompt 曾依序做兩件事，不足以建立固定 stage。

## 7. 本題尚未決定

- `waiting_for_employee` 的 exact 使用時機與是否對應「需要你的確認」；
- 一般 JD 待審變更是同 invocation interrupt、持久 pending data，或其他產品機制；
- exact model／Tool／token／時間／成本上限與 retry 次數；
- provider capability negotiation、fallback 與錯誤 wire contract；
- exact agent state、Runtime context、operation ID 或 API enum；
- Tool／Skill／Prompt／structured output、Memory／JD authority、UI 與 RAG；
- 是否採 LangSmith Agent Server，或在本機 API 中使用 OSS graph＋PostgreSQL checkpointer。

## 8. G3 Working Decision 與重開條件

Product Owner 於 2026-09-04 核准採 **方案 A** 作下一層 Working Decision。它採用各家公開的共同 lifecycle，而不把「理解→JD」誤寫成每則訊息固定執行的兩個模型 stages，也不為尚未需要的 active steering 引入複雜併發。

這仍是可調整的最小基線。若後續 Tool／Memory／JD authority、必要澄清、成本實測或代表性情境符合 §6 任一條件，必須重開 `LLM-Q003`／`LLM-Q004` 並與 Product Owner 討論，不能因文件已寫就硬套，也不能由實作者靜默翻案。

## 9. 官方來源

### OpenAI

- [OpenAI Agents SDK — Running agents](https://openai.github.io/openai-agents-python/running_agents/)
- [OpenAI Agents SDK — Streaming](https://openai.github.io/openai-agents-python/streaming/)
- [OpenAI Agents SDK — Sessions](https://openai.github.io/openai-agents-python/sessions/)
- [OpenAI Agents SDK — Context management](https://openai.github.io/openai-agents-python/context/)
- [OpenAI Responses API — Create a response](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- [OpenAI Responses API beta — Multi-agent Responses and events](https://developers.openai.com/api/reference/cli/resources/beta/subresources/responses)

### Anthropic

- [Anthropic Managed Agents — Events and streaming](https://platform.claude.com/docs/en/managed-agents/events-and-streaming)
- [Anthropic Managed Agents — Session operations](https://platform.claude.com/docs/en/managed-agents/session-operations)
- [Anthropic Managed Agents — Sessions](https://platform.claude.com/docs/en/managed-agents/sessions)
- [Anthropic Tool runner](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner)
- [Anthropic — How tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)

### LangChain／LangGraph

- [LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain Runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- [LangChain Short-term memory](https://docs.langchain.com/oss/python/langchain/short-term-memory)
- [LangChain Streaming](https://docs.langchain.com/oss/python/langchain/streaming)
- [LangChain Prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)
- [LangSmith Threads](https://docs.langchain.com/langsmith/use-threads)
- [LangSmith Runs](https://docs.langchain.com/langsmith/runs)
- [LangSmith Double texting](https://docs.langchain.com/langsmith/double-texting)

## 10. 下一個 gate

方案 A 已完成 G3 裁決。下一題 `LLM-Q005` 只處理 invocation 的停止、等待與錯誤分類及 framework primitive mapping；仍不進入 Tool／Memory／JD schema 或 production 施工。
