# 專業顧問第一個最小完整迴圈：研究與設計

日期：2026-07-30
狀態：設計已在對話中收斂；書面規格待 owner 最終審閱

## 1. 要解決的產品缺口

`app/job_analysis` 已有 PostgreSQL Current State、完整 Task Analysis packet、一次模型呼叫、
deterministic verifier、Work Model／Proposal transition、員工 Proposal 決策與 durable reload；Local Web
也已有文件庫與 Current JD Task 編輯器。但目前沒有員工可操作的 AI 訪談入口，因此還不是「AI 專業顧問」。

這一切片只接通一個可恢復的完整迴圈：

```text
固定開場問題
  → 員工回答
  → 一次 Task Analysis 模型操作
  → Work Model／Proposal／下一題原子保存
  → 員工 accept／edit／reject／defer
  → Current JD 更新或維持
  → 關閉、重開後從同一狀態繼續
```

第一版只分析 Task；不在這一切片加入 O/P/K/S/A、公版比對或匯出。

## 2. 權威資料與對本產品的含意

### 2.1 LLM 系統設計

- OpenAI 現行 Agents 文件建議能用單一 agent 時先用；只有能力、政策、prompt 或 trace 的隔離真的改善
  系統時才拆 specialist。過早拆分會增加 prompt、trace 與 approval surface。這支持第一版維持 A6 的單一
  one-stage Task Analysis，而不是新增 Controller、多 Agent 或 Graph runtime。
- OpenAI 的 conversation state 指南要求一段對話選一種 continuation strategy；混用 application replay 與
  provider-managed state 容易重複 context。本產品繼續由 PostgreSQL、Journal 與 application packet 擁有狀態，
  不再加入 provider conversation ID。
- Anthropic 的 2025 context engineering 指引把目標定為最小而高訊號的 context，並反對把複雜、脆弱的
  判斷硬編進 prompt。第一版送完整 transcript 與必要 Current State；只有長對話真的退化時才加入
  compaction、retrieval 或 Coverage 投影。
- Anthropic 的 2026 trustworthy agents 指引要求 agent 在涉及使用者意圖或偏好的不確定性時追問，同時避免
  每個小疑點都停下來。這支持「每回合處理所有訊號，但只問一個最高資訊價值問題」。

### 2.2 專業職務分析

- iCAP《職能基準發展指引》以開放問題、追問、具體實例、責任與工作產出逐步收斂職務內容，並允許依受訪者
  回答調整順序；因此本產品不做固定問卷或 phase machine。
- OPM Job Analysis 把 Task、所需能力及其連結視為系統化分析結果；本切片先把 Task 做穩，不因後續尚有
  O/P/K/S/A 就提早建立空實體。
- O*NET 2025 emerging-task 程序仍把新陳述與既有 Task 的 duplicate／overlap／new 判斷放在 Task 更新前。
  現行 `identity_assessment` 與 Proposal 邊界因此保留。

## 3. 比較過的做法

### A. 單一自適應顧問（採用）

維持強模型、light schema、one-stage。一次呼叫讀取完整高訊號 packet，同時理解本輪 0..N 個工作訊號、
更新 Task／issue／排除項、建立必要 Proposal，並選一個下一題。

優點是沿用已完成且實際跑過的 A6 主線，最少新狀態與失效模式。限制是第一版不能機械計算 Role／Coverage
完整度；這是已知風險，不假裝已解決。

### B. 立刻新增 Role Hypothesis／Coverage／StoryFocus（暫不採）

能讓工作地圖與訪談焦點更可檢查，但目前尚無本產品失敗證據證明這三個持久實體能改善結果。它們會同步擴大
模型 schema、DB、Context、transition、API 與 UI，違反 ADR 0042「新增必須有理由」的界線。

### C. Controller + Task specialist 或 Graph workflow（不採）

可顯式路由 `broaden`／`deepen_story`／`clarify_boundary` 等動作，但會增加模型呼叫、狀態同步與錯誤傳播。
現階段所有分支使用相同模型、相同資料、相同權限，沒有 specialist isolation 的實質需要。

## 4. 顧問每回合的行為

每次員工回答後，同一次模型呼叫必須：

1. 重新閱讀完整 transcript、Current Work Model、Current JD、open issues、excluded signals 與待決 Proposal；
2. 分析本輪所有內容，不只回答上一題，產生 0..N 個 `work_signals`；
3. 區分工作成果與 Java／Python／HTML 等 enabler，不能把工具、單一步驟或他人工作直接升格成 Task；
4. 對既有 Task 執行 duplicate／overlap／no-match 與必要的 merge／split 邊界判斷；
5. 對有足夠依據的文件變更建立 Proposal，不能直接修改 Current JD；
6. 從尚未解決的問題中選一個資訊價值最高的 `next_question`。

