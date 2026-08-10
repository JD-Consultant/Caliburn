# job_analysis — agent rules

`app/job_analysis` 是第一版產品唯一的 AI 工作面。Current JD authority 由本模組的 application 與 PostgreSQL current state 承擔，入口是 `/api/v1/job-analysis` 與 Web `/workspace`。跨 app 流程見 [`docs/design/task-analysis-engine.md`](../../../../docs/design/task-analysis-engine.md)。

## Layering

- `domain/` 只放純 domain、value objects 與不變量；不得 import FastAPI、SQLAlchemy 或 provider。
- `application/` 組合 domain transition、persistence ports、Context、LLM operation、verifier 與 employee decision；不負責 HTTP 或具體資料庫連線。
- `llm/` 定義 operation wire/schema 與 prompt mapping；`providers/` 實作 provider port，目前是 OpenRouter。
- `app/adapters/job_analysis_postgres/` 是 SQLAlchemy models、repositories、serialization；`app/api/job_analysis_deps.py` 集中 current route 的 composition。

## Authority rules

- 員工直接編輯與 AI Proposal 都經同一個 application authority commit；AI 只能提出候選，員工決策後才能改變 Current JD。
- provider 呼叫在 transaction 外；commit 前要重鎖文件並驗證 generation／read-set，避免覆蓋員工更新。
- 不建立第二份 document store，不把 transport DTO 當 domain truth，不讓 Web 重算 domain invariant。
- 目前沒有 legacy seam 可供相容；不要新增或恢復 OCS、interview、vNext、job_authoring 或通用 AI framework。

## Focused checks

修改本模組或其 seam 後，至少執行 `apps/api/tests/test_job_analysis_dependencies.py`、`tests/test_job_analysis_api.py`；動到 PostgreSQL adapter 再執行 `tests/test_job_analysis_api_postgres.py` 與相關 `test_job_analysis_*`。動到端到端流程，同步更新 [`docs/design/task-analysis-engine.md`](../../../../docs/design/task-analysis-engine.md)。
