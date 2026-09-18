# 0046. 專業顧問第一個最小 durable Task 訪談迴圈

- 狀態：Accepted
- 日期：2026-07-30
- 補充：[0040](0040-professional-consultant-engine-and-r1-validation-contract.md)、
  [0042](0042-r1-screening-stop-and-a6-first-version-default.md)、
  [0043](0043-job-analysis-local-current-state-persistence-and-authoring-authority.md)、
  [0045](0045-job-analysis-local-web-contract-and-shared-authority-commit.md)
- 研究：
  [專業顧問第一個最小完整迴圈](../specs/2026-07-30-professional-consultant-minimal-complete-loop-research.md)

## 脈絡

`job_analysis` 已接通 Task Analysis、PostgreSQL Current State、Proposal 決策與人工 Current JD editor，
但 Local Web 還沒有 AI 訪談入口。顧問最終流程要求彈性訪談、每回合全域理解、一段回答可含多項工作、
工具不得直接升格為 Task、Proposal 與訪談可並行，且關閉後能從同一狀態恢復。

目前沒有真實失敗證據支持先加入 Role／Coverage／Story 持久實體、Controller、多 Agent、Graph runtime、
streaming 或背景工作。反方審查另發現：若 idempotency replay 只在現有 commit 階段判定，相同 turn 重送仍會
再次付費呼叫模型；若 Consultation View 只回待決 Proposal，Web 又無法呈現已決／stale 歷史。

## 決定

- 第一版沿用 A6：強模型、light schema、one-stage、full harness。一次操作理解本輪全部工作訊號、更新
  Work Model／issue／排除項、建立必要 Proposal，並選一個最高資訊價值下一題。
- 不新增持久 `ConsultantAction`、Role Hypothesis、Coverage Map 或 StoryFocus。`broaden`、
  `deepen_story`、`clarify_boundary` 等保留為 prompt 的顧問策略詞彙；實際輸出沿用
  `TaskAnalysisResult.v1` 與 `next_question`。
- 每份新 document 在建立交易中決定性寫入固定 consultant opening Journal entry，並設為
  `active_question`；不呼叫模型。GET 保持 read-only；metadata rename 不碰 opening、Journal 或
  `authority_generation`。開發中舊資料不 migration／backfill。
- Conversation state 繼續由 application 的 PostgreSQL Current State、Journal 與 Context Packet 擁有；
  不混用 provider conversation ID。第一版送完整 transcript，不做 compaction／retrieval。
- 新增三個薄 route：Consultation View、提交 employee turn、提交 Proposal decision。兩個 POST 都要求
  `Idempotency-Key`；它是業界慣例，不宣稱為 RFC。
- Turn use case 必須在 provider call 前查 committed Journal replay：同 key／同 payload 直接回目前 view，
  不再呼叫模型；同 key／不同 payload 回 idempotency conflict。第一版不建 pending-operation ledger，
  因此只承諾已提交請求的循序重送，不宣稱 concurrent in-flight exactly-once；Web pending 時停用重送。
- Verified turn 仍採 snapshot → 交易外一次 provider call → verifier → 重鎖與 read-set/generation 檢查 →
  Work Model、Proposal、completed-turn Journal、下一題同交易 commit。任何 provider、parse、verifier 或
  stale failure 都不改 Current State。
- Consultation View 回 conversation、active question、全部 Proposal、Current JD 與 metadata；UI 將
  pending/deferred 與 terminal/stale 分組。第一版本機資料不做 Proposal pagination。
- Proposal 與下一題並行；下一題不得只是要求接受提案。Web 第一版提供 accept／文字 edit／reject／defer，
  不暴露尚未接 replacement path 的 `revision_requested`。
- Local Web 維持單文件雙欄：conversation/composer 與 Proposal/Current JD editor。寫入只有 Client mutation
  → FastAPI；不加 Server Actions、第二份 client store、streaming、polling 或 autosave conversation。
- 第一版沒有 completion gate。模型只能做遺漏檢查，不能宣稱職務分析、OPKS 或 JD 已完整完成。

## 後果

正面：

- 以最少新契約接通真正可用、可恢復的 AI Task 訪談，不重建已完成的 durable engine。
- 固定開場與短答 provenance 有一致持久來源；Proposal 決策不會吃掉待回答問題。
- replay 在付費呼叫前短路，循序重送不重複花費，也不重複 Journal。

成本：

- Journal 增加一種 opening payload；契約 #4 增加 Consultation／turn／decision DTO 與兩種 Problem type。
- prompt 必須承擔顧問選題；A6 先前結果不等於已證明下一題品質。

風險：

- 無 Role／Coverage 狀態可能在長訪談中遺忘或重問；出現真實失敗後才升級 R2，不先加表。
- 完整 transcript 終將有 context 壓力；沒有實際退化前不設定任意 window。
- 同時飛行的相同 POST 可能各自呼叫 provider；單機 UI 先以 pending guard 收斂，不能宣稱 exactly-once。
- 本 ADR 只完成 Task 訪談迴圈，不包含 O/P/K/S/A、公版比對、匯出與真正完成度判斷。
