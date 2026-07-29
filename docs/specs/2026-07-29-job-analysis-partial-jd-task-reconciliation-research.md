# Job Analysis：不完整 JD Task 與同一 identity 對齊研究

- 日期：2026-07-29
- 狀態：設計已由 owner 口頭核准，待書面複核；尚未進入 ADR／plan／實作
- 範圍：員工直接新增或編輯 Current JD Task 後，第一版 Task Analysis 如何保留空白、追問缺口，
  並把後續分析對回同一個 Task
- 不在範圍：O/P/K/S/A 契約、Web UI、匯出、公版排版、版本歷史、通用 workflow／Graph framework

## 1. 問題與產品需求

員工是 Current JD 的文件權威，因此必須能：

- 只輸入一個任務名稱或簡短描述就保存；
- 讓目的、情境、頻率、責任角色、工具及未來 O/P/K/S/A 暫時留空；
- 隨時回來修改、刪除或排序；
- 不因為欄位未填滿而被 AI 或 schema 擋住；
- 之後透過訪談慢慢補齊，而不是由 AI 猜出空白內容。

現行 `JdTaskFields` 已接近這個需求：只有 `statement` 必填且不可為空，
`purpose_result`、`context`、`frequency_text`、`responsibility_role` 可空，
`enablers` 可為空陣列。第一版把 UI 所稱的「任務名稱／描述」對應到 `statement`；
不為了暫時留白再新增 `title`、`completeness` 或逐欄狀態。

真正缺口是 identity：

1. `add_jd_task()` 已為直接新增的 JD Task 配發 stable `task_id`；
2. 為避免偽造 `action`／`object`／支持來源，它不會立即建立假的 Work Model Task；
3. 現行只留下 `OpenIssue(id="direct-task-{task_id}")`；
4. 後續模型若分析出 Task，`transition._add()` 會另產生 `operation_id-tN`；
5. 因此同一件工作可能在 Current JD 與 Work Model 取得兩個 identity。

把 `task_id` 藏在 `OpenIssue.id` 字串裡再解析，不是契約；用文字相似度找回舊 ID 也會在換句話說、
同名 Task 或 merge／split 時失效。

## 2. 外部權威核對

### 2.1 應用程式擁有產品狀態與決策

OpenAI Agents SDK 現行文件把「state storage」與「approval decisions」列為 application/server
的責任；SDK 負責 agent loop，不取代產品資料真相。這支持 Caliburn 繼續由 application 保存
Current JD、Work Model、提案與恢復狀態，而不是把 identity 交給模型或 provider。

來源：

