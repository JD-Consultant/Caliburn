# 0037. Interview AI vNext：QuestionFrame、分型 Evidence 與員工文件權威

- 狀態：Accepted（owner 於 2026-07-20 核准研究後寫成實作 authority）
- 日期：2026-07-20
- 範圍：R5 grounded short-answer、未來即時 JD 共編的最小相容 seam
- 詳細實作：[`../plans/2026-07-20-interview-vnext-v3-5a-r5-grounded-short-answer-amendment-plan.md`](../plans/2026-07-20-interview-vnext-v3-5a-r5-grounded-short-answer-amendment-plan.md)
- 研究：[`../specs/2026-07-20-interview-vnext-professional-job-analysis-and-short-answer-architecture-research.md`](../specs/2026-07-20-interview-vnext-professional-job-analysis-and-short-answer-architecture-research.md)

## 脈絡

成品的使用者是員工。員工與 AI 顧問持續對話，同時看著自己的職務說明書形成；員工可直接編輯，AI 的語意新增、
修改與刪除則必須先供員工接受、修改後採用或拒絕。第一版只處理一名員工、一次訪談與一份當下職務，不先建立 SaaS、
公司層 capability catalog、多人共編或 CRDT。

R1–R4 已把 provider binding、wire result、execution evidence、conformance、recovery 與 Capture 分開。原 R5 設計仍有
兩個產品級缺口：

1. 它只允許 current employee turn 的逐字 quote 支持 claim，因此員工回答「是」、「每週」、「主管」時，系統不知道
   回答綁在哪個問題／slot；
2. 它把「每天／每週／每月」同時當成 current time marker，會把「以前每週」錯標成現在工作。

只把完整 transcript 丟給模型猜，或放寬 quote verifier，都不能誠實表達：「命題內容來自系統剛才的問題，接受權威來自
員工這一輪的短回答」。另一方面，現有 Episode、Gap、Inference、Candidate 與 ContextBuilder 全部以 `evidence_id`
閉合。若另建與 Evidence 平行的頂層 `ContextualAssertion` collection，必須同時把整個 Job Model 改成 polymorphic
`SupportRef`；這不是 R5 所需，也會把風險擴散到尚未實作的 V3-6。

官方方向與本決策一致：OpenAI Structured Outputs 明確提醒 schema adherence 不代表內容正確；Anthropic 建議先用簡單、
可組合 workflow 與 programmatic gates，並把 context 視為每輪需策展的有限資源；Dialogflow CX 也以 active page/form
parameter 與 session state 綁定多輪 slot filling，而不是只靠自由文字歷史猜測。

## 決定

### 1. R5 是固定 workflow，不是 general agent

R5 保留一個 provider call：application 建立最小 context，模型提出 typed semantic proposals，application 再做 schema、
frame binding、quote、marker、domain 與 CAS gates。模型不得自行挑工具、改 state、產 application ID 或直接寫 JD。

若後續 eval 證明 one-call 無法達標，再以新的 operation/version 做 ablation；本 ADR 不預先加入 multi-agent、semantic
repair 或 provider memory。

### 2. 每個顧問問題都必須有 persisted `QuestionFrame.v1`

顧問訊息不只保存自然語言文字，還要在同一 reducer command 中保存 application-validated QuestionFrame。Frame 至少包含：

- exact consultant turn 與 question text hash；
- 單一 mode：open narrative、atomic confirmation、slot request、choice、correction check；
- 一個最小 semantic target（choice 的 options 嵌在同一 target）；
- immutable definition hash 與每個 target hash；
- active、consumed、superseded、stale lifecycle；
- 最多一個、且只限緊接該問題的 employee answer turn。

模型只看到 target ordinal 與必要語意，不看到／不回傳 frame、turn、Evidence 或 document domain ID。application 從持久化
frame 解 ordinal，並驗證 definition hash、target hash、scope 與 lifecycle。

### 3. v1 QuestionFrame 一次只引入一個新事實維度

`atomic_confirmation` 只能有一個 proposition target，且 `introduced_dimensions` 恰為一項。`slot_request` 只能問一個
typed slot；`choice` 只有一個 choice target；`correction_check` 必須指向 active Evidence lineage。

