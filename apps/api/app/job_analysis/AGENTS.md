# job_analysis — agent rules

`app/job_analysis` 是現行第一版產品的工作面。Current JD authority 由這個模組的 application
transition 與 PostgreSQL current state 承擔，入口是 `/api/v1/job-analysis` 與 Web `/workspace`。
跨 app 端到端流程見 [`docs/design/task-analysis-engine.md`](../../../../docs/design/task-analysis-engine.md)。

## Layering

- `domain/` 只放純 domain、value objects 與不變量；不得 import FastAPI、SQLAlchemy、provider SDK、
  `app.interview`、`app.interview_vnext`、`app.job_authoring` 或 `evals`。
- `application/` 組合 domain transition、persistence ports、Context、LLM operation、verifier 與
  employee decision；它不負責 HTTP 或具體資料庫連線。
- `llm/` 定義 operation wire/schema 與 prompt mapping；`providers/` 實作 provider port（目前是
  OpenRouter），不可把 provider 細節倒灌 domain。
- PostgreSQL 實作位於 `app/adapters/job_analysis_postgres.py`；current route 的依賴組裝集中在
  `app/api/job_analysis_deps.py`，不可回塞 shared/legacy `app/api/deps.py`。

## Authority rules

- 員工直接編輯與 AI Proposal 都經同一個 application authority commit；AI 只能提出候選，員工決策後
  才能改變 Current JD。
- 不讀、不搬、不雙寫 `app.interview`、`app.interview_vnext`、`app.job_authoring` 或 legacy OCS
  document state。不要為了共用而包裝 legacy AI chain。
- 新 API／共用 DTO 先核對 [`docs/contract-strategy.md`](../../../../docs/contract-strategy.md)；
  job-analysis wire shape 由 `packages/job-analysis-contract/schema/` 的 JSON Schema 定義。

## Focused checks

修改本模組或其 seam 後，至少執行 `apps/api/tests/test_job_analysis_dependencies.py`、
`tests/test_job_analysis_api.py`；動到 PostgreSQL adapter 再執行
`tests/test_job_analysis_api_postgres.py` 與相關 `test_job_analysis_*`。若變更端到端流程，
同步更新 [`docs/design/task-analysis-engine.md`](../../../../docs/design/task-analysis-engine.md)。