下一題的優先順序是：

1. 更正、矛盾、本人／他人責任；
2. Task／工具／步驟與 merge／split 邊界；
3. 職位主要替誰解決什麼問題；
4. 抽象工作轉成最近一次具體故事；
5. 故事已足夠深入後，回到工作週期掃描其他工作；
6. 已有足夠支持時建立 Proposal，同時追問下一個未覆蓋缺口；
7. 看似完整時做遺漏檢查，不自動宣告訪談或 JD 完成。

這是 prompt 的決策原則，不是 application 的硬編碼 phase。平手或涉及員工意圖時追問；其他可由現有資料
可靠判斷的事項由模型先分析，避免把訪談變成逐欄問卷。

## 5. 模型輸出與持久狀態

沿用 `TaskAnalysisResult.v1`：

- `work_signals[]`
- `next_question.text`
- `next_question.purpose`
- `next_question.target?`
- `limitations[]`

不新增 `consultant_action` enum。`purpose` 是單次結果內簡短、可檢查的選題理由，不是可見 CoT；第一版不把它
升格成新的持久領域狀態。`active_question` 只持久化實際問出的 consultant turn ID 與文字，這已足以讓短答
回到原問題。若真實案例證明問題文字不足以還原語境，再另案增加 bounded QuestionContext。
既有架構中的 `broaden`、`deepen_story`、`clarify_boundary` 等名稱仍是顧問策略詞彙，不是第一版 wire 或 DB enum。

Proposal 與訪談並行：模型可以同回合建立 Proposal 並問下一個實質問題。下一題不得只是「要不要接受提案」；
accept／edit／reject／defer 由 Proposal 卡處理。Proposal 決策不清除或替換 `active_question`，所以員工可以先
繼續回答，也可以先處理提案，離開後兩者都能恢復。

## 6. 固定開場與 Journal

新文件建立時，application 在同一個 PostgreSQL transaction 內：

1. 建立空 Current Work Model 與 Current JD；
2. 產生固定 consultant turn：
   `先不用照職稱回答：你這個職位最主要替誰解決什麼問題？`
3. 寫入新的 `ConsultantOpeningPayload` Journal entry；
4. 將該 turn 設為 `active_question`；
5. commit。

開場由 application 決定性產生，不呼叫模型，也不是 AI operation。GET 必須保持 read-only，不得在第一次讀取時
偷偷補寫開場。這是開發中 greenfield 資料；不為既有開發資料寫 migration 或 lazy backfill。

Journal 最小擴充：

```text
kind: consultant_opening
schema: job-analysis-consultant-opening/1
payload: { consultant_turn }
```

`consultant_opening` 可出現在 conversation transcript，但不是 Task 的 `SourceRef`；顧問問題只能作為
`question_turn_id` 的語境，不能證明員工做過某項工作。

Repository 應提供按 Journal sequence 展開的 conversation turns；開場是一個 consultant turn，後續既有
`CompletedTurnPayload` 各展開 employee + consultant 兩個 turn。不建立第二張 chat message 表。

## 7. 一個 durable turn 的交易邊界

沿用現有兩段式流程：

1. 讀取 authority snapshot 與完整 conversation；
2. 關閉 DB transaction；
3. 交易外執行一次 LLM request；
4. parse 並跑 deterministic verifier；
5. 重鎖 document，重建 read-set；
6. generation、authority、conversation 任一已改變就拒絕 stale result；
7. 套用 transition；
8. Work Model、Proposal、completed-turn Journal、`active_question` 與 generation 同交易 commit。

不新增背景工作、SSE、polling、隱藏 retry、operation ledger 或 workflow checkpoint。此模型操作是一次短回應；
OpenAI 的 background mode 是為數分鐘級工作設計，會引入輪詢與更高 time-to-first-token，第一版沒有理由採用。

若 provider、parse 或 verifier 失敗，Current State 與 Journal 都不變；Web 保留員工草稿與同一把 idempotency key
供明確重送。若 commit 前 authority 已改變，回傳既有 `authority-conflict`，不得用舊分析覆蓋新資料。

## 8. 最小 API 與 UI

新增三個 route，沿用 `job-analysis-contract` 的 JSON Schema → Pydantic／TypeScript SSOT 與 RFC 9457 error
慣例：

