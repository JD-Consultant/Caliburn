# 必要確認的模型控制入口（Working Design）

- 日期：2026-09-04
- Topic ID：`LLM-Q008`
- 階段：PAUSED；父前提由 `LLM-Q011` 重驗中
- 父決策：`LLM-Q006` 已限定使用時機；`LLM-Q007` 已限定以 LangGraph `interrupt()`／`Command(resume=...)` 保存與恢復真正 blocking 的確認
- 效力：研究與選項紀錄；不授權 Tool schema、UI、production code、測試或 migration

> 本文保留為方案歷史；訪談澄清是否應成為 Tool＋interrupt 尚未成立。Current 問題見 [`2026-09-04-conversational-question-vs-durable-interrupt-revalidation.md`](2026-09-04-conversational-question-vs-durable-interrupt-revalidation.md)。

## 1. 本輪唯一問題

模型應透過哪個最小、成熟、可驗證的控制入口，向 Runtime 表達「目前 operation 真的缺少員工決定，必須暫停」？該入口必須避免把普通訪談問句誤判成 interrupt。

## 2. 官方事實

### F1．OpenAI 以 Tool call 作模型與應用程式行為的 typed control channel

OpenAI Function calling 的公開流程是：應用程式提供 Tools，模型產生 Tool call，應用程式執行，再把 Tool output 交回模型。`strict: true` 可要求參數符合 schema。Responses 的 client-owned Tool／approval 若缺結果，可進入 `waiting_for_required_input`，之後沿既有 response lineage 接續。

因此 OpenAI 的共同 primitive 是「模型發出 typed Tool request，由 Runtime 執行或等待外部輸入」，不是由應用程式解析自然語句中的問號。OpenAI 公開文件沒有一個與 Claude `AskUserQuestion` 同名的通用內建澄清 Tool。

### F2．Anthropic 直接把必要澄清做成 `AskUserQuestion` Tool

Claude Agent SDK 在模型面臨多個有效方向、需要使用者決定時，會呼叫 `AskUserQuestion`。應用程式透過 `canUseTool` 辨識它、顯示問題與選項、收回答，再讓 Claude 繼續。這是明確的 Tool event，不是掃描普通文字輸出。

### F3．LangGraph 正式支援 Tool 內 `interrupt()`

LangGraph 可直接在 Tool function 內呼叫 `interrupt()`。模型自然呼叫 Tool 後，Runtime 暫停；回答以同一 thread 的 `Command(resume=...)` 回到 Tool。這正好銜接 `LLM-Q007` 已核准的 durable pause／resume，而不需再造一套 pending-question engine。

### F4．Structured output 是可靠資料輸出，但不是 pause primitive

OpenAI、Anthropic 與 LangChain 都提供 structured output／strict schema。LangChain `create_agent.response_format` 會在 agent 的 Tool loop 結束後產生並驗證 final structured response。它適合讓一個已完成回合輸出固定資料；若拿它表示 `requires_input`，Runtime 仍要額外把 completed output 轉成 interrupt，且每個普通 final response 都要承擔 union schema。

### F5．共同方向與 Caliburn mapping

可合理稱為跨廠共同方向的是：需要驅動應用程式行為或等待外部輸入時，使用 typed Tool／runtime event，不依靠自然語言解析。`AskUserQuestion` 的名稱與輸入欄位不是跨廠標準；Caliburn 仍需定義一個最小的職務訪談 Tool，作為對這些成熟 primitives 的產品 mapping。

## 3. 三個方案

| 方案 | 作法 | 優點 | 主要問題 |
|---|---|---|---|
| **A．專用小型確認 Tool（建議）** | 模型只有在 `LLM-Q006` 四條 blocking 判準都成立時呼叫專用 Tool；Tool 內由 Runtime 呼叫 LangGraph `interrupt()` | 最接近 Claude `AskUserQuestion`；同時符合 OpenAI Tool control channel 與 LangGraph interrupts-in-tools；不解析文字、不迫使所有回答套大 union | Tool 名稱與最小參數仍需下一題決定；需以情境驗證模型不會過度呼叫 |
| B．final structured output 回傳 `completed | requires_input` | 每次 agent 最終輸出固定 union；Runtime 看見 `requires_input` 再轉成等待 | 型別明確、容易在 final boundary 驗證 | final response 已表示本輪 Tool loop 結束；仍須自訂轉接成 interrupt；擴大每輪 schema，與已選動態顧問 Tool loop 不如 A 自然 |
| C．解析自然語言問句或另加分類器 | 從文字、問號、關鍵詞或第二次分類判斷是否暫停 | 表面上不需新增 Tool | 語言脆弱、會混淆普通訪談問題與 blocking 問題；另一次分類增加成本且仍不構成明確 runtime event，不建議 |

