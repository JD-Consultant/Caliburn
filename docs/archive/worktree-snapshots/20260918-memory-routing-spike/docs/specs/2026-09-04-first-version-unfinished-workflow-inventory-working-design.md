# 第一版 Unfinished Workflow 情境盤點（Working Design）

- 日期：2026-09-04
- Topic ID：`LLM-Q012`
- 階段：G3 complete；Product Owner 已於 2026-09-04 核准方案 B
- 父決策：`LLM-Q011` 已採方案 C——訪談問題預設 normal completion，只有答案後必須自動接續同一個既定 workflow 時才 durable interrupt
- 效力：只盤點第一版是否存在這種 workflow；不修改 production、Accepted ADR、Tool、schema、API 或 UI

## 1. 本輪唯一問題

第一版 Caliburn 是否有任何代表性情境符合以下全部條件：

1. 目前已有一個尚未完成的 workflow；
2. workflow 缺少特定員工／外部輸入便不能前進或安全結束；
3. 收到該輸入後，系統必須自動接續原 workflow，而不是開始下一個正常訪談回合或執行一個獨立 application command；
4. 因此必須保存 resumable run state，而不只是保存「仍待釐清的語意問題」。

「問題很重要」「畫面使用問題卡」「員工最好先回答」或「模型呼叫了一個 Tool」都不足以單獨成立 durable interrupt。

## 2. 官方生命週期判準

### F1．一般多輪對話與未完成 run 是不同生命週期

OpenAI Responses API 會在 response 完成後，把本輪 input／output 加進 conversation；下一則訊息可透過同一 conversation 或 `previous_response_id` 開始下一個 response。OpenAI 的 required-input continuation 則明確對應尚待 client 提供的 Tool result 或 approval decision。

Anthropic 也明確區分兩者：normal conversation turn 是 Claude 完成本輪後等待下一則訊息；`AskUserQuestion`／Tool permission 才會令目前 execution 暫停，直到 callback 回覆或 session 日後恢復。

這支持「等待下一則自然對話」與「保存未完成執行」必須分開建模。

### F2．Request-info 可以合理 interrupt，但前提是它位於一個既定 workflow 中

Google Workflow Builder 的 `Request info` 會暫停 workflow，官方用途是 workflow 需要額外資訊或澄清才能繼續。Microsoft Agent Framework 的 `RequestPort` 同樣由 executor 發出 request，外部回覆後由框架把 response 路由回原 executor；其 interactive handoff 則在 agent 正常回覆後把控制權交還使用者，下一則輸入屬一般多輪互動。

因此，clarification **可以**採 durable request-info，但官方資料沒有說所有聊天中的重要問題都應如此處理。是否 pause 取決於產品是否真的有待接續的 workflow。

### F3．Interrupt／HITL 的價值在「決定後仍有既定工作要執行」

LangGraph `interrupt()` 會保存 state、無限期等待，再以相同 thread 的 `Command(resume=...)` 回到被中斷 node；一般 multi-turn conversation 則應傳入 plain input，而不是拿 `Command(resume=...)` 代替下一則訊息。

OpenAI Agents SDK 與 LangChain HITL middleware 的典型流程都是：模型先產生尚未執行的敏感 Tool call，系統暫停，員工 approve／edit／reject 後，原 run 再執行或拒絕該 Tool，並繼續後續模型步驟。這種「決定後仍要執行原 action／run」正是 durable interrupt 的明確收益。

### F4．以上不是「各家都禁止聊天澄清 interrupt」

Anthropic `AskUserQuestion` 與 Google `Request info` 已證明，澄清也可以成為未完成 workflow。跨廠共同點只到：

- 正常完成的對話回合，和
- 等待特定外部輸入後繼續的未完成 workflow

必須分開。第一版 Caliburn 是否具有後者，是本文件的產品盤點與推論，不是廠商替 Caliburn 做出的答案。

## 3. 第一版產品情境 inventory