- `GET /api/v1/job-analysis/documents/{document_id}/consultation`
- `POST /api/v1/job-analysis/documents/{document_id}/turns`
- `POST /api/v1/job-analysis/documents/{document_id}/proposals/{proposal_id}/decisions`

GET 投影只回 UI 需要的 conversation、active question、pending/deferred Proposal、Current JD 與文件 metadata；
Work Model、Journal payload、authority generation 與內部 ordinal mapping 不外洩。

POST turn 使用 `Idempotency-Key`。verified result 才回成功；provider refused、truncated、invalid output、transport failure
對員工統一為 `consultant-unavailable`，細節留在 server log，不讓 Web 解析錯誤字串。不存在的 Proposal 使用
`proposal-not-found`；generation/read-set 衝突沿用 `authority-conflict`。

Workspace 採單頁雙欄：左側 conversation 與 composer，右側 Proposal cards 與 Current JD Task editor；窄畫面上下
排列，不做 tab、drawer 或第二份 client store。Proposal 卡提供 accept／文字 edit／reject／defer；
`revision_requested` 尚未接 replacement path，因此第一切片不暴露。

寫入只走 client mutation → FastAPI。TanStack Query mutation variables 承載 pending/error 顯示，成功後 invalidate；
失敗時保留草稿與 idempotency key，內容改變才換 key。支援 Ctrl/Cmd+Enter 送出、Enter 換行、離站 dirty guard，
conversation 使用 `role=log`，狀態與錯誤分別使用 `role=status`／`role=alert`。

## 9. 驗證與停止線

實作計畫至少要逐層驗證：

- 新文件同交易且只建立一次固定開場；重送 metadata PUT 不重複 Journal；GET 零寫入；
- 開場 turn 可被 `active_question` 引用，第一個短答能正確連回問題；
- 一回合可同時產生多個 Task／issue／排除項及一個下一題；
- Java／Python 等工具不單獨成 Task，含工具的完整工作仍可成立；
- provider／parse／verifier／stale 失敗皆零狀態變更；成功才原子保存完整回合；
- Proposal accept／edit／reject／defer 不會遺失 active question；
- 關閉再開後 conversation、待決 Proposal、Current JD 與待回答問題一致；
- legacy API error body 不因新 route 改變；
- PostgreSQL real-adapter smoke 與真實瀏覽器 smoke 各一條，不用大量模型矩陣冒充產品驗證。

下列任一情況出現時停線回設計，不在程式裡臨場加框架：

- 必須新增 Role／Coverage／Story 持久欄位才能避免真實的遺忘或重問；
- 完整 transcript 已造成長對話品質退化，才研究 recent-window／compaction；
- 單一 operation 無法清楚承擔顧問與 Task 分析責任，才重新評估 specialist；
- 需要多步工具循環或長時間工作，才研究 Agent SDK／Graph workflow／background execution。

## 10. 明確不做

- 不整合或搬移 vNext／舊 interview 資料與程式；
- 不新增 Role Hypothesis、Coverage Map、StoryFocus、Evidence claim layer；
- 不新增 Graph runtime、多 Agent、Controller LLM、Reviewer LLM；
- 不做 streaming、background job、autosave conversation、provider-managed conversation；
- 不做 O/P/K/S/A、公版比對、完成度 gate 或匯出；
- 不為開發中舊資料做 migration／backfill；
- 不以本切片完成宣稱整個專業顧問流程已完成。

## 11. 來源

- OpenAI, [Agents SDK — Build with the SDK](https://developers.openai.com/api/docs/guides/agents#build-with-the-sdk)
- OpenAI, [Orchestration and handoffs](https://developers.openai.com/api/docs/guides/agents/orchestration)
- OpenAI, [Running agents — Choose one conversation strategy](https://developers.openai.com/api/docs/guides/agents/running-agents#choose-one-conversation-strategy)
- OpenAI, [Background mode](https://developers.openai.com/api/docs/guides/background)
- Anthropic, [Trustworthy agents in practice](https://www.anthropic.com/research/trustworthy-agents), 2026-04-09
- Anthropic, [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), 2025-09-29
- Anthropic, [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents), 2026-01-09
- 勞動力發展署 iCAP，[職能基準發展指引](https://icap.wda.gov.tw/ap/get_file.php?c=%E8%81%B7%E8%83%BD%E5%9F%BA%E6%BA%96%E7%99%BC%E5%B1%95%E6%8C%87%E5%BC%95.pdf&e=20221026143138.pdf&t=download)，2022
- U.S. OPM, [Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/)
- O*NET, [Identification of Emerging Tasks: Revised Approach](https://www.onetcenter.org/reports/EmergingTasks_RevisedApproach.html), 2025-02-25
