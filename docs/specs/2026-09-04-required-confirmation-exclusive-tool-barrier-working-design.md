# 必要確認的 Exclusive Tool Barrier（Working Design）

- 日期：2026-09-04
- Topic ID：`LLM-Q011`
- 階段：PAUSED；父前提已由 `LLM-Q011` 重開
- 父決策：`LLM-Q005`～`LLM-Q010`
- 效力：只決定同一 model step 中 confirmation 與其他 Tool calls 的執行邊界；不授權 middleware、provider 參數、schema、UI、測試或 production

> 2026-09-04 重驗：Product Owner 指出模型可在 final output 詢問員工，且員工可能不回答或改談別題。這使「訪談澄清必須是 durable interrupt」的父前提尚未成立。本文件保留為方案歷史，不再是 current blocking question；目前請讀 [`2026-09-04-conversational-question-vs-durable-interrupt-revalidation.md`](2026-09-04-conversational-question-vs-durable-interrupt-revalidation.md)。

## 1. 本輪唯一問題

若模型同一個 model step 產生兩個以上 confirmation calls，或把 confirmation 與 Memory／JD／其他 Tool call 放進同一批，第一版應如何保證「先取得員工答案，答案回來前不執行同批其他動作」？

## 2. 為何現在必須決定

`LLM-Q009` 已採一個 Tool、一次一題，但 schema 只能限制**每次 call 裡**有一題，不能限制模型在同一 response 產生幾次 call。LangChain 也明確提醒模型可平行呼叫多個 Tools；若其中一個 Tool interrupt、其他 Tool 同時執行，可能在員工回答前產生 read／write effect，違反 confirmation 的 blocker 語意。

本題只管一個 model response 的 Tool batch，不限制整個 invocation：模型仍可先查 Memory，取得結果後在下一個 model step 單獨提出 confirmation；員工回答並 resume 後，也可繼續使用其他 Tools。

## 3. 官方事實

### F1．OpenAI 與 Anthropic 都提供「每個 response 最多一個 Tool call」控制

OpenAI 說明模型可在同一 turn 產生多個 function calls；`parallel_tool_calls: false` 可限制為零或一個 Tool call。Anthropic 也提供 `disable_parallel_tool_use: true`：搭配預設 `tool_choice: auto` 時，每個 response 最多一個 Tool call，仍可直接回普通文字。

兩家 API 的參數名稱與支援矩陣不同，而且這些都是 **request-level** 設定：一旦關閉平行呼叫，該 response 的所有 Tools 都受限制，不能只針對尚未產生的 confirmation call。故「可限制零或一 call」是共同能力方向，卻不能直接當成 confirmation-only 的選擇性安全機制。

### F2．LangChain 預設必須考慮平行 Tool calls

LangChain Tools 文件明確指出 LLM 可平行呼叫多個 Tools，涉及 state update 時須考慮 concurrent conflicts；多個 Tool calls 會先執行並各自產生 `ToolMessage`。因此只把 `interrupt()` 寫進 confirmation Tool，不能自行證明同批其他 Tool 不會執行。

### F3．LangChain middleware 提供執行前後的驗證 seam

LangChain middleware 可在每次 model response 後執行 `after_model`，官方列出的用途包含 validation；`wrap_model_call` 也能控制 handler 是否重試。這是可用來檢查 model Tool batch、阻止無效批次進入 Tool execution 的 framework seam，不必另包第二套 agent loop。

### F4．LangGraph 能處理多 interrupts，但不代表產品應採用

LangGraph 支援平行 branches 同時 interrupt，並以 interrupt ID 到 resume value 的 map 恢復。它證明 framework 不會無法表示多問題，但這會要求多問題 UI、答案配對與更複雜恢復；與 `LLM-Q009` 已核准的一次一題不符。能做不等於第一版應做。

## 4. 三個方案

| 方案 | 作法 | 優點 | 主要問題 |
|---|---|---|---|
| **A．Exclusive barrier＋Runtime guard（建議）** | prompt／Tool description 要求 confirmation 單獨呼叫；Runtime 在 Tool execution 前驗證整批，confirmation 若非唯一 call 就整批零執行，交回可修正錯誤並依既有 bounded repair 重試 | 員工回答前零同批副作用；不依賴 provider 特有參數；正常路徑沒有額外 model call；沿用 LangChain middleware | 需一個很薄的 batch guard；具體 middleware API 留待 implementation contract 驗證 |
| B．只用 provider serial setting | OpenAI／Anthropic 各自關閉平行 Tool calls，不另加 Runtime guard | 程式最少 | provider／gateway 不一定都支援；Caliburn 已有 OpenRouter capability routing 失敗證據；若設定未生效就沒有安全後盾，且會全域犧牲其他獨立 Tool 的平行能力 |
| C．接受多 confirmation／混合批次 | 使用 LangGraph 多 interrupts，或讓其他 Tool 與 confirmation 一起執行 | 完整利用 framework 的平行能力 | 違反一次一題；員工答案前可能有副作用；UI、resume mapping、錯誤與審核複雜度明顯增加，產品沒有此需求 |