- [OpenAI — Agents SDK: Build with the SDK](https://developers.openai.com/api/docs/guides/agents#build-with-the-sdk)

### 2.2 員工編輯立即成立，AI 的文件改動仍須審查

OpenAI 把「edits」列為應在 side effect 前暫停、交由 human-in-the-loop approval 的動作之一。
套到本產品：

- 員工自己的直接編輯不是 AI side effect，應立即保存；
- AI 後續若想改 Current JD 文字，必須另產生 Proposal；
- Work Model 對齊不得偷偷覆寫員工文件。

來源：

- [OpenAI — Guardrails and human review: Choose the right control](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals#choose-the-right-control)

### 2.3 不確定就追問，不替員工補造

Anthropic 2026 的 trustworthy-agents 指引要求在偏好、意圖或不確定資訊只有使用者能決定時，
模型應停下來澄清，而不是自行假設；同時要在「每件事都停」與「永遠硬做」之間校準。
因此不完整 Task 是合法狀態：資訊不足時留在 open issue、一次問一題；不能因為 output schema
需要欄位就硬填。

來源：

- [Anthropic — Trustworthy agents in practice](https://www.anthropic.com/research/trustworthy-agents)

### 2.4 Context 只補必要訊號

Anthropic 2025 的 Context Engineering 指引主張使用最小、最高訊號的 context，並避免把 brittle
logic 或多餘抽象塞進 prompt。這裡只需要讓模型看到「這個 open issue 對應哪一筆 JD Task，
目前員工寫了什麼、哪些欄位仍空白」；不需要新增 literal-claim layer、embedding、通用
reconciliation engine 或另一份 Current JD 鏡像。

來源：

- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

## 3. 比較過的方案

### 3.1 方案 A：直接建立不完整 Work Model Task

作法：員工新增 JD Task 時，同時建立同 ID 的 Work Model Task，缺的 `action`／`object` 用 placeholder
或從短文字猜出來。

否決：

- 目前 Work Model Task 的 `statement`／`action`／`object` 必填；
- 「報表」「Java」這類輸入無法可靠推出完整 Task；
- placeholder 會污染後續 identity、merge／split 與 prompt；
- 猜值違反「員工沒說的不能當成現況事實」。

### 3.2 方案 B：日後用文字相似度找回 identity

作法：模型建立新 Task 後，application 用 statement 相似度與 JD-only Task 配對。

否決：

- 同義改寫、同名 Task、工具名稱及一段文字含多工作都會產生不穩定配對；
- 相似度閾值是隱藏語意決策，員工無法理解或修正；
- merge／split 不是一對一文字比對；
- identity 錯配比保留 open issue 更危險。

### 3.3 方案 C：OpenIssue 明確持有 reconciliation target（採用）

作法：

- Current JD Task 建立時立即取得 stable `task_id`；
- Work Model 暫不建立假 Task；
- 對應的 OpenIssue 明確保存 `reconciliation_task_id`；
- Context Packet 把該 JD Task 的目前欄位投影到這筆 issue；
- 模型的每條 work signal 可明確指認它正在解決哪一筆 existing open issue；
- application 驗證後，沿用 `reconciliation_task_id` 建立 Work Model Task。

優點是 identity 明確、可驗證、可恢復；成本只是一個 nullable domain reference 與一個 nullable
output ordinal，不新增資料表或服務。

## 4. 核准設計

### 4.1 Current JD 的留白規則

第一版員工直接建立 JD Task 時：

| 欄位 | 規則 |
|---|---|
| `statement` | 唯一必填；UI 可稱「任務名稱／描述」 |
| `purpose_result` | 可空 |
| `context` | 可空 |
| `frequency_text` | 可空 |
| `responsibility_role` | 可空 |
| `enablers[]` | 可為空 |
| 未來 O/P/K/S/A | 可空；不在本切片預建 schema |

空白表示「員工尚未提供」，不是 validation failure，也不是授權 AI 補造。Current JD 可照常保存、
reload、編輯、刪除與排序。

### 4.2 JD-only Task 的持久表示

`OpenIssue` 增加一個 nullable 的 `reconciliation_task_id`：

- 只有直接新增、尚未形成 Work Model Task 的 issue 會帶值；
- 值必須指向 Current JD 中存在的 Task；
- 直接編輯同一筆 JD-only Task 時，保留同一 `task_id`，用最新 JD 內容與 direct-edit anchor
  更新這筆 issue；
- 直接刪除時，移除 issue，不建立假的 retirement；
- 不再從 `OpenIssue.id` 字串解析 identity。

這個欄位是 Work Model 的待釐清關聯，不是新 Task、Proposal 或 Evidence entity。

### 4.3 Context Packet

現有三區段不改。`open_issues` 中若 issue 帶 `reconciliation_task_id`，額外顯示：

- 此 issue 對應一筆尚未完成分析的 Current JD Task；
- JD Task 目前的 `statement` 與非空欄位；
- 哪些可選欄位仍為空；
- issue 的 source anchors 與 `last_asked_turn_id`。

不把 JD-only Task 偽裝成 active Work Model Task，也不給它 active Task ordinal。模型只能透過
open-issue ordinal 指認它。

當 `next_question.target` 指向 existing open issue 時，application 在保存顧問問題的同一個
authority 更新中，把該顧問 `turn_id` 寫入 `OpenIssue.last_asked_turn_id`。現有
`ActiveQuestion` 不再新增第二個 target 欄位；問題與 issue 的關係可由 `last_asked_turn_id`
可靠還原。

### 4.4 模型輸出與驗證

`WorkSignal` 增加 nullable `resolves_open_issue_ordinal`。第一版只允許兩種終結：

1. `task_change.add`：資料已足以形成一個 Task；
2. `exclude`：已能判定它是他人工作、過去工作、一次性支援、純工具／步驟或員工否認。

資訊不足、責任不明、Task 邊界不明時不得填這個欄位；保留原 issue，並讓
`next_question.target` 繼續指向它。

deterministic verifier 檢查：

- ordinal 必須指向帶 `reconciliation_task_id` 的 existing open issue；
- 同一筆 issue 在一個 result 中最多被解決一次；
- `task_change.add` 仍須提供完整、可 parse 的 Work Model `TaskFields`；
- `exclude` 必須帶合法理由；
- `support_only`、`revise`、`withdraw`、`merge`、`split` 不得用這個欄位；
- target JD Task 在 authority snapshot 中仍存在且內容未變；
- target ID 不得已存在於 Work Model。

「語意是否足以形成 Task」「是否真的是工具或步驟」仍屬 rubric／模型判斷，不偷渡進 verifier。

### 4.5 Application transition

#### 成為 Task

若 signal 是合法的 `task_change.add + resolves_open_issue_ordinal`：

1. application 解析 issue；
2. 使用 issue 的 `reconciliation_task_id`，不產生 `operation_id-tN`；
3. 建立 Work Model Task；
4. 支持來源包含 issue 既有 direct-edit anchor，加上本輪 employee-turn anchors；
5. 移除該 issue；
6. Current JD 保持原樣；
7. 若 Work Model 建議文字／欄位與 Current JD 不同，建立普通 `revise` Proposal，等員工決定；
   不直接補入空欄位。

這讓「員工先寫一行 → 訪談補資訊 → AI 理解同一件工作」保持同一個 Task identity。

#### 判定不是 Task

若 signal 是合法的 `exclude + resolves_open_issue_ordinal`：

1. 建立或更新 `ExcludedSignal`；
2. 移除該 issue；
3. Work Model 不建立 Task；
4. Current JD 仍不被 AI 靜默刪除；
5. application 建立一筆員工可見的 withdraw Proposal，讓員工確認是否從 JD 移除。

因此員工直接輸入「Java」「幫同事一次」不會被硬升格成 Task，也不會被 AI 偷刪。

### 4.6 後續直接編輯

- 編輯已存在的 Work Model／JD 同 ID Task：沿用現行 `pending_reconciliation` 路徑；
- 編輯 JD-only Task：更新同一 open issue，不換 ID；
- 刪除 JD-only Task：立即刪 JD 與 issue；
- 刪除已存在的 Work Model Task：JD 立即依員工命令刪除，Work Model 走現行 reconcile／retire
  邊界，不讓 AI 自動加回；
- 所有員工操作仍由 application 寫入 Journal；按儲存不呼叫 LLM。

UI 不必顯示 `pending_reconciliation`、open-issue ID 或 Work Model 狀態。員工只看到自己的文件、
顧問問題與需要決定的 AI Proposal。

## 5. 可恢復性與錯誤處理

- OpenIssue 與 `last_asked_turn_id` 已位於持久 Work Model JSONB；
- Current JD Task 已是 relational row；
- 顧問／員工回合與 direct edit 已在 Journal；
- Proposal 已有持久表。

所以不新增資料表即可在關閉後恢復：

```text
員工新增不完整 Task
  → Current JD 立即保存
  → OpenIssue 記住 reconciliation_task_id
  → 關閉／重開
  → AI 看到同一筆 issue 與 JD Task
  → 資訊不足：問一題並記 last_asked_turn_id
  → 資訊足夠：同 ID 建立 Work Model Task
  → 若建議改善 JD：另建 Proposal
```

若模型結果到達前，員工又改了該 JD Task，既有 authority snapshot／generation 保護使舊結果
失效；application 不會拿舊分析覆寫新文字。

## 6. 最小驗證

只測會改變產品真相的路徑：

1. 只有 `statement` 的 JD Task 可新增、保存、reload；
2. 其他現有可選欄位全空仍合法；
3. JD-only Task 在 packet 中只以 open issue 呈現，不冒充 active Task；
4. 對同一 issue 的回答建立 Work Model Task 時沿用原 `task_id`；
5. 不足時保留 issue，送出問題後保存 `last_asked_turn_id`；
6. 模型重複解決同一 issue、引用錯 ordinal、target 已不存在或已進 Work Model時拒絕；
7. AI 建議內容不同時只建立 Proposal，Current JD 不變；
8. 判定是工具／步驟時建立 withdraw Proposal，不直接刪 JD；
9. 員工在模型執行期間修改 target 時，舊結果 stale；
10. 關閉重開後仍能從同一 issue 與同一 Task identity 繼續。

不新增大型矩陣、真實 API 實驗、資料搬遷或 Web 測試。這一切片只證明 identity 與權威流程，
不宣稱 Prompt 或模型品質已完成。

## 7. 明確不做

- 不建立空殼 Work Model Task；
- 不新增 `draft/completeness/status` 狀態機；
- 不逐欄記 provenance；
- 不用 embedding 或文字相似度配對 identity；
- 不新增 reconciliation table、revision、checkpoint、hash chain；
- 不在儲存時呼叫 LLM；
- 不在本切片加入 O/P/K/S/A 欄位；
- 不接 Web；
- 不復用或整合 `interview_vnext`。

## 8. 後續文件順序

書面複核通過後：

1. 新增 ADR，鎖定「partial JD 是合法狀態、explicit reconciliation identity、AI 不補造／不靜默改 JD」；
2. 寫一份 bite-size plan；
3. 以 TDD 修改 contract → verifier → context → transition → durable reload；
4. focused tests 綠後再討論 Local Web。

