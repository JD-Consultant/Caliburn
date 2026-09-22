# apps/api 深文檔

> **歷史文件（2026-09-22 退役）：**`apps/api` 的可執行程式已移除，本頁只供追溯舊架構。現行產品與操作入口見 [`experiments/jd-relational-app`](../../../experiments/jd-relational-app/README.md) 及 [`docs/runbook.md`](../../../docs/runbook.md)。

退役前 API 只有 Job Analysis。跨 app 端到端流程見 [`docs/design/task-analysis-engine.md`](../../../docs/design/task-analysis-engine.md)；架構決策見 [`docs/adr/0057-current-only-runtime-and-data-boundary.md`](../../../docs/adr/0057-current-only-runtime-and-data-boundary.md)。

修改 `app/core`、`app/documents`、`app/task_analysis`、`app/opks`、`app/consultation`、`app/export`、PostgreSQL adapter、HTTP route 或 Web seam 時，請同 commit 更新對應設計文檔與測試。已刪除的 OCS／interview 深文檔不再保留在 app docs，歷史研究只在 `docs/archive/`、`docs/specs/` 與 ADR 中作追溯資料。
