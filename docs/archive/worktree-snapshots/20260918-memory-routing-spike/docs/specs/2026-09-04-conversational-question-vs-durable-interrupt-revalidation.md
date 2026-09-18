# 員工提問與 Durable Interrupt 的生命週期重驗（Working Design）

- 日期：2026-09-04
- Topic ID：`LLM-Q011`
- 階段：G3；Product Owner 已於 2026-09-04 核准方案 C
- 重開原因：Product Owner 指出模型本來就能在 final output 詢問員工；若員工不回答，既有設計沒有說明 durable pause 的額外價值與後續生命週期
- 影響範圍：重驗 `LLM-Q007`～`LLM-Q010` 中「員工澄清必須使用 Tool＋interrupt」的部分；不改 production、Accepted ADR、Memory、JD 審核或錯誤分類

## 1. 本輪唯一問題

當模型能安全地先停止相依分析，於本輪 final output 詢問員工時，Caliburn 應把它視為：

1. 已完成的正常對話回合；還是
2. 尚未完成、必須以同一 logical invocation resume 的 durable interrupt？

這不是 UI 是否顯示選項卡的問題；同一張卡可以承載正常回合或 interrupt。真正差異是：員工若不回答，Runtime 是否仍有一個 pending invocation，以及下一則一般訊息能否自然開始新回合。

## 2. 官方事實

### F1．OpenAI 區分已完成 conversation 與尚待 required input 的 continuation

Responses API 的 `conversation` 會在 response 完成後，把本輪 input／output 自動加入 conversation；`previous_response_id` 也用來建立一般 multi-turn conversation。

另一方面，Responses WebSocket 對尚缺 client-owned Tool result 或 approval decision 的 response 會發出 `response.steer.pending`，reason 是 `waiting_for_required_input`；應用程式必須補齊 `required_input`，再用相同 parent 建立明確 continuation。這直接證明 OpenAI 將「正常完成後的下一輪」與「仍缺特定輸入的 continuation」分成兩條生命週期。

OpenAI 這份公開契約直接列出的 `required_input` 是 Tool result／approval 等 client-owned input；它**沒有**規定所有 conversational clarification 都必須走 required-input continuation。

OpenAI 最新 model guidance 另建議：答案可能改變結果時提出聚焦問題；但在詢問核准前，先完成已獲授權且能使結果具體可審的工作，並避免不必要的 approval pause。這支持「需要問問題」與「Runtime 必須保留 pending continuation」不能畫上等號。

### F2．Anthropic 明確把兩條生命週期分開

Claude Agent SDK 同時有：

- normal conversation turn：Claude 完成本輪，等待下一則訊息；
- Tool permission／`AskUserQuestion`：callback 暫停目前執行，直到應用程式回傳結果；可能無限期等待，也可 defer 後由 persisted session 恢復。

`AskUserQuestion` 適用於 agent 正在執行一個任務、遇到多個有效做法且需要方向；官方也允許使用者不選既定選項，而改以 free-form response 回覆或改變方向。這證明 Anthropic **提供** in-run clarification，但不代表所有 assistant 問句都必須使用它。

Anthropic Managed Agents 也把自然 `end_turn` 與 `requires_action` 分開：前者可照常用下一則 `user.message` 繼續；後者保存待解的 Tool result／confirmation，所有 blocking events 解決後才回到 running。

### F3．Google 的 workflow 同時允許「索取資訊」與「核准」暫停

Gemini Enterprise Workflow Builder 明確提供兩種 HITL step：

- `Request info`：workflow 缺少額外資訊或澄清、無法繼續時暫停；
- `Approval`：下游 action 前需要人員審核／簽核時暫停。

因此，把 durable pause 限定成「只能等待 Tool approval」並不符合 Google 的公開產品契約。這份證據只適用於**已定義的 workflow run**，不能反推所有一般聊天問句都應暫停。

### F4．LangGraph 的 interrupt 是「未完成 execution」primitive