例如「你目前每週主要負責整理缺貨資料，對嗎？」一次引入 current、frequency、importance、ownership 四個維度，禁止
成為可短答確認的 frame。應拆成自然但小的問題。已由既有 Evidence 支持的 atom 可以保留在 proposition 中，但只有
一項尚待員工確認。

### 4. `Evidence.v3` 使用分型 support，不另建平行 assertion aggregate

R5 將 Evidence 升為 v3，共同欄位仍負責 evidence identity、claim、qualifiers、status、supersession 與 operation lineage；
證明來源改成 discriminated union：

- `literal_employee_span`：claim 直接由 employee quote/span 支持；
- `contextual_answer`：claim/value 來自已驗證 QuestionFrame target，員工權威來自 answer quote/span，並保存 frame
  definition hash、target hash、binding kind 與 resolution。

這保留兩種證明強度的型別差異，但仍讓 Episode、Gap、Inference 與 Candidate 只引用 `evidence_id`。任何 consumer 都必須
先查看 `support_kind`；不得把 contextual answer 的「是」顯示成完整 claim 的逐字 quote。

研究 Revision 4 建議的平行 `ContextualAssertion.v1` 因本次 code audit 被此決策取代。不是放棄 composite provenance，
而是把它封裝進 Evidence 的明確 union，避免在 R5 重寫整個 support graph。

### 5. 短答 binding 與 literal observation 可在同一 call 共存

`TurnInterpretOutput.v2` 分成：

- `answer_bindings`：affirm／deny／slot value／choice；
- `literal_observations`：current employee turn 中可逐字支持的新工作事實；
- `dialogue_act`、`episode_signal`、emergent topics 與 insufficiency codes。

「是，但月底還會做一份報告」可同時形成一筆 contextual Evidence 與一筆 literal Evidence。兩條路徑各自 partial accept；
其中一條失敗不會修補或污染另一條。模型產生的 ordinal 只是本次 output reference，真正 UUID 由 application 以 operation
ID 和原始位置派生。

### 6. 每個成功解讀的 employee turn 都保存 interpretation receipt

R5 不再用「有 Evidence 才 `ApplyEvidence`，零 Evidence 就 generic no-op」表示結果。新的
`ApplyTurnInterpretationCommand.v1` 在一個 state transition 中保存：

- accepted Evidence（可為空）；
- `TurnInterpretationRecord.v1`；
- QuestionFrame consumed transition（若有 eligible frame）；
- deterministic domain events。

因此 dont-know、decline、stop、off-topic、ambiguous 與完全被 verifier drop 的成功回合都可重播、可稽核，且同一 employee
turn 不會被解讀兩次。provider／conformance／operation failure 不建立 receipt；它們由 typed terminal failure 保存。generic
no-op contract 保留給其他 operation，但不再是 turn interpretation 的成功載體。

### 7. Context snapshot 必須含 state version；stale result 不自動 rebase

Context identity 升版並保存 `state_version + state_hash`。provider call 期間只要 state 前進，舊 context 的 commit 就以
`state_context_stale` 終止該 operation，不套用到最新 state，也不自動重解 ordinal。caller 使用新 operation ID 從最新
state 重建 context。

這個規則刻意嚴格。它先保護目前的訪談 commands，也保護下一階段員工在文件區直接編輯時，不讓同時返回的 AI 結果
覆蓋或誤解員工剛做的修改。日後若有數據證明需要更高併發，再另設 source-level revalidation，不在 R5 猜測安全 rebase。

### 8. frequency 與 time scope 是兩個獨立維度

每天、每週、每月、每季、每年只支持 `frequency`。只有明確「目前／現在／現階段／當前」等 marker 才支持
`time_scope=current`。

- 「以前每週」＝ past + per_week；
- 「每週」＝ unknown time + per_week；
- 「現在每週」＝ current + per_week。

contextual confirmation 只有在 QuestionFrame 唯一 introduced dimension 就是 current 時，才能由「是」接受 currentness。

### 9. 員工是文件 authority；R5 不依賴 editor

員工 direct edit 在未來 Authoring Core 中立即成為 current draft truth。AI 的任何語意 edit 都先形成 proposal，由員工
選「符合我的工作／修改後採用／不符合」。R5 不 import editor component、document JSON path、Qdrant、OCS 或 Web state。

本 ADR 只凍結兩個 future seam：

