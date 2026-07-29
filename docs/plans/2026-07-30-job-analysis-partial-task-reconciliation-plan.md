# Job Analysis Partial Task Reconciliation Implementation Plan

**Goal:** 讓員工只寫 Task 名稱／描述也能立即保存；後續 AI 可看見、追問，並以同一 ID 建立完整
Work Model Task 或提出員工可確認的移除 Proposal。

**Authority:** [ADR 0044](../adr/0044-partial-jd-task-reconciliation-and-human-confirmation.md)、
[研究紀錄](../specs/2026-07-29-job-analysis-partial-jd-task-reconciliation-research.md)。

**Scope:** 既有 `app/job_analysis` 與 PostgreSQL durable vertical。只改契約、Context、verifier、
transition、authoring／Proposal decisions 與相關文檔；不接 Web、不呼叫真實模型、不新增資料表，
不做自動 duplicate identity consolidation。

## 共同規則

- 每個 Task 先寫會失敗的關鍵測試，再做最小實作；每個 Task 綠後獨立 commit。
- 只保留保護文件權威、identity、reload 與 stale-input 的測試，不擴充大型矩陣。
- 不 import／整合舊 AI 路徑；不新增通用 reconciliation framework、alias、相似度配對或狀態機。
- 修改 durable vertical 時同步更新
  [`docs/design/task-analysis-engine.md`](../design/task-analysis-engine.md)。

## Task 1：最小契約與 schema

**修改：**

- `apps/api/app/job_analysis/domain/work_model.py`
- `apps/api/app/job_analysis/domain/proposal.py`
- `apps/api/app/job_analysis/llm/result.py`
- `apps/api/app/job_analysis/llm/provider_schema.py`
- `apps/api/app/job_analysis/llm/schemas/task_analysis_result.v1.json`
- `apps/api/tests/test_job_analysis_domain.py`
- `apps/api/tests/test_job_analysis_result_schema.py`

**完成條件：**

- `OpenIssue.reconciliation_task_id` 與 `WorkSignal.resolves_open_issue_ordinal` 可序列化、可 reload。
- Proposal 允許 JD-only withdraw 沒有 staged delta；其他 cross-layer action 護欄不變。
- 提供一個純函式，以「target 是否有未退休 Work Model Task」判斷 withdraw delta 是否一致。
- portable schema／golden 同步；非法 shape 有最小反例測試。

**Commit:** `feat(job-analysis): define partial reconciliation contracts`

## Task 2：Context、prompt 與 deterministic verifier

**修改：**

- `apps/api/app/job_analysis/application/context.py`
- `apps/api/app/job_analysis/application/verifier.py`
- `apps/api/app/job_analysis/llm/prompt.py`
- `apps/api/tests/test_job_analysis_context.py`
- `apps/api/tests/test_job_analysis_verifier.py`
- `apps/api/tests/test_job_analysis_operation.py`

**完成條件：**

- JD-only Task 只出現在 open-issue projection，含穩定 reference、目前 JD 內容與上次提問。
- pending／deferred withdraw 可從 Proposal 關聯推導並顯示，不新增 issue status。
- verifier 只允許 `no_match + add` 或 `exclude` 解決該 issue；錯 ordinal、重複解決與其他 relation/action
  均拒絕。
- prompt 明示 duplicate／overlap／uncertain 要追問，不得自動換 ID 或 merge。

**Commit:** `feat(job-analysis): expose partial tasks to analysis`

## Task 3：純 transition 與 Proposal 產生

**修改：**

- `apps/api/app/job_analysis/application/transition.py`
- `apps/api/tests/test_job_analysis_transition.py`
- `apps/api/tests/test_job_analysis_smoke.py`

**完成條件：**

- `no_match + add` 沿用 JD `task_id`、合併既有 issue anchors 與本輪 anchors，並移除 issue。
- target ID 已存在於任何 Work Model Task（含 retired）時拒絕。
- AI 建議文字不同時只建 revise Proposal，Current JD 不變。
- `exclude` 建立 ExcludedSignal 與 JD-only withdraw Proposal，不移除 JD 或 issue。
- 若 next question 指向既有 issue，同一 transition 保存 consultant turn ID 到
  `last_asked_turn_id`。

**Commit:** `feat(job-analysis): reconcile partial tasks in transitions`

## Task 4：持久 authoring、決策與 reload

**修改：**

- `apps/api/app/job_analysis/application/authoring.py`
- `apps/api/app/job_analysis/application/proposal_decisions.py`
- `apps/api/app/job_analysis/application/durable_turn.py`
- `apps/api/tests/test_job_analysis_authoring_postgres.py`
- `apps/api/tests/test_job_analysis_proposal_decisions_postgres.py`
- `apps/api/tests/test_job_analysis_durable_turn_postgres.py`
- `apps/api/tests/test_job_analysis_durable_smoke.py`
- `docs/design/task-analysis-engine.md`

**完成條件：**

- direct add 建立 `insufficient_evidence` issue 並存 explicit JD task reference；edit 保留，delete 清除。
- 接受會移除 JD Task 的 Proposal 時同步清除 dangling issue。
- Proposal 建立與接受共用 withdraw-delta predicate；在 lock 下現況不符時轉 stale，不覆寫較新的
  retirement。
- 關閉／重開後仍能由同一 issue、同一 JD Task identity 與上次提問繼續。

**Commit:** `feat(job-analysis): persist partial task reconciliation`

## 最終驗證

- focused `test_job_analysis_*.py`
- `uv run pytest` 全套；只接受與 baseline 相同的既有無關失敗
- `git diff --check`
- 更新本計畫狀態與端到端設計，同一 commit 收尾；不 push