LangGraph `interrupt()` 會保存 graph state 並無限等待，必須以相同 thread 的 `Command(resume=...)` 恢復；一般 multi-turn conversation 則傳普通 input dict。官方常見用途是 critical action approval、review/edit、Tool call review 與需要在下一 workflow step 前取得的有效輸入。

若使用者在一個 active run 尚未結束時又送新訊息，LangSmith Deployment 另有 enqueue／reject／interrupt／rollback 等 double-texting policy。這些政策正是 durable pending run 額外帶來的生命週期問題；不是一般已完成回合必須承擔的成本。

### F5．Microsoft 也區分一般互動與 workflow request

Microsoft Agent Framework 指出，互動式 handoff 中 agent 回覆後，控制權回到使用者，支援正常多輪對話；只有 workflow executor 確實需要外部 response 才用 `RequestPort` 暫停，checkpoint 才保存 pending request。Tool approval 同樣走 request／response pause。

## 3. 跨廠共同邊界

可從官方資料成立的共識是：

| 情況 | 生命週期 | 員工不回答時 |
|---|---|---|
| 模型可以安全停止相依工作，只是在回答末尾詢問 | **normal completion** | 沒有 pending run；員工可關閉、改談別題或之後再回答 |
| 一個已定義的 workflow 尚未完成，下一步必須取得特定外部輸入 | **durable external-input request** | 保存 continuation identity／state；產品必須定義 resume、cancel、redirect 或 abandon |

共同點不是「問題一定不 pause」，也不是「只有 Tool action 才 pause」，而是：

1. **已完成的對話回合**與**等待外部輸入後要接續的未完成 workflow**是不同生命週期。
2. 只有後者需要 continuation identity、持久 state 與明確 resume。
3. 若可能等待很久，待決 workflow 必須能持久保存，而不能只靠記憶體 callback。
4. pending workflow 收到另一則訊息時，產品必須選擇 queue、reject、redirect／interrupt、rollback、cancel 或其他明確政策。
5. 選項卡、自由文字、問題重要程度與是否使用 Tool，**都不能單獨決定**生命週期。

官方資料沒有形成以下跨廠共識：

- 哪些 clarification 必須 durable pause；
- clarification 應由模型呼叫 question Tool，還是由固定 workflow node 發出；
- 使用者忽略問題或改談別題時應採 cancel、redirect、queue 還是保留 pending；
- 一般自然對話是否值得建立 durable request-info workflow。

因此，判斷標準應是：**產品是否真的存在一個尚未完成、收到答案後必須自動接續的既定 workflow**。這是官方共同責任邊界；哪些 Caliburn 情境符合，仍是產品推論，不能冒充廠商共同規格。

## 4. 直接回答 Caliburn 情境

### 4.1 LLM output 已經可以問問題，pause 還有什麼意義？

只有當**本輪仍有一個明確、未完成的 workflow，且取得答案後要沿原 continuation 自動執行下一步**時，durable pause 才有額外價值，例如：

- 即將送出、刪除或執行不可逆 Tool action，等待 approve／reject；
- 外部 Tool call 已建立且必須把 result 配回特定 call ID；
- 固定 workflow 已走到 request-info step，下一步必須收到有效值才能繼續。

對 Caliburn 第一版的**暫時產品推論**是：自然訪談通常可停止相依判斷、不猜答案、在 final output 問員工，然後安全結束本輪；下一則員工訊息再啟動新 invocation。這種情況保存的是 conversation／Memory 中的未確定語意，而不是一個尚未完成的 runtime invocation。

但若日後產品加入「取得答案後必須自動回到某個固定節點繼續」的 workflow，request-info interrupt 就可能合理。這兩種情況不能因為畫面都顯示問題卡而混為一談。

### 4.2 員工不選選項、改傳別的訊息怎麼辦？

若採 normal completion，建議讓問題卡**不鎖聊天室**，並保留自由文字：

- 點選選項：下一則普通 employee message 帶入該答案；
- 自由輸入：當普通訊息處理，模型判斷它是否已直接或間接回答；
- 改談別題／關頁：正常允許，沒有 pending run 需要處理。

