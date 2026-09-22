# Interview AI vNext：下一題選擇、Context Engine 與最小顧問迴圈研究

- 狀態：accepted implementation research
- 日期：2026-07-23
- 產品範圍：本機 Web、單一員工、單一職務說明書
- 上位決策：[ADR 0038](../adr/0038-interview-vnext-context-engine-and-professional-consultant-workflow.md)
- 實作計畫：[2026-07-23 question.select plan](../plans/2026-07-23-interview-vnext-question-select-context-loop-plan.md)

## 1. 這一步要解決的產品問題

R5 已能把員工回答轉成有來源的 Evidence，Authoring Core 已能保存 task／output 並讓員工接受、修改或拒絕 AI proposal；
目前缺少的是兩者之間的顧問決策：

1. 員工剛回答完，系統下一題應該問什麼；
2. 哪些缺口值得追問、哪些不值得把訪談拖長；
3. 問題如何保留足夠上下文，讓「是、每天、給財務」這種短回答仍可正確解讀；
4. 如何讓訪談知道文件已有什麼，避免重複問員工已經編輯或接受的內容。

這不是單純生成一句問題。它是第一個真正把 Prompt Engineering、Context Engineering、Harness Engineering、
Loop Engineering 與既有 domain state 串起來的產品切片。

## 2. 2026 現行官方做法核對

### 2.1 Prompt：以 outcome、證據邊界與完成條件為中心

OpenAI 2026 現行 GPT-5.6 prompt guidance 建議先寫清楚 outcome、重要限制、可用證據與完成標準，刪除重複規則與不相關
工具；需要自主性的工作也要明訂停止條件與 approval boundary。這支持本 operation 的精簡 prompt：模型只負責從候選缺口
選一個並寫出自然問題，不負責建立事實、修改文件或決定任意後續流程。

來源：