| 第一版情境 | 員工輸入前已有什麼 | 員工輸入後應發生什麼 | 必須接續原 unfinished workflow？ | 判定 |
|---|---|---|---|---|
| 一般深入訪談問題 | 前一個 model run 已可保存理解／缺口並完成回覆 | 員工自由回答、改談別題或稍後回來；新訊息啟動下一個 bounded invocation | 否 | normal completion |
| 工作內容有歧義、矛盾或缺少只能由員工提供的事實 | 可先保存目前理解、矛盾與尚未確定的部分；停止依賴未知事實的 JD 變更 | 下一則員工訊息作為新來源，由新 invocation 更新理解並重新判斷 | 否 | normal completion；問題重要度不創造 pending run |
| 員工沒有回答上一題，先補充別的工作 | 上一題是仍待釐清的語意狀態，不是半執行中的 action | 新 invocation 先吸收當前訊息；尚未解決的問題仍可由 Memory／conversation 找回 | 否 | normal completion |
| AI 已編輯 working JD，等待員工接受／修改／拒絕 | AI run 已完成 workspace mutation 與驗證；差異可持久存在 | 員工日後用 typed review command 改變 approved JD 或撤回差異 | 否 | document review lifecycle，不是 model-run interrupt |
| 員工直接編輯 JD | 沒有待執行的模型 action | deterministic authority command 立即寫入員工內容；下個 model run 才讀取最新狀態 | 否 | application command |
| 員工用聊天方式更正先前說法 | 舊對話、目前理解與 JD 狀態都已保存 | 更正作為一般新訊息進下一個 bounded invocation，由模型依上下文修正理解 | 否 | normal completion；不需要「更正原話」專用 resume |
| 刪除文件／高影響結構刪除 | 員工正在操作 UI／application command | UI 可先確認，再執行或取消 deterministic command | 否 | application confirmation；沒有待續 LLM run |
| 有 readiness gap 時強制匯出 | export request 已能 deterministic 回報缺口 | 員工確認後以 `force=true` 發出新的 deterministic export request | 否 | HTTP/application confirmation，不是 agent interrupt |
| 模型填錯 Tool 參數、找不到項目或 workspace 不合法 | 同一 bounded run 仍在執行 | Tool 回傳可修正錯誤，由模型在 call limit 內修正；達限才成為明確失敗 | 否，員工不是修復者 | Tool error／bounded retry |
| 暫時性 provider／基礎設施失敗 | run 因技術錯誤停止 | 依 allowlist 重試，或保存明確 failed outcome 供員工重試同一來源 | 否 | retry／failure lifecycle |
| 第一版 Memory、Skill、來源與 working-JD Tool 使用 | model run 內的讀寫與驗證 | Tool result 在同一 run 回給模型；不需員工提供外部結果 | 否 | 一般 agent Tool loop |
| 未來傳送郵件、發布、付費、外部系統寫入或其他高影響 action | 尚未執行且已形成具體 Tool call | 員工決定後執行／取消原 action，再繼續 run | 可能是 | 官方 HITL 的典型情境，但不在第一版產品範圍 |
| 未來固定多步 workflow 的 request-info | 固定流程已走到某節點，答案決定後續既定節點 | 回答須路由回原 executor／node 並自動繼續 | 可能是 | 只有加入具體 workflow 後才成立；第一版目前沒有 |

盤點結果：**目前找不到第一版代表性情境需要員工回答後自動接續同一個未完成 workflow。**

## 4. 現行 required clarification 的實際行為

這一節只記錄目前 branch 的 code fact，不把現行 code 當成新產品方向。

1. Provider structured output 目前有 `question.kind=required_clarification`，模型還要填 `current_understanding`、`choices`、`affected_work_ids`、`affected_branch` 等欄位（`apps/api/app/consultant/model_output.py`）。
2. semantic commit 建立 `RequiredClarification` 並把相關 interview work 標成 blocked（`apps/api/app/consultant/interview.py`、`clarification.py`）。
3. graph 在每個 command 後進入 `required_clarification` node；有 request 時呼叫 `interrupt()`（`apps/api/app/consultant/graph.py`）。
4. 員工透過獨立 clarification API 回答；Runtime 保存回答來源並以 `Command(resume=...)` 恢復（`apps/api/app/adapters/langgraph/postgres.py`、`apps/api/app/api/routes/consultant.py`）。
5. resume 後的 node 只解除 blocker、清除 `required_clarification` 並到 `END`；clarification API 沒有啟動 `ConsultantTurnProcessor` 或新的 model analysis。也就是說，答案雖被保存，**並不會在這次 resume 中自動被模型吸收並接續分析**。

