# 必要確認的 Framework-native Pause／Resume 語意（Working Design）

- 日期：2026-09-04
- Topic ID：`LLM-Q007`
- 階段：PAUSED；`LLM-Q011` 正在重驗訪談澄清是否需要 durable interrupt
- 父決策：`LLM-Q006` 已把普通訪談問題與真正阻塞目前執行的必要確認分開
- 效力：可被新證據重開的 Working Decision；不修改 Accepted ADR、production code、Tool schema 或 UI

> 目前不得依本文施工。Owner 已觸發本文 §6 的重開條件：「必要問題其實能安全結束回合」與「UX 可能過度阻塞」。Current 問題與新官方證據見 [`2026-09-04-conversational-question-vs-durable-interrupt-revalidation.md`](2026-09-04-conversational-question-vs-durable-interrupt-revalidation.md)。

## 1. 本輪唯一問題

真正需要員工回答才能繼續的「需要你的確認」，應該正常結束回合後另外保存一筆待確認問題，還是使用 runtime 原生 interrupt 保存並恢復同一 logical invocation？

## 2. 官方事實與適用邊界

### F1．OpenAI 的公開 pause 主要承接 client-owned Tool 結果與 approval

OpenAI Responses 公開契約可在等待 client-owned Tool 結果或 approval 時停止，後續以既有 response／conversation 關聯繼續；OpenAI model guidance 同時要求避免不必要的 approval pause。公開文件沒有要求把每個普通 conversational clarification 都轉成 interruption。

### F2．Anthropic 明確同時提供 normal turn 與執行中 AskUserQuestion

Claude Agent SDK 的 `AskUserQuestion` 會暫停目前 query，等待使用者回答後繼續；官方明確說這不同於 Claude 完成本輪、等待下一則訊息的 normal conversation turn。等待時間過長時，TypeScript SDK 可用 `defer` 讓程序退出，再從持久 session 恢復。

### F3．LangGraph interrupt 是成熟的通用 human-input primitive

LangGraph `interrupt()` 會透過 Checkpointer 保存 graph state，等待外部輸入，再以同一 `thread_id` 與 `Command(resume=...)` 恢復。恢復時，包含 interrupt 的 node 會從頭執行；因此 interrupt 前的副作用必須可重複，或更安全地放在已完成的前一個 node。

### F4．共同方向與非共同部分

跨廠共同方向是把 normal completion 與尚未完成、等待外部輸入的 execution 分開。Anthropic 對 clarification 提供明確 pause primitive；OpenAI 公開 primitive 主要落在 Tool／approval。把 Caliburn 的少數必要確認映射到 LangGraph interrupt，是符合成熟 runtime 能力的 **Caliburn mapping**，不是「所有大廠都把每個澄清問題做成 pause」的事實。

## 3. 三個方案

| 方案 | 作法 | 判斷 |
|---|---|---|
| A．正常完成＋自建持久待確認物件 | 本輪 completed；另建 pending question，下一則訊息開新 invocation | 可行，但重複實作 framework 已有的 durability／resume，還會增加第二套生命週期 |
| **B．必要確認使用 framework-native interrupt** | 普通問題正常完成；真正 blocking 的問題由 LangGraph Checkpointer 保存並 resume | **建議且暫時核准**；貼合 Anthropic clarification 與 LangGraph human-input pattern，不自建 pause engine |
| C．所有問題都正常完成且不保存等待狀態 | 只依聊天歷史推斷下一則訊息在回答什麼 | 最簡單，但無法可靠表示同一 execution 正在等待必要輸入 |

## 4. 暫時核准的精確語意

### 4.1 保存什麼

由 LangGraph Checkpointer 保存：

- 到達安全邊界時可公開、可序列化的 graph state；
- interrupt payload，也就是員工看到的問題與必要的回答形狀；
- framework 用來把回答送回正確 interrupt 的 thread／interrupt 關聯。

這表示問題在技術上一定會耐久存在，否則關頁後不能恢復；但它只是 checkpoint 中的 framework interrupt，不是 Caliburn 另外建立的 `pending_confirmation` 資料表、第二份 Memory 或第二份 JD。

不保存模型隱藏思考。Canonical conversation、Semantic Memory 與 JD 仍由既有各自的 authority 管理，不能為 interrupt 複製一份。

### 4.2 停止什麼

- 停止目前 logical invocation 的 model／Tool loop；
- 不在背景持續呼叫模型或消耗 token；
- HTTP request／worker 可以結束，等待狀態由 durable Checkpointer 承接；
- pause 不等於鎖住整個 App。等待期間可否直接編輯 JD 是另一個產品／並行決策，本題不偷決定。

### 4.3 如何恢復

員工回答後，Runtime 以同一 thread 的 `Command(resume=answer)` 回覆該 interrupt，繼續原 logical invocation。因 LangGraph 會從 interrupt 所在 node 的開頭重跑：

1. 所有已確定且需要落盤的 effect 先在前一個 node 完成；
2. interrupt node 在 `interrupt()` 前不做不可重複的寫入；
3. 回答只送進 framework resume，不偽裝成另一筆普通新問題；
4. 員工關頁後仍可從同一 thread 恢復。

以上固定生命週期，不先固定 Tool 名稱、JSON 欄位、選項數或 UI 樣式。

## 5. 哪些情況不使用 interrupt

- 普通訪談追問；
- 一般資料缺口或稍後可補的細節；
- AI 已產生但尚待員工審核的 JD 變更；
- provider／schema／Tool 錯誤；
- 只因問題「很重要」，但目前 invocation 仍可安全完成的情況。

這些仍依 `LLM-Q005`／`LLM-Q006` 使用正常完成、模型修正、retry 或 terminal failure，不混成 human-input pause。

## 6. 重開條件

- LangGraph 官方 interrupt／resume 契約改變；
- 代表性測試顯示 node replay 造成不可接受的重複 effect 或狀態錯接；
- 必要確認其實都能安全結束回合，framework pause 沒有產品收益；
- 真實 UX 顯示 interrupt 讓長訪談過度阻塞；
- Product Owner 改變「需要你的確認」的產品語意。

## 7. 官方來源

- [OpenAI model guidance：避免不必要 approval pause](https://developers.openai.com/api/docs/guides/latest-model)
- [OpenAI Responses API：client-owned Tool／approval required input](https://developers.openai.com/api/reference/cli/resources/beta/subresources/responses)
- [Claude Agent SDK：Handle approvals and user input](https://code.claude.com/docs/en/agent-sdk/user-input)
- [Claude hooks：defer and resume](https://code.claude.com/docs/en/hooks)
- [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)

## 8. G3 裁決與下一個 gate

Product Owner 於 2026-09-04 暫時同意方案 B：普通問題維持 normal turn；只有依 `LLM-Q006` 判定為真正 blocking 的「需要你的確認」才使用 LangGraph framework-native interrupt。Checkpointer 保存必要的 interrupt state；不另建持久待確認問題、第二份 Memory 或第二份 JD。

下一題 `LLM-Q008` 只決定模型如何向 Runtime 表達這個必要確認，先比較專用小型 Tool、structured output 與其他 framework-native 入口；不先寫 schema 或 production code。