## 5. 建議 A 的精確語意

### 5.1 Exclusive 是「每個 model step」，不是「整個 invocation」

- 同一 assistant response 若包含 confirmation，該 response 只能有這一個 Tool call；
- 前一個 model step 已完成的純讀取 Tool 不回滾；
- confirmation interrupt 後，本次 invocation 停在 durable checkpoint；
- 員工回答並 resume 後，模型可以在後續 step 繼續查詢或提出變更；
- 一般彼此獨立、沒有 confirmation 的 read-only Tools 是否允許平行，留給 provider capability／Tool effect 題決定，不被本題全域禁止。

### 5.2 兩層各自負責什麼

1. **Instruction**：要求 confirmation 必須單獨呼叫，降低違規機率；不把提示當安全保證。
2. **Runtime/framework guard**：在 Tool 執行前檢查 model response。若有多個 confirmation，或 confirmation 與任何其他 Tool 混合，整批 Tool 都不執行。

第二層是 Caliburn 對已核准「一次一題、先回答才安全繼續」的最薄 deterministic mapping；不是 OpenAI、Anthropic 或 LangChain 的內建產品政策。

OpenAI／Anthropic 的 request-level serial setting 保留為 provider capability：若未來整個 agent step 本來就應全面序列化，可採用；本題不為了 confirmation 每輪強制開啟，也不把它當安全正確性的必要條件。

### 5.3 違規如何恢復

- 這是模型可修正的 Tool protocol／policy error，沿用 `LLM-Q005` 的 bounded repair 類別；
- 錯誤只告訴模型：confirmation 必須是本 step 唯一 Tool call，請保留最重要的一題並重新輸出；
- 不執行同批任何 Tool、不自行挑第一題、不把多題排隊、不顯示給員工；
- 達到既有 invocation repair 上限後，依 `LLM-Q005` 進入明確可理解的 limit／failure，不無限重試。

精確 ToolMessage 形狀、middleware hook 與 retry 次數是後續 implementation contract；本題不先發明。

## 6. 成本、效果與複雜度

- 正常路徑：沒有額外 model call；只有一次常數時間 batch 檢查。
- 只有模型真的輸出違規批次時才增加一次 bounded repair 的成本。
- 相較多 interrupts／排隊，A 不增加新的持久 queue、資料表、UI mode 或第二個 agent。
- 不宜只為 confirmation 全域禁止其他 read-only Tool 的平行化；exclusive 限制只在包含 confirmation 的 model step 生效。

## 7. 建議裁決

建議暫時採方案 A：把 confirmation 定義為 **exclusive barrier**。模型呼叫它時必須單獨呼叫；Runtime 在執行前作 deterministic batch guard。違規批次零執行並交回 bounded repair，不讓任何同批 Tool 在員工回答前先執行。provider 的 request-level serial setting 不作必要條件。

這個組合不是跨廠逐字標準；官方共識 primitive 是 typed Tool lifecycle、可選的 request-level serial control、middleware validation 與 durable interrupt。Exclusive barrier 是為了實現 Caliburn 已核准的一題一確認與零未授權副作用。

若核准，下一個 gate `LLM-Q012` 才定義最小、非大型 eval 的代表性情境與 pass／fail；本題仍不施工。

## 8. 重開條件

- Runtime guard 無法在 Tool execution 前可靠攔截違規批次；
- LangChain agent loop 改變，model response 與 Tool execution 間沒有 validation seam；
- 真實需求需要一次呈現多個互相獨立的 blockers；
- 代表性 characterization 證明 exclusive barrier 造成不可接受的延遲或漏失；
- Product Owner 改變一次一題或員工答案前零同批副作用的要求。

## 9. 官方來源

### OpenAI

- [Function calling：parallel function calling、Tool choice 與 strict mode](https://developers.openai.com/api/docs/guides/function-calling)

### Anthropic

- [Parallel tool use：`disable_parallel_tool_use` 的零或一 Tool call 行為](https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use)
- [Tool use overview：auto Tool choice 與單一 Tool call 範例](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)

### LangChain／LangGraph

- [LangChain Tools：平行 Tool calls、state update 與 ToolMessage lifecycle](https://docs.langchain.com/oss/python/langchain/tools)
- [LangChain Custom middleware：`after_model` validation 與 `wrap_model_call` control](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- [LangGraph Interrupts：單一與多個 interrupts 的 resume 語意](https://docs.langchain.com/oss/python/langgraph/interrupts)
