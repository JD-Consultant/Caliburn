# Task 4 實作報告 — 簡化 pending review 與失敗恢復

日期：2026-08-26
Worktree：`S:\\caliburn\\.worktrees\\shared-current-jd`
Branch：`codex/shared-current-jd`

## 結果

Task 4 已完成，範圍維持在 contract/domain、API projection/command 與既有 Web component；沒有實作 Task 5 的自然語言 lineage，也沒有擴大到 Task 6+ layout、framework、RAG 或 auto mode。

- public review decision 只剩 `accept_changes`、`edit_and_accept_changes`、`reject_changes`。
- pending 只代表 current working document 與 approved baseline 的尚未決定差異；不再有 defer lifecycle，員工可以繼續聊天、關閉或下次回來再決定。
- public review 移除 `deferred` count/status、`blocked_branches`、`safe_interview_work_available`、`decision_required_before_more_interview` 與 `explanation`。
- run failure 仍顯示「重試同一則回答」，但正常 textbox／送出保持可用；新文字使用新的 answer command，不會變成舊訊息的 retry。
- 主對話移除逐段「更正這段原話」與 `correctionSourceId` mode。既有 Store source lineage 與 optional supersession capability 保留給 Task 5。
- `required_clarification` 的 interrupt、answer route、snapshot 與 Web answer card 均保留，仍是獨立的硬阻擋；一般 Gap/pending review 沒有升格為 blocker。

## RED／GREEN

### Contract/domain RED

先修改 failing tests，再執行舊 production code：

- contract：`1 failed, 6 passed`；generated `DocumentReviewView` 仍要求已移除的 blocker fields。
- API workspace review／authority／understanding：`2 failed, 40 passed`；舊 enum 仍含 `defer`，progress 仍輸出 `deferred: 0`。

### Web RED

先更新 component fixture／expectation，再執行舊 component：`15 failed`；失敗集中在 deferred label、`blocked_branches` schema 讀取，以及 failure 時 textarea 被禁用，符合本 Task 要拆除的行為。

### GREEN

- `packages/job-analysis-contract`：`uv run pytest tests/test_consultant_contract.py -q` → **7 passed**。
- `apps/api` focused：
  `uv run pytest tests/test_consultant_workspace_review.py tests/test_consultant_workspace_authority.py tests/test_consultant_understanding_and_sufficiency.py tests/test_consultant_api_mapper.py tests/test_consultant_workspace_backend.py tests/test_consultant_api.py -q` → **80 passed**。
- `apps/web` focused：
  `npm run test -- ConsultantWorkspace.integration.test.tsx consultantWorkspaceModel.test.ts` → **28 passed**。
- `apps/web`：`npx tsc --noEmit` → **pass**；`npm run lint` → **pass**。
- `npm run check-codegen -w @caliburn/job-analysis-contract` → **pass**。
- `git diff HEAD --check` → **pass**；Windows LF→CRLF 與 pytest cache `WinError 5` 只有環境 warnings，沒有 product/test failure。

## 主要檔案

- Contract SSOT／生成：`packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`、生成的 Python／TypeScript models、package exports、contract tests。
- API/domain：`state.py`、`workspace_review.py`、`workspace_authority.py`、`understanding.py`；snapshot view／mapper／route 同步移除 public blocker 與 defer mapping。
- API tests：workspace review／authority／understanding／mapper／backend，以及既有 durable authority fixture 對齊三種 decision。
- Web：`ConsultantConversation.tsx`、`DocumentReviewPanel.tsx`、`ConsultantInsightPanel.tsx`、`consultantWorkspaceModel.ts` 與其 fixtures／integration tests。

## 歷史 probe 確認

`apps/api/consultant_purpose_conformance_spike.py` 是早期 purpose-conformance 的可丟棄驗證程式，不在 current production import／composition root。產品研究明示其為「可丟棄證據，不得直接搬進 production」，repo 引用也只在歷史 plan/spec。故其中舊 `deferred` 字樣沒有改動，避免把歷史 probe 誤納入 Task 4 production 範圍。

## 收尾

指定 commit：`refactor: simplify pending review and failure recovery`
本 Task 不 push、merge 或 tag。
