# 0044. 不完整 JD Task 的明確對齊與員工確認

- 狀態：Accepted
- 日期：2026-07-30
- 補充：[0043](0043-job-analysis-local-current-state-persistence-and-authoring-authority.md)
- 研究：
  [不完整 JD Task 與同一 identity 對齊研究](../specs/2026-07-29-job-analysis-partial-jd-task-reconciliation-research.md)

## 脈絡

員工可以直接新增只有名稱／描述的 Current JD Task，其他分析欄位暫時留空。這筆內容必須立即保存，
但不能為了滿足 Work Model 契約而補造假 Task。後續 AI 又必須能看到它、追問缺口，並把分析結果
對回同一筆 JD identity。

文字相似度不能可靠決定兩筆工作是否相同；AI 也不得在員工未確認時靜默合併或刪除 Current JD。
既有 Proposal 契約另假設 withdraw 一定有 Work Model delta，無法表達只存在於 JD 的 Task。

## 決定

- Current JD Task 只要求非空 `statement`；其他第一版分析欄位可空。
- 直接新增的 JD-only Task 不建立空殼 Work Model Task。`OpenIssue` 以 nullable
  `reconciliation_task_id` 明確指向該 JD Task，初始原因是 `insufficient_evidence`。
- Context Packet 投影該 JD Task、來源、上次提問及相關 pending／deferred Proposal；不把它偽裝成
  active Work Model Task，也不新增 issue status。
- 模型結果可用 `resolves_open_issue_ordinal` 關閉 issue。第一版只接受：
  `no_match + add`，或帶合法原因的 `exclude`。
- `no_match + add` 由 application 以原 JD `task_id` 建立完整 Work Model Task；若建議文字與 JD
  不同，只建立普通 revise Proposal，不直接改 JD。
- `duplicate`、`overlap`、`uncertain` 不自動換 ID、merge 或關閉 issue；保留 issue 並向員工追問。
  本 ADR 不建立 alias、文字相似度配對或通用 identity consolidation。
- `exclude` 不靜默刪除 JD，而是建立員工可見的 withdraw Proposal。Proposal pending／deferred
  期間 issue 保留且 agenda 不重問；接受移除 JD 後清掉 issue，拒絕或 stale 則保留。
- withdraw 是否需要 `staged_work_model_delta` 由同一個純判斷決定：target 有未退休 Work Model
  Task 時必須有 delta；完全不存在或已退休時必須沒有 delta。建立與接受均在各自 authority
  snapshot／document lock 下重驗，不一致即 stale。
- 員工直接編輯與刪除仍立即保存且不呼叫 LLM。送出的追問須持久保存並更新
  `last_asked_turn_id`，確保 reload 後可繼續。

## 後果

正面：

- 員工可先寫一個不完整 Task，AI 之後再問，不會因 schema 需要而補造內容。
- JD identity 可跨關閉／重開延續；AI 的改善仍經 Proposal，由員工掌握文件。
- JD-only 移除不需要假 Work Model Task，也不放寬已存在 Work Model Task 的 retirement 護欄。

成本：

- domain／LLM result 各增加一個 nullable reference，Context、verifier、transition 與 durable
  決策需同步升級。
- Proposal 值物件無法單獨判斷 target 是否存在於 Work Model；application 建立端與接受端必須
  共用並重驗同一條規則。

風險：

- 第一版不自動收斂 duplicate／overlap identity；模型可以追問，員工可以編輯，但不得宣稱完整
  identity matching 已完成。
- deterministic verifier 只能驗引用與動作形狀；Task 是否成立、是否 duplicate／overlap 仍是
  rubric 與員工判斷。