若新訊息沒有解決原不確定性，舊 run 已經完成，不會自動再次執行。缺少的事實若仍與後續判斷相關，就仍是未確定；系統不應基於它產生確定結論。何時重問、是否換問法、是否在最終完整檢查前再問，是 Caliburn 尚待設計的 conversational policy，不是上述框架自動提供的跨廠標準。

### 4.3 若使用 durable interrupt，而員工不回答或改談別題會怎樣？

- LangGraph run 會一直 pending，直到收到 `Command(resume=...)`；
- OpenAI required input 需要配回對應 Tool result／approval，再建立 continuation；
- Anthropic callback 可無限期 pending，Managed Agents 的 `requires_action` 必須先解決 blocking events；
- Google workflow 會停在 `Needs Review`；
- 產品必須另外定義 dismiss 是 answer、deny、cancel、abandon、redirect 還是 enqueue 新訊息。

框架只提供 pause／resume primitive，不會替 Caliburn 決定「忽略問題」的產品語意。因此，在沒有明確 unfinished workflow 時採 interrupt，會增加 pending lifecycle；是否值得，必須以具體產品流程證明，不能只因問題重要。

### 4.4 下一輪會不會又遇到同一個問題？

這取決於缺少的事實是否仍與下一輪工作相關，不取決於前一輪有沒有 interrupt：

- 若員工回答了，下一輪應以新資訊分析；
- 若員工改談無關主題，可以先處理新主題；
- 若下一步仍依賴該資訊，就仍不能猜，應再確認或停止那部分判斷；
- 若產品要求答案後自動接續原 workflow，才需要 durable continuation。

保存未解問題屬 conversation／Semantic Memory 設計；保存未完成 execution 屬 runtime interrupt。兩者可以同時存在，但不是同一件事。

## 5. 三個方案

| 方案 | 作法 | 優點 | 代價／風險 |
|---|---|---|---|
| A．模型決定何時使用 question Tool／interrupt | 模型呼叫專用 Tool，員工回答後 resume 原 run | 能承接 Anthropic `AskUserQuestion` 類型的 in-run clarification | 模型也在決定 runtime lifecycle；仍須定義忽略、改題、取消、stale、double texting，容易把自然訪談變成表單 workflow |
| B．所有員工問題 normal completion | 模型在 final output 問；下一訊息永遠是新 run | 最符合自然訪談；無 pending lifecycle | 未來若加入真正待核准 action，仍需另建 approval path |
| **C．由 Runtime 明確宣告 unfinished workflow（建議）** | 訪談問題預設 normal completion；只有產品事先定義、答案後須自動接續同一 workflow 的 external-input request 才 durable interrupt。它可包含 request-info、approval 或 Tool result | 符合各家對 completed turn／unfinished workflow 的責任分界；不把「問題重要」誤當 pending execution | 必須明確列出哪些產品 workflow 符合；若第一版沒有，就不向模型暴露 ask-user interrupt Tool |

對 Caliburn 第一版而言，目前尚未證明任何自然訪談情境必須在取得回答後 resume 原 invocation。每則員工訊息本來就可啟動下一個有界 run，模型也能停止依賴未知資訊的 JD 變更。因此，方案 C 在訪談問題上目前實際等同 B；若後續找到代表性 unfinished workflow，再逐項加入 interrupt，而不是先做一個由模型任意觸發的通用 pending channel。

這段是依 Caliburn 產品情境作出的**可推翻推論**，不是「所有大廠都選 C」。Anthropic 與 Google 的公開設計證明 A／durable request-info 也可能正確；差別在產品是否真的要保留並接續同一 workflow。

## 6. 若採方案 C，對既有決策的影響

- `LLM-Q004`：保留「每則員工訊息一個有界 invocation」；只有明確 unfinished workflow 才可能 resume。
- `LLM-Q005`：保留 completion／retry／failure／external-input pending 分類，但 clarification 不再因名稱或重要性自動映射 interrupt。
- `LLM-Q006`：保留普通問題不阻塞；將「目前 operation 無安全完成點」改以是否存在答案後須自動接續的 unfinished workflow 判定。它可能是 request-info、approval 或 Tool result，不能限縮成只有 Tool action。
- `LLM-Q007`～`LLM-Q010`：訪談澄清的 interrupt、專用 Tool、最小 schema、trigger instruction 與 exclusive barrier 全部暫停；若未來確認有 explicit unfinished workflow，再依該 workflow 的 continuation、輸入與取消語意重新設計。
- UI：仍可有「需要你的確認」卡、選項與自訂回答；它是正常 assistant output 的呈現，不代表 Runtime pending。