## 4. 建議方案 A 的精確邊界

```text
模型判斷符合 LLM-Q006 的 blocking 條件
    → 呼叫專用、很小的 confirmation Tool
    → Runtime 驗證 Tool 輸入
    → Tool 內呼叫 LangGraph interrupt(payload)
    → UI 顯示「需要你的確認」並等待
    → 員工回答
    → 同一 thread 以 Command(resume=answer) 恢復
    → Tool 將回答交回 agent，agent 繼續原 logical invocation
```

邊界如下：

1. Tool 只請求員工輸入，不直接修改 Semantic Memory、JD 或待審 changeset。
2. 普通訪談問題繼續以自然語言完成回合，不呼叫此 Tool。
3. Runtime／framework 產生 thread ID、interrupt ID、時間與狀態；不要求模型填這些系統欄位。
4. 不從模型的普通文字再猜是否應 interrupt；Tool call 本身就是控制訊號。
5. 本題不先決定一個或兩個 Tool、欄位、選項數、自由文字、UI 或重試規則，避免在 G2 偷渡 schema 設計。
6. LangGraph resume 會重跑含 interrupt 的 node；Tool 在 `interrupt()` 前不得執行不可重複的副作用，沿用 `LLM-Q007` 的既有約束。

## 5. 建議裁決

建議暫時採 **方案 A：專用小型確認 Tool＋Tool 內 LangGraph interrupt**。

這不是 Caliburn 自造 pause engine；它以 Anthropic 已公開使用的 clarification-Tool 形狀作產品參考，以 OpenAI／Anthropic 共通的 typed Tool channel 傳遞模型意圖，再由已選 LangGraph framework 承接 durable pause／resume。Caliburn 自訂的只剩：何時算 blocking（已由 `LLM-Q006` 決定）以及下一題要裁定的最小員工問題內容。

若 Owner 核准，下一個 gate 只討論 Tool 的最小輸入／回傳責任，並先檢查 LangChain／LangGraph 是否已有可直接使用的 schema／middleware；仍不直接施工。

## 6. 重開條件

- 代表性情境顯示模型頻繁把普通問題呼叫成 confirmation Tool；
- provider 無法穩定產生該 Tool call，或跨 provider Tool binding 行為不相容；
- LangGraph Tool 內 interrupt 契約改變；
- structured final outcome 經實證能以更少複雜度提供相同 durable resume；
- Product Owner 改變 `LLM-Q006`／`LLM-Q007` 的產品語意。

## 7. 官方來源

### OpenAI

- [Function calling：模型、Tool、應用程式與 Tool output 的完整流程](https://developers.openai.com/api/docs/guides/function-calling)
- [Responses API：等待 client-owned Tool／approval required input](https://developers.openai.com/api/reference/cli/resources/beta/subresources/responses)

### Anthropic

- [Claude Agent SDK：`AskUserQuestion` 與 `canUseTool`](https://code.claude.com/docs/en/agent-sdk/user-input)
- [Claude Tool use：client Tool 的 structured `tool_use`／`tool_result`](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)
- [Claude Structured outputs：JSON output 與 strict Tool use 的適用邊界](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)

### LangChain／LangGraph

- [LangGraph Interrupts：Tool 內 interrupt 與 `Command(resume=...)`](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangChain Structured output：`create_agent.response_format` 是 final structured response](https://docs.langchain.com/oss/python/langchain/structured-output)

## 8. G3 裁決與下一個 gate

Product Owner 於 2026-09-04 暫時核准方案 A：真正 blocking 的「需要你的確認」由模型透過專用小型 Tool 表達；Tool 內由 Runtime 使用 LangGraph `interrupt()`，員工回答後以同一 thread 的 `Command(resume=...)` 接續。普通訪談問題不呼叫此 Tool，也不從自然語言反向猜測控制意圖。

下一題 `LLM-Q009` 只研究 Tool 的最小模型輸入與 Runtime 回傳責任；先核對 framework 是否已有可直接沿用的 schema／middleware，再比較至多三個精簡方案。不先決定 UI、不要求模型填系統欄位，也不授權 production。