第 5 點很重要：現行機制付出了 interrupt state、專用 model schema、專用 API／UI 與 answer lifecycle 的成本，卻沒有實現官方 HITL 典型的「取得決定後接著執行原 action／workflow」。它更像是用 interrupt 保存一個待釐清 domain state。

這不表示 LangGraph interrupt 不成熟；表示目前產品情境與目前 continuation 不需要、也沒有真正利用它的 resumable-execution 語意。

## 5. 與現行 Accepted authority 的衝突

Accepted ADR 0060 與現行 design／code 明確保留 required-clarification interrupt：

- ADR 0060 §4、§5 決定 11 把來源衝突、重大責任邊界及員工專屬事實映射到 `interrupt`／`Command(resume)`；
- `docs/design/consultant-runtime.md` 把 required clarification 納入 agent output、checkpoint state、API 與 Web projection；
- production code 已實作上一節的 lifecycle。

因此，即使 Product Owner 採用本文件建議，也**不能只改研究稿或直接刪 code**。必須先開 successor ADR，明確取代 ADR 0060 的 required-clarification 部分，再完成 G4 contract、垂直實作與驗收。ADR 0060 其他 authority、workspace review、Memory、Tool 與 approved JD 規則不因本題自動改變。

## 6. 方案

| 方案 | 做法 | 優點 | 代價／問題 |
|---|---|---|---|
| A．保留現行通用 required-clarification interrupt | 模型可把重要歧義輸出成專用 request；員工走專用 API resume | 已有 code；可呈現選項卡 | 沒有具體 unfinished workflow；resume 不接續 model analysis；模型 schema、API、UI、stale／取消／改談別題生命週期皆增加複雜度 |
| **B．第一版沒有 employee-input unfinished workflow（建議）** | 所有訪談問句都作為 normal completion；員工所有文字走同一一般回答入口。未解歧義保存為 conversation／Semantic Memory 狀態；JD review 與其他確認各走自己的 application command。LangGraph interrupt capability不必移除依賴，但第一版不建立模型可觸發的 ask-user interrupt path | 符合目前產品的自然長訪談；減少模型欄位與錯誤面；員工可回答、改題或關閉；每則回答都會啟動正常 analysis；保留未來真正需要 interrupt 時再精準加入的空間 | 與 ADR 0060／現行 code 衝突，須 successor ADR 與受控 migration；後續仍要決定 normal-turn question 的最小 output contract |
| C．重做一個真的會續跑的 clarification workflow | 明確固定某一流程節點；答案後 resume 並自動再次執行模型／Tool，直到該 workflow 完成 | 真正利用 durable interrupt；適合未來固定 request-info workflow | 第一版目前沒有可命名場景；會先增加 workflow、取消、改題、timeout／stale 與 double-texting 語意，屬無需求的預先設計 |

## 7. 建議裁決

建議採 **方案 B**：

> 第一版 Caliburn 沒有員工輸入型 unfinished workflow。所有訪談問題，包括重要歧義與矛盾澄清，都以正常 assistant completion 結束；員工的下一則文字是新的 bounded invocation。影響後續分析的不確定性保存在 conversation／Semantic Memory，而不是保存為 pending execution。AI JD 審核、員工 direct edit、刪除及匯出確認維持各自的 application lifecycle，不拿通用 ask-user interrupt Tool 承接。LangGraph 的 interrupt 能力仍可在未來具體 workflow 出現時使用，但第一版不向模型暴露、也不建立專用 clarification API／state／UI。