1. Question Policy 可讀 bounded、versioned `JobStateDigest`，再產 QuestionFrame；Turn Interpreter 本身不讀 digest；
2. Authoring Core 若修改到 active frame 的 target/source，必須送 `InvalidateQuestionFrameCommand.v1`，使舊 frame stale。

因此現有 editor 可保留、包裝或替換，不會改變 R5 的 grounding contract。

### 10. 不新增 SQL migration 0011

QuestionFrame、Evidence v3 與 interpretation receipts 都存在 `InterviewState.v3` 的 canonical `state_json`；0010 已保存
state JSON、schema version/hash、commands、artifacts、events、checkpoint 與 manifest，不需新 table/column。

因 vNext 尚無 production route／production state，active runtime hard cut 到 v3；舊 JSON schemas 留作 frozen history。
持久層遇到 `interview_state.v2` 必須回明確 `UnsupportedPersistedSchemaVersion`，不得把合法舊資料誤報 corruption，也不得
偷偷 dual-read 或產 0011。測試／eval DB 可依既有 tenant-scoped cleanup 重建。

### 11. Provider boundary 不變

OpenRouter 仍是第一個 provider adapter，OpenAI 只保留 mocked reference。R5 只更新 output schema/hash 與對應 fixtures；
不得改 exact routing、retry、cache、pipeline、conformance 或 SDK/HTTP 行為，也不得跑 paid live。

## 被否決的選項

### 把完整聊天歷史交給模型自由猜「是」在回答什麼

無法 deterministic 驗證 expiry、target 或 concurrent edit，且 context 越長越容易混入舊問題。

### 把問題中的完整命題當成 employee quote

會偽造 provenance。「是」只證明員工接受已持久化的命題，不是該命題的逐字來源。

### 永遠要求員工重說完整句

可以維持 literal-only 精度，但會讓訪談變長且不自然，不符合產品目標。

### 建立獨立 `ContextualAssertion` collection 並立即改造所有 `SupportRef`

語意上正確，但現有 79 個左右的 evidence linkage consumer 都要改成 union，擴大 R5 blast radius。Evidence v3 的
discriminated support 已保留同等 provenance，又能沿用 evidence graph。

### 讓模型輸出 frame／Evidence UUID

模型不應管理 application identity。ordinal 由 context 投影，UUID 由 application 派生。

### 每輪都把完整 JD／editor state送進 Turn Interpreter

R5 不需要它，會增加注意力污染與 UI coupling。文件狀態只影響 Question Policy，並以 bounded digest 傳遞。

### 為 QuestionFrame 建新資料表

0010 的 canonical state JSON 與 event/artifact authority 已足夠；新 table 只增加 migration 與同步風險。

## 後果

- 短回答自然度提升，但不犧牲 provenance；
- contextual 與 literal evidence 仍可由型別明確區分；
- 每輪都有 durable receipt，zero-evidence 不再消失於 generic no-op；
- strict CAS 會讓同時編輯時偶爾需要重新執行一個 turn，但不會把舊推論套到新文件；
- R5 會機械遷移現有 domain/eval fixtures，工作量比原母計畫 R5 大，但可避免 R5 後立刻重構；
- R6 仍負責真正的多 trial、短回答品質與 model comparison，不把 mocked contract test 當品質結論；
- 共編、JD synthesis、K/S 與 export 仍是後續 vertical slices，不得混入 R5。

## Supersession

- 修正 ADR 0036 §6：correction target 也改用 context ordinal；模型不再接觸 opaque Evidence ID。
- 擴充 ADR 0036 §9：Context/Capture 保留，但 context identity 升版並納入 QuestionFrame/state version。
- 部分取代 ADR 0030：保留單一 conversation owner、AI 不可靜默改文件與 employee review；`_pending` 不再被視為
  canonical proposal store，「人改完不告知模型」由 bounded JobStateDigest feedback loop 取代。
- 不改 ADR 0035 的 OpenRouter-first provider boundary。

## 來源

- OpenAI, [Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- OpenAI, [Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
- Anthropic, [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- Anthropic, [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- Anthropic, [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- Anthropic, [Introducing Anthropic Interviewer](https://www.anthropic.com/research/anthropic-interviewer)
- Google Cloud, [Dialogflow CX Parameters](https://docs.cloud.google.com/dialogflow/cx/docs/concept/parameter)