## 7. 建議裁決

建議採方案 C：

> 員工訪談問題預設以 normal assistant completion 結束本輪，問題卡不因問題本身而鎖住聊天室。只有產品／Runtime 明確宣告「目前 workflow 尚未完成，取得特定外部輸入後必須自動接續」時，才建立 durable interrupt；它可用於 request-info、approval 或 Tool result。第一版若找不到這種代表性 workflow，就不向模型暴露通用 ask-user interrupt Tool。

這是 Caliburn 的暫時建議，不冒充跨廠共同選型，也不先決定問題卡 JSON、問題數、重問演算法、UI 樣式或未來 approval Tool。

## 8. 重開條件

- 代表性情境證明 normal completion 無法保留或找回影響 JD 的不確定性；
- 第一版加入取得外部輸入後必須自動接續同一 workflow 的代表性 request-info、approval 或 Tool result；
- 員工下一則訊息無法安全區分一般新輸入與 pending external-input response；
- OpenAI／Anthropic／Google／LangGraph／Microsoft 的公開生命週期契約改變；
- Product Owner 改變自然訪談、不鎖聊天室或 JD 待審語意。

## 9. 官方來源

### OpenAI

- [Responses API：conversation 在 response 完成後收錄本輪 input／output，`previous_response_id` 建立 multi-turn conversation](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- [Responses WebSocket：`waiting_for_required_input`、required Tool／approval input 與明確 continuation](https://developers.openai.com/api/reference/cli/resources/beta/subresources/responses)
- [OpenAI 最新 model guidance：聚焦澄清、完成已授權工作及避免不必要 approval pause](https://developers.openai.com/api/docs/guides/latest-model)

### Anthropic

- [Claude Agent SDK：normal turn 與 Tool／AskUserQuestion pause 的明確分界](https://code.claude.com/docs/en/agent-sdk/user-input)
- [Managed Agents event stream：`end_turn`、`requires_action` 與 pending Tool events](https://platform.claude.com/docs/en/managed-agents/events-and-streaming)

### Google

- [Gemini Enterprise Workflow Builder HITL：`Request info` 與 `Approval` 都能暫停既定 workflow](https://docs.cloud.google.com/gemini/enterprise/docs/workflow-builder/use-hitl-steps)

### LangChain／LangGraph

- [LangGraph Interrupts：durable wait、`Command(resume=...)` 與一般 multi-turn input 分界](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangSmith Double texting：active run 收到新輸入時的 enqueue／reject／interrupt／rollback](https://docs.langchain.com/langsmith/double-texting)

### Microsoft

- [Microsoft Agent Framework HITL：interactive handoff 與 workflow RequestPort／approval pause 分界](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop)

## 10. Closure

```text
Decision / finding:
  官方共同邊界是 completed conversation turn 與 explicit unfinished workflow continuation 分離。
  Clarification 可以是 normal turn，也可以是 durable request-info；是否 pause 取決於是否有答案後必須自動接續的既定 workflow，不能只看問題重要程度或是否使用 Tool。
Status:
  G3 complete；Product Owner 已核准方案 C。
Why:
  Caliburn 目前尚未證明自然訪談需要保留原 invocation；預設 normal completion 較貼合無限期訪談。這是產品推論，不是廠商共同選型。
Affected artifacts:
  LLM-Q006～LLM-Q011；其中 Q007～Q010 的 pause-specific mapping 暫停。
Next gate:
  進入 LLM-Q012：確認第一版是否存在任何明確 unfinished workflow；沒有就撤回訪談用 ask-user interrupt Tool，再研究 normal-turn question output 的最小 contract；不施工。
```