這是根據官方共同生命週期邊界與 Caliburn 第一版情境作出的產品推論；不是「OpenAI、Anthropic、Google 都禁止 request-info interrupt」。

Product Owner 於 2026-09-04 明確回覆「同意」，核准方案 B。這項 Working Decision 約束後續研究與 G4 設計，但在 successor ADR 通過並完成對應實作前，不取代 Accepted ADR 0060 或現行 production code。

## 8. 採 B 後的下一個 gate

1. 將 `LLM-Q007`～`LLM-Q010` 的訪談 interrupt／Tool／schema／trigger 路線標為 **SUPERSEDED for first-version interview**，保留作未來 explicit workflow 的歷史研究。
2. 開 successor ADR，精確取代 ADR 0060 中 required-clarification interrupt 的決定；沒有 successor ADR 前，production 仍依現行 authority。
3. G4 只定義 normal-turn question 的最小產品 contract，以及未解歧義如何進入既有 conversation／Semantic Memory；不先設計選項數、卡片樣式或重問演算法。
4. 之後以一個小型垂直切片移除專用 required-clarification output/state/API/UI，驗證：重要矛盾會被保存、相依 JD 變更不會亂做、聊天室不被鎖住、下一則一般回答能正常被模型吸收。

## 9. 重開條件

- 第一版加入明確的外部高影響 Tool action，必須由員工決定後再執行；
- 加入固定多步 workflow，能具體指出被中斷節點、期望輸入及 answer 後自動執行的下一步；
- normal completion 實測無法可靠保留或找回影響 JD 的未解歧義；
- 產品要求 employee answer 必須延續同一 run 的中間推理／Tool result，而不是新 run 重建 context；
- 官方 Runtime lifecycle 契約或 Product Owner 的自然訪談方向改變。

## 10. 官方來源

### OpenAI

- [Responses API：conversation 與 `previous_response_id` 的正常多輪生命週期](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- [Responses required input：尚待 Tool result／approval decision 的明確 continuation](https://developers.openai.com/api/reference/cli/resources/beta/subresources/responses)
- [OpenAI Agents SDK HITL：敏感 Tool approval、可序列化 `RunState` 與恢復原 run](https://openai.github.io/openai-agents-python/human_in_the_loop/)

### Anthropic

- [Claude Agent SDK：normal turn 與 Tool／`AskUserQuestion` pause 的分界](https://code.claude.com/docs/en/agent-sdk/user-input)

### Google

- [Gemini Enterprise Workflow Builder：`Request info`／`Approval` 都是 workflow pause step](https://docs.cloud.google.com/gemini/enterprise/docs/workflow-builder/use-hitl-steps)

### LangChain／LangGraph

- [LangGraph Interrupts：pause、checkpoint、`Command(resume=...)` 與 plain multi-turn input](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangChain HITL middleware：Tool call 在執行前 approve／edit／reject，再 resume agent](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)

### Microsoft

- [Agent Framework HITL：workflow `RequestPort` 與 interactive handoff 的生命週期分界](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop)

## 11. Closure

```text
Decision / finding:
  第一版情境 inventory 找不到任何員工輸入後必須自動接續同一 unfinished workflow 的代表性需求。
  現行 required-clarification resume 只清除 blocker 後結束，沒有自動接續 model analysis。
  建議方案 B：訪談問題全部 normal completion；不建立第一版 ask-user interrupt path。
Status:
  G3 complete；Product Owner 已核准方案 B，尚未改變 production authority。
Why:
  官方共同邊界要求區分 completed turn 與 unfinished workflow；Caliburn 的自然訪談、JD review、direct edit、export／delete confirmation、retry 與 Tool repair 都能安全完成或有獨立 application lifecycle。
Affected artifacts:
  LLM-Q006～LLM-Q012；方案 B 已核准，但仍須 successor ADR 取代 ADR 0060 的 required-clarification 部分後才能施工。
Next gate:
  G4 定義 normal-turn question 的最小 contract 與 required-clarification 的受控替換設計；其後開 successor ADR。現在仍不修改 Tool、schema、API、UI 或 production code。
```