- [OpenAI — GPT-5.6 prompt guidance](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)
- [OpenAI — Upgrading to GPT-5.6](https://developers.openai.com/api/docs/guides/upgrading-to-gpt-5p6-sol)
- [OpenAI — Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

模型版本指南不等於 provider 選型指令。本專案仍維持 provider-neutral contract 與 OpenRouter-first runtime；任何模型升級都要用
本 operation 的 eval 比較，不以「更新」兩字直接換模型。

### 2.2 Context：每輪只策展最小高訊號狀態

Anthropic 把 context engineering 定義為每一步策展最小、最高訊號的 token 集合，並指出更大的 context window 不能消除
context rot。OpenAI 的 conversation state 也只是傳輸／延續能力，不應取代應用程式可驗證的業務狀態。

因此 `question.select` 不讀完整 transcript、完整 editor JSON 或全部公版，只讀：

- application 產生的少量 candidate gaps；
- active episode 與必要 Evidence；
- bounded、deterministic `JobStateDigest`；
- 最近一個員工 turn 與必要的最近 consultant question；
- 明確的 interview budget／finish signals。

來源：

- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [OpenAI — Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)

### 2.3 Harness：schema 不是語意正確性

Structured Output 只能保證形狀，不能保證選到存在的 gap、沒有重問、問題真的能建立合法 QuestionFrame。application 必須再做：

- selected ordinal 範圍驗證；
- action 與 agenda 狀態相容性驗證；
- 問題文字非空、不是最近問題的重複；
- application-owned QuestionFrame target materialization；
- reducer／domain invariant 驗證。

測試先覆蓋最有產品風險的路徑，不追求所有排列：

1. 沒有 active episode 時能自然探索主要工作；
2. 有 action、缺 output 時優先追問 output；
3. 模型選不存在的 ordinal 時 fail closed；
4. 已有同樣 output 時不重複產生該缺口；
5. 產生的問題可被 reducer 保存成 QuestionFrame，下一輪短回答能綁定。

來源：

- [OpenAI — Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- [Anthropic — Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)

### 2.4 Loop／Graph：固定 workflow，模型只做語意節點

Anthropic 仍建議對可明確拆解的工作先用 simple composable workflow；Microsoft Agent Framework 也把 workflow 用在有已知步驟、
gate 與責任邊界的流程。此產品的 mutation、人工決策與完成權威都已知，沒有理由把 graph control 交給模型。

本階段的 loop：

```text
employee turn
  -> turn.interpret
  -> committed Evidence / receipt
  -> deterministic Agenda/Sufficiency
  -> build_question_select context
  -> question.select
  -> local verify + materialize command plan
  -> append consultant question + persisted QuestionFrame
```

Graph 目前就是這個 application state machine，不引入 LangGraph、多 Agent handoff 或 provider-owned memory。日後有
`episode.code` 時只是在明確條件下加入一個節點，不改變 domain authority。

來源：

- [Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- [Microsoft — Agent Framework workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/workflows)

## 3. 最小架構裁決

### 3.1 Agenda/Sufficiency 是純函式投影

不新增 Agenda 資料表，也不建立 planner agent。`build_question_agenda(state, job_digest)` 從 committed state 產生：

- active episode identity；
- 最多三個可選 candidate gaps；
- 是否允許 broad coverage；
- 是否可 offer finish；
- decision reasons 與固定排序。

同一份 state + digest 必須產生相同 agenda。模型不能新增 candidate gap，只能以 operation-local ordinal 選擇。

第一版只主動合成最高價值、最常見的缺口：

1. active episode 沒有 current employee action：補 action；
2. 有 action但沒有 output：補 output；
3. 有 action但沒有 purpose：補 purpose；
4. persisted open/deferred gap：依 priority 排序；
5. 沒有 active episode：broaden coverage。

不做完整欄位問卷。frequency、tool、ownership、standard、exception 只有已存在 gap 或後續品質 eval 證明值得時才問。
每個 episode 預設只追一至兩個高價值缺口，避免訪談過長。

### 3.2 `question.select` 的權限

模型可輸出：

- 一句簡短 acknowledgement；
- action：`ask_gap | broaden_coverage | offer_finish`；
- `selected_gap_ordinal`；
- 一個非複合、容易回答的問題。

模型不可輸出 UUID、Evidence、QuestionFrame target、command、JD mutation、K/S、hidden rationale 或工具呼叫。

### 3.3 QuestionFrame 由 application 建立

model 只選 gap 與寫問題。application 依已知 gap dimension 建 target：

- `output_recipient` 缺 output：`slot_request(output)`；
- `purpose`：`slot_request(purpose)`；
- 其餘第一版無法安全形成 slot 的 gap：`open_narrative`。

source ref、hash、turn／frame／command identity 都由 application 產生。如此模型不能用一段自然文字偷偷定義短回答要綁到
哪個事實。

### 3.4 JobStateDigest 的角色

`JobStateDigest` 是已接受文件的 deterministic bounded projection。它幫 question policy 知道目前 task/output 已有什麼，
但不把 pending proposal 當 truth，也不把完整 editor state塞進 prompt。本切片直接接受已建立的 digest，不新增查詢服務、
資料表或第二份摘要。

### 3.5 Provider 與持久化邊界

本切片先完成 provider-neutral contract、ContextBuilder、prompt、local verifier 與 scripted vertical。它不：

- 建 production OpenRouter composition；
- 新增 migration；
- 修改現有 provider adapter；
- 建通用 workflow framework；
- 執行 paid live。

下一切片才把同一份 `OperationSpec + Context + portable schema` 接進已驗證的 OpenRouter adapter／durable executor。

## 4. 明確不採用

- 一個 prompt 同時 interpret、選題、寫 JD；
- 每回合把完整 transcript／文件／公版全部送入模型；
- 讓模型自由建立 gap ID、Evidence 或 QuestionFrame target；
- 以模型自己的「已完成」宣告取代 application sufficiency；
- 為三個固定分支先導入 graph framework／multi-agent；
- provider conversation memory 作為唯一上下文；
- 為了形式完整而先做 K/S、匯出、SaaS、多租戶或權限。

## 5. 成功標準

完成後，scripted model 能在真 domain reducer 上走完：

```text
已解讀員工回答
  -> Agenda 發現「有 action、缺 output」
  -> question.select 選該 gap
  -> 顯示「了解，你會核對異常。這項工作最後會產出什麼？」
  -> 保存 QuestionFrame(slot=output)
  -> 員工下一輪只答「異常清單」時，R5 有合法 frame 可正確綁定
```

這代表最小顧問 loop 的「選題與提問」核心成立；不代表模型品質、production provider 或完整產品已完成。
