# 員工輸入與 Durable Interrupt 邊界（Working Design）

- 日期：2026-09-04
- Topic ID：`LLM-Q006`
- 階段：G3；Product Owner 已核准方案 A，但要求下一題明確釐清「保存狀態並暫停」的產品與 runtime 語意
- 父決策：`LLM-Q005` 已核准依「誰能恢復」使用 framework-native outcome／error primitive
- 效力：只決定何時暫停同一 logical invocation 等待員工、何時正常結束回合後自由續談；不授權 Tool schema、UI、資料欄位、JD 審核或 production 施工

## 1. 本輪唯一問題

哪些不可推測的員工問題必須 durable interrupt，讓同一 invocation 保存進度並等待回答；哪些只是顧問在正常聊天回合提出，員工可以稍後回答、改談別題或關閉後再回來？

## 2. 已知產品語意

1. 員工不需要按「本輪停止」；顧問回答完後，員工可以繼續傳訊息、暫停或關閉頁面。
2. 一般待釐清問題可顯示，也要能在長訪談中被記得，但不應鎖住整個聊天室。
3. 只有若缺少答案就會導致目前理解或後續分析產生重大歧義／錯誤時，才需要明確的「需要你的確認」。
4. AI 對 JD 的一般待審變更已有獨立審核語意；它不是每次都要阻塞 agent invocation 的 Tool approval。

以上是 Product Owner 已表達的產品方向；具體 mechanism 仍以本題研究裁決。

## 3. 官方事實

### F1．OpenAI 的 HITL interruption 用於需要授權的 Tool call，不是所有一般問題

OpenAI Agents SDK 的 HITL 流程在 Tool 宣告需要 approval 時暫停 run，將 interruption 放進可序列化的 `RunState`；使用者 approve／reject 後再恢復原 run。官方 model guidance 另明確建議：先完成已授權、可安全完成的工作，只在需要時才要求 approval，避免不必要的暫停。

OpenAI 公開 API／SDK 沒有要求把每個 conversational clarification 都變成 approval interruption。這表示 approval primitive 與普通對話輸出應分開；Caliburn 若要用同一 durable primitive 承接「必答澄清」，那是產品對 runtime 的 mapping，不是 OpenAI 的固定產品 taxonomy。

### F2．Anthropic 明確區分執行中 Clarification 與普通對話回合

Claude Agent SDK 官方文件直接區分：

- `AskUserQuestion` 用於 Claude 在執行中遇到多個有效方向、需要使用者選擇才可繼續；callback 會暫停 execution，回答後繼續同一 query；
- normal conversation turn 則是 Claude 完成該回合，等待下一則使用者訊息。

`AskUserQuestion` 可提供 2～4 個選項與自由文字，但官方也指出：若應用自己要提問，可由 application logic 另行處理；不是每個問題都必須走該 Tool。

### F3．LangGraph interrupt 的語意就是「需要外部輸入才能繼續」

LangGraph `interrupt()` 保存 checkpoint、無限期等待外部輸入，再以 `Command(resume=...)` 恢復。官方列出的用途是關鍵動作 approval、review／edit、Tool call 審核與必須驗證的人類輸入；它不是一般訊息的同義詞。

### F4．共同邊界是「是否必須在同一執行中取得答案」

OpenAI、Anthropic 與 LangGraph 的 API 名稱不同，但共同區分兩種生命週期：

1. 目前執行可以安全完成，之後再由普通 user message 開新 invocation；
2. 目前執行已停在必須取得外部決定的位置，需保存未完成狀態並 resume。

「問題重要」本身不足以判定 interrupt；真正差別是現在是否仍有一個未完成且不可安全推進的 operation。

## 4. 三個方案

| 方案 | 作法 | 優點 | 主要問題 |
|---|---|---|---|
| **A．只對真正阻塞目前執行的問題使用 interrupt（建議）** | 顧問能安全結束本輪時，以普通訊息提問；只有缺少答案就不能安全完成目前 analysis／operation 時，才 durable interrupt | 對齊 Anthropic 明確生命週期與 OpenAI 避免過度 approval 的方向；員工不會因一般缺口被鎖住；仍能可靠 resume 真正未完成工作 | 後續需定義一條窄判準並以代表性情境驗證，但不需自造 workflow engine |
| **B．所有澄清問題都 interrupt** | 只要 AI 想問問題就暫停當前 run | 每個問題都有明確 answer slot | 長訪談會頻繁被表單鎖住；員工不能先回答別題；把一般訪談誤作 approval workflow，增加狀態與 UI 負擔 |
| **C．所有問題都用普通聊天，不使用 clarification interrupt** | 每輪都正常完成，下一則訊息永遠是新 invocation | 最簡單、最自由 | 若模型已在一個不可安全完成的 operation 中等待決策，會失去精確 resume 點；可能重新推理、重做 Tool 或錯接答案 |

## 5. 建議 A 的判斷方式

