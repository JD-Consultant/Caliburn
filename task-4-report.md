# Task 4 report — Header 作為 Task Analysis 背景

## 結果

`JdHeader.competency_name` 與 `work_description` 現在只會決定性投影到 Task Analysis dynamic packet 的「員工填寫的整體描述」區。該區納入 authority read-set，但不帶 ordinal、`SourceRef` 或 Evidence，也不進 verifier context 或 OPKS。

Controller 更正後，`TASK_ANALYSIS_INSTRUCTIONS` 保持逐字不變；核定句只在 overview 有內容時緊鄰該區渲染。空 Header 不產生該區或該句。

## RED / GREEN 證據

- RED：`uv run pytest tests/test_job_analysis_context.py tests/test_job_analysis_prompt.py tests/test_job_analysis_opks_context.py -q` 先因缺少 overview field／rendering 與 static prompt 暫存變更失敗。
- GREEN：同一 focused gate 最終為 `62 passed`；並以 `git diff --exit-code -- app/job_analysis/llm/prompt.py` 驗證 static prompt zero diff。
- 完整 API：`DEBUG=false uv run pytest -q` 為 `1824 passed, 309 skipped`。
- PostgreSQL stale regression：`DEBUG=false uv run pytest tests/test_job_analysis_durable_turn_postgres.py -k header_change_after_prepare -q` 在此環境為 `1 skipped, 8 deselected`；測試已加入，但本機 PostgreSQL fixture 不可用。

## 檔案

- `apps/api/app/job_analysis/application/context.py`
- `apps/api/app/job_analysis/application/durable_turn.py`
- `apps/api/tests/test_job_analysis_context.py`
- `apps/api/tests/test_job_analysis_durable_turn_postgres.py`
- `apps/api/tests/test_job_analysis_opks_context.py`
- `apps/api/tests/test_job_analysis_prompt.py`
- `docs/design/task-analysis-engine.md`
- `docs/plans/2026-08-09-reviewed-job-analysis-slices-migration-plan.md`

## 關切事項

唯一未在本工作區實跑的是真 PostgreSQL stale snapshot regression；完整 API suite 的 PostgreSQL-dependent tests 同樣依環境 skip。其餘 Task 4 gate 均已通過。