只有同時符合下列條件，才是「需要你的確認」並 durable interrupt：

1. **不可可靠推測**：現有 conversation、Memory 與已知 JD 不能支持唯一答案；
2. **存在實質分歧**：至少兩個合理解讀會造成不同的工作理解、分析方向或受治理操作結果；
3. **錯猜有明顯代價**：繼續會形成重大錯誤、矛盾，或執行需要員工授權的動作；
4. **目前 operation 無安全完成點**：不能先完成其他已確定工作，再把問題留作一般後續訪談。

少一項，就以普通聊天問題處理；本輪正常 completed，員工可以稍後回答、改談別題或關閉後再回來。

這四項是依官方生命週期推導出的 **Caliburn 判準**，不是任何單一廠商使用的欄位或 enum。

## 6. 白話情境

### 普通問題：不 interrupt

> 「這項工作通常多久做一次？」

如果目前只是在補訪談細節，顧問可先保存「頻率待釐清」、正常結束回合並提出問題。員工沒有立即回答也不會破壞已完成工作，因此不鎖住聊天室。

### 必要確認：interrupt

> 員工先說自己核准請款，後來又說只有主管能核准；兩種解讀會改變責任邊界，而目前正在形成依賴此邊界的分析。

若既有資料無法排除其中一種解讀，也沒有安全的共同部分可先完成，顧問顯示「需要你的確認」，保存目前執行位置，等員工回答後接續同一 invocation。

### JD 待審變更：不因待審本身 interrupt

AI 已產生可撤回、尚未進入核准 JD 的變更時，員工可稍後集中審核。這是 document review queue，不等同「目前 agent 沒答案就無法繼續」；除非變更前本身遇到上述真正阻塞的歧義，否則不使用 clarification interrupt。

## 7. Framework responsibility mapping

- `create_agent`：正常顧問對話、Tool loop 與 final response。
- LangGraph Checkpointer＋`interrupt()`／`Command(resume=...)`：只保存與恢復真正未完成、等待員工輸入的 invocation。
- 普通訪談問題：作為 final response 的一部分，該 invocation 正常完成；下一則員工訊息開始新的 bounded invocation。
- Caliburn：只定義職務分析領域中何種歧義真的不可安全推測，並將 framework event 投影成員工可理解的產品狀態。

第一版不需自造另一套 pause engine，也不應把所有 LLM 問句掃描後強制轉成 interrupt。

## 8. 本題不先決定

- 是否以專用 Tool 讓模型提出必要確認；
- Tool 名稱、question／option schema 與選項數；
- 前端是卡片、dialog、inline form 或聊天訊息；
- 是否允許自由文字、一次幾題與顯示文案；
- Gap／待釐清的資料結構；
- JD changeset 審核、接受／拒絕／修改；
- retry、timeout、provider fallback、Memory schema 或 production 施工。

## 9. 建議與重開條件

建議採 **方案 A**。它保留員工自然訪談自由，也只在確有未完成 operation 時使用框架成熟的 durable pause／resume。

若代表性情境顯示模型會漏掉真正阻塞問題、過度 interrupt、resume 後錯接答案，或框架 primitive 改變，重開本決策。後續 Tool schema／UI 討論不得把 A 偷改成「所有問題都強制回答」。

## 10. 官方來源

### OpenAI

- [OpenAI model guidance：先完成可完成工作，避免不必要 approval pause](https://developers.openai.com/api/docs/guides/latest-model)
- [OpenAI API Reference：MCP approval request／response](https://platform.openai.com/docs/api-reference/responses-streaming/response/refusal)
- [OpenAI Agents SDK HITL（官方 SDK 文件）](https://openai.github.io/openai-agents-python/human_in_the_loop/)

### Anthropic

- [Claude Agent SDK：Handle approvals and user input](https://code.claude.com/docs/en/agent-sdk/user-input)
- [Claude Code Tools：AskUserQuestion](https://code.claude.com/docs/en/tools-reference)
- [Anthropic Managed Agents session statuses](https://platform.claude.com/docs/en/managed-agents/session-operations)

### LangChain／LangGraph

- [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangChain Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)

## 11. G3 裁決與下一個 gate

Product Owner 於 2026-09-04 核准方案 A：只有不可推測、存在實質分歧、錯猜有明顯代價且目前 operation 無安全完成點時才 durable interrupt；其餘問題正常結束回合，員工可自由決定何時回答。

`LLM-Q007` 已由 Product Owner 暫時核准：真正 blocking 的必要確認使用 LangGraph framework-native interrupt；Checkpointer 保存必要 interrupt state，不另建持久待確認問題、第二份 Memory 或第二份 JD。精確保存／停止／恢復語意與官方依據見 [`2026-09-04-required-confirmation-framework-pause-resume-working-design.md`](2026-09-04-required-confirmation-framework-pause-resume-working-design.md)。下一題才討論模型如何向 Runtime 表達必要確認，不直接跳到 production。
